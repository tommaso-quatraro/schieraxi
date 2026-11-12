"""Anteprima delle rose (piano «Ingresso facile», S1+S2): legge come l'importazione ma non salva niente; le scelte dell'utente sui
dubbi (`correzioni`) e la sua squadra (`mia_squadra`) arrivano insieme all'importazione. Dati finti, cartelle temporanee."""
import dataclasses
import json
import time
from datetime import datetime

import pytest

from fanta import contesto, lega, limiti, nomi, rose, server
from fanta.anteprima_rose import anteprima, applica_correzioni
from fanta.regole import Regole

from test_importa_sicuro import excel_buono
from test_isolamento import albero
from test_limiti import ambiente, importa, nuovo_utente  # noqa: F401 (fixture e utente di prova)
from test_rose_csv import RIDOTTO, codici_del_file, listone_finto

# Rossi è ambiguo (due omonimi, nessun ruolo nel testo), Kean ha una squadra diversa da quella del listone, Pinco Pallino non esiste
TESTO = "Mia\nP\tSommer\t10\nD\tBastoni\t15\nRossi\t7\nC\tLauriente\t4\nC\tPinco Pallino\t3\nA\tKean\tJUV\t30\nAltra\nA\tThuram\t20\n"


@pytest.fixture(autouse=True)
def _niente_ricordi_di_altri_test():
    limiti._gia_contate.clear()
    yield
    limiti._gia_contate.clear()


def leggi(testo, calciatori, correzioni=None, prima=None):
    r, avvisi = Regole(), []
    lette = rose.estrai([("testo", rose.griglia_da_testo(testo))], nomi.Indice(calciatori), r.rosa, avvisi)
    applica_correzioni(lette, correzioni, calciatori)
    return anteprima(lette, avvisi, r, prima, lega.da_import(lette, prima))


def per_testo(risposta, squadra="Mia"):
    s = next(x for x in risposta["squadre"] if x["nome"] == squadra)
    return {g["testo"]: g for g in s["giocatori"]}


# ---------------------------------------------------------------- il modulo, senza server
def test_stati_e_alternative(calciatori):
    a = leggi(TESTO, calciatori)
    g = per_testo(a)
    assert g["Sommer"]["stato"] == "sicuro" and g["Sommer"]["id"] == 2 and g["Sommer"]["alternative"] == []
    assert g["Lauriente"]["stato"] == "sicuro" and g["Lauriente"]["nome"] == "Laurienté"          # senza accento è lo stesso nome
    assert g["Rossi"]["stato"] == "da_controllare" and g["Rossi"]["id"] is None
    assert {x["id"] for x in g["Rossi"]["alternative"]} == {15, 16}
    assert set(g["Rossi"]["alternative"][0]) == {"id", "nome", "ruolo", "squadra"}
    assert g["Kean"]["stato"] == "da_controllare" and "squadra diversa" in g["Kean"]["avviso"]
    assert g["Kean"]["alternative"][0]["id"] == 14                                             # la proposta per prima
    assert g["Pinco Pallino"]["stato"] == "non_trovato" and g["Pinco Pallino"]["nome"] is None
    assert (a["sicuri"], a["da_controllare"], a["non_trovati"]) == (4, 2, 1)
    mia = a["squadre"][0]
    assert (mia["sicuri"], mia["da_controllare"], mia["non_trovati"], mia["totale"], mia["attesi"]) == (3, 2, 1, 6, 25)
    assert mia["ruoli"] == {"P": 1, "D": 1, "C": 2, "A": 1} and mia["senza_ruolo"] == 1 and mia["completa"] is False
    assert mia["mancano"]["P"] == 2 and mia["in_piu"] == {}
    assert "Mia: 6 giocatori su 25" in a["avvisi"] and "Mia: 1 giocatore senza ruolo" in a["avvisi"]
    assert any(x.startswith("Mia: mancano 2 portieri, 7 difensori") for x in a["avvisi"])
    assert a["totale_squadre"] == 2 and a["mia_squadra"] is None and a["differenze"]["prima_importazione"] is True


