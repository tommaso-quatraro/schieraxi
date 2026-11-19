"""Squalificati e diffidati calcolati dai cartellini dei voti (#640, nel calcolo dal #668).

Nel calcolo (`in_uso`) valgono SOLO LE ESPULSIONI: chi è stato espulso e non ha ancora saltato una partita della sua squadra è
squalificato. Niente squalifiche per somma di ammonizioni e niente diffidati: vengono dal conto delle ammonizioni, che
sull'archivio dà falsi squalificati oltre la soglia decisa per usarlo (uno ogni cento segnalati; vedi la misura qui sotto, si
rifà con `prove/misura_squalifiche.py`).
Si usa solo quando la giornata non ha una lettura buona delle probabili (`modello.previsioni`, `dai_cartellini`): con una
lettura buona vince la fonte, e una differenza a giornata cominciata va nel registro dei controlli
(`controlli.squalificati_cartellini`). L'ora non è mai quella vera: è quella dell'ultimo aggiornamento riuscito del calendario
(`ora_calendario`), e con i risultati fermi (`risultati_fermi`) la regola non si usa. `calcola` resta la regola intera, per
le misure.

La regola, dal Codice di giustizia sportiva della FIGC (testo aggiornato al 22/12/2025, letto il 12/11/2026 dal sito della FIGC):
- art. 9 comma 5: squalifica per una gara alla quinta ammonizione, poi dopo altre cinque (10), quattro (14), tre (17), due (19)
  e a ogni ammonizione in più;
- art. 9 comma 7: l'espulsione porta almeno una gara di squalifica (qui sempre una: le più lunghe non si indovinano);
- art. 19 comma 9: le ammonizioni decadono a fine stagione (dentro la stessa lega seguono il giocatore che cambia squadra);
- art. 21 commi 2, 4 e 7: la squalifica si sconta nelle gare della squadra finite con un risultato valido, con la squadra nuova
  se il giocatore l'ha cambiata. Quindi conta la prima partita che la squadra gioca davvero, in ordine di data: una partita
  rinviata non la sconta, un recupero sì. Per chi ha cambiato squadra la data del trasferimento non la sappiamo: conta anche
  una partita giocata dalla squadra di allora dopo il cartellino (via prudente: se era già andato via è un mancato, non un
  falso squalificato).

Partite non ancora giocate, secondo l'ora (`adesso`): una che comincia da MARGINE_RISULTATI prima di `adesso` in poi è in
programma, in corso o finita da poco e non ancora segnata come giocata, e sconta la squalifica; una cominciata da più di
MARGINE_RISULTATI e ancora non giocata è rinviata, e non la sconta. Serve l'ora perché l'archivio da solo non lo dice quando la
partita rinviata è l'ultima della sua giornata. Limiti noti, e cosa fa `in_uso`:
- nella mezza giornata dopo l'inizio, una partita rinviata conta come giocata: in quelle ore lo squalificato risulta libero
  per la giornata dopo (un mancato, non un falso);
- se il calendario non si aggiorna, una partita giocata ma non ancora segnata da più di mezza giornata sembrerebbe rinviata, e
  la squalifica resterebbe aperta una giornata di troppo. Per questo `in_uso` passa come `adesso` l'ora dell'ultimo
  aggiornamento riuscito del calendario: per quel calendario la partita è ancora in programma;
- se il calendario si aggiorna ma la fonte non segna il risultato, o se una partita rinviata resta con la data vecchia, una
  partita cominciata da più di mezza giornata non è segnata giocata e non si sa quale dei due casi sia: `in_uso` non usa la
  regola (`risultati_fermi`). Non si riusa la definizione di «rinviata» di `rinvii.py` (fuori dal turno della sua giornata):
  un recupero in programma prima della giornata sarebbe «rinviato» anche se la squalifica si sconta lì, e una partita del
  turno non segnata ore dopo l'inizio non lo sarebbe anche se può esserlo.

Cosa i nostri dati non dicono:
- nei voti una riga ha il giallo o il rosso, mai tutti e due (0 righe su 15.417): un giallo seguito dal rosso nella stessa
  partita arriva come solo rosso. Dopo un'espulsione il nostro conto delle ammonizioni può essere indietro di uno, quindi per
  quel giocatore non si dice né «squalificato per somma» né «diffidato» fino a fine stagione;
- un'ammonizione che nei voti non c'è non si vede (è la spiegazione più semplice del falso rimasto nella misura, non
  verificata);
- squalifiche di più giornate, squalifiche non nate da un cartellino, squalifiche rimaste dalla stagione prima (art. 21 comma
  6), e quelle scontate in una gara ufficiale che non è nel nostro calendario (art. 19 comma 6): non si vedono.

Misura del 12/11/2026 sull'archivio (2025-26 intero e 2026-27 fino alla giornata 11, 47 giornate): per ogni giornata, chi
risulta squalificato usando solo le partite di prima, e se poi è nel tabellino di quella partita (allora è un falso). Fatta
prima che la regola ricevesse l'ora; con l'ora, sull'archivio fino alla giornata 8 del 2026-27, i numeri non cambiano.
- 164 segnalati, 1 falso (0,61%). Per espulsione 72 segnalati, nessun falso; per somma di ammonizioni 92 (88 alla quinta,
  4 alla decima), 1 falso: 1,09%, sopra la soglia dell'1%. Lo 0,61% di tutti i segnalati è più basso solo perché ci sono
  dentro le espulsioni. Le soglie oltre la decima non si sono mai viste;
- i falsi misurati sono un minimo: chi è segnalato a torto ma poi non gioca per un altro motivo (infortunio, scelta
  dell'allenatore) conta come giusto;
- contro l'elenco della fonte, giornate 9-12 del 2026-27: squalificati 6 su 7 (il mancato è una squalifica di più giornate),
  nessuno solo nostro; diffidati 15 su 15, nessuno solo nostro.
Con un falso solo il tasso vero può stare sia sotto sia sopra l'1%. In più, la regola del conto incerto è nata guardando i
falsi di una prima versione della regola senza di essa, sugli stessi dati: quella versione serviva solo alla misura e non è
nel repository, quindi i suoi numeri (nella pull request #648) da qui non si rifanno.
Misura rifatta il 19/11/2026 su tutte le giornate dell'archivio locale (2025-26 intero e 2026-27 fino alla giornata 8, 44
giornate; #668): 160 segnalati, 1 falso (0,62%); per espulsione 68, nessun falso; per somma di ammonizioni 92, 1 falso
(1,09%, ancora sopra la soglia). Per questo nel calcolo vanno solo le espulsioni.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from typing import Iterable, Mapping, NamedTuple

SOGLIE = (5, 10, 14, 17, 19)          # ammonizioni che fanno scattare la squalifica; dopo l'ultima, ogni ammonizione
MARGINE_RISULTATI = timedelta(hours=12)   # come consigli.MARGINE_RISULTATI: una partita non giocata è in corso o da segnare
                                          # fino a mezza giornata dopo l'inizio; poi è rinviata
GIORNI_FERMI = timedelta(days=14)     # come sentinella.GIORNI_INDIETRO: i risultati fermi si cercano nelle ultime due settimane
PASSO_CALENDARIO = "calendario"       # la riga del passo in `aggiornamenti` (archivio.PASSI): `quando` = ultimo successo


class Stato(NamedTuple):
    squalificato: bool
    diffidato: bool


class _Quando(NamedTuple):
    """Quando si gioca una partita: la data («2026-11-08 20:45», None se manca) e il numero di giornata."""
    data: str | None
    giornata: int


def _scatta(n: int) -> bool:
    """Se l'ammonizione numero `n` della stagione porta una squalifica."""
    return n in SOGLIE or n > SOGLIE[-1]


