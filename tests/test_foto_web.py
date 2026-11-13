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


def test_le_foto_non_finiscono_nel_repository(tmp_path):
    assert "def fuori_dal_repository(" in FOTO           # rifiuta una cartella di uscita dentro il repository
    m = _modulo()
    with pytest.raises(SystemExit):
        m.fuori_dal_repository(RADICE / "foto-prova")
    with pytest.raises(SystemExit):
        m.fuori_dal_repository(RADICE)
    assert m.fuori_dal_repository(tmp_path / "foto") == (tmp_path / "foto").resolve()     # cartella temporanea: fuori


def test_da_una_worktree_rifiuta_anche_la_cartella_principale(tmp_path, monkeypatch):
    """Da una worktree (`.claude/worktrees/<nome>`) la cartella principale del repository è un altro repository di lavoro:
    lì .gitignore non esclude le foto, quindi va rifiutata anche lei."""
    m = _modulo()
    principale = tmp_path / "principale"
    worktree = principale / ".claude" / "worktrees" / "agente"
    worktree.mkdir(parents=True)
    monkeypatch.setattr(m, "RADICE", worktree)
    monkeypatch.setattr(m, "_principale", lambda: principale)
    for dentro in (principale / "foto", principale, worktree / "foto"):
        with pytest.raises(SystemExit):
            m.fuori_dal_repository(dentro)
    assert m.fuori_dal_repository(tmp_path / "altrove") == (tmp_path / "altrove").resolve()


def test_le_scene_principali_ci_sono_tutte():
    m = _modulo()
    assert list(m.SCENE) == ["formazione", "squadra", "rosa", "scheda", "altro", "diario", "regole", "impostazioni"]   # senza «oggi» (#616)


def test_argomenti_con_e_senza_indirizzo():
    m = _modulo()
    a = m.leggi_argomenti(["C:/fuori/foto"])
    assert a.indirizzo is None and a.cartella == "C:/fuori/foto"          # senza indirizzo avvia lui il server di prova
    assert a.larghezze == [390, 768, 1024, 1440] and a.temi == ["chiaro", "scuro"] and a.lingua == "it"
    assert a.scene == list(m.SCENE)
    a = m.leggi_argomenti(["http://127.0.0.31:8031", "C:/fuori/foto", "--scene", "formazione,scheda", "--larghezze", "390",
                           "--temi", "scuro", "--lingua", "en"])
    assert (a.indirizzo, a.scene, a.larghezze, a.temi, a.lingua) == ("http://127.0.0.31:8031", ["formazione", "scheda"], [390], ["scuro"], "en")
    for sbagliati in (["x", "--scene", "nessuna"], ["x", "--temi", "rosa"], ["x", "--larghezze", "tanta"], ["a", "b", "c"]):
        with pytest.raises(SystemExit):
            m.leggi_argomenti(sbagliati)


def test_riga_del_riepilogo_e_violazioni_gravi():
    m = _modulo()
    violazioni = [{"id": "color-contrast", "impact": "serious"}, {"id": "aria", "impact": "critical"},
                  {"id": "region", "impact": "moderate"}, {"id": "x", "impact": None}]
    assert m.gravi(violazioni) == 2
    assert m.riga_riepilogo("formazione", 390, "chiaro", 2, True, 0) == "formazione 390 chiaro gravi=2 scorrimento-di-lato=sì errori-console=0"
    assert m.riga_riepilogo("scheda", 1440, "scuro", 0, False, 3) == "scheda 1440 scuro gravi=0 scorrimento-di-lato=no errori-console=3"


def test_il_riepilogo_dice_quali_regole_gravi_sono_violate(tmp_path, monkeypatch):
    """#697: il riepilogo diceva solo «gravi=1» e il collaudo della prova non diceva quale regola. Ora la riga ha anche le regole
    gravi violate (gli elementi sono nel file axe-<scena>-<larghezza>-<tema>.json)."""
    m = _modulo()
    violazioni = [{"id": "color-contrast", "impact": "serious"}, {"id": "region", "impact": "moderate"},
                  {"id": "aria-allowed-attr", "impact": "critical"}]
    assert m.regole_gravi(violazioni) == ["color-contrast", "aria-allowed-attr"]
    assert m.riga_riepilogo("scheda", 390, "chiaro", 2, False, 0, ["color-contrast", "aria-allowed-attr"]) == \
        "scheda 390 chiaro gravi=2 scorrimento-di-lato=no errori-console=0 regole=color-contrast,aria-allowed-attr"
    pagina = _playwright_finto(monkeypatch, m, _Richieste())
    pagina.violazioni = [{"id": "color-contrast", "impact": "serious", "help": "x", "n": 1,
                          "nodi": [{"target": 'button[data-sostituisci="12"]', "sommario": "contrasto 2.01"}]}]
    uscita = tmp_path / "foto"
    assert m.main(["http://127.0.0.31:8031", str(uscita), "--solo-misure", "--scene", "scheda", "--larghezze", "390", "--temi", "chiaro"]) == 1
    assert (uscita / "riepilogo.txt").read_text(encoding="utf-8").split() == \
        ["scheda", "390", "chiaro", "gravi=1", "scorrimento-di-lato=no", "errori-console=0", "regole=color-contrast"]


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
    # tutte le funzioni accese, come sull'ambiente di prova: col profilo pubblico «confronto» risponde 404 (errore della console)
    assert env["FANTA_PROFILO_FUNZIONI"] == "completo"


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


