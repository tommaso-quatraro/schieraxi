"""Avvisi per utente con due giri insieme e con errori che devono lasciare traccia (#660).

Nell'ultima ora prima della scadenza il giro dei promemoria (cron, ogni 10 minuti) e il giro dei cambi del pianificatore (dentro
il servizio) leggono e riscrivono gli stessi file di stato di un utente: senza un blocco fra processi l'utente riceveva due volte
lo stesso avviso. E gli errori dei singoli utenti o di un pezzo di un avviso non lasciavano nessuna riga nel registro.
Dati inventati, cartelle temporanee, notifiche finte (registri), niente rete. Nessuna attesa a tempo: i due giri si danno il via
con un evento o con una riga; i tempi massimi servono solo a non lasciare il test appeso.
"""
import os
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

from fanta import avvisi_utenti, consigli, notifiche, push, server
from fanta.regole import Regole

from test_avvisi_utenti import UN_ORA_PRIMA, mondo, nuovo, registro  # noqa: F401 (fixture e aiuti)
from test_notifiche import _db

RADICE = Path(__file__).resolve().parent.parent
SEGRETO = "cartella-segreta-di-amico1"

# L'altro processo: tiene il blocco degli avvisi dell'utente finché non riceve il «via».
FIGLIO = r"""
import sys
from pathlib import Path
from fanta.blocco import BloccoFile
with BloccoFile(Path(sys.argv[1]), crea_cartella=False):
    print("preso", flush=True)
    sys.stdin.readline()
"""


def test_due_giri_insieme_sullo_stesso_utente_mandano_un_solo_promemoria(mondo, registro, monkeypatch):  # noqa: F811
    """Il primo giro si ferma mentre manda il promemoria (ha letto lo stato e non l'ha ancora scritto); intanto parte il secondo
    sullo stesso utente: non deve mandarlo di nuovo."""
    nuovo("amico1", (1, "Castro"))
    in_invio, via = threading.Event(), threading.Event()
    vero = push.invia

    def lento(*a, **k):
        if not in_invio.is_set():
            in_invio.set()
            via.wait(30)
        return vero(*a, **k)
    monkeypatch.setattr(push, "invia", lento)
    monkeypatch.setattr(avvisi_utenti, "ATTESA_BLOCCO", 0, raising=False)
    esiti = {}

    def giro(nome):
        esiti[nome] = avvisi_utenti.esegui("promemoria", _db("2026-10-28 18:30"), UN_ORA_PRIMA)
    primo = threading.Thread(target=giro, args=("primo",))
    primo.start()
    try:
        assert in_invio.wait(30)                                  # il primo giro sta mandando
        secondo = threading.Thread(target=giro, args=("secondo",))
        secondo.start()
        secondo.join(30)
        assert not secondo.is_alive()
    finally:
        via.set()
        primo.join(30)
    assert [t for _, t, _ in registro.web] == ["SchieraXI · formazione tra un'ora"]
    assert esiti["secondo"] == ({}, {})                            # utente occupato: non è un errore, passa al giro dopo
    avvisi_utenti.esegui("promemoria", mondo.db, UN_ORA_PRIMA)
    assert len(registro.web) == 1                                  # e il giro dopo sa che è già partito


