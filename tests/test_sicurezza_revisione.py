"""Correzioni chieste dalla revisione della PR #465 (dispositivo fidato, rallentamento, impronte, registri). Ogni test dice
quale attacco prova. Tutto su cartelle temporanee e dati finti."""
import contextlib
import hashlib
import logging
import os
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from fanta import account, percorsi, registro, rotte_account, server
from fanta.account import ErroreAccount

from test_account_http import PASSWORD
from test_sicurezza_pubblico import SBAGLIATA, _richiesta, attese, da, entra, registra, web  # noqa: F401 (fixture)


def _segreto(c: TestClient) -> str:
    return c.cookies.get(rotte_account.COOKIE_DISPOSITIVO)


def _ladro(segreto: str, ip: str) -> TestClient:
    c = da(ip)
    c.cookies.set(rotte_account.COOKIE_DISPOSITIVO, segreto, path="/api/account/")
    return c


# ================================================================ 1) il segreto del dispositivo si revoca
@pytest.mark.parametrize("come", ["recupero", "cambio_password", "esci_da_tutti"])
def test_il_segreto_rubato_non_salta_piu_i_tetti_dopo_la_revoca(web, monkeypatch, attese, come):
    """Attacco: un ladro copia il segreto del dispositivo fidato e prova password senza i tetti per nome e per indirizzo
    (prima: 900 password su 900). Dopo recupero, cambio password o «esci da tutti» il segreto non vale più."""
    monkeypatch.setattr(account, "FALLIMENTI_PER_NOME", (5, 3600))
    monkeypatch.setattr(account, "FALLIMENTI_PER_IP", (5, 900))
    telefono = da("1.1.1.1")
    codice = registra(telefono).json()["codice_recupero"]
    rubato = _segreto(telefono)
    esiti = [entra(_ladro(rubato, f"6.6.6.{i}"), "marco", f"{SBAGLIATA}-{i}").status_code for i in range(8)]
    assert esiti.count(401) == 8                                       # prima della revoca il segreto salta i tetti (è il suo scopo)
    if come == "recupero":
        r = da("1.1.1.1").post("/api/account/recupero", json={"nome_utente": "marco", "codice": codice, "nuova": "nuova-password-lunga"})
    elif come == "cambio_password":
        r = telefono.post("/api/account/cambia-password", json={"attuale": PASSWORD, "nuova": "nuova-password-lunga"})
    else:
        r = telefono.post("/api/account/esci-da-tutti")
    assert r.status_code == 200, r.text
    esiti = [entra(_ladro(rubato, f"6.6.7.{i}"), "marco", f"{SBAGLIATA}-{i}").status_code for i in range(8)]
    assert 429 in esiti and esiti.count(401) <= 5                      # il tetto per nome torna a valere per lui
    with contextlib.closing(account.apri()) as db:
        assert not account._dispositivo_noto(db, "marco", rubato)


# ================================================================ 2) il rallentamento non occupa i thread di tutti
def test_il_rallentamento_non_occupa_i_thread_di_tutti(multiutente, dati_isolati, monkeypatch):
    """Attacco: tanti accessi insieme oltre la soglia globale, ognuno fermo a dormire, per occupare tutti i thread del server
    (prima: /api/salute da 0,03 a 3,5 s con 80 accessi). Possono aspettare al massimo RALLENTATI_INSIEME richieste: le altre
    ricevono subito 429. Un solo client = un solo event loop e gli stessi thread, come nel server vero."""
    monkeypatch.setattr(account, "FALLIMENTI_GLOBALI", (1, 600))
    monkeypatch.setattr(account, "FALLIMENTI_PER_IP", (1000, 900))
    monkeypatch.setattr(account, "_dormi", lambda s: time.sleep(3))
    risposte, durate = [], []
    with TestClient(server.app, headers={"X-Fanta": "1"}) as c:
        c.post("/api/account/accedi", json={"nome_utente": "primo", "password": "x" * 12}, headers={"X-Forwarded-For": "6.6.0.1"})

        def prova(i):
            r = c.post("/api/account/accedi", json={"nome_utente": f"inventato{i}", "password": "x" * 12},
                       headers={"X-Forwarded-For": f"6.6.{i // 200 + 1}.{i % 200 + 2}"})
            risposte.append(r.status_code)
        fili = [threading.Thread(target=prova, args=(i,)) for i in range(60)]
        for f in fili:
            f.start()
        time.sleep(0.4)
        for _ in range(3):
            inizio = time.perf_counter()
            assert c.get("/api/salute").status_code in (200, 503)
            durate.append(time.perf_counter() - inizio)
        for f in fili:
            f.join(30)
    assert max(durate) < 2.0, durate                                            # il server risponde agli altri
    assert len(risposte) == 60 and risposte.count(429) >= 40, sorted(risposte)      # i più ricevono subito 429


