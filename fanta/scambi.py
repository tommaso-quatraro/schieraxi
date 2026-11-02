"""Scambi: quanto vale un giocatore PER UNA SQUADRA, analisi di uno scambio e proposte vantaggiose per tutti e due.

Il valore di una rosa è la somma, sulle prossime giornate, dei punti attesi della sua formazione migliore.
Uno scambio conviene a una squadra se fa crescere quel valore. Per cercare gli scambi in fretta si usa una
stima veloce della formazione migliore (senza simulazioni); le proposte migliori si possono poi controllare
con la simulazione completa (come per la formazione).

Probabilità di giocare nelle prossime giornate:
- prossima giornata: dalle probabili formazioni (se ci sono);
- giornate successive: presenze recenti; chi è infortunato salta anche la giornata dopo, chi è squalificato no.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from functools import cached_property, lru_cache

import pandas as pd

from . import consigli, modello
from .lega import Rose
from .regole import RUOLI, Regole, modulo_in_numeri

ORIZZONTE = 5            # giornate considerate una per una (calendario e probabili)
GIORNATE_INFORTUNIO = 2  # chi oggi è infortunato: fuori anche per la giornata successiva
P_SENZA_VOTO = 0.05      # anche un titolare fisso ogni tanto non prende voto
P_ENTRA_DALLA_PANCHINA = 0.5
PESO_RESTO = 0.5         # il resto della stagione conta, ma meno (le rose e le gerarchie cambiano)
SOGLIA = 0.5             # punti in stagione: sotto questa cifra uno scambio non cambia davvero nulla
GIORNATE_STAGIONE = 38
TEMPO_MASSIMO_DUE = 20.0   # secondi: oltre, la ricerca dei 2 contro 2 si ferma con quello che ha trovato
MIN_BASE = 0.5           # punti attesi: sotto questa cifra le variazioni in % non hanno senso


@dataclass
class Valori:
    """Per ogni giornata dell'orizzonte: {id: (ruolo, p, mu)}."""
    giornate: list[int]
    resto: int                         # giornate della stagione dopo l'orizzonte
    per_giornata: list[dict[int, tuple[str, float, float]]]
    info: pd.DataFrame                 # nome, ruolo, squadra, quotazione per id

    @cached_property
    def ruoli(self) -> dict:
        """{id: ruolo}: la ricerca degli scambi chiede il ruolo decine di migliaia di volte, `info.at` è lento."""
        return self.info["ruolo"].to_dict()


def valori(db: sqlite3.Connection, regole: Regole, orizzonte: int = ORIZZONTE) -> Valori:
    stagione = consigli.stagione_corrente()
    prima = consigli.giornata_da_giocare(db, stagione, regole)
    if prima is None:
        raise ValueError("Il calendario della stagione non è ancora disponibile (di solito esce a luglio): previsioni e asta partono appena arriva. Aggiorna i dati più avanti.")
    d = consigli.dati(db)
    giornate = [g for g in range(prima, prima + orizzonte)
                if not d.partite[(d.partite["stagione"] == stagione) & (d.partite["giornata"] == g)].empty]
    oggi, _, _ = consigli.previsioni(db, regole, prima)
    fuori_ora = {i: s for i, s in zip(oggi.index, oggi["stato"]) if s in ("infortunato", "squalificato")}
    per_giornata = []
    for k, g in enumerate(giornate):
        if k == 0:
            p = oggi
        else:   # giornate future: niente probabili, presenze recenti (e infortuni noti oggi)
            p = modello.previsioni(d, stagione, g, regole, giocatori=d.calciatori).set_index("id")
        riga = {}
        for i, x in p.iterrows():
            pv = float(x["p_voto"])
            if k > 0:   # più avanti conta anche la presenza sul lungo periodo
                pv = 0.5 * pv + 0.5 * float(x["p_lungo"])
                if fuori_ora.get(i) == "infortunato":
                    if k < GIORNATE_INFORTUNIO:
                        pv = 0.0
                    else:
                        # rientrato: le sue presenze recenti sono basse per colpa dell'infortunio, non perché
                        # non sia considerato; conta quanto spesso parte titolare quando c'è
                        quota = float(x["quota_titolare"])
                        pv = max(pv, (quota + (1 - quota) * P_ENTRA_DALLA_PANCHINA) * (1 - P_SENZA_VOTO))
            riga[int(i)] = (x["ruolo"], pv, float(x["mu"]))
        per_giornata.append(riga)
    info = d.calciatori.set_index("id")[["nome", "ruolo", "squadra", "quotazione"]]
    resto = max(0, GIORNATE_STAGIONE - (giornate[-1] if giornate else prima))
    return Valori(giornate, resto, per_giornata, info)


