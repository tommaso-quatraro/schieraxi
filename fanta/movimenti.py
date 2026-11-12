"""Cosa è cambiato tra due versioni delle rose: scambi tra squadre, svincolati presi, giocatori tagliati, crediti.

Si confrontano le rose di prima e di dopo un'importazione. Contano solo le squadre presenti in entrambe: se una squadra
sparisce (importazione con "togli le altre") o è nuova, i suoi giocatori non vengono scambiati per tagli o acquisti.
Lo storico dei movimenti resta in lega/movimenti.json.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .lega import GiocatoreRosa, Rose
from .percorsi import scrivi_sicuro

MAX_STORICO = 300


def _chiave(g: GiocatoreRosa, per_nome: frozenset = frozenset()) -> object:
    """Un giocatore si riconosce dal codice; se in una delle due importazioni non era stato riconosciuto (codice mancante), dal nome."""
    nome = g.nome.strip().lower()
    return ("nome", nome) if g.id is None or nome in per_nome else g.id


def _breve(g: GiocatoreRosa) -> dict:
    return {"id": g.id, "nome": g.nome, "ruolo": g.ruolo, "squadra": g.squadra, "costo": g.costo}


def differenze(prima: Rose | None, dopo: Rose) -> dict:
    """Confronta le due rose. 'testo' è un riassunto in italiano pronto da mostrare (anche in una notifica)."""
    if prima is None or not prima.squadre:
        n = len(dopo.squadre)
        return {"prima_importazione": True, "scambi": [], "svincolati_presi": [], "tagliati": [], "crediti": [],
                "squadre_nuove": [], "squadre_tolte": [], "nessuna_differenza": False,
                "testo": f"Prima importazione: {n} {'squadra' if n == 1 else 'squadre'}."}
    nomi_prima = {s.nome for s in prima.squadre}
    nomi_dopo = {s.nome for s in dopo.squadre}
    comuni = nomi_prima & nomi_dopo
    per_nome = frozenset(g.nome.strip().lower() for r in (prima, dopo) for s in r.squadre for g in s.giocatori if g.id is None)
    giocatori_prima = {s.nome: {_chiave(g, per_nome): g for g in s.giocatori} for s in prima.squadre}
    giocatori_dopo = {s.nome: {_chiave(g, per_nome): g for g in s.giocatori} for s in dopo.squadre}
    proprietario_prima = {k: n for n, gs in giocatori_prima.items() for k in gs}
    proprietario_dopo = {k: n for n, gs in giocatori_dopo.items() for k in gs}

    passaggi: dict[tuple[str, str], list[dict]] = {}     # (da, a) -> giocatori
    presi: dict[str, list[dict]] = {}                    # squadra -> giocatori arrivati dagli svincolati
    tagliati: dict[str, list[dict]] = {}                 # squadra -> giocatori usciti dalla lega
    for k, a in proprietario_prima.items():
        if a not in comuni:
            continue
        b = proprietario_dopo.get(k)
        g = giocatori_prima[a][k]
        if b is None:
            tagliati.setdefault(a, []).append(_breve(g))
        elif b != a and b in comuni:
            passaggi.setdefault((a, b), []).append(_breve(giocatori_dopo[b][k]))
    for k, b in proprietario_dopo.items():
        if b in comuni and k not in proprietario_prima:
            presi.setdefault(b, []).append(_breve(giocatori_dopo[b][k]))

    scambi, fatti = [], set()
    for (a, b), da_a in passaggi.items():
        if (a, b) in fatti:
            continue
        fatti.add((a, b)); fatti.add((b, a))
        scambi.append({"squadre": [a, b], "da_a": da_a, "da_b": passaggi.get((b, a), [])})
    crediti = []
    for s_dopo in dopo.squadre:
        s_prima = next((s for s in prima.squadre if s.nome == s_dopo.nome), None)
        if s_prima and s_prima.crediti_residui != s_dopo.crediti_residui:
            crediti.append({"squadra": s_dopo.nome, "prima": s_prima.crediti_residui, "dopo": s_dopo.crediti_residui})

    elenco = lambda gs: ", ".join(g["nome"] for g in gs)   # noqa: E731
    nuove = [s.nome for s in dopo.squadre if s.nome not in nomi_prima]
    tolte = [s.nome for s in prima.squadre if s.nome not in nomi_dopo]
    righe = []
    if nuove:
        righe.append(f"Squadre aggiunte: {', '.join(nuove)}")
    if tolte:
        righe.append(f"Squadre tolte: {', '.join(tolte)}")
    for sc in scambi:
        a, b = sc["squadre"]
        if sc["da_b"]:
            righe.append(f"Scambio {a} / {b}: {elenco(sc['da_a'])} ⇄ {elenco(sc['da_b'])}")
        else:
            righe.append(f"Passaggio da {a} a {b}: {elenco(sc['da_a'])}")
    righe += [f"{s} prende dagli svincolati: {elenco(gs)}" for s, gs in presi.items()]
    righe += [f"{s} lascia liberi: {elenco(gs)}" for s, gs in tagliati.items()]
    righe += [f"Crediti {c['squadra']}: {c['prima']} → {c['dopo']}" for c in crediti]
    nessuna = not righe
    return {"prima_importazione": False, "scambi": scambi,
            "svincolati_presi": [{"squadra": s, "giocatori": gs} for s, gs in presi.items()],
            "tagliati": [{"squadra": s, "giocatori": gs} for s, gs in tagliati.items()],
            "crediti": crediti, "squadre_nuove": nuove, "squadre_tolte": tolte, "nessuna_differenza": nessuna,
            "testo": "Nessuna differenza rispetto a prima." if nessuna else "\n".join(righe)}


def registra(percorso: Path, diff: dict, quando: datetime | None = None) -> None:
    """Aggiunge i movimenti allo storico (se c'è qualcosa di nuovo)."""
    if diff.get("nessuna_differenza") or diff.get("prima_importazione"):
        return
    storico = leggi(percorso)
    storico.append({"quando": (quando or datetime.now()).isoformat(timespec="seconds"),
                    **{k: diff[k] for k in ("scambi", "svincolati_presi", "tagliati", "crediti", "squadre_nuove", "squadre_tolte", "testo")
                       if k in diff}})
    scrivi_sicuro(percorso, json.dumps(storico[-MAX_STORICO:], ensure_ascii=False))


def leggi(percorso: Path, ultimi: int | None = None) -> list[dict]:
    try:
        dati = json.loads(percorso.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    dati = dati if isinstance(dati, list) else []
    return dati[-ultimi:] if ultimi else dati
