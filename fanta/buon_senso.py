"""Buon senso sui consigli di mercato: svincolati (Mercato > Consigliati, «Da fare» di Oggi, widget) e scambi in «Da fare».

I soli numeri producono consigli che sembrano stupidi: «svincola il tuo attaccante da 200 crediti, fermo due settimane, per una
riserva di un'altra squadra» per pochi decimi di punto a giornata. Qui stanno, tutte insieme e con un nome, le regole che un
fantallenatore applica a mente prima di proporre un cambio. Ogni regola è una funzione piccola che dice «va bene» oppure il
motivo, in una frase, per cui no. Il modello (`modello.py`) non cambia: queste regole scelgono solo cosa vale la pena dire.

Regolamento (lettere come nella richiesta che l'ha originato):
 (a) il guadagno deve essere significativo: almeno SOGLIA_BREVE[ruolo] punti sommati sulle giornate dell'orizzonte (5) e positivo
     in almeno QUOTA_GIORNATE_POSITIVE di esse. Le soglie sono per ruolo, circa metà del normale su e giù del fantavoto di un
     giocatore di quel ruolo in 5 giornate (gli attaccanti oscillano di più dei difensori).
 (b) chi entra deve giocare davvero: probabilità di voto nella prossima giornata >= P_MIN_ENTRA, parte titolare quando c'è
     (quota_titolare >= QUOTA_TITOLARE_MIN_ENTRA) ed è continuo sul lungo periodo (p_lungo >= P_LUNGO_MIN_ENTRA, oppure le
     probabili lo danno titolare con almeno PERCENTUALE_TITOLARE_SICURO %). Niente infortunati, squalificati o in dubbio.
 (c) chi esce non si svincola se è un titolare utile: quando c'è parte titolare (quota_titolare >= QUOTA_TITOLARE_PROTETTA) e vale
     almeno quanto chi entra (mu) e non manca da settimane (p_lungo >= P_LUNGO_MIN_DO): la sua assenza di oggi passa. Un infortunio è «breve» se la nota delle probabili non parla
     di mesi, stagione, legamenti, fratture, operazioni (PAROLE_INFORTUNIO_LUNGO). Un giocatore pagato molto (costo >=
     QUOTA_COSTO_PROTETTO dei crediti iniziali) non si svincola (si riavrebbe solo il rimborso) a meno che sia ormai una riserva
     (quota_titolare < QUOTA_TITOLARE_FLOP) o fermo a lungo.
 (d) crediti: il cambio deve essere fattibile (crediti + rimborso >= quotazione di chi entra); lo calcola `gestione.mercato`.
 (e) coerenza: stesso ruolo per costruzione; il calendario è già dentro i punti attesi per giornata, non si somma due volte.
 (f) niente ripensamenti: chi è arrivato nella tua rosa da meno di GIORNI_RIPENSAMENTO giorni non si propone in uscita, chi l'hai
     lasciato libero da meno di GIORNI_RIPENSAMENTO giorni non si ripropone in entrata (dai movimenti registrati). Nella stessa
     lista uno stesso giocatore non compare in due consigli diversi.
 (g) al massimo MAX_CONSIGLI consigli (dubbi, coperture, svincolati, scambi) in «Da fare», ognuno con il perché in una frase; se non
     c'è niente di utile la lista resta vuota e il client scrive «Nessuna azione utile oggi».
Gli scambi («Da fare») seguono (a), (b) per chi ricevo, (c) per chi do, (f) e in più (h): chi do deve essere giocabile per
l'altra squadra (p_lungo >= P_LUNGO_MIN_DO), perché nessuno accetta un infortunato in cambio di un titolare.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

from .frasi import F, elenco

# (a) guadagno significativo: punti sommati sulle giornate dell'orizzonte (scambi.ORIZZONTE = 5)
SOGLIA_BREVE = {"P": 2.0, "D": 2.0, "C": 2.5, "A": 3.0}
QUOTA_GIORNATE_POSITIVE = 0.6
# (b) chi entra
P_MIN_ENTRA = 0.75
QUOTA_TITOLARE_MIN_ENTRA = 0.6
P_LUNGO_MIN_ENTRA = 0.6
PERCENTUALE_TITOLARE_SICURO = 75.0
# (c) chi esce
QUOTA_TITOLARE_PROTETTA = 0.6
QUOTA_COSTO_PROTETTO = 0.08          # 8% dei crediti iniziali (40 su 500)
QUOTA_TITOLARE_FLOP = 0.4
PAROLE_INFORTUNIO_LUNGO = ("stagione", "mesi", "crociato", "legament", "frattur", "operazion", "intervent", "achille", "menisco", "lungo stop")
# (f) ripensamenti
GIORNI_RIPENSAMENTO = 21
# (g) quanti consigli in «Da fare»
MAX_CONSIGLI = 3
# (h) scambi: chi do deve essere giocabile per chi lo riceve
P_LUNGO_MIN_DO = 0.4

FUORI = ("infortunato", "squalificato")
CAMPI = ("nome", "ruolo", "squadra", "p_voto", "quota_titolare", "p_lungo", "stato", "nota", "percentuale", "mu", "dubbio")


def _num(x: float) -> str:
    return f"{x:.1f}".replace(".", ",")


def _pc(x: float) -> int:
    return round(100 * float(x))


def _nome_squadra(y: dict) -> str:
    """Il nome della squadra (Roma, Milan...) per «titolare fisso (Roma)»: niente articolo, che cambia da squadra a squadra
    (la Roma, il Milan, l'Inter). Vuoto se non si sa."""
    return str(y["squadra"]).capitalize() if y.get("squadra") else ""


# ---------------------------------------------------------------- profili dei giocatori
def profili(prev: pd.DataFrame | None) -> dict[int, dict]:
    """Da una tabella di previsioni (consigli.previsioni) a un dizionario leggero id -> {campi che servono alle regole}."""
    if prev is None or prev.empty:
        return {}
    presenti = [c for c in CAMPI if c in prev.columns]
    out: dict[int, dict] = {}
    for i, riga in zip(prev.index, prev[presenti].to_dict("records")):
        r = {k: (None if isinstance(v, float) and pd.isna(v) else v) for k, v in riga.items()}
        out[int(i)] = r
    return out


def infortunio_lungo(nota: str | None) -> bool:
    """La nota delle probabili parla di uno stop lungo (mesi, stagione finita, legamenti...)?"""
    if not nota:
        return False
    testo = str(nota).lower()
    return any(p in testo for p in PAROLE_INFORTUNIO_LUNGO)


# ---------------------------------------------------------------- le regole, una per funzione
def guadagno_significativo(per_giornata: list[float], ruolo: str) -> str | None:
    """(a) Il motivo per cui il guadagno NON basta, oppure None se basta."""
    if not per_giornata:
        return F("senso.nessuna_giornata")
    breve = sum(per_giornata)
    soglia = SOGLIA_BREVE.get(ruolo, max(SOGLIA_BREVE.values()))
    positive = sum(1 for x in per_giornata if x > 0) / len(per_giornata)
    n = len(per_giornata)
    if breve < soglia or positive < QUOTA_GIORNATE_POSITIVE:
        return F("senso.differenza_piccola", punti=round(breve, 1), giornate=F("tempo.giornate", n=n))
    return None


def entra_affidabile(y: dict | None) -> str | None:
    """(b) Il motivo per cui chi entra NON è un acquisto sensato, oppure None."""
    if not y:
        return None                                    # senza profilo non si può giudicare: la regola non si applica
    nome = y.get("nome", "Chi entra")
    stato = y.get("stato")
    if stato in FUORI:
        return F("senso.entra_squalificato" if stato == "squalificato" else "senso.entra_infortunato", nome=nome)
    if y.get("dubbio"):
        return F("senso.entra_dubbio", nome=nome)
    p = float(y.get("p_voto") or 0)
    quota = float(y.get("quota_titolare") or 0)
    lungo = float(y.get("p_lungo") or 0)
    squadra = _nome_squadra(y)
    if p < P_MIN_ENTRA:
        return F("senso.entra_non_sicuro", nome=nome, p=_pc(p))
    if quota < QUOTA_TITOLARE_MIN_ENTRA:
        return (F("senso.entra_non_titolare_sq", nome=nome, squadra=squadra, p=_pc(quota)) if squadra
                else F("senso.entra_non_titolare", nome=nome, p=_pc(quota)))
    titolare_oggi = stato == "titolare" and float(y.get("percentuale") or 0) >= PERCENTUALE_TITOLARE_SICURO
    if lungo < P_LUNGO_MIN_ENTRA and not titolare_oggi:
        return (F("senso.entra_discontinuo_sq", nome=nome, squadra=squadra, p=_pc(lungo)) if squadra
                else F("senso.entra_discontinuo", nome=nome, p=_pc(lungo)))
    return None


def esce_protetto(x: dict | None, costo: int | None, crediti_iniziali: int | None, rimborso: float, mu_entra: float | None) -> str | None:
    """(c) Il motivo per cui chi esce NON va svincolato, oppure None."""
    if not x:
        return None
    nome = x.get("nome", "Chi esce")
    stato = x.get("stato")
    quota = float(x.get("quota_titolare") or 0)
    mu = float(x.get("mu") or 0)
    lungo = stato == "infortunato" and infortunio_lungo(x.get("nota"))
    if stato == "infortunato" and not lungo and quota >= QUOTA_TITOLARE_PROTETTA:
        return F("senso.esce_fuori_poco", nome=nome)
    continuo = float(x.get("p_lungo") if x.get("p_lungo") is not None else 1.0) >= P_LUNGO_MIN_DO     # chi manca da settimane non è «utile»
    if not lungo and quota >= QUOTA_TITOLARE_PROTETTA and continuo and (mu_entra is None or mu >= mu_entra):
        return F("senso.esce_titolare", nome=nome)
    if costo is not None and crediti_iniziali and costo >= QUOTA_COSTO_PROTETTO * crediti_iniziali and not lungo and quota >= QUOTA_TITOLARE_FLOP:
        return F("senso.esce_pagato", nome=nome, costo=int(costo), p=round(rimborso * 100))
    return None


def ripensamento(id_esce: int | None, id_entra: int | None, recenti: tuple[set[int], set[int]] | None) -> str | None:
    """(f) `recenti` = (presi da poco, lasciati liberi da poco), vedi `movimenti_recenti`."""
    if not recenti:
        return None
    presi, lasciati = recenti
    if id_esce in presi:
        return F("senso.preso_da_poco")
    if id_entra in lasciati:
        return F("senso.lasciato_da_poco")
    return None


def movimenti_recenti(storico: list[dict], mia: str | None, adesso: datetime | None = None) -> tuple[set[int], set[int]]:
    """Dai movimenti registrati (movimenti.leggi): gli id arrivati nella mia rosa e quelli che ho lasciato liberi negli ultimi
    GIORNI_RIPENSAMENTO giorni. Voci rovinate o senza data si saltano."""
    adesso = adesso or datetime.now()
    limite = adesso - timedelta(days=GIORNI_RIPENSAMENTO)
    presi: set[int] = set()
    lasciati: set[int] = set()
    if not mia:
        return presi, lasciati
    for m in storico or []:
        try:
            quando = datetime.fromisoformat(str(m.get("quando"))[:19])
        except (TypeError, ValueError):
            continue
        if quando < limite:
            continue
        for blocco, dove in ((m.get("svincolati_presi"), presi), (m.get("tagliati"), lasciati)):
            for voce in blocco or []:
                if isinstance(voce, dict) and voce.get("squadra") == mia:
                    dove |= {int(g["id"]) for g in voce.get("giocatori") or [] if isinstance(g, dict) and g.get("id") is not None}
        for sc in m.get("scambi") or []:
            if not isinstance(sc, dict):
                continue
            a, b = (sc.get("squadre") or [None, None])[:2]
            ricevuti = sc.get("da_b") if a == mia else sc.get("da_a") if b == mia else []
            presi |= {int(g["id"]) for g in ricevuti or [] if isinstance(g, dict) and g.get("id") is not None}
    return presi, lasciati


# ---------------------------------------------------------------- giudizi completi
def perche_si(x: dict | None, y: dict | None) -> str:
    """La frase positiva che accompagna un consiglio sensato: perché conviene, a parole."""
    parti = []
    if y:
        squadra = _nome_squadra(y)
        parti.append(F("senso.si_titolare_fisso_sq", nome=y.get("nome", "chi entra"), squadra=squadra) if squadra
                     else F("senso.si_titolare_fisso", nome=y.get("nome", "chi entra")))
    if x:
        stato = x.get("stato")
        if stato == "infortunato" and infortunio_lungo(x.get("nota")):
            parti.append(F("senso.si_fuori_a_lungo", nome=x.get("nome", "chi esce")))
        elif stato == "squalificato":
            parti.append(F("senso.si_squalificato", nome=x.get("nome", "chi esce")))
        elif float(x.get("quota_titolare") or 0) < QUOTA_TITOLARE_FLOP or float(x.get("p_lungo") or 1) < P_LUNGO_MIN_DO:
            parti.append(F("senso.si_gioca_poco", nome=x.get("nome", "chi esce")))
    return elenco(parti)


def giudica_svincolo(x: dict | None, y: dict | None, per_giornata: list[float], ruolo: str, costo: int | None,
                     crediti_iniziali: int | None, rimborso: float, fattibile: bool | None = None,
                     recenti: tuple[set[int], set[int]] | None = None, id_esce: int | None = None, id_entra: int | None = None) -> tuple[bool, str]:
    """Esce `x`, entra `y` (profili, anche None), con i punti in più giornata per giornata. (va bene, motivo): se va bene il motivo
    è il perché positivo (anche vuoto), altrimenti la prima regola che lo boccia, in una frase."""
    for motivo in (ripensamento(id_esce, id_entra, recenti),
                   esce_protetto(x, costo, crediti_iniziali, rimborso, float(y["mu"]) if y and y.get("mu") is not None else None),
                   entra_affidabile(y),
                   guadagno_significativo(per_giornata, ruolo),
                   F("senso.crediti") if fattibile is False else None):
        if motivo:
            return False, motivo
    return True, perche_si(x, y)


def giudica_scambio(p: dict, prof: dict[int, dict], recenti: tuple[set[int], set[int]] | None = None) -> tuple[bool, str]:
    """Una proposta di scambio (scambi.Scambio.come_dict): la stessa prudenza, dal mio punto di vista e da quello di chi accetta."""
    do, ricevo = p.get("do") or [], p.get("ricevo") or []
    per_giornata = p.get("per_giornata_mio") or []
    ruoli = [g.get("ruolo") for g in ricevo if g.get("ruolo") in SOGLIA_BREVE]
    ruolo = max(ruoli, key=lambda r: SOGLIA_BREVE[r]) if ruoli else "A"
    for g in do:
        x = prof.get(int(g["id"])) if g.get("id") is not None else None
        simili = [prof[int(r["id"])].get("mu") for r in ricevo if r.get("id") is not None and int(r["id"]) in prof
                  and r.get("ruolo") == g.get("ruolo") and prof[int(r["id"])].get("mu") is not None]
        m = ripensamento(g.get("id"), None, recenti) or esce_protetto(x, None, None, 0.0, max(simili) if simili else None)
        if m:
            return False, m
        if x and (x.get("stato") in FUORI or float(x.get("p_lungo") or 0) < P_LUNGO_MIN_DO):
            perche = (F("senso.stato_squalificato" if x.get("stato") == "squalificato" else "senso.stato_infortunato") if x.get("stato") in FUORI
                      else F("senso.gioca_poco_perc", p=_pc(float(x.get("p_lungo") or 0))))
            return False, F("senso.nessuno_accetta", nome=x.get("nome", "un giocatore"), perche=perche)
    for g in ricevo:
        y = prof.get(int(g["id"])) if g.get("id") is not None else None
        m = ripensamento(None, g.get("id"), recenti) or entra_affidabile(y)
        if m:
            return False, m
    m = guadagno_significativo(per_giornata, ruolo)
    if m:
        return False, m
    return True, perche_si(None, prof.get(int(ricevo[0]["id"])) if ricevo and ricevo[0].get("id") is not None else None)
