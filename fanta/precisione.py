"""«Quanto ci abbiamo preso»: pochi numeri onesti sulle giornate finite, anche quando vanno male.

Per l'utente (dalle voci del suo diario, quindi solo i suoi dati):
- fantavoto: di quanto sbaglia in media il fantavoto atteso dei suoi giocatori che hanno preso voto;
- gioca: quando l'app diceva «gioca N%», quante volte il giocatore ha preso voto davvero (per gruppi di N);
- confronto: in quante giornate la consigliata ha fatto più punti della formazione schierata, e quanti punti in tutto;
- squadra: punti attesi della consigliata contro punti fatti.
I numeri per giocatore sono quelli MOSTRATI allora quando la consigliata di quella giornata è stata salvata con i numeri
(istantanea, diario.py), altrimenti quelli RICOSTRUITI con i soli dati di prima della giornata: il campo `fonte` lo dice.
«Gioca N%» usa SOLO i mostrati (con le probabili formazioni) se ci sono almeno MIN_GIORNATE_MOSTRATI giornate così; se no i
ricostruiti, che non conoscono le probabili, e `gioca.fonte` = «ricostruiti» fa scrivere al client una frase diversa.

Su tutta la Serie A (`serie_a`, #374): una riga in più con l'errore del fantavoto atteso (contro quello della fantamedia) e «gioca
N%» di TUTTI i giocatori della Serie A, presi dal registro delle giornate (`registro_giornate.py`: i numeri mostrati prima di ogni
giornata, regole classiche), anche quando vanno male. Uguale per tutti gli utenti, niente dati personali. Il testo lo scrive il
server (`frasi.py`, chiavi `diario.serie_a*`): la web lo traduce, l'iPhone mostra `testo`.

Per il sito (in futuro, `python -m fanta affidabilita --pubblico`): gli stessi numeri del modello su tutti i giocatori della
Serie A con le regole classiche, più un riassunto delle formazioni solo se ci sono almeno `MINIMO_UTENTI` utenti. Niente nomi,
niente squadre, niente identificativi.
"""
from __future__ import annotations

import logging
import math
import sqlite3
from datetime import datetime

from . import consigli, diario, registro_giornate
from .affidabilita import giornate_concluse
from .frasi import F, Frase
from .modello import Parametri
from .regole import Regole

POCHI_DATI = diario.POCHI_DATI          # sotto queste giornate i client avvisano «ancora pochi dati»
GRUPPI_GIOCA = ((0, 40), (40, 70), (70, 90), (90, 101))     # fasce di «gioca N%» (N in percento, l'ultima comprende il 100)
POCHI_GIOCATORI = 20                    # un gruppo con meno giocatori di così è solo indicativo
MINIMO_UTENTI = 5                       # il riassunto pubblico delle formazioni esce solo con almeno tanti utenti (anonimato)
MASSIMO_GIORNATE_PUBBLICO = 12
MIN_GIORNATE_SERIE_A = 3                # la riga «su tutta la Serie A» ha i numeri da 3 giornate misurate del registro in su
LOG = logging.getLogger(__name__)


def _numero(x) -> float | None:
    return float(x) if isinstance(x, (int, float)) and not isinstance(x, bool) and x == x else None


MIN_GIORNATE_MOSTRATI = 3              # sotto queste giornate con i numeri mostrati, «gioca N%» usa quelli ricostruiti (e lo dice)


def numeri_giornata(voce: dict) -> tuple[list[tuple[float, float, float | None]], list[tuple[float, float, float | None]]]:
    """(mostrati, ricostruiti) di una voce del diario, ognuno [(p_voto, fantavoto atteso, fantavoto vero o None)].
    «Mostrati» = i numeri che l'app mostrava prima della scadenza (istantanea; le probabili formazioni comprese);
    «ricostruiti» = rifatti dopo con i soli dati di prima della giornata, SENZA le probabili formazioni."""
    veri = {g["id"]: g for g in voce.get("giocatori") or [] if isinstance(g, dict) and "id" in g}
    if not veri:
        return [], []
    ist = voce.get("istantanea") if isinstance(voce.get("istantanea"), dict) else {}
    mostrati = []
    for t in (ist.get("titolari") or []) + (ist.get("panchina") or []):
        p, a = (_numero(t.get("p_voto")), _numero(t.get("fv_atteso"))) if isinstance(t, dict) else (None, None)
        if p is not None and a is not None and t.get("id") in veri:
            mostrati.append((p, a, _numero(veri[t["id"]].get("fv"))))
    ricostruiti = [(p, a, _numero(g.get("fv"))) for g in veri.values()
                   if (p := _numero(g.get("p_voto"))) is not None and (a := _numero(g.get("fv_atteso"))) is not None]
    return mostrati, ricostruiti