# ---------------------------------------------------------------- valore veloce di una rosa
@lru_cache(maxsize=64)
def _moduli_e_massimi(moduli: tuple[str, ...]) -> tuple[tuple[tuple[str, int, int, int], ...], dict[str, int]]:
    """I moduli in numeri e il massimo di titolari per reparto: si calcolano una volta per elenco di moduli, non a ogni valutazione
    di rosa (se ne fanno decine di migliaia per ricerca). Il dizionario si legge soltanto."""
    elenco = tuple((m, *modulo_in_numeri(m)) for m in moduli)
    massimo = {"P": 1, "D": 0, "C": 0, "A": 0}
    for _, d, c, a in elenco:
        massimo["D"], massimo["C"], massimo["A"] = max(massimo["D"], d), max(massimo["C"], c), max(massimo["A"], a)
    return elenco, massimo


@lru_cache(maxsize=64)
def _conteggi(elenco: tuple[tuple[str, int, int, int], ...]) -> dict[str, tuple[int, ...]]:
    """Per ogni reparto, quanti titolari chiedono i moduli (tutti i numeri diversi, in ordine). Il dizionario si legge soltanto."""
    return {"P": (1,), "D": tuple(sorted({d for _, d, _, _ in elenco})), "C": tuple(sorted({c for _, _, c, _ in elenco})),
            "A": tuple(sorted({a for _, _, _, a in elenco}))}


@lru_cache(maxsize=4096)
def _reparto(lista: tuple[tuple[float, float], ...], conteggi: tuple[int, ...], posto: int | None,
             massimo: int) -> dict[int, tuple[float, float]]:
    """Un reparto: {titolari richiesti: (punti del reparto, di cui dalla panchina)}. `lista` = (p, mu) dei giocatori del ruolo
    nell'ordine della rosa; `posto` = posti in panchina per il ruolo (None = panchina senza posti per ruolo).
    Si ricorda: in una ricerca di scambi gli stessi reparti tornano migliaia di volte. Chi lo riceve lo legge soltanto."""
    ordinati = sorted(lista, key=lambda x: -x[0] * x[1])
    prefissi = None
    risultato = {}
    for n in conteggi:
        titolari, riserve = ordinati[:n], ordinati[n:]
        pezzo = sum(p * mu for p, mu in titolari)                           # posti scoperti: zero
        da_panchina = 0.0
        if riserve and titolari:
            prima_panchina = pezzo
            if prefissi is None:      # probabilità di «almeno j assenti» per ogni numero di titolari del ruolo, in un solo passaggio
                prefissi = _almeno_prefissi([1 - p for p, _ in ordinati], massimo)
            assenti = prefissi[len(titolari)]
            limite = min(len(titolari), posto) if posto is not None else len(titolari)     # panchina a posti fissi per ruolo
            pezzo += sum(p * mu * assenti[j] for j, (p, mu) in enumerate(riserve[:limite], 1))
            da_panchina = pezzo - prima_panchina
        risultato[n] = (pezzo, da_panchina)
    return risultato


