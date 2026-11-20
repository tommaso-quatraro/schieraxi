"""Copertura della rosa: ogni reparto ha abbastanza giocatori disponibili per i moduli ammessi dalla lega?

Calcolo leggero (solo contare), nessuna simulazione: parte dalle previsioni già in cache (stato di ogni giocatore per la prossima
giornata: infortunato, squalificato, diffidato) e dai moduli ammessi in `regole`. Niente numeri scritti nel codice: il minimo per
reparto è quello del modulo meno esigente tra quelli ammessi dalla lega (il portiere è sempre 1).
- «scoperto»: i disponibili non bastano a riempire il reparto in nessun modulo ammesso;
- «a rischio»: bastano ma senza ricambio, oppure contando i diffidati (che con un giallo salterebbero la partita dopo) non bastano.
Lo usa «Da fare» in Oggi (`da_fare.py`; l'avviso del reparto scoperto non parte più dalla #693).
I testi sono `Frase` del catalogo (chiavi `dafare.copertura_*`, fanta/frasi.py): italiano nel testo, la traduzione la fa chi la
mostra (#816; prima erano scritti qui, in italiano e in inglese, senza chiave).
"""
from __future__ import annotations

import pandas as pd

from . import frasi
from .frasi import F, Frase
from .lega import Rose
from .regole import RUOLI, Regole, modulo_in_numeri

FUORI = ("infortunato", "squalificato")
SCOPERTO, RISCHIO = "scoperto", "rischio"
NOME = {"P": "dafare.copertura_portiere", "D": "dafare.copertura_difensore", "C": "dafare.copertura_centrocampista",
        "A": "dafare.copertura_attaccante"}                       # «nessun portiere»
QUANTI = {"P": "rose.portieri", "D": "rose.difensori", "C": "rose.centrocampisti", "A": "rose.attaccanti"}     # «2 portieri»
MAX_NOMI = 3


def _richieste(regole: Regole) -> list[dict[str, int]]:
    """Quanti giocatori per reparto chiede ciascun modulo ammesso."""
    out = []
    for m in regole.moduli:
        try:
            d, c, a = modulo_in_numeri(m)
        except ValueError:
            continue
        out.append({"P": 1, "D": d, "C": c, "A": a})
    return out


def _elenco(nomi: list[str]):
    """«A, B, C» o, con più di MAX_NOMI nomi, «A, B, C e altri 2»."""
    primi = frasi.elenco(nomi[:MAX_NOMI])
    return F("dafare.copertura_altri", nomi=primi, n=len(nomi) - MAX_NOMI) if len(nomi) > MAX_NOMI else primi


def _testo(ruolo: str, livello: str, minimo: int, disp: int, diffidati: list[str], fuori: list[str]) -> Frase:
    """Il testo di un reparto. Il punto in fondo si scrive una volta sola anche dopo un nome con l'iniziale («Fuori: Rossi L.»,
    lo fa `Frase`)."""
    quanti = F(QUANTI[ruolo], n=disp)
    if livello == SCOPERTO:
        t = (F("dafare.copertura_nessuno", ruolo=F(NOME[ruolo]), minimo=minimo) if disp == 0
             else F("dafare.copertura_pochi", quanti=quanti, minimo=minimo, n=disp))
        return F("dafare.copertura_fuori", testo=t, fuori=_elenco(fuori)) if fuori else t
    if disp - len(diffidati) < minimo and diffidati:
        quali = F("dafare.copertura_diffidati_nomi", n=len(diffidati), nomi=_elenco(diffidati))
        return F("dafare.copertura_diffidati", quanti=quanti, diffidati=quali, n=disp)
    return F("dafare.copertura_minimo", quanti=quanti, n=disp)


def analizza(prev: pd.DataFrame, regole: Regole, rose: Rose) -> dict | None:
    """None se non si può dire (rosa o previsioni mancanti). Altrimenti
    `{"reparti": [{ruolo, livello, disponibili, minimo, testo, fuori, diffidati}], "moduli_possibili": [...]}`:
    solo i reparti scoperti o a rischio, quelli scoperti per primi. `testo` è una `Frase` (italiano, con la chiave per tradurlo)."""
    s = rose.squadra(rose.mia_squadra or "")
    if not s:
        return None
    mia = [g.id for g in s.giocatori if g.id is not None and g.id in prev.index]
    if not mia:
        return None                                    # niente previsioni per la mia rosa: meglio tacere che dare un falso allarme
    richieste = _richieste(regole)
    if not richieste:
        return None
    disp = {r: [] for r in RUOLI}
    fuori = {r: [] for r in RUOLI}
    diffidati = {r: [] for r in RUOLI}
    for i in mia:
        x = prev.loc[i]
        r = x["ruolo"]
        if r not in disp:
            continue
        if x["stato"] in FUORI:
            fuori[r].append(str(x["nome"]))
        else:
            disp[r].append(str(x["nome"]))
            if bool(x.get("diffidato", False)):
                diffidati[r].append(str(x["nome"]))
    reparti = []
    for r in RUOLI:
        minimo = min(q[r] for q in richieste)
        n = len(disp[r])
        livello = SCOPERTO if n < minimo else RISCHIO if n == minimo or n - len(diffidati[r]) < minimo else None
        if livello:
            reparti.append({"ruolo": r, "livello": livello, "disponibili": n, "minimo": minimo, "fuori": fuori[r], "diffidati": diffidati[r],
                            "testo": _testo(r, livello, minimo, n, diffidati[r], fuori[r])})
    possibili = [m for m, q in zip(regole.moduli, richieste) if all(len(disp[r]) >= q[r] for r in RUOLI)]
    if not possibili and not any(x["livello"] == SCOPERTO for x in reparti):
        # ogni reparto basta da solo ma nessun modulo ammesso li soddisfa tutti insieme (es. solo 3-5-2 e 5-3-2)
        reparti.append({"ruolo": None, "livello": SCOPERTO, "disponibili": 0, "minimo": 0, "fuori": [], "diffidati": [],
                        "testo": F("dafare.copertura_moduli")})
    reparti.sort(key=lambda x: (x["livello"] != SCOPERTO, RUOLI.index(x["ruolo"]) if x["ruolo"] else 9))
    return {"reparti": reparti, "moduli_possibili": possibili}
