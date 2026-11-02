"""Token del widget iOS: uno per utente, solo hash, 90 giorni, vale SOLO per leggere /api/oggi e /api/widget."""
import contextlib
import re
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from fanta import account, server
from test_account_http import PASSWORD, cliente, registra

OGGI = {"giornata": 9, "giornata_lega": 6, "inizio": "2026-11-01 18:00", "ore_mancanti": 30.0, "iniziata": False, "con_probabili": True,
        "formazione": {"modulo": "3-4-3", "punteggio_atteso": 71.5, "squadra": "Real Esempio"},
        "avvisi": [{"id": 2, "nome": "Sommer", "ruolo": "P", "squadra": "INT", "tipo": "dubbio", "p_voto": 0.6, "in_formazione": True}],
        "migliori": [], "partite": [{"data": "2026-11-01 18:00", "casa": "A", "trasferta": "B", "giocata": False}]}


def _scheda(i, **extra):  # squadra: come nelle schede vere
    return {"id": i, "nome": f"g{i}", "ruolo": "C", "squadra": "inter", "avversario": "XXX", "in_casa": True, "data_partita": "2026-11-01 18:00",
            "stato": "titolare", "percentuale": 90.0, "dubbio": False, "diffidato": i == 3, "punti_attesi": 6.0, "p_voto": 0.9,
            "voto_atteso": 6.2, "rigori_attesi": 0.3 if i == 1 else 0.0} | extra


@pytest.fixture
def due_utenti(multiutente, dati_isolati, monkeypatch):
    from types import SimpleNamespace as NS
    import pandas as pd
    from fanta import calcolo, consigli, widget as w
    def nuovo_db():
        db = sqlite3.connect(":memory:")
        db.execute("CREATE TABLE aggiornamenti (quando TEXT, cosa TEXT, dettaglio TEXT)")
        db.execute("INSERT INTO aggiornamenti VALUES ('2026-10-30T10:00:00', 'aggiornamento', '')")
        return db
    monkeypatch.setattr(server, "_db", nuovo_db)
    squadra = NS(nome="Real Esempio", crediti_residui=12, giocatori=[NS(id=i) for i in range(1, 15)])
    monkeypatch.setattr(server, "_rose", lambda ctx: NS(mia_squadra="Real Esempio", squadra=lambda n: squadra))
    monkeypatch.setattr(server, "_regole", lambda ctx: object())
    monkeypatch.setattr(w.gestione, "oggi", lambda db, regole, rose, *a, **k: OGGI)
    monkeypatch.setattr(w.consigli, "formazione", lambda db, regole, rose, *a, **k: {
        "squadra": "Real Esempio", "modulo": "3-4-3", "punteggio_atteso": 71.5,
        "titolari": [_scheda(i) for i in range(1, 12)], "panchina": [_scheda(i) for i in range(12, 15)]})
    monkeypatch.setattr(w.consigli, "previsioni", lambda db, regole, *a: (pd.DataFrame(index=list(range(1, 15))), 9, True))
    monkeypatch.setattr(w.consigli, "scheda_previsione", lambda i, x: _scheda(i))
    monkeypatch.setattr(w.avatar, "tutti", lambda: {1: {"carnagione": 2}})
    monkeypatch.setattr(w.consigli, "proposte_scambi", lambda *a, **k: (_ for _ in ()).throw(calcolo.InCalcolo()))
    monkeypatch.setattr(w.consigli, "mercato", lambda *a, **k: {"proposte": [
        {"esce": {"id": 5, "nome": "g5", "ruolo": "C"}, "entra": {"id": 40, "nome": "g40", "ruolo": "C", "quotazione": 9},
         "guadagno": 3.2, "fattibile": True}]})
    a, b = cliente(), cliente()
    assert registra(a, "anna").status_code == 200
    assert registra(b, "bruno").status_code == 200
    return a, b


def widget(token, **extra):
    return cliente(**extra), {"Authorization": f"Bearer {token}"}


