"""Limiti sull'invio degli avvisi (#515, requisito R4 di #483).

- ogni invio di un avviso verso un servizio di notifica ha un tempo massimo totale (`limiti.MAX_SECONDI_INVIO`), anche con un
  servizio che risponde un byte alla volta (dove il tempo massimo di ogni singola lettura non basta);
- un destinatario lento non ferma gli altri: né gli altri dispositivi dello stesso utente né gli utenti dopo nel giro;
- la prova degli avvisi ha un tetto all'ora per utente (`limiti.MAX_PROVE_AVVISI_ORA`); senza account nessun tetto;
- gli script del server fermano i giri degli avvisi dopo un tempo massimo (`timeout`), lo scrivono nel log e vanno avanti.
Mai l'orologio vero: il tempo dell'invio lo fa scorrere il servizio finto (un secondo per ogni byte che manda). I servizi finti
stanno solo su 127.0.0.1. Cartelle temporanee e dati inventati."""
import base64
import http.client
import json
import os
import socket
import threading
import time
from datetime import datetime
from types import SimpleNamespace

import pytest

from fanta import avvisi_utenti, limiti, push, scarica_immagine

from test_limiti import ambiente, nuovo_utente  # noqa: F401 (fixture e utente di prova)
from test_script_server import BASH, _casa_aggiorna, _lancia, _msys, _scrivi, _stub, con_bash, SCRIPT
from test_server import client  # noqa: F401 (fixture: un solo utente, senza account)

ORA_FISSA = datetime(2026, 11, 8, 10, 15)          # il tetto orario non deve cambiare ora a metà test
BYTE_LENTI = 200                                   # il servizio lento, lasciato fare, risponde per 200 «secondi»
TEMPO_INVIO = 20                                   # secondi in tutto per un invio (valore deciso nel piano, G3)
PROVE_ORA = 5                                      # prove degli avvisi all'ora per utente (valore deciso nel piano, G3)


class Orologio:
    """Il tempo dell'invio: lo fa scorrere il servizio lento, un secondo per ogni byte che manda."""

    def __init__(self):
        self.t = 0.0
        self._blocco = threading.Lock()

    def avanza(self):
        with self._blocco:
            self.t += 1

    def __call__(self):
        return self.t


def _leggi_richiesta(conn) -> bool:
    """Legge una richiesta intera; False se la connessione si chiude prima (nessun avviso è arrivato)."""
    dati = b""
    while b"\r\n\r\n" not in dati:
        pezzo = conn.recv(4096)
        if not pezzo:
            return False
        dati += pezzo
    testa, _, corpo = dati.partition(b"\r\n\r\n")
    lunghezza = next((int(r.split(b":")[1]) for r in testa.split(b"\r\n") if r.lower().startswith(b"content-length:")), 0)
    while len(corpo) < lunghezza:
        pezzo = conn.recv(4096)
        if not pezzo:
            return False
        corpo += pezzo
    return True


class Servizio:
    """Un finto servizio di notifica su 127.0.0.1 (http semplice: il certificato non c'entra con i tempi).
    `lento`: risponde un byte alla volta; `ok`: 201 subito; `scaduta`: 410 subito (iscrizione da togliere);
    `rifiuta`: 503 subito (servizio che non accetta l'avviso)."""

    def __init__(self, orologio, modo):
        self.orologio, self.modo = orologio, modo
        self.arrivi: list[float] = []              # quando (tempo dell'invio) è arrivata ogni richiesta
        self.finito_da_solo = False                # il lento ha mandato tutti i suoi byte: nessuno l'ha interrotto
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(8)
        self.porta = self.sock.getsockname()[1]
        threading.Thread(target=self._servi, daemon=True).start()

    def _servi(self):
        while True:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            threading.Thread(target=self._rispondi, args=(conn,), daemon=True).start()

    def _rispondi(self, conn):
        with conn:
            conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            if not _leggi_richiesta(conn):
                return
            self.arrivi.append(self.orologio.t)
            if self.modo == "lento":
                risposta = (b"HTTP/1.1 201 Created\r\nX-Lento: " + b"a" * BYTE_LENTI)[:BYTE_LENTI]
                for b in risposta:
                    self.orologio.avanza()
                    try:
                        conn.sendall(bytes([b]))
                    except OSError:
                        return
                    time.sleep(0.01)
                self.finito_da_solo = True
                return
            stato = {"ok": b"201 Created", "scaduta": b"410 Gone", "rifiuta": b"503 Service Unavailable"}[self.modo]
            conn.sendall(b"HTTP/1.1 " + stato + b"\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")

    def chiudi(self):
        self.sock.close()