def _fantavoto(numeri: list[tuple]) -> dict | None:
    """Errore medio (senza segno), scostamento medio (fatto meno atteso: positivo = hanno fatto più del previsto) e quota entro un punto."""
    diff = [f - a for _, a, f in numeri if f is not None]
    if not diff:
        return None
    return {"errore_medio": round(sum(abs(x) for x in diff) / len(diff), 1), "scostamento": round(sum(diff) / len(diff), 1),
            "entro_un_punto": round(100 * sum(1 for x in diff if abs(x) <= 1) / len(diff)), "voti": len(diff)}


def _gioca(numeri: list[tuple]) -> dict | None:
    """Per ogni fascia di «gioca N%»: quanto dicevamo in media (`detto`) e quanti hanno preso voto davvero (`giocato`), in percento.
    `principale` = la fascia da mettere in evidenza: tra quelle dal 70% in su, quella con più giocatori (la frase «quando diciamo
    che gioca...»). Si mostra anche quando il numero è brutto."""
    if not numeri:
        return None
    gruppi = []
    for da, a in GRUPPI_GIOCA:
        dentro = [(p, f) for p, _, f in numeri if da <= 100 * p < a]
        if dentro:
            gruppi.append({"da": da, "a": min(a, 100), "giocatori": len(dentro), "pochi": len(dentro) < POCHI_GIOCATORI,
                           "detto": round(100 * sum(p for p, _ in dentro) / len(dentro)),
                           "giocato": round(100 * sum(1 for _, f in dentro if f is not None) / len(dentro))})
    return {"giocatori": len(numeri), "gruppi": gruppi, "principale": _principale(gruppi)}


def _principale(gruppi: list[dict]) -> int | None:
    """L'indice della fascia da mettere in evidenza: tra quelle dal 70% in su, quella con più giocatori (None se non ce n'è)."""
    alti = [i for i, g in enumerate(gruppi) if g["da"] >= 70]
    return max(alti, key=lambda i: gruppi[i]["giocatori"]) if alti else None


def _confronto(voci: list[dict]) -> dict:
    """Le giornate in cui c'è la formazione schierata: quante volte la consigliata ha fatto di più, di meno, uguale; `punti` = somma
    di (consigliata - tua): positivo = seguendo sempre la consigliata avresti fatto più punti."""
    righe = [(v["consigliata"]["reale"], v["schierata"]["reale"]) for v in voci
             if isinstance(v.get("schierata"), dict) and isinstance(v.get("consigliata"), dict)
             and _numero(v["schierata"].get("reale")) is not None and _numero(v["consigliata"].get("reale")) is not None]
    if not righe:
        return {"giornate": 0}
    n = len(righe)
    return {"giornate": n, "meglio_consigliata": sum(1 for c, s in righe if c > s), "meglio_tua": sum(1 for c, s in righe if c < s),
            "pari": sum(1 for c, s in righe if c == s), "punti": round(sum(c - s for c, s in righe), 1),
            "media_consigliata": round(sum(c for c, _ in righe) / n, 1), "media_tua": round(sum(s for _, s in righe) / n, 1)}


