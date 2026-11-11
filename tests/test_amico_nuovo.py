"""Il percorso automatico «amico nuovo» (prove/amico_nuovo/percorso.py): file delle rose, riepilogo, esito, segreti.

I test non aprono il browser e non leggono `dati/fanta.sqlite`: provano le parti che non ne hanno bisogno (file delle rose
costruiti dalla lega d'esempio, righe del riepilogo, esito complessivo, argomenti, segreti mai stampati né salvati)."""
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

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