@pytest.fixture
def orologio(monkeypatch):
    o = Orologio()
    monkeypatch.setattr(push, "_orologio", o, raising=False)
    return o


@pytest.fixture
def servizi(orologio, monkeypatch, tmp_path):
    """servizi(nome_del_sito="lento"|"ok"|"scaduta"|"rifiuta"): un servizio finto per ogni nome; la connessione dell'invio va lì.
    `servizi.collegamento_lento`: i siti il cui collegamento (con la stretta di mano TLS) dura 25 secondi."""
    monkeypatch.setattr(push, "FILE_ISCRIZIONI", tmp_path / "push.json")       # push.log nella cartella temporanea
    attivi: dict[str, Servizio] = {}
    lenti: set[str] = set()

    class Locale(http.client.HTTPConnection):
        def __init__(self, host, ip, porta, timeout):
            super().__init__("127.0.0.1", attivi[host].porta, timeout=timeout)
            self._sito = host

        def connect(self):
            super().connect()
            if self._sito in lenti:
                orologio.t += 25
    monkeypatch.setattr(scarica_immagine, "_Connessione", Locale)

    def crea(**per_sito):
        for sito, modo in per_sito.items():
            attivi[f"{sito}.example.org"] = Servizio(orologio, modo)
        return {sito: attivi[f"{sito}.example.org"] for sito in per_sito}
    crea.collegamento_lento = lenti
    yield crea
    for s in attivi.values():
        s.chiudi()


def _b64(dati: bytes) -> str:
    return base64.urlsafe_b64encode(dati).rstrip(b"=").decode()


