"""Lo strumento delle foto della web (prove/foto_web/foto.py): mai una finestra, axe del repository, foto fuori dal repository.

I test non aprono il browser: leggono il file e provano le parti che non ne hanno bisogno (argomenti, riepilogo, copia dei
dati, server di prova chiuso anche quando qualcosa va storto)."""
import importlib.util
import sqlite3
import subprocess
import sys
import urllib.request
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parent.parent
PERCORSO = RADICE / "prove" / "foto_web" / "foto.py"
FOTO = PERCORSO.read_text(encoding="utf-8")


def _modulo():
    spec = importlib.util.spec_from_file_location("foto_web_in_prova", PERCORSO)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)          # Playwright si importa solo quando servono le foto: qui non c'è
    return m


def test_foto_senza_finestra_con_chrome_di_sistema():
    assert "headless=True" in FOTO and "headless=False" not in FOTO
    assert 'channel="chrome"' in FOTO


def test_axe_del_repository_e_tutte_le_larghezze_e_i_temi():
    assert "tests/strumenti/axe/axe.min.js" in FOTO.replace("\\", "/")
    for larghezza in ("390", "768", "1024", "1440"):
        assert larghezza in FOTO
    assert 'color_scheme="light"' in FOTO and 'color_scheme="dark"' in FOTO


def test_le_foto_non_finiscono_nel_repository():
    assert "def fuori_dal_repository(" in FOTO           # rifiuta una cartella di uscita dentro il repository
    m = _modulo()
    with pytest.raises(SystemExit):
        m.fuori_dal_repository(RADICE / "foto-prova")
    with pytest.raises(SystemExit):
        m.fuori_dal_repository(RADICE)
    assert m.fuori_dal_repository(RADICE.parent / "fuori-dal-repository") == (RADICE.parent / "fuori-dal-repository").resolve()


def test_le_scene_principali_ci_sono_tutte():
    m = _modulo()
    for scena in ("oggi", "formazione", "squadra", "elenco", "rosa", "scheda", "confronto", "altro", "diario", "regole",
                  "scambi", "impostazioni"):
        assert scena in m.SCENE


def test_argomenti_con_e_senza_indirizzo():
    m = _modulo()
    a = m.leggi_argomenti(["C:/fuori/foto"])
    assert a.indirizzo is None and a.cartella == "C:/fuori/foto"          # senza indirizzo avvia lui il server di prova
    assert a.larghezze == [390, 768, 1024, 1440] and a.temi == ["chiaro", "scuro"] and a.lingua == "it"
    assert a.scene == list(m.SCENE)
    a = m.leggi_argomenti(["http://127.0.0.31:8031", "C:/fuori/foto", "--scene", "oggi,scheda", "--larghezze", "390",
                           "--temi", "scuro", "--lingua", "en"])
    assert (a.indirizzo, a.scene, a.larghezze, a.temi, a.lingua) == ("http://127.0.0.31:8031", ["oggi", "scheda"], [390], ["scuro"], "en")
    for sbagliati in (["x", "--scene", "nessuna"], ["x", "--temi", "rosa"], ["x", "--larghezze", "tanta"], ["a", "b", "c"]):
        with pytest.raises(SystemExit):
            m.leggi_argomenti(sbagliati)


def test_riga_del_riepilogo_e_violazioni_gravi():
    m = _modulo()
    violazioni = [{"id": "color-contrast", "impact": "serious"}, {"id": "aria", "impact": "critical"},
                  {"id": "region", "impact": "moderate"}, {"id": "x", "impact": None}]
    assert m.gravi(violazioni) == 2
    assert m.riga_riepilogo("oggi", 390, "chiaro", 2, True, 0) == "oggi 390 chiaro gravi=2 scorrimento-di-lato=sì errori-console=0"
    assert m.riga_riepilogo("scheda", 1440, "scuro", 0, False, 3) == "scheda 1440 scuro gravi=0 scorrimento-di-lato=no errori-console=3"


def test_il_foglio_aperto_si_fotografa_a_pezzi_fino_in_fondo():
    """La scheda, il confronto e il diario stanno in un foglio fermo che scorre da sé: la foto della pagina intera ne
    mostrerebbe solo l'inizio. Si fotografa a pezzi, scorrendo il foglio, con un po' di sovrapposizione."""
    m = _modulo()
    assert m.posizioni_foglio(500, 800) == [0]                           # entra tutto: una foto
    pos = m.posizioni_foglio(3000, 800)
    assert pos[0] == 0 and pos[-1] == 3000 - 800                         # l'ultima arriva in fondo
    assert all(0 < b - a < 800 for a, b in zip(pos, pos[1:]))            # nessun buco tra un pezzo e l'altro
    assert len(m.posizioni_foglio(10**6, 800)) == m.PEZZI_FOGLIO         # tetto ai pezzi


