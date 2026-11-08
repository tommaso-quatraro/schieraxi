"""Regressione visiva della web nelle pull request (script/ci/aspetto_web.py e .github/workflows/aspetto-web.yml, issue #503).

Il riferimento sono le foto di main scattate nella stessa corsa, con lo stesso Chrome e le risposte registrate di
ios/fotografie/ (nomi inventati). I test non aprono il browser: provano confronto delle immagini, soglia, riga «Aspetto:»,
esito, server finto, elenco delle scene e le regole di sicurezza del workflow."""
import importlib.util
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest
from PIL import Image

RADICE = Path(__file__).resolve().parent.parent
PERCORSO = RADICE / "script" / "ci" / "aspetto_web.py"
WORKFLOW = RADICE / ".github" / "workflows" / "aspetto-web.yml"
REQUISITI = RADICE / ".github" / "playwright-requisiti.txt"
MODELLO_PR = RADICE / ".github" / "PULL_REQUEST_TEMPLATE.md"


def _modulo():
    spec = importlib.util.spec_from_file_location("aspetto_web_in_prova", PERCORSO)
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m          # le dataclass con `from __future__ import annotations` cercano qui il loro modulo
    spec.loader.exec_module(m)          # Playwright si importa solo quando servono le foto: qui non c'è
    return m


@pytest.fixture(scope="module")
def aw():
    return _modulo()


def _png(percorso: Path, misura=(100, 100), colore=(255, 255, 255), macchia=None) -> Path:
    """Un'immagine finta: fondo di un colore e, se chiesto, un rettangolo `macchia` = (x, y, larghezza, altezza, colore)."""
    img = Image.new("RGB", misura, colore)
    if macchia:
        x, y, w, h, c = macchia
        for i in range(x, x + w):
            for j in range(y, y + h):
                img.putpixel((i, j), c)
    img.save(percorso)
    return percorso


# ------------------------------------------------------------------ confronto delle immagini
def test_immagini_uguali_zero(aw, tmp_path):
    a = _png(tmp_path / "a.png", macchia=(10, 10, 20, 20, (0, 90, 40)))
    b = _png(tmp_path / "b.png", macchia=(10, 10, 20, 20, (0, 90, 40)))
    d = aw.confronta(a, b)
    assert (d.pixel, d.quota, d.misura_diversa) == (0, 0.0, False)
    assert not d.diversa


def test_pochi_pixel_sotto_soglia_non_contano(aw, tmp_path):
    # 400x400 = 160.000 pixel: lo 0,1% sono 160. Dieci pixel molto diversi restano sotto la soglia...
    a = _png(tmp_path / "a.png", misura=(400, 400))
    b = _png(tmp_path / "b.png", misura=(400, 400), macchia=(0, 0, 10, 1, (0, 0, 0)))
    d = aw.confronta(a, b)
    assert d.pixel == 10 and not d.misura_diversa
    assert not d.diversa
    # ...e un'area grande cambiata di poco (sfumatura dei caratteri, 16/255 al massimo su un canale) non conta affatto
    c = _png(tmp_path / "c.png", misura=(400, 400), colore=(255, 255, 255))
    e = _png(tmp_path / "e.png", misura=(400, 400), colore=(239, 250, 255))
    assert aw.confronta(c, e).pixel == 0


def test_area_sopra_soglia_conta(aw, tmp_path):
    a = _png(tmp_path / "a.png", misura=(400, 400))
    b = _png(tmp_path / "b.png", misura=(400, 400), macchia=(50, 50, 20, 10, (200, 0, 0)))     # 200 pixel > 160
    d = aw.confronta(a, b)
    assert d.pixel == 200 and d.quota == pytest.approx(200 / 160_000)
    assert d.diversa and not d.misura_diversa
    # 17/255 su un canale basta per contare il pixel
    c = _png(tmp_path / "c.png", misura=(400, 400), colore=(238, 255, 255))
    assert aw.confronta(a, c).pixel == 160_000


def test_misura_diversa_conta(aw, tmp_path):
    a = _png(tmp_path / "a.png", misura=(390, 800))
    b = _png(tmp_path / "b.png", misura=(390, 801))            # una riga di pixel in più: la pagina è più lunga
    d = aw.confronta(a, b)
    assert d.misura_diversa and d.diversa
    assert d.pixel == 0                                         # la parte in comune è identica


