"""/api/widget senza il blocco `live` (27/11/2026). Nessun widget mostra più la diretta (tolta con #634): il blocco serviva solo
a far chiedere al widget una ricarica ogni 2 minuti durante le partite. In più il minuto e l'ora della raccolta entravano
nell'ETag, quindi ogni ricarica scaricava tutta la risposta (circa 18 kB) invece di un 304, e consumava le ricariche che iOS
concede al giorno. I risultati in diretta restano in GET /api/live. Le app già installate leggono `live` come facoltativo
(`RiassuntoWidget.live`, test Swift `testIlLiveMancanteOStranoNonRompe`): senza, tornano alle ricariche di 10-30 minuti."""
from fanta import server
from test_token_widget import due_utenti, token_di, widget  # noqa: F401  (fixture)


def _diretta(minuto: str, ora: str) -> dict:
    """La diretta come la dà `_risposta_live`, inventata: una partita in gioco, cambia solo il minuto (e l'ora della raccolta)."""
    return {"aggiornato_il": ora, "fonte": "espn", "in_corso": 1,
            "partite": [{"casa": "inter", "trasferta": "roma", "data": "2026-11-01 18:00", "stato": "primo_tempo", "minuto": minuto,
                         "gol_casa": 1, "gol_trasferta": 0, "eventi": []}]}


def test_il_widget_non_porta_la_diretta(due_utenti, monkeypatch):  # noqa: F811
    a, _ = due_utenti
    monkeypatch.setattr(server, "_risposta_live", lambda: _diretta("12'", "2026-11-01 18:13:04"))
    c, h = widget(token_di(a))
    r = c.get("/api/widget", headers=h)
    assert r.status_code == 200 and "live" not in r.json()
    assert c.get("/api/live", headers=h).json()["partite"][0]["minuto"] == "12'"     # la diretta resta nella sua rotta


def test_il_minuto_della_partita_non_cambia_l_etag(due_utenti, monkeypatch):  # noqa: F811
    """Due minuti dopo, con la partita che va avanti e niente altro di cambiato, il widget riceve 304."""
    a, _ = due_utenti
    c, h = widget(token_di(a))
    monkeypatch.setattr(server, "_risposta_live", lambda: _diretta("12'", "2026-11-01 18:13:04"))
    prima = c.get("/api/widget", headers=h)
    assert prima.status_code == 200
    monkeypatch.setattr(server, "_risposta_live", lambda: _diretta("14'", "2026-11-01 18:15:04"))
    assert c.get("/api/widget", headers=h | {"If-None-Match": prima.headers["etag"]}).status_code == 304