@pytest.fixture
def db_noto(multiutente, monkeypatch):
    monkeypatch.setattr(account, "FALLIMENTI_GLOBALI", (1, 600))
    monkeypatch.setattr(account, "_dormi", lambda s: None)
    with contextlib.closing(account.apri()) as db:
        inv = account.crea_invito(db, "prova")
        account.registra(db, "marco", PASSWORD, inv, ip="1.1.1.1")
        segreto = account.ricorda_dispositivo(db, account.elenco(db)[0]["id"])
        for i in range(3):
            with contextlib.suppress(ErroreAccount):
                account.accedi(db, f"nome{i}", "x" * 12, ip=f"6.6.{i}.9")
        yield db, segreto


def test_chi_e_noto_non_aspetta_anche_se_i_posti_sono_pieni(db_noto):
    db, segreto = db_noto
    for _ in range(account.RALLENTATI_INSIEME):
        account._rallentati.acquire()
    try:
        utente, _, _ = account.accedi_ricordando(db, "marco", PASSWORD, ip="9.9.9.9", fidato=segreto)
        assert utente.nome_utente == "marco"
        with pytest.raises(ErroreAccount) as e:                                 # chi non è noto: 429 subito, niente attesa
            account.accedi(db, "inventato", "x" * 12, ip="6.6.6.6")
        assert e.value.stato == 429 and e.value.riprova_tra
    finally:
        for _ in range(account.RALLENTATI_INSIEME):
            account._rallentati.release()


# ================================================================ 3) impronte con una chiave segreta
def test_le_impronte_hanno_una_chiave_segreta(multiutente):
    """Attacco: rubare account.sqlite e provare tutti gli indirizzi IPv4 per risalire a quelli salvati. Senza la chiave
    (in un file a parte, solo per il servizio) l'impronta non si ricalcola."""
    with contextlib.closing(account.apri()) as db:
        inv = account.crea_invito(db, "prova")
        account.registra(db, "marco", PASSWORD, inv, ip="203.0.113.77")
        salvate = {r[0] for r in db.execute("SELECT indirizzo_hash FROM indirizzi_noti")}
    senza_chiave = hashlib.sha256("indirizzo\x1f203.0.113.77".encode()).hexdigest()[:40]
    assert salvate and senza_chiave not in salvate
    file = percorsi.cartella_account() / account.FILE_CHIAVE_IMPRONTE
    assert file.exists() and len(file.read_bytes()) == 32
    if os.name == "posix":
        assert file.stat().st_mode & 0o077 == 0


def test_la_chiave_resta_la_stessa_tra_un_avvio_e_l_altro(multiutente):
    prima = account._chiave("indirizzo", "1.2.3.4")
    account._chiavi_impronte.clear()                                            # come dopo un riavvio: si rilegge dal file
    assert account._chiave("indirizzo", "1.2.3.4") == prima


