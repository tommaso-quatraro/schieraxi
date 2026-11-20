"""#797: con «Cambi consigliati» (`mercato`) spento per un utente, né «Da fare» di `GET /api/oggi` né `GET /api/widget` propongono
uno svincolato da prendere. Lo decide il server con la regola di `funzioni.acceso` (scelta dell'amministratore, ambiente,
predefinito, «Mostra tutte», ruolo), la stessa che blocca `GET /api/mercato`. Nessun campo cambia: si tolgono solo le voci.

La fixture `due_utenti` ha in cache un cambio con lo svincolato 40 (guadagno 3,2, fattibile) e nessuno scambio."""
import contextlib

import pytest

from fanta import account, calcolo, consigli, funzioni as fn
from test_token_widget import due_utenti, token_di, widget  # noqa: F401  (fixture)

SVINCOLATO = 40


def _svincolati_in_da_fare(chi, intestazioni=None) -> list[dict]:
    r = chi.get("/api/oggi", headers=intestazioni or {})
    assert r.status_code == 200, r.text
    return [v for v in r.json()["da_fare"] if v["tipo"] == "svincolato"]


def _widget(chi, intestazioni=None) -> dict:
    r = chi.get("/api/widget", headers=intestazioni or {})
    assert r.status_code == 200, r.text
    return r.json()


def _propone(chi, intestazioni=None) -> tuple[bool, bool]:
    """(«Da fare» propone lo svincolato, il widget lo propone)."""
    da_fare = any(v["entra"]["id"] == SVINCOLATO for v in _svincolati_in_da_fare(chi, intestazioni))
    w = _widget(chi, intestazioni)
    return da_fare, (w.get("svincolato") or {}).get("entra", {}).get("id") == SVINCOLATO


def _amministratore(nome: str) -> None:
    with contextlib.closing(account.apri()) as db:
        db.execute("UPDATE utenti SET ruolo = 'amministratore' WHERE nome_utente = ?", (nome,))
        db.commit()


# ---------------------------------------------------------------- acceso: come prima
def test_mercato_acceso_da_fare_e_widget_propongono_lo_svincolato(due_utenti):  # noqa: F811  (fixture)
    """Guardia: con la funzione accesa (predefinito nei test e scelta dell'amministratore) non cambia niente, con la sessione e
    con il token del widget."""
    a, _ = due_utenti
    c, h = widget(token_di(a))
    for scelta in (None, True):
        fn.imposta("mercato", scelta)
        assert _propone(a) == (True, True)
        assert _propone(c, h) == (True, True)
    v = _svincolati_in_da_fare(a)[0]
    assert v["esce"]["id"] == 5 and v["guadagno"] == 3.2
    w = _widget(c, h)
    assert w["svincolato"]["guadagno"] == 3.2 and w["mancano"] == ["scambio"]


# ---------------------------------------------------------------- spento: niente svincolati
def test_mercato_spento_niente_svincolati_ne_in_da_fare_ne_nel_widget(due_utenti):  # noqa: F811  (fixture)
    a, b = due_utenti
    c, h = widget(token_di(a))
    acceso = _widget(c, h)
    fn.imposta("mercato", False)
    for chi, intestazioni in ((a, None), (b, None), (c, h)):
        assert _propone(chi, intestazioni) == (False, False)
    spento = _widget(c, h)
    assert "svincolato" not in spento and spento["mancano"] == ["scambio"]          # non «manca»: la funzione è spenta
    assert set(acceso) - set(spento) == {"svincolato"}                              # gli altri campi restano tutti
    assert spento["formazione"] == acceso["formazione"] and spento["funzioni"] == acceso["funzioni"]


def test_mercato_spento_e_cache_vuota_lo_svincolato_non_va_in_mancano(due_utenti, monkeypatch):  # noqa: F811  (fixture)
    """Spento, il widget non chiede nemmeno il mercato: «svincolato» non finisce in `mancano` come se fosse da calcolare."""
    a, _ = due_utenti
    chiesto = []

    def mercato_non_pronto(*args, **kwargs):
        chiesto.append(1)
        raise calcolo.InCalcolo()
    monkeypatch.setattr(consigli, "mercato", mercato_non_pronto)
    c, h = widget(token_di(a))
    assert "svincolato" in _widget(c, h)["mancano"]                                 # acceso: manca perché non è in cache
    fn.imposta("mercato", False)
    chiesto.clear()
    assert _widget(c, h)["mancano"] == ["scambio"] and not _svincolati_in_da_fare(c, h)
    assert not chiesto                                                              # spento: il mercato non si legge


# ---------------------------------------------------------------- per utente: ruolo e «Mostra tutte»
def test_versione_pubblica_niente_svincolati_tranne_per_l_amministratore(due_utenti, monkeypatch):  # noqa: F811  (fixture)
    """Il server pubblico, senza scelte: `mercato` è spento di predefinito. L'utente normale non riceve svincolati; l'amministratore
    sì, come per `GET /api/mercato`, anche con il token del suo widget (il ruolo è suo, non della sessione)."""
    a, b = due_utenti
    monkeypatch.setattr(fn, "VERSIONE_PUBBLICA", True)
    assert fn.origine("mercato") == (False, "predefinito")
    _amministratore("anna")
    c, h = widget(token_di(a))
    assert _propone(b) == (False, False)
    assert _propone(a) == (True, True)
    assert _propone(c, h) == (True, True)
    assert a.get("/api/mercato").status_code != 404 and b.get("/api/mercato").status_code == 404     # stessa regola della rotta


def test_spento_dall_amministratore_mostra_tutte_lo_riapre_come_la_rotta(due_utenti):  # noqa: F811  (fixture)
    a, b = due_utenti
    c, h = widget(token_di(a))
    fn.imposta("mercato", False)
    assert a.put("/api/funzioni", json={"mostra_tutte": True}).status_code == 200
    assert _propone(a) == (True, True) and _propone(c, h) == (True, True)
    assert _propone(b) == (False, False)                                            # «Mostra tutte» è solo di anna


@pytest.mark.parametrize("scelta", [False, True])
def test_l_etag_del_widget_segue_l_interruttore(due_utenti, scelta):  # noqa: F811  (fixture)
    """Cambiando l'interruttore cambia l'ETag: il widget non resta con la copia di prima (304)."""
    a, _ = due_utenti
    c, h = widget(token_di(a))
    fn.imposta("mercato", not scelta)
    prima = c.get("/api/widget", headers=h).headers["etag"]
    fn.imposta("mercato", scelta)
    assert c.get("/api/widget", headers=h | {"If-None-Match": prima}).status_code == 200