def riassunto(voci: list[dict]) -> dict:
    """«Quanto ci abbiamo preso» dalle voci del diario (come le dà `diario.elenco`, con `istantanea`). `per_giornata` va dalla più
    vecchia alla più recente (per l'andamento). Tutti i campi numerici possono essere null se manca il dato."""
    voci = sorted([v for v in voci if isinstance(v, dict) and isinstance(v.get("consigliata"), dict)],
                  key=lambda v: (str(v.get("stagione", "")), int(v.get("giornata") or 0)))
    tutti: list[tuple] = []                 # per il fantavoto: in ogni giornata i mostrati se ci sono, se no i ricostruiti
    tutti_mostrati: list[tuple] = []
    tutti_ricostruiti: list[tuple] = []
    per_giornata = []
    fonti = {"mostrati": 0, "ricostruiti": 0}
    for v in voci:
        mostrati, ricostruiti = numeri_giornata(v)
        numeri, fonte = (mostrati, "mostrati") if mostrati else (ricostruiti, "ricostruiti") if ricostruiti else ([], None)
        tutti += numeri
        tutti_mostrati += mostrati
        tutti_ricostruiti += ricostruiti
        if fonte:
            fonti[fonte] += 1
        fv = _fantavoto(numeri)
        c, s = v["consigliata"], v.get("schierata") if isinstance(v.get("schierata"), dict) else None
        per_giornata.append({"stagione": v.get("stagione"), "giornata": v.get("giornata"), "giornata_lega": v.get("giornata_lega"),
                             "fonte": fonte, "errore_fantavoto": fv["errore_medio"] if fv else None, "voti": fv["voti"] if fv else 0,
                             "attesi": _numero(c.get("atteso")), "fatti": _numero(c.get("reale")),
                             "tua": _numero(s.get("reale")) if s else None,
                             "differenza": round(c["reale"] - s["reale"], 1) if s and _numero(s.get("reale")) is not None
                             and _numero(c.get("reale")) is not None else None})
    sq = diario.affidabilita(voci)
    n = len(per_giornata)
    # «gioca N%» onesto: solo quello che l'app ha detto davvero (con le probabili); con poche giornate così, i ricostruiti,
    # che non conoscono le probabili formazioni: `gioca.fonte` lo dice e il client usa un'altra frase
    if fonti["mostrati"] >= MIN_GIORNATE_MOSTRATI:
        gioca = _gioca(tutti_mostrati)
        fonte_gioca, giornate_gioca = "mostrati", fonti["mostrati"]
    else:
        gioca = _gioca(tutti_ricostruiti)
        fonte_gioca, giornate_gioca = "ricostruiti", sum(1 for v in voci if numeri_giornata(v)[1])
    if gioca:
        gioca |= {"fonte": fonte_gioca, "giornate": giornate_gioca}
    return {"giornate": n, "pochi_dati": n < POCHI_DATI, "giornate_minime": POCHI_DATI, "fonti": fonti,
            "fantavoto": _fantavoto(tutti), "gioca": gioca, "confronto": _confronto(voci),
            "squadra": None if not sq.get("giornate") else {k: sq.get(k) for k in (
                "giornate", "punti_medi_attesi", "punti_medi_fatti", "scarto_medio", "errore_medio", "dentro_fascia", "con_fascia",
                "percentuale_dentro", "fascia_dichiarata")},
            "per_giornata": per_giornata}


def _gioca_registro(righe: list[dict]) -> dict | None:
    """«Gioca N%» su tutta la Serie A dalle fasce di 10 punti del registro (per fascia: [giocatori, somma del detto, quanti hanno preso
    voto]), raccolte nelle fasce di GRUPPI_GIOCA: la stessa forma di `_gioca`."""
    fasce = [[0, 0.0, 0] for _ in range(registro_giornate.FASCE)]
    for r in righe:
        for b, f in enumerate(r.get("fasce") or []):
            if b < len(fasce) and isinstance(f, list) and len(f) == 3 and all(_numero(x) is not None for x in f):
                fasce[b] = [fasce[b][0] + int(f[0]), fasce[b][1] + float(f[1]), fasce[b][2] + int(f[2])]
    passo = 100 / registro_giornate.FASCE
    gruppi = []
    for da, a in GRUPPI_GIOCA:
        dentro = [f for b, f in enumerate(fasce) if da <= b * passo < a]
        n = sum(f[0] for f in dentro)
        if n > 0:
            gruppi.append({"da": da, "a": min(a, 100), "giocatori": n, "pochi": n < POCHI_GIOCATORI,
                           "detto": round(100 * sum(f[1] for f in dentro) / n), "giocato": round(100 * sum(f[2] for f in dentro) / n)})
    if not gruppi:
        return None
    return {"giocatori": sum(g["giocatori"] for g in gruppi), "gruppi": gruppi, "principale": _principale(gruppi)}


def _intero(x: float) -> int:
    """Arrotondato all'intero più vicino, il mezzo lontano dallo zero (come `Math.round` della web per i positivi)."""
    return int(math.copysign(math.floor(abs(x) + 0.5), x))


def _con_testo(frase: Frase) -> dict:
    return {"testo": str(frase), "frase": frase.json()}


