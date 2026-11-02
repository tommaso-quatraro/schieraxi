"""Permessi dei file con segreti: chiave VAPID, iscrizioni push e relativo log leggibili solo dal proprietario (600);
i log degli script del server nascono riservati (umask 077)."""
import json
import os
import stat
from pathlib import Path

import pytest

from fanta import push

SOLO_POSIX = pytest.mark.skipif(os.name == "nt", reason="i bit dei permessi esistono solo su Linux/macOS")
SUB = {"endpoint": "https://push.example.org/abc", "keys": {"p256dh": "AAAA", "auth": "BBBB"}}
SCRIPT = Path(__file__).resolve().parent.parent / "script" / "server"


def _modo(p: Path) -> int:
    return stat.S_IMODE(p.stat().st_mode)


@SOLO_POSIX
def test_vapid_e_iscrizioni_nascono_600_anche_con_umask_permissivo(tmp_path):
    vecchia = os.umask(0o000)                      # attacco: servizio con umask aperto, tutti leggerebbero tutto
    try:
        chiave = push.chiavi(tmp_path / "vapid.json")
        push.iscrivi(SUB, tmp_path / "push.json")
        push.togli("https://altro.example.org/x", tmp_path / "push.json")
    finally:
        os.umask(vecchia)
    assert chiave["privata"]
    for nome in ("vapid.json", "push.json"):
        assert _modo(tmp_path / nome) == 0o600, nome
    assert not list(tmp_path.glob("*.tmp"))        # il temporaneo non resta in giro


@SOLO_POSIX
def test_i_file_vecchi_leggibili_da_tutti_vengono_sistemati(tmp_path):
    v, i = tmp_path / "vapid.json", tmp_path / "push.json"
    v.write_text(json.dumps(push.chiavi(tmp_path / "x.json")))
    i.write_text(json.dumps([SUB]))
    os.chmod(v, 0o644)
    os.chmod(i, 0o644)
    push.chiavi(v)
    assert push.iscrizioni(i) == [SUB]
    assert _modo(v) == 0o600 and _modo(i) == 0o600


@SOLO_POSIX
def test_il_log_delle_notifiche_e_riservato(tmp_path, monkeypatch):
    monkeypatch.setattr(push, "FILE_ISCRIZIONI", tmp_path / "push.json")
    vecchia = os.umask(0o000)
    try:
        push._annota("errore finto")
    finally:
        os.umask(vecchia)
    assert _modo(tmp_path / "push.log") == 0o600


def test_scrittura_riservata_funziona_ovunque(tmp_path):
    """Su ogni sistema: il contenuto è giusto e non restano file temporanei."""
    push.scrivi_sicuro(tmp_path / "a" / "b.json", '{"x": 1}')
    assert json.loads((tmp_path / "a" / "b.json").read_text(encoding="utf-8")) == {"x": 1}
    assert not list((tmp_path / "a").glob("*.tmp"))


@pytest.mark.skipif(not SCRIPT.is_dir(), reason="script/server non fa parte della copia pubblica")
def test_gli_script_del_server_creano_log_riservati():
    for nome in ("aggiorna.sh", "backup-serale.sh", "promemoria.sh"):
        assert "umask 077" in (SCRIPT / nome).read_text(encoding="utf-8"), nome
    t = (SCRIPT / "aggiorna-app.sh").read_text(encoding="utf-8")
    assert 'umask 077; : >> "$LOG"' in t and 'chmod 600 "$LOG"' in t


def test_iscrizioni_insieme_non_si_perdono(tmp_path, monkeypatch):
    """Due dispositivi che si iscrivono (o un invio che toglie una iscrizione scaduta) nello stesso momento: leggere-modificare-scrivere
    senza blocco faceva vincere solo l ultimo e le altre iscrizioni sparivano."""
    import threading
    import time
    originale = push.scrivi_sicuro

    def lenta(percorso, testo):
        time.sleep(0.05)                               # allarga la finestra fra lettura e scrittura
        originale(percorso, testo)
    monkeypatch.setattr(push, "scrivi_sicuro", lenta)
    file = tmp_path / "push.json"
    errori = []

    def iscrivi(n):
        try:
            push.iscrivi({"endpoint": f"https://8.8.8.8/p/{n}", "keys": {"p256dh": "AAAA", "auth": "BBBB"}}, file)
        except Exception as e:  # noqa: BLE001
            errori.append(e)
    fili = [threading.Thread(target=iscrivi, args=(n,)) for n in range(4)]
    for f in fili:
        f.start()
    for f in fili:
        f.join()
    assert not errori
    assert sorted(s["endpoint"] for s in push.iscrizioni(file)) == [f"https://8.8.8.8/p/{n}" for n in range(4)]
