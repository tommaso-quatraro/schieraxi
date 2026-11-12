"""Interruttori delle funzioni: predefinito, ambiente, scelta dell'amministratore, «Mostra tutte» e rotte."""
import pytest
from fastapi.testclient import TestClient

from fanta import funzioni as fn
from fanta import server


def test_predefinito_privato_tutto_acceso_pubblico_dalla_tabella(monkeypatch):
    assert all(fn.acceso(k) == (k not in fn.SPENTE_DI_NORMA) for k in fn.FUNZIONI)
    assert fn.SPENTE_DI_NORMA == {"asta", "crediti"}
    assert all(fn.acceso(k) for k in ("diario", "live", "scambi_trova", "confronto", "backup"))
    assert fn.acceso("asta", amministratore=True) and fn.acceso("crediti", mostra_tutte=True)
    # «Sotto il cofano» è tolta: sempre spenta, anche per l'amministratore e con «Mostra tutte», e resta `false` nella risposta
    assert "sotto_il_cofano" not in fn.FUNZIONI and fn.RITIRATE == {"sotto_il_cofano"}
    assert not fn.acceso("sotto_il_cofano", mostra_tutte=True, amministratore=True)
    assert fn.per_utente(mostra_tutte=True, amministratore=True)["sotto_il_cofano"] is False
    fn.imposta("asta", False)                                  # la scelta dell'amministratore resta anche per lui
    assert not fn.acceso("asta", amministratore=True)
    fn.imposta("asta", None)
    monkeypatch.setattr(fn, "VERSIONE_PUBBLICA", True)
    assert {k for k in fn.FUNZIONI if fn.acceso(k)} == {"movimenti"}   # la tabella pubblica è spenta, tranne i movimenti della propria rosa
    assert fn.acceso("chiave_che_non_c_e")                     # fuori elenco = acceso
    assert fn.acceso("asta", mostra_tutte=True)
    assert not fn.acceso("live", mostra_tutte=True) and not fn.acceso("immagini_web", mostra_tutte=True)   # rete e diretta: mai riaperte


def test_movimenti_acceso_di_norma_e_bloccabile_dall_amministratore():
    assert "movimenti" in fn.FUNZIONI and fn.acceso("movimenti")
    assert fn.per_utente()["movimenti"] is True
    fn.imposta("movimenti", False)
    assert not fn.acceso("movimenti") and not fn.acceso("movimenti", amministratore=True)
    assert fn.acceso("movimenti", mostra_tutte=True)               # come le altre: «Mostra tutte» riapre solo i menu
    fn.imposta("movimenti", None)
    assert fn.acceso("movimenti")


def test_ambiente_e_amministratore(monkeypatch):
    monkeypatch.setenv("FANTA_FUNZIONE_ASTA", "0")
    assert not fn.acceso("asta") and fn.origine("asta") == (False, "ambiente")
    fn.imposta("asta", True)
    assert fn.origine("asta") == (True, "amministratore")
    fn.imposta("asta", None)
    assert fn.origine("asta")[1] == "ambiente"
    with pytest.raises(KeyError):
        fn.imposta("inventata", True)


def test_file_rovinato_o_con_chiavi_strane():
    fn.FILE.write_text("non è json", encoding="utf-8")
    assert fn.acceso("live")
    fn.FILE.write_text('{"live": "no", "inventata": false, "asta": false}', encoding="utf-8")
    assert fn.acceso("live") and not fn.acceso("asta")


def test_rotte_utente_e_admin(dati_isolati):
    c = TestClient(server.app, headers={"X-Fanta": "1"})
    r = c.get("/api/funzioni")
    assert r.status_code == 200 and r.json()["mostra_tutte"] is False and set(r.json()["funzioni"]) == set(fn.FUNZIONI) | fn.RITIRATE
    r = c.put("/api/admin/funzioni", json={"funzione": "asta", "acceso": False})
    assert r.status_code == 200 and [x for x in r.json()["funzioni"] if x["id"] == "asta"][0]["acceso"] is False
    assert c.put("/api/admin/funzioni", json={"funzione": "inventata", "acceso": True}).status_code == 400
    assert c.get("/api/funzioni").json()["funzioni"]["asta"] is False
    r = c.put("/api/funzioni", json={"mostra_tutte": True})
    assert r.json()["mostra_tutte"] is True and r.json()["funzioni"]["asta"] is True
    assert fn.acceso("live") and fn.acceso("immagini_web")      # (non spente dall'amministratore)
    assert c.get("/api/funzioni").json()["mostra_tutte"] is True
    assert c.put("/api/funzioni", json={"mostra_tutte": "boh"}).status_code == 422
    assert len(c.get("/api/admin/funzioni").json()["funzioni"]) == len(fn.FUNZIONI)


# ---------------------------------------------------------------- il server rispetta gli interruttori anche sulle rotte
ROTTE_BLOCCABILI = [("GET", "/api/live"), ("GET", "/api/asta"), ("GET", "/api/scambi/proposte"), ("GET", "/api/scambi/limite"),
                    ("GET", "/api/confronto?a=1&b=2")]
DA_URL = {"squadra": "x", "tipo": "stemma", "url": "https://esempio.it/a.png"}


