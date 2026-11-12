"""Stato dei dati, web: il registro delle giornate (#344). Per ogni misura la media, la soglia e «regge» / «non regge» /
«servono ancora N giornate»; poi le giornate perse con il motivo. I dati vengono dalle funzioni vere del server
(`registro_giornate.registra_misura` e `riepilogo`); la carta la disegna la funzione vera di `app.js`, eseguita con node."""
import json
import re
import shutil
import subprocess
from datetime import datetime

import pytest

from fanta import archivio, registro_giornate, server
import codice_web

WEB = server.WEB
APP = codice_web.app()
TESTI_JS = codice_web.leggi("testi.js")
NODE = shutil.which("node")
ST = "2026-27"
# una giornata misurata (come in test_stato_dati): errore del fantavoto atteso 1,00 contro 1,06 della fantamedia (−5,7%), Brier 0,100,
# scarto di 10 punti tra «gioca N%» e chi ha giocato, punti veri dentro la fascia 16 volte su 20 (80%)
MISURA = {"voti": 2, "sq_modello": 2.0, "sq_fantamedia": 2.25, "presenze": 4, "brier_somma": 0.4,
          "fasce": [[2, 0.3, 0]] + [[0, 0.0, 0]] * 8 + [[2, 1.9, 2]], "fascia_casi": 20, "fascia_dentro": 16}
I1 = "Errore del fantavoto atteso contro la fantamedia avvicinata alla media del ruolo"      # l'avversario onesto di #614
I2 = "«Gioca N%» contro chi ha giocato davvero"
I3 = "Punti veri dentro la fascia «8 volte su 10»"
PERSA = {9: registro_giornate.SENZA_TENTATIVI}
# la stessa risposta per i test dell'iPhone (ModelliTests, RegistroGiornateTests): 8 giornate misurate e la 9 persa
FIXTURE_IOS = server.WEB.parent.parent / "ios" / "Tests" / "Fixtures" / "stato-dati-registro.json"


def _registro(tmp_path, misurate: int, perse: dict | None = None) -> dict:
    """Il campo `registro` di /api/stato-dati con `misurate` giornate misurate e le giornate `perse` ({giornata: motivo})."""
    db = archivio.apri(tmp_path / f"r{misurate}.sqlite")
    for g in range(1, misurate + 1):
        db.execute("INSERT INTO registro_giornate (stagione, giornata, salvato, giocatori, con_probabili) VALUES (?, ?, ?, 600, 1)",
                   (ST, g, "2026-09-01T18:20:00"))
        registro_giornate.registra_misura(db, ST, g, MISURA, datetime(2026, 9, 2, 12))
    for g, motivo in (perse or {}).items():
        db.execute("INSERT INTO registro_giornate (stagione, giornata, giocatori, con_probabili, persa, da_avvisare, avvisati) "
                   "VALUES (?, ?, 0, 0, ?, '[]', '[]')", (ST, g, motivo))
    db.commit()
    try:
        return json.loads(json.dumps(registro_giornate.riepilogo(db)))
    finally:
        db.close()


def _codice_registro() -> str:
    """Le funzioni vere di app.js: `esc`, `nomeGiornata`, `num`, `segno` e il blocco del registro (fino a «Stato dei dati»)."""
    esc = APP[APP.index("function esc(x)"):APP.index("\n}\n", APP.index("function esc(x)")) + 3]
    esc += APP[APP.index("function nomeGiornata("):APP.index("\n}\n", APP.index("function nomeGiornata(")) + 3]
    righe = [re.search(rf"^const {n} = .*$", APP, re.M).group(0) for n in ("num", "segno")]
    inizio = APP.index("// Registro delle giornate")
    blocco = APP[inizio:APP.index("// Stato dei dati: da dove arriva tutto", inizio)]
    return esc + "\n".join(righe) + "\n" + blocco