def test_copia_con_lega_d_esempio_e_solo_l_archivio_dei_dati(tmp_path):
    m = _modulo()
    dati = tmp_path / "dati"
    dati.mkdir()
    with sqlite3.connect(dati / "fanta.sqlite") as db:
        db.execute("CREATE TABLE prova(x)")
        db.execute("INSERT INTO prova VALUES (7)")
    db.close()
    (dati / "diario.json").write_text("{}", encoding="utf-8")            # file personali: restano fuori dalla copia
    (dati / "scelte.json").write_text("{}", encoding="utf-8")
    copia = m.prepara_copia(tmp_path / "copia", dati)
    assert (copia / "fanta" / "server.py").is_file()
    assert not list((copia / "fanta").rglob("__pycache__"))
    assert (copia / "lega" / "regole.json").read_bytes() == (RADICE / "lega" / "esempio" / "regole.json").read_bytes()
    assert sorted(p.name for p in (copia / "dati").iterdir()) == ["fanta.sqlite"]
    with sqlite3.connect(copia / "dati" / "fanta.sqlite") as db:
        assert db.execute("SELECT x FROM prova").fetchone() == (7,)
    db.close()
    vuota = m.prepara_copia(tmp_path / "vuota", None)                    # senza archivio: si parte vuoti, non si cerca altrove
    assert list((vuota / "dati").iterdir()) == []


def test_ambiente_del_server_senza_azioni_vere(tmp_path, monkeypatch):
    m = _modulo()
    monkeypatch.setenv("FANTA_MULTIUTENTE", "1")
    monkeypatch.setenv("FANTA_FONTE_VOTI", "1")
    env = m.ambiente_server(tmp_path)
    assert env["FANTA_LEGA"] == str(tmp_path / "lega")
    assert "FANTA_MULTIUTENTE" not in env and "FANTA_FONTE_VOTI" not in env      # fonti spente: nessuna richiesta fuori
    for spento in ("FANTA_PIANIFICATORE", "FANTA_COPIA_SCADENZA", "FANTA_REGISTRO_GIORNATE"):
        assert env[spento] == "0"


def test_porta_libera_e_indirizzo_di_loopback_proprio():
    m = _modulo()
    host = m.host_per(8031)
    assert host.startswith("127.0.0.") and host != "127.0.0.1"
    porta = m.porta_libera(host)
    assert 1024 < porta < 65536


def test_il_server_di_prova_si_ferma_anche_se_qualcosa_va_storto(tmp_path):
    m = _modulo()
    (tmp_path / "api").mkdir()
    (tmp_path / "api" / "salute").write_text("ok", encoding="utf-8")
    host = m.host_per(8031)
    porta = m.porta_libera(host)
    comando = [sys.executable, "-m", "http.server", str(porta), "--bind", host, "--directory", str(tmp_path)]
    server = m.ServerDiProva(comando, f"http://{host}:{porta}", cwd=tmp_path, env=None, log=tmp_path / "server.log")
    with pytest.raises(RuntimeError, match="prova"):
        with server:
            assert server.processo.poll() is None
            with urllib.request.urlopen(f"http://{host}:{porta}/api/salute", timeout=5) as r:
                assert r.status == 200
            raise RuntimeError("prova di un errore a metà")
    assert server.processo.poll() is not None


def test_server_che_non_parte_dice_dove_guardare(tmp_path):
    m = _modulo()
    comando = [sys.executable, "-c", "import sys; print('rotto'); sys.exit(3)"]
    server = m.ServerDiProva(comando, "http://127.0.0.31:1", cwd=tmp_path, env=None, log=tmp_path / "server.log", attesa=5)
    with pytest.raises(SystemExit) as e:
        with server:
            pass
    assert "server.log" in str(e.value)
    assert server.processo.poll() is not None


def test_si_lancia_come_script_e_spiega_l_uso():
    r = subprocess.run([sys.executable, str(PERCORSO), "--help"], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0 and "--scene" in r.stdout and "riepilogo" in r.stdout