def test_le_righe_salvate_prima_valgono_ancora_e_si_riscrivono(multiutente):
    """Compatibilità: un indirizzo noto salvato dalla versione di prima (SHA-256 senza chiave) vale ancora e al primo accesso
    riuscito si riscrive con la chiave (la riga vecchia sparisce)."""
    with contextlib.closing(account.apri()) as db:
        inv = account.crea_invito(db, "prova")
        account.registra(db, "marco", PASSWORD, inv)
        uid = account.elenco(db)[0]["id"]
        vecchia = account._chiave_vecchia("indirizzo", "10.0.0.1")
        db.execute("INSERT INTO indirizzi_noti (utente_id, indirizzo_hash, ultimo) VALUES (?, ?, ?)", (uid, vecchia, multiutente.t))
        db.commit()
        assert account._indirizzo_noto(db, "marco", "10.0.0.1")
        account.accedi(db, "marco", PASSWORD, ip="10.0.0.1")
        salvate = {r[0] for r in db.execute("SELECT indirizzo_hash FROM indirizzi_noti")}
        assert vecchia not in salvate and account._chiave("indirizzo", "10.0.0.1") in salvate


# ================================================================ 4) registri
def test_pulizia_dei_registri_anche_senza_scritture(tmp_path, monkeypatch):
    monkeypatch.setenv("FANTA_DATI_UTENTI", str(tmp_path))
    vecchio = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat(timespec="seconds")
    for nome in registro.REGISTRI:
        (tmp_path / nome).write_text(f"{vecchio} vecchia ip=1.2.3.x\n", encoding="utf-8")
    fermo = threading.Event()
    fermo.set()                                     # un giro solo: la pulizia si fa subito, all'avvio
    registro.sorveglia(fermo)
    for nome in registro.REGISTRI:
        assert "vecchia" not in (tmp_path / nome).read_text(encoding="utf-8")


def test_registro_delle_richieste_con_indirizzi_accorciati():
    """Il registro delle richieste di uvicorn scriveva l'indirizzo intero (con la porta)."""
    for indirizzo, atteso in (("203.0.113.77:5555", "203.0.113.x"), ("2001:db8:1:2:3:4:5:6:443", "2001:db8:1:2::/64"), ("", "?")):
        r = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, '%s - "%s %s HTTP/%s" %d',
                              (indirizzo, "GET", "/api/oggi", "1.1", 200), None)
        registro.FILTRO_INDIRIZZI.filter(r)
        assert r.getMessage().startswith(atteso + " - "), r.getMessage()
    registro.accorcia_registro_richieste()
    registro.accorcia_registro_richieste()
    assert logging.getLogger("uvicorn.access").filters.count(registro.FILTRO_INDIRIZZI) == 1


def test_all_avvio_il_filtro_c_e(dati_isolati, monkeypatch):
    monkeypatch.setattr(server.riscaldamento, "attivo", lambda: False)
    monkeypatch.setenv("FANTA_LIVE", "0")
    logging.getLogger("uvicorn.access").removeFilter(registro.FILTRO_INDIRIZZI)
    with TestClient(server.app):
        assert registro.FILTRO_INDIRIZZI in logging.getLogger("uvicorn.access").filters


# ================================================================ 5) piccole
def test_backup_non_valido_senza_dettagli_interni():
    from fanta import backup
    with pytest.raises(ValueError) as e:
        backup.controlla({"formato": backup.FORMATO, "versione": 1, "file": {"dati/osservati.json": ["/home/utente/segreto"]}})
    assert "segreto" not in str(e.value) and "(" not in str(e.value)


def test_intestazione_via_vale_come_proxy():
    assert rotte_account.richiesta_locale(_richiesta("127.0.0.1", (("Via", "1.1 caddy"),))) is False


