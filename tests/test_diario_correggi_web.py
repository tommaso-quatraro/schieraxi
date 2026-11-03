"""Diario sul web: «Ho schierato un'altra formazione» / «Correggi a mano» come sull'iPhone (controlli statici su app.js e testi.js)."""
from fanta import server

APP = (server.WEB / "app.js").read_text(encoding="utf-8")
TESTI = (server.WEB / "testi.js").read_text(encoding="utf-8")


def test_ogni_giornata_ha_il_pulsante_per_correggere_a_mano():
    assert 'data-correggi="${idVoceDiario(g)}"' in APP           # stagione + giornata: prova di comportamento in test_diario_stagione_web.py
    assert 't("diario.correggi") : t("diario.ho_schierato_altra")' in APP
    assert '"diario.ho_schierato_altra": "Ho schierato un\'altra formazione"' in TESTI and '"diario.correggi": "Correggi a mano"' in TESTI


def test_l_editor_chiede_undici_titolari_e_manda_tipo_manuale():
    inizio = APP.index("async function correggiDiario(g)")
    corpo = APP[inizio:APP.index("// Prova del modello sulle ultime giornate giocate")]
    assert 'corpoSchierata(g, "manuale", titolari)' in corpo and "n !== 11" in corpo and "titolari.length !== 11" in corpo
    assert 'api("/api/rosa")' in corpo and "innerHTML" not in corpo                 # niente innerHTML diretto: i nomi passano da esc()
    assert "esc(x.nome)" in corpo