def token_di(c) -> str:
    r = c.post("/api/account/token-widget")
    assert r.status_code == 200, r.text
    return r.json()["token"]


def test_creazione_stato_e_solo_hash(due_utenti):
    a, _ = due_utenti
    assert a.get("/api/account/token-widget").json() == {"presente": False}
    r = a.post("/api/account/token-widget").json()
    assert re.fullmatch(r"fw_[A-Za-z0-9_-]{43}", r["token"]) and r["etichetta"] == "widget"        # 256 bit
    scade = datetime.fromisoformat(r["scade"])
    assert timedelta(days=89) < scade - datetime.now(timezone.utc) <= timedelta(days=90)
    s = a.get("/api/account/token-widget").json()
    assert s["presente"] and s["valido"] and r["token"] not in str(s) and "token" not in s
    with contextlib.closing(account.apri()) as db:
        tutto = " ".join(str(tuple(x)) for x in db.execute("SELECT * FROM token_widget"))
    assert r["token"] not in tutto and account._hash_token(r["token"]) in tutto


def test_rigenerare_revoca_il_precedente_e_ne_resta_uno_solo(due_utenti):
    a, _ = due_utenti
    vecchio, nuovo = token_di(a), token_di(a)
    assert vecchio != nuovo
    c, h = widget(vecchio)
    assert c.get("/api/oggi", headers=h).status_code == 401
    c, h = widget(nuovo)
    assert c.get("/api/oggi", headers=h).status_code == 200
    with contextlib.closing(account.apri()) as db:
        assert db.execute("SELECT COUNT(*) FROM token_widget").fetchone()[0] == 1


def test_il_token_legge_oggi_e_widget(due_utenti):
    from fanta import widget as modulo_widget  # noqa: F401
    a, _ = due_utenti
    c, h = widget(token_di(a))
    assert c.get("/api/oggi", headers=h).json()["giornata"] == 9
    w = c.get("/api/widget", headers=h)
    assert w.status_code == 200
    corpo = w.json()
    assert corpo["formazione"]["modulo"] == "3-4-3" and corpo["formazione"]["punti_attesi"] == 71.5 and corpo["giornata"] == 9
    assert corpo["giornata_lega"] == 6      # facoltativo: senza regola o fuori lega vale null
    assert len(corpo["formazione"]["titolari"]) == 11 and corpo["formazione"]["titolari"][0]["avatar"] == {"carnagione": 2}
    assert corpo["avvisi"][0]["tipo"] == "dubbio" and corpo["avvisi"][0]["id"] == 2
    assert corpo["crediti_residui"] == 12 and corpo["rigoristi"] == [1] and corpo["diffidati"] == [3] and corpo["scadenza"] == "2026-11-01 18:00"
    assert corpo["svincolato"]["entra"]["id"] == 40 and "scambio" not in corpo and corpo["mancano"] == ["scambio"]    # in cache solo lo svincolato
    assert corpo["formazione"]["titolari"][0]["squadra"] == "inter" and corpo["rosa"][0]["squadra"] == "inter"     # il club, per evidenziare le partite
    assert "capitano" not in corpo and "classifica" not in corpo
    assert len(w.content) < 20_000
    # ETag: se non è cambiato niente, 304 senza corpo
    r2 = c.get("/api/widget", headers=h | {"If-None-Match": w.headers["etag"]})
    assert r2.status_code == 304 and not r2.content and r2.headers["cache-control"] == "private, no-cache"


def test_il_widget_non_fa_partire_calcoli(due_utenti, monkeypatch):
    """Con il token del widget un risultato non in cache non si calcola: 202, e la funzione di calcolo non parte mai."""
    from fanta import calcolo
    a, _ = due_utenti
    partito = []
    monkeypatch.setattr(server.gestione, "oggi", lambda *x, **k: calcolo.ottieni(("prova-widget",), lambda d: partito.append(1), None))
    c, h = widget(token_di(a))
    r = c.get("/api/oggi", headers=h)
    assert r.status_code == 202 and r.json()["calcolo"] == "in_corso" and not partito
    monkeypatch.setattr(server.widget_riassunto.gestione, "oggi", lambda *x, **k: calcolo.ottieni(("prova-widget",), lambda d: partito.append(1), None))
    assert c.get("/api/widget", headers=h).status_code == 202 and not partito


