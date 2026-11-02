"""Oggi nel web secondo la fase della giornata: a giornata in corso la giornata in diretta (niente «Da controllare»), a giornata
finita il riepilogo e la prossima. Le carte si provano con node su dati finti."""
import json
import re
import shutil
import subprocess

import pytest

from fanta import server

APP = (server.WEB / "app.js").read_text(encoding="utf-8")
NODE = shutil.which("node")

IN_CORSO = {"punti_fatti": 34.5, "punti_previsti": 66.0, "ancora_da_giocare": 2, "giocatori": [
    {"id": 1, "nome": "Rossi <b>", "ruolo": "P", "squadra": "inter", "titolare": True, "a_punteggio": True, "stato": "fatto", "fantavoto": 6.5, "data": None},
    {"id": 2, "nome": "Verdi", "ruolo": "D", "squadra": "roma", "titolare": True, "a_punteggio": True, "stato": "da_giocare", "fantavoto": None, "data": "2026-11-09 20:45"},
    {"id": 3, "nome": "Neri", "ruolo": "D", "squadra": "milan", "titolare": True, "a_punteggio": False, "stato": "senza_voto", "fantavoto": None, "data": None},
    {"id": 4, "nome": "Bianchi", "ruolo": "D", "squadra": "inter", "titolare": False, "a_punteggio": True, "stato": "fatto", "fantavoto": 6.0, "data": None},
    {"id": 5, "nome": "Gialli", "ruolo": "C", "squadra": "lazio", "titolare": True, "a_punteggio": True, "stato": "attesa_voti", "fantavoto": None, "data": None}],
    "sostituzioni": [{"esce": {"id": 3, "nome": "Neri", "ruolo": "D"}, "entra": {"id": 4, "nome": "Bianchi", "ruolo": "D"}, "certa": True},
                     {"esce": {"id": 9, "nome": "Blu", "ruolo": "C"}, "entra": None, "certa": False}]}


def _esegui(chiamata: str) -> str:
    inizio, fine = APP.index("const STATO_LIVE"), APP.index("function mostraOggi(")
    num = re.search(r"^const num = .*$", APP, re.M).group(0)
    testi = (server.WEB / "testi.js").read_text(encoding="utf-8")
    stub = """const esc = s => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
const sigla = s => esc((s || "").slice(0, 3).toUpperCase()); const badgeRuolo = r => `<i>${r}</i>`;
const parseData = s => s ? new Date(String(s).replace(" ", "T")) : null; const quando = s => s ? "QUANDO(" + s + ")" : "–";"""
    codice = f"{testi}\n{num}\n{stub}\n{APP[inizio:fine]}\nconsole.log(JSON.stringify({chiamata}));"
    r = subprocess.run([NODE, "-"], input=codice, capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_oggi_usa_la_fase_e_i_server_vecchi_restano_come_prima():
    assert 'const fase = o.fase || "prima"' in APP
    assert 'inCorso || finita ? [] : o.avvisi.filter(a => a.in_formazione)' in APP       # niente «Da controllare»
    assert "cardInCorso(o.in_corso, o.formazione)" in APP and "cardRiepilogo(o.riepilogo, o.prossima)" in APP


@pytest.mark.skipif(NODE is None, reason="node non installato")
def test_carta_della_giornata_in_corso():
    h = _esegui(f"cardInCorso({json.dumps(IN_CORSO)}, {{punteggio_atteso: 68}})")
    assert "Punti fatti finora" in h and "34,5" in h and "≈ 66,0" in h and "attesi prima: 68,0" in h
    assert "2 giocatori devono ancora giocare" in h and "QUANDO(2026-11-09 20:45)" in h and "voto in arrivo" in h
    assert "Rossi &lt;b&gt;" in h and "<b>\"" not in h                       # nomi sempre ripuliti
    assert "Neri</span>" not in h.split("Cambi dalla panchina")[0]          # chi non va a punteggio non è nell'elenco
    assert "entrato dalla panchina" in h and "Neri → Bianchi" in h and "già fatto" in h
    assert "Blu → nessun sostituto" in h and "probabile" in h
    assert "undefined" not in h and "NaN" not in h
    assert _esegui("cardInCorso(null, {})") == ""


@pytest.mark.skipif(NODE is None, reason="node non installato")
def test_carta_del_riepilogo_e_della_prossima():
    r = {"giornata": 10, "giornata_lega": 7, "formazione_di": "tua", "nel_diario": True, "punti_fatti": 66, "punti_attesi": 67,
         "consigliata": {"punti_fatti": 70.5, "punti_attesi": 68}}
    p = {"giornata": 11, "giornata_lega": 8, "scadenza": "2099-11-14 15:00", "prepara_da": "2099-11-11 15:00", "con_probabili": False}
    h = _esegui(f"cardRiepilogo({json.dumps(r)}, {json.dumps(p)})")
    assert "Giornata 7 finita" in h and "66,0" in h and "67,0" in h and "Con la consigliata: 70,5 punti (68,0 attesi)." in h
    assert 'data-apri-diario="10"' in h and "Giornata 8: la formazione si chiude QUANDO(2099-11-14 15:00)." in h
    assert "Conviene prepararla da QUANDO(2099-11-11 15:00)" in h
    h2 = _esegui(f"cardRiepilogo({json.dumps(r | {'nel_diario': False, 'consigliata': None, 'punti_attesi': None})}, "
                 f"{json.dumps(p | {'con_probabili': True})})")
    assert "arriva nel Diario" in h2 and "Puoi già prepararla." in h2 and "attesi" not in h2.split("Giornata 8")[0]
    assert "undefined" not in h + h2 and "NaN" not in h + h2
    assert _esegui("cardRiepilogo(null, null)") == ""
