"""#803: con «Scambi: trova» (`scambi_trova`) spento per un utente, né «Da fare» di `GET /api/oggi` né `GET /api/widget` propongono
uno scambio. Lo decide il server con la regola di `funzioni.acceso` (scelta dell'amministratore, ambiente, predefinito, «Mostra
tutte», ruolo), la stessa che blocca `GET /api/scambi/proposte`; `funzioni.scambi_trova` del widget segue la stessa regola, ruolo
compreso, così la risposta non si contraddice. Nessun campo cambia: si tolgono solo le proposte.

La fixture `con_scambio` mette in cache, sopra `due_utenti`, uno scambio con «Atletico Prova» che supera il buon senso: dai il 6
(continuo, non un titolare fisso), ricevi il 50 (fuori dalle previsioni finte: senza profilo le regole su chi entra non si
applicano), 4 punti in più sulle prossime 5 giornate, tutte in guadagno."""
import contextlib

import pytest

from fanta import account, calcolo, consigli, funzioni as fn, widget as modulo_widget
from test_token_widget import _previsioni_finte, due_utenti, token_di, widget  # noqa: F401  (fixture)

ALTRA = "Atletico Prova"
SCAMBIO = {"altra": ALTRA, "do": [{"id": 6, "nome": "g6", "ruolo": "C"}], "ricevo": [{"id": 50, "nome": "g50", "ruolo": "C"}],
           "guadagno_mio": 4.0, "breve_mio": 4.0, "per_giornata_mio": [1.0, 0.8, 0.9, 0.7, 0.6], "giornate": [10, 11, 12, 13, 14]}


@pytest.fixture
def con_scambio(due_utenti, monkeypatch):  # noqa: F811  (fixture)
    prev = _previsioni_finte()
    prev["p_lungo"] = 0.9                       # chi do è giocabile per l'altra squadra (regola (h) del buon senso)
    monkeypatch.setattr(consigli, "previsioni", lambda db, regole, *a: (prev, 9, True))
    monkeypatch.setattr(consigli, "proposte_scambi", lambda *a, **k: ({}, [dict(SCAMBIO)]))
    return due_utenti


def _scambi_in_da_fare(chi, intestazioni=None) -> list[dict]:
    r = chi.get("/api/oggi", headers=intestazioni or {})
    assert r.status_code == 200, r.text
    return [v for v in r.json()["da_fare"] if v["tipo"] == "scambio"]


def _widget(chi, intestazioni=None) -> dict:
    r = chi.get("/api/widget", headers=intestazioni or {})
    assert r.status_code == 200, r.text
    return r.json()


def _propone(chi, intestazioni=None) -> tuple[bool, bool]:
    """(«Da fare» propone lo scambio, il widget lo propone). Il widget non si contraddice: lo scambio c'è se e solo se la sua
    `funzioni.scambi_trova` è accesa."""
    da_fare = any(v["con"] == ALTRA for v in _scambi_in_da_fare(chi, intestazioni))
    w = _widget(chi, intestazioni)
    nel_widget = (w.get("scambio") or {}).get("altra") == ALTRA
    assert nel_widget == w["funzioni"]["scambi_trova"], w["funzioni"]
    return da_fare, nel_widget


def _amministratore(nome: str) -> None:
    with contextlib.closing(account.apri()) as db:
        db.execute("UPDATE utenti SET ruolo = 'amministratore' WHERE nome_utente = ?", (nome,))
        db.commit()


# ---------------------------------------------------------------- acceso: come prima
def test_scambi_accesi_da_fare_e_widget_propongono_lo_scambio(con_scambio):
    """Guardia: con la funzione accesa (predefinito nei test e scelta dell'amministratore) non cambia niente, con la sessione e
    con il token del widget."""
    a, _ = con_scambio
    c, h = widget(token_di(a))
    for scelta in (None, True):
        fn.imposta("scambi_trova", scelta)
        assert _propone(a) == (True, True)
        assert _propone(c, h) == (True, True)
    v = _scambi_in_da_fare(a)[0]
    assert v["guadagno"] == 4.0 and v["destinazione"]["scheda"] == "scambi"
    w = _widget(c, h)
    assert w["scambio"]["guadagno_mio"] == 4.0 and "mancano" not in w                 # scambio e svincolato in cache