def test_ctrl_c_mentre_aspetta_il_server_lo_ferma(tmp_path, monkeypatch):
    """Ctrl+C durante l'attesa (fino a 30 s): `__enter__` non finisce, quindi il `with` non chiamerebbe `__exit__`."""
    m = _modulo()

    def interrompi(*a, **k):
        raise KeyboardInterrupt

    monkeypatch.setattr(m.urllib.request, "urlopen", interrompi)
    comando = [sys.executable, "-c", "import time; time.sleep(60)"]
    server = m.ServerDiProva(comando, "http://127.0.0.31:1", cwd=tmp_path, env=None, log=tmp_path / "server.log")
    with pytest.raises(KeyboardInterrupt):
        with server:
            pass
    assert server.processo.poll() is not None
    assert server._file_log.closed


def test_server_che_non_parte_dice_dove_guardare(tmp_path):
    m = _modulo()
    comando = [sys.executable, "-c", "import sys; print('rotto'); sys.exit(3)"]
    server = m.ServerDiProva(comando, "http://127.0.0.31:1", cwd=tmp_path, env=None, log=tmp_path / "server.log", attesa=5)
    with pytest.raises(SystemExit) as e:
        with server:
            pass
    assert "server.log" in str(e.value)
    assert server.processo.poll() is not None


def test_il_comando_unico_prepara_il_diario_e_chiude_il_server_anche_dopo_un_errore(tmp_path, monkeypatch):
    """Senza indirizzo: copia, diario della lega d'esempio (sennò la scena «diario» è vuota), server, foto. Se le foto si
    rompono a metà il server si ferma lo stesso e l'errore arriva a chi ha lanciato."""
    m = _modulo()
    passi = []

    def copia(dove, dati):
        passi.append("copia")
        dove.mkdir(parents=True)
        return dove

    class ServerFinto:
        def __init__(self, comando, base, **k):
            self.base, self.processo = base, type("P", (), {"pid": 1})()
            assert comando[1:4] == ["-m", "fanta", "server"]

        def __enter__(self):
            passi.append("server acceso")
            return self

        def __exit__(self, *e):
            passi.append("server spento")
            return False

    def foto_rotte(*a, **k):
        passi.append("foto")
        raise RuntimeError("Chrome chiuso a metà")

    dati = tmp_path / "dati"                      # un archivio finto: in CI la cartella dati/ non c'è
    dati.mkdir()
    (dati / "fanta.sqlite").write_bytes(b"")
    monkeypatch.setattr(m, "prepara_copia", copia)
    monkeypatch.setattr(m, "calcola_diario", lambda copia, python: passi.append("diario"))
    monkeypatch.setattr(m, "ServerDiProva", ServerFinto)
    monkeypatch.setattr(m, "fotografa", foto_rotte)
    with pytest.raises(RuntimeError, match="Chrome"):
        m.main([str(tmp_path / "foto"), "--scene", "diario", "--larghezze", "390", "--temi", "chiaro", "--dati", str(dati)])
    assert passi == ["copia", "diario", "server acceso", "foto", "server spento"]