def valore_giornata(ids: list[int], tabella: dict[int, tuple[str, float, float]], regole: Regole,
                    reparti: dict | None = None, dettaglio: dict | None = None) -> float:
    """Punti attesi della formazione migliore in una giornata, stima veloce.

    Titolari: i migliori per p*mu nel modulo migliore. Le riserve dello stesso ruolo entrano in ordine:
    la j-esima vale solo se mancano almeno j titolari di quel ruolo. Niente limite di cambi né modificatore.
    """
    per_ruolo: dict[str, list[tuple[float, float]]] = {r: [] for r in RUOLI}
    for i in ids:
        if i in tabella:
            r, p, mu = tabella[i]
            if r in per_ruolo:
                per_ruolo[r].append((p, mu))
    meglio = 0.0
    posti = regole.panchina.posti
    moduli, massimo = _moduli_e_massimi(tuple(regole.moduli))
    conteggi = _conteggi(moduli)
    # ogni reparto si calcola da solo (dipende solo dai suoi giocatori): in una ricerca di scambi cambia un reparto per volta,
    # gli altri tre sono quelli di prima e si riprendono già fatti (stesse operazioni, stessi numeri)
    pezzo_di = {r: _reparto(tuple(per_ruolo[r]), conteggi[r], (posti.get(r, 0) if posti else None), massimo[r]) for r in RUOLI}
    for m, d, c, a in moduli:
        servono = {"P": 1, "D": d, "C": c, "A": a}
        totale = 0.0
        panchina = 0.0
        pezzi = {}
        for r in RUOLI:
            pezzo, da_panchina = pezzo_di[r][servono[r]]
            panchina += da_panchina
            pezzi[r] = pezzo
            totale += pezzo
        if totale > meglio:
            meglio = totale
            if reparti is not None:
                reparti.clear()
                reparti.update(pezzi)
            if dettaglio is not None:             # quanto vale la panchina (parte del totale) e con che modulo
                dettaglio.clear()
                dettaglio.update(panchina=panchina, modulo=m)
    return meglio


def _almeno(probabilita: list[float]) -> list[float]:
    """[P(almeno 0 eventi), P(almeno 1), ...] con eventi indipendenti di probabilità diverse."""
    distribuzione = [1.0] + [0.0] * len(probabilita)
    for q in probabilita:
        for k in range(len(distribuzione) - 1, 0, -1):
            distribuzione[k] = distribuzione[k] * (1 - q) + distribuzione[k - 1] * q
        distribuzione[0] *= (1 - q)
    risultato, somma = [], 0.0
    for x in reversed(distribuzione):
        somma += x
        risultato.append(somma)
    return risultato[::-1]


def _almeno_prefissi(probabilita: list[float], massimo: int) -> list[list[float]]:
    """Per ogni k da 0 a `massimo`: `_almeno(probabilita[:k])`, con le stesse operazioni (stessi numeri) ma un solo passaggio.
    Il risultato si ricorda: in una ricerca di scambi cambiano uno o due reparti per volta, gli altri hanno le stesse probabilità
    di prima. Chi lo riceve lo legge soltanto."""
    return _almeno_prefissi_ricordati(tuple(probabilita), massimo)


@lru_cache(maxsize=2048)
def _almeno_prefissi_ricordati(probabilita: tuple[float, ...], massimo: int) -> list[list[float]]:
    n = min(len(probabilita), massimo)
    distribuzione = [1.0] + [0.0] * n
    risultati = [[1.0]]
    for passo, q in enumerate(probabilita[:n], 1):
        for k in range(passo, 0, -1):
            distribuzione[k] = distribuzione[k] * (1 - q) + distribuzione[k - 1] * q
        distribuzione[0] *= (1 - q)
        somma, cumulata = 0.0, []
        for x in reversed(distribuzione[:passo + 1]):
            somma += x
            cumulata.append(somma)
        risultati.append(cumulata[::-1])
    return risultati


def valore_rosa(ids: list[int], v: Valori, regole: Regole) -> list[float]:
    return [valore_giornata(ids, t, regole) for t in v.per_giornata]


def valore_reparti(ids: list[int], v: Valori, regole: Regole) -> dict[str, float]:
    """Punti attesi per reparto (P, D, C, A) sommati sulle giornate dell'orizzonte."""
    somma = {r: 0.0 for r in RUOLI}
    for t in v.per_giornata:
        pezzi: dict = {}
        valore_giornata(ids, t, regole, pezzi)
        for r, x in pezzi.items():
            somma[r] += x
    return somma


