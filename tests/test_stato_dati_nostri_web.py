"""Stato dei dati, web: i gol attesi «nostri» senza Understat (I4 dal vivo, Fase E del piano 2026-11-06-gol-attesi-nostri, #401).
Il verdetto delle tre misure insieme («reggono» / «non reggono» / «servono ancora N giornate»), per ogni misura la media, la soglia e
«regge» / «non regge», poi le giornate una per una. I dati vengono dalla funzione vera del server (`registro_nostri.riepilogo`, sulle
tabelle dell'archivio); la carta la disegna la funzione vera di `app.js`, eseguita con node."""
import json
import re
import shutil
import subprocess

import pytest

from fanta import archivio, nostri, registro_nostri, server
import codice_web

WEB = server.WEB
APP = codice_web.app()
TESTI_JS = codice_web.leggi("testi.js")
NODE = shutil.which("node")
ST = "2026-27"
V = "3"                                     # la versione dei nostri nei test (fissa: la fixture dell'iPhone non cambia con il calcolo)
# una giornata misurata (300 giocatori con il voto, 20 rose): errore del fantavoto atteso dei nostri +0,6% rispetto ai mostrati
# (√1,012036 = 1,006), 2 punti in meno su 20 rose (−0,10 a rosa), gol attesi per fasce [casi, somma attesi, somma veri] con gol attesi
# su veri 32,1 / 34 = 0,94 (mostrati 33,3 / 34 = 0,98). Sommate su più giornate, la quarta fascia (0,20-0,30) arriva a 50 casi e il
# suo scarto è 0,05 gol a giocatore: oltre la soglia di 0,03.
RIGA = {"voti": 300, "sq_nostri": 1012.036, "sq_mostrati": 1000.0, "rose": 20, "punti_nostri": 1300.0, "punti_mostrati": 1302.0,
        "fasce": [[100, 2.0, 2], [60, 4.5, 4], [50, 7.5, 7], [30, 7.5, 9], [20, 7.6, 8], [5, 3.0, 4]],
        "fasce_mostrati": [[100, 2.2, 2], [60, 4.0, 4], [50, 7.0, 7], [30, 8.5, 9], [20, 8.0, 8], [5, 3.6, 4]]}
# la stessa, con la quarta fascia giusta: lo scarto più grande è quello della quinta (0,02), entro la soglia
BUONA = {**RIGA, "fasce": [*RIGA["fasce"][:3], [30, 9.0, 9], *RIGA["fasce"][4:]]}
INSIEME = "Le tre misure insieme"
ERRORE = "Errore del fantavoto atteso contro i numeri mostrati"
PUNTI = "Punti veri della formazione migliore contro i numeri mostrati"
GOL = "Gol attesi contro gol veri, per fasce"
PERSA = (10, registro_nostri.SENZA_TENTATIVI)
SALVATA = (11, 3)
# la stessa risposta per i test dell'iPhone (GolAttesiNostriTests): 8 giornate misurate della versione 3 (dalla 2 alla 9), la 1 di
# un'altra versione, la 10 persa e la 11 salvata ma non ancora misurata
FIXTURE_IOS = server.WEB.parent.parent / "ios" / "Tests" / "Fixtures" / "stato-dati-nostri.json"


@pytest.fixture(autouse=True)
def _versione(monkeypatch):
    monkeypatch.setattr(nostri, "VERSIONE", V)


def _misurata(db, g, riga, versione):
    db.execute("INSERT INTO registro_i4 (stagione, giornata, versione, misurato, voti, sq_nostri, sq_mostrati, rose, punti_nostri, "
               "punti_mostrati, fasce, fasce_mostrati, avvisato) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)",
               (ST, g, versione, f"2026-10-{g:02d}T12:00:00", riga["voti"], riga["sq_nostri"], riga["sq_mostrati"], riga["rose"],
                riga["punti_nostri"], riga["punti_mostrati"], json.dumps(riga["fasce"]), json.dumps(riga["fasce_mostrati"])))