def test_nomi_per_esteso_e_suggerimenti(calciatori):
    # come li incolla chi comincia: nome e cognome, iniziale in più, un errore che non basta a riconoscerlo
    testo = "Mia\nA\tLautaro Martinez\t40\nA\tKean M.\t20\nD\tDimarko\t10\n"
    g = per_testo(leggi(testo, calciatori))
    assert (g["Lautaro Martinez"]["stato"], g["Lautaro Martinez"]["id"]) == ("da_controllare", 10)
    assert (g["Kean M."]["stato"], g["Kean M."]["id"]) == ("da_controllare", 14)
    assert g["Dimarko"]["stato"] == "non_trovato" and g["Dimarko"]["id"] is None
    assert [x["id"] for x in g["Dimarko"]["alternative"]] == [13]                 # suggerito, non scelto


def test_una_sola_squadra_basta_per_cominciare(calciatori):
    a = leggi("Mia\nP\tSommer\t10\n", calciatori)
    assert a["mia_squadra"] == "Mia"                                   # una sola squadra letta: è la tua (si può cambiare)
    assert any("una sola squadra" in x for x in a["avvisi"])


def test_la_tua_squadra_resta_se_aggiungi_le_rose_degli_altri(calciatori):
    """Prima la propria rosa, poi quelle degli altri: la domanda «qual è la tua squadra?» propone ancora la tua."""
    prima = lega.da_import(rose.estrai([("testo", rose.griglia_da_testo("Mia\nP\tSommer\t10\n"))], nomi.Indice(calciatori)))
    prima.mia_squadra = "Mia"
    assert leggi("Altra\nA\tThuram\t20\nTerza\nA\tKean\t20\n", calciatori, prima=prima)["mia_squadra"] == "Mia"
    assert leggi("Altra\nA\tThuram\t20\n", calciatori, prima=prima)["mia_squadra"] == "Mia"     # non l'unica letta


def test_correzione_su_chi_ce_gia_non_crea_un_doppione(ambiente):
    a, _ = nuovo_utente("utentea")
    corr = [{"squadra": "Mia", "testo": "Rossi", "id": 2}]                      # Sommer, già nella stessa rosa
    assert a.post("/api/rose/testo", json={"testo": TESTO, "correzioni": corr, "mia_squadra": "Mia"}).status_code == 200
    rosa = a.get("/api/rosa").json()
    assert sum(g["id"] == 2 for g in rosa["giocatori"]) == 1


def test_rosa_completa_senza_avvisi(calciatori):
    elenco = [dataclasses.replace(c, ruolo="P" if c.id < 1003 else "D" if c.id < 1011 else "C" if c.id < 1019 else "A")
              for c in listone_finto(range(1000, 1025))]                 # 3 P, 8 D, 8 C, 6 A
    testo = "Mia\n" + "".join(f"{c.ruolo}\t{c.nome}\t1\n" for c in elenco)
    a = leggi(testo, elenco)
    assert a["squadre"][0]["completa"] is True and a["squadre"][0]["avvisi"] == [] and a["sicuri"] == 25


def test_correzioni_scelgono_e_tolgono(calciatori):
    corr = [{"squadra": "Mia", "testo": "Rossi", "id": 15}, {"squadra": "Mia", "testo": "Pinco Pallino", "id": None},
            {"squadra": "Mia", "testo": "Kean", "id": 14}]
    g = per_testo(leggi(TESTO, calciatori, corr))
    assert g["Rossi"]["stato"] == "sicuro" and g["Rossi"]["metodo"] == "manuale" and g["Rossi"]["id"] == 15 and g["Rossi"]["ruolo"] == "D"
    assert "Pinco Pallino" not in g and g["Kean"]["stato"] == "sicuro"