def totale(per_giornata: list[float], v: Valori) -> float:
    """Valore complessivo: le prossime giornate una per una, più il resto della stagione stimato
    dalle ultime giornate dell'orizzonte (dove gli infortuni di oggi sono già smaltiti)."""
    lontane = per_giornata[GIORNATE_INFORTUNIO:] or per_giornata
    return sum(per_giornata) + PESO_RESTO * v.resto * (sum(lontane) / len(lontane) if lontane else 0)


# ---------------------------------------------------------------- analisi e proposte
@dataclass
class Scambio:
    mia: str
    altra: str
    do: list[int]
    ricevo: list[int]
    guadagno_mio: float                  # punti attesi in più: prossime giornate + resto della stagione (pesato)
    guadagno_loro: float
    per_giornata_mio: list[float] = field(default_factory=list)
    per_giornata_loro: list[float] = field(default_factory=list)
    quotazione_do: int = 0
    quotazione_ricevo: int = 0
    reparti: dict = field(default_factory=dict)       # variazione % per reparto, {"mio": {...}, "loro": {...}}
    percentuale_mio: float | None = None              # variazione % del valore della mia rosa (prossime giornate)

    def come_dict(self, v: Valori) -> dict:
        nomi = lambda ids: [{"id": i, "nome": v.info.at[i, "nome"] if i in v.info.index else str(i),  # noqa: E731
                             "ruolo": v.info.at[i, "ruolo"] if i in v.info.index else "?",
                             "squadra": v.info.at[i, "squadra"] if i in v.info.index else "",
                             "quotazione": int(v.info.at[i, "quotazione"]) if i in v.info.index else 0} for i in ids]
        return {"formato": f"{len(self.do)}v{len(self.ricevo)}", "n_do": len(self.do), "n_ricevo": len(self.ricevo),
                "mia": self.mia, "altra": self.altra, "do": nomi(self.do), "ricevo": nomi(self.ricevo),
                "guadagno_mio": round(self.guadagno_mio, 2), "guadagno_loro": round(self.guadagno_loro, 2),
                "per_giornata_mio": [round(x, 2) for x in self.per_giornata_mio],
                "per_giornata_loro": [round(x, 2) for x in self.per_giornata_loro],
                "breve_mio": round(sum(self.per_giornata_mio), 2), "breve_loro": round(sum(self.per_giornata_loro), 2),
                "giornate": v.giornate, "resto": v.resto, "reparti": self.reparti,
                "percentuale_mio": self.percentuale_mio,
                "quotazione_do": self.quotazione_do, "quotazione_ricevo": self.quotazione_ricevo}


def _ids(rose: Rose, nome: str) -> list[int]:
    s = rose.squadra(nome)
    if not s:
        raise ValueError(f"Squadra non trovata: {nome}")
    return [g.id for g in s.giocatori if g.id is not None]


def _quot(v: Valori, ids: list[int]) -> int:
    return int(sum(v.info.at[i, "quotazione"] for i in ids if i in v.info.index))


