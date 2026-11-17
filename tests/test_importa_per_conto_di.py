"""Importazione «per conto di»: il proprietario importa le rose di un amico che lo ha chiesto (rotta admin e comando)."""
import contextlib
import sys
import threading
import time

import pytest

from fanta import __main__ as cli
from fanta import account, blocco, percorsi, rose, server
from fanta import contesto
from test_account_http import PASSWORD, cliente

ROSE = "Squadra dell'amico\nP\tSommer\t10\nD\tBastoni\t15\nAltra\nA\tKean\t30\n"


@pytest.fixture
def mondo(multiutente, dati_isolati, calciatori, monkeypatch):
    monkeypatch.setattr(server.listone, "carica", lambda *a, **k: (calciatori, "oggi"))
    monkeypatch.setattr(server.consigli, "stagione_corrente", lambda: "2026-27")
    persone = {}
    for nome, admin in (("capo", True), ("amico", False), ("altro", False)):
        with contextlib.closing(account.apri()) as db:
            inv = account.crea_invito(db, nome, admin)
        c = cliente()
        r = c.post("/api/account/registra", json={"nome_utente": nome, "password": PASSWORD, "invito": inv})
        assert r.status_code == 200, r.text
        persone[nome] = (c, r.json()["utente"]["id"])
    return persone


def test_il_proprietario_importa_per_l_amico(mondo):
    capo, amico, altro = mondo["capo"][0], mondo["amico"], mondo["altro"][0]
    r = capo.post(f"/api/admin/utenti/{amico[1]}/rose", json={"testo": ROSE})
    assert r.status_code == 200, r.text
    assert r.json()["squadre_importate"] == ["Squadra dell'amico", "Altra"]
    assert [s["nome"] for s in amico[0].get("/api/squadre").json()] == ["Squadra dell'amico", "Altra"]     # le vede lui
    assert altro.get("/api/squadre").status_code == 409                                                      # un altro no
    assert capo.get("/api/squadre").status_code == 409                                                       # e nemmeno il proprietario nelle sue
    sicurezza = capo.get("/api/admin/registro").json()["sicurezza"]
    riga = [e for e in sicurezza if e["tipo"] == "importazione_per_conto_di"][0]
    assert riga["admin"] == str(mondo["capo"][1]) and riga["utente"] == str(amico[1]) and riga["squadre"] == "2"
    assert "Sommer" not in str(sicurezza)                                                                     # mai il contenuto


def test_non_consuma_le_importazioni_dell_amico(mondo):
    capo, amico = mondo["capo"][0], mondo["amico"]
    for _ in range(12):                                                                                       # più del tetto di 10 al giorno
        assert capo.post(f"/api/admin/utenti/{amico[1]}/rose", json={"testo": ROSE}).status_code == 200
    assert amico[0].post("/api/rose/testo", json={"testo": ROSE}).status_code == 200


def test_solo_l_amministratore_e_utente_esistente(mondo):
    capo, amico, altro = mondo["capo"][0], mondo["amico"], mondo["altro"]
    for c in (amico[0], altro[0], cliente()):
        r = c.post(f"/api/admin/utenti/{altro[1]}/rose", json={"testo": ROSE})
        assert r.status_code in (401, 403), r.status_code
    assert capo.get("/api/squadre").status_code == 409
    assert altro[0].get("/api/squadre").status_code == 409                                                    # niente è stato scritto
    assert capo.post("/api/admin/utenti/9999/rose", json={"testo": ROSE}).status_code == 404


def test_controlli_come_l_importazione_normale(mondo):
    capo, amico = mondo["capo"][0], mondo["amico"]
    assert capo.post(f"/api/admin/utenti/{amico[1]}/rose", json={"testo": "x" * 300_000}).status_code in (400, 413)
    assert capo.post(f"/api/admin/utenti/{amico[1]}/rose", json={"testo": "\n".join("a\tb" for _ in range(1600))}).status_code == 400
    assert capo.post(f"/api/admin/utenti/{amico[1]}/rose", json={"testo": "niente di utile"}).status_code == 400
    assert capo.post(f"/api/admin/utenti/{amico[1]}/rose", json={}).status_code == 422
    assert amico[0].get("/api/squadre").status_code == 409


