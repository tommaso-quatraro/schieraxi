"""Il campo `serve_promemoria` di GET /api/oggi (#710): dice se il promemoria della scadenza serve per la giornata di Oggi, con la
regola dei promemoria del server (`notifiche.promemoria`): tace solo con una scelta che si può schierare, spuntata «L'ho messa» e
senza titolari diventati indisponibili. L'iPhone programma con questo i suoi promemoria locali, anche in background: la spunta
messa o tolta dalla web (o caduta perché gli 11 sono cambiati) vale anche lì senza riaprire l'app.

Dal riallineamento dell'iPhone (#673) anche l'app ha la spunta: una scelta salvata dall'iPhone (`da: "app"`) senza la spunta riceve
il promemoria come una della web. Solo le scelte che non dicono da dove arrivano (salvate prima del 13/11) tacciono come prima.
Mai l'orologio vero: `adesso` è un argomento. Dati inventati e cartelle temporanee."""
import pytest

from fanta import notifiche, scelte, server
from fanta.regole import Regole

from test_promemoria_messa import CON_ZETA, ROSA_12, SCHIERATI, ST, UN_ORA, _mondo, _salvata
from test_promemoria_schierato import _db
from test_server import client  # noqa: F401 (fixture: un solo utente, senza account)


def _serve(tmp_path):
    return notifiche.serve_promemoria(_db(), Regole(), ROSA_12, ST, 9, tmp_path / "scelte.json")


def test_senza_scelta_serve(tmp_path, monkeypatch):
    _mondo(tmp_path, monkeypatch)
    assert _serve(tmp_path) is True


@pytest.mark.parametrize("da", ["web", "app"])
def test_serve_finche_la_formazione_non_e_segnata_come_messa(tmp_path, monkeypatch, da):
    _mondo(tmp_path, monkeypatch)
    _salvata(tmp_path, da=da)
    assert _serve(tmp_path) is True
    _salvata(tmp_path, da=da, messa=True)
    assert _serve(tmp_path) is False


def test_se_gli_11_cambiano_la_spunta_cade_e_serve_di_nuovo(tmp_path, monkeypatch):
    """Spunta messa dall'iPhone, poi dalla web cambia un titolare: la spunta cade e il promemoria serve di nuovo."""
    _mondo(tmp_path, monkeypatch)
    _salvata(tmp_path, da="app", messa=True)
    assert _serve(tmp_path) is False
    _salvata(tmp_path, CON_ZETA, da="web")
    assert _serve(tmp_path) is True


def test_con_la_spunta_serve_se_un_titolare_e_diventato_indisponibile(tmp_path, monkeypatch):
    _mondo(tmp_path, monkeypatch, stato="infortunato")
    _salvata(tmp_path, da="app", messa=True)
    assert _serve(tmp_path) is True


def test_con_la_spunta_serve_se_la_scelta_non_si_puo_piu_schierare(tmp_path, monkeypatch):
    _mondo(tmp_path, monkeypatch)
    _salvata(tmp_path, [*SCHIERATI[1:], 99], da="web", messa=True)          # 99 non è nella rosa: vale la consigliata
    assert _serve(tmp_path) is True


SCENARI = {
    "nessuna scelta": ({}, None),
    "web senza spunta": ({}, {"da": "web"}),
    "web con la spunta": ({}, {"da": "web", "messa": True}),
    "iPhone senza spunta": ({}, {"da": "app"}),
    "iPhone con la spunta": ({}, {"da": "app", "messa": True}),
    "scelta di prima": ({}, {}),
    "spunta e titolare infortunato": ({"stato": "infortunato"}, {"da": "app", "messa": True}),
    "spunta e scelta non valida": ({}, {"da": "web", "messa": True, "titolari": [*SCHIERATI[1:], 99]}),
}


@pytest.mark.parametrize("nome", SCENARI)
def test_il_campo_dice_quello_che_fa_il_promemoria_del_server(tmp_path, monkeypatch, nome):
    """Una regola sola: il campo vale vero esattamente quando il promemoria del server parte."""
    mondo, scelta = SCENARI[nome]
    promemoria, _ = _mondo(tmp_path, monkeypatch, **mondo)
    if scelta is not None:
        scelta = dict(scelta)
        _salvata(tmp_path, scelta.pop("titolari", SCHIERATI), **scelta)
    assert _serve(tmp_path) is bool(promemoria(UN_ORA))


# ---------------------------------------------------------------- la rotta
def test_oggi_ha_il_campo_con_le_scelte_di_chi_chiede(client, tmp_path, monkeypatch):  # noqa: F811
    """GET /api/oggi calcola il campo sulla giornata di Oggi e sulle scelte salvate di chi chiede."""
    _mondo(tmp_path, monkeypatch)
    monkeypatch.setattr(server, "_rose", lambda ctx: ROSA_12)
    monkeypatch.setattr(server.gestione, "oggi", lambda *a, **k: {"giornata": 9})
    monkeypatch.setattr(server.da_fare, "costruisci", lambda *a, **k: [])
    assert client.get("/api/oggi").json()["serve_promemoria"] is True
    scelte.salva(ST, 9, SCHIERATI, "4-4-2", scelte.FILE_SCELTE, da="app", messa=True)
    assert client.get("/api/oggi").json()["serve_promemoria"] is False
    scelte.salva(ST, 9, CON_ZETA, "4-4-2", scelte.FILE_SCELTE, da="web")       # dalla web cambia un titolare: la spunta cade
    assert client.get("/api/oggi").json()["serve_promemoria"] is True
