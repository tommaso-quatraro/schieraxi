"""Squalificati e diffidati calcolati dai cartellini dei voti (#640).

NON È ANCORA USATO DAL CALCOLO: nessun altro modulo lo chiama. Oggi squalificati e diffidati arrivano solo dalla pagina delle
probabili; questo modulo è la regola pronta per quando la pagina non ha una lettura buona. Non è agganciato perché la misura
sull'archivio (qui sotto) ha dato, per la somma di ammonizioni, falsi squalificati oltre la soglia decisa per agganciarlo (uno
ogni cento segnalati); si rimisura con `prove/misura_squalifiche.py`.

La regola, dal Codice di giustizia sportiva della FIGC (testo aggiornato al 22/12/2025, letto il 12/11/2026 dal sito della FIGC):
- art. 9 comma 5: squalifica per una gara alla quinta ammonizione, poi dopo altre cinque (10), quattro (14), tre (17), due (19)
  e a ogni ammonizione in più;
- art. 9 comma 7: l'espulsione porta almeno una gara di squalifica (qui sempre una: le più lunghe non si indovinano);
- art. 19 comma 9: le ammonizioni decadono a fine stagione (dentro la stessa lega seguono il giocatore che cambia squadra);
- art. 21 commi 2, 4 e 7: la squalifica si sconta nelle gare della squadra finite con un risultato valido, con la squadra nuova
  se il giocatore l'ha cambiata. Quindi conta la prima partita che la squadra gioca davvero, in ordine di data: una partita
  rinviata non la sconta, un recupero sì.

Partite non ancora giocate, secondo l'ora (`adesso`): una che comincia da MARGINE_RISULTATI prima di `adesso` in poi è in
programma, in corso o finita da poco e non ancora segnata come giocata, e sconta la squalifica; una cominciata da più di
MARGINE_RISULTATI e ancora non giocata è rinviata, e non la sconta. Serve l'ora perché l'archivio da solo non lo dice quando la
partita rinviata è l'ultima della sua giornata. Limiti noti:
- nella mezza giornata dopo l'inizio, una partita rinviata conta come giocata: in quelle ore lo squalificato risulta libero
  per la giornata dopo;
- se il calendario non si aggiorna, una partita giocata ma non ancora segnata da più di mezza giornata sembra rinviata: la
  squalifica resta aperta una giornata di troppo.

Cosa i nostri dati non dicono:
- nei voti una riga ha il giallo o il rosso, mai tutti e due (0 righe su 15.417): un giallo seguito dal rosso nella stessa
  partita arriva come solo rosso. Dopo un'espulsione il nostro conto delle ammonizioni può essere indietro di uno, quindi per
  quel giocatore non si dice né «squalificato per somma» né «diffidato» fino a fine stagione;
- un'ammonizione che nei voti non c'è non si vede (è la spiegazione più semplice del falso rimasto nella misura, non
  verificata);
- squalifiche di più giornate, squalifiche non nate da un cartellino, squalifiche rimaste dalla stagione prima (art. 21 comma
  6), e quelle scontate in una gara ufficiale che non è nel nostro calendario (art. 19 comma 6): non si vedono.

Misura del 12/11/2026 sull'archivio (2025-26 intero e 2026-27 fino alla giornata 11, 47 giornate): per ogni giornata, chi
risulta squalificato usando solo le partite di prima, e se poi è nel tabellino di quella partita (allora è un falso).
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
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterable, Mapping, NamedTuple

SOGLIE = (5, 10, 14, 17, 19)          # ammonizioni che fanno scattare la squalifica; dopo l'ultima, ogni ammonizione
MARGINE_RISULTATI = timedelta(hours=12)   # come consigli.MARGINE_RISULTATI: una partita non giocata è in corso o da segnare
                                          # fino a mezza giornata dopo l'inizio; poi è rinviata


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

    per_giocatore: dict[int, list[tuple[_Quando, bool, bool]]] = {}   # giocatore -> [(quando, giallo, rosso)]
    for c in cartellini:
        if c["stagione"] != stagione or not (c["ammonizioni"] or c["espulsioni"]):
            continue
        g = int(c["giornata"])
        per_giocatore.setdefault(int(c["calciatore_id"]), []).append(
            (quando.get((g, c["squadra"]), _Quando(None, g)), bool(c["ammonizioni"]), bool(c["espulsioni"])))

    esito = {}
    for cid, carte in per_giocatore.items():
        squadra = squadre.get(cid)
        meta = quando.get((giornata, squadra))           # la partita per cui si chiede
        if meta is None:
            continue
        carte = [c for c in carte if _prima(c[0], meta)]
        if not carte:
            continue
        gialli = sum(1 for _, giallo, rosso in carte if giallo and not rosso)
        certo = not any(rosso for _, _, rosso in carte)  # un rosso può nascondere un giallo della stessa partita
        ultimo = carte[0]
        for c in carte[1:]:
            if _prima(ultimo[0], c[0]):
                ultimo = c
        # Solo l'ultimo cartellino può lasciare una squalifica aperta: dopo uno più vecchio il giocatore è tornato in campo.
        decisivo = ultimo[2] or (certo and _scatta(gialli))
        squalificato = decisivo and not _scontata(ultimo[0], meta, della_squadra[squadra], da_giocare_dal)
        diffidato = certo and _scatta(gialli + 1)
        if squalificato or diffidato:
            esito[cid] = Stato(squalificato, diffidato)
    return esito


def _scontata(cartellino: _Quando, meta: _Quando, della_squadra: list[tuple[_Quando, bool]], da_giocare_dal: str) -> bool:
    """Se tra il cartellino e la partita `meta` la squadra ha un'altra partita in cui la squalifica si sconta: una giocata,
    oppure una non ancora giocata che comincia da `da_giocare_dal` in poi (in programma, come un recupero a metà settimana;
    in corso; o finita da poco e non ancora segnata come giocata). Una partita non giocata cominciata da più di
    MARGINE_RISULTATI è rinviata e non la sconta, come una senza data. Non conta la partita della stessa giornata del
    cartellino: è quella del cartellino, o quella della squadra nuova giocata quando il giocatore era ancora nella vecchia."""
    return any(q.giornata != cartellino.giornata and _prima(cartellino, q) and _prima(q, meta)
               and (giocata or (q.data is not None and q.data >= da_giocare_dal))
               for q, giocata in della_squadra)
