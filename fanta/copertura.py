"""Copertura della rosa: ogni reparto ha abbastanza giocatori disponibili per i moduli ammessi dalla lega?

Calcolo leggero (solo contare), nessuna simulazione: parte dalle previsioni già in cache (stato di ogni giocatore per la prossima
giornata: infortunato, squalificato, diffidato) e dai moduli ammessi in `regole`. Niente numeri scritti nel codice: il minimo per
reparto è quello del modulo meno esigente tra quelli ammessi dalla lega (il portiere è sempre 1).
- «scoperto»: i disponibili non bastano a riempire il reparto in nessun modulo ammesso;
- «a rischio»: bastano ma senza ricambio, oppure contando i diffidati (che con un giallo salterebbero la partita dopo) non bastano.
Lo usa «Da fare» in Oggi (`da_fare.py`; l'avviso del reparto scoperto non parte più dalla #693).
"""
from __future__ import annotations

import pandas as pd

from .lega import Rose
from .lingua import EN
from .regole import RUOLI, Regole, modulo_in_numeri

FUORI = ("infortunato", "squalificato")
SCOPERTO, RISCHIO = "scoperto", "rischio"
NOMI = {"P": ("portiere", "portieri"), "D": ("difensore", "difensori"), "C": ("centrocampista", "centrocampisti"),
        "A": ("attaccante", "attaccanti")}
NOMI_EN = {"P": ("goalkeeper", "goalkeepers"), "D": ("defender", "defenders"), "C": ("midfielder", "midfielders"),
           "A": ("forward", "forwards")}
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


def _nome(ruolo: str, n: int) -> str:
    return NOMI[ruolo][0 if n == 1 else 1]


def _disponibili(n: int) -> str:
    return "disponibile" if n == 1 else "disponibili"


def _elenco(nomi: list[str], lingua: str = "it") -> str:
    altri = f" and {len(nomi) - MAX_NOMI} more" if lingua == EN else f" e altri {len(nomi) - MAX_NOMI}"
    return ", ".join(nomi[:MAX_NOMI]) + (altri if len(nomi) > MAX_NOMI else "")


def _testo_en(ruolo: str, livello: str, minimo: int, disp: int, diffidati: list[str], fuori: list[str]) -> str:
    nome = NOMI_EN[ruolo][0 if disp == 1 else 1]
    if livello == SCOPERTO:
        t = (f"You have no {NOMI_EN[ruolo][0]} available: you need at least {minimo}." if disp == 0
             else f"You have only {disp} {nome} available: you need at least {minimo} to play.")
        return t + (f" Out: {_elenco(fuori, EN)}." if fuori else "")
    if disp - len(diffidati) < minimo and diffidati:
        k = len(diffidati)
        return (f"You have {disp} {nome} available, but {k} {'is' if k == 1 else 'are'} one yellow card from a ban ({_elenco(diffidati, EN)}): "
                f"with a yellow you would be short.")
    return f"You have only {disp} {nome} available, the minimum to play: if another one is out, you have no cover."


def _testo(ruolo: str, livello: str, minimo: int, disp: int, diffidati: list[str], fuori: list[str], lingua: str = "it") -> str:
    if lingua == EN:
        return _testo_en(ruolo, livello, minimo, disp, diffidati, fuori)
    nome = _nome(ruolo, disp)
    if livello == SCOPERTO:
        t = (f"Non hai nessun {_nome(ruolo, 1)} disponibile: ne servono almeno {minimo}." if disp == 0
             else f"Hai solo {disp} {nome} {_disponibili(disp)}: per giocare ne servono almeno {minimo}.")
        return t + (f" Fuori: {_elenco(fuori)}." if fuori else "")
    if disp - len(diffidati) < minimo and diffidati:
        k = len(diffidati)
        return (f"Hai {disp} {nome} {_disponibili(disp)}, ma {k} {'è diffidato' if k == 1 else 'sono diffidati'} ({_elenco(diffidati)}): "
                f"con un giallo resti scoperto.")
    return f"Hai solo {disp} {nome} {_disponibili(disp)}, il minimo per giocare: se un altro salta, resti senza ricambi."


def analizza(prev: pd.DataFrame, regole: Regole, rose: Rose, lingua: str = "it") -> dict | None:
    """None se non si può dire (rosa o previsioni mancanti). Altrimenti
    `{"reparti": [{ruolo, livello, disponibili, minimo, testo, fuori, diffidati}], "moduli_possibili": [...]}`:
    solo i reparti scoperti o a rischio, quelli scoperti per primi. `lingua` ("it" o "en") è la lingua di `testo`."""
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
                            "testo": _testo(r, livello, minimo, n, diffidati[r], fuori[r], lingua)})
    possibili = [m for m, q in zip(regole.moduli, richieste) if all(len(disp[r]) >= q[r] for r in RUOLI)]
    if not possibili and not any(x["livello"] == SCOPERTO for x in reparti):
        # ogni reparto basta da solo ma nessun modulo ammesso li soddisfa tutti insieme (es. solo 3-5-2 e 5-3-2)
        reparti.append({"ruolo": None, "livello": SCOPERTO, "disponibili": 0, "minimo": 0, "fuori": [], "diffidati": [],
                        "testo": ("With the players available you cannot field any of the formations your league allows." if lingua == EN
                                  else "Con i giocatori disponibili non riesci a schierare nessuno dei moduli ammessi dalla tua lega.")})
    reparti.sort(key=lambda x: (x["livello"] != SCOPERTO, RUOLI.index(x["ruolo"]) if x["ruolo"] else 9))
    return {"reparti": reparti, "moduli_possibili": possibili}
