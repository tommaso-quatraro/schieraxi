"""Il percorso automatico «amico nuovo» (prove/amico_nuovo/percorso.py): file delle rose, riepilogo, esito, segreti.

I test non aprono il browser e non leggono `dati/fanta.sqlite`: provano le parti che non ne hanno bisogno (file delle rose
costruiti dalla lega d'esempio, righe del riepilogo, esito complessivo, argomenti, segreti mai stampati né salvati)."""
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from fanta import rose

RADICE = Path(__file__).resolve().parent.parent
PERCORSO = RADICE / "prove" / "amico_nuovo" / "percorso.py"
ROSE_ESEMPIO = RADICE / "lega" / "esempio" / "rose.json"


def _modulo():
    spec = importlib.util.spec_from_file_location("amico_nuovo_in_prova", PERCORSO)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)          # Playwright si importa solo quando si apre il browser: qui non c'è
    return m


def _squadre_esempio() -> dict[str, int]:
    dati = json.loads(ROSE_ESEMPIO.read_text(encoding="utf-8"))
    return {s["nome"]: len(s["giocatori"]) for s in dati["squadre"]}


def _celle(griglie) -> set[str]:
    return {c for _, g in griglie for riga in g for c in riga if c}


@pytest.mark.parametrize("formato", ["testo", "rosters", "excel"])
def test_file_rose_hanno_tutte_le_squadre_d_esempio(tmp_path, formato):
    m = _modulo()
    f = m.file_rose(ROSE_ESEMPIO, formato, tmp_path)
    assert f.is_file() and f.parent == tmp_path                  # sempre nella cartella data, mai nel repository
    griglie = rose.leggi_griglie(f)
    squadre = _squadre_esempio()
    assert len(squadre) == 10
    assert set(squadre) <= _celle(griglie)
    righe = [r for _, g in griglie for r in g]
    if formato == "rosters":                                     # una riga «squadra,codice,costo» per giocatore
        assert sum(1 for r in righe if rose._riga_rosters([c for c in r if c != ""])) == sum(squadre.values())
    if formato == "testo":                                       # intestazione, una riga per squadra, una per giocatore
        assert [c.lower() for c in righe[0]] == ["ruolo", "nome", "club", "prezzo"]
        giocatori = [r for r in righe[1:] if len([c for c in r if c]) == 4]
        assert len(giocatori) == sum(squadre.values())


def test_formato_sconosciuto_rifiutato(tmp_path):
    with pytest.raises(ValueError):
        _modulo().file_rose(ROSE_ESEMPIO, "pdf", tmp_path)


def test_file_sbagliato_riconosce_la_frase_senza_rose_del_server():
    # La frase vera del server (#577 l'ha accorciata: «Non ho trovato rose nel file…»), e quella di prima per un server remoto
    # non ancora aggiornato: il passo «file_sbagliato» le riconosce entrambe; un altro errore no.
    m = _modulo()
    assert m.dice_nessuna_rosa(rose.NESSUNA_ROSA)
    assert m.dice_nessuna_rosa("Non ho trovato nessuna rosa nel file. I formati che leggo sono: …")
    assert not m.dice_nessuna_rosa("Il file è troppo grande")


def test_riga_del_riepilogo():
    m = _modulo()
    assert m.riga("rose", 4.3, 3, 0, 0, "ok") == "rose secondi=4.3 tocchi=3 errori-console=0 gravi=0 esito=ok"
    assert m.riga("rientro", 12.04, 9, 1, 2, "errore:TimeoutError") == \
        "rientro secondi=12.0 tocchi=9 errori-console=1 gravi=2 esito=errore:TimeoutError"


def test_esito_rosso_se_un_passo_non_e_ok():
    m = _modulo()
    ok = [m.riga(p, 1, 1, 0, 0, "ok") for p in m.PASSI if p != "rose"]
    assert m.esito_complessivo(ok + [m.riga("rose", 1, 1, 0, 0, "bloccato")]) == (False, ["rose: bloccato"])
    assert m.esito_complessivo(ok + [m.riga("rose", 1, 1, 0, 0, "ok")]) == (True, [])
    assert m.esito_complessivo([])[0] is False                 # nessun passo fatto non è un successo