@pytest.mark.parametrize("corr, messaggio", [
    ({"squadra": "Mia", "testo": "Nessuno", "id": 15}, "non corrispondono"),
    ({"squadra": "Inventata", "testo": "Rossi", "id": 15}, "non corrispondono"),
    ({"squadra": "Mia", "testo": "Rossi", "id": 99999}, "non è nel listone"),
])
def test_correzioni_sbagliate(calciatori, corr, messaggio):
    with pytest.raises(ValueError, match=messaggio):
        leggi(TESTO, calciatori, [corr])


# ---------------------------------------------------------------- le rotte
def test_l_anteprima_non_salva_niente(ambiente):
    a, uid = nuovo_utente("utentea")
    assert importa(a, "Vecchia\nP\tSommer\t10\n").status_code == 200
    etag = a.get("/api/rosa").headers["etag"]
    cartella = contesto.cartella_utente(uid)
    prima = albero(cartella)
    r = a.post("/api/rose/anteprima", json={"testo": TESTO})
    assert r.status_code == 200, r.text
    assert r.headers["etag"] == etag and "no-store" in r.headers["cache-control"]
    assert albero(cartella) == prima and a.get("/api/rosa").headers["etag"] == etag
    corpo = r.json()
    assert [s["nome"] for s in corpo["squadre"]] == ["Mia", "Altra"] and all(s["nuova"] for s in corpo["squadre"])
    assert corpo["totale_squadre"] == 3                                  # con «Vecchia», che l'importazione lascerebbe
    assert [s["nome"] for s in a.get("/api/squadre").json()] == ["Vecchia"]


def test_anteprima_di_un_file_rosters(ambiente, monkeypatch):
    testo = RIDOTTO.read_text(encoding="utf-8")
    monkeypatch.setattr(server.listone, "carica", lambda *a, **k: (listone_finto(codici_del_file(testo)), "oggi"))
    a, uid = nuovo_utente("utentea")
    r = a.post("/api/rose/anteprima/file", files={"file": ("rosters.csv", testo.encode(), "text/csv")})
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert [s["nome"] for s in corpo["squadre"]] == ["Real Esempio", "Under Prova"]
    assert [s["totale"] for s in corpo["squadre"]] == [25, 25] and corpo["sicuri"] == 50 and corpo["da_controllare"] == 0
    assert not (contesto.cartella_utente(uid) / "rose.json").exists()
    # e lo stesso testo incollato dà la stessa anteprima
    assert a.post("/api/rose/anteprima", json={"testo": testo}).json()["squadre"] == corpo["squadre"]


def test_anteprima_di_un_excel(ambiente, tmp_path):
    a, uid = nuovo_utente("utentea")
    r = a.post("/api/rose/anteprima/file", files={"file": ("rose.xlsx", excel_buono(tmp_path).read_bytes(), "application/octet-stream")})
    assert r.status_code == 200, r.text
    assert [s["nome"] for s in r.json()["squadre"]] == ["Mia", "Altra"] and r.json()["sicuri"] == 3
    assert not (contesto.cartella_utente(uid) / "rose.json").exists()
    assert list((server.RADICE / "dati" / "cache").glob("*.xlsx")) == []          # il file temporaneo non resta


def test_anteprima_errori_chiari(ambiente):
    a, _ = nuovo_utente("utentea")
    r = a.post("/api/rose/anteprima", json={"testo": "Pos,Punti\n1,30\n"})
    assert r.status_code == 400 and "rosters" in r.json()["detail"]
    assert a.post("/api/rose/anteprima", json={"testo": "x" * 300_000}).status_code == 400
    assert a.post("/api/rose/anteprima", json={"testo": "a\n" * 2000}).status_code == 400
    assert a.post("/api/rose/anteprima/file", files={"file": ("vuoto.csv", b" \n", "text/csv")}).status_code == 400
    assert a.post("/api/rose/anteprima/file", files={"file": ("r.xlsm", b"PK\x03\x04", "application/zip")}).status_code == 400
    r = a.post("/api/rose/anteprima", json={"testo": TESTO, "correzioni": [{"squadra": "Mia", "testo": "Nessuno", "id": 2}]})
    assert r.status_code == 400 and "rifai il controllo" in r.json()["detail"]
    assert a.post("/api/rose/anteprima", json={"testo": TESTO}, headers={"X-Fanta": ""}).status_code == 403