# ================================================================ revisione della PR #468
def test_utente_giusto_non_bloccato_dopo_429_del_semaforo(multiutente, monkeypatch):
    """Test avversario del revisore. Durante un attacco i posti del rallentamento sono pieni: il titolare, con la password
    GIUSTA, da una rete mobile nuova e senza dispositivo fidato (l'app iPhone non lo manda ancora), riceve 429 più volte.
    Prima ognuno di quei 429 contava come errore per nome e indirizzo: finito l'attacco restava fuori fino a 15 minuti."""
    monkeypatch.setattr(account, "FALLIMENTI_GLOBALI", (1, 600))
    monkeypatch.setattr(account, "_dormi", lambda s: None)
    with contextlib.closing(account.apri()) as db:
        inv = account.crea_invito(db, "prova")
        account.registra(db, "marco", PASSWORD, inv, ip="1.1.1.1")
        for i in range(3):
            with contextlib.suppress(ErroreAccount):
                account.accedi(db, f"nome{i}", "x" * 12, ip=f"6.6.{i}.9")
        for _ in range(account.RALLENTATI_INSIEME):
            account._rallentati.acquire()
        try:
            for _ in range(6):
                with pytest.raises(ErroreAccount) as e:
                    account.accedi(db, "marco", PASSWORD, ip="5.5.5.5")
                assert e.value.stato == 429 and e.value.riprova_tra <= 5            # attesa breve, non 15 minuti
        finally:
            for _ in range(account.RALLENTATI_INSIEME):
                account._rallentati.release()
        monkeypatch.setattr(account, "FALLIMENTI_GLOBALI", (10 ** 6, 600))         # attacco finito
        utente, _ = account.accedi(db, "marco", PASSWORD, ip="5.5.5.5")
        assert utente.nome_utente == "marco"


def test_il_semaforo_pieno_lascia_una_riga_nel_registro(web, monkeypatch, attese):
    monkeypatch.setattr(account, "FALLIMENTI_GLOBALI", (1, 600))
    for i in range(2):
        entra(da(f"6.6.{i}.1"), f"inventato{i}", "x" * 12)
    for _ in range(account.RALLENTATI_INSIEME):
        account._rallentati.acquire()
    try:
        assert entra(da("203.0.113.77"), "qualcuno", "x" * 12).status_code == 429
    finally:
        for _ in range(account.RALLENTATI_INSIEME):
            account._rallentati.release()
    testo = (percorsi.cartella_account() / registro.FILE_SICUREZZA).read_text(encoding="utf-8")
    assert "accesso_rallentamento_pieno" in testo and "ip=203.0.113.x" in testo and "203.0.113.77" not in testo


@pytest.mark.parametrize("contenuto", [b"", b"corta"])
def test_chiave_vuota_o_tagliata_si_ricrea_invece_di_503(multiutente, contenuto):
    """Un file di chiave vuoto (per esempio disco pieno durante la scrittura) mandava in 503 tutti gli accessi."""
    file = percorsi.cartella_account() / account.FILE_CHIAVE_IMPRONTE
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_bytes(contenuto)
    account._chiavi_impronte.clear()
    assert len(account._chiave("indirizzo", "1.2.3.4")) == 40
    assert len(file.read_bytes()) == 32
    assert not list(file.parent.glob(f".{file.name}.*.tmp"))                         # nessun file temporaneo rimasto


def test_chiave_creata_insieme_da_due_thread_resta_una_sola(multiutente):
    """Due richieste che creano la chiave nello stesso momento (anche da due processi): vince una, e tutte usano quella."""
    file = percorsi.cartella_account() / account.FILE_CHIAVE_IMPRONTE
    file.parent.mkdir(parents=True, exist_ok=True)
    risultati, barriera = [], threading.Barrier(8)

    def crea():
        barriera.wait()
        account._scrivi_chiave(file, sostituisci=False)
        risultati.append(file.read_bytes())
    fili = [threading.Thread(target=crea) for _ in range(8)]
    for f in fili:
        f.start()
    for f in fili:
        f.join(10)
    assert len(set(risultati)) == 1 and len(risultati[0]) == 32
    assert not list(file.parent.glob(f".{file.name}.*.tmp"))


def test_il_backup_notturno_copia_la_chiave():
    testo = (percorsi.RADICE / "script" / "server" / "backup-dati.sh").read_text(encoding="utf-8")
    assert "chiave-impronte.key" in testo and 'chmod 600 "$stage/dati/chiave-impronte.key"' in testo and "umask 077" in testo