def _data(valore) -> str | None:
    return valore if isinstance(valore, str) and valore.strip() else None


def _prima(a: _Quando, b: _Quando) -> bool:
    """`a` si gioca prima di `b`: per data; se una delle due date manca, per numero di giornata."""
    if a.data and b.data:
        return a.data < b.data
    return a.giornata < b.giornata


def calcola(cartellini: Iterable[Mapping], partite: Iterable[Mapping], stagione: str, giornata: int,
            squadre: Mapping[int, str], adesso: datetime) -> dict[int, Stato]:
    """Chi è squalificato o diffidato per la partita della sua squadra nella `giornata`: {calciatore_id: Stato}. Chi non è né
    l'uno né l'altro non c'è.

    `cartellini`: le righe dei voti (stagione, giornata, calciatore_id, squadra, ammonizioni, espulsioni).
    `partite`: il calendario (stagione, giornata, data, casa, trasferta, giocata).
    `squadre`: la squadra di adesso di ogni giocatore; chi non c'è, o ha la squadra che non gioca la giornata, si salta.
    `adesso`: l'ora a cui si chiede; dice se una partita non giocata è in programma (o in corso) oppure rinviata.
    Contano solo i cartellini della stagione presi prima di quella partita: la stessa funzione vale per le giornate passate.
    """
    quando: dict[tuple[int, str], _Quando] = {}                       # (giornata, squadra) -> quando gioca
    della_squadra: dict[str, list[tuple[_Quando, bool]]] = {}         # squadra -> [(quando, giocata)]
    for p in partite:
        if p["stagione"] != stagione:
            continue
        q = _Quando(_data(p["data"]), int(p["giornata"]))
        for s in (p["casa"], p["trasferta"]):
            quando[(q.giornata, s)] = q
            della_squadra.setdefault(s, []).append((q, bool(p["giocata"])))
    da_giocare_dal = (adesso - MARGINE_RISULTATI).strftime("%Y-%m-%d %H:%M")   # non giocata e cominciata prima: rinviata

    per_giocatore: dict[int, list[tuple[_Quando, bool, bool, str]]] = {}   # giocatore -> [(quando, giallo, rosso, squadra)]
    for c in cartellini:
        if c["stagione"] != stagione or not (c["ammonizioni"] or c["espulsioni"]):
            continue
        g = int(c["giornata"])
        per_giocatore.setdefault(int(c["calciatore_id"]), []).append(
            (quando.get((g, c["squadra"]), _Quando(None, g)), bool(c["ammonizioni"]), bool(c["espulsioni"]), c["squadra"]))

    esito = {}
    for cid, carte in per_giocatore.items():
        squadra = squadre.get(cid)
        meta = quando.get((giornata, squadra))           # la partita per cui si chiede
        if meta is None:
            continue
        carte = [c for c in carte if _prima(c[0], meta)]
        if not carte:
            continue
        gialli = sum(1 for _, giallo, rosso, _ in carte if giallo and not rosso)
        certo = not any(rosso for _, _, rosso, _ in carte)  # un rosso può nascondere un giallo della stessa partita
        ultimo = carte[0]
        for c in carte[1:]:
            if _prima(ultimo[0], c[0]):
                ultimo = c
        # Solo l'ultimo cartellino può lasciare una squalifica aperta: dopo uno più vecchio il giocatore è tornato in campo.
        decisivo = ultimo[2] or (certo and _scatta(gialli))
        # Cambio di squadra: la data del trasferimento non la sappiamo. Le partite giocate dalla squadra di allora dopo il
        # cartellino contano come scontate (via prudente: al peggio un mancato, se era già andato via, mai un falso).
        di_allora = [(q, True) for q, giocata in della_squadra.get(ultimo[3], []) if giocata] if ultimo[3] != squadra else []
        squalificato = decisivo and not _scontata(ultimo[0], meta, della_squadra[squadra] + di_allora, da_giocare_dal)
        diffidato = certo and _scatta(gialli + 1)
        if squalificato or diffidato:
            esito[cid] = Stato(squalificato, diffidato)
    return esito