def test_anteprima_e_importazione_dello_stesso_testo_contano_una_volta(ambiente):
    a, uid = nuovo_utente("utentea")
    assert a.post("/api/rose/anteprima", json={"testo": TESTO}).status_code == 200
    assert a.post("/api/rose/anteprima", json={"testo": TESTO, "correzioni": [{"squadra": "Mia", "testo": "Rossi", "id": 15}]}).status_code == 200
    assert limiti.usati_oggi(uid, "importazioni") == 1                  # rifarla dopo aver scelto i dubbi non conta
    assert importa(a, TESTO).status_code == 200
    assert limiti.usati_oggi(uid, "importazioni") == 1                  # l'importazione che segue è già pagata
    assert importa(a, TESTO).status_code == 200
    assert limiti.usati_oggi(uid, "importazioni") == 2                  # ma una volta sola
    assert importa(a, "Altro\nP\tSommer\t10\n").status_code == 200
    assert limiti.usati_oggi(uid, "importazioni") == 3


def test_le_anteprime_hanno_un_tetto(ambiente, monkeypatch):
    monkeypatch.setattr(limiti, "MAX_ANTEPRIME_ALL_ORA", 3)
    a, _ = nuovo_utente("utentea")
    for _ in range(3):
        assert a.post("/api/rose/anteprima", json={"testo": TESTO}).status_code == 200
    r = a.post("/api/rose/anteprima", json={"testo": TESTO})
    assert r.status_code == 429 and "retry-after" in r.headers


def test_le_anteprime_contano_nel_tetto_delle_importazioni(ambiente):
    a, _ = nuovo_utente("utentea")
    for i in range(limiti.MAX_IMPORTAZIONI_AL_GIORNO):
        assert a.post("/api/rose/anteprima", json={"testo": f"Squadra {i}\nP\tSommer\t10\n"}).status_code == 200
    assert a.post("/api/rose/anteprima", json={"testo": "Ancora\nP\tSommer\t10\n"}).status_code == 429
    # l'anteprima rifiutata NON lascia un buono: importare quel testo resta oltre il tetto (revisione della PR #483)
    assert importa(a, "Ancora\nP\tSommer\t10\n").status_code == 429
    assert a.post("/api/rose/file", files={"file": ("r.txt", b"Ancora\nP\tSommer\t10\n", "text/plain")}).status_code == 429
    assert a.post("/api/rose/anteprima", json={"testo": "Ancora\nP\tSommer\t10\n"}).status_code == 429   # e neanche rifarla


def test_la_chiave_non_si_ricorda_se_il_tetto_rifiuta(ambiente):
    _, uid = nuovo_utente("utentea")
    ctx = type("C", (), {"utente_id": uid})()
    for _ in range(limiti.MAX_IMPORTAZIONI_AL_GIORNO):
        limiti.conta(ctx, "importazioni")
    with pytest.raises(limiti.ErroreAccount):
        limiti.conta(ctx, "importazioni", chiave="qualcosa")
    assert not limiti.gia_contata_oggi(ctx, "importazioni", "qualcosa")


