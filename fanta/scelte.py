"""La formazione scelta a mano per una giornata ("la mia scelta"): resta sul server, così si ritrova da ogni dispositivo
e un domani si potrà confrontare con quella consigliata. Un file solo, una voce per giornata."""
from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path

from . import etichette
from .percorsi import RADICE, chiavi_vecchie, scrivi_sicuro
from .punteggio import modulo_valido

FILE_SCELTE = RADICE / "dati" / "scelte.json"
MAX_GIORNATE = 60
TIPO_AUTOMATICA = "automatica"
NESSUNA, VALIDA, NON_VALIDA = "nessuna", "valida", "non_valida"      # `stato_scelta` di GET /api/formazione
DA_WEB, DA_APP = "web", "app"          # campo `da` della scelta salvata: da dove arriva il salvataggio (vedi `salva`)
DA = (DA_WEB, DA_APP)
_blocco = threading.Lock()


def motivo_non_valida(titolari, ruoli: dict[int, str], regole) -> str | None:
    """Perché questi titolari non si possono schierare (frase per l'utente), o None se si può. `ruoli`: {id: ruolo} dei giocatori
    della rosa che si possono schierare. Servono 11 titolari diversi, tutti lì, con un portiere e un modulo ammesso dalla lega.
    È la regola unica della scelta: la usano la Formazione (`consigli.valuta`), Oggi, la giornata in diretta, il riepilogo e il
    Diario. Una scelta salvata che non la rispetta più (giocatore ceduto, ruolo o moduli della lega cambiati) non conta: vale la
    consigliata, come quando non hai salvato niente."""
    try:
        scelti = list(dict.fromkeys(int(i) for i in titolari))
    except (TypeError, ValueError):                              # file rovinato: non è una formazione
        scelti = []
    if len(scelti) != 11 or any(i not in ruoli for i in scelti):
        return "Servono 11 titolari diversi, tutti della rosa"
    conta = {r: sum(1 for i in scelti if ruoli[i] == r) for r in "PDCA"}
    if conta["P"] != 1 or not modulo_valido(conta["D"], conta["C"], conta["A"], regole):
        return f"Il modulo {conta['D']}-{conta['C']}-{conta['A']} con {conta['P']} portieri non è ammesso nella tua lega"
    return None


def stato(scelta: dict | None, ruoli: dict[int, str], regole) -> str:
    """`nessuna` (niente salvato dall'utente), `valida` (la scelta salvata vale) o `non_valida` (c'è, ma non si può più schierare:
    vale la consigliata). `scelta`: quella di `leggi` (la copia automatica non è una scelta dell'utente)."""
    if not (isinstance(scelta, dict) and isinstance(scelta.get("titolari"), list)):
        return NESSUNA
    return NON_VALIDA if motivo_non_valida(scelta["titolari"], ruoli, regole) else VALIDA


def che_vale(scelta: dict | None, ruoli: dict[int, str], regole) -> dict | None:
    """La scelta (quella di `leggi`) se si può schierare, altrimenti None: una scelta che non vale più conta come nessuna scelta e
    vale la consigliata. La usano gli avvisi (promemoria, «cambia la formazione», «cambio pronto», riepilogo) e «Da fare»."""
    return scelta if stato(scelta, ruoli, regole) == VALIDA else None


# ---------------------------------------------------------------- anticipi già cominciati (#373)
# Un anticipo (turno.py) non fissa la scadenza: la formazione resta aperta, ma nella lega chi gioca una partita già cominciata non si
# sposta più. Rispetto alla formazione che vale in quel momento (la scelta salvata se vale, altrimenti la consigliata) chi era
# titolare resta titolare e chi non lo era non entra. «Cominciata» è la regola della consigliata (`consigli._anticipi_iniziati`, #368).
class GiocatoreBloccato(ValueError):
    """Un salvataggio sposta un giocatore di una partita già cominciata: 400 con la frase per l'utente e `codice`."""
    codice = "giocatore_bloccato"


def bloccati(schede: dict, squadre) -> list[int]:
    """Gli id (in ordine) dei giocatori delle `schede` della Formazione ({id: scheda}) che giocano per una delle `squadre` di Serie A
    con un anticipo già cominciato: il campo `bloccati` di GET /api/formazione. Vuoto senza anticipi cominciati."""
    if not squadre:
        return []
    return sorted(int(x["id"]) for x in schede.values() if isinstance(x, dict) and "id" in x and x.get("squadra") in squadre)


def controlla_bloccati(fermi, prima, nuovi, nomi: dict[int, str]) -> None:
    """GiocatoreBloccato se i titolari `nuovi` spostano uno dei `fermi` (id di `bloccati`) rispetto ai titolari `prima` della
    formazione che vale adesso: esce un titolare o entra chi non lo era. `nomi`: {id: nome} per la frase."""
    prima, nuovi = {int(i) for i in prima}, {int(i) for i in nuovi}
    for i in fermi:
        if (i in prima) != (i in nuovi):
            raise GiocatoreBloccato(f"{nomi.get(i) or 'Un giocatore'} gioca in una partita già cominciata: non si può più spostare.")


