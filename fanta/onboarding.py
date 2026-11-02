"""La procedura guidata per chi arriva (solo con FANTA_MULTIUTENTE=1): il suo stato sul server, la lega demo e i controlli finali.

Lo stato (a che passo è, se ha finito) sta in `account.sqlite`, tabella `leghe`, così si riprende da un altro dispositivo.
Qui non c'è FastAPI: le rotte stanno in server.py e il percorso a schermo (primo avvio) in `web/primoavvio.js`.
"""
from __future__ import annotations

import sqlite3
from dataclasses import asdict
from datetime import datetime, timezone

from . import lega, regole
from .account import ErroreAccount
from .lega import GiocatoreRosa, Rose, Squadra
from .listone import Calciatore

PASSI = ("benvenuto", "tipo", "regole", "rose", "squadra", "controlli", "formazione", "avvisi")
STATI = ("da_fare", "in_corso", "completato", "saltato")
TIPI = ("classic",)
SQUADRE_DEMO = ("Atletico Prova", "Real Esempio", "Dinamo Finta", "Sporting Demo")      # nomi inventati: nessuna squadra o lega vera


def _ora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _come_dict(riga: sqlite3.Row) -> dict:
    return {"tipo": riga["tipo"], "stato": riga["stato"], "passo": riga["passo"], "demo": bool(riga["demo"]),
            "aggiornato": riga["aggiornato"], "passi": list(PASSI)}


def leggi(db: sqlite3.Connection, utente_id: int, ha_rose: bool = False) -> dict:
    """Lo stato della procedura. La prima volta si crea: chi ha già delle rose (per esempio l'amministratore con la sua lega
    di sempre) la procedura non gli serve, e parte già come completata."""
    riga = db.execute("SELECT * FROM leghe WHERE utente_id = ?", (utente_id,)).fetchone()
    if riga is None:
        db.execute("INSERT INTO leghe (utente_id, tipo, stato, passo, demo, aggiornato) VALUES (?, 'classic', ?, 'benvenuto', 0, ?)",
                   (utente_id, "completato" if ha_rose else "da_fare", _ora()))
        db.commit()
        riga = db.execute("SELECT * FROM leghe WHERE utente_id = ?", (utente_id,)).fetchone()
    return _come_dict(riga)


def aggiorna(db: sqlite3.Connection, utente_id: int, passo: str | None = None, stato: str | None = None, tipo: str | None = None,
             demo: bool | None = None, ha_rose: bool = False) -> dict:
    """Cambia passo, stato o tipo (solo i campi indicati). Valori sconosciuti o una lega Mantra: errore chiaro in italiano."""
    leggi(db, utente_id, ha_rose)
    if passo is not None and passo not in PASSI:
        raise ErroreAccount("Passo sconosciuto della procedura guidata")
    if stato is not None and stato not in STATI:
        raise ErroreAccount("Stato sconosciuto della procedura guidata")
    if tipo is not None and tipo not in TIPI:
        raise ErroreAccount("Per ora SchieraXI funziona solo con le leghe classic: la Mantra non è ancora supportata.")
    campi = {"passo": passo, "stato": stato, "tipo": tipo, "demo": None if demo is None else int(demo)}
    campi = {k: v for k, v in campi.items() if v is not None}
    if campi:
        db.execute(f"UPDATE leghe SET {', '.join(k + ' = ?' for k in campi)}, aggiornato = ? WHERE utente_id = ?",
                   (*campi.values(), _ora(), utente_id))
        db.commit()
    return leggi(db, utente_id)


# ---------------------------------------------------------------- regole dal regolamento incollato
def applica_modifiche(base: regole.Regole, modifiche: list[dict]) -> regole.Regole:
    """Le regole `base` con le modifiche riconosciute da regole_testo.interpreta (chiave a percorso puntato: «bonus.gol.D»).
    Si applicano tutte e poi si controlla il risultato (alcune non stanno in piedi da sole, per esempio i posti in panchina e il loro totale)."""
    dati = asdict(base)
    for m in modifiche:
        *percorso, ultima = str(m["chiave"]).split(".")
        pezzo = dati
        for p in percorso:
            if not isinstance(pezzo.get(p), dict):
                raise ValueError(f"Regola sconosciuta: {m['chiave']}")
            pezzo = pezzo[p]
        if ultima not in pezzo:
            raise ValueError(f"Regola sconosciuta: {m['chiave']}")
        pezzo[ultima] = m["valore"]
    return regole.da_dict(dati)