@pytest.mark.parametrize("metodo,rotta", [
    ("GET", "/api/rosa"), ("GET", "/api/regole"), ("GET", "/api/backup"), ("GET", "/api/account/me"), ("GET", "/api/account/token-widget"),
    ("POST", "/api/account/token-widget"), ("DELETE", "/api/account/token-widget"), ("POST", "/api/account/cambia-password"),
    ("POST", "/api/account/accedi"), ("POST", "/api/account/elimina"), ("POST", "/api/account/esci-da-tutti"),
    ("POST", "/api/oggi"), ("PUT", "/api/widget"), ("DELETE", "/api/oggi"), ("GET", "/api/admin/utenti"), ("POST", "/api/aggiorna"),
    ("GET", "/api/formazione"), ("GET", "/api/sotto-il-cofano"), ("PUT", "/api/mia-squadra"), ("GET", "/api/avatar"), ("GET", "/api/oggi/altro"), ("GET", "/api/widgetx"),
])
def test_ogni_altra_rotta_o_metodo_e_403(due_utenti, metodo, rotta):
    a, _ = due_utenti
    c, h = widget(token_di(a))
    r = c.request(metodo, rotta, headers=h, json={} if metodo != "GET" else None)
    assert r.status_code == 403, (metodo, rotta, r.status_code, r.text)
    # e non ha fatto niente: il token e la sessione di Anna funzionano ancora
    assert a.get("/api/account/me").status_code == 200 and a.get("/api/account/token-widget").json()["presente"]


def test_il_token_non_e_una_sessione_ne_un_cookie(due_utenti):
    a, _ = due_utenti
    t = token_di(a)
    senza_header = cliente()
    senza_header.cookies.set("fanta_sessione", t)
    assert senza_header.get("/api/oggi").status_code == 401            # nel cookie non vale
    assert cliente().get("/api/oggi", params={"token": t}).status_code == 401      # nemmeno nell'indirizzo
    assert cliente().get("/api/oggi", headers={"Authorization": t}).status_code == 401       # serve la parola Bearer


def test_scaduto_e_revocato(due_utenti):
    a, _ = due_utenti
    t = token_di(a)
    c, h = widget(t)
    with contextlib.closing(account.apri()) as db:
        db.execute("UPDATE token_widget SET scade = ?", (account._testo(datetime.now(timezone.utc) - timedelta(seconds=1)),))
        db.commit()
        assert account.utente_da_token_widget(db, t) is None
    assert c.get("/api/oggi", headers=h).status_code == 401
    assert a.get("/api/account/token-widget").json()["valido"] is False
    t2 = token_di(a)
    c, h = widget(t2)
    assert c.get("/api/oggi", headers=h).status_code == 200
    assert a.delete("/api/account/token-widget").json() == {"revocato": True}
    assert c.get("/api/oggi", headers=h).status_code == 401
    assert a.get("/api/account/token-widget").json() == {"presente": False}
    assert a.delete("/api/account/token-widget").json() == {"revocato": False}


def test_scadenza_a_novanta_giorni_precisa(multiutente, dati_isolati):
    with contextlib.closing(account.apri()) as db:
        db.execute("INSERT INTO utenti (nome_utente, password_hash, recupero_hash, creato) VALUES ('x', 'h', 'r', '2026-01-01T00:00:00')")
        db.commit()
        adesso = datetime(2026, 1, 1, tzinfo=timezone.utc)
        t, _ = account.crea_token_widget(db, 1, adesso)
        assert account.utente_da_token_widget(db, t, adesso + timedelta(days=89, hours=23)) is not None
        assert account.utente_da_token_widget(db, t, adesso + timedelta(days=90, seconds=1)) is None