# ---------------------------------------------------------------- «Metti in campo» (#643)
NON_ENTRANO = ("infortunato", "squalificato")      # stato del giocatore (etichette.codice) che non si mette in campo


def chi_lascia_il_posto(entra: int, titolari, schede: dict, regole, fermi=()) -> list[dict]:
    """Chi può lasciare il posto a `entra`, un giocatore delle `schede` della Formazione ({id: scheda}) che non è fra i `titolari`:
    i titolari che, tolti per far entrare lui, lasciano una formazione schierabile per la regola unica della scelta
    (`motivo_non_valida`: lo stesso ruolo, oppure un altro modulo ammesso dalla lega). Per ognuno {esce, modulo, cambia_modulo,
    differenza}: il modulo dopo il cambio e i punti attesi di chi entra meno quelli di chi esce (lo stesso numero di «Sostituisci»
    dalla scheda del titolare, con il segno girato), il cambio migliore in cima. Vuoto se `entra` è già titolare, non è nelle
    schede, è fra i `fermi` (anticipo già cominciato, `bloccati`), infortunato o squalificato; i fermi non escono."""
    sch = {int(k): x for k, x in schede.items() if isinstance(x, dict)}
    dentro = [int(i) for i in titolari]
    fermi = {int(i) for i in fermi}
    nuovo = sch.get(int(entra))
    if nuovo is None or int(entra) in dentro or int(entra) in fermi or etichette.codice(nuovo) in NON_ENTRANO:
        return []
    ruoli = {i: x.get("ruolo") for i, x in sch.items()}
    modulo = lambda ids: "-".join(str(sum(1 for i in ids if ruoli[i] == r)) for r in "DCA")     # noqa: E731
    prima = modulo(dentro) if motivo_non_valida(dentro, ruoli, regole) is None else None
    uscite = []
    for esce in dentro:
        dopo = [int(entra) if i == esce else i for i in dentro]
        if esce in fermi or motivo_non_valida(dopo, ruoli, regole):
            continue
        uscite.append({"esce": esce, "modulo": modulo(dopo), "cambia_modulo": modulo(dopo) != prima,
                       "differenza": round(float(nuovo["punti_attesi"]) - float(sch[esce]["punti_attesi"]), 2)})
    return sorted(uscite, key=lambda u: -u["differenza"])


def ruoli_schierabili(rose, prev=None) -> dict[int, str]:
    """{id: ruolo} dei giocatori della tua rosa che si possono schierare, per `motivo_non_valida`. Con le previsioni della giornata
    da giocare (`prev`) come la Formazione: solo chi ne ha una, con il ruolo delle previsioni. Senza (giornata finita) tutta la
    rosa con il suo ruolo, come il Diario e il riepilogo di Oggi."""
    s = rose.squadra(rose.mia_squadra or "") if rose is not None else None
    ruoli = {}
    for g in (s.giocatori if s else []):
        if g.id is None:
            continue
        i = int(g.id)
        if prev is None:
            ruoli[i] = g.ruolo
        elif i in prev.index:
            ruoli[i] = str(prev.at[i, "ruolo"])
    return ruoli