def _riepilogo(tmp_path, misurate: int, riga: dict = RIGA, vecchia: bool = False, persa: tuple | None = None,
               salvata: tuple | None = None) -> dict:
    """Il campo `registro_nostri` di /api/stato-dati: `misurate` giornate misurate della versione di oggi (dalla 2 in poi), la 1 di
    un'altra versione se `vecchia`, una giornata persa (giornata, motivo) e una salvata e non ancora misurata (giornata, giocatori)."""
    db = archivio.apri(tmp_path / f"n{misurate}-{int(vecchia)}-{bool(persa)}-{bool(salvata)}.sqlite")
    try:
        if vecchia:
            _misurata(db, 1, riga, "2")
        for g in range(2, 2 + misurate):
            _misurata(db, g, riga, V)
        if persa:
            db.execute("INSERT INTO registro_i4 (stagione, giornata, versione, voti, rose, persa, avvisato) VALUES (?, ?, ?, 0, 0, ?, 0)",
                       (ST, persa[0], V, persa[1]))
        if salvata:
            archivio.inserisci(db, "registro_nostri", [
                {"stagione": ST, "giornata": salvata[0], "calciatore_id": 100 + k, "versione": V, "p_voto": 0.9, "mu": 6.0, "mu_voto": 6.2,
                 "e_gol": 0.1, "e_rigori": 0.0, "e_assist": 0.05, "minuti": 80.0, "e_rigori_mostrati": 0.0} for k in range(salvata[1])])
        db.commit()
        return json.loads(json.dumps(registro_nostri.riepilogo(db)))
    finally:
        db.close()


def _codice() -> str:
    """Le funzioni vere di app.js: `esc`, `nomeGiornata`, `num`, `segno` e i blocchi dei gol attesi nostri e del registro (fino a
    «Stato dei dati»)."""
    esc = APP[APP.index("function esc(x)"):APP.index("\n}\n", APP.index("function esc(x)")) + 3]
    esc += APP[APP.index("function nomeGiornata("):APP.index("\n}\n", APP.index("function nomeGiornata(")) + 3]
    righe = [re.search(rf"^const {n} = .*$", APP, re.M).group(0) for n in ("num", "segno")]
    inizio = APP.index("// Gol attesi nostri")
    blocco = APP[inizio:APP.index("// Stato dei dati: da dove arriva tutto", inizio)]
    return esc + "\n".join(righe) + "\n" + blocco