def test_utente_tenuto_da_un_altro_processo_passa_al_giro_dopo_e_gli_altri_ricevono(mondo, registro, monkeypatch, caplog):  # noqa: F811
    """Un processo vero tiene il blocco degli avvisi di amico1: il giro salta solo lui (una riga nel registro, con il numero),
    amico2 riceve. Finito l'altro, al giro dopo amico1 riceve il suo promemoria, una volta."""
    a, b = nuovo("amico1", (1, "Castro")), nuovo("amico2", (2, "Bonny"))
    figlio = subprocess.Popen([sys.executable, "-c", FIGLIO, str(a.cartella / "avvisi.lock")], cwd=RADICE, text=True,
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE, env={**os.environ, "PYTHONPATH": str(RADICE)})
    guardia = threading.Timer(60, figlio.kill)       # solo se il figlio resta appeso: il test non deve bloccare la suite
    guardia.start()
    try:
        assert figlio.stdout.readline().strip() == "preso"
        monkeypatch.setattr(avvisi_utenti, "ATTESA_BLOCCO", 0, raising=False)
        with caplog.at_level("WARNING", logger="fanta.avvisi_utenti"):
            esiti, errori = avvisi_utenti.esegui("promemoria", mondo.db, UN_ORA_PRIMA)
        assert [chi for chi, _, _ in registro.web] == [b.cartella.name]
        assert errori == {} and set(esiti) == {"amico2"}
        righe = [r.getMessage() for r in caplog.records if f"utente {a.utente_id}" in r.getMessage()]
        assert len(righe) == 1 and "amico1" not in caplog.text
        figlio.stdin.write("via\n")
        figlio.stdin.flush()
        assert figlio.wait(30) == 0
    finally:
        guardia.cancel()
        if figlio.poll() is None:
            figlio.kill()
            figlio.wait()
        figlio.stdin.close()
        figlio.stdout.close()
    avvisi_utenti.esegui("promemoria", mondo.db, UN_ORA_PRIMA)
    assert sorted(chi for chi, _, _ in registro.web) == sorted([a.cartella.name, b.cartella.name])


def test_ordine_del_giro_tenuto_da_un_altro_processo_non_si_sovrascrive(mondo, registro, monkeypatch, caplog, tmp_path):  # noqa: F811
    """L'ordine del giro sta in un file solo per i due giri (cambi e promemoria): chi lo riscrive mentre l'altro lo tiene
    cancellerebbe l'ordine dell'altro. Occupato: non si scrive, una riga nel registro, e gli avvisi partono lo stesso."""
    from fanta.blocco import BloccoFile
    nuovo("amico1", (1, "Castro"))
    giro = tmp_path / "giro.json"
    giro.write_text('{"cambi": {"1": 7}}', encoding="utf-8")
    monkeypatch.setattr(avvisi_utenti, "ATTESA_GIRO", 0, raising=False)
    with caplog.at_level("WARNING", logger="fanta.avvisi_utenti"), BloccoFile(tmp_path / "giro.json.lock"):
        esiti, errori = avvisi_utenti.esegui("promemoria", mondo.db, UN_ORA_PRIMA, avvisi_utenti.utenti_attivi(), file_giro=giro)
    assert errori == {} and len(esiti["amico1"]) == 1
    assert giro.read_text(encoding="utf-8") == '{"cambi": {"1": 7}}'
    assert "TimeoutError" in caplog.text


# ---------------------------------------------------------------- errori che lasciano traccia
def test_promemoria_con_l_avviso_prima_della_scadenza_rotto_lascia_traccia_e_parte(mondo, registro, monkeypatch, caplog):  # noqa: F811
    """L'avviso «cambia la formazione» di amico1 alza un errore: il suo promemoria parte lo stesso, quello di amico2 anche;
    l'errore va nel ritorno del giro (il comando lo stampa) e nel registro, con il numero dell'utente e il solo tipo."""
    a = nuovo("amico1", (1, "Castro"))
    nuovo("amico2", (2, "Bonny"))
    vero = notifiche.avviso_scadenza

    def rotto(db, regole, rose, adesso, file_stato, *r, **k):
        if file_stato.parent == a.cartella:
            raise OSError(f"disco pieno: {SEGRETO}")
        return vero(db, regole, rose, adesso, file_stato, *r, **k)
    monkeypatch.setattr(notifiche, "avviso_scadenza", rotto)
    with caplog.at_level("WARNING", logger="fanta"):
        esiti, errori = avvisi_utenti.esegui("promemoria", mondo.db, UN_ORA_PRIMA)
    assert len(esiti["amico1"]) == 1 and len(esiti["amico2"]) == 1          # i promemoria partono comunque
    assert set(errori) == {"amico1"} and "OSError" in errori["amico1"] and SEGRETO not in errori["amico1"]
    righe = [r.getMessage() for r in caplog.records if f"utente {a.utente_id}" in r.getMessage()]
    assert len(righe) == 1 and "OSError" in righe[0]
    assert SEGRETO not in caplog.text and "amico1" not in caplog.text