def test_funzione_spenta_risponde_404_chiaro(dati_isolati):
    c = TestClient(server.app, headers={"X-Fanta": "1"})
    for f in ("live", "asta", "scambi_trova", "confronto", "immagini_web"):
        fn.imposta(f, False)
    for metodo, rotta in ROTTE_BLOCCABILI:
        r = c.request(metodo, rotta)
        assert r.status_code == 404 and r.json()["funzione"] in fn.FUNZIONI and "non è disponibile" in r.json()["detail"], (rotta, r.text)
        assert r.headers["cache-control"] == "no-store"
    r = c.post("/api/squadre/immagine/da-url", json=DA_URL)
    assert r.status_code == 404 and r.json()["funzione"] == "immagini_web"


def test_funzione_accesa_o_senza_rotte_proprie_come_prima(dati_isolati):
    c = TestClient(server.app, headers={"X-Fanta": "1"})
    assert c.get("/api/live").status_code == 200
    # funzioni spente ma senza rotte proprie: le rotte rispondono come sempre (mai 404 con il campo «funzione»)
    for f in ("scambi_costruisci", "seguiti", "diario", "backup", "squadre_altrui", "novita", "elenco_giocatori"):
        fn.imposta(f, False)
    for rotta in ("/api/scambi/analizza?con=x&do=1&ricevo=2", "/api/osservati", "/api/diario", "/api/backup", "/api/squadre", "/api/novita"):
        r = c.get(rotta)
        corpo = r.json() if r.headers.get("content-type", "").startswith("application/json") else None
        assert not (isinstance(corpo, dict) and "funzione" in corpo), rotta


def test_mostra_tutte_riapre_le_rotte(dati_isolati):
    c = TestClient(server.app, headers={"X-Fanta": "1"})
    fn.imposta("asta", False)
    assert c.get("/api/asta").status_code == 404
    c.put("/api/funzioni", json={"mostra_tutte": True})
    r = c.get("/api/asta")
    assert "funzione" not in r.json()
    c.put("/api/funzioni", json={"mostra_tutte": False})
    assert c.get("/api/asta").status_code == 404


def test_mostra_tutte_non_riapre_rete_e_diretta(dati_isolati):
    """Spente dall'amministratore, `live` e `immagini_web` restano bloccate per tutti: «Mostra tutte» vale solo per i menu."""
    c = TestClient(server.app, headers={"X-Fanta": "1"})
    for f in ("live", "immagini_web", "asta"):
        fn.imposta(f, False)
    assert c.get("/api/live").status_code == 404                      # prima 404
    r = c.put("/api/funzioni", json={"mostra_tutte": True})
    assert r.json()["funzioni"]["live"] is False and r.json()["funzioni"]["immagini_web"] is False
    assert r.json()["funzioni"]["asta"] is True                       # i menu si vedono
    r = c.get("/api/live")                                            # ... ma il server non apre
    assert r.status_code == 404 and r.json()["funzione"] == "live" and "non è disponibile" in r.json()["detail"]
    r = c.post("/api/squadre/immagine/da-url", json=DA_URL)
    assert r.status_code == 404 and r.json()["funzione"] == "immagini_web"
    fn.imposta("live", True)                                          # riaccesa dall'amministratore: poi 200
    assert c.get("/api/live").status_code == 200


def test_di_rotta():
    assert fn.di_rotta("GET", "/api/asta/") == "asta"
    assert fn.di_rotta("POST", "/api/asta") is None
    assert fn.di_rotta("GET", "/api/scambi/analizza") is None
    assert set(fn.ROTTE.values()) <= fn.CON_ROTTE


def test_due_utenti_ognuno_il_suo_mostra_tutte(multiutente, dati_isolati):
    import contextlib
    from fanta import account
    from test_account_http import cliente
    clienti = []
    for nome in ("utentea", "utenteb"):
        with contextlib.closing(account.apri()) as db:
            inv = account.crea_invito(db, nome)
        c = cliente()
        assert c.post("/api/account/registra", json={"nome_utente": nome, "password": "una-password-lunga-9", "invito": inv}).status_code == 200
        clienti.append(c)
    fn.imposta("live", False)
    a, b = clienti
    assert a.get("/api/live").status_code == 404 and b.get("/api/live").status_code == 404
    a.put("/api/funzioni", json={"mostra_tutte": True})
    assert a.get("/api/live").status_code == 404                  # «Mostra tutte» non riapre le rotte bloccate
    fn.imposta("live", True)
    assert a.get("/api/live").status_code == 200 and b.get("/api/live").status_code == 200


def test_fonti_ombra_spente_saltano_il_passo_di_misura(tmp_path, monkeypatch):
    from fanta import aggiorna, archivio

    class Finto(aggiorna.Aggiornamento):
        def __init__(self, db, righe):
            super().__init__(db, aggiorna.Stagione(2026), scrivi=righe.append)
            self.slug_noti = {"x"}
            self.eseguiti = []

        def listone(self): pass
        def calendario(self): pass
        def probabili(self): pass
        def voti(self, stagione=None): pass
        def understat(self, stagione=None, dettaglio_partite=True): pass
        def quotazioni(self, stagione): pass
        def dati_extra(self, stagione=None): self.eseguiti.append("extra")

    db = archivio.apri(tmp_path / "t.sqlite")
    try:
        righe = []
        a = Finto(db, righe)
        a.esegui()
        assert a.eseguiti == ["extra"]                           # acceso (privato): l'unica fonte in ombra, football-data
        assert not any("probabili" in r and "saltato" in r for r in righe)
        monkeypatch.setenv("FANTA_FUNZIONE_FONTI_OMBRA", "0")
        righe = []
        a = Finto(db, righe)
        a.esegui()
        assert a.eseguiti == [] and sum("saltato" in r for r in righe) == 1
    finally:
        db.close()
