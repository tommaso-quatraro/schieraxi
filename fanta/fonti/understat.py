"""Understat: xG, xA, tiri, minuti, rigori calciati, partita per partita; e abbinamento dei giocatori al listone."""
from __future__ import annotations

import difflib
import re
from collections import defaultdict

from ..listone import Calciatore
from ..nomi import normalizza

BASE = "https://understat.com"
HEADERS = {"X-Requested-With": "XMLHttpRequest"}


def url_lega(anno_inizio: int) -> str:
    return f"{BASE}/getLeagueData/Serie_A/{anno_inizio}"


def url_partita(understat_id: int) -> str:
    return f"{BASE}/getMatchData/{understat_id}"


def _f(x) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def _i(x) -> int:
    return int(_f(x))


def leggi_lega(dati: dict) -> tuple[list[dict], list[dict]]:
    """Restituisce (partite, totali dei giocatori nella stagione)."""
    partite = [{
        "id": int(m["id"]), "data": m["datetime"], "casa": m["h"]["title"], "trasferta": m["a"]["title"],
        "gol_casa": _i(m["goals"]["h"]) if m["isResult"] else None,
        "gol_trasferta": _i(m["goals"]["a"]) if m["isResult"] else None,
        "xg_casa": _f(m["xG"]["h"]) if m["isResult"] else None,
        "xg_trasferta": _f(m["xG"]["a"]) if m["isResult"] else None,
        "giocata": int(bool(m["isResult"])),
    } for m in dati.get("dates", [])]
    giocatori = [{
        "understat_giocatore": int(p["id"]), "nome": p["player_name"], "squadre": p["team_title"],
        "posizione": p.get("position", ""), "partite": _i(p["games"]), "minuti": _i(p["time"]),
        "gol": _i(p["goals"]), "npgol": _i(p.get("npg")), "xg": _f(p["xG"]), "npxg": _f(p.get("npxG")),
        "assist": _i(p["assists"]), "xa": _f(p["xA"]), "tiri": _i(p["shots"]), "passaggi_chiave": _i(p["key_passes"]),
        "gialli": _i(p["yellow_cards"]), "rossi": _i(p["red_cards"]),
        "xg_chain": _f(p.get("xGChain")), "xg_buildup": _f(p.get("xGBuildup")),
    } for p in dati.get("players", [])]
    return partite, giocatori


def leggi_partita(dati: dict, understat_id: int, casa: str, trasferta: str) -> list[dict]:
    """Una riga per giocatore sceso in campo. casa/trasferta: nomi delle squadre (come in Understat)."""
    rigori, rigori_gol, punizioni = defaultdict(int), defaultdict(int), defaultdict(int)
    for lato in ("h", "a"):
        for tiro in dati.get("shots", {}).get(lato, []):
            gid = int(tiro["player_id"])
            if tiro.get("situation") == "Penalty":
                rigori[gid] += 1
                rigori_gol[gid] += tiro.get("result") == "Goal"
            elif tiro.get("situation") == "DirectFreekick":
                punizioni[gid] += 1
    righe = []
    for lato, squadra in (("h", casa), ("a", trasferta)):
        for p in dati.get("rosters", {}).get(lato, {}).values():
            if _i(p.get("time")) <= 0:
                continue
            gid = int(p["player_id"])
            righe.append({
                "understat_partita": understat_id, "understat_giocatore": gid, "squadra": squadra,
                "posizione": p.get("position", ""), "minuti": _i(p["time"]), "gol": _i(p["goals"]),
                "autogol": _i(p.get("own_goals")), "tiri": _i(p["shots"]), "xg": _f(p["xG"]), "xa": _f(p["xA"]),
                "assist": _i(p["assists"]), "passaggi_chiave": _i(p["key_passes"]),
                "xg_chain": _f(p.get("xGChain")), "xg_buildup": _f(p.get("xGBuildup")),
                "gialli": _i(p.get("yellow_card")), "rossi": _i(p.get("red_card")),
                "rigori_calciati": rigori[gid], "rigori_segnati": rigori_gol[gid], "punizioni": punizioni[gid],
                "entrato": int(_i(p.get("roster_in")) != 0),
                "uscito": int(_i(p.get("roster_out")) != 0),
            })
    return righe


# ---------------- abbinamento al listone ----------------
def _parti_nome(nome_fc: str) -> tuple[list[str], list[str]]:
    """'Martinez Jo.' -> (['martinez'], ['jo']); 'Esposito F.P.' -> (['esposito'], ['f', 'p'])."""
    cognomi, iniziali = [], []
    for i, parte in enumerate(nome_fc.split()):
        if i > 0 and parte.endswith("."):
            iniziali += [x for x in normalizza(parte).split() if x]
        else:
            cognomi += normalizza(parte).split()
    return cognomi, iniziali