def test_errori_console_rendono_rosso():
    m = _modulo()
    assert m.esito_complessivo([m.riga("invito", 1, 0, 2, 0, "ok")]) == (False, ["invito: errori-console=2"])
    assert m.esito_complessivo([m.riga("rose", 1, 0, 0, 1, "ok")]) == (False, ["rose: gravi=1"])


def test_passi_e_passi_locali():
    m = _modulo()
    assert m.PASSI == ("invito", "registrazione", "recupero_salvato", "installabile", "rose", "squadra", "tempi", "regole",
                       "formazione", "rientro", "elimina")
    assert m.PASSI_LOCALI == ("invito_usato", "file_sbagliato")
    assert len(m.ordine(locale=True)) == 13 and set(m.ordine(locale=True)) == set(m.PASSI) | set(m.PASSI_LOCALI)
    assert m.ordine(locale=False) == tuple(p for p in m.ordine(locale=True) if p in m.PASSI)
    assert m.ordine(locale=True)[-1] == "elimina"              # l'account si cancella sempre per ultimo


def test_risposte_d_errore_attese_solo_dove_servono():
    m = _modulo()
    assert m.risposta_attesa("invito", "/api/account/me", 401)              # pagina d'accesso prima di registrarsi
    assert m.risposta_attesa("invito_usato", "/api/account/registra", 403)
    assert not m.risposta_attesa("rose", "/api/account/me", 401)
    assert not m.risposta_attesa("rose", "/api/rose/anteprima/file", 500)


def test_manifesto_per_la_home():
    m = _modulo()
    buono = {"name": "SchieraXI", "display": "standalone", "start_url": "/?da=app",
             "icons": [{"src": "a.png", "sizes": "192x192"}, {"src": "b.png", "sizes": "512x512"}]}
    assert m.controlla_manifesto(buono) == []
    assert m.controlla_manifesto(json.loads((RADICE / "fanta" / "web" / "manifest.webmanifest").read_text(encoding="utf-8"))) == []
    assert m.controlla_manifesto(None) == ["manifesto assente o illeggibile"]
    rotto = {"display": "browser", "icons": [{"sizes": "192x192"}]}
    assert len(m.controlla_manifesto(rotto)) == 4       # nome, icona 512, schermo intero, start_url


def test_oscura_toglie_ogni_segreto():
    m = _modulo()
    testo = "invito ABCD-1234 a https://prova.esempio.invalid/x con pw s3greta-lunga e codice K9K9K9"
    pulito = m.oscura(testo, ["ABCD-1234", "https://prova.esempio.invalid", "prova.esempio.invalid", "s3greta-lunga", "K9K9K9", ""])
    for segreto in ("ABCD-1234", "prova.esempio.invalid", "s3greta-lunga", "K9K9K9"):
        assert segreto not in pulito


def _lancia(argv, env_extra=None, cwd=None):
    env = {k: v for k, v in os.environ.items() if not k.startswith("SCHIERAXI_")}
    env.update(env_extra or {})
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run([sys.executable, str(PERCORSO), *argv], capture_output=True, text=True, encoding="utf-8",
                          env=env, cwd=cwd or RADICE, timeout=120)


def test_segreti_mai_nell_uscita(tmp_path):
    invito, indirizzo = "INVITO-SEGRETO-4242", "https://prova.esempio.invalid"
    uscita = tmp_path / "uscita"
    r = _lancia([str(uscita), "--remoto", "--a-secco", "--formato", "excel"],
                {"SCHIERAXI_INVITO": invito, "SCHIERAXI_INDIRIZZO": indirizzo})
    assert r.returncode == 0, r.stderr
    tutto = r.stdout + r.stderr
    for segreto in (invito, indirizzo, "prova.esempio.invalid"):
        assert segreto not in tutto
    file = [f for f in uscita.rglob("*") if f.is_file()]
    assert any(f.suffix == ".xlsx" for f in file)                 # il file delle rose c'è, nella cartella data
    for f in file:
        dati = f.read_bytes()
        for segreto in (invito, "prova.esempio.invalid"):
            assert segreto.encode() not in dati and segreto.encode("utf-16-le") not in dati
    for passo in _modulo().ordine(locale=False):
        assert passo in r.stdout                                  # a secco stampa i passi che farebbe


