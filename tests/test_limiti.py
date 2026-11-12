"""Limiti per utente (importazioni, scambi, spazio, dimensione della lega): solo con gli account accesi, e solo per chi li supera.
Tutto su cartelle temporanee e dati finti (vedi le fixture multiutente e dati_isolati)."""
import contextlib
import json
from datetime import datetime, timedelta

import pytest

from fanta import account, backup, contesto, limiti, scambi, server

from test_account_http import PASSWORD, cliente

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 24


@pytest.fixture(autouse=True)
def _niente_ricordi_di_altri_test():
    limiti._gia_contate.clear()          # le richieste già contate si ricordano in memoria: ogni test riparte da zero
    yield
    limiti._gia_contate.clear()


def ricerca(c, i):
    """Una ricerca diversa dalle altre (squadra diversa): ognuna costa un uso."""
    return c.get("/api/scambi/proposte", params={"con": f"Squadra {i}"})


@pytest.fixture
def ambiente(multiutente, dati_isolati, calciatori, monkeypatch):
    """Il necessario per importare rose e cercare scambi senza rete né calcoli veri."""
    monkeypatch.setattr(server.listone, "carica", lambda *a, **k: (calciatori, "oggi"))
    monkeypatch.setattr(server.consigli, "stagione_corrente", lambda: "2026-27")
    monkeypatch.setattr(server.consigli, "valori_scambi", lambda db, regole: type("V", (), {"giornate": []})())
    monkeypatch.setattr(scambi, "proponi", lambda *a, **k: [])
    # la ricerca vera si ricorda e, con gli account, passa dalla coda (202): qui si prova solo il conteggio, quindi senza ricordo
    def senza_ricordo(db, regole, rose, con=None, due=False, fino_a=0):
        v = server.consigli.valori_scambi(db, regole)
        return v, [s.come_dict(v) for s in scambi.proponi(v, regole, rose, rose.mia_squadra, con, anche_due=due)]
    monkeypatch.setattr(server.consigli, "proposte_scambi", senza_ricordo)


def nuovo_utente(nome: str):
    with contextlib.closing(account.apri()) as db:
        inv = account.crea_invito(db, nome)
    c = cliente()
    r = c.post("/api/account/registra", json={"nome_utente": nome, "password": PASSWORD, "invito": inv})
    assert r.status_code == 200, r.text
    return c, r.json()["utente"]["id"]


def rose_di(squadre: int, giocatori: int = 1) -> str:
    return "".join(f"Squadra {i}\n" + "D\tBastoni\t5\n" * giocatori for i in range(squadre))


def importa(c, testo="Mia\nP\tSommer\t10\n"):
    return c.post("/api/rose/testo", json={"testo": testo})


# ---------------------------------------------------------------- tetti giornalieri
def test_dieci_importazioni_al_giorno(ambiente):
    (a, _), (b, _) = nuovo_utente("utentea"), nuovo_utente("utenteb")
    for _ in range(limiti.MAX_IMPORTAZIONI_AL_GIORNO):
        assert importa(a).status_code == 200
    r = importa(a)
    assert r.status_code == 429 and "limite di importazioni di rose di oggi (10)" in r.json()["detail"] and "Si azzera tra" in r.json()["detail"]
    assert "Riprova" not in r.json()["detail"] and "Tailscale" not in r.json()["detail"]          # un solo messaggio, senza doppioni né consigli sbagliati
    assert 0 < int(r.headers["retry-after"]) <= 24 * 3600 and r.json()["riprova_tra"] == int(r.headers["retry-after"])
    assert importa(b).status_code == 200                          # il tetto è di ciascuno: B non ne risente


def test_il_file_conta_come_il_testo(ambiente):
    a, _ = nuovo_utente("utentea")
    file = {"file": ("rose.txt", b"Mia\nP\tSommer\t10\n", "text/plain")}
    for _ in range(5):
        assert importa(a).status_code == 200
        assert a.post("/api/rose/file", files=file).status_code == 200
    assert importa(a).status_code == 429
    assert a.post("/api/rose/file", files=file).status_code == 429


def test_il_giorno_dopo_si_riparte(ambiente, monkeypatch):
    a, _ = nuovo_utente("utentea")
    for _ in range(limiti.MAX_IMPORTAZIONI_AL_GIORNO):
        importa(a)
    assert importa(a).status_code == 429
    domani = datetime.now() + timedelta(days=1)
    monkeypatch.setattr(limiti, "_adesso", lambda: domani)
    assert importa(a).status_code == 200