def test_il_buono_torna_se_l_importazione_fallisce(ambiente):
    a, uid = nuovo_utente("utentea")
    assert a.post("/api/rose/anteprima", json={"testo": TESTO}).status_code == 200
    assert limiti.usati_oggi(uid, "importazioni") == 1
    assert a.post("/api/rose/testo", json={"testo": TESTO, "mia_squadra": "Inesistente"}).status_code == 400
    r = a.post("/api/rose/testo", json={"testo": TESTO, "correzioni": [{"squadra": "Mia", "testo": "Rossi", "id": 99999}]})
    assert r.status_code == 400
    assert limiti.usati_oggi(uid, "importazioni") == 1                  # il primo errore ha restituito il buono, il secondo l'ha usato
    assert importa(a, TESTO).status_code == 200
    assert limiti.usati_oggi(uid, "importazioni") == 2                  # il buono torna una volta sola per lo stesso contenuto
    # con un file e le rose cambiate nel frattempo (412): il buono non si tocca
    file = {"file": ("rose.txt", TESTO.replace("Thuram\t20", "Thuram\t21").encode(), "text/plain")}
    etag = a.post("/api/rose/anteprima/file", files=file).headers["etag"]
    assert limiti.usati_oggi(uid, "importazioni") == 3
    assert importa(a, "Altro\nP\tSommer\t10\n").status_code == 200       # le rose cambiano
    assert limiti.usati_oggi(uid, "importazioni") == 4
    assert a.post("/api/rose/file", files=file, headers={"If-Match": etag}).status_code == 412
    assert a.post("/api/rose/file", files=file).status_code == 200
    assert limiti.usati_oggi(uid, "importazioni") == 4


def test_il_buono_non_torna_all_infinito(ambiente, tmp_path):
    """Revisione: con una sola anteprima si poteva rimandare per sempre un file che fallisce (ogni volta un Excel aperto in un
    processo a parte), senza mai toccare il tetto delle importazioni. Qui con un file di testo (stessa strada del buono, senza
    caricare i runner lenti con decine di processi per l'Excel)."""
    a, uid = nuovo_utente("utentea")
    file = {"file": ("rose.txt", TESTO.encode(), "text/plain")}
    assert a.post("/api/rose/anteprima/file", files=file).status_code == 200
    assert limiti.usati_oggi(uid, "importazioni") == 1
    codici, contati = [], []
    for _ in range(50):
        codici.append(a.post("/api/rose/file", files=file, data={"mia_squadra": "Inesistente"}).status_code)
        contati.append(limiti.usati_oggi(uid, "importazioni"))
    assert codici[:2] == [400, 400] and contati[:2] == [1, 1]          # il buono torna una volta, poi si consuma
    assert contati[2] == 2                                              # dal terzo invio conta come sempre
    assert contati[-1] == limiti.MAX_IMPORTAZIONI_AL_GIORNO and codici[-1] == 429


def test_un_excel_alla_volta(ambiente, tmp_path, monkeypatch):
    """Revisione: ogni lettura di un Excel è un processo che può arrivare a 1 GB; più letture insieme fanno chiudere il servizio.
    Se un'altra lettura è in corso: 503 «riprova tra poco», e né l'anteprima né l'importazione contano."""
    monkeypatch.setattr(server, "ATTESA_LETTURA_EXCEL", 0.05)
    a, uid = nuovo_utente("utentea")
    file = {"file": ("rose.xlsx", excel_buono(tmp_path).read_bytes(), "application/octet-stream")}
    assert server._letture_excel.acquire(timeout=1)                    # un'altra lettura in corso
    try:
        r = a.post("/api/rose/anteprima/file", files=file)
        assert r.status_code == 503 and r.json()["detail"] == server.OCCUPATO_EXCEL and r.headers["retry-after"]
        assert limiti.usati_oggi(uid, "importazioni") == 0              # anteprima mai cominciata: non conta
        assert a.post("/api/rose/file", files=file).status_code == 503
        assert limiti.usati_oggi(uid, "importazioni") == 0              # occupato = non conta
    finally:
        server._letture_excel.release()
    assert a.post("/api/rose/anteprima/file", files=file).status_code == 200
    assert limiti.usati_oggi(uid, "importazioni") == 1
    assert a.post("/api/rose/file", files=file).status_code == 200      # col buono dell'anteprima
    assert limiti.usati_oggi(uid, "importazioni") == 1
    assert a.post("/api/rose/file", files=file).status_code == 200
    assert limiti.usati_oggi(uid, "importazioni") == 2
    assert server._letture_excel.acquire(blocking=False)                # e il semaforo è libero
    server._letture_excel.release()