def test_a_secco_locale_prepara_il_file_e_stampa_tredici_passi(tmp_path):
    r = _lancia([str(tmp_path / "u"), "--locale", "--a-secco", "--formato", "testo", "--telefono", "android",
                 "--larghezza", "360"])
    assert r.returncode == 0, r.stderr
    assert (tmp_path / "u" / "rose.txt").is_file()
    for passo in _modulo().ordine(locale=True):
        assert passo in r.stdout


def test_remoto_senza_variabili_esce_con_2_e_le_nomina(tmp_path):
    r = _lancia([str(tmp_path / "u"), "--remoto", "--a-secco"])
    assert r.returncode == 2
    assert "SCHIERAXI_INDIRIZZO" in r.stderr and "SCHIERAXI_INVITO" in r.stderr


def test_argomenti_sbagliati_escono_con_2(tmp_path):
    assert _lancia([str(tmp_path / "u"), "--locale", "--remoto", "--a-secco"]).returncode == 2
    assert _lancia([str(tmp_path / "u"), "--a-secco"]).returncode == 2
    assert _lancia([str(tmp_path / "u"), "--locale", "--larghezza", "500", "--a-secco"]).returncode == 2
    assert _lancia([str(tmp_path / "u"), "--locale", "--formato", "pdf", "--a-secco"]).returncode == 2


def test_cartella_nel_repository_rifiutata(tmp_path):
    dentro = RADICE / "prova-amico-nuovo-da-togliere"
    r = _lancia([str(dentro), "--locale", "--a-secco"])
    assert r.returncode == 2
    assert not dentro.exists()                                    # nemmeno creata
    with pytest.raises(SystemExit):
        _modulo().foto.fuori_dal_repository(RADICE / "foto")


def test_senza_finestra_chrome_di_sistema_e_riuso_di_foto():
    testo = PERCORSO.read_text(encoding="utf-8")
    assert "headless=True" in testo and "headless=False" not in testo
    assert 'channel="chrome"' in testo
    assert "prove/foto_web/foto.py" in testo.replace("\\", "/") or '"foto_web"' in testo
    for nome in ("fuori_dal_repository", "ServerDiProva", "prepara_copia", "ambiente_server", "gravi"):
        assert f"foto.{nome}" in testo or f"{nome} = foto." in testo                # riusati, non copiati
    assert "def fuori_dal_repository" not in testo and "class ServerDiProva" not in testo
    assert "secrets.token_urlsafe(18)" in testo


def test_freno_contro_la_produzione(tmp_path):
    m = _modulo()
    assert m.indirizzo_di_prova("https://prova.esempio.invalid")
    assert m.indirizzo_di_prova("https://PROVA.esempio.invalid/")
    for altrove in ("https://app.esempio.invalid", "https://esempio.invalid", "http://localhost:8000", "https://prova.",
                    "https://miaprova.esempio.invalid", "non è un indirizzo", ""):
        assert not m.indirizzo_di_prova(altrove), altrove
    indirizzo = "https://app.esempio.invalid"
    r = _lancia([str(tmp_path / "u"), "--remoto", "--a-secco"], {"SCHIERAXI_INVITO": "INVITO-9999", "SCHIERAXI_INDIRIZZO": indirizzo})
    assert r.returncode == 2 and "prova." in r.stderr
    assert "app.esempio.invalid" not in r.stdout + r.stderr and "INVITO-9999" not in r.stdout + r.stderr
    assert not (tmp_path / "u").exists()                          # si ferma prima di preparare qualunque file


class _Risposta:
    def __init__(self, status):
        self.status = status


class _Richieste:
    """Il `request` di Playwright, finto: l'accesso riesce solo con la password giusta; registra le chiamate."""

    def __init__(self, giusta, elimina=200):
        self.giusta, self.stato_elimina, self.chiamate = giusta, elimina, []

    def post(self, indirizzo, data=None, headers=None, **k):
        self.chiamate.append((indirizzo.rsplit("/", 1)[1], data.get("password")))
        assert headers == {"X-Fanta": "1"}
        if indirizzo.endswith("/accedi"):
            return _Risposta(200 if data["password"] == self.giusta else 401)
        return _Risposta(self.stato_elimina)


