"""Scelta della formazione: 11 titolari, modulo e ordine della panchina con il massimo dei punti attesi.

I punti attesi tengono conto delle sostituzioni con le regole della lega (panchina libera o per ruolo, numero massimo di
cambi, cambio modulo, voto d'ufficio, modificatore difesa). Si contano esatti dalle probabilità di prendere voto (p_voto);
le simulazioni, uguali per tutte le formazioni a confronto, restano per il modificatore difesa, per l'oscillazione e per gli stili.
"""
from __future__ import annotations

import math
from collections.abc import Callable, Collection
from dataclasses import dataclass, field
from functools import lru_cache

import numpy as np

from .punteggio import modificatore_difesa, modulo_valido
from .regole import RUOLI, Regole, modulo_in_numeri

ORDINE_RUOLO = {r: i for i, r in enumerate(RUOLI)}
SCARTO_VOTO = 0.6     # variabilità tipica di un voto intorno alla sua media
# Come sceglie uno stile: punteggio scelto = atteso - giu x (atteso - brutta giornata) + su x (giornata eccezionale - atteso),
# dove brutta/eccezionale sono il 10% peggiore e il 10% migliore delle giornate simulate.
# Il peso di base è zero (#612): la consigliata è la formazione con più punti attesi. Prima toglieva 0,15 x (atteso - brutta
# giornata): misurato su 880 rose a sorte in 44 giornate costava 0,11 punti veri a giornata [0,03; 0,19] e faceva dipendere
# la scelta dal seme della simulazione (il 10° percentile di 600 estrazioni è un criterio rumoroso).
PESO_BASE = (0.0, 0.0)
# Gli stili sono preset completi: (id, nome, peso rischio/giornata eccezionale, inclinazione del modulo, descrizione di una riga).
# L'inclinazione (punti per difensore, punti per attaccante oltre il 4-x-3) sposta solo la scelta del MODULO. Valori misurati con il
# backtest sulle rose della lega (docs/STILI.md): nessuna perdita oltre il rumore di misura. "Equilibrata" è la consigliata.
LIVELLI_RISCHIO = [
    (-2, "Molto sicura", (1.5, 0.0), (0.5, 0.0),
     "Punta su chi gioca quasi di sicuro e preferisce difese più folte: meno rischio di una brutta giornata, a costo di qualche punto atteso."),
    (-1, "Sicura", (0.6, 0.0), (0.5, 0.0),
     "Titolari più sicuri e, a parità di punti, una difesa più folta: perde al massimo qualche decimo di punto atteso."),
    (0, "Equilibrata", PESO_BASE, (0.0, 0.0),
     "La formazione con più punti attesi: è quella consigliata."),
    (1, "Rischiosa", (0.0, 0.25), (0.0, 0.5),
     "Qualche rischio in più su chi può fare molti punti e, a parità, un attaccante in più: più possibilità di una giornata eccezionale."),
    (2, "Molto rischiosa", (0.0, 0.5), (0.0, 0.5),
     "Punta sul colpo e sul reparto offensivo: la giornata eccezionale è più probabile, ma anche quella brutta."),
]
MODULO_NEUTRO = (4, 3)     # difensori e attaccanti del modulo da cui si misura l'inclinazione di uno stile
# Nessun titolare che non gioca (#329). Per i numeri un titolare improbabile con una riserva sicura dietro vale quasi quanto la
# riserva titolare (se lui non gioca, entra lei); per chi legge il consiglio è un errore. Dopo la ricerca, un titolare che prende
# voto meno di IMPROBABILE_SOTTO (chi è infortunato o squalificato ha quasi 0) lascia il posto al miglior compagno di ruolo che lo
# prende almeno COMPAGNO_ALMENO, se il cambio costa meno di COSTO_MASSIMO_CAMBIO punti attesi. Non sono regole della lega: valgono
# per ogni lega e ogni stile. La soglia è quella di «improbabile» di consigli.titolarita.
# Dalla revisione di #612 basta un compagno che non è improbabile (prima doveva giocare almeno il 50%) e il tetto è 0,5 (prima 0,3):
# in panchina chi è improbabile sta in fondo (`_panchina`), quindi da titolare vale qualche centesimo in più che da riserva e la
# ricerca lo sceglie più spesso. Con tre portieri al 4%, 22% e 92% restava titolare quello al 4% (il 92% costava più del tetto, il
# 22% non si provava); con uno al 19% e uno al 95% il cambio costava 0,32.
IMPROBABILE_SOTTO = 0.2
COMPAGNO_ALMENO = IMPROBABILE_SOTTO
COSTO_MASSIMO_CAMBIO = 0.5


@dataclass(frozen=True)
class Giocatore:
    id: int
    nome: str
    ruolo: str
    p: float          # probabilità di prendere voto
    mu: float         # fantavoto atteso se prende voto
    mu_voto: float    # voto in pagella atteso (per il modificatore difesa)

    @property
    def valore(self) -> float:
        return self.p * self.mu


@dataclass
class Formazione:
    modulo: str
    titolari: list[Giocatore]
    panchina: list[Giocatore]
    atteso: float = 0.0
    dev: float = 0.0          # oscillazione (deviazione standard) del punteggio simulato
    scelto: float = 0.0       # punteggio usato per la scelta (vedi PESO_BASE)
    alternative: list[tuple[str, float]] = field(default_factory=list)   # (modulo, punteggio atteso)
    tutte: list["Formazione"] = field(default_factory=list)              # la migliore per ogni modulo, in ordine


# ---------------------------------------------------------------- sostituzioni
def chi_va_a_punteggio(titolari: list[Giocatore], panchina: list[Giocatore], gioca: dict[int, bool],
                       regole: Regole) -> tuple[list[Giocatore], int]:
    """Applica le sostituzioni. Restituisce (giocatori che vanno a punteggio, titolari senza voto né sostituto)."""
    in_campo = [t for t in titolari if gioca[t.id]]
    if len(in_campo) == len(titolari):        # tutti in campo (caso comune): niente sostituzioni
        return in_campo, 0
    pr = regole.panchina
    mancanti = sorted([t for t in titolari if not gioca[t.id]], key=lambda t: ORDINE_RUOLO[t.ruolo])
    conta = {r: 0 for r in RUOLI}
    for t in titolari:
        conta[t.ruolo] += 1
    in_panchina = [b for b in panchina if gioca[b.id]]       # solo chi prende voto può entrare
    usati: set[int] = set()
    cambi = 0
    scoperti = 0
    for m in mancanti:
        scelto = None
        if cambi < pr.max_sostituzioni:
            disponibili = [b for b in in_panchina if b.id not in usati] if usati else in_panchina
            if pr.tipo == "per_ruolo":
                scelto = next((b for b in disponibili if b.ruolo == m.ruolo), None)
                if scelto is None and pr.cambio_modulo:
                    scelto = next((b for b in disponibili if _cambio_ammesso(m, b, conta, regole)), None)
            else:  # libera: il primo della panchina che si può far entrare
                scelto = next((b for b in disponibili if b.ruolo == m.ruolo
                               or (pr.cambio_modulo and _cambio_ammesso(m, b, conta, regole))), None)
        if scelto is None:
            scoperti += 1
            continue
        usati.add(scelto.id)
        cambi += 1
        conta[m.ruolo] -= 1
        conta[scelto.ruolo] += 1
        in_campo.append(scelto)
    return in_campo, scoperti