def test_comando(mondo, tmp_path, monkeypatch, capsys):
    amico = mondo["amico"]
    file = tmp_path / "rose.txt"
    file.write_text(ROSE, encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["fanta", "importa-per-conto-di", "--utente", "AMICO", str(file)])
    cli.main()
    assert "Importate 2 squadre per «AMICO»" in capsys.readouterr().out
    assert [s["nome"] for s in amico[0].get("/api/squadre").json()] == ["Squadra dell'amico", "Altra"]
    monkeypatch.setattr(sys, "argv", ["fanta", "importa-per-conto-di", "--utente", "nessuno", str(file)])
    with pytest.raises(SystemExit) as e:
        cli.main()
    assert "non esiste" in str(e.value)


def test_a_interruttore_spento_non_fa_niente(monkeypatch):
    monkeypatch.delenv("FANTA_MULTIUTENTE", raising=False)
    r = cliente().post("/api/admin/utenti/1/rose", json={"testo": ROSE})
    assert r.status_code == 409 and "FANTA_MULTIUTENTE=1" in r.json()["detail"]


def test_rose_di_dimensione_vera_non_si_fermano_al_tetto_degli_account(mondo):
    capo, amico = mondo["capo"][0], mondo["amico"]
    assert capo.post(f"/api/admin/utenti/{amico[1]}/rose", json={"testo": ROSE + " " * 30_000}).status_code == 200
    assert capo.post(f"/api/admin/utenti/{amico[1]}/rose", content=b"x" * 700_000, headers={"content-type": "application/json"}).status_code == 413
    assert capo.post("/api/admin/inviti", content=b"x" * 20_000, headers={"content-type": "application/json"}).status_code == 413    # le altre rotte admin: tetto piccolo


def test_due_importazioni_insieme_non_si_perdono(mondo):
    amico = mondo["amico"]
    altre = "Terza\nP\tSommer\t10\nQuarta\nA\tKean\t30\n"
    esiti = []
    fermi = threading.Barrier(2)

    def vai(testo):
        fermi.wait()
        esiti.append(server.importa_per_conto_di(amico[1], [("testo", server.rose.griglia_da_testo(testo))], False, 1))

    fili = [threading.Thread(target=vai, args=(t,)) for t in (ROSE, altre)]
    [f.start() for f in fili]
    [f.join(20) for f in fili]
    assert len(esiti) == 2
    nomi = {s["nome"] for s in amico[0].get("/api/squadre").json()}
    assert nomi == {"Squadra dell'amico", "Altra", "Terza", "Quarta"}


def test_importazione_di_testo_e_di_file_aspettano_il_blocco_delle_rose(mondo):
    """Revisione 31/10: anche /api/rose/testo e /api/rose/file prendono il blocco delle rose (prima solo l'importazione per conto di)."""
    amico = mondo["amico"][0]
    altre = "Terza\nP\tSommer\t10\nQuarta\nA\tKean\t30\n"
    esiti = {}

    def testo():
        esiti["testo"] = amico.post("/api/rose/testo", json={"testo": ROSE}).status_code

    def file():
        esiti["file"] = amico.post("/api/rose/file", files={"file": ("rose.csv", altre.encode(), "text/csv")}).status_code

    with server._scrittura_rose:                      # il blocco è preso: le due importazioni devono aspettare
        fili = [threading.Thread(target=testo), threading.Thread(target=file)]
        [f.start() for f in fili]
        time.sleep(0.8)
        assert esiti == {}
    [f.join(30) for f in fili]
    assert esiti == {"testo": 200, "file": 200}
    nomi = {s["nome"] for s in amico.get("/api/squadre").json()}
    assert nomi == {"Squadra dell'amico", "Altra", "Terza", "Quarta"}      # nessuna delle due ha cancellato l'altra


def test_il_blocco_su_file_ferma_anche_un_altro_processo(mondo):
    amico = mondo["amico"]
    finito = threading.Event()

    def vai():
        server.importa_per_conto_di(amico[1], [("testo", server.rose.griglia_da_testo(ROSE))], False, None)
        finito.set()

    with blocco.BloccoFile(percorsi.cartella_account() / "blocco-rose.lock"):         # come se la tenesse un altro processo
        filo = threading.Thread(target=vai)
        filo.start()
        assert not finito.wait(0.5)
    assert finito.wait(10)
    filo.join()