def _giro_finto(password_usate):
    return SimpleNamespace(nome="amico-123456", base_api="http://127.0.0.5:8005", password_usate=list(password_usate),
                           creato=True)


def test_pulizia_prova_tutte_le_password_del_giro():
    m = _modulo()
    richieste = _Richieste(giusta="prima-del-rientro")
    assert m.pulisci(_giro_finto(["prima-del-rientro", "dopo-il-rientro"]), richieste)
    assert richieste.chiamate == [("accedi", "dopo-il-rientro"), ("accedi", "prima-del-rientro"),
                                  ("elimina", "prima-del-rientro")]


def test_pulizia_non_scambia_un_accesso_rifiutato_per_cancellato():
    m = _modulo()
    assert not m.pulisci(_giro_finto(["a", "b"]), _Richieste(giusta="nessuna"))
    assert not m.pulisci(_giro_finto(["a"]), _Richieste(giusta="a", elimina=500))


def test_account_non_cancellato_avvisa_con_il_nome_senza_password(capsys):
    m = _modulo()
    g = _giro_finto(["password-segreta-1", "password-segreta-2"])
    m.chiudi_account(g, _Richieste(giusta="nessuna"))
    err = capsys.readouterr().err
    assert "ATTENZIONE" in err and "amico-123456" in err and "password-segreta" not in err
    g = _giro_finto(["password-segreta-1"])
    m.chiudi_account(g, _Richieste(giusta="password-segreta-1"))
    assert g.creato is False and capsys.readouterr().err == ""


class _Pagina:
    """Una pagina di Playwright finta: axe trova una violazione che riporta un segreto, la foto è un file finto."""

    def __init__(self, segreto):
        self.segreto = segreto

    def on(self, *a):
        pass

    def set_default_timeout(self, *a):
        pass

    def wait_for_timeout(self, *a):
        pass

    def locator(self, selettore):
        return selettore

    def screenshot(self, path, **k):
        Path(path).write_bytes(b"png")

    def evaluate(self, codice, *argomenti):
        if "typeof stato" in codice:
            return False                                          # pagina d'accesso: niente attesa dell'app
        if argomenti:                                             # LANCIA_AXE
            return [{"id": "esempio", "impact": "minor", "help": "", "n": 1,
                     "nodi": [{"target": "#ac-invito", "sommario": f"valore {self.segreto}"}]}]
        return None


def test_file_scritti_davvero_senza_segreti(tmp_path):
    m = _modulo()
    invito, password, recupero = "INVITO-ABCD-1234", "pw-segreta-di-prova-0001", "RECUP-ZZZZ-9999"
    segreti = [invito]
    g = m.Giro(SimpleNamespace(pages=[_Pagina(recupero)]), "http://localhost:8005", tmp_path, segreti)
    g.password = password
    g.segreto(password, recupero)

    def passo(g):
        g.nota(f"ho visto {invito} e {password}")
        raise m.Bloccato(f"rifiutato il codice {recupero}")

    r = g.fai(3, "rientro", passo)
    assert r.endswith("esito=bloccato") and invito not in r
    m.scrivi_dettagli(g, tmp_path)
    log = tmp_path / "originale" / "server.log"
    log.parent.mkdir()
    log.write_text(f'GET /?invito={invito} HTTP/1.1" 200\nrecupero {recupero}\n', encoding="utf-8")
    m.copia_registro(log, tmp_path, segreti)
    scritti = {f.name: f.read_text(encoding="utf-8")
               for f in (tmp_path / "dettagli.txt", tmp_path / "axe-03-rientro.json", tmp_path / "server.log")}
    assert "invito=«nascosto»" in scritti["server.log"] and "rifiutato il codice «nascosto»" in scritti["dettagli.txt"]
    for nome, testo in scritti.items():
        for segreto in (invito, password, recupero):
            assert segreto not in testo, (nome, segreto)
    assert (tmp_path / "03-rientro.png").is_file()


