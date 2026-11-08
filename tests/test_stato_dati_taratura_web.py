"""Stato dei dati, web: la riga della taratura di «gioca N%» con le probabili (PR C del piano 2026-11-06-gioca-probabili-server,
#379). Sotto i gruppi della carta «Quanto ci azzecca il modello», una frase sola per chi amministra: in attesa, attiva (con la prova),
non attiva (con il motivo), spenta a mano. I dati vengono dalla funzione vera del server (`taratura_probabili.riepilogo`, sulla
tabella `taratura_probabili` dell'archivio); la riga la scrive la funzione vera di `app.js`, eseguita con node. I numeri sono quelli
del server: la web li scrive con la virgola, non li ricalcola."""
import json
import re
import shutil
import subprocess

import pytest

from fanta import archivio, server
from fanta import taratura_probabili as tp

WEB = server.WEB
APP = (WEB / "app.js").read_text(encoding="utf-8")
TESTI_JS = (WEB / "testi.js").read_text(encoding="utf-8")
NODE = shutil.which("node")
ST = "2026-27"
COEFFICIENTI = {"titolare": [-1.0, 4.0], "panchina": [-2.5, 3.0], "dubbio": -0.5, "non_citato": 0.03}   # coerenti (`tp.coerente`)
PROVA = [[ST, 9], [ST, 10], [ST, 11], [ST, 12]]
# la prova di una versione: Brier 0,0912 della formula tarata contro 0,0968 dei numeri di partenza e 0,0975 dei mostrati,
# scarto (calibrazione) 0,0213 = 2,1 punti
MISURA = {"nuova": {"brier": 0.0912, "calibrazione": 0.0213}, "attuale": {"brier": 0.0968}, "mostrati": {"brier": 0.0975}}
# una versione attiva tornata ai numeri di partenza: nelle 2 giornate dopo la sua prova sbagliava di più
RITORNO = {**MISURA, "ritirata": {"quando": "2027-02-01T10:00:00"},
           "ritorno": {"giornate": [[ST, 13], [ST, 14]], "attiva": {"brier": 0.1041, "calibrazione": 0.061},
                       "partenza": {"brier": 0.0972}}}
TITOLO = "Taratura con le probabili"


def _riga(versione, creata, stato, motivo, misura=MISURA, prova=PROVA, coefficienti=COEFFICIENTI):
    return (versione, creata, stato, json.dumps(coefficienti), json.dumps(prova), json.dumps(misura) if misura else None, motivo)


def _riepilogo(tmp_path, monkeypatch, giornate: int, *righe) -> dict:
    """Il campo `calibrazione.taratura` di /api/stato-dati con le `righe` nella tabella `taratura_probabili` e `giornate` giornate
    del registro buone per la taratura."""
    monkeypatch.setattr(tp, "giornate", lambda r: [(ST, g) for g in range(1, giornate + 1)])
    db = archivio.apri(tmp_path / f"t{len(list(tmp_path.iterdir()))}.sqlite")
    try:
        db.executemany("INSERT INTO taratura_probabili (versione, creata, stato, coefficienti, prova, misura, motivo, avvisato) "
                       "VALUES (?, ?, ?, ?, ?, ?, ?, 1)", righe)
        db.commit()
        return json.loads(json.dumps(tp.riepilogo(db)))
    finally:
        db.close()


ATTIVA = _riga(1, "2027-01-15T10:00:00", "attiva", "migliora")


def _codice() -> str:
    """Le funzioni vere di app.js: `esc`, `num`, `regCifra` e il blocco della taratura (fino a «Stato dei dati»)."""
    esc = APP[APP.index("function esc(x)"):APP.index("\n}\n", APP.index("function esc(x)")) + 3]
    righe = [re.search(rf"^const {n} = .*$", APP, re.M).group(0) for n in ("num", "segno", "regCifra")]
    inizio = APP.index("// Taratura di «gioca N%»")
    blocco = APP[inizio:APP.index("// Stato dei dati: da dove arriva tutto", inizio)]
    return esc + "\n".join(righe) + "\n" + blocco