def test_blocco_scaduto_da_un_errore_chiaro(tmp_path):
    f = tmp_path / "x.lock"
    with blocco.BloccoFile(f):
        with pytest.raises(TimeoutError, match="ancora in corso"):
            with blocco.BloccoFile(f, attesa=0.2):
                pass


def test_sostituisci_tutto_lascia_copie_datate(mondo):
    capo, amico = mondo["capo"][0], mondo["amico"]
    cartella = contesto.cartella_utente(amico[1]) / "rose-prima"
    for i in range(7):
        r = capo.post(f"/api/admin/utenti/{amico[1]}/rose", json={"testo": ROSE.replace("Altra", f"Altra{i}"), "sostituisci_tutto": True})
        assert r.status_code == 200, r.text
    copie = sorted(cartella.glob("rose-*.json"))
    assert len(copie) == server.COPIE_DELLE_ROSE                                  # le ultime cinque, non una sola che si sovrascrive
    assert "Altra5" in copie[-1].read_text(encoding="utf-8")                      # l'ultima e' lo stato prima dell'ultima sostituzione
    capo.post(f"/api/admin/utenti/{amico[1]}/rose", json={"testo": ROSE})        # senza sostituire: nessuna copia in piu'
    assert len(list(cartella.glob("rose-*.json"))) == server.COPIE_DELLE_ROSE


def test_excel_letto_in_parte_rifiutato_non_consuma_le_copie_datate(mondo):
    """Un Excel con più fogli del tetto e «sostituisci tutto» che toglierebbe una squadra salvata: rifiutato PRIMA della copia
    datata, altrimenti ogni tentativo aggiungerebbe una copia uguale e toglierebbe la più vecchia delle cinque vere."""
    capo, amico = mondo["capo"][0], mondo["amico"]
    assert capo.post(f"/api/admin/utenti/{amico[1]}/rose", json={"testo": ROSE}).status_code == 200
    cartella = contesto.cartella_utente(amico[1]) / "rose-prima"
    griglie = rose.Fogli([("Altra", [["Altra"], ["A", "Kean", 30]])], nel_file=12)     # «Squadra dell'amico» non letta
    with pytest.raises(ValueError, match="12 fogli"):
        server.importa_per_conto_di(amico[1], griglie, True, None)
    assert list(cartella.glob("rose-*.json")) == []


def test_tetto_di_frequenza(mondo, monkeypatch):
    capo, amico = mondo["capo"][0], mondo["amico"]
    monkeypatch.setattr(server, "IMPORTAZIONI_PER_CONTO_DI", (3, 3600))
    for _ in range(3):
        assert capo.post(f"/api/admin/utenti/{amico[1]}/rose", json={"testo": ROSE}).status_code == 200
    assert capo.post(f"/api/admin/utenti/{amico[1]}/rose", json={"testo": ROSE}).status_code == 429


def test_json_annidato_a_dismisura_e_una_richiesta_sbagliata(mondo):
    capo, amico = mondo["capo"][0], mondo["amico"]
    brutto = b"[" * 100_000 + b"]" * 100_000
    r = capo.post(f"/api/admin/utenti/{amico[1]}/rose", content=b'{"testo": ' + brutto + b"}", headers={"content-type": "application/json"})
    assert r.status_code in (400, 422), r.status_code
    piccolo = b"[" * 3000 + b"]" * 3000
    r = capo.post("/api/admin/inviti", content=b'{"etichetta": ' + piccolo + b"}", headers={"content-type": "application/json"})
    assert r.status_code in (400, 422), r.status_code


def test_comando_invito_con_usi(multiutente, capsys, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["fanta", "invito", "--etichetta", "amici", "--usi", "12"])
    cli.main()
    assert "fino a 12 persone" in capsys.readouterr().out
    with contextlib.closing(account.apri()) as db:
        assert db.execute("SELECT usi_max FROM inviti").fetchone()[0] == 12
    monkeypatch.setattr(sys, "argv", ["fanta", "invito", "--etichetta", "x", "--admin", "--usi", "3"])
    with pytest.raises(SystemExit) as e:
        cli.main()
    assert "una volta sola" in str(e.value)