def analizza(v: Valori, regole: Regole, rose: Rose, mia: str, altra: str, do: list[int], ricevo: list[int]) -> Scambio:
    a, b = _ids(rose, mia), _ids(rose, altra)
    if rose.squadra(mia).nome == rose.squadra(altra).nome:
        raise ValueError("Scegli un'altra squadra: non puoi scambiare con te stesso")
    if len(set(do)) != len(do) or len(set(ricevo)) != len(ricevo) or len(do) != len(ricevo) or not do:
        raise ValueError("Lo scambio deve essere tra lo stesso numero di giocatori, senza ripetizioni")
    if any(i not in v.info.index for i in list(do) + list(ricevo)):
        raise ValueError("Uno dei giocatori non è nel listone di Serie A: non si può valutare")
    if not set(do) <= set(a):
        raise ValueError(f"Non tutti i giocatori da dare sono in {mia}")
    if not set(ricevo) <= set(b):
        raise ValueError(f"Non tutti i giocatori da ricevere sono in {altra}")
    ruoli = lambda ids: sorted(v.info.at[i, "ruolo"] for i in ids if i in v.info.index)  # noqa: E731
    if ruoli(do) != ruoli(ricevo):
        raise ValueError("Lo scambio cambia il numero di giocatori per ruolo: le rose non resterebbero valide")
    a2 = [i for i in a if i not in do] + ricevo
    b2 = [i for i in b if i not in ricevo] + do
    prima_a, dopo_a = valore_rosa(a, v, regole), valore_rosa(a2, v, regole)
    prima_b, dopo_b = valore_rosa(b, v, regole), valore_rosa(b2, v, regole)
    pa = [y - x for x, y in zip(prima_a, dopo_a)]
    pb = [y - x for x, y in zip(prima_b, dopo_b)]
    reparti = {}
    for chi, prima, dopo in (("mio", a, a2), ("loro", b, b2)):
        x, y = valore_reparti(prima, v, regole), valore_reparti(dopo, v, regole)
        # con una base minuscola la percentuale non ha senso: sotto MIN_BASE punti si mostra 0
        reparti[chi] = {r: round(100 * (y[r] - x[r]) / x[r], 1) if x[r] >= MIN_BASE else 0.0 for r in RUOLI}
    s = Scambio(rose.squadra(mia).nome, rose.squadra(altra).nome, do, ricevo, totale(pa, v), totale(pb, v), pa, pb,
                _quot(v, do), _quot(v, ricevo))
    s.reparti = reparti
    s.percentuale_mio = (round(100 * (sum(dopo_a) - sum(prima_a)) / sum(prima_a), 1)
                         if sum(prima_a) >= MIN_BASE else 0.0)
    return s


def _coppia(v, regole, a, b, base_a, base_b, xs, ys):
    """Variazione per giornata (mia, loro) se io do `xs` e ricevo `ys`."""
    a2 = [i for i in a if i not in xs] + list(ys)
    b2 = [i for i in b if i not in ys] + list(xs)
    return ([y - x for x, y in zip(base_a, valore_rosa(a2, v, regole))],
            [y - x for x, y in zip(base_b, valore_rosa(b2, v, regole))])