def test_immagine_della_differenza(aw, tmp_path):
    a = _png(tmp_path / "a.png", misura=(60, 40))
    b = _png(tmp_path / "b.png", misura=(60, 50), macchia=(5, 5, 4, 4, (0, 0, 0)))
    uscita = aw.immagine_differenza(a, b, tmp_path / "diff.png")
    img = Image.open(uscita).convert("RGB")
    assert img.size == (60, 50)                                 # la misura più grande delle due
    assert img.getpixel((6, 6)) == aw.ROSSO                     # pixel cambiato
    assert img.getpixel((30, 45)) == aw.ROSSO                   # parte che c'è solo in una delle due
    assert img.getpixel((30, 20)) != aw.ROSSO                   # parte uguale


def test_confronto_di_una_scena_con_pezzi_del_foglio(aw, tmp_path):
    """Le scene con un foglio che scorre (scheda, confronto, diario) hanno più pezzi: un pezzo in più o in meno è misura diversa."""
    base, pr = tmp_path / "base", tmp_path / "pr"
    base.mkdir(), pr.mkdir()
    for cartella in (base, pr):
        _png(cartella / "scheda-390-chiaro.png")
        _png(cartella / "scheda-390-chiaro-2.png")
        _png(cartella / "oggi-390-chiaro.png")
    _png(pr / "scheda-390-chiaro-3.png")
    diff = aw.confronta_scatti(base, pr, ["scheda-390-chiaro", "oggi-390-chiaro"])
    assert diff["scheda-390-chiaro"].diversa and diff["scheda-390-chiaro"].misura_diversa
    assert not diff["oggi-390-chiaro"].diversa


def test_per_l_artifact_tutti_i_pezzi_dei_due_lati(aw, tmp_path):
    """Se il foglio di main è più lungo, il suo pezzo in più finisce lo stesso fra le immagini (prima si guardava solo la PR)."""
    for lato in ("base", "pr"):
        (tmp_path / lato).mkdir()
        _png(tmp_path / lato / "diario-390-chiaro.png")
        _png(tmp_path / lato / "diario-390-chiaro-2.png", macchia=(0, 0, 50, 50, (0, 0, 0)) if lato == "pr" else None)
    _png(tmp_path / "base" / "diario-390-chiaro-3.png")
    aw.copia_diverse(tmp_path, "diario-390-chiaro")
    nomi = sorted(p.name for p in (tmp_path / "diverse").iterdir())
    assert "diario-390-chiaro-3-main.png" in nomi and "diario-390-chiaro-3-pr.png" not in nomi
    assert {"diario-390-chiaro-2-main.png", "diario-390-chiaro-2-pr.png", "diario-390-chiaro-2-differenza.png"} <= set(nomi)