def test_sessanta_ricerche_di_scambi_al_giorno(ambiente):
    (a, _), (b, _) = nuovo_utente("utentea"), nuovo_utente("utenteb")
    for c in (a, b):
        assert importa(c).status_code == 200
        assert c.put("/api/mia-squadra", json={"nome": "Mia"}).status_code == 200
    for i in range(limiti.MAX_SCAMBI_AL_GIORNO):
        assert ricerca(a, i).status_code == 200
    r = ricerca(a, 999)
    assert r.status_code == 429 and "limite di ricerche di scambi di oggi (60)" in r.json()["detail"] and r.json()["riprova_tra"] > 0
    assert ricerca(b, 0).status_code == 200
    assert limiti.usati_oggi(1, "scambi") == 60 and limiti.usati_oggi(2, "scambi") == 1


def test_il_contatore_dice_quante_ricerche_restano(ambiente):
    a, id_a = nuovo_utente("utentea")
    importa(a)
    a.put("/api/mia-squadra", json={"nome": "Mia"})
    assert a.get("/api/scambi/limite").json() == {"restano": 60, "tetto": 60}
    r = ricerca(a, 1)
    assert r.json()["ricerche"] == {"restano": 59, "tetto": 60}          # anche nella risposta della ricerca
    assert a.get("/api/scambi/limite").json()["restano"] == 59
    a.get("/api/scambi/limite")
    assert limiti.usati_oggi(id_a, "scambi") == 1                         # leggere il contatore non consuma niente
    for i in range(2, 61):
        ricerca(a, i)
    assert a.get("/api/scambi/limite").json() == {"restano": 0, "tetto": 60}


def test_il_contatore_non_c_e_per_l_amministratore(ambiente):
    from test_account_http import invito, PASSWORD
    capo = cliente()
    assert capo.post("/api/account/registra", json={"nome_utente": "capo", "password": PASSWORD, "invito": invito(True)}).status_code == 200
    assert capo.get("/api/scambi/limite").json() == {"restano": None, "tetto": None}


def test_la_stessa_ricerca_ripetuta_non_consuma_altre_ricerche(ambiente):
    a, id_a = nuovo_utente("utentea")
    importa(a)
    a.put("/api/mia-squadra", json={"nome": "Mia"})
    for _ in range(5):
        assert ricerca(a, 1).status_code == 200                 # stessi parametri e stesse rose: risultato in cache
    assert limiti.usati_oggi(id_a, "scambi") == 1
    assert a.get("/api/scambi/proposte", params={"con": "Squadra 1", "fino_a": 2}).status_code == 200      # un'altra misura è un'altra ricerca
    assert limiti.usati_oggi(id_a, "scambi") == 2


def test_a_tetto_finito_la_stessa_ricerca_di_oggi_si_puo_rifare(ambiente):
    a, id_a = nuovo_utente("utentea")
    importa(a)
    a.put("/api/mia-squadra", json={"nome": "Mia"})
    for i in range(limiti.MAX_SCAMBI_AL_GIORNO):
        assert ricerca(a, i).status_code == 200
    assert ricerca(a, 999).status_code == 429                    # una ricerca nuova no
    r = ricerca(a, 3)                                            # una già fatta oggi sì: rilegge il risultato e non costa
    assert r.status_code == 200 and r.json()["ricerche"] == {"restano": 0, "tetto": limiti.MAX_SCAMBI_AL_GIORNO}
    assert limiti.usati_oggi(id_a, "scambi") == limiti.MAX_SCAMBI_AL_GIORNO


def test_l_amministratore_non_ha_limiti_di_uso(ambiente):
    from test_account_http import invito, PASSWORD
    capo = cliente()
    assert capo.post("/api/account/registra", json={"nome_utente": "capo", "password": PASSWORD, "invito": invito(True)}).status_code == 200
    importa(capo)
    capo.put("/api/mia-squadra", json={"nome": "Mia"})
    for i in range(limiti.MAX_SCAMBI_AL_GIORNO + 5):
        assert ricerca(capo, i).status_code == 200
    for _ in range(limiti.MAX_IMPORTAZIONI_AL_GIORNO + 3):
        assert importa(capo).status_code == 200
    assert limiti.usati_oggi(1, "scambi") == limiti.MAX_SCAMBI_AL_GIORNO + 5                    # il contatore resta, per le statistiche