def iscrizione(sito: str) -> dict:
    """Un dispositivo inventato con chiavi vere (la cifratura dell'avviso le usa davvero)."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    pubblica = ec.generate_private_key(ec.SECP256R1()).public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    return {"endpoint": f"https://{sito}.example.org/push/abc", "keys": {"p256dh": _b64(pubblica), "auth": _b64(os.urandom(16))}}


def scrivi_iscrizioni(percorso, *siti):
    percorso.write_text(json.dumps([iscrizione(s) for s in siti]), encoding="utf-8")


def invia(tmp_path, percorso):
    return push.invia("Promemoria", "Schiera la formazione", percorso=percorso, file_chiavi=tmp_path / "vapid.json")


# ---------------------------------------------------------------- tempo massimo di un invio
def test_invio_lento_interrotto_dopo_il_tempo_totale(tmp_path, servizi, orologio):
    s = servizi(lento="lento")["lento"]
    f = tmp_path / "iscrizioni.json"
    scrivi_iscrizioni(f, "lento")
    assert invia(tmp_path, f) == 0
    assert not s.finito_da_solo
    assert TEMPO_INVIO <= orologio.t <= TEMPO_INVIO + 5      # fermato al tempo massimo, non prima né molto dopo
    assert len(push.iscrizioni(f)) == 1                                                   # lento non vuol dire scaduto: l'iscrizione resta
    log = (tmp_path / "push.log").read_text(encoding="utf-8")
    assert "lento.example.org#" in log and "/push/abc" not in log                         # nel log il sito, mai l'indirizzo segreto


def test_il_tempo_massimo_si_cambia_con_la_variabile(tmp_path, servizi, orologio, monkeypatch):
    monkeypatch.setenv("FANTA_MAX_SECONDI_INVIO", "8")
    servizi(lento="lento")
    f = tmp_path / "iscrizioni.json"
    scrivi_iscrizioni(f, "lento")
    assert invia(tmp_path, f) == 0
    assert 8 <= orologio.t <= 8 + 5


def test_invio_normale_arriva_e_le_iscrizioni_scadute_si_tolgono(tmp_path, servizi):
    s = servizi(ok="ok", vecchia="scaduta")
    f = tmp_path / "iscrizioni.json"
    scrivi_iscrizioni(f, "ok", "vecchia")
    assert invia(tmp_path, f) == 1
    assert len(s["ok"].arrivi) == 1 and len(s["vecchia"].arrivi) == 1
    assert [i["endpoint"] for i in push.iscrizioni(f)] == ["https://ok.example.org/push/abc"]


def test_un_rifiuto_del_servizio_resta_nel_registro(tmp_path, servizi):
    """Un servizio che rifiuta (per esempio 403 dopo che le chiavi del server sono cambiate, o 503) non toglie l'iscrizione ma
    lascia una riga in push.log, con il codice e il sito mascherato: senza, un guasto di tutti gli avvisi non lascerebbe traccia."""
    servizi(giu="rifiuta")
    f = tmp_path / "iscrizioni.json"
    scrivi_iscrizioni(f, "giu")
    assert invia(tmp_path, f) == 0
    assert len(push.iscrizioni(f)) == 1
    log = (tmp_path / "push.log").read_text(encoding="utf-8")
    assert "Rifiutata 503 (giu.example.org#" in log and "/push/abc" not in log


def test_collegamento_oltre_il_tempo_l_avviso_non_parte(tmp_path, servizi, orologio):
    """Collegamento e stretta di mano TLS finiti dopo la scadenza: l'avviso non si manda più. Altrimenti arriverebbe sul telefono
    ma risulterebbe «non consegnato», e al giro dopo arriverebbe una seconda volta."""
    s = servizi(ok="ok")["ok"]
    servizi.collegamento_lento.add("ok.example.org")
    f = tmp_path / "iscrizioni.json"
    scrivi_iscrizioni(f, "ok")
    assert invia(tmp_path, f) == 0
    assert s.arrivi == []                                                  # la richiesta non è mai partita
    assert "TimeoutError (ok.example.org#" in (tmp_path / "push.log").read_text(encoding="utf-8")


# ---------------------------------------------------------------- un destinatario lento non ferma gli altri
def test_un_dispositivo_lento_non_ritarda_gli_altri_dello_stesso_utente(tmp_path, servizi):
    s = servizi(lento="lento", veloce="ok")
    f = tmp_path / "iscrizioni.json"
    scrivi_iscrizioni(f, "lento", "veloce")                                # il lento per primo
    assert invia(tmp_path, f) == 1
    assert s["veloce"].arrivi and s["veloce"].arrivi[0] < TEMPO_INVIO      # non ha aspettato che il lento finisse il suo tempo


def test_un_destinatario_lento_non_ferma_gli_altri(tmp_path, servizi, monkeypatch):
    s = servizi(lento="lento", veloce="ok")
    attivi = []
    for nome, sito in (("anna", "lento"), ("bruno", "veloce")):          # anna, con il servizio lento, viene prima nel giro
        f = tmp_path / f"{nome}.json"
        scrivi_iscrizioni(f, sito)
        attivi.append(SimpleNamespace(utente=SimpleNamespace(nome_utente=nome), ctx=SimpleNamespace(regole=None, iscrizioni_push=f)))
    monkeypatch.setattr(avvisi_utenti.regole, "carica", lambda percorso: None)

    def promemoria(a, db, r, adesso):
        return ["mandato"] if invia(tmp_path, a.ctx.iscrizioni_push) else []
    monkeypatch.setitem(avvisi_utenti._LAVORI, "promemoria", promemoria)
    esiti, errori = avvisi_utenti.esegui("promemoria", None, ORA_FISSA, attivi=attivi)
    assert errori == {} and esiti == {"anna": [], "bruno": ["mandato"]}
    assert s["veloce"].arrivi[0] <= TEMPO_INVIO + 5          # bruno servito appena finito il tempo di anna


# ---------------------------------------------------------------- tetto alle prove degli avvisi
def test_sesta_prova_avvisi_in_un_ora_429(ambiente, monkeypatch):  # noqa: F811 (fixture importata)
    monkeypatch.setattr(limiti, "_adesso", lambda: ORA_FISSA)
    (a, _), (b, _) = nuovo_utente("utentea"), nuovo_utente("utenteb")
    for _ in range(6):                                                     # senza dispositivi non parte niente: non conta
        assert a.post("/api/avvisi/prova").status_code == 409
    for c in (a, b):
        assert c.post("/api/push/iscrivi", json=iscrizione("push")).status_code == 200
    for _ in range(PROVE_ORA):
        assert a.post("/api/avvisi/prova").status_code == 200
    r = a.post("/api/avvisi/prova")
    assert r.status_code == 429 and "quest'ora" in r.json()["detail"]
    assert int(r.headers["retry-after"]) == 45 * 60 and r.json()["riprova_tra"] == 45 * 60     # alle 10:15 si riparte alle 11
    assert b.post("/api/avvisi/prova").status_code == 200                  # il tetto è di ciascuno


def test_il_tetto_delle_prove_si_cambia_con_la_variabile(ambiente, monkeypatch):  # noqa: F811
    monkeypatch.setattr(limiti, "_adesso", lambda: ORA_FISSA)
    monkeypatch.setenv("FANTA_MAX_PROVE_AVVISI_ORA", "2")
    a, _ = nuovo_utente("utentea")
    assert a.post("/api/push/iscrivi", json=iscrizione("push")).status_code == 200
    assert [a.post("/api/avvisi/prova").status_code for _ in range(3)] == [200, 200, 429]


def test_senza_account_la_prova_non_ha_tetto(client, dati_isolati, monkeypatch):  # noqa: F811
    from fanta import notifiche
    monkeypatch.setattr(notifiche, "canale", lambda: "canale-finto")
    monkeypatch.setattr(notifiche, "invia", lambda *a, **k: True)
    assert [client.post("/api/avvisi/prova").status_code for _ in range(PROVE_ORA + 2)] == [200] * 7


# ---------------------------------------------------------------- tempo massimo dei giri negli script del server
def _timeout_finto(cartella, chiamate, ferma=""):
    """`timeout` che scrive i suoi argomenti e lancia il comando; con `ferma` (un comando di fanta) fa come se il tempo fosse finito."""
    _stub(cartella, "timeout", f'echo "timeout $*" >> "{_msys(chiamate)}"\n'
                               + (f'case "$*" in *"fanta {ferma}"*) exit 124;; esac\n' if ferma else "")
                               + 'shift\nexec "$@"')


def _aggiorna(tmp_path, ferma="", ambiente_env=None):
    app, bin_, chiamate = _casa_aggiorna(tmp_path, "exit 0")
    _timeout_finto(bin_, chiamate, ferma)
    if ambiente_env is not None:
        _scrivi(app, "dati/ambiente.env", ambiente_env)
    env = {**os.environ, "PATH": f"{bin_}{os.pathsep}{os.environ['PATH']}", "HOME": _msys(tmp_path / "casa"),
           "SCHIERAXI_CANALE": _msys(tmp_path / "nessun-canale")}
    r = _lancia([BASH, (app / "script" / "server" / "aggiorna.sh").as_posix()], env=env)
    assert r.returncode == 0, r.stderr
    return chiamate.read_text(encoding="utf-8"), (app / "dati" / "aggiorna.log").read_text(encoding="utf-8")


def _promemoria(tmp_path, ferma="", ambiente_env=None):
    app = tmp_path / "casa" / "fantacalcio"
    for nome in ("promemoria.sh", "leggi-ambiente.sh", "registri.sh"):
        _scrivi(app, f"script/server/{nome}", (SCRIPT / nome).read_text(encoding="utf-8").replace("\r\n", "\n"))
    if ambiente_env is not None:
        _scrivi(app, "dati/ambiente.env", ambiente_env)
    (app / ".venv" / "bin").mkdir(parents=True)
    chiamate = tmp_path / "chiamate.txt"
    _stub(app / ".venv" / "bin", "python", f'echo "python $*" >> "{_msys(chiamate)}"\n'
                                           'case "$*" in *"fanta promemoria"*) echo "promemoria mandato a 1 utente";; esac\nexit 0')
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    _stub(bin_, "flock", "exit 0")
    _timeout_finto(bin_, chiamate, ferma)
    env = {**os.environ, "PATH": f"{bin_}{os.pathsep}{os.environ['PATH']}", "HOME": _msys(tmp_path / "casa")}
    r = _lancia([BASH, (app / "script" / "server" / "promemoria.sh").as_posix()], env=env)
    assert r.returncode == 0, r.stderr
    return chiamate.read_text(encoding="utf-8"), (app / "dati" / "promemoria.log").read_text(encoding="utf-8")


@con_bash
def test_script_con_timeout(tmp_path):
    """I giri degli avvisi hanno un tempo massimo: 10 minuti in aggiorna.sh (cambi, riepilogo, «formazione pronta»), 8 minuti in
    promemoria.sh (meno dei 10 minuti fra un giro e l'altro). Se il tempo finisce lo scrivono nel log e vanno avanti."""
    chiamate, log = _aggiorna(tmp_path / "a", ferma="cambi")
    for comando in ("cambi", "riepilogo", "avviso"):
        assert f"timeout 600 .venv/bin/python -m fanta {comando}" in chiamate, comando
    assert "cambi: fermato dopo 600 secondi" in log
    assert "python -m fanta riepilogo" in chiamate and "python -m fanta taratura-probabili" in chiamate      # e si va avanti

    chiamate, log = _promemoria(tmp_path / "p")
    assert "timeout 480 .venv/bin/python -m fanta promemoria" in chiamate
    assert "promemoria mandato a 1 utente" in log and "fermato" not in log            # senza tempo superato, il log di sempre
    chiamate, log = _promemoria(tmp_path / "p2", ferma="promemoria")
    assert "promemoria: fermato dopo 480 secondi" in log
    assert "python -m fanta salute" in chiamate                                          # il controllo di salute parte lo stesso


@con_bash
def test_script_tempo_del_giro_da_ambiente(tmp_path):
    """Il tempo massimo si cambia in dati/ambiente.env; un valore non valido vale quello di sempre."""
    chiamate, _ = _aggiorna(tmp_path / "a", ambiente_env="FANTA_MAX_SECONDI_GIRO_AVVISI=90\n")
    assert "timeout 90 .venv/bin/python -m fanta cambi" in chiamate
    chiamate, _ = _aggiorna(tmp_path / "b", ambiente_env="FANTA_MAX_SECONDI_GIRO_AVVISI=10m;x\n")
    assert "timeout 600 .venv/bin/python -m fanta cambi" in chiamate
    chiamate, _ = _promemoria(tmp_path / "p", ambiente_env="FANTA_MAX_SECONDI_GIRO_PROMEMORIA=300\n")
    assert "timeout 300 .venv/bin/python -m fanta promemoria" in chiamate