def punteggio(nome_fc: str, nome_us: str) -> float:
    """Quanto un nome di Fantacalcio.it ('Martinez L.') corrisponde a uno di Understat ('Lautaro Martínez'). 0 = no."""
    cognomi, iniziali = _parti_nome(nome_fc)
    parole = normalizza(nome_us).split()
    if not cognomi or not parole:
        return 0.0
    attaccati = "".join(cognomi)
    if all(c in parole for c in cognomi):
        base = 2.0 + len(cognomi)
    elif any(attaccati == "".join(parole[i:j]) for i in range(len(parole)) for j in range(i + 2, len(parole) + 1)):
        base = 3.0                           # 'Delprato' e 'Del Prato'
    elif len(cognomi) > 1 and len(parole) > 1 and cognomi[0] == parole[-1] and len(cognomi[0]) >= 4:
        # cognome doppio scritto a metà: 'Floriani Mussolini' e 'Romano Floriani' (ma non 'Kevin Carlos' e 'Kevin Omoruyi')
        base = 2.0
    else:  # piccole differenze di grafia
        rapporto = max(difflib.SequenceMatcher(None, " ".join(cognomi), " ".join(parole[i:i + len(cognomi)])).ratio()
                       for i in range(max(1, len(parole) - len(cognomi) + 1)))
        if rapporto < 0.85:
            return 0.0
        base = rapporto
    nomi_propri = [p for p in parole if p not in cognomi]
    if iniziali and nomi_propri:
        sigla = "".join(iniziali)                    # 'Jo.' -> 'jo', 'Hj.' -> 'hj', 'F.P.' -> 'fp'
        prime_lettere = "".join(p[0] for p in nomi_propri)
        if any(p.startswith(sigla) for p in nomi_propri) or sigla in prime_lettere:
            base += 1.0
        else:
            return 0.0                               # 'Martinez Jo.' non è 'Lautaro Martinez'
    if normalizza(nome_fc) == normalizza(nome_us):
        base += 1.0
    return base


# Soprannomi: nome su Understat -> nome su Fantacalcio.it (stessa squadra). Da allungare quando serve.
SOPRANNOMI = {
    "valde": "Valdepenas",
    "kevin omoruyi": "Kevin Carlos",       # Kevin Carlos Omoruyi Benjamin
    "alfonso": "Pedraza",                  # Alfonso Pedraza
    "kouadio kone": "Konè M.",             # Kouadio Manu Koné
}


def abbina(giocatori_us: list[dict], calciatori: list[Calciatore], slug_di) -> dict[int, tuple[int, str]]:
    """{understat_id: (calciatore_id, metodo)}. slug_di: funzione nome squadra Understat -> slug Fantacalcio.

    Prima nella stessa squadra (abbinamento uno a uno, il punteggio più alto vince),
    poi, per chi resta, in tutta la Serie A se il nome è inequivocabile (trasferimenti).
    """
    per_squadra: dict[str, list[Calciatore]] = defaultdict(list)
    for c in calciatori:
        per_squadra[c.squadra_slug].append(c)
    coppie = []
    for g in giocatori_us:
        slugs = {slug_di(t.strip()) for t in re.split(r",", g["squadre"] or "")} - {None}
        soprannome = SOPRANNOMI.get(normalizza(g["nome"]))
        for s in slugs:
            for c in per_squadra.get(s, []):
                if soprannome:
                    p = 10.0 if normalizza(c.nome) == normalizza(soprannome) else 0.0
                else:
                    p = punteggio(c.nome, g["nome"])
                if p > 0:
                    coppie.append((p, g["understat_giocatore"], c.id))
    esito: dict[int, tuple[int, str]] = {}
    usati: set[int] = set()
    migliori: dict[int, list[float]] = defaultdict(list)
    for p, gid, cid in coppie:
        migliori[gid].append(p)
    for p, gid, cid in sorted(coppie, reverse=True):
        if gid in esito or cid in usati:
            continue
        pari = sorted(migliori[gid], reverse=True)
        if len(pari) > 1 and pari[0] == pari[1] == p:
            continue                         # due candidati identici: meglio non abbinare
        esito[gid] = (cid, "squadra" if p >= 3 else "squadra_simile")
        usati.add(cid)
    for g in giocatori_us:                    # trasferiti: nome forte e unico in tutta la Serie A
        gid = g["understat_giocatore"]
        if gid in esito:
            continue
        candidati = [c for c in calciatori if c.id not in usati and punteggio(c.nome, g["nome"]) >= 3]
        if len(candidati) == 1:
            esito[gid] = (candidati[0].id, "altra_squadra")
            usati.add(candidati[0].id)
    return esito
