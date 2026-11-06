"""«Da fare» di Oggi: le cose che l'utente dovrebbe sbrigare adesso, in ordine di importanza (campo `da_fare` di GET /api/oggi).

Tutto si legge da cose già pronte: previsioni e formazione già in cache (le ha appena usate `gestione.oggi`), svincolati e scambi
SOLO se già in cache (mai un calcolo nuovo), e piccoli file dell'utente. Ogni controllo è a sé: se uno fallisce gli altri restano,
e `costruisci` non alza mai errori (Oggi si deve aprire comunque). Contratto per le app in docs/API.md.
I testi sono `Frase` (fanta/frasi.py): la voce ha `testo` in italiano e, accanto, `frase` (chiave e parametri per tradurlo) e `azione_frase`.
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from . import avvisi, buon_senso, consigli, diario, etichette, frasi, movimenti, rinvii, scelte, stato_utente, widget
from .frasi import F
from .lega import Rose
from .regole import ASTA_ESTIVA_PREDEFINITA, ASTA_INVERNALE_PREDEFINITA, Regole, periodo, serie_a_a_lega
from .turno import della_giornata, inizio as inizio_turno

LOG = logging.getLogger(__name__)
MAX_VOCI = 8
MAX_DUBBI = 3
MAX_DIARIO = 1
MAX_COPERTURA = 2
ORE_FORMAZIONE = 12            # la formazione non salvata si segnala da qui alla scadenza
ORE_URGENTE = 3
SOGLIA_GUADAGNO = 1.5          # punti in più (stagione) sotto cui uno svincolato o uno scambio non si nomina nemmeno; le regole
#                                di buon senso (soglie per ruolo sulle prossime giornate, titolarità, costo...) stanno in buon_senso.py
CONSIGLI = ("dubbio", "copertura", "svincolato", "scambio")      # le voci che sono consigli: al massimo buon_senso.MAX_CONSIGLI
GIORNI_SOSTA = 10              # fra l'ultima partita di una giornata e la prima della successiva: da qui in su è una sosta
GIORNI_DATI = 3
GIORNI_CERTIFICATO = 3
ALTA, MEDIA, BASSA = 1, 2, 3
FUORI = ("infortunato", "squalificato")
MAX_NOMI_CAMBIATI = 3          # «la consigliata è cambiata» nomina i titolari fino a 3 cambi; oltre dice solo quanti sono
ORDINE_RUOLI = {"P": 0, "D": 1, "C": 2, "A": 3}
# etichette (fanta/etichette.py) che la voce di un titolare incerto scrive con la stessa parola, in minuscolo (chiavi `etichetta.*`
# di fanta/frasi.py): «Lerri: improbabile, gioca 2%.». `in_dubbio` resta «è in dubbio» (le chiavi `dafare.dubbio_incerto*`).
IN_FRASE = ("ballottaggio", "panchina", "improbabile", "rinviata")


def _num(x: float) -> str:
    return f"{x:.1f}".replace(".", ",")


def _destinazione(scheda: str, sezione: str | None = None, **extra) -> dict:
    """Dove porta il pulsante. `scheda`: oggi|formazione|mercato|scambi|lega|impostazioni (le stesse del web e dei collegamenti
    schieraxi://). `link` è già pronto per iOS e Android; `sezione` e gli extra (giocatore, giornata) dicono il punto preciso."""
    link = f"schieraxi://{scheda}" + (f"/{sezione}" if sezione else "")
    if "giocatore" in extra:
        link = f"schieraxi://giocatore/{extra['giocatore']}"
    return {"scheda": scheda, "sezione": sezione, "link": link} | extra


def _voce(id: str, tipo: str, testo: str, priorita: int, azione: str, destinazione: dict, **extra) -> dict:
    voce = {"id": id, "tipo": tipo, "testo": testo, "priorita": priorita, "azione": azione, "destinazione": destinazione} | extra
    if frasi.di(testo):
        voce["frase"] = frasi.di(testo)
    if frasi.di(azione):
        voce["azione_frase"] = frasi.di(azione)
    return voce


def _ore_a_parole(ore: float) -> str:
    return F("tempo.meno_di_un_ora") if ore < 1 else F("tempo.ore", n=round(ore))


# ---------------------------------------------------------------- i singoli controlli
def _consigliata(db, regole: Regole, rose: Rose, f: dict | None = None) -> tuple[list[int], list[int]] | None:
    """(titolari, panchina in ordine) della formazione consigliata `f` se chi chiama l'ha già, altrimenti quella in cache (l'ha appena
    calcolata `gestione.oggi`); None se non si riesce a formare la squadra."""
    if f is None:
        try:
            f = consigli.formazione(db, regole, rose)
        except ValueError:
            return None
    return [int(g["id"]) for g in f["titolari"]], [int(g["id"]) for g in f.get("panchina") or []]


def _bloccati(db, giornata: int, schede: dict) -> set[int]:
    """Anticipi già cominciati (#373): gli id delle `schede` ({id: scheda}) di chi gioca una partita già cominciata. Non si spostano
    più (il server rifiuta il salvataggio), quindi «Da fare» non propone cambi su di loro. Regola della consigliata (#368)."""
    return set(scelte.bloccati(schede, consigli._anticipi_iniziati(db, consigli.stagione_corrente(), giornata)))


def _sostituzioni_ammesse(regole: Regole) -> bool:
    return getattr(getattr(regole, "panchina", None), "max_sostituzioni", 1) > 0


def _dubbi(db, regole: Regole, rose: Rose, giornata: int, file_scelte: Path | None, *, formazione: dict | None = None) -> list[dict]:
    """Titolari (quelli che l'utente ha salvato, se si possono ancora schierare, altrimenti i consigliati) fuori o in dubbio. Il cambio con il miglior sostituto
    libero («Meglio Y», «Sostituisci») si propone solo se la formazione consigliata lo fa davvero: stessa regola di `consigliato`
    del confronto (`consigli.da_schierare`). Se la consigliata tiene il titolare, la voce dice chi entra dalla panchina se lui non
    gioca (la prima riserva dello stesso ruolo, come le sostituzioni) e porta alla formazione: Oggi e Formazione non si contraddicono.
    `formazione`: la consigliata (`consigli.formazione`) se chi chiama l'ha già calcolata (l'avviso «cambio pronto», notifiche.py)."""
    s = rose.squadra(rose.mia_squadra or "")
    prev, _, _ = consigli.previsioni(db, regole)
    consigliata = _consigliata(db, regole, rose, formazione)
    scelta = scelte.leggi(consigli.stagione_corrente(), giornata, file_scelte)
    if scelta:                      # conta solo se si può ancora schierare (regola unica, come la Formazione): se no la consigliata
        scelta = scelte.che_vale(scelta, scelte.ruoli_schierabili(rose, prev), regole)
    if scelta:
        titolari = [int(i) for i in scelta["titolari"]]
    elif consigliata:
        titolari = consigliata[0]
    else:
        return []
    sistema, panchina = consigliata or (None, [])
    schede = {g.id: consigli.scheda_previsione(g.id, prev.loc[g.id]) for g in s.giocatori if g.id is not None and g.id in prev.index}
    # anticipi già cominciati (#373): niente voce su chi è bloccato e non entra al posto di un altro; resta solo come riserva che
    # entra da sola dalla panchina
    fermi = _bloccati(db, giornata, schede)
    voci = []
    # un sostituto per volta: prima chi è fuori, poi chi rischia di più; chi è già nominato (proposto o riserva) non torna una seconda volta
    in_dubbio = [i for i in titolari if i not in fermi and (x := schede.get(i)) and (x["stato"] in FUORI or x["dubbio"] or x["p_voto"] < 0.75)]
    in_dubbio.sort(key=lambda i: (schede[i]["stato"] not in FUORI, schede[i]["p_voto"]))
    usati: set[int] = set()

    def libero(j: int, ruolo: str) -> bool:
        y = schede.get(j)
        return y is not None and j not in titolari and j not in usati and y["ruolo"] == ruolo and y["stato"] not in FUORI

    for i in in_dubbio:
        x = schede[i]
        fuori = x["stato"] in FUORI
        # il candidato: chi la consigliata schiera al suo posto, se c'è; altrimenti il libero con più punti attesi
        alt = max((y for j, y in schede.items() if libero(j, x["ruolo"]) and j not in fermi),
                  key=lambda y: (bool(sistema) and y["id"] in sistema, y["punti_attesi"]), default=None)
        codice = etichette.codice(x)
        if fuori:
            chiave, param = "dafare.dubbio_squalificato" if x["stato"] == "squalificato" else "dafare.dubbio_infortunato", {}
        elif codice in IN_FRASE:     # con la parola dell'etichetta di Formazione e scheda: «in dubbio» solo se lo dicono le probabili (#282)
            chiave, param = "dafare.incerto", {"stato": F("etichetta." + codice), "p": etichette.percento(x["p_voto"])}
        else:
            chiave, param = "dafare.dubbio_incerto", {"p": etichette.percento(x["p_voto"])}
        extra = {}
        if alt and consigli.da_schierare(x, alt, sistema)["id"] == alt["id"]:
            usati.add(alt["id"])
            testo = F(chiave + "_alt", nome=x["nome"], alt=alt["nome"], **param)       # «Adams A.» finisce già col punto: ne basta uno
            extra["alternativa"] = {"id": alt["id"], "nome": alt["nome"], "ruolo": alt["ruolo"], "punti_attesi": alt["punti_attesi"]}
            azione, destinazione = F("dafare.az_sostituisci"), _destinazione("formazione", giocatore=i)
        else:                       # nessun cambio da proporre (la consigliata lo tiene, o non c'è un sostituto): niente «Sostituisci»
            riserva = None
            if not fuori and sistema and i in sistema and _sostituzioni_ammesse(regole):
                riserva = next((schede[j] for j in panchina if libero(j, x["ruolo"])), None)
            if riserva:
                usati.add(riserva["id"])
                testo = F(chiave + "_tiene", nome=x["nome"], riserva=riserva["nome"], **param)
                extra["riserva"] = {"id": riserva["id"], "nome": riserva["nome"]}
            else:
                testo = F(chiave, nome=x["nome"], **param)
            azione, destinazione = F("dafare.az_formazione"), _destinazione("formazione")
        voci.append(_voce(f"dubbio:{i}", "dubbio", testo, ALTA if fuori else MEDIA, azione, destinazione,
                          giocatore={"id": i, "nome": x["nome"]}, **extra))
    voci.sort(key=lambda v: (v["priorita"], "alternativa" not in v, v["id"]))     # a pari priorità prima i cambi da fare
    return voci[:MAX_DUBBI]


def era_consigliata(db, regole: Regole, rose: Rose, titolari: list[int], giornata: int | None = None,
                    file_diario: Path | None = None) -> bool:
    """Gli 11 `titolari` sono quelli della consigliata (l'ordine non conta). Lo chiede il server quando salvi la formazione («Salva
    questa»): lo scrive nella scelta (`era_consigliata`) e «Da fare» sa che hai salvato la consigliata (#333). Vale la consigliata
    che l'app ti ha mostrato, cioè l'istantanea che GET /api/formazione scrive nel tuo Diario (`file_diario`): se tra l'apertura della
    Formazione e il salvataggio i dati si aggiornano, quella di adesso è già un'altra. Vale anche la consigliata di adesso (stessa
    `giornata`, già in cache da `consigli.valuta`). Nel dubbio False, cioè scelta a mano come prima."""
    try:
        scelti = {int(i) for i in titolari}
        if giornata is not None:
            ist = (diario.carica(file_diario).get("istantanee") or {}).get(f"{consigli.stagione_corrente()}/{giornata}")
            if isinstance(ist, dict) and {int(t["id"]) for t in ist.get("titolari") or [] if isinstance(t, dict) and "id" in t} == scelti:
                return True
        f = consigli.formazione(db, regole, rose, giornata=giornata)
        if giornata is not None and f.get("giornata") not in (None, giornata):
            return False
        return {int(g["id"]) for g in f["titolari"]} == scelti
    except Exception as e:                              # noqa: BLE001  (il salvataggio non deve fallire per questo)
        LOG.warning("consigliata salvata: confronto non riuscito (%s), la scelta conta come fatta a mano", type(e).__name__)
        return False


def _e_la_consigliata(scelta: dict) -> bool:
    """La scelta salvata era la consigliata: il segno di «Salva questa» o «ho schierato la consigliata»."""
    return scelta.get("era_consigliata") is True or scelta.get("tipo") == "consigliata"


def _consigliata_cambiata(prev, salvati: list[int], adesso: list[int], giornata: int) -> dict:
    """UNA voce: la consigliata ha titolari diversi da quelli che hai salvato. Dice chi entra e chi esce (fino a MAX_NOMI_CAMBIATI
    cambi, poi solo quanti sono) e porta alla Formazione. Non cambia niente da sola. Se fra chi esce c'è un infortunato o uno
    squalificato lo dice per primo e la priorità è alta («Urgente»), come la voce del suo dubbio che sostituisce."""
    schede = {i: consigli.scheda_previsione(i, prev.loc[i]) for i in set(salvati) ^ set(adesso)}
    ruolo = lambda i: ORDINE_RUOLI.get(schede[i].get("ruolo"), len(ORDINE_RUOLI))     # per ruolo, poi nell'ordine della formazione
    entrano = sorted((i for i in adesso if i not in salvati), key=ruolo)
    escono = sorted((i for i in salvati if i not in adesso), key=ruolo)
    nomi = lambda ids: [schede[i]["nome"] for i in ids]
    fuori = [i for i in escono if schede[i].get("stato") in FUORI]
    chiave, perche = "dafare.consigliata_cambiata", {}
    if fuori:                       # «Bianchi è infortunato, Verdi è squalificato e la consigliata è cambiata…»
        chiave = "dafare.consigliata_cambiata_fuori"
        perche = {"fuori": frasi.elenco([F("dafare.fuori_" + schede[i]["stato"], nome=schede[i]["nome"]) for i in fuori])}
    if len(entrano) <= MAX_NOMI_CAMBIATI:
        testo = F(chiave, **perche, entrano=frasi.elenco(nomi(entrano), con_e=True), escono=frasi.elenco(nomi(escono), con_e=True))
    else:
        testo = F(chiave + "_molti", **perche, n=len(entrano))
    return _voce(f"consigliata:{giornata}", "formazione", testo, ALTA if fuori else MEDIA, F("dafare.az_formazione"),
                 _destinazione("formazione"),
                 entrano=[{"id": i, "nome": schede[i]["nome"]} for i in entrano],
                 escono=[{"id": i, "nome": schede[i]["nome"]} for i in escono])


def _cambi_possibili(salvati: list[int], adesso: list[int], fermi: set[int], schede: dict) -> tuple[list[int], list[int]]:
    """(chi entra, chi esce) per passare dai titolari `salvati` a quelli della consigliata `adesso`, senza i cambi che non si
    possono più fare (#373): chi è in `fermi` resta dov'è. Un titolare fermo che la consigliata toglie resta, quindi entra uno in
    meno del suo ruolo (il meno utile per punti attesi); uno fermo che la consigliata fa entrare non entra, quindi esce uno in meno
    del suo ruolo (resta il più utile). `schede`: {id: scheda} di chi cambia, con `ruolo` e `punti_attesi`."""
    entrano = [i for i in adesso if i not in salvati]
    escono = [i for i in salvati if i not in adesso]
    ruolo = lambda i: (schede.get(i) or {}).get("ruolo")
    punti = lambda i: (schede.get(i) or {}).get("punti_attesi") or 0.0
    for r in {ruolo(i) for i in fermi & {*entrano, *escono}}:
        k = sum(1 for i in escono if i in fermi and ruolo(i) == r) - sum(1 for i in entrano if i in fermi and ruolo(i) == r)
        if k > 0:
            tolti = sorted((i for i in entrano if i not in fermi and ruolo(i) == r), key=punti)[:k]
        else:
            tolti = sorted((i for i in escono if i not in fermi and ruolo(i) == r), key=punti, reverse=True)[:-k]
        entrano, escono = [i for i in entrano if i not in tolti], [i for i in escono if i not in tolti]
    return [i for i in entrano if i not in fermi], [i for i in escono if i not in fermi]


def _titolari(db, regole: Regole, rose: Rose, giornata: int, file_scelte: Path | None) -> list[dict]:
    """Le voci sui tuoi titolari. Con una formazione fatta a mano, o niente di salvato, i dubbi di sempre (`_dubbi`). Se hai salvato
    la consigliata (#333) nessun cambio proposto: era già la scelta migliore. Se intanto la consigliata ha titolari diversi, UNA voce
    lo dice e porta alla Formazione. La scelta salvata non si tocca mai: la cambi solo tu."""
    prev = consigli.previsioni(db, regole)[0]
    scelta = scelte.leggi(consigli.stagione_corrente(), giornata, file_scelte)
    if scelta:                      # conta solo se si può ancora schierare (regola unica, come in `_dubbi`)
        scelta = scelte.che_vale(scelta, scelte.ruoli_schierabili(rose, prev), regole)
    if not (scelta and _e_la_consigliata(scelta)):
        return _dubbi(db, regole, rose, giornata, file_scelte)
    salvati = [int(i) for i in scelta["titolari"]]
    consigliata = _consigliata(db, regole, rose)
    if consigliata and set(consigliata[0]) != set(salvati):
        # chi gioca un anticipo già cominciato non si sposta più (#373): non si nomina come cambio; se cambiano solo loro, niente voce
        schede = {i: consigli.scheda_previsione(i, prev.loc[i]) for i in set(consigliata[0]) ^ set(salvati) if i in prev.index}
        entrano, escono = _cambi_possibili(salvati, consigliata[0], _bloccati(db, giornata, schede), schede)
        if entrano or escono:
            adesso = [i for i in consigliata[0] if i in entrano] + [i for i in salvati if i not in escono]
            return [_consigliata_cambiata(prev, salvati, adesso, giornata)]
    # la stessa consigliata (o non si riesce a calcolarla): restano solo le voci che non chiedono un cambio
    return [v for v in _dubbi(db, regole, rose, giornata, file_scelte) if "alternativa" not in v]


def _copertura(db, regole: Regole, rose: Rose, lingua: str = "it") -> list[dict]:
    """Reparti della rosa scoperti (priorità alta) o senza ricambi (media): un conteggio sulle previsioni già in cache."""
    from . import copertura
    prev, _, _ = consigli.previsioni(db, regole)
    r = copertura.analizza(prev, regole, rose, lingua)
    voci = []
    for x in (r or {}).get("reparti", [])[:MAX_COPERTURA]:
        scoperto = x["livello"] == copertura.SCOPERTO
        voci.append(_voce(f"copertura:{x['ruolo'] or 'moduli'}", "copertura", x["testo"], ALTA if scoperto else MEDIA,
                          F("dafare.az_rimpiazzo") if x["ruolo"] else F("dafare.az_formazione"),
                          _destinazione("mercato" if x["ruolo"] else "formazione"), reparto=x["ruolo"], livello=x["livello"],
                          disponibili=x["disponibili"], minimo=x["minimo"]))
    return voci


def _formazione_non_salvata(db, regole: Regole, rose: Rose, ore: float | None, giornata: int, file_scelte: Path | None) -> dict | None:
    """La formazione si chiude presto e non c'è una scelta salvata che si possa schierare. Una scelta che non vale più (giocatore
    ceduto, modulo tolto dalla lega) conta come nessuna per i conti, ma la frase lo dice: «quella che hai salvato non è più valida»."""
    if ore is None or not 0 < ore <= ORE_FORMAZIONE:
        return None
    scelta = scelte.leggi(consigli.stagione_corrente(), giornata, file_scelte)
    if scelta and scelte.che_vale(scelta, scelte.ruoli_schierabili(rose, consigli.previsioni(db, regole)[0]), regole):
        return None
    chiave = "dafare.formazione_non_valida" if scelta else "dafare.formazione_chiude"
    return _voce(f"formazione:{giornata}", "formazione", F(chiave, tempo=_ore_a_parole(ore)),
                 ALTA if ore <= ORE_URGENTE else MEDIA, F("dafare.az_formazione"), _destinazione("formazione"))


def _recenti(rose: Rose, file_movimenti: Path | None, adesso: datetime) -> tuple[set[int], set[int]]:
    """(presi da poco, lasciati liberi da poco) dai movimenti registrati: regola (f) di buon_senso.py."""
    if file_movimenti is None:
        return set(), set()
    return buon_senso.movimenti_recenti(movimenti.leggi(file_movimenti), rose.mia_squadra, adesso)


def _frase_guadagno(breve: float | None, guadagno: float, n: int | None) -> str:
    """I punti in più a parole: sulle prossime giornate se si sanno (più concreti), altrimenti il totale di stagione."""
    if breve is not None and n:
        return F("dafare.guadagno_breve", punti=float(breve), n=n)
    return F("dafare.guadagno_stagione", punti=float(guadagno))


def _svincolato(db, regole: Regole, rose: Rose, recenti: tuple[set[int], set[int]]) -> dict | None:
    """Il miglior cambio con uno svincolato già promosso dal buon senso in `gestione.mercato` (solo se in cache). Qui si applica
    in più la regola sui movimenti recenti, che il mercato (in cache per tutti) non conosce."""
    mancano: list[str] = []
    m = widget._opzionale(mancano, "svincolato", lambda: consigli.mercato(db, regole, rose))
    for p in (m or {}).get("proposte") or []:
        if p.get("sensato") is False or p.get("fattibile") is False or p.get("guadagno", 0) < SOGLIA_GUADAGNO:
            continue
        esce, entra = p["esce"], p["entra"]
        if buon_senso.ripensamento(esce["id"], entra["id"], recenti):
            continue
        motivo = frasi.da_json(p.get("motivo_frase")) or p.get("motivo") or ""       # il motivo del mercato è una Frase (o il suo oggetto, se è passato da JSON)
        n = len(p.get("giornate") or []) or None
        guadagno = _frase_guadagno(p.get("breve"), p["guadagno"], n)
        testo = (F("dafare.svincolato_motivo", entra=entra["nome"], esce=esce["nome"], motivo=motivo, guadagno=guadagno) if motivo
                 else F("dafare.svincolato", entra=entra["nome"], esce=esce["nome"], guadagno=guadagno))
        return _voce(f"svincolato:{entra['id']}", "svincolato", testo, BASSA, F("dafare.az_vedi"),
                     _destinazione("mercato", giocatore=entra["id"]), esce={"id": esce["id"], "nome": esce["nome"]},
                     entra={"id": entra["id"], "nome": entra["nome"]}, guadagno=p["guadagno"], motivo=motivo)
    return None


def _scambio(db, regole: Regole, rose: Rose, recenti: tuple[set[int], set[int]]) -> dict | None:
    """La prima proposta di scambio (in cache) che supera il buon senso (`buon_senso.giudica_scambio`)."""
    mancano: list[str] = []
    r = widget._opzionale(mancano, "scambio", lambda: consigli.proposte_scambi(db, regole, rose)[1])
    if not r:
        return None
    prof = {}
    try:
        prof = buon_senso.profili(consigli.previsioni(db, regole)[0])
    except Exception:                                   # noqa: BLE001  (senza profili si giudica solo il guadagno)
        pass
    for p in r:
        if p.get("guadagno_mio", 0) < SOGLIA_GUADAGNO:
            continue
        ok, motivo = buon_senso.giudica_scambio(p, prof, recenti)
        if not ok:
            continue
        do, ricevo = ", ".join(g["nome"] for g in p["do"]), ", ".join(g["nome"] for g in p["ricevo"])
        n = len(p.get("giornate") or []) or None
        guadagno = _frase_guadagno(p.get("breve_mio"), p["guadagno_mio"], n)
        testo = (F("dafare.scambio_motivo", altra=p["altra"], do=do, ricevo=ricevo, motivo=motivo, guadagno=guadagno) if motivo
                 else F("dafare.scambio", altra=p["altra"], do=do, ricevo=ricevo, guadagno=guadagno))
        return _voce(f"scambio:{p['altra']}", "scambio", testo, BASSA, F("dafare.az_scambio"), _destinazione("scambi"), con=p["altra"],
                     guadagno=p["guadagno_mio"], motivo=motivo)
    return None


def _giocatori_di(v: dict) -> set[int]:
    """Gli id dei giocatori nominati da una voce (per non proporre due consigli sullo stesso giocatore)."""
    ids = set()
    for k in ("giocatore", "alternativa", "riserva", "esce", "entra"):
        if isinstance(v.get(k), dict) and v[k].get("id") is not None:
            ids.add(int(v[k]["id"]))
    return ids


def _limita_consigli(voci: list[dict]) -> list[dict]:
    """(g) e (f) di buon_senso.py: al massimo MAX_CONSIGLI consigli (dubbi, coperture, svincolati, scambi), in ordine di
    importanza, e mai due consigli di mercato sullo stesso giocatore. Le altre voci (formazione, diario, backup...) restano."""
    out, n, visti = [], 0, set()
    for v in voci:
        if v["tipo"] not in CONSIGLI:
            out.append(v)
            continue
        ids = _giocatori_di(v) if v["tipo"] in ("svincolato", "scambio") else set()
        if n >= buon_senso.MAX_CONSIGLI or (ids & visti):
            continue
        visti |= _giocatori_di(v)
        out.append(v)
        n += 1
    return out


def _turni(db, stagione: str) -> dict[int, tuple[datetime, datetime]]:
    """Per ogni giornata della stagione: prima e ultima partita giocata con la sua giornata (turno e anticipi, regola unica di
    turno.py): una partita rinviata a settimane dopo non sposta la fine della giornata."""
    date: dict[int, list[datetime]] = {}
    for g, testo in db.execute("SELECT giornata, data FROM partite WHERE stagione = ? AND data IS NOT NULL", (stagione,)):
        try:
            date.setdefault(int(g), []).append(datetime.fromisoformat(str(testo)[:16].replace("T", " ")))
        except (TypeError, ValueError):
            continue
    turni = {}
    for g, dd in date.items():
        inizio = inizio_turno(dd)
        sue = [d for d in dd if della_giornata(d, inizio)]
        if sue:
            turni[g] = (min(sue), max(sue))
    return turni


def _momenti_mercato(regole: Regole, stagione: str, turni: dict[int, tuple[datetime, datetime]],
                     inizio_lega: datetime | None) -> list[tuple[datetime, datetime]]:
    """Quando cambiano le rose della lega, come (inizio, fine) del momento. Le date sono quelle della lega (regole.json); se non le
    indica: per le aste ASTA_ESTIVA_PREDEFINITA e ASTA_INVERNALE_PREDEFINITA (2-3 settimane dopo la chiusura del mercato della Serie
    A), per gli scambi le soste del calendario della Serie A (almeno GIORNI_SOSTA giorni fra l'ultima partita di una giornata e la
    prima della successiva; `finestre_scambio: []` = nessuna finestra). Contano solo le date della stagione in corso: quelle di
    un'altra stagione rimaste nel file valgono come non indicate.
    La lega non gioca senza rose: un'asta estiva che comprende `inizio_lega` (la scadenza della sua prima giornata) finisce lì, e
    quella di partenza non conta se la lega è partita prima (l'asta c'è già stata)."""
    anno = int(stagione[:4])
    dal_stagione, al_stagione = datetime(anno, 7, 1), datetime(anno + 1, 7, 1)

    def momento(p: dict) -> tuple[datetime, datetime] | None:
        primo, ultimo = periodo(p)
        inizio = datetime.combine(primo, datetime.min.time())
        fine = datetime.combine(ultimo, datetime.min.time()) + timedelta(days=1)          # alla fine dell'ultimo giorno
        return (inizio, fine) if dal_stagione <= inizio < al_stagione else None

    def di_partenza(anno: int, giorni: tuple[tuple[int, int], tuple[int, int]]) -> tuple[datetime, datetime]:
        (m1, g1), (m2, g2) = giorni
        return datetime(anno, m1, g1), datetime(anno, m2, g2) + timedelta(days=1)

    estiva = regole.asta_estiva and momento(regole.asta_estiva)
    if not estiva:
        estiva = di_partenza(anno, ASTA_ESTIVA_PREDEFINITA)
        if inizio_lega is not None and inizio_lega <= estiva[0]:
            estiva = None
    if estiva and inizio_lega is not None and estiva[0] < inizio_lega < estiva[1]:
        estiva = (estiva[0], inizio_lega - timedelta(seconds=1))         # così la giornata «dopo la fine» è la prima della lega
    invernale = regole.asta_invernale and momento(regole.asta_invernale) or di_partenza(anno + 1, ASTA_INVERNALE_PREDEFINITA)
    momenti = [estiva, invernale]
    finestre = [momento(p) for p in regole.finestre_scambio or []]
    if regole.finestre_scambio is not None and (any(finestre) or not regole.finestre_scambio):
        momenti += finestre
    else:
        giornate = sorted(turni)
        momenti += [(turni[g][1], turni[g][1]) for g, dopo in zip(giornate, giornate[1:])
                    if turni[dopo][0] - turni[g][1] >= timedelta(days=GIORNI_SOSTA)]
    return [m for m in momenti if m]


def _rose_vecchie(db, stagione: str, regole: Regole, file_rose: Path, adesso: datetime) -> dict | None:
    """Promemoria «aggiorna le rose» (#334): solo dopo un momento di mercato della lega (`_momenti_mercato`) e solo se le rose non
    sono state aggiornate da quando è cominciato. Sparisce con l'aggiornamento o alla scadenza della prima giornata della lega
    dopo la fine del momento (scadenza della lega, `avvisi.scadenza`), così copre anche un'asta alla fine del periodo. Prima
    compariva dopo ogni giornata giocata: era rumore."""
    aggiornate = datetime.fromtimestamp(file_rose.stat().st_mtime)
    turni = _turni(db, stagione)
    giornate = sorted(g for g in turni if g >= regole.prima_giornata_lega)
    scadenze: dict[int, datetime | None] = {}

    def scadenza(g: int) -> datetime | None:
        if g not in scadenze:
            scadenze[g] = avvisi.scadenza(avvisi.prima_partita(db, stagione, g), regole)
        return scadenze[g]

    prima = regole.prima_giornata_lega
    inizio_lega = scadenza(prima) if prima in turni else None
    entro = None                    # la giornata (di Serie A) entro la cui scadenza aggiornare le rose
    for inizio, fine in _momenti_mercato(regole, stagione, turni, inizio_lega):
        if not aggiornate < inizio <= adesso:
            continue
        g = next((g for g in giornate if (s := scadenza(g)) is not None and s > fine), None)
        if g is not None and adesso < scadenza(g) and (entro is None or g < entro):
            entro = g
    if entro is None:
        return None
    giorni = (adesso - aggiornate).days
    return _voce("rose-vecchie", "rose", F("dafare.rose_mercato", giornata=frasi.nome_giornata(entro, serie_a_a_lega(entro, regole))),
                 MEDIA, F("dafare.az_aggiorna_rose"), _destinazione("lega", "rose"), giorni=giorni)


def _certificato(giorni: int | None) -> dict | None:
    """Lo calcola il client (il server non sa quando scade il certificato dell'app sull'iPhone) e lo manda in `certificato_giorni`."""
    if giorni is None or giorni > GIORNI_CERTIFICATO:
        return None
    if giorni < 0:
        testo, pr = F("dafare.cert_scaduto"), ALTA
    elif giorni == 0:
        testo, pr = F("dafare.cert_oggi"), ALTA
    else:
        testo, pr = F("dafare.cert", n=giorni), ALTA if giorni == 1 else MEDIA
    return _voce("certificato", "certificato", testo, pr, F("dafare.az_rinnova"), _destinazione("impostazioni", "installazione"))


def _chiusa_prima(db, stagione: str, giornata: int, minuti: int, dal: datetime) -> bool:
    """La formazione della giornata si è chiusa prima di `dal` (per esempio prima che l'account esistesse). Inizio della giornata
    dalla regola unica (turno.py, `avvisi.prima_partita`): né un anticipo né una partita rinviata con la data vecchia la anticipano."""
    inizio = avvisi.prima_partita(db, stagione, giornata)
    if inizio is None:
        return False
    return inizio - timedelta(minutes=minuti or 0) <= dal


def _diario(db, stagione: str, rose: Rose, file_scelte: Path | None, file_diario: Path | None, regole: Regole,
            dal: datetime | None = None) -> list[dict]:
    """Solo l'ULTIMA giornata finita, se manca la formazione dichiarata: basta un tocco per dire «ho schierato la consigliata».
    Una scelta salvata che non si può schierare con la rosa (regola unica della scelta, come il Diario) non conta come dichiarata.
    Le giornate più vecchie non si chiedono più (prima si accumulavano «la giornata 6 è finita», «la giornata 7 è finita»...).
    `dal` (ora locale): quando è nato l'account; se la formazione di quella giornata si è chiusa prima, non si chiede niente
    (chi è appena entrato non aveva nessuna consigliata da schierare)."""
    voci = diario.carica(file_diario).get("giornate", {})
    prima = getattr(regole, "prima_giornata_lega", 1)
    # finite per la lega: con una partita rinviata e la regola «senza voto» o «voto d'ufficio» basta il turno (rinvii.py)
    concluse = rinvii.giornate_chiuse(db, stagione, regole)
    finite = [x for x in concluse if x >= prima]
    if not finite:
        return []
    g = max(finite)
    scelta = scelte.che_vale(scelte.leggi(stagione, g, file_scelte), scelte.ruoli_schierabili(rose), regole)
    if scelta or (voci.get(f"{stagione}/{g}") or {}).get("schierata"):
        return []
    if dal is not None and _chiusa_prima(db, stagione, g, getattr(regole, "scadenza_minuti", 0), dal):
        return []
    return [_voce(f"diario:{g}", "diario", F("dafare.diario", giornata=frasi.nome_giornata(g, g - prima + 1)), BASSA,
                  F("dafare.az_schierato"), _destinazione("lega", "diario", giornata=g), giornata=g)][:MAX_DIARIO]


def _dati_vecchi(db, adesso: datetime) -> dict | None:
    """Avviso del server, solo per chi lo gestisce: i dati non si aggiornano da giorni."""
    q = db.execute("SELECT MAX(quando) FROM aggiornamenti WHERE cosa = 'aggiornamento'").fetchone()[0]
    if not q:
        return None
    giorni = (adesso - datetime.fromisoformat(str(q)[:19])).days
    if giorni < GIORNI_DATI:
        return None
    return _voce("dati-vecchi", "server", F("dafare.dati_vecchi", giorni=giorni), MEDIA, F("dafare.az_controlla"),
                 _destinazione("impostazioni", "avanzate"), giorni=giorni)


def _primo_avvio(file_impostazioni: Path | None) -> dict | None:
    s = stato_utente.leggi_primo_avvio(file_impostazioni) if file_impostazioni else None
    if not s or s["chiuso"] or not s["saltati"]:
        return None
    n = len(s["saltati"])
    return _voce("primo-avvio", "primo_avvio", F("dafare.primo_avvio", n=n), BASSA,
                 F("dafare.az_riprendi"), _destinazione("impostazioni", "informazioni"), saltati=s["saltati"])


# ---------------------------------------------------------------- senza rose
def senza_rose(imp: Path | None) -> list[dict]:
    """Per chi non ha ancora importato le rose: Oggi non è un errore ma un benvenuto. Prima voce `rose` (importa), poi, se la
    configurazione guidata non è mai stata iniziata, `primo_avvio`."""
    destinazione = _destinazione("lega", "rose")
    voci = [_voce("senza-rose", "rose", F("dafare.benvenuto"), ALTA, F("dafare.az_importa"), destinazione)]
    try:
        iniziato = bool(stato_utente.leggi_primo_avvio(imp)) if imp else True
    except Exception:                                       # noqa: BLE001  (Oggi si apre comunque)
        iniziato = True
    if not iniziato:
        voci.append(_voce("primo-avvio", "primo_avvio", F("dafare.ti_guido"), MEDIA, F("dafare.az_inizia"),
                          _destinazione("impostazioni", "informazioni"), saltati=[]))
    return voci


# ---------------------------------------------------------------- insieme
def costruisci(db: sqlite3.Connection, regole: Regole, rose: Rose, oggi: dict, ctx, certificato_giorni: int | None = None,
               amministratore: bool = False, adesso: datetime | None = None, lingua: str = "it", dal: datetime | None = None) -> list[dict]:
    """La lista ordinata (priorità 1 = alta, poi 2 e 3; a parità, nell'ordine dei controlli), al massimo MAX_VOCI voci e al
    massimo buon_senso.MAX_CONSIGLI consigli. `ctx` è il contesto dell'utente (percorsi dei suoi file); `dal` è quando è nato
    il suo account (ora locale; None = senza account o non noto). Non alza mai errori:
    un controllo che fallisce viene saltato."""
    adesso = adesso or datetime.now()
    stagione = consigli.stagione_corrente()
    ore, giornata = oggi.get("ore_mancanti"), oggi.get("giornata")
    aperta = not oggi.get("iniziata")
    rose_file = getattr(ctx, "rose", None)
    con_account = getattr(ctx, "utente_id", None) is not None
    imp = getattr(ctx, "impostazioni_avvisi", None)
    # fasi della giornata (fasi.py): «in_corso» = formazione chiusa, nessun consiglio su chi schierare; «finita» = la prossima è
    # ancora lontana: niente dubbi sui titolari (le probabili non ci sono ancora), restano rosa e mercato se superano il buon senso
    finita = oggi.get("fase") == "finita"
    controlli = []
    if aperta and giornata and not finita:
        controlli += [lambda: _titolari(db, regole, rose, giornata, ctx.scelte)]
    if aperta and giornata:
        controlli += [lambda: _copertura(db, regole, rose, lingua),
                      lambda: _formazione_non_salvata(db, regole, rose, ore, giornata, ctx.scelte)]
    controlli += [lambda: _certificato(certificato_giorni)]
    if rose_file is not None:
        controlli += [lambda: _rose_vecchie(db, stagione, regole, rose_file, adesso)]
    if aperta:
        recenti = _recenti(rose, getattr(ctx, "movimenti", None), adesso)
        controlli += [lambda: _svincolato(db, regole, rose, recenti), lambda: _scambio(db, regole, rose, recenti)]
    controlli += [lambda: _diario(db, stagione, rose, ctx.scelte, ctx.diario, regole, dal)]
    if amministratore or not con_account:
        controlli += [lambda: _dati_vecchi(db, adesso)]
    controlli += [lambda: _primo_avvio(imp)]

    voci: list[dict] = []
    for c in controlli:
        try:
            r = c()
        except Exception:                                   # noqa: BLE001  (Oggi si apre comunque)
            continue
        voci += r if isinstance(r, list) else [r] if r else []
    voci.sort(key=lambda v: v["priorita"])                   # ordinamento stabile: a parità resta l'ordine dei controlli
    return _limita_consigli(voci)[:MAX_VOCI]