def test_cambi_vicino_alla_scadenza_con_l_avviso_rotto_lascia_traccia_e_parte(mondo, registro, monkeypatch, caplog):  # noqa: F811
    """Nell'ultima ora i cambi provano prima l'avviso «cambia la formazione»: se alza un errore, l'avviso dei cambi parte lo stesso
    e l'errore si vede (ritorno del giro e registro)."""
    a = nuovo("amico1", (1, "Castro"))
    avvisi_utenti.esegui("cambi", mondo.db, UN_ORA_PRIMA)                  # primo controllo: solo memorizza

    def rotto(*a, **k):
        raise OSError(f"disco pieno: {SEGRETO}")
    monkeypatch.setattr(notifiche, "avviso_scadenza", rotto)
    mondo.prev.loc[1, ["stato", "percentuale"]] = ["panchina", 30.0]
    with caplog.at_level("WARNING", logger="fanta"):
        esiti, errori = avvisi_utenti.esegui("cambi", mondo.db, UN_ORA_PRIMA)
    assert [t for _, t, _ in registro.web] == ["SchieraXI · cambia un titolare"] and len(esiti["amico1"]) == 1
    assert set(errori) == {"amico1"} and "OSError" in errori["amico1"]
    assert any(f"utente {a.utente_id}" in r.getMessage() and "OSError" in r.getMessage() for r in caplog.records)
    assert SEGRETO not in caplog.text


def test_promemoria_senza_account_coi_dettagli_rotti_lascia_una_riga(tmp_path, monkeypatch, caplog):
    """Senza account: se i dettagli della formazione non si calcolano il promemoria parte lo stesso, e nel registro resta una riga
    con il tipo d'errore (mai il messaggio)."""
    from test_notifiche import ROSE
    mandati = []
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: "2026-27")
    monkeypatch.setattr(consigli, "prossima_giornata", lambda db, st, adesso=None: 9)

    def rotta(*a, **k):
        raise RuntimeError(f"formazione: {SEGRETO}")
    monkeypatch.setattr(consigli, "formazione", rotta)
    with caplog.at_level("WARNING", logger="fanta.notifiche"):
        righe = notifiche.promemoria(_db("2026-10-28 18:30"), Regole(), ROSE, datetime(2026, 10, 28, 17, 35), tmp_path / "p.json",
                                     lambda *a, **k: mandati.append(a) or True, {})
    assert len(righe) == 1 and len(mandati) == 1
    assert "RuntimeError" in caplog.text and SEGRETO not in caplog.text


def test_giro_vicino_alla_scadenza_un_utente_in_errore_lascia_la_riga_e_gli_altri_ricevono(mondo, registro, monkeypatch, caplog):  # noqa: F811
    """I giri a 60, 30 e 15 minuti del servizio (`_dopo_giro_leggero`): un utente in errore lascia una riga nel registro (numero e
    tipo d'errore, mai nomi né messaggi) e gli avvisi degli altri partono."""
    a, b = nuovo("amico1", (1, "Castro")), nuovo("amico2", (2, "Bonny"))
    serviti = []

    def lavoro(att, db, r, adesso):
        if att.utente.id == a.utente_id:
            raise OSError(f"disco pieno: {SEGRETO}")
        serviti.append(att.utente.id)
        return ["avviso"]
    monkeypatch.setitem(avvisi_utenti._LAVORI, "cambi", lavoro)
    monkeypatch.setattr(server, "_db", lambda: mondo.db)
    with caplog.at_level("WARNING", logger="fanta"):
        server._dopo_giro_leggero()
    assert serviti == [b.utente_id]
    righe = [r.getMessage() for r in caplog.records if f"utente {a.utente_id}" in r.getMessage()]
    assert len(righe) == 1 and "OSError" in righe[0]
    assert SEGRETO not in caplog.text and "amico1" not in caplog.text