def proponi(v: Valori, regole: Regole, rose: Rose, mia: str, altra: str | None = None, massimo: int = 10,
            soglia: float = SOGLIA, anche_due: bool = False, tempo_massimo: float = TEMPO_MASSIMO_DUE,
            fino_a: int = 0, max_valutazioni: int | None = None) -> list[Scambio]:
    """Scambi 1 contro 1 dello stesso ruolo in cui guadagnano tutte e due le squadre, e a richiesta anche scambi più grandi:
    `anche_due` aggiunge i 2 contro 2, `fino_a` (2-4) tutti gli N contro M fino a quella misura (anche 2 contro 1, 3 contro 2...).
    Gli scambi grandi sono moltissimi: si guardano solo i giocatori più promettenti, i più promettenti per primi, e ci si ferma
    dopo `max_valutazioni` calcoli (o `tempo_massimo` secondi): vedi scambi_multi.cerca_grandi."""
    import time
    from . import scambi_multi
    inizio = time.monotonic()
    a = _ids(rose, mia)
    if altra is not None and rose.squadra(altra) is None:
        raise ValueError(f"Squadra non trovata: {altra}")
    altre = [s.nome for s in rose.squadre if s.nome != rose.squadra(mia).nome
             and (altra is None or s.nome == rose.squadra(altra).nome)]
    base_a = valore_rosa(a, v, regole)
    ruolo = v.ruoli.get
    formati = scambi_multi.formati_da_cercare(anche_due, fino_a)
    cont_a = scambi_multi._conteggio(rose.squadra(mia), v, [], [])
    trovati: list[Scambio] = []
    for nome in altre:
        b = _ids(rose, nome)
        base_b = valore_rosa(b, v, regole)
        cont_b = scambi_multi._conteggio(rose.squadra(nome), v, [], [])
        singoli = {}
        for x in a:
            for y in b:      # di norma lo stesso ruolo; di ruolo diverso solo se le rose hanno posto (massimo e minimo per ruolo)
                if ruolo(x) and ruolo(y) and (ruolo(x) == ruolo(y) or scambi_multi.ok_dopo(cont_a, cont_b, [ruolo(x)], [ruolo(y)], regole)):
                    singoli[(x, y)] = _coppia(v, regole, a, b, base_a, base_b, (x,), (y,))
        for (x, y), (pa, pb) in singoli.items():
            ga, gb = totale(pa, v), totale(pb, v)
            if ga >= soglia and gb >= soglia:
                trovati.append(Scambio(rose.squadra(mia).nome, nome, [x], [y], ga, gb, pa, pb,
                                       quotazione_do=_quot(v, (x,)), quotazione_ricevo=_quot(v, (y,))))
        if formati:
            restante = max(0.0, tempo_massimo - (time.monotonic() - inizio))
            trovati += scambi_multi.cerca_grandi(v, regole, rose, rose.squadra(mia).nome, nome, a, b, base_a, base_b, formati,
                                                 singoli, soglia, max_valutazioni, restante)
    # prima quelli più equilibrati e utili per me: il minimo dei due guadagni pesa, così l'altro è invogliato
    trovati.sort(key=lambda s: -(s.guadagno_mio + 0.5 * min(s.guadagno_loro, s.guadagno_mio)))
    # proposte varie: ogni giocatore (dato o ricevuto) compare al massimo due volte
    scelti, conta = [], {}
    for s in trovati:
        coinvolti = list(s.do) + list(s.ricevo)
        if any(conta.get(i, 0) >= 2 for i in coinvolti):
            continue
        for i in coinvolti:
            conta[i] = conta.get(i, 0) + 1
        scelti.append(s)
        if len(scelti) >= massimo:
            break
    return scelti


# ---------------------------------------------------------------- offerta ricevuta, scritta a parole
def _chiave_nome(nome: str) -> tuple[str, ...]:
    """Le parole che identificano un giocatore nel testo: 'Castro S.' -> ('castro',), 'De Ketelaere' -> ('de', 'ketelaere')."""
    from . import nomi
    parole = [p for p in nome.split() if not p.endswith(".")]            # 'S.' e 'Se.' sono sigle del nome di battesimo
    return tuple(x for p in parole for x in nomi.normalizza(p).split())


def riconosci_nel_testo(testo: str, rose: Rose, mia: str, altra: str | None = None) -> dict:
    """Trova nel testo di un messaggio i giocatori della mia rosa (quelli che do) e di un'altra (quelli che ricevo): basta il
    cognome, e chi è di chi lo dice la rosa, non l'ordine delle frasi. Senza `altra` sceglie la squadra con più giocatori nominati."""
    from . import nomi
    parole = set(nomi.normalizza(testo).split())

    def trova(nome_squadra: str) -> tuple[list[int], list[str]]:
        s = rose.squadra(nome_squadra)
        candidati: dict[tuple[str, ...], list] = {}
        for g in (s.giocatori if s else []):
            chiave = _chiave_nome(g.nome)
            if g.id is not None and chiave and all(x in parole for x in chiave):
                candidati.setdefault(chiave, []).append(g)
        ids, ambigui = [], []
        for lista in candidati.values():
            if len(lista) == 1:
                ids.append(lista[0].id)
            else:
                ambigui.append(" / ".join(g.nome for g in lista))
        return ids, ambigui

    do, ambigui = trova(mia)
    scelta, migliore = altra, ([], [])
    if altra:
        migliore = trova(altra)
    else:
        for s in rose.squadre:
            if s.nome == mia:
                continue
            ris = trova(s.nome)
            if len(ris[0]) > len(migliore[0]):
                scelta, migliore = s.nome, ris
    return {"con": scelta, "do": do, "ricevo": migliore[0], "ambigui": ambigui + migliore[1]}