def test_avviso_di_github_con_testo_protetto(aw, monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    aw._avviso("100% diverso\nseconda riga")
    uscita = capsys.readouterr().out
    assert uscita == "::warning title=Aspetto della web::100%25 diverso%0Aseconda riga\n"


# ------------------------------------------------------------------ riga «Aspetto:» ed esito
def test_riga_aspetto(aw):
    assert aw.aspetto_dichiarato("Closes #1\n\nAree: fanta/web\nAspetto: oggi, formazione\n") == {"oggi", "formazione"}
    assert aw.aspetto_dichiarato("Aree: fanta/web\nAspetto: nessuno\n") == set()
    assert aw.aspetto_dichiarato("Aree: fanta/web\n\n## Cosa cambia\n") is None
    # come nel modello delle PR: il commento non è una dichiarazione
    assert aw.aspetto_dichiarato("Aspetto: <!-- scene che cambiano, o «nessuno» -->\n") is None
    assert aw.aspetto_dichiarato(None) is None
    assert aw.aspetto_dichiarato("aspetto:  `Oggi`  scheda\n") == {"oggi", "scheda"}
    assert aw.aspetto_dichiarato("Aspetto: tutte\n") == set(aw.SCENE)


def test_riga_aspetto_piu_righe(aw):
    """Conta ogni riga «Aspetto:» non vuota, non solo la prima: la riga del modello lasciata col solo commento non nasconde
    quella scritta più sotto."""
    modello_e_vera = "Aree: fanta/web\n\nAspetto: <!-- scene che cambiano -->\n\n## Cosa cambia\nAspetto: oggi\n"
    assert aw.aspetto_dichiarato(modello_e_vera) == {"oggi"}
    assert aw.aspetto_dichiarato("Aspetto: oggi\n\nAspetto: rosa, scheda\n") == {"oggi", "rosa", "scheda"}
    assert aw.aspetto_dichiarato("Aspetto: nessuno\nAspetto: oggi\n") == {"oggi"}
    assert aw.aspetto_dichiarato("Aspetto: <!-- a -->\nAspetto:\n") is None


def test_esito_dichiarate_0_non_dichiarate_1(aw):
    assert aw.esito(diverse=set(), dichiarate=None, problemi=set()) == 0
    assert aw.esito(diverse={"oggi"}, dichiarate={"oggi", "rosa"}, problemi=set()) == 0
    assert aw.esito(diverse={"oggi", "rosa"}, dichiarate={"oggi"}, problemi=set()) == 1
    assert aw.esito(diverse={"oggi"}, dichiarate=None, problemi=set()) == 1           # senza riga: nessuna è dichiarata
    assert aw.esito(diverse={"oggi"}, dichiarate=set(), problemi=set()) == 1          # «nessuno»
    assert aw.esito(diverse=set(), dichiarate=set(), problemi={"scheda"}) == 2        # scena che non si apre o instabile
    assert aw.esito(diverse={"oggi"}, dichiarate=set(), problemi={"scheda"}) == 2


def test_il_riassunto_dice_cosa_fare(aw):
    testo = aw.riassunto(diverse={"oggi": ["oggi-390-chiaro"], "rosa": ["rosa-1440-scuro"]}, dichiarate={"oggi"},
                         problemi={"scheda": "non si apre nella PR: Timeout"}, mancanti=["/api/novita"], instabili={})
    assert "rosa" in testo and "rosa-1440-scuro" in testo
    assert "Aspetto:" in testo                                    # come si dichiara
    assert "/api/novita" in testo                                 # rotte senza risposta registrata
    assert "scheda" in testo and "Timeout" in testo
    pulito = aw.riassunto(diverse={}, dichiarate=None, problemi={}, mancanti=[], instabili={})
    assert "Nessuna scena diversa" in pulito


def test_il_riassunto_scrive_i_pixel_di_ogni_scena_anche_sotto_soglia(aw):
    """Con lo 0,1% della pagina un numero o una parola cambiati passano: i pixel di ogni scena servono a scegliere la soglia
    giusta prima che il controllo diventi bloccante."""
    pixel = {"oggi": aw.Differenza(1234, 0.0005, False), "rosa": aw.Differenza(0, 0.0, False),
             "scheda": aw.Differenza(7, 0.00002, True)}
    testo = aw.riassunto(diverse={}, dichiarate=None, problemi={}, mancanti=[], instabili={}, pixel=pixel)
    righe = {r.split("|")[1].strip(" `"): r for r in testo.splitlines() if r.startswith("| `")}
    assert set(righe) == {"oggi", "rosa", "scheda"}
    assert "1234" in righe["oggi"] and "0,050%" in righe["oggi"]
    assert "| 0 |" in righe["rosa"]
    assert "misura" in righe["scheda"]


# ------------------------------------------------------------------ server finto
def _scenario(tmp_path: Path) -> Path:
    s = tmp_path / "scenario.json"
    s.write_text(json.dumps({"scenario": "prova", "adesso": "2026-10-27T15:10:00", "risposte": {
        "/api/stato": json.dumps({"nome_lega": "Lega Inventata"}),
        "/api/formazione?squadra=Real%20Esempio": json.dumps({"squadra": "Real Esempio"}),
        "/api/formazione": json.dumps({"squadra": "Squadra Demo"}),
    }}), encoding="utf-8")
    return s


def _web(tmp_path: Path) -> Path:
    web = tmp_path / "progetto" / "web"
    web.mkdir(parents=True)
    (web / "index.html").write_text("<!doctype html><title>prova</title>", encoding="utf-8")
    (web / "app.js").write_text("console.log('ciao');", encoding="utf-8")
    (tmp_path / "progetto" / "segreto.txt").write_text("non uscire", encoding="utf-8")
    return web


def _chiedi(base: str, percorso: str, metodo: str = "GET"):
    richiesta = urllib.request.Request(base + percorso, method=metodo, data=b"{}" if metodo == "POST" else None)
    try:
        with urllib.request.urlopen(richiesta, timeout=5) as r:
            return r.status, r.headers.get("Content-Type", ""), r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type", ""), e.read().decode("utf-8")


def test_server_finto_risponde_dalla_registrazione(aw, tmp_path):
    with aw.ServerFinto(_web(tmp_path), _scenario(tmp_path), porta=0) as s:
        assert _chiedi(s.indirizzo, "/api/stato")[0] == 200
        stato, tipo, corpo = _chiedi(s.indirizzo, "/api/formazione?squadra=Real%20Esempio")      # con la query
        assert stato == 200 and "application/json" in tipo and json.loads(corpo)["squadra"] == "Real Esempio"
        stato, _, corpo = _chiedi(s.indirizzo, "/api/formazione?giornata=9")                     # query sconosciuta: senza
        assert stato == 200 and json.loads(corpo)["squadra"] == "Squadra Demo"
        assert _chiedi(s.indirizzo, "/api/stato", "POST")[0] == 200                              # nessuna scrittura: stessa risposta
        stato, _, corpo = _chiedi(s.indirizzo, "/api/novita?da=1")                               # mancante
        assert stato == 404 and json.loads(corpo) == {"detail": "rotta non registrata"}
        stato, tipo, corpo = _chiedi(s.indirizzo, "/?vista=oggi")
        assert stato == 200 and "text/html" in tipo and "<title>prova</title>" in corpo
        stato, tipo, _ = _chiedi(s.indirizzo, "/app.js?v=3")
        assert stato == 200 and "javascript" in tipo                                              # mai text/plain (Windows)
        assert s.mancanti == ["/api/novita?da=1"]
        assert s.indirizzo.startswith("http://127.0.0.")


def test_server_finto_non_esce_dalla_cartella(aw, tmp_path):
    with aw.ServerFinto(_web(tmp_path), _scenario(tmp_path), porta=0) as s:
        for percorso in ("/../segreto.txt", "/%2e%2e/segreto.txt", "/%2E%2E%2Fsegreto.txt", "/..%5csegreto.txt",
                         "/%2e%2e%5csegreto.txt", "//segreto.txt", "/web/../../segreto.txt"):
            stato, _, corpo = _chiedi(s.indirizzo, percorso)
            assert stato == 404 and "non uscire" not in corpo, percorso


def test_server_finto_non_cerca_il_nome_dell_indirizzo(aw, tmp_path, monkeypatch):
    """HTTPServer chiede il nome di 127.0.0.NN (getfqdn): su Windows sono secondi di attesa per ogni server."""
    import socket

    def vietata(*argomenti):
        raise AssertionError("getfqdn non serve")
    monkeypatch.setattr(socket, "getfqdn", vietata)
    with aw.ServerFinto(_web(tmp_path), _scenario(tmp_path), porta=0) as s:
        assert _chiedi(s.indirizzo, "/api/stato")[0] == 200


def test_server_finto_scenario_senza_risposte_e_errore(aw, tmp_path):
    vuoto = tmp_path / "vuoto.json"
    vuoto.write_text(json.dumps({"adesso": "2026-10-27T15:10:00", "risposte": {}}), encoding="utf-8")
    with pytest.raises(ValueError):
        aw.leggi_scenario(vuoto)
    assert aw.leggi_scenario(_scenario(tmp_path))["adesso"] == "2026-10-27T15:10:00"


# ------------------------------------------------------------------ scene
def test_elenco_delle_scene(aw):
    """Le schermate che la spec chiede di coprire: le quattro schede, scheda, confronto, diario, regole, scambi, impostazioni."""
    assert list(aw.SCENE) == ["oggi", "formazione", "squadra", "rosa", "scheda", "confronto", "altro", "diario", "regole",
                              "scambi", "impostazioni"]
    for nome, scena in aw.SCENE.items():
        assert scena.indirizzo.startswith("/?vista="), nome
    assert aw.LARGHEZZE == (390, 1440) and aw.TEMI == ("chiaro", "scuro")


def test_scene_senza_funzioni_interne(aw):
    """Solo indirizzi e clic su elementi della pagina: con la web divisa in moduli le funzioni interne di app.js non sono
    più raggiungibili per nome, mentre indirizzi ed elementi restano."""
    for nome, scena in aw.SCENE.items():
        for pezzo in (scena.indirizzo, *scena.clic):
            assert not re.search(r"[A-Za-z_$][\w$]*\s*\(", pezzo), f"{nome}: «{pezzo}» chiama una funzione"
            assert "=>" not in pezzo and ";" not in pezzo, f"{nome}: «{pezzo}» è codice"
    sorgente = PERCORSO.read_text(encoding="utf-8")
    for interna in ("vai(", "vistaRosa(", "apriGiocatore(", "apriConfronto(", "apriDiario(", "vistaRegole(", "typeof vai"):
        assert interna not in sorgente, interna


def test_foto_senza_finestra_e_ferme(aw):
    sorgente = PERCORSO.read_text(encoding="utf-8")
    assert "headless=True" in sorgente and "headless=False" not in sorgente
    assert 'channel="chrome"' in sorgente                       # Chrome di sistema: niente browser da scaricare
    assert 'service_workers="block"' in sorgente                # niente copia vecchia dalla cache
    assert 'reduced_motion="reduce"' in sorgente and 'animations="disabled"' in sorgente
    assert "set_fixed_time" in sorgente                         # orologio fermo su «adesso» dello scenario
    assert "document.fonts.ready" in sorgente


def test_scene_instabili_hanno_un_motivo(aw):
    for nome, motivo in aw.INSTABILI.items():
        assert nome in aw.SCENE and motivo.strip(), nome


def test_argomenti(aw, tmp_path):
    a = aw.leggi_argomenti(["--base", "b", "--pr", "p", "--uscita", str(tmp_path), "--scene", "oggi,rosa"])
    assert a.scene == ["oggi", "rosa"] and a.larghezze == [390, 1440] and a.temi == ["chiaro", "scuro"]
    with pytest.raises(SystemExit):
        aw.leggi_argomenti(["--base", "b", "--pr", "p", "--uscita", str(tmp_path), "--scene", "inventata"])


def test_preparazione_sbagliata_esce_con_3(aw, tmp_path, capsys):
    web = _web(tmp_path)
    assert aw.main(["--base", str(tmp_path / "non-esiste"), "--pr", str(web.parent), "--uscita", str(tmp_path / "u"),
                    "--scenario", str(_scenario(tmp_path))]) == 3
    assert "non-esiste" in capsys.readouterr().out


# ------------------------------------------------------------------ flusso di main() con foto finte (senza browser)
GRANDE = (0, 0, 30, 30, (0, 0, 0))       # 900 pixel su 10.000: scena diversa
PICCOLA = (0, 0, 3, 1, (0, 0, 0))        # 3 pixel: sotto la soglia dello 0,1%


def _scatta_finta(macchie: dict, errori: dict | None = None, chiamate: list | None = None):
    """Al posto di `scatta`: una foto bianca 100x100 per scena, larghezza e tema nella cartella del lato (base, pr, base-2),
    con la macchia di `macchie[(lato, scena)]` se c'è; `errori[(lato, scena)]` = la scena non si apre."""
    def scatta(indirizzo, cartella, scene, larghezze, temi, adesso):
        cartella = Path(cartella)
        cartella.mkdir(parents=True, exist_ok=True)
        if chiamate is not None:
            chiamate.append((cartella.name, list(scene)))
        mancate = {}
        for tema in temi:
            for larghezza in larghezze:
                for scena in scene:
                    nome = f"{scena}-{larghezza}-{tema}"
                    if (errori or {}).get((cartella.name, scena)):
                        mancate[nome] = errori[(cartella.name, scena)]
                        continue
                    _png(cartella / f"{nome}.png", macchia=macchie.get((cartella.name, scena)))
        return mancate
    return scatta


def _copia(tmp_path: Path) -> Path:
    """Una copia finta del repository: solo fanta/web/index.html (le foto le fa `_scatta_finta`)."""
    web = tmp_path / "copia" / "fanta" / "web"
    web.mkdir(parents=True)
    (web / "index.html").write_text("<!doctype html><title>prova</title>", encoding="utf-8")
    return tmp_path / "copia"


def _lancia(aw, tmp_path, monkeypatch, corpo: str | None, scene="oggi,rosa"):
    copia = _copia(tmp_path)
    if corpo is None:
        monkeypatch.delenv("CORPO", raising=False)
    else:
        monkeypatch.setenv("CORPO", corpo)
    riassunto_corsa = tmp_path / "riassunto-corsa.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(riassunto_corsa))
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    uscita = tmp_path / "uscita"
    codice = aw.main(["--base", str(copia), "--pr", str(copia), "--uscita", str(uscita),
                      "--scenario", str(_scenario(tmp_path)), "--larghezze", "390", "--temi", "chiaro", "--scene", scene])
    return codice, uscita, riassunto_corsa


def test_flusso_scena_cambiata_non_dichiarata(aw, tmp_path, monkeypatch, capsys):
    chiamate = []
    monkeypatch.setattr(aw, "scatta", _scatta_finta({("pr", "oggi"): GRANDE}, chiamate=chiamate))
    codice, uscita, riassunto_corsa = _lancia(aw, tmp_path, monkeypatch, "Aree: fanta/web\nAspetto: nessuno\n")
    assert codice == 1
    assert chiamate == [("base", ["oggi", "rosa"]), ("pr", ["oggi", "rosa"]), ("base-2", ["oggi"])]   # rifatta su main
    assert sorted(p.name for p in (uscita / "diverse").iterdir()) == [
        "oggi-390-chiaro-differenza.png", "oggi-390-chiaro-main.png", "oggi-390-chiaro-pr.png"]
    testo = (uscita / "riassunto.md").read_text(encoding="utf-8")
    assert "`oggi`: diversa da main, **non dichiarata**" in testo and "`Aspetto: oggi`" in testo
    assert riassunto_corsa.read_text(encoding="utf-8") == testo                  # anche nel riassunto della corsa
    assert "::warning title=Aspetto della web::scene diverse da main non dichiarate" in capsys.readouterr().out


def test_flusso_scena_dichiarata_anche_su_una_riga_piu_sotto(aw, tmp_path, monkeypatch):
    monkeypatch.setattr(aw, "scatta", _scatta_finta({("pr", "oggi"): GRANDE}))
    corpo = "Aree: fanta/web\n\nAspetto: <!-- commento del modello -->\n\n## Cosa cambia\nAspetto: oggi\n"
    codice, uscita, _ = _lancia(aw, tmp_path, monkeypatch, corpo)
    assert codice == 0
    assert "`oggi`: diversa da main, dichiarata" in (uscita / "riassunto.md").read_text(encoding="utf-8")


def test_flusso_main_che_cambia_da_sola_e_instabile(aw, tmp_path, monkeypatch):
    """La seconda foto di main è diversa dalla prima (e uguale alla PR): non è colpa della PR, la scena è instabile."""
    monkeypatch.setattr(aw, "scatta", _scatta_finta({("pr", "rosa"): GRANDE, ("base-2", "rosa"): GRANDE}))
    codice, uscita, _ = _lancia(aw, tmp_path, monkeypatch, None)
    assert codice == 2
    assert not (uscita / "diverse").exists()                                    # niente immagini: non è una differenza
    testo = (uscita / "riassunto.md").read_text(encoding="utf-8")
    assert "cambia da sola anche su main" in testo and "`rosa`" in testo and "non dichiarata" not in testo


def test_flusso_scena_che_non_si_apre(aw, tmp_path, monkeypatch):
    monkeypatch.setattr(aw, "scatta", _scatta_finta({}, errori={("pr", "rosa"): "TimeoutError: attesa finita"}))
    codice, uscita, _ = _lancia(aw, tmp_path, monkeypatch, "Aspetto: nessuno\n")
    assert codice == 2
    assert "rosa-390-chiaro non si apre nella PR: TimeoutError" in (uscita / "riassunto.md").read_text(encoding="utf-8")


def test_flusso_pochi_pixel_passano_ma_si_vedono(aw, tmp_path, monkeypatch):
    chiamate = []
    monkeypatch.setattr(aw, "scatta", _scatta_finta({("pr", "oggi"): PICCOLA}, chiamate=chiamate))
    codice, uscita, _ = _lancia(aw, tmp_path, monkeypatch, None)
    assert codice == 0 and [c[0] for c in chiamate] == ["base", "pr"]           # niente seconda foto su main
    assert not (uscita / "diverse").exists()
    testo = (uscita / "riassunto.md").read_text(encoding="utf-8")
    assert "Nessuna scena diversa da main" in testo
    righe = {r.split("|")[1].strip(" `"): r for r in testo.splitlines() if r.startswith("| `")}
    assert "| 3 |" in righe["oggi"] and "| 0 |" in righe["rosa"]


# ------------------------------------------------------------------ workflow, requisiti, modello delle PR
def _testo_workflow() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_workflow_solo_avviso_e_permessi_minimi():
    testo = _testo_workflow()
    assert re.search(r"^permissions:\s*\n  contents: read\s*$", testo, re.M)
    assert "write" not in re.sub(r"#.*", "", testo)              # nessun permesso di scrittura, nemmeno nei job
    assert "secrets." not in testo and "pull_request" + "_target" not in testo     # in due pezzi: la parola intera la ferma anti_residui
    assert "continue-on-error: true" in testo                    # il confronto non fa fallire la corsa: solo avviso
    assert "aspetto" not in (RADICE / ".github" / "workflows" / "test.yml").read_text(encoding="utf-8")   # fuori da «unisci»


def test_workflow_parte_sulle_pr_che_toccano_la_web():
    testo = _testo_workflow()
    blocco = testo[testo.index("pull_request:"):testo.index("workflow_dispatch:")]
    for percorso in ("fanta/web/**", "script/ci/aspetto_web.py", "ios/fotografie/**"):
        assert f'"{percorso}"' in blocco, percorso


def test_workflow_due_copie_senza_credenziali_e_corpo_solo_in_env():
    testo = _testo_workflow()
    assert testo.count("actions/checkout@") == 2 == testo.count("persist-credentials: false")
    # nelle PR la base è il primo genitore del commit di prova (il main su cui la PR si unisce), come in test.yml e
    # revisione.yml: base.sha dell'evento può essere più vecchio e mostrerebbe come «diverse» le scene cambiate su main
    assert "fetch-depth: 2" in testo and 'worktree add --detach "$GITHUB_WORKSPACE/base" HEAD^1' in testo
    assert "pull_request.base.sha" not in testo
    # il testo della PR (e ogni dato della PR o dell'ingresso a mano) arriva solo come variabile d'ambiente, mai dentro un comando
    for riga in testo.splitlines():
        if "${{" in riga and re.search(r"github\.event\.|inputs\.|head_ref", riga):
            assert re.match(r"^\s+(ref|group|[A-Z_]+):\s", riga), f"dato della PR fuori da env/ref: {riga.strip()}"
    assert re.search(r"^\s+CORPO: \$\{\{ github\.event\.pull_request\.body \}\}\s*$", testo, re.M)


def test_workflow_ambiente_fissato_e_artifact_breve():
    testo = _testo_workflow()
    assert "--require-hashes --only-binary=:all: -r pr/.github/playwright-requisiti.txt" in testo
    assert "name: aspetto-web" in testo and "retention-days: 7" in testo
    assert "GITHUB_STEP_SUMMARY" in testo or "riassunto" in testo


def test_requisiti_di_playwright_con_versioni_e_hash_fissati():
    requisiti = REQUISITI.read_text(encoding="utf-8")
    librerie = re.findall(r"^([A-Za-z0-9_.-]+)==\S+ \\$", requisiti, re.M)
    blocchi = re.split(r"^[A-Za-z0-9_.-]+==\S+ \\$", requisiti, flags=re.M)[1:]
    assert {n.lower() for n in librerie} >= {"playwright", "pillow", "greenlet", "pyee"}
    assert len(librerie) == len(blocchi)
    assert all(re.search(r"--hash=sha256:[0-9a-f]{64}", b) for b in blocchi), "ogni libreria ha i suoi hash"
    assert re.search(r"^playwright==\d+\.\d+\.\d+ \\$", requisiti, re.M)
    # Pillow come nei requisiti dei test: le stesse immagini si confrontano allo stesso modo in locale e in CI
    sviluppo = (RADICE / "requirements-dev.txt").read_text(encoding="utf-8")
    versione = re.search(r"^pillow==(\S+) \\$", requisiti, re.M | re.I).group(1)
    assert re.search(rf"^pillow=={re.escape(versione)} \\$", sviluppo, re.M | re.I)


def test_modello_delle_pr_ha_la_riga_aspetto(aw):
    modello = MODELLO_PR.read_text(encoding="utf-8")
    assert re.search(r"^Aspetto:", modello, re.M)
    assert aw.aspetto_dichiarato(modello) is None                # il segnaposto del modello non dichiara niente