def proponi_regole(base: regole.Regole, testo: str) -> dict:
    """Legge il regolamento e propone le regole: `riconosciute` (con la riga di origine), `da_confermare` (righe con numeri che non so
    leggere: l'utente le guarda una per una) e le `regole` risultanti. Non salva niente."""
    from . import regole_testo
    esito = regole_testo.interpreta(testo[:30000])
    risultato = applica_modifiche(base, esito["modifiche"]) if esito["modifiche"] else base
    return {"riconosciute": esito["modifiche"], "da_confermare": esito["non_riconosciute"], "regole": asdict(risultato)}


# ---------------------------------------------------------------- lega demo
def crea_demo(calciatori: list[Calciatore], r: regole.Regole) -> Rose:
    """Quattro squadre inventate con calciatori veri, distribuiti a turno per quotazione (squadre simili fra loro):
    serve a provare l'app senza importare niente. I nomi di squadra sono finti."""
    squadre = [Squadra(nome, [], r.crediti_iniziali) for nome in SQUADRE_DEMO]
    for ruolo, quanti in r.rosa.items():
        migliori = sorted((c for c in calciatori if c.ruolo == ruolo), key=lambda c: (-c.quotazione, c.nome))[: quanti * len(squadre)]
        for posto, c in enumerate(migliori):
            giro, k = divmod(posto, len(squadre))
            squadre[k if giro % 2 == 0 else len(squadre) - 1 - k].giocatori.append(
                GiocatoreRosa(c.id, c.nome, c.ruolo, c.squadra, costo=None, riconosciuto="esatto"))
    return Rose(squadre, SQUADRE_DEMO[0], datetime.now().isoformat(timespec="seconds"))


def e_demo(rose: Rose | None) -> bool:
    """Queste rose sono ancora quelle della lega demo (stessi nomi di squadra inventati)? Se l'utente ha importato le sue, no."""
    return bool(rose and rose.squadre and {s.nome for s in rose.squadre} == set(SQUADRE_DEMO))


# ---------------------------------------------------------------- controlli finali
def controlli(r: regole.Regole, rose: Rose | None, regole_salvate: bool) -> list[dict]:
    """Le spunte prima della prima formazione. `obbligatorio`: senza non si va avanti; le altre sono avvisi (si può continuare)."""
    squadre = rose.squadre if rose else []
    avvisi = lega.controlla(rose, r) if rose and squadre else []
    non_riconosciuti = [f"{s.nome}: {g.nome}" for s in squadre for g in s.giocatori if g.id is None]
    doppioni = [a for a in avvisi if "è in più squadre" in a]
    incomplete = [a for a in avvisi if "rosa diversa dalle regole" in a]

    def voce(id_, titolo, ok, obbligatorio, dettaglio=""):
        return {"id": id_, "titolo": titolo, "ok": bool(ok), "obbligatorio": obbligatorio, "dettaglio": dettaglio}
    return [
        voce("regole", "Regole della lega confermate", regole_salvate, True,
             "" if regole_salvate else "Conferma le regole (anche il modello standard) al passo delle regole."),
        # una squadra basta per cominciare (decisione del 2/11/2026): le altre servono solo agli scambi, quindi sono un avviso
        voce("rose", "Rose importate", len(squadre) >= 1, True,
             "" if squadre else "Importa almeno la rosa della tua squadra."),
        voce("altre_squadre", "Rose delle altre squadre", len(squadre) >= 2, False,
             "" if len(squadre) != 1 else lega.UNA_SQUADRA),
        voce("squadra", "Hai scelto la tua squadra", bool(rose and rose.mia_squadra and rose.squadra(rose.mia_squadra)), True),
        voce("riconosciuti", "Tutti i giocatori sono riconosciuti", not non_riconosciuti, False,
             "; ".join(non_riconosciuti[:5]) + (f" e altri {len(non_riconosciuti) - 5}" if len(non_riconosciuti) > 5 else "")),
        voce("complete", "Le rose rispettano le regole", not incomplete, False, "; ".join(incomplete[:3])),
        voce("doppioni", "Nessun giocatore in due squadre", not doppioni, False, "; ".join(doppioni[:3])),
    ]