def test_l_amministratore_non_aggira_i_limiti_di_sicurezza(ambiente, tmp_path):
    from test_account_http import invito, PASSWORD
    capo = cliente()
    capo.post("/api/account/registra", json={"nome_utente": "capo", "password": PASSWORD, "invito": invito(True)})
    r = importa(capo, rose_di(limiti.MAX_SQUADRE + 1))                                         # dimensione della lega
    assert r.status_code == 413
    assert capo.post("/api/account/accedi", json={"nome_utente": "capo", "password": "sbagliata1234"}).status_code in (400, 401, 429)


def test_una_richiesta_sbagliata_non_consuma_lo_scambio(ambiente):
    a, _ = nuovo_utente("utentea")
    importa(a)
    a.put("/api/mia-squadra", json={"nome": "Mia"})
    assert a.get("/api/scambi/proposte", params={"due": True}).status_code == 400      # 2 contro 2 senza squadra
    assert limiti.usati_oggi(1, "scambi") == 0


def test_il_202_sto_calcolando_non_consuma_la_ricerca(ambiente, monkeypatch):
    """L'app riprova da sola ogni 3 secondi mentre il calcolo è in coda: solo il risultato pronto conta come ricerca."""
    from fanta import calcolo
    a, id_a = nuovo_utente("utentea")
    importa(a)
    a.put("/api/mia-squadra", json={"nome": "Mia"})
    risposte = [calcolo.InCalcolo(), calcolo.InCalcolo(), type("V", (), {"giornate": []})()]

    def valori(db, regole):
        r = risposte.pop(0)
        if isinstance(r, Exception):
            raise r
        return r
    monkeypatch.setattr(server.consigli, "valori_scambi", valori)
    assert a.get("/api/scambi/proposte").status_code == 202
    assert a.get("/api/scambi/proposte").status_code == 202
    assert limiti.usati_oggi(id_a, "scambi") == 0
    assert a.get("/api/scambi/proposte").status_code == 200
    assert limiti.usati_oggi(id_a, "scambi") == 1


def test_un_errore_nel_calcolo_degli_scambi_non_consuma_la_ricerca(ambiente, monkeypatch):
    a, id_a = nuovo_utente("utentea")
    importa(a)
    a.put("/api/mia-squadra", json={"nome": "Mia"})
    monkeypatch.setattr(scambi, "proponi", lambda *x, **k: (_ for _ in ()).throw(ValueError("Squadra sconosciuta")))
    assert a.get("/api/scambi/proposte", params={"con": "Nessuna"}).status_code == 400
    assert limiti.usati_oggi(id_a, "scambi") == 0


def test_il_tetto_degli_scambi_si_controlla_prima_del_calcolo(ambiente, monkeypatch):
    """Esaurito il tetto, la risposta è 429 senza nemmeno far partire il calcolo."""
    a, id_a = nuovo_utente("utentea")
    importa(a)
    a.put("/api/mia-squadra", json={"nome": "Mia"})
    for i in range(limiti.MAX_SCAMBI_AL_GIORNO):
        assert ricerca(a, i).status_code == 200
    chiamate = []
    monkeypatch.setattr(server.consigli, "valori_scambi", lambda db, regole: chiamate.append(1))
    assert ricerca(a, 999).status_code == 429 and not chiamate


def test_i_rifiuti_immediati_non_consumano_importazioni_i_file_letti_si(ambiente):
    a, id_a = nuovo_utente("utentea")
    assert a.post("/api/rose/file", files={"file": ("rose.xlsm", b"PK\x03\x04", "application/zip")}).status_code == 400
    assert a.post("/api/rose/file", files={"file": ("vuoto.csv", b"  \n", "text/csv")}).status_code == 400
    assert a.post("/api/rose/testo", json={"testo": "x" * 300_000}).status_code == 400
    assert a.post("/api/rose/testo", json={"testo": "a\n" * 2000}).status_code == 400          # troppe righe
    assert limiti.usati_oggi(id_a, "importazioni") == 0
    # un file che il server ha dovuto leggere conta anche se poi è rifiutato (niente file sbagliati all'infinito)
    assert a.post("/api/rose/file", files={"file": ("rose.pdf", b"%PDF", "application/pdf")}).status_code == 400
    assert a.post("/api/rose/file", files={"file": ("rose.xls", b"\xd0\xcf\x11\xe0" + b"\x00" * 40, "application/vnd.ms-excel")}).status_code == 400
    assert limiti.usati_oggi(id_a, "importazioni") == 2
    assert importa(a).status_code == 200
    assert limiti.usati_oggi(id_a, "importazioni") == 3