# ---- #598: nel passo `installabile` la nota «primo avvio aperto / NON aperto» guardava appena l'app era pronta, ma il foglio
# del primo avvio si apre dopo (prima la risposta del server sullo stato della guida): la foto dello stesso passo lo mostrava aperto.
class _Nodo:
    """Un elemento della pagina finta: il foglio del primo avvio (`.pa-capo`) compare quando l'orologio arriva al ritardo."""

    def __init__(self, pagina, selettore):
        self.pagina, self.selettore = pagina, selettore

    @property
    def first(self):
        return self

    def _quando(self):
        return self.pagina.ritardo_ms if ".pa-capo" in self.selettore else 0       # None = non compare mai

    def count(self):
        quando = self._quando()
        return int(quando is not None and self.pagina.adesso_ms >= quando)

    def is_visible(self):
        return bool(self.count())

    def wait_for(self, state="visible", timeout=None):
        assert state == "visible"
        limite = self.pagina.adesso_ms + (self.pagina.limite_ms if timeout is None else timeout)
        quando = self._quando()
        if quando is not None and quando <= limite:
            self.pagina.adesso_ms = max(self.pagina.adesso_ms, quando)
            return
        self.pagina.adesso_ms = limite
        raise TimeoutError(f"Timeout {timeout}ms exceeded.")             # lo stesso nome dell'errore di Playwright

    def inner_text(self):
        return "Benvenuto in SchieraXI"


class _PaginaLenta:
    """La web aperta dalla Home, finta e con un orologio suo (niente attese vere): service worker e app pronti subito, il
    foglio del primo avvio dopo `ritardo_ms` (None = mai)."""

    def __init__(self, ritardo_ms):
        self.ritardo_ms, self.adesso_ms, self.limite_ms = ritardo_ms, 0, 30000

    def on(self, *a):
        pass

    def set_default_timeout(self, ms):
        self.limite_ms = ms

    def goto(self, *a, **k):
        pass

    def wait_for_function(self, *a, **k):
        pass

    def wait_for_timeout(self, ms):
        self.adesso_ms += ms

    def locator(self, selettore):
        return _Nodo(self, selettore)

    def evaluate(self, codice, *a):
        if "manifest" in codice:
            return {"name": "SchieraXI", "display": "standalone", "start_url": "/",
                    "icons": [{"sizes": "192x192"}, {"sizes": "512x512"}]}
        return {"icona": 200, "capace": "yes", "titolo": "SchieraXI"}


class _Contesto:
    def __init__(self, nuova):
        self.pages, self.nuova = [_PaginaLenta(None)], nuova

    def new_page(self):
        return self.nuova

    def new_cdp_session(self, pagina):
        return SimpleNamespace(send=lambda *a: {"installabilityErrors": []})


def _installabile(tmp_path, ritardo_ms):
    m = _modulo()
    nuova = _PaginaLenta(ritardo_ms)
    g = m.Giro(_Contesto(nuova), "http://localhost:8005", tmp_path, [])
    g.passo = "installabile"
    m.passo_installabile(g)
    nota = [d for d in g.dettagli if "primo avvio" in d]
    assert len(nota) == 1, g.dettagli
    return nota[0], nuova.adesso_ms


def test_installabile_aspetta_il_primo_avvio_che_si_apre_dopo_l_app(tmp_path):
    nota, _ = _installabile(tmp_path, ritardo_ms=1500)
    assert "primo avvio aperto" in nota and "NON aperto" not in nota


def test_installabile_dice_non_aperto_solo_dopo_il_tempo_massimo(tmp_path):
    nota, atteso_ms = _installabile(tmp_path, ritardo_ms=None)
    assert "primo avvio NON aperto" in nota
    assert 5000 <= atteso_ms <= 30000                    # ha aspettato, ma non all'infinito


def test_installabile_con_il_primo_avvio_gia_aperto_non_aspetta(tmp_path):
    nota, atteso_ms = _installabile(tmp_path, ritardo_ms=0)
    assert "primo avvio aperto" in nota and atteso_ms == 0