def test_si_lancia_come_script_e_spiega_l_uso():
    r = subprocess.run([sys.executable, str(PERCORSO), "--help"], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0 and "--scene" in r.stdout and "riepilogo" in r.stdout


# =========================== collaudo della prova: --accesso e --solo-misure ===========================
class _Risposta:
    def __init__(self, status):
        self.status = status


class _Richieste:
    """Il `request` del contesto di Playwright: i cookie della risposta restano nel contesto del browser."""
    def __init__(self, status=200):
        self.status, self.chiamate = status, []

    def post(self, indirizzo, data=None, headers=None, **k):
        self.chiamate.append((indirizzo, data))
        # come il server vero: senza X-Fanta una richiesta che cambia qualcosa ha 403
        return _Risposta(self.status if (headers or {}).get("X-Fanta") == "1" else 403)


class _Pagina:
    def __init__(self, m):
        self.m, self.codici, self.violazioni = m, [], []

    def on(self, *a):
        pass

    def emulate_media(self, **k):
        pass

    def set_viewport_size(self, *a):
        pass

    def goto(self, *a, **k):
        pass

    def wait_for_function(self, *a, **k):
        pass

    def wait_for_load_state(self, *a, **k):
        pass

    def wait_for_timeout(self, *a):
        pass

    def evaluate(self, codice, *a):
        self.codici.append(codice)
        return self.violazioni if codice == self.m.LANCIA_AXE else False

    def screenshot(self, path, **k):
        Path(path).write_bytes(b"\x89PNG finta")


def _playwright_finto(monkeypatch, m, richieste):
    """Un Playwright finto (niente browser): `fotografa` gira davvero, le pagine rispondono «tutto a posto».
    Torna la pagina finta, che ricorda il codice lanciato."""
    import types
    pagina = _Pagina(m)

    class Contesto:
        request = richieste
        pages: list = []

        def add_init_script(self, *a):
            pass

        def new_page(self):
            return pagina

        def close(self):
            pass

    class Gestore:
        chromium = type("C", (), {"launch_persistent_context": staticmethod(lambda *a, **k: Contesto())})()

        def __enter__(self):
            return self

        def __exit__(self, *e):
            return False

    sync_api = types.ModuleType("playwright.sync_api")
    sync_api.sync_playwright = Gestore
    monkeypatch.setitem(sys.modules, "playwright", types.ModuleType("playwright"))
    monkeypatch.setitem(sys.modules, "playwright.sync_api", sync_api)
    return pagina


def test_axe_misura_ad_animazioni_finite(tmp_path, monkeypatch):
    """Le schermate entrano sfumando (opacity): axe lanciato a metà misura un contrasto più basso del vero, e diverso a ogni
    giro (collaudo con falsi allarmi). Prima di axe e dello scorrimento di lato le animazioni finite si portano alla fine."""
    m = _modulo()
    assert "getAnimations()" in m.FINISCI_ANIMAZIONI and "finish()" in m.FINISCI_ANIMAZIONI
    assert "Infinity" in m.FINISCI_ANIMAZIONI                 # quelle senza fine (rotelle) no: finish() darebbe errore
    pagina = _playwright_finto(monkeypatch, m, _Richieste())
    m.main(["http://127.0.0.31:8031", str(tmp_path / "foto"), "--solo-misure", "--scene", "formazione", "--larghezze", "390", "--temi", "chiaro"])
    assert m.FINISCI_ANIMAZIONI in pagina.codici
    assert pagina.codici.index(m.FINISCI_ANIMAZIONI) < pagina.codici.index(m.LANCIA_AXE)
    assert pagina.codici.index(m.FINISCI_ANIMAZIONI) < pagina.codici.index(m.SCORRE_DI_LATO)


def test_accesso_dalle_variabili_mai_stampato(tmp_path, monkeypatch, capsys):
    m = _modulo()
    aiuto = subprocess.run([sys.executable, str(PERCORSO), "--help"], capture_output=True, text=True, encoding="utf-8", timeout=60).stdout
    assert "--accesso" in aiuto and "--password" not in aiuto and "SCHIERAXI_PASSWORD" in aiuto     # mai sulla riga di comando
    richieste = _Richieste()
    _playwright_finto(monkeypatch, m, richieste)
    monkeypatch.setenv("SCHIERAXI_UTENTE", "collaudo-finto")
    monkeypatch.setenv("SCHIERAXI_PASSWORD", "password-finta-123")
    uscita = tmp_path / "foto"
    m.main(["http://127.0.0.31:8031", str(uscita), "--accesso", "--scene", "formazione", "--larghezze", "390", "--temi", "chiaro"])
    assert richieste.chiamate == [("http://127.0.0.31:8031/api/account/accedi",
                                   {"nome_utente": "collaudo-finto", "password": "password-finta-123"})]
    scritto = capsys.readouterr()
    assert "password-finta-123" not in scritto.out + scritto.err
    assert all("password-finta-123" not in f.read_text(encoding="utf-8", errors="replace") for f in uscita.iterdir())
    # accesso rifiutato: si ferma, e nemmeno l'errore dice la password
    _playwright_finto(monkeypatch, m, _Richieste(status=401))
    with pytest.raises(SystemExit) as e:
        m.main(["http://127.0.0.31:8031", str(tmp_path / "foto2"), "--accesso", "--scene", "formazione", "--larghezze", "390"])
    assert "401" in str(e.value) and "password-finta-123" not in str(e.value)
    # variabili mancanti: si ferma prima di aprire il browser e dice quali servono
    monkeypatch.delenv("SCHIERAXI_PASSWORD")
    with pytest.raises(SystemExit) as e:
        m.main(["http://127.0.0.31:8031", str(tmp_path / "foto3"), "--accesso"])
    assert "SCHIERAXI_PASSWORD" in str(e.value)


def test_solo_misure_senza_png(tmp_path, monkeypatch):
    m = _modulo()
    _playwright_finto(monkeypatch, m, _Richieste())
    uscita = tmp_path / "foto"
    codice = m.main(["http://127.0.0.31:8031", str(uscita), "--solo-misure", "--scene", "formazione,altro", "--larghezze", "390,1440",
                     "--temi", "chiaro"])
    assert codice == 0
    assert not list(uscita.glob("*.png"))
    assert (uscita / "riepilogo.txt").read_text(encoding="utf-8").count("gravi=0") == 4
    assert len(list(uscita.glob("axe-*.json"))) == 4
    # senza l'opzione le foto ci sono (il finto le scrive davvero)
    m.main(["http://127.0.0.31:8031", str(tmp_path / "con"), "--scene", "formazione", "--larghezze", "390", "--temi", "chiaro"])
    assert [p.name for p in (tmp_path / "con").glob("*.png")] == ["formazione-390-chiaro.png"]