def test_excel_occupato_ha_un_tetto_e_non_lavora_a_vuoto(ambiente, tmp_path, monkeypatch):
    """Revisione: con il semaforo occupato ogni invio di un Excel scriveva il temporaneo e controllava lo zip (fino a 20 MB di XML),
    teneva un thread per l'attesa e non contava: decine di richieste potevano occupare tutti i thread del servizio.
    Ora il turno si prende prima di ogni lavoro e i 503 gratuiti hanno un tetto orario; oltre, 429 subito."""
    monkeypatch.setattr(server, "ATTESA_LETTURA_EXCEL", 0.01)
    zip_controllati, temporanei = [], []
    vero_zip, vero_temp = server.importa_sicuro.controlla_zip, server.tempfile.NamedTemporaryFile
    monkeypatch.setattr(server.importa_sicuro, "controlla_zip", lambda p: zip_controllati.append(p) or vero_zip(p))
    monkeypatch.setattr(server.tempfile, "NamedTemporaryFile", lambda *a, **k: temporanei.append(1) or vero_temp(*a, **k))
    a, uid = nuovo_utente("utentea")
    base = excel_buono(tmp_path).read_bytes()
    codici = []
    assert server._letture_excel.acquire(timeout=1)
    try:
        for i in range(100):
            file = {"file": (f"r{i}.xlsx", base + f"diverso {i}".encode(), "application/octet-stream")}
            codici.append(a.post("/api/rose/file", files=file).status_code)
        monkeypatch.setattr(server, "ATTESA_LETTURA_EXCEL", 5.0)
        partenza = time.monotonic()
        assert a.post("/api/rose/file", files={"file": ("x.xlsx", base + b"x", "application/octet-stream")}).status_code == 429
        assert time.monotonic() - partenza < 2                          # oltre il tetto: risposta subito, senza attesa
    finally:
        server._letture_excel.release()
    n = limiti.MAX_EXCEL_OCCUPATO_ALL_ORA
    assert codici[:n] == [503] * n and codici[n:] == [429] * (100 - n)
    assert zip_controllati == [] and temporanei == []                  # nessun lavoro a vuoto
    assert limiti.usati_oggi(uid, "importazioni") == limiti.MAX_IMPORTAZIONI_AL_GIORNO   # i tentativi oltre il tetto contano


def test_il_turno_si_libera_anche_se_la_lettura_fallisce(ambiente, tmp_path, monkeypatch):
    a, _ = nuovo_utente("utentea")
    rotto = {"file": ("rotto.xlsx", b"PK\x03\x04 non sono un vero Excel", "application/octet-stream")}
    assert a.post("/api/rose/file", files=rotto).status_code == 400
    assert a.post("/api/rose/anteprima/file", files=rotto).status_code == 400
    assert server._letture_excel.acquire(blocking=False)
    server._letture_excel.release()
    monkeypatch.setattr(server.importa_sicuro, "TEMPO_MASSIMO", 0.001)  # il processo che legge va oltre il tempo massimo
    file = {"file": ("rose.xlsx", excel_buono(tmp_path).read_bytes(), "application/octet-stream")}
    r = a.post("/api/rose/file", files=file)
    assert r.status_code == 400 and r.json()["detail"] == server.importa_sicuro.PESANTE
    assert server._letture_excel.acquire(blocking=False)
    server._letture_excel.release()