# ---------------------------------------------------------------- spento: niente scambi
def test_scambi_spenti_niente_scambio_ne_in_da_fare_ne_nel_widget(con_scambio):
    a, b = con_scambio
    c, h = widget(token_di(a))
    acceso = _widget(c, h)
    fn.imposta("scambi_trova", False)
    for chi, intestazioni in ((a, None), (b, None), (c, h)):
        assert _propone(chi, intestazioni) == (False, False)
    spento = _widget(c, h)
    assert "scambio" not in spento and "scambio" not in spento.get("mancano", [])  # non «manca»: la funzione è spenta
    assert set(acceso) - set(spento) == {"scambio"}                                 # gli altri campi restano tutti
    assert spento["formazione"] == acceso["formazione"] and spento["svincolato"] == acceso["svincolato"]
    assert spento["funzioni"] == acceso["funzioni"] | {"scambi_trova": False}


def test_scambi_spenti_e_cache_vuota_lo_scambio_non_va_in_mancano(due_utenti, monkeypatch):  # noqa: F811  (fixture)
    """Spento, né il widget né «Da fare» chiedono le proposte: «scambio» non finisce in `mancano` come se fosse da calcolare."""
    a, _ = due_utenti
    chiesto = []

    def proposte_non_pronte(*args, **kwargs):
        chiesto.append(1)
        raise calcolo.InCalcolo()
    monkeypatch.setattr(consigli, "proposte_scambi", proposte_non_pronte)
    c, h = widget(token_di(a))
    assert "scambio" in _widget(c, h)["mancano"]                                    # acceso: manca perché non è in cache
    fn.imposta("scambi_trova", False)
    chiesto.clear()
    assert "scambio" not in _widget(c, h).get("mancano", []) and not _scambi_in_da_fare(c, h)
    assert not _scambi_in_da_fare(a)
    assert not chiesto                                                              # spento: le proposte non si leggono


# ---------------------------------------------------------------- per utente: ruolo e «Mostra tutte»
def test_versione_pubblica_niente_scambi_tranne_per_l_amministratore(con_scambio, monkeypatch):
    """Il server pubblico, senza scelte: `scambi_trova` è spento di predefinito. L'utente normale non riceve scambi;
    l'amministratore sì, come per `GET /api/scambi/proposte`, anche con il token del suo widget (il ruolo è suo, non della
    sessione), e `funzioni.scambi_trova` del suo widget lo dice."""
    a, b = con_scambio
    monkeypatch.setattr(fn, "VERSIONE_PUBBLICA", True)
    assert fn.origine("scambi_trova") == (False, "predefinito")
    _amministratore("anna")
    c, h = widget(token_di(a))
    assert _propone(b) == (False, False)
    assert _propone(a) == (True, True)
    assert _propone(c, h) == (True, True)
    assert a.get("/api/scambi/limite").status_code != 404 and b.get("/api/scambi/limite").status_code == 404   # stessa regola della rotta


def test_funzioni_del_widget_uguali_a_quelle_dell_app_anche_per_l_amministratore(con_scambio, monkeypatch):
    """`funzioni` del widget = `GET /api/funzioni` letta con la sessione dello stesso utente, per tutte le chiavi del widget:
    ruolo compreso (#803; prima il widget dell'amministratore le vedeva spente se spente solo di predefinito)."""
    a, b = con_scambio
    monkeypatch.setattr(fn, "VERSIONE_PUBBLICA", True)
    fn.imposta("diario", False)                                                     # spenta dall'amministratore: spenta per tutti
    _amministratore("anna")
    for chi in (a, b):
        app = chi.get("/api/funzioni").json()["funzioni"]
        c, h = widget(token_di(chi))
        w = _widget(c, h)["funzioni"]
        assert w == {k: app[k] for k in modulo_widget.FUNZIONI_WIDGET}
    assert _widget(*widget(token_di(a)))["funzioni"]["scambi_trova"] is True
    assert _widget(*widget(token_di(b)))["funzioni"]["scambi_trova"] is False


def test_spento_dall_amministratore_mostra_tutte_lo_riapre_come_la_rotta(con_scambio):
    a, b = con_scambio
    c, h = widget(token_di(a))
    fn.imposta("scambi_trova", False)
    assert a.put("/api/funzioni", json={"mostra_tutte": True}).status_code == 200
    assert _propone(a) == (True, True) and _propone(c, h) == (True, True)
    assert _propone(b) == (False, False)                                            # «Mostra tutte» è solo di anna


@pytest.mark.parametrize("scelta", [False, True])
def test_l_etag_del_widget_segue_l_interruttore(con_scambio, scelta):
    """Cambiando l'interruttore cambia l'ETag: il widget non resta con la copia di prima (304)."""
    a, _ = con_scambio
    c, h = widget(token_di(a))
    fn.imposta("scambi_trova", not scelta)
    prima = c.get("/api/widget", headers=h).headers["etag"]
    fn.imposta("scambi_trova", scelta)
    assert c.get("/api/widget", headers=h | {"If-None-Match": prima}).status_code == 200
