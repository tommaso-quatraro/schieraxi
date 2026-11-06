"""Oggi web, collaudo del 2/11/2026: «I tuoi migliori» con una sola percentuale («gioca N%») e senza il numero dell'indice senza
etichetta sul volto; «Da fare» con il pulsante sotto il testo quando il riquadro è stretto e il testo con una larghezza massima."""
import re

from fanta import server

APP = (server.WEB / "app.js").read_text(encoding="utf-8")
CSS = (server.WEB / "stile.css").read_text(encoding="utf-8")
TESTI = (server.WEB / "testi.js").read_text(encoding="utf-8")


def test_una_sola_percentuale_nelle_righe_dei_giocatori():
    assert 'const MOTIVI_CON_PERCENTUALE = ["motivo.gol_atteso", "motivo.porta_inviolata"];' in APP
    assert "motiviUtili(x).filter(senzaPercentuale)" in APP
    assert r"!/\d\s*%/.test(m.testo)" in APP          # server vecchio senza le frasi: si riconosce dal testo


def test_migliori_senza_numero_sul_volto_e_numero_altrove_con_etichetta():
    assert "migliori.map(x => voceGiocatore({ ...x, indice: null }))" in APP
    assert 'class="badge-indice" title="${esc(t("comune.indice_aria"' in APP
    assert '"comune.indice_aria": "Indice {n} su 100' in TESTI and '"comune.indice_aria": "Index {n} of 100' in TESTI


def test_da_fare_pulsante_sotto_il_testo_nei_riquadri_stretti():
    """Nella colonna stretta l'azione va sotto il testo (accanto il testo andava su 4-5 righe); con la grafica B è testo nel colore
    delle azioni e resta a destra, dove sta nelle righe larghe (spec C9)."""
    assert ".df-carta { container-type: inline-size; }" in CSS
    blocco = re.search(r"@container \(max-width: 520px\) \{(.*?)\n\}", CSS, re.S)
    assert blocco and "grid-template-columns: minmax(0, 1fr);" in blocco.group(1) and ".df-azione { justify-self: end; }" in blocco.group(1)
    assert re.search(r"\.df-testo \{[^}]*max-width: 60ch", CSS)