@pytest.mark.parametrize("brutto", ["", "fw_", "fw_corto", "fw_" + "a" * 42, "fw_" + "a" * 44, "fw_" + "a" * 42 + "!", "FW_" + "a" * 43,
                                    "fw_" + "a" * 43 + "\n", "fw_' OR 1=1 --", "fw_" + "a" * 5000, "bearer fw_x", "fw_é" + "a" * 42])
def test_formati_sbagliati(due_utenti, brutto):
    a, _ = due_utenti
    token_di(a)
    with contextlib.closing(account.apri()) as db:
        assert account.utente_da_token_widget(db, brutto) is None
    try:
        r = cliente().get("/api/oggi", headers={"Authorization": f"Bearer {brutto}"})
    except UnicodeEncodeError:
        return                                          # intestazioni non ASCII: non arrivano nemmeno al server
    assert r.status_code == 401


def test_il_token_e_dell_utente_che_l_ha_creato(due_utenti):
    a, b = due_utenti
    ta, tb = token_di(a), token_di(b)
    with contextlib.closing(account.apri()) as db:
        assert account.utente_da_token_widget(db, ta).nome_utente == "anna"
        assert account.utente_da_token_widget(db, tb).nome_utente == "bruno"
    # Bruno non vede il token di Anna e non può revocarlo: le rotte guardano solo la sua sessione
    assert b.delete("/api/account/token-widget").json() == {"revocato": True}
    c, h = widget(ta)
    assert c.get("/api/oggi", headers=h).status_code == 200
    assert a.get("/api/account/token-widget").json()["presente"]
    # un parametro non cambia di chi sono i dati
    assert c.get("/api/oggi", headers=h, params={"utente": 2, "utente_id": 2}).status_code == 200


def test_senza_sessione_non_si_crea_ne_si_legge(due_utenti):
    assert cliente().post("/api/account/token-widget").status_code == 401
    assert cliente().get("/api/account/token-widget").status_code == 401
    assert cliente().delete("/api/account/token-widget").status_code == 401


def test_protezione_x_fanta_sulle_scritture(due_utenti):
    a, _ = due_utenti
    senza = cliente()
    senza.cookies.update(a.cookies)
    del senza.headers["X-Fanta"]
    assert senza.post("/api/account/token-widget").status_code == 403
    assert senza.delete("/api/account/token-widget").status_code == 403
    assert a.get("/api/account/token-widget").json() == {"presente": False}


def test_cambio_password_ed_esci_da_tutti_chiudono_il_widget(due_utenti):
    a, _ = due_utenti
    t = token_di(a)
    assert a.post("/api/account/esci-da-tutti").status_code == 200
    c, h = widget(t)
    assert c.get("/api/oggi", headers=h).status_code == 401
    with contextlib.closing(account.apri()) as db:
        assert db.execute("SELECT COUNT(*) FROM token_widget").fetchone()[0] == 0


def test_eliminare_l_account_toglie_il_token(due_utenti):
    a, _ = due_utenti
    t = token_di(a)
    assert a.post("/api/account/elimina", json={"password": PASSWORD}).status_code == 200
    c, h = widget(t)
    assert c.get("/api/oggi", headers=h).status_code == 401


def test_limiti_di_frequenza(due_utenti, monkeypatch):
    a, _ = due_utenti
    for _ in range(10):
        assert a.post("/api/account/token-widget").status_code == 200
    r = a.post("/api/account/token-widget")
    assert r.status_code == 429 and int(r.headers["retry-after"]) >= 1
    monkeypatch.setattr("fanta.rotte_account.LETTURE_WIDGET_ALL_ORA", (3, account.ORA))
    with contextlib.closing(account.apri()) as db:
        nuovo, _ = account.crea_token_widget(db, 1)
    c, h = widget(nuovo)
    assert [c.get("/api/oggi", headers=h).status_code for _ in range(4)] == [200, 200, 200, 429]