# ---------------------------------------------------------------- dimensione della lega
def test_venti_squadre_vanno_ventuno_no(ambiente):
    a, id_a = nuovo_utente("utentea")
    assert importa(a, rose_di(limiti.MAX_SQUADRE)).status_code == 200
    r = a.post("/api/rose/testo", json={"testo": rose_di(limiti.MAX_SQUADRE + 1), "sostituisci_tutto": True})
    assert r.status_code == 413 and "21 squadre" in r.json()["detail"]
    assert len(a.get("/api/squadre").json()) == 20                    # la lega di prima è rimasta com'era


def test_le_squadre_si_contano_anche_con_quelle_gia_salvate(ambiente):
    a, _ = nuovo_utente("utentea")
    assert importa(a, rose_di(20)).status_code == 200
    r = importa(a, "Un'altra\nP\tSommer\t10\n")                      # senza sostituire tutto le squadre si sommano: sarebbero 21
    assert r.status_code == 413


def test_quaranta_giocatori_per_squadra(ambiente):
    a, _ = nuovo_utente("utentea")
    # giocatori tutti diversi (lo stesso ripetuto ora resta uno solo): nomi non riconosciuti, che in rosa restano e contano
    diversi = lambda n: "Squadra 0\n" + "".join(f"D\tSconosciuto {chr(65 + k // 26)}{chr(65 + k % 26)}\t5\n" for k in range(n))  # noqa: E731
    assert importa(a, diversi(limiti.MAX_GIOCATORI_SQUADRA)).status_code == 200
    r = importa(a, diversi(limiti.MAX_GIOCATORI_SQUADRA + 1))
    assert r.status_code == 413 and "41 giocatori" in r.json()["detail"]


def _rose_nel_backup(squadre: int, giocatori: int) -> dict:
    return {"squadre": [{"nome": f"Squadra {i}", "giocatori": [{"id": None, "nome": f"G{i}-{k}", "ruolo": "D", "squadra": None}
                                                               for k in range(giocatori)]} for i in range(squadre)],
            "mia_squadra": None, "aggiornato": "", "stagione": "2026-27"}


@pytest.mark.parametrize("squadre, giocatori, testo", [(limiti.MAX_SQUADRE + 1, 1, "21 squadre"),
                                                        (1, limiti.MAX_GIOCATORI_SQUADRA + 1, "41 giocatori")])
def test_il_ripristino_del_backup_ha_gli_stessi_tetti_dell_importazione(ambiente, squadre, giocatori, testo):
    a, id_a = nuovo_utente("utentea")
    assert importa(a).status_code == 200
    copia = a.get("/api/backup").json()
    cartella = contesto.cartella_utente(id_a)
    prima = {p.relative_to(cartella).as_posix(): p.read_bytes() for p in cartella.rglob("*") if p.is_file()}
    copia["file"]["lega/rose.json"] = _rose_nel_backup(squadre, giocatori)
    copia["file"]["dati/osservati.json"] = [1, 2]
    r = a.post("/api/backup/ripristina", json=copia)
    assert r.status_code == 413 and testo in r.json()["detail"]
    dopo = {p.relative_to(cartella).as_posix(): p.read_bytes() for p in cartella.rglob("*") if p.is_file()}
    assert dopo == prima                                                       # niente scritto, nemmeno la copia di prima


def test_il_ripristino_del_backup_al_tetto_va(ambiente):
    a, _ = nuovo_utente("utentea")
    copia = a.get("/api/backup").json()
    copia["file"]["lega/rose.json"] = _rose_nel_backup(limiti.MAX_SQUADRE, limiti.MAX_GIOCATORI_SQUADRA)
    r = a.post("/api/backup/ripristina", json=copia)
    assert r.status_code == 200 and "lega/rose.json" in r.json()["ripristinati"]
    assert len(a.get("/api/squadre").json()) == limiti.MAX_SQUADRE


