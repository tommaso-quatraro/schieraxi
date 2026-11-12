"""Fantacalcio.it: calendario, voti per giornata, probabili formazioni con indisponibili.

Tutte le pagine riportano il codice del calciatore nel link (…/squadre/<squadra>/<nome>/<codice>):
è quello che usiamo per abbinare tutto senza ambiguità.
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag

BASE = "https://www.fantacalcio.it"
STATO_FINITA = "4"


def url_calendario(giornata: int) -> str:
    """Solo stagione in corso (con la stagione nell'indirizzo il sito mostra il dettaglio di una partita).
    Le partite delle stagioni passate si leggono dalle pagine dei voti, che le contengono."""
    return f"{BASE}/serie-a/calendario/{giornata}"


def url_voti(stagione: str, giornata: int) -> str:
    return f"{BASE}/voti-fantacalcio-serie-a/{stagione}/{giornata}"


URL_PROBABILI = f"{BASE}/probabili-formazioni-serie-a"


def _id_calciatore(a: Tag | None) -> int | None:
    # .../squadre/<squadra>/<nome>/<codice>, nelle stagioni passate seguito da /<stagione>
    m = re.search(r"/squadre/[^/]+/[^/]+/(\d+)", a.get("href", "")) if a else None
    return int(m.group(1)) if m else None


def _slug_squadra(a: Tag | None) -> str | None:
    m = re.search(r"/squadre/([^/]+)", a.get("href", "")) if a else None
    return m.group(1) if m else None


def _numero(testo: str | None) -> float | None:
    """'6,5' -> 6.5; '55' (senza voto) o vuoto -> None."""
    if testo is None or testo.strip() in ("", "55", "-"):
        return None
    try:
        return float(testo.replace(",", "."))
    except ValueError:
        return None


def _intero(testo: str | None) -> int | None:
    """'2' o '2.0' -> 2; vuoto o illeggibile ('-', 'n.d.') -> None. Un solo campo strano non deve far perdere tutta la pagina."""
    try:
        return int(float(str(testo).strip().replace(",", ".")))
    except (TypeError, ValueError, OverflowError):
        return None


def _percentuale(testo: str | None) -> float | None:
    """'75' -> 75.0 (qui 55 è una percentuale vera, non il «senza voto» dei voti); illeggibile -> None."""
    try:
        return float(str(testo).strip().replace(",", "."))
    except ValueError:
        return None


# ---------------- calendario ----------------
def leggi_calendario(html: str, giornata: int, stagione: str) -> list[dict]:
    """Partite della giornata e della stagione chieste (es. '2026-27'). A cavallo dell'estate la pagina
    può mostrare l'altra stagione: in quel caso non restituisce nulla, invece di mescolarle."""
    s = BeautifulSoup(html, "lxml")
    partite = []
    visti = set()
    for pill in s.select("li.match .match-pill"):
        punteggio = pill.select_one("a.match-score")
        m = re.search(r"/calendario/(\d+)/([^/]+)/[^/]+/(\d+)", punteggio.get("href", "")) if punteggio else None
        if not m or int(m.group(1)) != giornata or m.group(2) != stagione or int(m.group(3)) in visti:
            continue  # riquadri di altre giornate/stagioni (o della stessa, ripetuta) presenti nella pagina
        visti.add(int(m.group(3)))
        casa = _slug_squadra(pill.select_one(".team-home a.team-link"))
        trasferta = _slug_squadra(pill.select_one(".team-away a.team-link"))
        data = pill.select_one(".match-date meta[itemprop=startDate]")
        ora = pill.select_one(".match-date .hours")
        finita = pill.get("data-match-status") == STATO_FINITA
        gc, gt = pill.select_one(".score-home"), pill.select_one(".score-away")
        gol_c = _intero(gc.get_text(strip=True)) if finita and gc else None
        gol_t = _intero(gt.get_text(strip=True)) if finita and gt else None
        if finita and gc and gt and (gol_c is None or gol_t is None):
            finita = False          # punteggio illeggibile (es. «-»): resta da finire, il prossimo aggiornamento la completa
        partite.append({
            "id": int(m.group(3)), "giornata": giornata,
            "data": f"{data['content']} {ora.get_text(strip=True)}" if data and ora else (data["content"] if data else None),
            "casa": casa, "trasferta": trasferta,
            "gol_casa": gol_c if finita else None,
            "gol_trasferta": gol_t if finita else None,
            "giocata": int(finita),
        })
    return partite


def stagioni_nel_calendario(html: str) -> set[str]:
    """Le stagioni delle partite che la pagina del calendario mostra (es. {'2026-27'}): d'estate il sito mostra ancora quella
    vecchia, e `leggi_calendario` per la stagione nuova non trova niente. Insieme vuoto = nessuna partita riconoscibile."""
    s = BeautifulSoup(html, "lxml")
    return {m.group(1) for a in s.select("li.match .match-pill a.match-score")
            if (m := re.search(r"/calendario/\d+/([^/]+)/", a.get("href", "")))}


# ---------------- voti ----------------
_BONUS = {"Gol segnati": "gol", "Gol subiti": "gol_subiti", "Autoreti": "autogol", "Rigori segnati": "rig_segnati",
          "Rigori sbagliati": "rig_sbagliati", "Rigori parati": "rig_parati", "Assist": "assist",
          "Player of the match": "mvp"}


SCARTI_TOLLERATI = 2          # righe dei voti senza i tre voti e i tre fantavoti che si saltano senza fermare la pagina...
QUOTA_SCARTI = 0.10           # ...e quota oltre la quale (se sono più di SCARTI_TOLLERATI) la pagina è cambiata: errore


def leggi_voti(html: str, giornata: int) -> list[dict]:
    """Le righe dei voti della giornata (vedi `leggi_voti_e_scarti`)."""
    return leggi_voti_e_scarti(html, giornata)[0]


def leggi_voti_e_scarti(html: str, giornata: int) -> tuple[list[dict], int]:
    """(righe, scartate): una riga per giocatore; «scartate» = righe di giocatori senza i tre voti e i tre fantavoti, che prima si
    saltavano in silenzio. Poche si saltano e si contano (le scrive l'aggiornamento); se sono più di SCARTI_TOLLERATI e oltre
    QUOTA_SCARTI delle righe, la pagina è cambiata e si ferma con un errore (prima: giornata con meno voti, senza dirlo)."""
    s = BeautifulSoup(html, "lxml")
    titolo = s.title.get_text() if s.title else ""
    m = re.search(r"(\d+)\s*giornata", titolo)
    if m and int(m.group(1)) != giornata:
        raise ValueError(f"La pagina voti è della giornata {m.group(1)}, non della {giornata}")
    righe = []
    scartate = 0
    for tabella in s.select("table.grades-table"):
        squadra = _slug_squadra(tabella.select_one("a.team-link"))
        for tr in tabella.select("tbody tr"):
            a = tr.select_one("a.player-link")
            ruolo = tr.select_one(".role")
            ruolo = ruolo["data-value"] if ruolo else ""
            if not a or ruolo == "all":       # le righe degli allenatori non ci servono
                continue
            if _id_calciatore(a) is None:
                raise ValueError(f"voti: codice calciatore non trovato nel link {a.get('href')!r}")
            voti = tr.select(".player-grade")
            fv = tr.select(".player-fanta-grade")
            if len(voti) != 3 or len(fv) != 3:
                scartate += 1
                continue
            bonus = {_BONUS[b["title"]]: _intero(b.get("data-value")) or 0 for b in tr.select(".player-bonus")
                     if b.get("title") in _BONUS}
            classi = " ".join(" ".join(v.get("class", [])) for v in voti)
            icone = " ".join(i.get("title", "") for i in tr.select("img.player-icon"))
            righe.append({
                "giornata": giornata, "calciatore_id": _id_calciatore(a), "nome": a.get_text(strip=True),
                "squadra": squadra, "ruolo": ruolo.upper(),
                "voto_red": _numero(voti[0].get("data-value")), "fv_red": _numero(fv[0].get("data-value")),
                "voto_stat": _numero(voti[1].get("data-value")), "fv_stat": _numero(fv[1].get("data-value")),
                "voto_ita": _numero(voti[2].get("data-value")), "fv_ita": _numero(fv[2].get("data-value")),
                **{k: bonus.get(k, 0) for k in _BONUS.values()},
                "ammonizioni": int("yellow-card" in classi), "espulsioni": int("red-card" in classi),
                "subentrato": int("Subentrato" in icone), "sostituito": int("Sostituito" in icone),
            })
    totale = len(righe) + scartate
    if scartate > SCARTI_TOLLERATI and scartate > QUOTA_SCARTI * totale:
        raise ValueError(f"voti giornata {giornata}: {scartate} righe su {totale} senza i tre voti e i tre fantavoti, "
                         "la pagina forse è cambiata")
    return righe, scartate


# ---------------- probabili formazioni e indisponibili ----------------
def leggi_probabili(html: str) -> tuple[int | None, list[dict]]:
    """Restituisce (giornata, righe). Una riga per giocatore citato; chi non è citato è da considerare fuori."""
    s = BeautifulSoup(html, "lxml")
    m = re.search(r"Giornata\s+(\d+)", s.get_text(" ", strip=True))
    giornata = int(m.group(1)) if m else None
    righe: dict[int, dict] = {}

    def riga(a: Tag, squadra: str | None, partita: int) -> dict | None:
        cid = _id_calciatore(a)
        if cid is None:
            return None
        return righe.setdefault(cid, {
            "calciatore_id": cid, "squadra": squadra or _slug_squadra(a), "partita_id": partita,
            "stato": None, "percentuale": None, "in_dubbio": 0, "diffidato": 0, "nota": None})

    for match in s.select("li.match-item[data-match-id]"):
        partita = int(match["data-match-id"])
        carte = match.select("div.team-card")
        for carta in carte:
            for lista, stato in (("ul.starters", "titolare"), ("ul.reserves", "panchina")):
                for li in carta.select(f"{lista} li.player-item"):
                    a = li.select_one("a.player-link")
                    r = riga(a, _slug_squadra(a), partita) if a else None
                    if r is None:
                        continue
                    valore = li.select_one(".progress-bar[aria-valuenow]")
                    r["stato"] = stato
                    r["percentuale"] = _percentuale(valore["aria-valuenow"]) if valore else None
        sezioni = match.select_one("section.match-graphs > div.card")
        if not sezioni:
            continue
        for classe, campo in (("suspendeds", "squalificato"), ("cautioneds", "diffidato"),
                              ("injureds", "infortunato"), ("dubts", "in_dubbio")):
            for sezione in sezioni.select(f"section.{classe}"):
                for li in sezione.select("li"):
                    a = li.select_one("a.player-link")
                    r = riga(a, None, partita) if a else None
                    if r is None:
                        continue
                    nota = li.select_one(".description")
                    nota = nota.get_text(" ", strip=True) if nota else None
                    if campo in ("diffidato", "in_dubbio"):
                        r[campo] = 1
                    else:
                        r["stato"] = campo
                        r["percentuale"] = 0.0
                    if nota:
                        r["nota"] = nota
    for r in righe.values():
        if r["stato"] is None:      # citato solo come diffidato o in dubbio, fuori dalla lista dei convocati
            r["stato"] = "non_convocato"
    return giornata, list(righe.values())