def test_a_mezzanotte_si_restituisce_nel_giorno_del_conteggio(ambiente, monkeypatch):
    """Revisione: il buono o l'importazione si restituivano nel giorno del 503, non in quello del conteggio."""
    _, uid = nuovo_utente("utentea")
    ctx = type("C", (), {"utente_id": uid})()
    orologio = [datetime(2026, 11, 2, 23, 59, 59)]
    monkeypatch.setattr(limiti, "_adesso", lambda: orologio[0])
    with pytest.raises(server.ExcelOccupato):
        with server._buono_dell_anteprima(ctx, "impronta"):
            assert limiti.usati_oggi(uid, "importazioni") == 1
            orologio[0] = datetime(2026, 11, 3, 0, 0, 1)
            raise server.ExcelOccupato()
    assert limiti.usati_oggi(uid, "importazioni") == 0                  # domani niente di regalato
    orologio[0] = datetime(2026, 11, 2, 23, 59, 59)
    assert limiti.usati_oggi(uid, "importazioni") == 0                  # e ieri l'importazione è tornata
    # col buono dell'anteprima: torna nel giorno dell'anteprima, non nel giorno dopo
    limiti.conta_anteprima(ctx, "altra")
    with pytest.raises(ValueError):
        with server._buono_dell_anteprima(ctx, "altra"):
            orologio[0] = datetime(2026, 11, 3, 0, 0, 1)
            raise ValueError("fallita")
    assert limiti.chiave_anteprima("altra") in limiti._gia_contate[(uid, "2026-11-02", "importazioni")]
    assert limiti.chiave_anteprima("altra") not in limiti._gia_contate.get((uid, "2026-11-03", "importazioni"), set())


def test_importazione_con_correzioni_e_mia_squadra(ambiente):
    a, _ = nuovo_utente("utentea")
    corr = [{"squadra": "Mia", "testo": "Rossi", "id": 16}, {"squadra": "Mia", "testo": "Pinco Pallino", "id": None}]
    r = a.post("/api/rose/testo", json={"testo": TESTO, "correzioni": corr, "mia_squadra": "Mia"})
    assert r.status_code == 200, r.text
    assert r.json()["mia_squadra"] == "Mia"
    rosa = a.get("/api/rosa").json()
    assert rosa["nome"] == "Mia" and rosa["mia"] is True
    rossi = next(g for g in rosa["giocatori"] if g["nome"] == "Rossi")
    assert (rossi["id"], rossi["ruolo"], rossi["squadra"], rossi["riconosciuto"]) == (16, "A", "LEC", "manuale")
    assert all(g["nome"] != "Pinco Pallino" for g in rosa["giocatori"])
    # con un file: gli stessi campi nel modulo multipart
    r = a.post("/api/rose/file", files={"file": ("rose.txt", TESTO.encode(), "text/plain")},
               data={"correzioni": json.dumps(corr), "mia_squadra": "Altra"})
    assert r.status_code == 200, r.text
    assert r.json()["mia_squadra"] == "Altra"
    assert next(g for g in a.get("/api/rosa", params={"squadra": "Mia"}).json()["giocatori"] if g["nome"] == "Rossi")["id"] == 16


def test_importazione_con_scelte_sbagliate_non_salva(ambiente):
    a, uid = nuovo_utente("utentea")
    assert importa(a, "Vecchia\nP\tSommer\t10\n").status_code == 200
    prima = albero(contesto.cartella_utente(uid))
    r = a.post("/api/rose/testo", json={"testo": TESTO, "mia_squadra": "Inesistente"})
    assert r.status_code == 400 and "squadra scelta come tua" in r.json()["detail"]
    r = a.post("/api/rose/testo", json={"testo": TESTO, "correzioni": [{"squadra": "Mia", "testo": "Rossi", "id": 99999}]})
    assert r.status_code == 400 and "listone" in r.json()["detail"]
    for male in ("non è json", json.dumps([{"squadra": "Mia"}]), json.dumps({"a": 1})):
        r = a.post("/api/rose/file", files={"file": ("rose.txt", TESTO.encode(), "text/plain")}, data={"correzioni": male})
        assert r.status_code == 422 and r.json()["detail"] == server.DATI_NON_VALIDI
    assert albero(contesto.cartella_utente(uid)) == prima


