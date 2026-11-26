"""«Da controllare» nel widget (26/11/2026): Oggi mette prima infortunati e squalificati, anche quelli fuori formazione, e /api/widget
manda solo i primi 6 avvisi. Il widget contava i titolari su quei 6: con tanti infortunati in panchina i dubbi dei titolari restavano
fuori e il numero era sbagliato. Ora il server mette i titolari prima del taglio e manda il conto in `da_controllare` (facoltativo:
le app già installate contano come prima, e con i titolari in testa contano meglio). Nomi inventati."""
from fanta import widget as w
from test_token_widget import OGGI, due_utenti, token_di, widget  # noqa: F401  (fixture)


def _avviso(i, tipo, in_formazione):
    return {"id": i, "nome": f"Giocatore{i}", "ruolo": "C", "squadra": "XXX", "tipo": tipo, "in_formazione": in_formazione,
            "etichetta": {"codice": tipo, "testo": tipo.capitalize(), "tono": "attenzione"}}


# nell'ordine di Oggi (gestione.oggi): prima infortunati e squalificati (anche fuori formazione), poi i dubbi, i diffidati titolari,
# in fondo i diffidati in panchina
AVVISI_DI_OGGI = ([_avviso(i, "infortunato", False) for i in range(20, 25)]
                  + [_avviso(30, "infortunato", True), _avviso(31, "squalificato", False), _avviso(32, "squalificato", False)]
                  + [_avviso(40, "dubbio", True), _avviso(41, "dubbio", True), _avviso(50, "diffidato", True), _avviso(51, "diffidato", False)])


def _widget(due_utenti, monkeypatch, avvisi) -> dict:  # noqa: F811
    a, _ = due_utenti
    monkeypatch.setattr(w.gestione, "oggi", lambda *x, **k: OGGI | {"avvisi": avvisi})
    c, h = widget(token_di(a))
    r = c.get("/api/widget", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def test_i_titolari_prima_del_taglio_e_il_conto_dal_server(due_utenti, monkeypatch):  # noqa: F811
    corpo = _widget(due_utenti, monkeypatch, AVVISI_DI_OGGI)
    avvisi = corpo["avvisi"]
    assert len(avvisi) == w.MAX_AVVISI
    titolari = [a["id"] for a in avvisi if a["in_formazione"]]
    assert titolari == [30, 40, 41, 50], "tutti i titolari con un avviso, nell'ordine di Oggi"
    assert [a["id"] for a in avvisi[:4]] == titolari, "prima i titolari, poi gli altri"
    assert [a["id"] for a in avvisi[4:]] == [20, 21], "dopo, gli altri nell'ordine di Oggi"
    assert corpo["da_controllare"] == 4


def test_il_conto_vale_anche_oltre_il_taglio(due_utenti, monkeypatch):  # noqa: F811
    titolari = [_avviso(60 + i, "dubbio", True) for i in range(8)]
    corpo = _widget(due_utenti, monkeypatch, [_avviso(20, "infortunato", False)] + titolari)
    assert len(corpo["avvisi"]) == w.MAX_AVVISI and all(a["in_formazione"] for a in corpo["avvisi"])
    assert corpo["da_controllare"] == 8, "il numero dei titolari da controllare, anche quelli che non entrano nei 6"


def test_senza_avvisi_il_conto_e_zero(due_utenti, monkeypatch):  # noqa: F811
    corpo = _widget(due_utenti, monkeypatch, [_avviso(20, "infortunato", False), _avviso(51, "diffidato", False)])
    assert [a["id"] for a in corpo["avvisi"]] == [20, 51]
    assert corpo["da_controllare"] == 0