def _scontata(cartellino: _Quando, meta: _Quando, della_squadra: list[tuple[_Quando, bool]], da_giocare_dal: str) -> bool:
    """Se tra il cartellino e la partita `meta` la squadra (più, per chi l'ha cambiata, le partite giocate dalla squadra di
    allora) ha un'altra partita in cui la squalifica si sconta: una giocata,
    oppure una non ancora giocata che comincia da `da_giocare_dal` in poi (in programma, come un recupero a metà settimana;
    in corso; o finita da poco e non ancora segnata come giocata). Una partita non giocata cominciata da più di
    MARGINE_RISULTATI è rinviata e non la sconta, come una senza data. Non conta la partita della stessa giornata del
    cartellino: è quella del cartellino, o quella della squadra nuova giocata quando il giocatore era ancora nella vecchia."""
    return any(q.giornata != cartellino.giornata and _prima(cartellino, q) and _prima(q, meta)
               and (giocata or (q.data is not None and q.data >= da_giocare_dal))
               for q, giocata in della_squadra)


# ---------------------------------------------------------------- la regola nel calcolo (#668)
def espulsioni(cartellini: Iterable[Mapping]) -> list[Mapping]:
    """I cartellini con un'espulsione. Con questi soli `calcola` dice gli squalificati per espulsione e basta: niente somma di
    ammonizioni né diffidati (con un rosso il conto delle ammonizioni non è certo). È la parte della regola usata nel calcolo,
    e quella che `prove/misura_squalifiche.py` conta come «per espulsione»."""
    return [c for c in cartellini if c["espulsioni"]]