def test_senza_i_campi_nuovi_tutto_come_prima(ambiente):
    a, _ = nuovo_utente("utentea")
    r = importa(a, TESTO)
    assert r.status_code == 200
    assert set(r.json()) == {"squadre_importate", "totale_squadre", "avvisi", "mia_squadra", "differenze", "riepilogo"}
    assert r.json()["mia_squadra"] is None
    rossi = next(g for g in a.get("/api/rosa", params={"squadra": "Mia"}).json()["giocatori"] if g["nome"] == "Rossi")
    assert rossi["id"] is None and rossi["riconosciuto"] == "ambiguo"
    assert a.post("/api/rose/file", files={"file": ("rose.txt", TESTO.encode(), "text/plain")}).status_code == 200


def test_senza_account_l_anteprima_funziona_e_non_salva(dati_isolati, calciatori, monkeypatch):
    monkeypatch.delenv("FANTA_MULTIUTENTE", raising=False)
    monkeypatch.setattr(server.listone, "carica", lambda *a, **k: (calciatori, "oggi"))
    from test_account_http import cliente
    c = cliente()
    r = c.post("/api/rose/anteprima", json={"testo": TESTO})
    assert r.status_code == 200, r.text
    assert r.json()["da_controllare"] == 2
    assert [p for p in dati_isolati.rglob("*") if p.is_file()] == []


# ---------------------------------------------------------------- file delle rose rovinato (#650)
def _tronca(testo: str) -> str:
    return testo[: len(testo) // 2]


def _stagione_scritta_male(testo: str) -> str:
    return json.dumps(json.loads(testo) | {"stagione": "2026/27"})


@pytest.mark.parametrize("rovina", [_tronca, _stagione_scritta_male])
def test_file_delle_rose_rovinato_si_rimedia_importando(ambiente, rovina):
    """Il messaggio di errore dice «importa di nuovo le rose»: anteprima e importazione funzionano, il file rovinato resta da
    parte e la copia di riserva di prima non cambia."""
    a, uid = nuovo_utente("utentea")
    file_rose = contesto.Contesto.per_utente(uid).rose
    riserva = file_rose.with_name("rose.json.bak")
    assert importa(a, "Prima\nP\tSommer\t10\n").status_code == 200
    assert importa(a, "Mia\nP\tSommer\t10\nAltra\nA\tKean\t30\n").status_code == 200
    copia_buona = riserva.read_bytes()
    rovinato = rovina(file_rose.read_text(encoding="utf-8"))
    file_rose.write_text(rovinato, encoding="utf-8")
    assert a.get("/api/squadre").status_code == 400                       # ogni schermata lo dice
    testo = "Nuova\nD\tBastoni\t5\n"
    r = a.post("/api/rose/anteprima", json={"testo": testo})
    assert r.status_code == 200, r.text
    assert r.json()["totale_squadre"] == 1 and lega.ROSE_ROVINATE in r.json()["avvisi"]
    assert file_rose.read_text(encoding="utf-8") == rovinato                # l'anteprima non scrive niente
    r = importa(a, testo)
    assert r.status_code == 200, r.text
    assert lega.ROSE_ROVINATE in r.json()["avvisi"] and r.json()["totale_squadre"] == 1
    assert [s["nome"] for s in a.get("/api/squadre").json()] == ["Nuova"]
    assert riserva.read_bytes() == copia_buona                             # la copia buona di prima resta
    assert file_rose.with_name("rose.json.rovinato").read_text(encoding="utf-8") == rovinato


def test_importazione_rifiutata_non_sposta_il_file_rovinato(ambiente):
    """Se l'importazione non va a buon fine (qui la squadra scelta non c'è nel file) il file resta dov'era."""
    a, uid = nuovo_utente("utentea")
    file_rose = contesto.Contesto.per_utente(uid).rose
    assert importa(a).status_code == 200
    file_rose.write_text('{"squadre": [', encoding="utf-8")
    r = a.post("/api/rose/testo", json={"testo": "Nuova\nD\tBastoni\t5\n", "mia_squadra": "Non c'è"})
    assert r.status_code == 400, r.text
    assert file_rose.read_text(encoding="utf-8") == '{"squadre": [' and not file_rose.with_name("rose.json.rovinato").exists()