def _cambio_ammesso(esce: Giocatore, entra: Giocatore, conta: dict[str, int], regole: Regole) -> bool:
    if "P" in (esce.ruolo, entra.ruolo):
        return esce.ruolo == entra.ruolo
    nuova = dict(conta)
    nuova[esce.ruolo] -= 1
    nuova[entra.ruolo] += 1
    return modulo_valido(nuova["D"], nuova["C"], nuova["A"], regole)


def punteggio(titolari, panchina, gioca: dict[int, bool], fv: dict[int, float], voto: dict[int, float],
              regole: Regole) -> float:
    """Punteggio della squadra dati chi prende voto (gioca), i fantavoti (fv) e i voti (per il modificatore)."""
    va, scoperti = chi_va_a_punteggio(titolari, panchina, gioca, regole)
    totale = sum(fv[g.id] for g in va)
    if regole.voto_senza_sostituto is not None:
        totale += scoperti * regole.voto_senza_sostituto
    portiere = next((voto[g.id] for g in va if g.ruolo == "P"), None)
    difensori = [voto[g.id] for g in va if g.ruolo == "D"]
    return totale + modificatore_difesa(portiere, difensori, regole)


def _candidati(ordinati: list[Giocatore], ids: set[int], peso: tuple[float, float]) -> list[Giocatore]:
    """Chi provare al posto di un titolare: i due migliori esclusi per valore; se si cerca più sicurezza o più rischio,
    anche i due più sicuri (probabilità di giocare) o i due con il fantavoto più alto quando gioca.
    Per la consigliata (peso di base) restano i soli due per valore, anche se così la ricerca non arriva sempre al massimo dei
    punti attesi. Misura del 12/11/2026 (#612, 537 rose-giornata): provando anche i due con il fantavoto più alto si trovano in
    media 0,04-0,08 punti attesi in più con la panchina lunga per ruolo (0,00-0,01 con quella libera a 7), ma i punti veri non
    lo confermano (+0,11 [-0,05; +0,27] sulle rose a sorte, -0,17 [-0,42; +0,10] su quelle della lega) e i titolari senza voto
    salgono di 0,17 per formazione: chi gioca poco, quando gioca, vale meno del suo fantavoto atteso."""
    fuori = [g for g in ordinati if g.id not in ids]
    scelti = fuori[:2]
    if peso[0] > 0.4 or peso[1] > 0.1:
        extra = sorted(fuori, key=(lambda g: -g.p) if peso[0] > 0.4 else (lambda g: -g.mu))[:2]
        scelti += [g for g in extra if g not in scelti]
    return scelti


# ---------------------------------------------------------------- punti attesi esatti (#612)
# I punti attesi di una formazione si contano, non si stimano con le simulazioni: chi prende voto è indipendente dagli altri,
# quindi la probabilità che ogni riserva entri si calcola esatta. Così la scelta non dipende dal seme né dal numero di
# simulazioni (misura del 12/11/2026: con la media simulata un altro seme cambiava almeno un titolare in 5-8 casi su 10).
# - Senza cambio di modulo: reparto per reparto (i reparti si legano solo per il tetto dei cambi), con ogni panchina.
# - Con il cambio di modulo: tutti i casi, uno per uno (quanti titolari mancano in ogni reparto x quali riserve hanno voto),
#   con lo stesso conto a insiemi delle simulazioni; se i casi sono più di MAX_CASI resta la media delle simulazioni.
# Resta simulato il modificatore difesa (va a soglie sul voto: serve il rumore dei voti): dove la lega lo usa, un altro seme
# cambia ancora un titolare in circa 2 casi su 10, tra difensori o portieri quasi pari (prima 5 su 10).
MAX_CASI = 1 << 15
MAX_TABELLE = 16 << 20     # byte delle tabelle che un Valutatore tiene in memoria (una per forma di formazione)


def _quanti(probabilita) -> list[float]:
    """Quanti eventi accadono, tra eventi indipendenti con le probabilità date: [probabilità di 0, di 1, ...]."""
    d = [1.0]
    for q in probabilita:
        d = [a * (1 - q) + b * q for a, b in zip(d + [0.0], [0.0] + d)]
    return d


def _ingressi_stesso_ruolo(senza: dict[str, list[float]], ruoli_b: list[str], p_b: list[float], massimo: int) -> list[float]:
    """Probabilità che ogni riserva entri, senza cambio di modulo: per ogni titolare senza voto entra la prima riserva con voto
    dello stesso ruolo, finché restano cambi (stesse regole di `chi_va_a_punteggio`). `senza[ruolo]` = per ogni titolare del
    ruolo la probabilità di restare senza voto; `ruoli_b`, `p_b` = ruolo e probabilità di voto delle riserve, in ordine."""
    entra = [0.0] * len(ruoli_b)
    fatti = (1.0,) + (0.0,) * massimo                           # probabilità di aver già fatto c cambi nei reparti prima
    for ruolo in RUOLI:                                         # l'ordine in cui si guardano i titolari senza voto
        riserve = [j for j, r in enumerate(ruoli_b) if r == ruolo]
        if riserve and senza[ruolo] and massimo > 0:
            entrano, fatti = _ingressi_reparto(tuple(senza[ruolo]), tuple(p_b[j] for j in riserve), fatti)
            for j, e in zip(riserve, entrano):
                entra[j] = e
    return entra


@lru_cache(maxsize=4096)
def _ingressi_reparto(senza: tuple, p_riserve: tuple, fatti: tuple) -> tuple[tuple, tuple]:
    """Un reparto di `_ingressi_stesso_ruolo`: (probabilità che ogni riserva del reparto entri, probabilità di c cambi fatti dopo
    il reparto). `fatti[c]` = probabilità di c cambi già fatti prima (la lunghezza dice il massimo dei cambi). In memoria: lo
    stesso reparto torna in molte formazioni a confronto."""
    massimo = len(fatti) - 1
    mancano = _quanti(senza)
    tetto = min(len(senza), len(p_riserve), massimo)            # più di così non ne entrano in questo reparto
    # posti[c][k] = probabilità di c cambi già fatti e k posti da coprire (titolari senza voto, entro i cambi rimasti)
    posti = [[0.0] * (tetto + 1) for _ in range(massimo + 1)]
    for c, pc in enumerate(fatti):
        if pc:
            riga, liberi = posti[c], min(massimo - c, tetto)
            for m, pm in enumerate(mancano):
                riga[m if m < liberi else liberi] += pc * pm
    almeno = [sum(riga[k] for riga in posti) for k in range(tetto + 1)]
    for k in range(tetto - 1, -1, -1):
        almeno[k] += almeno[k + 1]                              # probabilità di almeno k posti
    entrano = []
    con_voto = [1.0]                                            # quante riserve del reparto, tra quelle prima, hanno voto
    for p in p_riserve:                                         # entra se ha voto e resta un posto dopo quelle prima di lei
        entrano.append(p * sum(pv * almeno[v + 1] for v, pv in enumerate(con_voto[:tetto])))
        con_voto = [a * (1 - p) + b * p for a, b in zip(con_voto + [0.0], [0.0] + con_voto)]
    dopo = [0.0] * (massimo + 1)
    for c, riga in enumerate(posti):
        for k, pk in enumerate(riga):
            if pk:
                for v, pv in enumerate(con_voto):               # entrano min(posti, riserve con voto)
                    dopo[c + (k if k < v else v)] += pk * pv
    return tuple(entrano), tuple(dopo)