def _html(taratura, lingua="it") -> str:
    if NODE is None:
        pytest.skip("serve node")
    prova = TESTI_JS + f'\nLINGUA = "{lingua}";\n' + _codice() + f"\nconsole.log(JSON.stringify(rigaTaratura({json.dumps(taratura)})));"
    r = subprocess.run([NODE, "-"], input=prova, capture_output=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def _frase(taratura, lingua="it") -> str:
    """Il testo della riga (senza i tag), o "" se la web non ne mostra."""
    return " ".join(re.sub(r"<[^>]+>", " ", _html(taratura, lingua)).split())


def test_in_attesa_quante_giornate_su_quante(tmp_path, monkeypatch):
    assert _frase(_riepilogo(tmp_path, monkeypatch, 2)) == f"{TITOLO}: in attesa · 2 giornate su 4"
    assert _frase(_riepilogo(tmp_path, monkeypatch, 1)) == f"{TITOLO}: in attesa · 1 giornata su 4"
    assert _frase(_riepilogo(tmp_path, monkeypatch, 0)) == f"{TITOLO}: in attesa · 0 giornate su 4"


def test_in_attesa_con_le_giornate_gia_raggiunte(tmp_path, monkeypatch):
    """Riaccesa da poco, o giornate con poche righe: le giornate bastano ma il verdetto non c'è ancora. Niente «6 giornate su 4»."""
    riaccesa = _riga(2, "2027-01-20T10:00:00", "riaccesa", None, misura=None, prova=None, coefficienti=None)
    taratura = _riepilogo(tmp_path, monkeypatch, 6, _riga(1, "2027-01-10T10:00:00", "scartata", "non_migliora"), riaccesa)
    assert taratura["stato"] == "in_attesa"
    assert _frase(taratura) == f"{TITOLO}: in attesa · 6 giornate"


def test_attiva_con_la_prova(tmp_path, monkeypatch):
    taratura = _riepilogo(tmp_path, monkeypatch, 8, ATTIVA)
    assert (taratura["stato"], taratura["dal"], taratura["motivo"]) == ("attiva", "2027-01-15T10:00:00", None)
    assert _frase(taratura) == (f"{TITOLO}: attiva dal 15/1 (versione 1) · nelle ultime 4 giornate Brier 0,091 invece di 0,097, "
                                "scarto 2,1 punti")


def test_attiva_con_un_cambio_rimandato(tmp_path, monkeypatch):
    rimandata = _riga(2, "2027-02-06T10:00:00", "rimandata", "scadenza_vicina")
    taratura = _riepilogo(tmp_path, monkeypatch, 10, ATTIVA, rimandata)
    assert (taratura["stato"], taratura["motivo"]) == ("attiva", "scadenza_vicina")
    assert _frase(taratura) == (f"{TITOLO}: attiva dal 15/1 (versione 1) · nelle ultime 4 giornate Brier 0,091 invece di 0,097, "
                                "scarto 2,1 punti · cambio rimandato: la prima partita è tra meno di 24 ore")


def test_attiva_senza_numeri_della_prova_ne_data():
    taratura = {"stato": "attiva", "giornate": 8, "minimo": 4, "versione": 3, "dal": None, "prova": None, "motivo": None}
    assert _frase(taratura) == f"{TITOLO}: attiva (versione 3)"
    taratura = {**taratura, "dal": "2027-03-02T06:00:00",
                "prova": {"giornate": 1, "brier": None, "brier_prima": 0.1, "brier_mostrati": None, "calibrazione": None}}
    assert _frase(taratura) == f"{TITOLO}: attiva dal 2/3 (versione 3) · nell'ultima giornata Brier – invece di 0,100, scarto – punti"


def test_pronta_si_accende_con_8_giornate(tmp_path, monkeypatch):
    taratura = _riepilogo(tmp_path, monkeypatch, 5, _riga(1, "2026-12-10T10:00:00", "pronta", "poche_giornate"))
    assert (taratura["stato"], taratura["motivo"]) == ("non_attiva", "poche_giornate")
    assert _frase(taratura) == f"{TITOLO}: non attiva · la prova passa, si accende con 8 giornate (ora 5)"


def test_scartata_non_sbaglia_meno(tmp_path, monkeypatch):
    taratura = _riepilogo(tmp_path, monkeypatch, 6, _riga(1, "2026-12-10T10:00:00", "scartata", "non_migliora"))
    assert (taratura["stato"], taratura["motivo"]) == ("non_attiva", "non_migliora")
    assert _frase(taratura) == f"{TITOLO}: non attiva · non sbaglia meno dei numeri di partenza"


def test_ritirata_perche_peggiorata(tmp_path, monkeypatch):
    taratura = _riepilogo(tmp_path, monkeypatch, 14, _riga(1, "2027-01-15T10:00:00", "ritirata", "peggiorata", misura=RITORNO))
    assert (taratura["stato"], taratura["versione"], taratura["motivo"]) == ("non_attiva", 1, "peggiorata")
    assert _frase(taratura) == f"{TITOLO}: non attiva · tornata ai numeri di partenza: sbagliava di più nelle ultime giornate"


def test_spenta_a_mano(tmp_path, monkeypatch):
    spenta = _riga(2, "2027-02-02T10:00:00", "spenta", None, misura=None, prova=None, coefficienti=None)
    taratura = _riepilogo(tmp_path, monkeypatch, 14, _riga(1, "2027-01-15T10:00:00", "ritirata", "spenta_a_mano"), spenta)
    assert taratura["stato"] == "spenta"
    assert _frase(taratura) == f"{TITOLO}: spenta a mano"


@pytest.mark.parametrize(("motivo", "frase"), [
    ("non_migliora", "non sbaglia meno dei numeri di partenza"),
    ("poche_giornate", "la prova passa, si accende con 8 giornate (ora 7)"),
    ("fuori_soglia", "fuori dalle soglie di scarto o di Brier"),
    ("incoerente", "i numeri tarati non sono validi"),
    ("peggiorata", "tornata ai numeri di partenza: sbagliava di più nelle ultime giornate"),
    ("scadenza_vicina", "cambio rimandato: la prima partita è tra meno di 24 ore"),
    ("spenta_a_mano", "spenta a mano"),
])
def test_una_frase_per_ogni_motivo(motivo, frase):
    assert motivo in tp.MOTIVI
    taratura = {"stato": "non_attiva", "giornate": 7, "minimo": 4, "versione": 2, "dal": None, "prova": None, "motivo": motivo}
    assert _frase(taratura) == f"{TITOLO}: non attiva · {frase}"


def test_ogni_motivo_del_server_ha_la_sua_frase():
    frasi = {_frase({"stato": "non_attiva", "giornate": 7, "minimo": 4, "versione": 2, "dal": None, "prova": None, "motivo": m})
             for m in tp.MOTIVI}
    assert len(frasi) == len(tp.MOTIVI) and f"{TITOLO}: non attiva" not in frasi


def test_motivo_sconosciuto_o_assente_niente_codici():
    base = {"stato": "non_attiva", "giornate": 7, "minimo": 4, "versione": 2, "dal": None, "prova": None}
    assert _frase({**base, "motivo": "nuovo_motivo"}) == f"{TITOLO}: non attiva"
    assert _frase({**base, "motivo": None}) == f"{TITOLO}: non attiva"


def test_senza_campo_niente_riga():
    """Un server di prima della taratura (campo assente) o una taratura che non si legge (`null`): nessuna riga."""
    assert _frase(None) == ""
    assert _frase({"stato": "sconosciuto", "giornate": 1, "minimo": 4}) == ""


def test_versione_protetta():
    taratura = {"stato": "attiva", "giornate": 8, "minimo": 4, "versione": "<b>1</b>", "dal": "x", "prova": None, "motivo": None}
    frase = _frase(taratura)
    assert "<b>" not in frase and "&lt;b&gt;1&lt;/b&gt;" in frase and frase == f"{TITOLO}: attiva (versione &lt;b&gt;1&lt;/b&gt;)"
    for stato, motivo in (("in_attesa", None), ("non_attiva", "poche_giornate")):       # giornate: solo numeri, mai il testo ricevuto
        html = _html({"stato": stato, "giornate": "<i>5</i>", "minimo": "<i>4</i>", "versione": 1, "prova": None, "motivo": motivo})
        assert "<i>" not in html
    html = _html({**taratura, "versione": 1, "prova": {"giornate": "<i>4</i>", "brier": 0.1, "brier_prima": 0.1, "calibrazione": 0.02}})
    assert "<i>" not in html


@pytest.mark.parametrize("lingua", ["it", "en"])
def test_niente_chiavi_mancanti_ne_numeri_rotti(tmp_path, monkeypatch, lingua):
    stati = [_riepilogo(tmp_path, monkeypatch, 2), _riepilogo(tmp_path, monkeypatch, 8, ATTIVA),
             _riepilogo(tmp_path, monkeypatch, 5, _riga(1, "2026-12-10T10:00:00", "pronta", "poche_giornate")),
             _riepilogo(tmp_path, monkeypatch, 14, _riga(1, "2027-01-15T10:00:00", "ritirata", "peggiorata", misura=RITORNO)),
             {"stato": "spenta", "giornate": 3, "minimo": 4, "versione": None, "dal": None, "prova": None, "motivo": "spenta_a_mano"}]
    for taratura in stati:
        testo = _frase(taratura, lingua)
        assert testo and "sd.tar_" not in testo
        assert "undefined" not in testo and "NaN" not in testo and "null" not in testo and "[object" not in testo
    if lingua == "en":
        assert _frase(stati[1], "en").startswith("Calibration with the probable lineups: active since 15/1 (version 1)")


def test_la_pagina_mostra_la_riga_sotto_i_gruppi_della_calibrazione():
    corpo = APP[APP.index("async function apriStatoDati"):APP.index("// Aspetto: tema")]
    carta = corpo[corpo.index('t("scambio.quanto_azzecca_modello")'):]
    assert "${rigaTaratura(c.taratura)}" in carta
    assert carta.index("${gruppi}") < carta.index("${rigaTaratura(c.taratura)}")


def test_negli_aggiornamenti_la_riga_della_taratura_ha_un_nome():
    corpo = APP[APP.index("async function apriStatoDati"):APP.index("// Aspetto: tema")]
    assert f'"{tp.CHIAVE}": t("sd.f_taratura")' in corpo
    assert '"sd.f_taratura": "Taratura di «gioca N%»"' in TESTI_JS
