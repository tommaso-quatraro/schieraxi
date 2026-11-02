"""Oggi, «Partite del turno»: una partita rinviata ha l'etichetta «Rinviata» al posto dell'orario (collaudo del 2/11/2026)."""
from fanta import server

APP = (server.WEB / "app.js").read_text(encoding="utf-8")
CSS = (server.WEB / "stile.css").read_text(encoding="utf-8")
TESTI = (server.WEB / "testi.js").read_text(encoding="utf-8")


def test_etichetta_rinviata_nella_riga_della_partita():
    assert 'const rinviata = p.stato === "rinviata";' in APP
    assert 'const oraTesto = rinviata ? t("live.rinviata") : ora ? fOra(ora) : "–";' in APP
    assert '${rinviata ? "rinviata" : ""}' in APP
    assert ".partita.rinviata .ora" in CSS
    assert '"live.rinviata": "Rinviata"' in TESTI and '"live.rinviata": "Postponed"' in TESTI