def _entrano_con_cambio(pr, ammessi: frozenset, modulo: tuple, ruoli_t: list[str], bit_t: list[int], ruoli_b: list[str],
                        bit_b: list[int], tutti: int, gia_cambiati: int = 0) -> list[int]:
    """Sostituzioni con il cambio di modulo, stesse regole di `chi_va_a_punteggio`, per tanti casi insieme (le simulazioni, oppure
    tutti i casi possibili). Un caso è un bit di un intero Python: `bit_t[i]` / `bit_b[j]` = i casi in cui il titolare i / la
    riserva j ha voto, `tutti` = tutti i casi, `gia_cambiati` = i casi con un cambio già fatto prima. `modulo` = (difensori,
    centrocampisti, attaccanti) di partenza. Restituisce, per ogni riserva, i casi in cui entra."""
    # I mancanti si guardano uno alla volta in ordine di ruolo; per ognuno, le riserve nell'ordine della panchina prendono i casi
    # in cui il titolare manca e nessuna riserva precedente è già entrata. Il modulo cambia con i cambi tra ruoli diversi:
    # si tiene l'insieme dei casi per ogni modulo raggiunto (sono pochi).
    massimo = pr.max_sostituzioni
    nb = len(ruoli_b)
    entra = [0] * nb
    if massimo <= 0:
        return entra
    libere = list(bit_b)                                         # con voto e non ancora entrate
    moduli = {tuple(modulo): tutti}                              # modulo -> casi
    cambi = [tutti, gia_cambiati] + [0] * (massimo - 1)          # almeno c cambi fatti
    # libera: il primo della panchina che può entrare; per ruolo: prima lo stesso ruolo, poi chi cambia il modulo
    passate = ((True, False),) if pr.tipo != "per_ruolo" else ((True,), (False,))
    for i in sorted(range(len(ruoli_t)), key=lambda k: ORDINE_RUOLO[ruoli_t[k]]):
        rm = ruoli_t[i]
        manca = (tutti ^ bit_t[i]) & ~cambi[massimo]             # senza voto e con ancora cambi a disposizione
        if not manca:
            continue
        ammesse = {}                                             # ruolo di chi entra -> casi in cui il modulo resta valido
        if rm != "P":
            for rb in set(ruoli_b) - {"P", rm}:
                ammesse[rb] = 0
                for mod, casi in moduli.items():
                    if _modulo_dopo(mod, rm, rb) in ammessi:
                        ammesse[rb] |= casi
        prese = [0] * nb
        resto = manca
        for ammessi_stesso in passate:
            for j in range(nb):
                stesso = ruoli_b[j] == rm
                if not resto or stesso not in ammessi_stesso:
                    continue
                p = resto & libere[j] & (tutti if stesso else ammesse.get(ruoli_b[j], 0))
                if p:
                    prese[j] = p
                    resto ^= p
        coperte = manca ^ resto
        if not coperte:
            continue
        for j, p in enumerate(prese):
            if p:
                libere[j] ^= p
                entra[j] |= p
        for k in range(massimo, 0, -1):
            cambi[k] |= cambi[k - 1] & coperte
        cambiano = [(p, ruoli_b[j]) for j, p in enumerate(prese) if p and ruoli_b[j] != rm]
        if cambiano:
            nuovi: dict = {}
            for mod, casi in moduli.items():
                for p, rb in cambiano:
                    mosse = casi & p
                    if mosse:
                        casi ^= mosse
                        dopo = _modulo_dopo(mod, rm, rb)
                        nuovi[dopo] = nuovi.get(dopo, 0) | mosse
                if casi:
                    nuovi[mod] = nuovi.get(mod, 0) | casi
            moduli = nuovi
    return entra


def _intero(bit: np.ndarray) -> int:
    """Un array di vero/falso come intero Python: il bit k dell'intero è l'elemento k."""
    return int.from_bytes(np.packbits(bit, bitorder="little").tobytes(), "little")


def _righe(insiemi: list[int], quanti: int) -> np.ndarray:
    """Da un insieme di casi (intero Python, un bit per caso) per riserva a una tabella di vero/falso: una riga per riserva,
    `quanti` colonne."""
    byte = (quanti + 7) // 8
    pacchi = np.frombuffer(b"".join(e.to_bytes(byte, "little") for e in insiemi), dtype=np.uint8)
    return np.unpackbits(pacchi.reshape(len(insiemi), byte), axis=1, count=quanti, bitorder="little").view(bool)