def ora_calendario(db: sqlite3.Connection) -> datetime | None:
    """L'ora dell'ultimo aggiornamento riuscito del calendario (passo «calendario» in `aggiornamenti`, ora italiana come le date
    delle partite); None se non è mai riuscito o non si legge. Un passo fallito lascia l'ora dell'ultimo successo."""
    r = db.execute("SELECT quando FROM aggiornamenti WHERE cosa = ?", (PASSO_CALENDARIO,)).fetchone()
    try:
        return datetime.fromisoformat(str(r[0])[:19]) if r and r[0] else None
    except ValueError:
        return None


def risultati_fermi(partite: Iterable[Mapping], stagione: str, ora: datetime) -> bool:
    """Se per il calendario aggiornato all'`ora` una partita della stagione è cominciata da più di MARGINE_RISULTATI (e da meno
    di GIORNI_FERMI) e non è segnata giocata. Può essere un risultato fermo (la squalifica si è scontata) o un rinvio rimasto con
    la data vecchia (non si è scontata): la regola non sa quale dei due, quindi non si usa. Una partita rinviata con una data
    nuova o senza data non conta. Stessa soglia di `calcola`: è proprio la partita che `calcola` direbbe rinviata."""
    da = (ora - GIORNI_FERMI).strftime("%Y-%m-%d %H:%M")
    a = (ora - MARGINE_RISULTATI).strftime("%Y-%m-%d %H:%M")
    return any(p["stagione"] == stagione and not p["giocata"] and (d := _data(p["data"])) is not None and da <= d[:16] < a
               for p in partite)


_PARTITE = ("stagione", "giornata", "data", "casa", "trasferta", "giocata")
_VOTI = ("stagione", "giornata", "calciatore_id", "squadra", "ammonizioni", "espulsioni")


def in_uso(db: sqlite3.Connection, stagione: str, giornata: int) -> dict[int, Stato] | None:
    """La regola usata nel calcolo: chi è squalificato per espulsione per la partita della sua squadra nella `giornata`
    ({calciatore_id: Stato}; chi non lo è non c'è), con la squadra di oggi (il listone) e, come ora, quella dell'ultimo
    aggiornamento riuscito del calendario. None se la regola non si può usare: calendario mai aggiornato, o risultati fermi."""
    ora = ora_calendario(db)
    if ora is None:
        return None
    partite = [dict(zip(_PARTITE, r)) for r in
               db.execute(f"SELECT {', '.join(_PARTITE)} FROM partite WHERE stagione = ?", (stagione,))]
    if risultati_fermi(partite, stagione, ora):
        return None
    carte = [dict(zip(_VOTI, r)) for r in db.execute(
        f"SELECT {', '.join(_VOTI)} FROM voti WHERE stagione = ? AND (ammonizioni > 0 OR espulsioni > 0)", (stagione,))]
    squadre = {int(cid): s for cid, s in db.execute("SELECT id, squadra_slug FROM calciatori WHERE squadra_slug IS NOT NULL")}
    return calcola(espulsioni(carte), partite, stagione, giornata, squadre, ora)
