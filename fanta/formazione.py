"""Scelta della formazione: 11 titolari, modulo e ordine della panchina che massimizzano il punteggio atteso.

Il punteggio atteso tiene conto delle sostituzioni: si simula molte volte chi prende voto (secondo p_voto)
e si applicano le regole della lega (panchina libera o per ruolo, numero massimo di cambi, cambio modulo,
voto d'ufficio, modificatore difesa). Tutte le formazioni a confronto usano le stesse simulazioni.
"""
from __future__ import annotations

import math
from collections.abc import Callable, Collection
from dataclasses import dataclass, field

import numpy as np

from .punteggio import modificatore_difesa, modulo_valido
from .regole import RUOLI, Regole, modulo_in_numeri

ORDINE_RUOLO = {r: i for i, r in enumerate(RUOLI)}
SCARTO_VOTO = 0.6     # variabilità tipica di un voto intorno alla sua media
# Come si sceglie tra formazioni quasi pari: punteggio scelto = atteso - giu x (atteso - brutta giornata) + su x (giornata eccezionale - atteso),
# dove brutta/eccezionale sono il 10% peggiore e il 10% migliore delle giornate simulate. Con il peso di base, a parità di punti attesi
# (entro 0,2-0,3) vince la formazione con meno rischio di una brutta giornata, cioè con i titolari più sicuri.
PESO_BASE = (0.15, 0.0)
# Gli stili sono preset completi: (id, nome, peso rischio/giornata eccezionale, inclinazione del modulo, descrizione di una riga).
# L'inclinazione (punti per difensore, punti per attaccante oltre il 4-x-3) sposta solo la scelta del MODULO. Valori misurati con il
# backtest sulle rose della lega (docs/STILI.md): nessuna perdita oltre il rumore di misura; "Equilibrata" resta identica a prima.
LIVELLI_RISCHIO = [
    (-2, "Molto sicura", (1.5, 0.0), (0.5, 0.0),
     "Punta su chi gioca quasi di sicuro e preferisce difese più folte: meno rischio di una brutta giornata, a costo di qualche punto atteso."),
    (-1, "Sicura", (0.6, 0.0), (0.5, 0.0),
     "Titolari più sicuri e, a parità di punti, una difesa più folta: perde al massimo qualche decimo di punto atteso."),
    (0, "Equilibrata", PESO_BASE, (0.0, 0.0),
     "La via di mezzo: punti attesi alti ma con un po' di prudenza sui titolari. Non è lo stile con il massimo assoluto di punti attesi: «Rischiosa» a volte ne mostra qualche decimo in più."),
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
# per ogni lega e ogni stile. Le soglie sono quelle di «improbabile» e «ballottaggio» di consigli.titolarita.
IMPROBABILE_SOTTO = 0.2
COMPAGNO_ALMENO = 0.5
COSTO_MASSIMO_CAMBIO = 0.3


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
    anche i due più sicuri (probabilità di giocare) o i due con il fantavoto più alto quando gioca."""
    fuori = [g for g in ordinati if g.id not in ids]
    scelti = fuori[:2]
    if peso[0] > 0.4 or peso[1] > 0.1:
        extra = sorted(fuori, key=(lambda g: -g.p) if peso[0] > 0.4 else (lambda g: -g.mu))[:2]
        scelti += [g for g in extra if g not in scelti]
    return scelti


# ---------------------------------------------------------------- valutazione e scelta
class Valutatore:
    """Punteggio atteso di una formazione, con simulazioni comuni a tutte le formazioni a confronto."""

    def __init__(self, rosa: list[Giocatore], regole: Regole, simulazioni: int = 600, seme: int = 7, fissi: list[Giocatore] = ()):
        """`fissi` (facoltativo, Diario #447): giocatori senza estrazioni, che prendono voto sempre (p ≥ 1) o mai, con fantavoto e voto
        fissi. Stanno in colonne dopo quelle della rosa: le estrazioni della rosa restano identiche a quelle senza di loro."""
        rng = np.random.default_rng(seme)
        self.regole = regole
        self.indice = {g.id: i for i, g in enumerate(rosa)}
        self.gioca = rng.random((simulazioni, len(rosa))) < np.array([g.p for g in rosa])
        self.fv = np.array([g.mu for g in rosa], dtype=float)
        # il modificatore difesa va a soglie: serve la variabilità del voto, non solo la media
        rumore = rng.normal(0, SCARTO_VOTO, (simulazioni, len(rosa)))
        self.voti = np.array([g.mu_voto for g in rosa], dtype=float) + rumore
        if fissi:
            self.indice |= {g.id: len(rosa) + k for k, g in enumerate(fissi)}
            self.gioca = np.hstack([self.gioca, np.tile(np.array([g.p >= 1 for g in fissi]), (simulazioni, 1))])
            self.fv = np.append(self.fv, [g.mu for g in fissi])
            self.voti = np.hstack([self.voti, np.tile(np.array([g.mu_voto for g in fissi], dtype=float), (simulazioni, 1))])
        self._ammessi = _tabella_moduli(regole)
        self._cache: dict = {}
        # Le stesse estrazioni in altre due forme, solo per fare prima: una riga per giocatore e, per ogni giocatore, un intero
        # Python con un bit per simulazione (bit s = prende voto nella simulazione s): le sostituzioni diventano poche operazioni
        # tra interi invece di decine di operazioni numpy su array piccoli.
        self._gioca_g = np.ascontiguousarray(self.gioca.T)
        self._byte = (simulazioni + 7) // 8
        self._bit = [int.from_bytes(r.tobytes(), "little") for r in np.packbits(self._gioca_g, axis=1, bitorder="little")]
        self._tutti = (1 << simulazioni) - 1
        self._cache_difesa: dict = {}
        self._panchine: dict = {}       # panchine già scelte da `migliore`, per rosa

    # ------------------------------------------------------------ calcolo su tutte le simulazioni insieme
    def _punti(self, titolari: list[Giocatore], panchina: list[Giocatore]) -> np.ndarray:
        if sum(t.ruolo == "P" for t in titolari) != 1:      # caso anomalo (nessun portiere o più d'uno): strada lenta
            return self._punti_lenti(titolari, panchina)
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
            return totale + self._difesa(titolari, panchina, ct, cb, self._gioca_g[ct], righe_e)
        # Senza cambio di modulo il modificatore dipende solo da portiere e difensori titolari e dalle riserve P e D (in ordine):
        # i cambi vanno per reparto P, D, C, A, quindi chi entra in porta e in difesa non dipende da centrocampo e attacco.
        # Lo stesso reparto difensivo torna in molte formazioni a confronto: si calcola una volta.
        chiave = (tuple(c for c, t in zip(ct, titolari) if t.ruolo == "P"),
                  tuple(sorted(c for c, t in zip(ct, titolari) if t.ruolo == "D")),
                  tuple((b.ruolo, c) for c, b in zip(cb, panchina) if b.ruolo in ("P", "D")))
        difesa = self._cache_difesa.get(chiave)
        if difesa is None:
            difesa = self._cache_difesa[chiave] = self._difesa(titolari, panchina, ct, cb, self._gioca_g[ct], righe_e)
        return totale + difesa

    def _sostituzioni_cambio_modulo(self, titolari, panchina, ct, cb) -> np.ndarray:
        """Sostituzioni con il cambio di modulo, stesse regole di `chi_va_a_punteggio`, per tutte le simulazioni insieme.
        Restituisce chi entra: una riga per riserva, una colonna per simulazione."""
        # Insiemi di simulazioni (interi Python, un bit per simulazione). I mancanti si guardano uno alla volta in ordine di ruolo;
        # per ognuno, le riserve nell'ordine della panchina prendono le simulazioni in cui il titolare manca e nessuna riserva
        # precedente è già entrata. Il modulo (difensori, centrocampisti, attaccanti) cambia con i cambi tra ruoli diversi:
        # si tiene l'insieme delle simulazioni per ogni modulo raggiunto (sono pochi).
        pr = self.regole.panchina
        massimo = pr.max_sostituzioni
        bit, tutti = self._bit, self._tutti
        nb = len(cb)
        entra = [0] * nb
        if massimo > 0:
            ruoli_b = [b.ruolo for b in panchina]
            libere = [bit[c] for c in cb]                            # con voto e non ancora entrate
            moduli = {tuple(sum(t.ruolo == r for t in titolari) for r in "DCA"): tutti}   # modulo -> simulazioni
            cambi = [tutti] + [0] * massimo                          # almeno c cambi fatti
            # libera: il primo della panchina che può entrare; per ruolo: prima lo stesso ruolo, poi chi cambia il modulo
            passate = ((True, False),) if pr.tipo != "per_ruolo" else ((True,), (False,))
            for i in sorted(range(len(titolari)), key=lambda k: ORDINE_RUOLO[titolari[k].ruolo]):
                rm = titolari[i].ruolo
                manca = (tutti ^ bit[ct[i]]) & ~cambi[massimo]       # senza voto e con ancora cambi a disposizione
                if not manca:
                    continue
                ammesse = {}                                         # ruolo di chi entra -> simulazioni in cui il modulo resta valido
                if rm != "P":
                    for rb in set(ruoli_b) - {"P", rm}:
                        ammesse[rb] = 0
                        for mod, sims in moduli.items():
                            if self._cambio_valido(mod, rm, rb):
                                ammesse[rb] |= sims
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
                    for mod, sims in moduli.items():
                        for p, rb in cambiano:
                            mosse = sims & p
                            if mosse:
                                sims ^= mosse
                                dopo = _modulo_dopo(mod, rm, rb)
                                nuovi[dopo] = nuovi.get(dopo, 0) | mosse
                        if sims:
                            nuovi[mod] = nuovi.get(mod, 0) | sims
                    moduli = nuovi
        return self._righe(entra)

    def _cambio_valido(self, mod: tuple, esce: str, entra: str) -> bool:
        d, c, a = _modulo_dopo(mod, esce, entra)
        return bool(self._ammessi[d, c, a])

    def _righe(self, insiemi: list[int]) -> np.ndarray:
        """Da un insieme di simulazioni (intero Python) per riserva a una tabella di bool: una riga per riserva."""
        pacchi = np.frombuffer(b"".join(e.to_bytes(self._byte, "little") for e in insiemi), dtype=np.uint8)
        return np.unpackbits(pacchi.reshape(len(insiemi), self._byte), axis=1, count=self.gioca.shape[0],
                             bitorder="little").view(bool)

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
        return self._righe(entra)

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
        """(punteggio atteso, oscillazione, brutta giornata, giornata eccezionale) di una formazione, sulle simulazioni comuni."""
        r = self._riassunto(titolari, panchina)
        if r[1] is None:    # l'oscillazione serve solo per le formazioni finali: si calcola quando serve, con lo stesso ordine di prima
            r[1] = float(self._punti(r[4], r[5]).std())
        return r[0], r[1], r[2], r[3]

    def _riassunto(self, titolari: list[Giocatore], panchina: list[Giocatore]) -> list:
        """[media, oscillazione (None finché non serve), brutta, eccezionale, titolari, panchina] di una formazione, in cache.
        Titolari e panchina restano nell'ordine della prima chiamata: le somme in virgola mobile dipendono dall'ordine."""
        chiave = (tuple(sorted(t.id for t in titolari)), tuple(b.id for b in panchina))
        r = self._cache.get(chiave)
        if r is None:
            punti = self._punti(titolari, panchina)
            brutta, eccezionale = _percentili_10_90(punti)
            r = self._cache[chiave] = [float(punti.mean()), None, float(brutta), float(eccezionale), tuple(titolari), tuple(panchina)]
        return r

    def atteso(self, titolari: list[Giocatore], panchina: list[Giocatore]) -> float:
        return self._riassunto(titolari, panchina)[0]

    def scelta(self, titolari: list[Giocatore], panchina: list[Giocatore], peso: tuple[float, float]) -> float:
        media, _, brutta, eccezionale = self._riassunto(titolari, panchina)[:4]
        return media - peso[0] * (media - brutta) + peso[1] * (eccezionale - media)


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


def _tabella_moduli(regole: Regole) -> np.ndarray:
    """tabella[d, c, a] = True se (d, c, a) è un modulo ammesso."""
    t = np.zeros((12, 12, 12), dtype=bool)
    for m in regole.moduli:
        d, c, a = modulo_in_numeri(m)
        t[d, c, a] = True
    return t


def _panchina(rosa: list[Giocatore], titolari: list[Giocatore], regole: Regole,
              ordinati: list[Giocatore] | None = None) -> list[Giocatore]:
    """I migliori non titolari per valore (gioca N% x fantavoto atteso; almeno un portiere se c'è), messi in ordine di fantavoto
    atteso: una riserva entra solo se ha preso voto, e a quel punto conta quanto vale se gioca (#612). Panchina per ruolo: prima
    i ruoli nell'ordine della lega (P, D, C, A), dentro il ruolo chi vale di più; panchina libera: chi vale di più, di ogni ruolo.
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
        return sorted(scelti, key=lambda g: (ORDINE_RUOLO[g.ruolo], -g.mu))
    # libera: il posto del portiere di riserva non conta (entra solo per il portiere, e nessun altro può entrare al suo posto)
    return sorted(scelti, key=lambda g: -g.mu)


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
    """La formazione migliore tra tutti i moduli ammessi: punteggio atteso alto e, a parità, titolari più sicuri.
    Con più peso alla brutta giornata si preferiscono i titolari sicuri, con più peso alla giornata eccezionale chi può fare il colpo.
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