def _annidato(livelli: int):
    d: list = [0]
    for _ in range(livelli - 1):
        d = [d]
    return d


def _file_utente(cartella) -> dict:
    return {p.relative_to(cartella).as_posix(): p.read_bytes() for p in cartella.rglob("*") if p.is_file()}


@pytest.mark.parametrize("nome, contenuto", [
    pytest.param("dati/scelte.json", {f"x{i}": _annidato(50) for i in range(3)}, id="scelte-annidate"),
    pytest.param("lega/movimenti.json", [_annidato(50)], id="movimenti-annidati"),
    pytest.param("lega/movimenti.json", [1, 2, 3], id="movimenti-numeri"),
    pytest.param("lega/rose.json", _rose_nel_backup(1, 1) | {"mia_squadra": "Squadra 0\ud800"}, id="rose-testo-spezzato"),
])
def test_il_ripristino_con_dati_di_forma_sbagliata_risponde_400_e_non_scrive_niente(ambiente, nome, contenuto):
    a, id_a = nuovo_utente("utentea")
    assert importa(a).status_code == 200
    copia = a.get("/api/backup").json()
    cartella = contesto.cartella_utente(id_a)
    prima = _file_utente(cartella)
    copia["file"]["dati/osservati.json"] = [1, 2]                   # un file buono prima di quello sbagliato: non si scrive nemmeno lui
    copia["file"][nome] = contenuto
    corpo = json.dumps(copia)                     # i caratteri fuori dall'ASCII come \uXXXX, anche quelli spezzati
    r = a.post("/api/backup/ripristina", content=corpo, headers={"Content-Type": "application/json"})
    assert r.status_code == 400 and r.json()["detail"] == f"{nome} non è valido: controlla di aver scelto il file di backup giusto"
    assert _file_utente(cartella) == prima                                    # niente scritto, nemmeno la copia di prima


def test_il_ripristino_misura_lo_spazio_su_quello_che_scrive(ambiente, monkeypatch):
    """Lo spazio si controlla anche sul peso vero dei file che il ripristino scrive, prima di scriverli."""
    a, id_a = nuovo_utente("utentea")
    assert importa(a).status_code == 200
    copia = a.get("/api/backup").json()
    copia["file"]["dati/osservati.json"] = [1, 2]
    misure = []
    vera = limiti.controlla_spazio

    def misura(ctx, in_arrivo=0, consiglio=""):
        misure.append(in_arrivo)
        return vera(ctx, in_arrivo, consiglio)
    monkeypatch.setattr(limiti, "controlla_spazio", misura)
    r = a.post("/api/backup/ripristina", json=copia)
    assert r.status_code == 200
    cartella = contesto.cartella_utente(id_a)
    scritti = sum((cartella / nome.rsplit("/", 1)[1]).stat().st_size for nome in r.json()["ripristinati"])
    assert misure[-1] == scritti


# ---------------------------------------------------------------- spazio
def riempi(utente_id: int, byte: int) -> None:
    cartella = contesto.cartella_utente(utente_id)
    cartella.mkdir(parents=True, exist_ok=True)
    (cartella / "riempitivo.bin").write_bytes(b"\x00" * byte)


def test_cinque_mb_di_dati_personali(ambiente):
    a, id_a = nuovo_utente("utentea")
    importa(a, "Mia\nP\tSommer\t10\n")
    riempi(id_a, limiti.MAX_BYTE_UTENTE - 1000)
    grande = {"file": ("s.png", PNG + b"\x00" * 5000, "image/png")}
    r = a.post("/api/squadre/immagine", params={"squadra": "Mia", "tipo": "stemma"}, files=grande)
    assert r.status_code == 413 and "5 MB" in r.json()["detail"]
    assert not (contesto.cartella_utente(id_a) / "immagini").exists()
    piccola = {"file": ("s.png", PNG, "image/png")}
    assert a.post("/api/squadre/immagine", params={"squadra": "Mia", "tipo": "stemma"}, files=piccola).status_code == 200


def test_il_ripristino_di_un_backup_enorme_si_ferma(ambiente):
    a, id_a = nuovo_utente("utentea")
    riempi(id_a, limiti.MAX_BYTE_UTENTE - 10)
    r = a.post("/api/backup/ripristina", json={"formato": backup.FORMATO, "versione": 1, "file": {}})
    assert r.status_code == 413
    assert "immagini" not in r.json()["detail"] and "backup" in r.json()["detail"]      # il consiglio sulle immagini vale solo per le immagini