def _tutte(percorso: Path | None = None) -> dict:
    try:
        d = json.loads((percorso or FILE_SCELTE).read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def leggi(stagione: str, giornata: int, percorso: Path | None = None, anche_automatica: bool = False) -> dict | None:
    """La scelta dell'utente per la giornata. La copia salvata in automatico dal programma (tipo «automatica») non è una scelta
    dell'utente: si vede solo con `anche_automatica=True`."""
    v = _tutte(percorso).get(f"{stagione}/{giornata}")
    if not (isinstance(v, dict) and isinstance(v.get("titolari"), list)):
        return None
    return v if anche_automatica or v.get("tipo") != TIPO_AUTOMATICA else None


def _stessi_titolari(prima, titolari: list[int]) -> bool:
    """La scelta di prima è dell'utente (non la copia automatica) e ha gli stessi 11 (l'ordine non conta)."""
    return (isinstance(prima, dict) and prima.get("tipo") != TIPO_AUTOMATICA
            and isinstance(prima.get("titolari"), list) and set(prima["titolari"]) == set(titolari))


def _messa(prima, titolari: list[int], messa: bool | None, adesso: str) -> str | None:
    """Quando l'utente ha detto «L'ho messa» per questi titolari, o None se non l'ha detto. `messa` vero: adesso (o il momento di
    prima, se gli 11 sono gli stessi e l'aveva già detto); falso: mai; None (chi salva non dice niente, per esempio un client di
    prima): resta com'era finché gli 11 sono gli stessi della scelta dell'utente di prima, perché nell'app della lega c'è ancora
    quella formazione; con un titolare diverso cade."""
    if messa is False:
        return None
    if _stessi_titolari(prima, titolari) and prima.get("messa") is True:
        return prima.get("messa_il") or adesso
    return adesso if messa else None


def salva(stagione: str, giornata: int, titolari: list[int], modulo: str, percorso: Path | None = None, tipo: str = "manuale",
          panchina: list[int] | None = None, era_consigliata: bool = False, messa: bool | None = None, da: str | None = None) -> dict:
    """Salva la scelta dell'utente. `tipo`: «manuale» (scelta a mano, anche quando non c'è il campo: file vecchi) o «consigliata»
    (ha detto «ho schierato la consigliata»). `panchina` (facoltativa, per le giornate importate): gli id della panchina nell'ordine
    in cui l'hai schierata; senza, il Diario sceglie la panchina da solo. `era_consigliata`: gli 11 erano quelli della consigliata nel
    momento in cui li hai salvati («Salva questa»): «Da fare» allora non propone cambi (#333). Il campo si scrive solo se è vero e il
    `tipo` resta «manuale», così il Diario e i client di prima non vedono differenze. Chi chiama lo ricalcola a ogni salvataggio sulla
    consigliata di adesso: se gli 11 sono gli stessi della scelta di prima, che lo aveva, resta vero (la consigliata può essere
    cambiata nel frattempo, la formazione salvata no: per esempio quando si mette o si toglie la spunta «L'ho messa»).
    `messa` («L'ho messa», #616): l'utente dice di aver messo questi 11 nell'app della lega. Nella voce diventa `messa: true` con
    `messa_il` (quando l'ha detto), scritti solo se vero. None = chi salva non dice niente: vedi `_messa`.
    `da` (#639): da dove arriva il salvataggio, «web» o «app» (l'app nativa); scritto solo se è uno dei due. Lo usa il promemoria
    (`notifiche._gia_schierato`): web e iPhone hanno la spunta «L'ho messa» e una loro scelta la chiede; le scelte senza `da`
    (salvate prima del 13/11) no."""
    with _blocco:
        tutte = _tutte(percorso)
        adesso = datetime.now().isoformat(timespec="seconds")
        voce = {"titolari": [int(i) for i in titolari], "modulo": modulo, "salvata": adesso, "tipo": tipo}
        prima = tutte.get(f"{stagione}/{giornata}")
        if era_consigliata or (_stessi_titolari(prima, voce["titolari"]) and prima.get("era_consigliata") is True):
            voce["era_consigliata"] = True
        if panchina:
            voce["panchina"] = [int(i) for i in panchina][:20]
        messa_il = _messa(prima, voce["titolari"], messa, adesso)
        if messa_il:
            voce["messa"], voce["messa_il"] = True, messa_il
        if da in DA:
            voce["da"] = da
        tutte[f"{stagione}/{giornata}"] = voce
        for vecchia in chiavi_vecchie(tutte, MAX_GIORNATE):
            tutte.pop(vecchia, None)
        scrivi_sicuro(percorso or FILE_SCELTE, json.dumps(tutte))
        return voce


def salva_automatica(stagione: str, giornata: int, titolari: list[int], modulo: str, percorso: Path | None = None) -> bool:
    """Ricorda la formazione consigliata come copia automatica, ma solo se l'utente non ha già una sua scelta per la giornata.
    True se ha scritto qualcosa (la copia cambia finché la formazione non si chiude)."""
    with _blocco:
        tutte = _tutte(percorso)
        chiave = f"{stagione}/{giornata}"
        attuale = tutte.get(chiave)
        if isinstance(attuale, dict) and attuale.get("tipo") != TIPO_AUTOMATICA and isinstance(attuale.get("titolari"), list):
            return False
        nuovi = [int(i) for i in titolari]
        if isinstance(attuale, dict) and attuale.get("titolari") == nuovi and attuale.get("modulo") == modulo:
            return False
        tutte[chiave] = {"titolari": nuovi, "modulo": modulo, "salvata": datetime.now().isoformat(timespec="seconds"), "tipo": TIPO_AUTOMATICA}
        for vecchia in chiavi_vecchie(tutte, MAX_GIORNATE):
            tutte.pop(vecchia, None)
        scrivi_sicuro(percorso or FILE_SCELTE, json.dumps(tutte))
        return True


def cancella(stagione: str, giornata: int, percorso: Path | None = None) -> None:
    with _blocco:
        tutte = _tutte(percorso)
        if tutte.pop(f"{stagione}/{giornata}", None) is not None:
            scrivi_sicuro(percorso or FILE_SCELTE, json.dumps(tutte))