@lru_cache(maxsize=64)
def _casi_cambio(con_portiere: bool, tetti: tuple, nb: int) -> tuple:
    """Tutti i casi del cambio di modulo come insiemi (dipendono solo dalla forma: si tengono in memoria). Un caso = (cambio già
    usato per il portiere, titolari senza voto nei reparti D, C, A fino a `tetti`, quali delle `nb` riserve di movimento hanno
    voto). Restituisce (ruoli dei titolari che possono mancare, i casi in cui hanno voto, i casi in cui ogni riserva ha voto,
    tutti i casi, i casi con il cambio del portiere già fatto)."""
    n_m = math.prod(t + 1 for t in tetti)
    n_v = 1 << nb
    n_g = 2 if con_portiere else 1
    indice_m, indice_v = np.arange(n_m), np.arange(n_v)
    ruoli_t, bit_t = [], []
    passo = n_m
    for ruolo, tetto in zip("DCA", tetti):
        passo //= tetto + 1
        mancano = (indice_m // passo) % (tetto + 1)
        for i in range(1, tetto + 1):                            # l'i-esimo del reparto ha voto se ne mancano meno di i
            ruoli_t.append(ruolo)
            bit_t.append(_intero(np.tile(np.repeat(mancano < i, n_v), n_g)))
    bit_b = tuple(_intero(np.tile((indice_v >> j) & 1 == 1, n_g * n_m)) for j in range(nb))
    quanti = n_g * n_m * n_v
    gia = ((1 << quanti) - 1) ^ ((1 << (n_m * n_v)) - 1) if con_portiere else 0      # la seconda metà dei casi
    return tuple(ruoli_t), tuple(bit_t), bit_b, (1 << quanti) - 1, gia


def _quanti_casi(titolari_per_reparto, massimo: int, nb: int, con_portiere: bool = True) -> int:
    """Quanti casi conta `_ingressi_con_cambio` per una formazione con questi titolari nei reparti D, C, A e `nb` riserve di
    movimento. Oltre il tetto (cambi e riserve) un titolare in più senza voto non cambia chi entra: nel reparto resta scoperto."""
    return (2 if con_portiere else 1) * math.prod(min(n, massimo, nb) + 1 for n in titolari_per_reparto) << nb


def _ingressi_con_cambio(pr, ammessi: frozenset, senza: dict[str, list[float]], ruoli_b: list[str], p_b: list[float],
                         portiere: float, tabelle: dict | None = None) -> list[float]:
    """Probabilità che ogni riserva di movimento entri, con il cambio di modulo. `senza`, `ruoli_b`, `p_b` come in
    `_ingressi_stesso_ruolo` ma solo per D, C, A; `portiere` = probabilità che un cambio sia già stato usato per il portiere.
    `tabelle` (facoltativo): dove tenere, per forma della formazione (modulo e ruoli della panchina), chi entra in ogni caso:
    dipende solo dalla forma, e la stessa forma torna in molte formazioni a confronto."""
    nb, massimo = len(ruoli_b), pr.max_sostituzioni
    if not nb or massimo <= 0:
        return [0.0] * nb
    modulo = tuple(len(senza[r]) for r in "DCA")
    tetti = tuple(min(n, massimo, nb) for n in modulo)
    con_portiere = portiere > 0
    chiave = (pr.tipo, massimo, modulo, tuple(ruoli_b), con_portiere)
    entrano = None if tabelle is None else tabelle.get(chiave)
    if entrano is None:
        ruoli_t, bit_t, bit_b, tutti, gia = _casi_cambio(con_portiere, tetti, nb)
        entra = _entrano_con_cambio(pr, ammessi, modulo, ruoli_t, bit_t, ruoli_b, bit_b, tutti, gia)
        quanti = _quanti_casi(modulo, massimo, nb, con_portiere)
        entrano = _righe(entra, quanti).reshape(nb, quanti >> nb, 1 << nb)       # [riserva, caso dei titolari, caso della panchina]
        if tabelle is not None:
            if sum(x.size for x in tabelle.values()) + entrano.size > MAX_TABELLE:
                tabelle.clear()
            tabelle[chiave] = entrano
    # il peso di ogni caso: (cambio del portiere) x (titolari senza voto per reparto) x (riserve con voto), nell'ordine dei casi
    peso_m = np.array([1 - portiere, portiere] if con_portiere else [1.0])
    for r, t in zip("DCA", tetti):
        d = _quanti(senza[r])
        peso_m = np.multiply.outer(peso_m, np.array(d[:t] + [sum(d[t:])])).ravel()
    peso_v = np.ones(1)
    for p in p_b:                                               # il bit j dell'indice = la riserva j ha voto
        peso_v = np.concatenate([peso_v * (1 - p), peso_v * p])
    return ((entrano @ peso_v) @ peso_m).tolist()


# ---------------------------------------------------------------- valutazione e scelta
class Valutatore:
    """Punti attesi di una formazione: esatti per titolari, riserve e voto d'ufficio (`_media_esatta`); le simulazioni, comuni
    a tutte le formazioni a confronto, servono per il modificatore difesa, per l'oscillazione e per la brutta giornata e la
    giornata eccezionale degli stili."""

    def __init__(self, rosa: list[Giocatore], regole: Regole, simulazioni: int = 600, seme: int = 7, fissi: list[Giocatore] = ()):
        """`fissi` (facoltativo, Diario #447): giocatori senza estrazioni, che prendono voto sempre (p ≥ 1) o mai, con fantavoto e voto
        fissi. Stanno in colonne dopo quelle della rosa: le estrazioni della rosa restano identiche a quelle senza di loro."""
        rng = np.random.default_rng(seme)
        self.regole = regole
        self.indice = {g.id: i for i, g in enumerate(rosa)}
        self.gioca = rng.random((simulazioni, len(rosa))) < np.array([g.p for g in rosa])
        # la probabilità di voto di ogni colonna, per i punti attesi esatti: tra 0 e 1 come nelle estrazioni (i `fissi`: sempre o mai)
        self._p = [g.p if 0 < g.p < 1 else float(g.p >= 1) for g in rosa] + [float(g.p >= 1) for g in fissi]
        self.fv = np.array([g.mu for g in rosa], dtype=float)
        # il modificatore difesa va a soglie: serve la variabilità del voto, non solo la media
        rumore = rng.normal(0, SCARTO_VOTO, (simulazioni, len(rosa)))
        self.voti = np.array([g.mu_voto for g in rosa], dtype=float) + rumore
        if fissi:
            self.indice |= {g.id: len(rosa) + k for k, g in enumerate(fissi)}
            self.gioca = np.hstack([self.gioca, np.tile(np.array([g.p >= 1 for g in fissi]), (simulazioni, 1))])
            self.fv = np.append(self.fv, [g.mu for g in fissi])
            self.voti = np.hstack([self.voti, np.tile(np.array([g.mu_voto for g in fissi], dtype=float), (simulazioni, 1))])
        self._ammessi = _moduli_ammessi(regole)
        self._cache: dict = {}
        # Le stesse estrazioni in altre due forme, solo per fare prima: una riga per giocatore e, per ogni giocatore, un intero
        # Python con un bit per simulazione (bit s = prende voto nella simulazione s): le sostituzioni diventano poche operazioni
        # tra interi invece di decine di operazioni numpy su array piccoli.
        self._gioca_g = np.ascontiguousarray(self.gioca.T)
        self._bit = [int.from_bytes(r.tobytes(), "little") for r in np.packbits(self._gioca_g, axis=1, bitorder="little")]
        self._tutti = (1 << simulazioni) - 1
        self._cache_difesa: dict = {}
        self._medie_difesa: dict = {}
        self._tabelle: dict = {}        # per il conto esatto con il cambio di modulo (`_ingressi_con_cambio`)
        self._casi_massimi: dict = {}
        self._panchine: dict = {}       # panchine già scelte da `migliore`, per rosa

    # ------------------------------------------------------------ calcolo su tutte le simulazioni insieme
    def _punti(self, titolari: list[Giocatore], panchina: list[Giocatore]) -> np.ndarray:
        """I punti della formazione in ogni simulazione."""
        totale, difesa = self._parti(titolari, panchina)
        return totale if difesa is None else totale + difesa

    def _parti(self, titolari: list[Giocatore], panchina: list[Giocatore]) -> tuple[np.ndarray, np.ndarray | None]:
        """Per ogni simulazione: (punti senza il modificatore difesa, modificatore difesa). Nel caso anomalo (nessun portiere o
        più d'uno) si va per la strada lenta e il secondo è None: i punti stanno tutti nel primo."""
        if sum(t.ruolo == "P" for t in titolari) != 1:
            return self._punti_lenti(titolari, panchina), None
        reg = self.regole
        ct = [self.indice[t.id] for t in titolari]
        cb = [self.indice[b.id] for b in panchina]
        gt = self.gioca[:, ct]
        n_sim, nb = len(gt), len(cb)
        entrati = np.zeros((n_sim, nb), dtype=bool)         # riserve che entrano
        righe_e = entrati.T                                 # le stesse, una riga per riserva
        scoperti = np.zeros(n_sim, dtype=int)               # titolari senza voto né sostituto
        if nb == 0:
            scoperti = (~gt).sum(axis=1)
        elif any(self._bit[c] != self._tutti for c in ct):   # qualche titolare senza voto in qualche simulazione
            if reg.panchina.cambio_modulo:
                righe_e = self._sostituzioni_cambio_modulo(titolari, panchina, ct, cb)
            else:
                righe_e = self._sostituzioni_stesso_ruolo(titolari, panchina, ct, cb)
            entrati[:] = righe_e.T
            if reg.voto_senza_sostituto is not None:
                scoperti = (~gt).sum(axis=1) - entrati.sum(axis=1)
        # le somme in virgola mobile restano le stesse operazioni sugli stessi array: risultati identici bit per bit
        totale = gt @ self.fv[ct]
        if nb:
            totale = totale + entrati @ self.fv[cb]
        if reg.voto_senza_sostituto is not None:
            totale = totale + scoperti * reg.voto_senza_sostituto
        if reg.panchina.cambio_modulo or not reg.modificatore_difesa.attivo:
            return totale, self._difesa(titolari, panchina, ct, cb, self._gioca_g[ct], righe_e)
        # Senza cambio di modulo il modificatore dipende solo dal reparto difensivo, che torna in molte formazioni a confronto:
        # si calcola una volta.
        chiave = self._reparto_difensivo(titolari, panchina)
        difesa = self._cache_difesa.get(chiave)
        if difesa is None:
            difesa = self._cache_difesa[chiave] = self._difesa(titolari, panchina, ct, cb, self._gioca_g[ct], righe_e)
        return totale, difesa

    def _media_esatta(self, titolari: list[Giocatore], panchina: list[Giocatore]) -> float | None:
        """Punti attesi della formazione senza il modificatore difesa, contati e non simulati: titolari che prendono voto,
        riserve che entrano (ognuna con la sua probabilità esatta di entrare) e voto d'ufficio per chi resta scoperto.
        None se il conto non si fa: con il cambio di modulo e troppi casi (`_si_conta`)."""
        pr = self.regole.panchina
        p_t = [self._p[self.indice[t.id]] for t in titolari]
        p_b = [self._p[self.indice[b.id]] for b in panchina]
        ruoli_b = [b.ruolo for b in panchina]
        senza = {r: [1 - p for p, t in zip(p_t, titolari) if t.ruolo == r] for r in RUOLI}
        if not pr.cambio_modulo:
            entra = _ingressi_stesso_ruolo(senza, ruoli_b, p_b, pr.max_sostituzioni)
        else:
            # il portiere esce solo per un portiere: il primo di riserva con voto; agli altri resta un cambio in meno
            entra, manca = [0.0] * len(panchina), senza["P"][0] if pr.max_sostituzioni > 0 else 0.0
            for j, r in enumerate(ruoli_b):
                if r == "P":
                    entra[j] = manca * p_b[j]
                    manca *= 1 - p_b[j]
            movimento = [j for j, r in enumerate(ruoli_b) if r != "P"]
            if not self._si_conta(tuple(len(senza[r]) for r in "DCA"), len(movimento)):
                return None
            altri = _ingressi_con_cambio(pr, self._ammessi, senza, [ruoli_b[j] for j in movimento], [p_b[j] for j in movimento],
                                         sum(entra), self._tabelle)
            for j, e in zip(movimento, altri):
                entra[j] = e
        totale = sum(p * self.fv[self.indice[t.id]] for p, t in zip(p_t, titolari))
        totale += sum(e * self.fv[self.indice[b.id]] for e, b in zip(entra, panchina))
        if self.regole.voto_senza_sostituto is not None:
            totale += (len(titolari) - sum(p_t) - sum(entra)) * self.regole.voto_senza_sostituto
        return float(totale)

    def _si_conta(self, modulo: tuple, riserve: int) -> bool:
        """Con il cambio di modulo: vero se i casi da contare stanno in MAX_CASI. Si guarda il modulo ammesso che ne ha di più
        (e quello della formazione, se non è tra gli ammessi): così tutte le formazioni a confronto con la stessa panchina si
        valutano nello stesso modo, o tutte esatte o tutte con le simulazioni."""
        massimo = self._casi_massimi.get(riserve)
        if massimo is None:
            cambi = self.regole.panchina.max_sostituzioni
            massimo = self._casi_massimi[riserve] = max((_quanti_casi(m, cambi, riserve) for m in self._ammessi), default=0)
        return max(massimo, _quanti_casi(modulo, self.regole.panchina.max_sostituzioni, riserve)) <= MAX_CASI

    def _sostituzioni_cambio_modulo(self, titolari, panchina, ct, cb) -> np.ndarray:
        """Sostituzioni con il cambio di modulo, stesse regole di `chi_va_a_punteggio`, per tutte le simulazioni insieme
        (`_entrano_con_cambio`). Restituisce chi entra: una riga per riserva, una colonna per simulazione."""
        bit = self._bit
        entra = _entrano_con_cambio(self.regole.panchina, self._ammessi, tuple(sum(t.ruolo == r for t in titolari) for r in "DCA"),
                                    [t.ruolo for t in titolari], [bit[c] for c in ct], [b.ruolo for b in panchina],
                                    [bit[c] for c in cb], self._tutti)
        return _righe(entra, self.gioca.shape[0])

    def _sostituzioni_stesso_ruolo(self, titolari, panchina, ct, cb) -> np.ndarray:
        """Sostituzioni senza cambio di modulo: entra il primo della panchina con voto dello STESSO ruolo (panchina per ruolo o libera
        è lo stesso), fino al massimo di cambi. Stesso risultato di `chi_va_a_punteggio`, per tutte le simulazioni insieme.
        Restituisce chi entra: una riga per riserva, una colonna per simulazione."""
        # Si lavora con insiemi di simulazioni (interi Python, un bit per simulazione) e reparto per reparto (P, D, C, A, l'ordine
        # dei mancanti): chi manca in uno stesso reparto è indistinguibile, quindi le riserve di quel ruolo, nell'ordine della
        # panchina, entrano se hanno voto, se nel reparto restano titolari scoperti e se restano cambi. Gli "almeno t" si tengono
        # come insiemi: almeno[t] = simulazioni in cui il conteggio vale almeno t.
        massimo = self.regole.panchina.max_sostituzioni
        bit, tutti = self._bit, self._tutti
        entra = [0] * len(cb)
        if massimo > 0:
            cambi = [tutti] + [0] * massimo                          # almeno c cambi fatti
            for ruolo in RUOLI:
                riserve = [j for j, b in enumerate(panchina) if b.ruolo == ruolo]
                if not riserve:
                    continue
                righe = [c for c, t in zip(ct, titolari) if t.ruolo == ruolo]
                tetto = min(len(righe), len(riserve), massimo)        # più di così non ne entrano in questo reparto
                if not tetto:
                    continue
                mancano = [tutti] + [0] * tetto                      # almeno t titolari del reparto senza voto
                for c in righe:
                    senza = tutti ^ bit[c]
                    for t in range(tetto, 0, -1):
                        mancano[t] |= mancano[t - 1] & senza
                dentro = [tutti] + [0] * tetto                       # almeno t riserve del reparto già entrate
                for j in riserve:
                    posto = 0                                        # entrate finora (t) < titolari scoperti
                    for t in range(tetto):
                        posto |= (dentro[t] ^ dentro[t + 1]) & mancano[t + 1]
                    e = bit[cb[j]] & posto & ~cambi[massimo]
                    if not e:
                        continue
                    entra[j] = e
                    for t in range(tetto, 0, -1):
                        dentro[t] |= dentro[t - 1] & e
                    for k in range(massimo, 0, -1):
                        cambi[k] |= cambi[k - 1] & e
        return _righe(entra, self.gioca.shape[0])

    def _difesa(self, titolari, panchina, ct, cb, righe_t, righe_e) -> np.ndarray:
        """Modificatore difesa per ogni simulazione (stesse regole di `modificatore_difesa`).
        `righe_t` / `righe_e`: chi prende voto tra i titolari / chi entra dalla panchina, una riga per giocatore."""
        m = self.regole.modificatore_difesa
        n_sim = self.gioca.shape[0]
        if not m.attivo:
            return np.zeros(n_sim)
        voti = self.voti
        ip = next(i for i, t in enumerate(titolari) if t.ruolo == "P")
        voto_p = np.where(righe_t[ip], voti[:, ct[ip]], 0.0)
        ha_p = righe_t[ip]
        for j, b in enumerate(panchina):
            if b.ruolo == "P":
                voto_p = np.where(righe_e[j], voti[:, cb[j]], voto_p)
                ha_p = ha_p | righe_e[j]
        difensori = [(righe_t[i], ct[i]) for i, t in enumerate(titolari) if t.ruolo == "D"]
        difensori += [(righe_e[j], cb[j]) for j, b in enumerate(panchina) if b.ruolo == "D"]
        quanti = 0
        if difensori:
            # i 3 voti migliori dei difensori in campo (-inf = fuori), in ordine crescente come dopo un sort: si tengono con
            # massimi e minimi elemento per elemento invece di ordinare ogni simulazione; poi la stessa somma di prima
            primo = secondo = terzo = np.full(n_sim, -np.inf)
            for in_campo, c in difensori:
                x = np.where(in_campo, voti[:, c], -np.inf)
                terzo = np.maximum(terzo, np.minimum(secondo, x))
                secondo = np.maximum(secondo, np.minimum(primo, x))
                primo = np.maximum(primo, x)
                quanti = quanti + in_campo.view(np.int8)
            migliori = np.empty((n_sim, min(len(difensori), 3)))
            for k, colonna in enumerate((terzo, secondo, primo)[3 - migliori.shape[1]:]):
                migliori[:, k] = colonna
            somma = np.where(np.isfinite(migliori), migliori, 0.0).sum(axis=1)
        else:
            somma = np.zeros(n_sim)
        media = (voto_p + somma) / 4
        bonus = np.zeros(n_sim)
        for soglia, valore in sorted(m.soglie):
            bonus = np.where(media >= soglia, valore, bonus)
        return np.where(ha_p & (quanti >= m.min_difensori), bonus, 0.0)

    def _punti_lenti(self, titolari, panchina) -> np.ndarray:
        """Come `_punti`, una simulazione alla volta con `punteggio` (per le formazioni fuori dal caso normale)."""
        ids = [g.id for g in list(titolari) + list(panchina)]
        cols = [self.indice[i] for i in ids]
        fv = {i: float(self.fv[c]) for i, c in zip(ids, cols)}
        return np.array([punteggio(titolari, panchina, {i: bool(self.gioca[s, c]) for i, c in zip(ids, cols)}, fv,
                                   {i: float(self.voti[s, c]) for i, c in zip(ids, cols)}, self.regole)
                         for s in range(len(self.gioca))])

    def statistiche(self, titolari: list[Giocatore], panchina: list[Giocatore]) -> tuple[float, float, float, float]:
        """(punti attesi, oscillazione, brutta giornata, giornata eccezionale) di una formazione. Le ultime tre vengono dalle
        simulazioni comuni."""
        r = self._riassunto(titolari, panchina)
        attesi = self._attesi(r)
        self._simulati(r, oscillazione=True)
        return attesi, r[1], r[2], r[3]

    def atteso(self, titolari: list[Giocatore], panchina: list[Giocatore]) -> float:
        """I punti attesi della formazione."""
        return self._attesi(self._riassunto(titolari, panchina))

    def scelta(self, titolari: list[Giocatore], panchina: list[Giocatore], peso: tuple[float, float]) -> float:
        """Il punteggio con cui uno stile sceglie (vedi PESO_BASE). Con il peso di base sono i punti attesi. Gli altri stili
        scelgono come prima di #612, tutto sulle simulazioni: media meno (o più) una parte della distanza dalla brutta giornata
        (o dalla giornata eccezionale); i punti attesi che mostrano sono comunque quelli di `atteso`."""
        r = self._riassunto(titolari, panchina)
        if not peso[0] and not peso[1]:
            return self._attesi(r)
        media, brutta, eccezionale = self._simulati(r)[6], r[2], r[3]
        return media - peso[0] * (media - brutta) + peso[1] * (eccezionale - media)

    def _riassunto(self, titolari: list[Giocatore], panchina: list[Giocatore]) -> list:
        """La voce in cache di una formazione: [punti attesi, oscillazione, brutta giornata, giornata eccezionale, titolari,
        panchina, media delle simulazioni]. I numeri restano None finché non servono: i punti attesi li mette `_attesi`, gli
        altri (che vengono dalle simulazioni) `_simulati`. Titolari e panchina restano nell'ordine della prima chiamata: le
        somme in virgola mobile dipendono dall'ordine."""
        chiave = (tuple(sorted(t.id for t in titolari)), tuple(b.id for b in panchina))
        r = self._cache.get(chiave)
        if r is None:
            r = self._cache[chiave] = [None, None, None, None, tuple(titolari), tuple(panchina), None]
        return r

    def _attesi(self, r: list) -> float:
        """I punti attesi della voce `r`: esatti (`_media_esatta`) più la media simulata del modificatore difesa; dove il conto
        esatto non si fa (nessun portiere o più d'uno, troppi casi) la media delle simulazioni."""
        if r[0] is None:
            titolari, panchina = r[4], r[5]
            esatta = self._media_esatta(titolari, panchina) if sum(t.ruolo == "P" for t in titolari) == 1 else None
            if esatta is None:
                r[0] = self._simulati(r)[6]
            elif not self.regole.modificatore_difesa.attivo:
                r[0] = esatta
            else:
                # senza cambio di modulo il modificatore dipende solo dal reparto difensivo: la sua media si calcola una volta
                chiave = None if self.regole.panchina.cambio_modulo else self._reparto_difensivo(titolari, panchina)
                difesa = self._medie_difesa.get(chiave)
                if difesa is None:
                    totale, per_simulazione = self._parti(titolari, panchina)
                    difesa = float(per_simulazione.mean())
                    if chiave is not None:
                        self._medie_difesa[chiave] = difesa
                    if r[2] is None:                    # la simulazione è già fatta: si tiene anche il resto
                        self._dalle_simulazioni(r, totale + per_simulazione)
                r[0] = esatta + difesa
        return r[0]

    def _simulati(self, r: list, oscillazione: bool = False) -> list:
        """Riempie la voce `r` con i numeri che vengono dalle simulazioni (brutta giornata, giornata eccezionale, media; con
        `oscillazione` anche la deviazione standard, che serve solo per le formazioni finali). Restituisce `r`."""
        if r[2] is None or (oscillazione and r[1] is None):
            punti = self._punti(r[4], r[5])
            if r[2] is None:
                self._dalle_simulazioni(r, punti)
            if oscillazione:
                r[1] = float(punti.std())
        return r

    @staticmethod
    def _dalle_simulazioni(r: list, punti: np.ndarray) -> None:
        r[2], r[3] = (float(x) for x in _percentili_10_90(punti))
        r[6] = float(punti.mean())

    def _reparto_difensivo(self, titolari: list[Giocatore], panchina: list[Giocatore]) -> tuple:
        """Ciò da cui dipende il modificatore difesa senza cambio di modulo: portiere e difensori titolari e le riserve P e D
        in ordine (i cambi vanno per reparto P, D, C, A: chi entra in porta e in difesa non dipende da centrocampo e attacco)."""
        indice = self.indice
        return (tuple(indice[t.id] for t in titolari if t.ruolo == "P"),
                tuple(sorted(indice[t.id] for t in titolari if t.ruolo == "D")),
                tuple((b.ruolo, indice[b.id]) for b in panchina if b.ruolo in ("P", "D")))


@lru_cache(maxsize=1024)
def _modulo_dopo(mod: tuple, esce: str, entra: str) -> tuple:
    """(difensori, centrocampisti, attaccanti) dopo che un giocatore di ruolo `esce` lascia il posto a uno di ruolo `entra`."""
    nuovo = list(mod)
    nuovo["DCA".index(esce)] -= 1
    nuovo["DCA".index(entra)] += 1
    return tuple(nuovo)


def _percentili_10_90(punti: np.ndarray) -> tuple[float, float]:
    """Come `np.percentile(punti, (10, 90))` (metodo lineare), stessi numeri bit per bit, ma con una sola `partition` e i conti
    di numpy rifatti su due numeri: `np.percentile` costa molto di più per un array di 600 valori."""
    n = len(punti)
    if n < 2:
        return tuple(np.percentile(punti, (10, 90)))
    virtuali = [(n - 1) * q for q in (0.1, 0.9)]          # = np.true_divide((10, 90), 100) * (n - 1)
    sotto = [int(math.floor(v)) for v in virtuali]
    k = sorted({sotto[0], sotto[0] + 1, sotto[1], sotto[1] + 1, n - 1} - {n})
    parte = np.partition(punti, k)
    if math.isnan(parte[n - 1]):                            # come numpy: con un NaN il risultato è NaN
        return tuple(np.percentile(punti, (10, 90)))
    esito = []
    for v, i in zip(virtuali, sotto):
        a = float(parte[i])
        b = float(parte[i + 1]) if i + 1 < n else a
        t = v - i
        d = b - a
        esito.append(b - d * (1 - t) if t >= 0.5 else a + d * t)   # = numpy _lerp
    return esito[0], esito[1]


def _moduli_ammessi(regole: Regole) -> frozenset:
    """I moduli ammessi come (difensori, centrocampisti, attaccanti)."""
    return frozenset(modulo_in_numeri(m) for m in regole.moduli)


def _panchina(rosa: list[Giocatore], titolari: list[Giocatore], regole: Regole,
              ordinati: list[Giocatore] | None = None) -> list[Giocatore]:
    """I migliori non titolari per valore (gioca N% x fantavoto atteso; almeno un portiere se c'è), messi in ordine di fantavoto
    atteso: una riserva entra solo se ha preso voto, e a quel punto conta quanto vale se gioca (#612). Panchina per ruolo: prima
    i ruoli nell'ordine della lega (P, D, C, A), dentro il ruolo chi vale di più; panchina libera: chi vale di più, di ogni ruolo.
    Chi quasi certamente non gioca (meno di IMPROBABILE_SOTTO: infortunati, squalificati, chi non è tra i convocati) sta dopo chi
    gioca: per i punti attesi non cambia quasi niente, ma un infortunato per primo in panchina a chi legge sembra un errore, come
    tra i titolari (#329). Con le probabili del 12/11/2026 senza questa regola succedeva in 9 squadre su 10.
    `ordinati` (facoltativo) = la rosa già ordinata con `_per_valore`, per non riordinarla a ogni chiamata."""
    ids = {t.id for t in titolari}
    resto = [g for g in (ordinati if ordinati is not None else _per_valore(rosa)) if g.id not in ids]
    posti = regole.panchina.posti
    if posti:        # panchina a posti fissi: i migliori di ogni ruolo, tanti quanti sono i posti di quel ruolo
        scelti = [g for r in RUOLI for g in [x for x in resto if x.ruolo == r][:posti.get(r, 0)]]
    else:
        n = regole.panchina.numero
        portieri = [g for g in resto if g.ruolo == "P"][:1]
        altri = [g for g in resto if g.id not in {p.id for p in portieri}]
        scelti = (portieri + altri)[:n]
    # a pari fantavoto atteso resta davanti chi ha più valore (ordinamento stabile: `scelti` è già in ordine di valore nel ruolo)
    if regole.panchina.tipo == "per_ruolo":
        return sorted(scelti, key=lambda g: (ORDINE_RUOLO[g.ruolo], g.p < IMPROBABILE_SOTTO, -g.mu))
    # libera: il posto del portiere di riserva non conta (entra solo per il portiere, e nessun altro può entrare al suo posto)
    return sorted(scelti, key=lambda g: (g.p < IMPROBABILE_SOTTO, -g.mu))


def _per_valore(rosa: list[Giocatore]) -> list[Giocatore]:
    """La rosa dal valore più alto al più basso (ordinamento stabile: a pari valore resta l'ordine della rosa). Togliere i titolari
    da questa lista dà lo stesso ordine che ordinare i soli non titolari."""
    return sorted(rosa, key=lambda g: -g.valore)


def _senza_improbabili(titolari: list[Giocatore], panchina: list[Giocatore], per_ruolo: dict[str, list[Giocatore]],
                       panchina_di, val: Valutatore, peso: tuple[float, float],
                       fissi: Collection[int] = ()) -> tuple[list[Giocatore], list[Giocatore]]:
    """Toglie dagli 11 chi gioca meno di IMPROBABILE_SOTTO, se un compagno di ruolo che gioca almeno COMPAGNO_ALMENO costa meno di
    COSTO_MASSIMO_CAMBIO punti attesi. Tra i compagni che si possono mettere vince il migliore per lo stile (`peso`), come nella
    ricerca. Si parte dal titolare meno probabile e dopo ogni cambio si ricomincia: alla fine nessun improbabile rimasto ha un
    compagno così (ogni cambio toglie un improbabile, quindi i giri finiscono). Chi sta in `fissi` resta dov'è."""
    cambiato = True
    while cambiato:
        cambiato = False
        atteso = val.atteso(titolari, panchina)
        ids = {x.id for x in titolari}
        for i, t in sorted(enumerate(titolari), key=lambda c: c[1].p):
            if t.p >= IMPROBABILE_SOTTO:
                break
            if t.id in fissi:
                continue
            meglio = None
            for alt in per_ruolo[t.ruolo]:
                if alt.id in ids or alt.p < COMPAGNO_ALMENO:
                    continue
                prova = titolari[:i] + [alt] + titolari[i + 1:]
                pp = panchina_di(prova)
                if atteso - val.atteso(prova, pp) >= COSTO_MASSIMO_CAMBIO:
                    continue
                v = val.scelta(prova, pp, peso)
                if meglio is None or v > meglio[2] + 1e-9:
                    meglio = (prova, pp, v)
            if meglio is not None:
                titolari, panchina = meglio[0], meglio[1]
                cambiato = True
                break
    return titolari, panchina


def migliore(rosa: list[Giocatore], regole: Regole, simulazioni: int = 600, ricerca: bool = True,
             peso: tuple[float, float] = PESO_BASE, valutatore: Valutatore | None = None,
             inclinazione: tuple[float, float] = (0.0, 0.0), fissi: Collection[int] = (),
             scegli_panchina: Callable[[list[Giocatore]], list[Giocatore]] | None = None) -> Formazione:
    """La formazione migliore tra tutti i moduli ammessi. Con il peso di base (la consigliata) è quella con più punti attesi
    fra le formazioni che la ricerca prova; con più peso alla brutta giornata si preferiscono i titolari sicuri, con più peso
    alla giornata eccezionale chi può fare il colpo.
    `inclinazione` = (punti per ogni difensore, punti per ogni attaccante) oltre il 4-?-3 neutro: sposta la scelta del MODULO
    (non dei giocatori) verso le difese folte o gli attacchi folti; (0, 0) = solo punti attesi.
    In ogni modulo, dopo la ricerca (anche senza), un titolare che quasi certamente non gioca lascia il posto a un compagno che
    gioca, se costa poco (`_senza_improbabili`).
    Giocatori che non si possono più spostare (anticipo già cominciato, consigli.py): chi sta in `fissi` resta titolare, la panchina
    la sceglie `scegli_panchina` e chi non deve diventare titolare si lascia fuori da `rosa` (allora `valutatore`, fatto sulla rosa
    intera, serve). Senza questi due il calcolo è quello di sempre."""
    rosa = list({g.id: g for g in rosa}.values())       # un giocatore ripetuto nella rosa (riga doppia importata) conta una volta sola
    val = valutatore or Valutatore(rosa, regole, simulazioni)
    per_ruolo = {r: sorted([g for g in rosa if g.ruolo == r], key=lambda g: -g.valore) for r in RUOLI}
    ordinati = _per_valore(rosa)
    # la panchina dipende solo da rosa, regole e titolari: la ricerca (e gli altri stili, con lo stesso valutatore) ripassa dagli stessi
    panchine = val._panchine.setdefault(tuple(rosa), {}) if regole is val.regole and scegli_panchina is None else {}
    fissi = frozenset(fissi)
    # i titolari di partenza: prima chi resta titolare per forza, poi i migliori per valore (senza `fissi`: per_ruolo com'è)
    in_testa = {r: sorted(per_ruolo[r], key=lambda g: g.id not in fissi) for r in RUOLI} if fissi else per_ruolo
    quanti_fissi = {r: sum(1 for g in per_ruolo[r] if g.id in fissi) for r in RUOLI}

    def panchina_di(tit: list[Giocatore]) -> list[Giocatore]:
        chiave = frozenset(g.id for g in tit)
        if chiave not in panchine:
            panchine[chiave] = scegli_panchina(tit) if scegli_panchina else _panchina(rosa, tit, regole, ordinati)
        return panchine[chiave]

    risultati = []
    for modulo in regole.moduli:
        d, c, a = modulo_in_numeri(modulo)
        servono = {"P": 1, "D": d, "C": c, "A": a}
        if any(len(per_ruolo[r]) < servono[r] or quanti_fissi[r] > servono[r] for r in RUOLI):
            continue
        titolari = [g for r in RUOLI for g in in_testa[r][:servono[r]]]
        panchina = panchina_di(titolari)
        valore = val.scelta(titolari, panchina, peso)
        if ricerca:  # prova a scambiare ogni titolare con i migliori esclusi dello stesso ruolo
            migliorato = True
            while migliorato:
                migliorato = False
                for i, t in enumerate(titolari):
                    if t.id in fissi:
                        continue
                    ids = {x.id for x in titolari}
                    for alt in _candidati(per_ruolo[t.ruolo], ids, peso):
                        prova = titolari[:i] + [alt] + titolari[i + 1:]
                        pp = panchina_di(prova)
                        v = val.scelta(prova, pp, peso)
                        if v > valore + 1e-9:
                            titolari, panchina, valore, migliorato = prova, pp, v, True
                            break
        titolari, panchina = _senza_improbabili(titolari, panchina, per_ruolo, panchina_di, val, peso, fissi)
        valore = val.scelta(titolari, panchina, peso)
        media, dev = val.statistiche(titolari, panchina)[:2]
        risultati.append(Formazione(modulo, sorted(titolari, key=lambda g: (ORDINE_RUOLO[g.ruolo], -g.valore)),
                                    list(panchina), media, dev))
        risultati[-1].scelto = valore + inclinazione[0] * (d - MODULO_NEUTRO[0]) + inclinazione[1] * (a - MODULO_NEUTRO[1])
    if not risultati:
        raise ValueError("Nessun modulo ammesso è compatibile con la rosa")
    risultati.sort(key=lambda f: -f.scelto)
    scelta = risultati[0]
    scelta.alternative = [(f.modulo, round(f.atteso, 2)) for f in risultati[1:]]
    scelta.tutte = risultati
    return scelta