def test_lo_spazio_di_uno_non_conta_per_l_altro(ambiente):
    (_, id_a), (b, _) = nuovo_utente("utentea"), nuovo_utente("utenteb")
    importa(b)
    riempi(id_a, limiti.MAX_BYTE_UTENTE)
    r = b.post("/api/squadre/immagine", params={"squadra": "Mia", "tipo": "stemma"}, files={"file": ("s.png", PNG, "image/png")})
    assert r.status_code == 200


# ---------------------------------------------------------------- interruttore spento
def test_spento_nessun_limite(monkeypatch, tmp_path, dati_isolati, calciatori):
    monkeypatch.delenv("FANTA_MULTIUTENTE", raising=False)
    monkeypatch.setenv("FANTA_DATI_UTENTI", str(tmp_path / "non-deve-esistere"))
    monkeypatch.setattr(server.listone, "carica", lambda *a, **k: (calciatori, "oggi"))
    monkeypatch.setattr(server.consigli, "stagione_corrente", lambda: "2026-27")
    c = cliente()
    for _ in range(limiti.MAX_IMPORTAZIONI_AL_GIORNO + 2):
        assert importa(c, rose_di(limiti.MAX_SQUADRE + 3, limiti.MAX_GIOCATORI_SQUADRA + 3)).status_code == 200
    riempi_locale = server.RADICE / "riempitivo.bin"                  # RADICE è la cartella finta di dati_isolati
    riempi_locale.parent.mkdir(parents=True, exist_ok=True)
    riempi_locale.write_bytes(b"\x00" * (limiti.MAX_BYTE_UTENTE + 10))
    assert c.post("/api/squadre/immagine", params={"squadra": "Squadra 0", "tipo": "stemma"},
                  files={"file": ("s.png", PNG, "image/png")}).status_code == 200
    assert not (tmp_path / "non-deve-esistere").exists()              # nemmeno il database dei contatori


def test_limite_orario_atomico_con_richieste_parallele(multiutente):
    """Tetto all'ora nella tabella dei contatori: con 45 richieste insieme ne passano esattamente 30; la stessa chiave vale una volta."""
    import threading
    (_, uid), (_, altro) = nuovo_utente("utentea"), nuovo_utente("utenteb")
    ctx = type("C", (), {"utente_id": uid})
    esiti, prenotazioni = [], []

    def una(i):
        try:
            prenotazioni.append(limiti.prenota_ora(ctx, "schierate", ("k", i)))
            esiti.append("ok")
        except account.ErroreAccount as e:
            esiti.append(e.stato if hasattr(e, "stato") else "429")
    fili = [threading.Thread(target=una, args=(i,)) for i in range(45)]
    for f in fili:
        f.start()
    for f in fili:
        f.join()
    assert esiti.count("ok") == limiti.MAX_SCHIERATE_ALL_ORA and len(esiti) == 45
    with pytest.raises(account.ErroreAccount):
        limiti.prenota_ora(ctx, "schierate", ("nuova", 1))
    prenotazioni[0].annulla()                                                   # un lavoro fallito restituisce il posto
    assert limiti.prenota_ora(ctx, "schierate", ("nuova", 2)) is not None
    limiti.prenota_ora(type("C", (), {"utente_id": altro}), "schierate", ("k", 0))      # un altro utente non è toccato
    limiti.prenota_ora(type("C", (), {"utente_id": None}), "schierate")                 # senza account nessun limite


def test_schierata_stessa_richiesta_ripetuta_conta_una_volta(multiutente):
    (_, uid) = nuovo_utente("utentea")
    ctx = type("C", (), {"utente_id": uid})
    assert limiti.prenota_ora(ctx, "schierate", ("k", 1)) is not None
    for _ in range(100):                                                        # il 202 ripetuto dall'app
        assert limiti.prenota_ora(ctx, "schierate", ("k", 1)) is None
    for i in range(2, limiti.MAX_SCHIERATE_ALL_ORA + 1):
        limiti.prenota_ora(ctx, "schierate", ("k", i))                          # arriva al tetto esatto senza errori
    with pytest.raises(account.ErroreAccount):
        limiti.prenota_ora(ctx, "schierate", ("altra", 0))