def _carta(nostri_, lingua="it") -> str:
    if NODE is None:
        pytest.skip("serve node")
    prova = TESTI_JS + f'\nLINGUA = "{lingua}";\n' + _codice() + f"\nconsole.log(JSON.stringify(cartaNostri({json.dumps(nostri_)})));"
    r = subprocess.run([NODE, "-"], input=prova, capture_output=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def _testi(html: str) -> list[str]:
    """I pezzi di testo della carta, nell'ordine in cui si leggono."""
    return [p.strip() for p in re.sub(r"<[^>]+>", "\n", html).split("\n") if p.strip()]


def _dopo(pezzi: list[str], testo: str) -> str:
    """Il pezzo che segue `testo` (lo stato accanto al nome della misura, o la riga sotto una giornata)."""
    assert testo in pezzi, pezzi
    return pezzi[pezzi.index(testo) + 1]


def test_prima_di_8_giornate_medie_soglie_e_quante_ne_servono(tmp_path):
    pezzi = _testi(_carta(_riepilogo(tmp_path, 3)))
    assert pezzi[0] == "Gol attesi nostri (senza Understat)"
    assert "Media delle ultime 3 giornate misurate, versione 3 del calcolo." in pezzi
    for nome in (INSIEME, ERRORE, PUNTI, GOL):
        assert _dopo(pezzi, nome) == "servono ancora 5 giornate"
    assert "+0,6% (deve stare a +1% o meno)" in pezzi
    assert "−0,10 punti a rosa e giornata (deve stare a −0,3 o più)" in pezzi
    assert "scarto più grande 0,050 gol a giocatore (al massimo 0,030) · gol attesi su veri 0,94, con i numeri mostrati 0,98" in pezzi


def test_con_8_giornate_il_verdetto_e_quello_del_server(tmp_path):
    reg = _riepilogo(tmp_path, 8, vecchia=True, persa=PERSA, salvata=SALVATA)
    assert reg["verdetto"] and reg["regge"] == {"errore": True, "punti": True, "gol": False} and reg["regge_tutto"] is False
    html = _carta(reg)
    pezzi = _testi(html)
    assert "Media delle ultime 8 giornate misurate, versione 3 del calcolo." in pezzi
    assert (_dopo(pezzi, INSIEME), _dopo(pezzi, ERRORE), _dopo(pezzi, PUNTI), _dopo(pezzi, GOL)) == (
        "non reggono", "regge", "regge", "non regge")
    assert re.search(r'style="color:var\(--rosso\)">non reggono<', html)       # il colore accompagna la parola, non la sostituisce
    assert re.search(r'style="color:var\(--verde\)">regge<', html)


def test_quando_reggono_tutte_e_tre(tmp_path):
    reg = _riepilogo(tmp_path, 8, riga=BUONA)
    assert reg["regge_tutto"] is True
    html = _carta(reg)
    pezzi = _testi(html)
    assert (_dopo(pezzi, INSIEME), _dopo(pezzi, GOL)) == ("reggono", "regge")
    assert re.search(r'style="color:var\(--verde\)">reggono<', html)
    assert "scarto più grande 0,020 gol a giocatore (al massimo 0,030) · gol attesi su veri 0,99, con i numeri mostrati 0,98" in pezzi


def test_il_verdetto_viene_dal_server_non_dal_client(tmp_path):
    """Se il server dice «regge» per una misura fuori soglia, la web scrive «regge»: le soglie non si ricalcolano qui."""
    reg = _riepilogo(tmp_path, 8)
    reg["regge"], reg["regge_tutto"] = {"errore": False, "punti": None, "gol": True}, True
    pezzi = _testi(_carta(reg))
    assert (_dopo(pezzi, INSIEME), _dopo(pezzi, ERRORE), _dopo(pezzi, PUNTI), _dopo(pezzi, GOL)) == (
        "reggono", "non regge", "ancora nessun dato", "regge")


def test_le_giornate_una_per_una(tmp_path):
    html = _carta(_riepilogo(tmp_path, 8, vecchia=True, persa=PERSA, salvata=SALVATA))
    pezzi = _testi(html)
    assert "<details>" in html and "Giornata per giornata" in pezzi                       # ripiegate: sono fino a 38
    giornate = [p for p in pezzi if p.endswith("giornata di Serie A · 2026-27")]
    assert giornate == [f"{g}ª giornata di Serie A · 2026-27" for g in range(11, 0, -1)]   # dalla più recente, come il registro
    assert _dopo(pezzi, "11ª giornata di Serie A · 2026-27") == "salvati i numeri di 3 giocatori, da misurare a giornata finita"
    assert _dopo(pezzi, "10ª giornata di Serie A · 2026-27") == registro_nostri.SENZA_TENTATIVI
    assert re.search(r'style="color:var\(--rosso\)">' + re.escape(registro_nostri.SENZA_TENTATIVI), html)
    assert _dopo(pezzi, "9ª giornata di Serie A · 2026-27") == "errore +0,6% · punti −0,10 · gol attesi su veri 0,94"
    assert _dopo(pezzi, "1ª giornata di Serie A · 2026-27") == "errore +0,6% · punti −0,10 · gol attesi su veri 0,94 · versione 2, non conta"


def test_giornata_misurata_senza_giocatori_e_motivo_protetto(tmp_path):
    db = archivio.apri(tmp_path / "vuota.sqlite")
    try:
        db.execute("INSERT INTO registro_i4 (stagione, giornata, versione, misurato, voti, rose, avvisato) "
                   "VALUES (?, 4, ?, '2026-10-04T12:00:00', 0, 0, 0)", (ST, V))
        db.execute("INSERT INTO registro_i4 (stagione, giornata, versione, voti, rose, persa, avvisato) VALUES (?, 5, ?, 0, 0, ?, 0)",
                   (ST, V, "misura non riuscita <b>x</b>"))
        db.commit()
        reg = json.loads(json.dumps(registro_nostri.riepilogo(db)))
    finally:
        db.close()
    html = _carta(reg)
    pezzi = _testi(html)
    assert _dopo(pezzi, "4ª giornata di Serie A · 2026-27") == "misurata, ma senza giocatori da confrontare"
    assert _dopo(pezzi, "5ª giornata di Serie A · 2026-27") == "misura non riuscita &lt;b&gt;x&lt;/b&gt;"
    assert "<b>x</b>" not in html


@pytest.mark.parametrize(("misurate", "riga", "stato"), [
    (1, "Media di 1 giornata misurata, versione 3 del calcolo.", "servono ancora 7 giornate"),
    (7, "Media delle ultime 7 giornate misurate, versione 3 del calcolo.", "serve ancora 1 giornata"),
])
def test_plurali(tmp_path, misurate, riga, stato):
    pezzi = _testi(_carta(_riepilogo(tmp_path, misurate, salvata=(12, 1))))
    assert riga in pezzi and _dopo(pezzi, INSIEME) == stato and _dopo(pezzi, ERRORE) == stato
    assert _dopo(pezzi, "12ª giornata di Serie A · 2026-27") == "salvati i numeri di 1 giocatore, da misurare a giornata finita"


def test_senza_giornate_misurate_solo_la_spiegazione(tmp_path):
    pezzi = _testi(_carta(_riepilogo(tmp_path, 0)))
    assert pezzi[0] == "Gol attesi nostri (senza Understat)"
    assert "Ancora nessuna giornata misurata: i numeri arrivano il giorno dopo la fine della prima giornata salvata." in pezzi
    assert "versione" not in " ".join(pezzi)                         # un dettaglio interno: non si scrive
    assert INSIEME not in pezzi and ERRORE not in pezzi and "Giornata per giornata" not in pezzi and "–" not in " ".join(pezzi)
    pezzi = _testi(_carta(_riepilogo(tmp_path, 0, salvata=SALVATA)))                  # la prima giornata salvata, da misurare
    assert INSIEME not in pezzi and "Giornata per giornata" in pezzi


def test_senza_campo_niente_carta():
    assert _carta(None) == ""


@pytest.mark.parametrize("lingua", ["it", "en"])
def test_niente_chiavi_mancanti_ne_numeri_rotti(tmp_path, lingua):
    for reg in (_riepilogo(tmp_path, 3, salvata=SALVATA), _riepilogo(tmp_path, 8, vecchia=True, persa=PERSA, salvata=SALVATA),
                _riepilogo(tmp_path, 0)):
        testo = " ".join(_testi(_carta(reg, lingua)))
        assert "sd.nos_" not in testo and "sd.reg_" not in testo
        assert "undefined" not in testo and "NaN" not in testo and "null" not in testo and "[object" not in testo


def test_la_fixture_dell_iphone_e_la_risposta_vera_del_server(tmp_path):
    """Se il server cambia il campo `registro_nostri`, la fixture dei test iOS va rifatta: dentro va {"stagione", "registro_nostri"}."""
    salvata = json.loads(FIXTURE_IOS.read_text(encoding="utf-8"))
    assert salvata == {"stagione": ST, "registro_nostri": _riepilogo(tmp_path, 8, vecchia=True, persa=PERSA, salvata=SALVATA)}


def test_la_pagina_mostra_la_carta_dopo_il_registro():
    corpo = APP[APP.index("async function apriStatoDati"):APP.index("// Aspetto: tema")]
    assert "${cartaNostri(s.registro_nostri)}" in corpo
    assert corpo.index("${cartaRegistro(s.registro)}") < corpo.index("${cartaNostri(s.registro_nostri)}")