def test_il_token_legge_anche_i_risultati_live(due_utenti):
    """/api/live è in sola lettura e comune a tutti; /api/widget ne porta una copia piccola (anche con l'archivio ancora vuoto)."""
    a, b = due_utenti
    c, h = widget(token_di(a))
    r = c.get("/api/live", headers=h)
    assert r.status_code == 200 and r.json()["partite"] == [] and "etag" in r.headers
    assert c.get("/api/widget", headers=h).json()["live"]["partite"] == []
    assert c.post("/api/live", headers=h | {"X-Fanta": "1"}).status_code == 403
    assert b.get("/api/live").status_code == 200                       # con la sessione, come ogni utente
    assert cliente().get("/api/live").status_code == 401               # senza accesso no


def test_migrazione_non_distruttiva(multiutente, dati_isolati):
    with contextlib.closing(account.apri()) as db:
        assert db.execute("SELECT name FROM sqlite_master WHERE name = 'token_widget'").fetchone()
        assert db.execute("PRAGMA user_version").fetchone()[0] == len(account.MIGRAZIONI)


def test_cache_del_telefono_non_mescola_gli_account(due_utenti):
    """Attacco: una cache condivisa (o dello stesso telefono con due account) serve a bruno la risposta di anna. Le risposte
    per persona sono «private, no-cache» e variano per Authorization e Cookie, con il token e con la sessione, anche in 304."""
    a, b = due_utenti
    c, h = widget(token_di(a))
    for chi, intest in ((c, h), (a, {}), (b, {})):
        for percorso in ("/api/oggi", "/api/widget"):
            r = chi.get(percorso, headers=intest)
            assert r.status_code == 200
            assert r.headers["cache-control"] == "private, no-cache", (percorso, r.headers["cache-control"])
            assert {x.strip() for x in r.headers["vary"].split(",")} >= {"Authorization", "Cookie"}
            assert "public" not in r.headers["cache-control"] and "max-age" not in r.headers["cache-control"]
    r304 = c.get("/api/widget", headers=h | {"If-None-Match": c.get("/api/widget", headers=h).headers["etag"]})
    assert r304.status_code == 304 and "Cookie" in r304.headers["vary"]


def test_il_token_di_un_admin_non_vede_le_voci_riservate_all_admin(due_utenti, monkeypatch):
    from fanta import da_fare
    a, _ = due_utenti
    visti = []
    monkeypatch.setattr(da_fare, "costruisci", lambda *args, **kw: visti.append(kw.get("amministratore")) or [])
    with contextlib.closing(account.apri()) as db:
        db.execute("UPDATE utenti SET ruolo = 'amministratore'")
        db.commit()
    c, h = widget(token_di(a))
    assert c.get("/api/oggi", headers=h).status_code == 200
    assert visti == [False]


def test_widget_porta_lo_stato_delle_funzioni(due_utenti, monkeypatch, tmp_path):
    """`funzioni` nel widget: solo quelle dei widget, con le scelte dell'amministratore; l'ETag cambia; le altre rotte restano 403."""
    from fanta import funzioni
    monkeypatch.setattr(funzioni, "FILE", tmp_path / "funzioni.json")
    a, _ = due_utenti
    c, h = widget(token_di(a))
    w = c.get("/api/widget", headers=h)
    f = w.json()["funzioni"]
    assert set(f) == {"live", "diario", "scambi_trova", "seguiti", "widget_extra"} and all(f.values())
    funzioni.imposta("diario", False)
    w2 = c.get("/api/widget", headers=h)
    assert w2.json()["funzioni"]["diario"] is False and w2.headers["etag"] != w.headers["etag"]
    assert c.get("/api/widget", headers=h | {"If-None-Match": w2.headers["etag"]}).status_code == 304
    assert c.get("/api/funzioni", headers=h).status_code == 403
    assert c.put("/api/funzioni", headers=h, json={"mostra_tutte": True}).status_code == 403
