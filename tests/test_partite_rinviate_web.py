"""Oggi, «Partite del turno»: una partita rinviata ha l'etichetta «Rinviata» al posto dell'orario (collaudo del 2/11/2026)."""
from fanta import server
import codice_web

APP = codice_web.app()
CSS = (server.WEB / "stile.css").read_text(encoding="utf-8")
TESTI = codice_web.leggi("testi.js")


def test_etichetta_rinviata_nella_riga_della_partita():
    assert 'const rinviata = p.stato === "rinviata";' in APP
    assert 'const oraTesto = rinviata ? t("live.rinviata") : p.stato === "in_corso"' in APP
    assert '${rinviata ? "rinviata" : ""}' in APP
    assert ".partita.rinviata .ora" in CSS
    assert '"live.rinviata": "Rinviata"' in TESTI and '"live.rinviata": "Postponed"' in TESTI


def test_partita_cominciata_senza_diretta_dice_in_corso_non_l_ora():
    """Collaudo del 2/11: a 45 minuti dall'inizio, senza dati di diretta, la riga mostrava ancora «18:30». Lo stato viene dal
    server (fasi.stato_partita: calendario, diretta, poi orario)."""
    assert 'p.stato === "in_corso" ? t("oggi.partita_in_corso")' in APP
    assert ': p.stato === "finita" && !p.giocata ? t("live.finita") : ora ? fOra(ora) : "–";' in APP
    assert '"oggi.partita_in_corso": "In corso"' in TESTI and '"oggi.partita_in_corso": "In progress"' in TESTI