def _carta(registro, lingua="it") -> str:
    if NODE is None:
        pytest.skip("serve node")
    prova = TESTI_JS + f'\nLINGUA = "{lingua}";\n' + _codice_registro() + f"\nconsole.log(JSON.stringify(cartaRegistro({json.dumps(registro)})));"
    r = subprocess.run([NODE, "-"], input=prova, capture_output=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def _testi(html: str) -> list[str]:
    """I pezzi di testo della carta, nell'ordine in cui si leggono."""
    return [p.strip() for p in re.sub(r"<[^>]+>", "\n", html).split("\n") if p.strip()]


def _dopo(pezzi: list[str], testo: str) -> str:
    """Il pezzo che segue `testo` (lo stato accanto al nome della misura)."""
    assert testo in pezzi, pezzi
    return pezzi[pezzi.index(testo) + 1]


def test_prima_di_8_giornate_medie_soglie_e_quante_ne_servono(tmp_path):
    pezzi = _testi(_carta(_registro(tmp_path, 3)))
    assert pezzi[0] == "Registro delle giornate"
    assert "Media delle ultime 3 giornate misurate." in pezzi
    for nome in (I1, I2, I3):
        assert _dopo(pezzi, nome) == "servono ancora 5 giornate"
    assert _dopo(pezzi, "servono ancora 5 giornate") == "−5,7% (deve stare a +1% o meno) · errore 1,00 contro 1,06"
    assert "scarto 10 punti (al massimo 5) · punteggio di Brier 0,100 (al massimo 0,150)" in pezzi
    assert "80% (deve stare tra 72% e 88%)" in pezzi
    assert "Giornate perse" not in pezzi


def test_con_8_giornate_regge_o_non_regge_come_dice_il_server(tmp_path):
    reg = _registro(tmp_path, 8)
    assert reg["verdetto"] and reg["regge"] == {"I1": True, "I2": False, "I3": True}
    html = _carta(reg)
    pezzi = _testi(html)
    assert "Media delle ultime 8 giornate misurate." in pezzi
    assert (_dopo(pezzi, I1), _dopo(pezzi, I2), _dopo(pezzi, I3)) == ("regge", "non regge", "regge")
    assert re.search(r'style="color:var\(--rosso\)">non regge<', html)          # il colore accompagna la parola, non la sostituisce
    assert re.search(r'style="color:var\(--verde\)">regge<', html)


def test_il_verdetto_viene_dal_server_non_dal_client(tmp_path):
    """Se il server dice «regge» per una misura fuori soglia, la web scrive «regge»: le soglie non si ricalcolano qui."""
    reg = _registro(tmp_path, 8)
    reg["regge"] = {"I1": False, "I2": True, "I3": None}
    pezzi = _testi(_carta(reg))
    assert (_dopo(pezzi, I1), _dopo(pezzi, I2), _dopo(pezzi, I3)) == ("non regge", "regge", "ancora nessun dato")


@pytest.mark.parametrize(("misurate", "riga", "stato"), [
    (1, "Media di 1 giornata misurata.", "servono ancora 7 giornate"),
    (7, "Media delle ultime 7 giornate misurate.", "serve ancora 1 giornata"),
])
def test_plurali(tmp_path, misurate, riga, stato):
    pezzi = _testi(_carta(_registro(tmp_path, misurate)))
    assert riga in pezzi and _dopo(pezzi, I1) == stato


def test_senza_giornate_misurate_solo_la_spiegazione(tmp_path):
    pezzi = _testi(_carta(_registro(tmp_path, 0)))
    assert pezzi[0] == "Registro delle giornate"
    assert any(p.startswith("Ancora nessuna giornata misurata") for p in pezzi)
    assert I1 not in pezzi and "–" not in " ".join(pezzi)


def test_giornate_perse_con_il_motivo_protetto(tmp_path):
    reg = _registro(tmp_path, 2, {9: "previsioni non pronte <b>x</b>", 5: registro_giornate.SENZA_TENTATIVI})
    html = _carta(reg)
    pezzi = _testi(html)
    assert "Giornate perse" in pezzi
    assert "Non salvate prima della prima partita: non si possono più misurare." in pezzi
    assert _dopo(pezzi, "9ª giornata di Serie A · 2026-27") == "previsioni non pronte &lt;b&gt;x&lt;/b&gt;"      # #299: come il Diario
    assert _dopo(pezzi, "5ª giornata di Serie A · 2026-27") == registro_giornate.SENZA_TENTATIVI
    assert "<b>x</b>" not in html


def test_senza_campo_registro_niente_carta():
    assert _carta(None) == ""


@pytest.mark.parametrize("lingua", ["it", "en"])
def test_niente_chiavi_mancanti_ne_numeri_rotti(tmp_path, lingua):
    for reg in (_registro(tmp_path, 3, {4: "motivo"}), _registro(tmp_path, 8)):
        testo = " ".join(_testi(_carta(reg, lingua)))
        assert "sd.reg_" not in testo and "undefined" not in testo and "NaN" not in testo and "null" not in testo


def test_la_fixture_dell_iphone_e_la_risposta_vera_del_server(tmp_path):
    """Se il server cambia il campo `registro`, la fixture dei test iOS va rifatta: dentro va {"stagione", "registro"} come qui."""
    salvata = json.loads(FIXTURE_IOS.read_text(encoding="utf-8"))
    assert salvata == {"stagione": ST, "registro": _registro(tmp_path, 8, PERSA)}


def test_la_pagina_mostra_la_carta():
    corpo = APP[APP.index("async function apriStatoDati"):APP.index("// Aspetto: tema")]
    assert "${cartaRegistro(s.registro)}" in corpo