def serie_a(db: sqlite3.Connection) -> dict | None:
    """La riga «su tutta la Serie A» di «Quanto ci abbiamo preso» (#374), dalle ultime giornate misurate del registro (al massimo
    `registro_giornate.FINESTRA`). Con meno di MIN_GIORNATE_SERIE_A giornate: `{giornate, giornate_minime, mancano, testo, frase}`
    («servono ancora N giornate»). Da lì in su anche `voti`, `errore_fantavoto` ed `errore_fantamedia` (radice dell'errore
    quadratico, in punti), `rispetto_fantamedia` (in percento: negativo = il fantavoto atteso sbaglia meno della fantamedia) e
    `gioca` (come `_gioca`). Si mostra anche quando i numeri sono brutti. None = niente riga: registro vuoto, spento prima di
    arrivare alle giornate che servono (non ci arriverebbe mai), o illeggibile (il Diario non si rompe per questa riga)."""
    try:
        righe = registro_giornate.ultime_misurate(db)
    except sqlite3.Error as e:
        LOG.warning("riga «su tutta la Serie A» del Diario non letta: %s", type(e).__name__)
        return None
    n = len(righe)
    mancano = max(0, MIN_GIORNATE_SERIE_A - n)
    if n == 0 or (mancano and not registro_giornate.acceso()):
        return None
    base = {"giornate": n, "giornate_minime": MIN_GIORNATE_SERIE_A, "mancano": mancano}
    if mancano:
        return base | _con_testo(F("diario.serie_a_attesa", n=mancano))
    m = registro_giornate.medie(righe)
    sq_m = sum(float(r.get("sq_modello") or 0) for r in righe)
    sq_f = sum(float(r.get("sq_fantamedia") or 0) for r in righe)
    rispetto = _intero(100 * (math.sqrt(sq_m / sq_f) - 1)) if m["voti"] and sq_f > 0 else None
    gioca = _gioca_registro(righe)
    principale = gioca["gruppi"][gioca["principale"]] if gioca and gioca["principale"] is not None else None
    parti = []
    if rispetto is not None:
        parti.append(F("diario.serie_a_fv_meno", pct=-rispetto) if rispetto < 0
                     else F("diario.serie_a_fv_piu", pct=rispetto) if rispetto > 0 else F("diario.serie_a_fv_pari"))
    if principale:
        parti.append(F("diario.serie_a_gioca", p=principale["detto"], k=_intero(principale["giocato"] / 10)))
    if not parti:
        return None
    frase = (F("diario.serie_a", n=n, fv=parti[0], gioca=parti[1]) if len(parti) == 2
             else F("diario.serie_a_solo", n=n, parte=parti[0]))
    return base | {"voti": m["voti"], "errore_fantavoto": m["errore_modello"], "errore_fantamedia": m["errore_fantamedia"],
                   "rispetto_fantamedia": rispetto, "gioca": gioca} | _con_testo(frase)


def aggregato_utenti(diari: list[list[dict]], minimo: int = MINIMO_UTENTI) -> dict | None:
    """Riassunto anonimo delle formazioni di più utenti (somme, niente per utente): None se gli utenti con almeno una giornata
    schierata sono meno di `minimo`, così nessuno si riconosce nei numeri."""
    confronti = [c for c in (_confronto(v) for v in diari) if c["giornate"]]
    if len(confronti) < minimo:
        return None
    giornate = sum(c["giornate"] for c in confronti)
    pct = lambda k: round(100 * sum(c[k] for c in confronti) / giornate)      # noqa: E731
    # solo percentuali e il numero di utenti a scaglioni (5, 10, 25, 50, 100...): niente conteggi esatti da incrociare
    return {"utenti_almeno": max(s for s in SCAGLIONI_UTENTI if s <= len(confronti)),
            "meglio_consigliata": pct("meglio_consigliata"), "meglio_tua": pct("meglio_tua"), "pari": pct("pari"),
            "punti_per_giornata": round(sum(c["punti"] for c in confronti) / giornate, 1)}


SCAGLIONI_UTENTI = (5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000)


def pubblico(db: sqlite3.Connection, diari: list[list[dict]] | None = None, massimo_giornate: int = MASSIMO_GIORNATE_PUBBLICO) -> dict:
    """Il riassunto per il sito: il modello su TUTTI i giocatori della Serie A nelle ultime giornate finite, ricostruito con i soli
    dati di prima di ogni giornata e con le regole classiche (mai quelle di una lega). Solo numeri: niente nomi, squadre o
    identificativi. `diari` (facoltativo) = le voci del diario di ogni utente, per `aggregato_utenti`."""
    regole = Regole()
    stagione = consigli.stagione_corrente()
    d = consigli.dati(db)
    tutti: list[tuple] = []
    per_giornata = []
    for g in giornate_concluse(db, stagione)[-massimo_giornate:]:
        pv = diario._previsti_e_veri(d, stagione, g, regole, Parametri())
        if pv is None:
            continue
        prev, _, fv_vero = pv
        numeri = [(float(prev.at[i, "p_voto"]), float(prev.at[i, "mu"]), fv_vero.get(i)) for i in prev.index]
        tutti += numeri
        fv = _fantavoto(numeri)
        per_giornata.append({"giornata": int(g), "errore_fantavoto": fv["errore_medio"] if fv else None, "voti": fv["voti"] if fv else 0})
    gioca = _gioca(tutti)
    if gioca:
        gioca["fonte"] = "ricostruiti"          # senza le probabili formazioni: la frase sul sito deve dirlo
    return {"aggiornato": datetime.now().isoformat(timespec="seconds"), "stagione": stagione, "giornate": len(per_giornata),
            "pochi_dati": len(per_giornata) < POCHI_DATI,
            "metodo": "ricostruito con i soli dati di prima di ogni giornata, senza le probabili formazioni, regole classiche",
            "fantavoto": _fantavoto(tutti), "gioca": gioca, "per_giornata": per_giornata,
            "formazioni": aggregato_utenti(diari or [])}
