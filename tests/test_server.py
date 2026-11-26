"""Server dell'app: regole e importazione rose, su file temporanei (la lega vera non viene toccata)."""
import contextlib
import json
import subprocess
import sys
import threading

import pytest
from fastapi.testclient import TestClient

from fanta import server
from fanta.regole import Regole, da_dict as regole_da_dict


@pytest.fixture
def client(dati_isolati, tmp_path, monkeypatch, calciatori):
    """L'app di sempre su file temporanei: con `dati_isolati` anche l'archivio e la `dati/` del repository restano fuori (#582)."""
    monkeypatch.setattr(server, "FILE_REGOLE", tmp_path / "regole.json")
    monkeypatch.setattr(server, "FILE_ROSE", tmp_path / "rose.json")
    monkeypatch.setattr(server.listone, "carica", lambda *a, **k: (calciatori, "oggi"))
    return TestClient(server.app, headers={"X-Fanta": "1"})


def test_richiesta_interrotta_dal_browser_non_e_un_errore(client, monkeypatch, capsys):
    async def interrotta(request, chiama):
        raise RuntimeError("No response returned.")
    monkeypatch.setattr(server, "_risposta", interrotta)
    assert client.get("/api/regole").status_code == 499
    assert "Traceback" not in capsys.readouterr().err


def test_senza_rose_il_messaggio_dice_cosa_toccare_senza_un_percorso_di_menu(client):
    """Senza rose il server rimanda ad «Aggiorna le rose», senza un percorso di menu: la frase arriva uguale alla web e all'iPhone,
    che hanno menu diversi (#618). Comincia sempre con «Nessuna rosa importata»: web e iPhone la riconoscono da lì."""
    r = client.get("/api/rosa")
    assert r.status_code == 409
    testo = r.json()["detail"]
    assert testo.startswith("Nessuna rosa importata") and "«Aggiorna le rose»" in testo and ">" not in testo, testo


def test_senza_la_mia_squadra_il_messaggio_non_ha_un_percorso_di_menu(client, tmp_path):
    (tmp_path / "rose.json").write_text(json.dumps({"squadre": [{"nome": "Squadra Uno", "giocatori": []}], "mia_squadra": None}),
                                        encoding="utf-8")
    r = client.get("/api/scambi/proposte")
    assert r.status_code == 400
    testo = r.json()["detail"]
    assert "«La mia squadra»" in testo and ">" not in testo, testo


def test_pagina_e_file_dell_app(client):
    assert client.get("/").status_code == 200
    for f in ("/app.js", "/primoavvio.js", "/stile.css", "/manifest.webmanifest", "/sw.js", "/icona-180.png"):
        assert client.get(f).status_code == 200, f


def test_regole_lettura_scrittura_e_controlli(client):
    r = client.get("/api/regole").json()
    assert r["bonus"]["assist"] == Regole().bonus.assist
    r["bonus"]["gol"]["D"] = 4.5
    assert client.put("/api/regole", json=r).status_code == 200
    assert client.get("/api/regole").json()["bonus"]["gol"]["D"] == 4.5
    r["moduli"] = ["3-4-4"]
    risposta = client.put("/api/regole", json=r)
    assert risposta.status_code == 400 and "3-4-4" in risposta.json()["detail"]
    assert client.get("/api/regole").json()["moduli"] != ["3-4-4"]      # quelle sbagliate non si salvano


def test_regole_rifiutano_valori_esagerati_e_infiniti(client):
    import json
    base = client.get("/api/regole").json()

    def prova(**cambi):
        r = json.loads(json.dumps(base))
        for chiave, valore in cambi.items():
            dove = r
            *percorso, ultima = chiave.split("__")
            for k in percorso:
                dove = dove[k]
            dove[ultima] = valore
        return client.put("/api/regole", json=r)
    assert prova(moduli=["4-4-2", "4-4-2"]).status_code == 400
    assert prova(moduli=["4-4-2"] * 31).status_code == 422          # oltre i tetti di misura (#480)
    assert prova(rosa__D=31).status_code == 400
    assert prova(panchina__max_sostituzioni=11).status_code == 400
    # Infinity e NaN: prima davano OverflowError (errore 500)
    for testo in ("Infinity", "-Infinity", "NaN"):
        corpo = json.dumps(base).replace('"scadenza_minuti": 0', f'"scadenza_minuti": {testo}', 1)
        assert '"scadenza_minuti": ' + testo in corpo
        r = client.put("/api/regole", content=corpo, headers={"Content-Type": "application/json"})
        assert r.status_code == 400, (testo, r.status_code)
    corpo = json.dumps(base).replace('"fattore_campo": 0.0', '"fattore_campo": Infinity', 1)
    assert client.put("/api/regole", content=corpo, headers={"Content-Type": "application/json"}).status_code == 400

def test_schierata_calcola_fuori_dal_blocco_delle_scelte(client, monkeypatch):
    """Le simulazioni non tengono il lucchetto delle scelte (valido per tutti); il lucchetto serve solo a scrivere."""
    from fanta import diario, versioni
    visto = {}

    def prepara(*a, **k):
        visto["libero_durante_il_calcolo"] = not versioni.blocco("scelte").locked()
        return {"schierata": {"modulo": "4-4-2"}}, [1]
    from fanta.lega import Rose
    monkeypatch.setattr(server, "_rose", lambda ctx: Rose())
    monkeypatch.setattr(diario, "prepara_schierata", prepara)
    monkeypatch.setattr(diario, "scrivi_schierata", lambda *a, **k: visto.setdefault("scritto_con_lucchetto", versioni.blocco("scelte").locked()))
    r = client.post("/api/diario/schierata", json={"giornata": 3, "tipo": "consigliata"})
    assert r.status_code == 200, r.text
    assert visto == {"libero_durante_il_calcolo": True, "scritto_con_lucchetto": True}


def test_schierata_con_regole_cambiate_durante_il_calcolo_risponde_409(client, monkeypatch):
    from fanta import diario
    from fanta.lega import Rose
    from fanta import calcolo
    calcolo.cache.clear()                                                         # il test precedente ha lasciato lo stesso risultato in memoria
    stato = {"regole": Regole()}
    scritto = []
    monkeypatch.setattr(server, "_rose", lambda ctx: Rose())
    monkeypatch.setattr(server, "_regole", lambda ctx: stato["regole"])

    def prepara(*a, **k):
        stato["regole"] = Regole(nome_lega="cambiata nel frattempo")          # qualcuno salva le regole mentre si calcola
        return {"schierata": {"modulo": "4-4-2"}}, [1]
    monkeypatch.setattr(diario, "prepara_schierata", prepara)
    monkeypatch.setattr(diario, "scrivi_schierata", lambda *a, **k: scritto.append(1))
    r = client.post("/api/diario/schierata", json={"giornata": 3, "tipo": "consigliata"})
    assert r.status_code == 409 and scritto == []



def test_dati_non_validi_una_frase_chiara_e_i_campi_a_parte(client):
    """Prima rispondeva «Dati non validi: controlla corpo» (o il nome interno del campo): ora una frase per l'utente, i campi in `campi`."""
    for percorso, metodo in (("/api/primo-avvio", client.put), ("/api/diario/schierata", client.post), ("/api/avvisi", client.put)):
        r = metodo(percorso, content=b"{ non json", headers={"Content-Type": "application/json"})
        assert r.status_code == 422 and r.json() == {"detail": server.DATI_NON_VALIDI, "campi": ["corpo"]}, (percorso, r.text)
    r = client.put("/api/avvisi", json={"silenzio_da": 24})                      # il campo sbagliato resta indicato, ma non nel messaggio
    assert r.json()["detail"] == server.DATI_NON_VALIDI and r.json()["campi"] == ["silenzio_da"]
    assert "corpo" not in server.DATI_NON_VALIDI and "controlla" in server.DATI_NON_VALIDI


def test_import_rose_da_testo_e_mia_squadra(client):
    assert client.get("/api/squadre").status_code == 409                # niente rose ancora
    testo = "Real Esempio\nP\tSommer\t10\nD\tBastoni\t15\nI Bomber\nA\tKean\t30\n"
    esito = client.post("/api/rose/testo", json={"testo": testo}).json()
    assert esito["squadre_importate"] == ["Real Esempio", "I Bomber"]
    assert client.put("/api/mia-squadra", json={"nome": "real"}).json() == {"mia_squadra": "Real Esempio"}
    squadre = client.get("/api/squadre").json()
    assert [s["nome"] for s in squadre if s["mia"]] == ["Real Esempio"]
    # reimportando solo una squadra l'altra resta
    client.post("/api/rose/testo", json={"testo": "I Bomber\nA\tKean\t31\n"})
    assert len(client.get("/api/squadre").json()) == 2


def test_import_file_senza_estensione_riconosce_excel(client, tmp_path):
    from openpyxl import Workbook
    wb = Workbook(); ws = wb.active
    ws.append(["Real Esempio"]); ws.append(["P", "Sommer", "INT", 10]); ws.append(["D", "Bastoni", "INT", 15])
    f = tmp_path / "rose.xlsx"; wb.save(f)
    r = client.post("/api/rose/file", files={"file": ("Rose_LegaProva", f.read_bytes(), "application/octet-stream")})
    assert r.status_code == 200 and r.json()["squadre_importate"] == ["Real Esempio"]
    assert client.post("/api/rose/file", files={"file": ("senzaestensione", b"%PDF-1.4", "application/pdf")}).status_code == 400


def test_import_file_formato_sbagliato(client):
    r = client.post("/api/rose/file", files={"file": ("rose.pdf", b"%PDF", "application/pdf")})
    assert r.status_code == 400


def test_altri_siti_non_possono_modificare(client):
    estraneo = TestClient(server.app)          # senza l'intestazione dell'app
    assert estraneo.post("/api/aggiorna").status_code == 403
    assert estraneo.post("/api/rose/testo", json={"testo": "x"}).status_code == 403
    assert estraneo.get("/api/regole").status_code == 200      # leggere si può


def _fine_aggiornamento():
    """Aspetta che il lavoro avviato da POST /api/aggiorna finisca e lasci i blocchi (un thread del server). Il lavoro mette
    `in_corso` a falso, poi lascia il blocco su file e per ultimo il lucchetto interno: lucchetto libero = tutto lasciato.
    Il tempo massimo evita solo il test appeso."""
    import time
    fine = time.monotonic() + 30
    while time.monotonic() < fine:
        if not server._aggiornamento["in_corso"] and server._blocco.acquire(blocking=False):
            server._blocco.release()
            return
        time.sleep(0.01)
    raise AssertionError("il lavoro di POST /api/aggiorna non ha lasciato i blocchi in 30 secondi")


def test_aggiorna_dall_app_non_parte_con_l_aggiornamento_programmato_in_corso(client, monkeypatch):
    """«Aggiorna i dati» mentre gira l'aggiornamento programmato del server (o un giro leggero di un altro processo): il blocco su file
    è occupato, quindi niente secondo aggiornamento insieme (le stesse pagine chieste due volte alle fonti, #660). Libero, parte; e il
    blocco resta preso fino alla fine del lavoro."""
    import contextlib
    chiamate, tenuto = [], []
    monkeypatch.setattr(server.aggiorna, "esegui", lambda **k: chiamate.append(bool(tenuto)) or [])
    monkeypatch.setattr(server.pianificatore, "blocco_processo", lambda: contextlib.nullcontext(False))
    assert client.post("/api/aggiorna").json() == {"avviato": False, "messaggio": "Aggiornamento già in corso"}
    assert chiamate == [] and not server._aggiornamento["in_corso"]

    @contextlib.contextmanager
    def libero():
        tenuto.append(1)
        try:
            yield True
        finally:
            tenuto.clear()
    monkeypatch.setattr(server.pianificatore, "blocco_processo", libero)
    assert client.post("/api/aggiorna").json() == {"avviato": True}          # il lucchetto interno non è rimasto preso
    _fine_aggiornamento()
    assert chiamate == [True] and tenuto == []                              # tenuto durante il lavoro, lasciato alla fine


def test_aggiorna_con_tutte_le_fonti_spente_lo_dice_e_non_parte(client, monkeypatch):
    """«Aggiorna i dati» con le fonti dell'aggiornamento spente (#779): prima ogni passo si saltava e l'avviso diceva «Dati
    aggiornati». Ora la risposta dice che nessuna fonte è accesa e il lavoro non parte; football-data conta solo con le fonti in
    ombra accese, ESPN e le foto non contano. Riaccesa una fonte, il pulsante riparte (niente lucchetto rimasto preso)."""
    import contextlib

    from fanta import fonti_attive, funzioni
    chiamate = []
    monkeypatch.setattr(server.aggiorna, "esegui", lambda **k: chiamate.append(1) or [])
    monkeypatch.setattr(server.pianificatore, "blocco_processo", lambda: contextlib.nullcontext(True))
    for fonte in fonti_attive.FONTI:
        fonti_attive.imposta(fonte, fonte in ("espn", "footballdata"))
    funzioni.imposta("fonti_ombra", False)
    r = client.post("/api/aggiorna").json()
    assert r["avviato"] is False and "Nessuna fonte di dati è accesa" in r["messaggio"], r
    assert chiamate == [] and not server._aggiornamento["in_corso"]

    fonti_attive.imposta("understat", True)
    assert client.post("/api/aggiorna").json() == {"avviato": True}
    _fine_aggiornamento()
    assert chiamate == [1]


def test_aggiorna_dall_app_non_si_rilancia_prima_di_dieci_minuti(client, monkeypatch):
    """Prima «Aggiorna i dati» si poteva premere di continuo, e ogni giro rifà tutte le richieste alle fonti. Ora fra la fine di
    un giro e l'avvio del successivo passano almeno 10 minuti: prima la risposta dice fra quanto riprovare (minuti arrotondati
    per eccesso, `riprova_tra` in secondi) e il lavoro non parte."""
    import contextlib
    ora = [1000.0]
    chiamate = []
    monkeypatch.setattr(server, "_orologio_aggiorna", lambda: ora[0])
    monkeypatch.setattr(server.aggiorna, "esegui", lambda **k: chiamate.append(1) or [])
    monkeypatch.setattr(server.pianificatore, "blocco_processo", lambda: contextlib.nullcontext(True))
    assert client.post("/api/aggiorna").json() == {"avviato": True}
    _fine_aggiornamento()
    ora[0] += 61
    assert client.post("/api/aggiorna").json() == {"avviato": False, "riprova_tra": 539,
                                                   "messaggio": "I dati sono stati aggiornati da poco: riprova fra 9 minuti."}
    ora[0] += 538
    assert client.post("/api/aggiorna").json()["messaggio"] == "I dati sono stati aggiornati da poco: riprova fra 1 minuto."
    assert chiamate == [1] and not server._aggiornamento["in_corso"]
    ora[0] += 1                                                             # 10 minuti dalla fine: riparte
    assert client.post("/api/aggiorna").json() == {"avviato": True}
    _fine_aggiornamento()
    assert chiamate == [1, 1]


def test_stato_dice_aggiornamento_in_corso_anche_se_lo_fa_un_altro(client, monkeypatch):
    """`aggiornamento_in_corso` di /api/stato è vero anche quando i dati li sta aggiornando un altro (l'aggiornamento programmato
    del server o un giro leggero, che tengono il blocco su file), non solo dopo «Aggiorna i dati» da qui (#763)."""
    monkeypatch.setattr(server.pianificatore, "blocco_tenuto", lambda: True)
    assert client.get("/api/stato").json()["aggiornamento_in_corso"] is True
    monkeypatch.setattr(server.pianificatore, "blocco_tenuto", lambda: False)
    assert client.get("/api/stato").json()["aggiornamento_in_corso"] is False


# L'altro processo, come l'aggiornamento programmato (`exec 9>>…/blocco; flock 9` in aggiorna.sh): tiene il blocco su file
# finché non riceve il «via». «condiviso» fa come un'altra lettura dello stato in corso.
FIGLIO_BLOCCO = r"""
import fcntl, sys
with open(sys.argv[1], "ab") as f:
    fcntl.flock(f, fcntl.LOCK_SH if sys.argv[2] == "condiviso" else fcntl.LOCK_EX)
    print("preso", flush=True)
    sys.stdin.readline()
"""
SOLO_LINUX = pytest.mark.skipif(sys.platform == "win32", reason="il blocco dell'aggiornamento c'è solo dove c'è fcntl, come sul server")


@contextlib.contextmanager
def _blocco_di_un_altro_processo(file, modo="esclusivo"):
    figlio = subprocess.Popen([sys.executable, "-I", "-c", FIGLIO_BLOCCO, str(file), modo], cwd=file.parent, text=True,
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    guardia = threading.Timer(60, figlio.kill)       # solo se il figlio resta appeso: il test non deve bloccare la suite
    guardia.start()
    try:
        assert figlio.stdout.readline().strip() == "preso"
        yield
    finally:
        with contextlib.suppress(OSError):
            figlio.stdin.write("via\n")
            figlio.stdin.flush()
        figlio.wait(30)
        guardia.cancel()


@SOLO_LINUX
def test_stato_con_il_blocco_tenuto_da_un_altro_processo(client, tmp_path, monkeypatch):
    """Il blocco vero, tenuto da un altro processo: «aggiornamento in corso» finché lo tiene, poi no. La lettura non aspetta, non
    lascia il blocco preso (un giro leggero subito dopo parte), non vede come aggiornamento un'altra lettura in corso e non crea
    il file se manca (#763)."""
    file = tmp_path / "blocco"
    monkeypatch.setattr(server.pianificatore, "file_blocco", lambda: file)
    with _blocco_di_un_altro_processo(file):
        assert client.get("/api/stato").json()["aggiornamento_in_corso"] is True
    assert client.get("/api/stato").json()["aggiornamento_in_corso"] is False
    with server.pianificatore.blocco_processo() as libero:
        assert libero is True
    with _blocco_di_un_altro_processo(file, "condiviso"):
        assert client.get("/api/stato").json()["aggiornamento_in_corso"] is False
    manca = tmp_path / "manca" / "blocco"
    monkeypatch.setattr(server.pianificatore, "file_blocco", lambda: manca)
    assert client.get("/api/stato").json()["aggiornamento_in_corso"] is False
    assert not manca.parent.exists()


@SOLO_LINUX
def test_la_lettura_del_blocco_non_fa_rinunciare_un_giro_leggero(tmp_path, monkeypatch):
    """Un giro leggero (o «Aggiorna i dati») prova il blocco senza aspettare: se in quell'istante lo tiene la lettura di
    /api/stato, aspetta la fine della lettura invece di rinunciare come se l'aggiornamento programmato fosse in corso (#763)."""
    import fcntl
    file = tmp_path / "blocco"
    file.touch()
    monkeypatch.setattr(server.pianificatore, "file_blocco", lambda: file)
    vero, esiti, giri = fcntl.flock, [], []

    def giro():
        with server.pianificatore.blocco_processo() as libero:
            esiti.append(libero)

    def flock(fd, modo):
        vero(fd, modo)
        if modo == fcntl.LOCK_SH | fcntl.LOCK_NB and not giri:      # la lettura ha il blocco in mano: proprio ora parte un giro
            giri.append(threading.Thread(target=giro))
            giri[0].start()
            giri[0].join(0.5)                                      # il giro deve aspettare la lettura, non finire qui con «occupato»
    monkeypatch.setattr(fcntl, "flock", flock)
    assert server.pianificatore.blocco_tenuto() is False
    giri[0].join(30)
    assert esiti == [True]


def test_app_sempre_aggiornata_sul_telefono(client):
    assert client.get("/app.js").headers["cache-control"] == "no-cache"


def test_scheda_rendimento_sopra_le_occasioni():
    from fanta import scheda
    av = {"minuti": 600, "gol": 6, "xg": 3.0, "assist": 1, "xa": 1.5}
    r = scheda.rendimento(av, "A", 5, Regole())
    assert r["gol_meno_xg"] == 3.0 and r["sovra_rendimento"] > 0     # sta segnando più di quanto crea
    assert scheda.rendimento(None, "A", 5, Regole()) is None
    assert scheda.rendimento(av, "A", 0, Regole()) is None


def test_import_mostra_cosa_e_cambiato_e_tiene_lo_storico(client, tmp_path, monkeypatch):
    monkeypatch.setattr(server, "FILE_MOVIMENTI", tmp_path / "movimenti.json")
    prima = "Real Esempio\nP\tSommer\t10\nD\tBastoni\t15\nI Bomber\nA\tKean\t30\nD\tDimarco\t8\n"
    primo = client.post("/api/rose/testo", json={"testo": prima}).json()
    assert primo["differenze"]["prima_importazione"] and client.get("/api/movimenti").json() == []
    # Kean e Bastoni si scambiano squadra, Dimarco viene lasciato libero, Barella è uno svincolato preso da Real Esempio
    dopo = "Real Esempio\nP\tSommer\t10\nA\tKean\t30\nC\tBarella\t5\nI Bomber\nD\tBastoni\t15\n"
    secondo = client.post("/api/rose/testo", json={"testo": dopo}).json()
    d = secondo["differenze"]
    assert not d["nessuna_differenza"] and len(d["scambi"]) == 1
    assert {g["nome"] for g in d["scambi"][0]["da_a"] + d["scambi"][0]["da_b"]} == {"Bastoni", "Kean"}
    assert d["tagliati"][0]["giocatori"][0]["nome"] == "Dimarco"
    assert d["svincolati_presi"][0]["giocatori"][0]["nome"] == "Barella"
    assert "Scambio" in secondo["riepilogo"]
    storico = client.get("/api/movimenti").json()
    assert len(storico) == 1 and storico[0]["scambi"]
    # lo stesso file di nuovo: niente di nuovo, lo storico non cresce
    assert client.post("/api/rose/testo", json={"testo": dopo}).json()["differenze"]["nessuna_differenza"]
    assert len(client.get("/api/movimenti").json()) == 1


def test_novita_e_versione(client):
    elenco = client.get("/api/novita").json()
    assert elenco and elenco[0]["versione"] and all(v["voci"] for v in elenco)
    client.post("/api/rose/testo", json={"testo": "Real Esempio\nP\tSommer\t10\n"})
    assert client.get("/api/stato").json()["versione"] == elenco[0]["versione"]


def test_novita_in_inglese_a_richiesta(client, monkeypatch):
    monkeypatch.setattr(server, "_novita", lambda: [
        {"versione": "9.3", "titolo": "Nuova", "voci": ["a", "b"], "titolo_en": "New", "voci_en": ["x", "y"]},
        {"versione": "9.2", "titolo": "Tradotta a parte", "voci": ["a"]},
        {"versione": "9.1", "titolo": "Solo italiano", "voci": ["a"]}])
    monkeypatch.setattr(server, "_novita_en", lambda: {"9.2": {"titolo": "Translated", "voci": ["z"]}, "9.1": {"titolo": "Rotta", "voci": ["1", "2"]}})
    it = client.get("/api/novita").json()
    assert [v["titolo"] for v in it] == ["Nuova", "Tradotta a parte", "Solo italiano"] and "titolo_en" not in it[0]
    for r in (client.get("/api/novita?lingua=en"), client.get("/api/novita", headers={"Accept-Language": "en-GB,en;q=0.8"})):
        assert "Accept-Language" in r.headers["vary"]
        en = r.json()
        assert [v["titolo"] for v in en] == ["New", "Translated", "Rotta"] and en[0]["voci"] == ["x", "y"] and en[1]["voci"] == ["z"]
        assert en[2]["voci"] == [server.NOVITA_EN_VOCE] and "voci_en" not in en[0]   # traduzione con un numero di voci diverso: si scarta
    monkeypatch.setattr(server, "_novita_en", lambda: {})
    solo_it = client.get("/api/novita?lingua=en").json()                          # senza traduzione: testo generico in inglese
    assert [v["titolo"] for v in solo_it] == ["New", server.NOVITA_EN_TITOLO, server.NOVITA_EN_TITOLO]
    assert solo_it[1]["voci"] == [server.NOVITA_EN_VOCE] and solo_it[0]["voci"] == ["x", "y"]
    assert client.get("/api/novita?lingua=it", headers={"Accept-Language": "en"}).json() == it


def test_traduzioni_delle_novita_corrispondono_alle_versioni_vere():
    veri = {v["versione"]: v for v in server._novita()}
    en = server._novita_en()
    assert en and set(en) <= set(veri)
    for versione, e in en.items():
        assert e["titolo"].strip() and len(e["voci"]) == len(veri[versione]["voci"]), versione


def test_riconosci_regole_non_cambia_nulla(client):
    prima = client.get("/api/regole").json()
    r = client.post("/api/regole/riconosci", json={"testo": "Assist +2\nAmmonizione -1"}).json()
    assert {m["chiave"]: m["valore"] for m in r["modifiche"]} == {"bonus.assist": 2.0, "bonus.ammonizione": -1.0}
    assert client.get("/api/regole").json() == prima       # solo una proposta: le regole restano com'erano


def test_riconosci_regole_segnala_le_righe_dubbie_senza_numeri(client):
    """Una riga che l'app non sa leggere con sicurezza, anche senza numeri, arriva ai client fra quelle da controllare (#684)."""
    r = client.post("/api/regole/riconosci", json={"testo": "Assist +2\nNon è vietato il cambio modulo\nMedia 6-6,5: +1"}).json()
    assert r["da_controllare"] == [
        {"riga": "Non è vietato il cambio modulo",
         "regole": [{"chiave": "panchina.cambio_modulo", "etichetta": "Cambio modulo nelle sostituzioni"}]},
        {"riga": "Media 6-6,5: +1", "regole": []}]
    assert r["non_riconosciute"] == ["Media 6-6,5: +1"] and "dubbie" not in r


POSTI_FISSI = {"P": 2, "D": 3, "C": 3, "A": 3}


def _con_posti_fissi(client) -> dict:
    regole = client.get("/api/regole").json()
    regole["panchina"] |= {"posti": POSTI_FISSI, "numero": 11}
    assert client.put("/api/regole", json=regole).status_code == 200
    return regole


def test_riconosci_regole_non_propone_la_panchina_che_non_si_puo_salvare(client):
    """Con i posti fissi per ruolo il numero della panchina è la somma dei posti: «Panchina di 12 giocatori» non si può salvare.
    Non sta fra i valori riconosciuti (l'anteprima mostra solo ciò che si salva): torna fra i non applicabili con il perché, una
    volta sola (la riga non va anche fra quelle da controllare) (#881)."""
    from fanta import onboarding
    regole = _con_posti_fissi(client)
    riga = "Panchina di 12 giocatori, massimo 5 sostituzioni."
    r = client.post("/api/regole/riconosci", json={"testo": riga}).json()
    assert {m["chiave"]: m["valore"] for m in r["modifiche"]} == {"panchina.max_sostituzioni": 5}
    onboarding.applica_modifiche(regole_da_dict(regole), r["modifiche"])      # ogni proposta, applicata, dà regole valide
    [na] = r["non_applicabili"]
    assert (na["chiave"], na["etichetta"], na["valore"], na["riga"]) == ("panchina.numero", "Giocatori in panchina", 12, riga)
    assert "posti fissi" in na["motivo"] and "11" in na["motivo"]
    # una frase valida per la web e per l'iPhone: niente «Modifica i valori», che c'è solo sulla web (#889)
    assert na["motivo"] == "La tua panchina ha posti fissi per ruolo, 11 in tutto: cambia a mano i posti di ogni ruolo nei valori delle regole."
    assert na["motivo_frase"] == {"chiave": "regole.panchina_posti_fissi", "param": {"n": 11}}
    assert r["da_controllare"] == [] and r["non_riconosciute"] == []


@pytest.mark.parametrize("testo, posti_fissi", [
    ("Panchina di 12 giocatori", False),                                          # senza posti fissi il numero si salva
    ("Panchina di 11 giocatori", True),                                           # uguale alla somma dei posti: si salva com'è
    ("Panchina: 2 portieri, 4 difensori, 3 centrocampisti, 3 attaccanti", True),  # i posti nuovi portano il loro totale
])
def test_riconosci_regole_propone_la_panchina_che_si_salva(client, testo, posti_fissi):
    if posti_fissi:
        _con_posti_fissi(client)
    r = client.post("/api/regole/riconosci", json={"testo": testo}).json()
    assert "panchina.numero" in {m["chiave"] for m in r["modifiche"]} and r["non_applicabili"] == []


def test_regole_salvate_oltre_i_tetti_rispondono_422(client):
    regole = client.get("/api/regole").json()
    regole["modificatore_difesa"]["soglie"] = [[6 + i / 100, 1] for i in range(21)]
    r = client.put("/api/regole", json=regole)
    assert r.status_code == 422 and "al massimo 20 fasce" in r.json()["detail"]
    r = client.put("/api/regole", json=client.get("/api/regole").json() | {"nome_lega": "L" * 101})
    assert r.status_code == 422 and "il nome della lega può avere al massimo 100 caratteri" in r.json()["detail"]
    r = client.put("/api/regole", json=client.get("/api/regole").json() | {"fonte_voto": "inventata"})
    assert r.status_code == 400                                     # gli altri errori delle regole restano come prima
    assert client.get("/api/regole").json()["nome_lega"] == Regole().nome_lega


def test_riconosci_regole_oltre_i_tetti_risponde_422(client):
    from fanta import regole_testo
    r = client.post("/api/regole/riconosci", json={"testo": "Assist +1\n" * (regole_testo.MAX_TESTO // 10 + 1)})
    assert r.status_code == 422 and r.json()["detail"].startswith("Il regolamento è troppo lungo (al massimo 30 mila caratteri)")
    r = client.post("/api/regole/riconosci", json={"testo": "Gol +3\n" + "x" * (regole_testo.MAX_RIGA + 1)})
    assert r.status_code == 422 and r.json()["detail"].startswith("Una riga del regolamento è troppo lunga (al massimo 2000 caratteri)")


def test_stemma_e_maglia_della_squadra(client, tmp_path, monkeypatch):
    from fanta import immagini
    monkeypatch.setattr(immagini, "CARTELLA", tmp_path / "immagini")
    client.post("/api/rose/testo", json={"testo": "Real Esempio\nP\tSommer\t10\n"})
    assert client.get("/api/squadre").json()[0]["immagini"] == {"stemma": False, "maglia": False}
    assert client.get("/api/squadre/immagine", params={"squadra": "Real Esempio", "tipo": "stemma"}).status_code == 404
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 50
    r = client.post("/api/squadre/immagine", params={"squadra": "real", "tipo": "stemma"}, files={"file": ("s.png", png, "image/png")})
    assert r.status_code == 200 and r.json()["immagini"]["stemma"] is True
    g = client.get("/api/squadre/immagine", params={"squadra": "Real Esempio", "tipo": "stemma"})
    assert g.status_code == 200 and g.headers["content-type"] == "image/png" and g.content == png
    assert client.post("/api/squadre/immagine", params={"squadra": "Real Esempio", "tipo": "stemma"},
                       files={"file": ("x.txt", b"non e' un'immagine", "text/plain")}).status_code == 400
    assert client.post("/api/squadre/immagine", params={"squadra": "Nessuna", "tipo": "stemma"}, files={"file": ("s.png", png, "image/png")}).status_code == 404
    assert client.post("/api/squadre/immagine", params={"squadra": "Real Esempio", "tipo": "scudo"}, files={"file": ("s.png", png, "image/png")}).status_code == 400


@pytest.mark.parametrize("lingua", ["it", "en"])
def test_stemma_cambiato_non_resta_vecchio_nel_browser(client, tmp_path, monkeypatch, lingua):
    """Stemma e maglia hanno sempre lo stesso indirizzo: il browser non deve riusare la sua copia senza chiedere (#654), altrimenti
    dopo un cambio torna quello vecchio. Si ricontrolla con l'ETag: uguale -> 304 senza corpo, cambiato -> l'immagine nuova."""
    from fanta import immagini
    monkeypatch.setattr(immagini, "CARTELLA", tmp_path / "immagini")
    client.post("/api/rose/testo", json={"testo": "Real Esempio\nP\tSommer\t10\n"})
    q = {"squadra": "Real Esempio", "tipo": "stemma"}
    vecchio, nuovo = b"\x89PNG\r\n\x1a\n" + b"1" * 40, b"\x89PNG\r\n\x1a\n" + b"2" * 40      # stessa dimensione
    lingua_h = {"Accept-Language": lingua}
    assert client.post("/api/squadre/immagine", params=q, files={"file": ("s.png", vecchio, "image/png")}).status_code == 200
    g = client.get("/api/squadre/immagine", params=q, headers=lingua_h)
    regole_cache = [v.strip() for v in g.headers["cache-control"].split(",")]
    assert g.status_code == 200 and g.content == vecchio
    assert "no-cache" in regole_cache and "private" in regole_cache, g.headers["cache-control"]
    assert not [v for v in regole_cache if v.startswith("max-age") and v != "max-age=0"], g.headers["cache-control"]
    etag = g.headers["etag"]
    uguale = client.get("/api/squadre/immagine", params=q, headers=lingua_h | {"If-None-Match": etag})
    assert uguale.status_code == 304 and uguale.content == b"", (uguale.status_code, uguale.headers)
    assert uguale.headers["etag"] == etag and "no-cache" in uguale.headers["cache-control"]
    assert client.post("/api/squadre/immagine", params=q, files={"file": ("s.png", nuovo, "image/png")}).status_code == 200
    cambiato = client.get("/api/squadre/immagine", params=q, headers=lingua_h | {"If-None-Match": etag})
    assert cambiato.status_code == 200 and cambiato.content == nuovo and cambiato.headers["etag"] != etag


def test_avvisi_impostazioni_e_prova(client, tmp_path, monkeypatch):
    monkeypatch.setattr(server.notifiche, "FILE_IMPOSTAZIONI", tmp_path / "avvisi.json")
    monkeypatch.setattr(server.notifiche, "canale", lambda: None)
    monkeypatch.setattr(server.notifiche_web, "FILE_ISCRIZIONI", tmp_path / "push-vuoto.json")
    assert client.get("/api/avvisi").json() == {"impostazioni": {"cambi": True, "promemoria_60": True, "promemoria_15": True, "riepilogo": True, "app_nativa": False, "silenzio": False, "copertura": True, "silenzio_da": 23, "silenzio_a": 7, "avviso_prima": 60, "lingua": "it"}, "canale": False, "dispositivi": 0, "promemoria_da": "app"}
    r = client.put("/api/avvisi", json={"cambi": False, "promemoria_60": True, "promemoria_15": False, "riepilogo": True})
    assert r.json()["impostazioni"] == {"cambi": False, "promemoria_60": True, "promemoria_15": False, "riepilogo": True, "app_nativa": False,
                                        "silenzio": False, "copertura": True, "silenzio_da": 23, "silenzio_a": 7, "avviso_prima": 60, "lingua": "it"}
    assert client.get("/api/avvisi").json()["impostazioni"]["cambi"] is False
    r = client.put("/api/avvisi", json={"silenzio": True, "silenzio_da": 22, "silenzio_a": 6})
    assert (r.json()["impostazioni"]["silenzio"], r.json()["impostazioni"]["silenzio_da"], r.json()["impostazioni"]["cambi"]) == (True, 22, False)
    assert client.put("/api/avvisi", json={"silenzio_da": 24}).status_code == 422                    # le ore vanno da 0 a 23
    r = client.put("/api/avvisi", json={"silenzio_a": 22})                                          # inizio = fine con l'interruttore acceso: rifiutato
    assert r.status_code == 422 and "stessa ora" in r.json()["detail"]
    assert client.get("/api/avvisi").json()["impostazioni"]["silenzio_a"] == 6                      # e non salva niente
    client.put("/api/avvisi", json={"silenzio": False})
    assert client.put("/api/avvisi", json={"silenzio_da": 5, "silenzio_a": 5}).status_code == 200   # a interruttore spento le ore uguali non fanno danni
    client.put("/api/avvisi", json={"silenzio_da": 22, "silenzio_a": 6})
    client.put("/api/avvisi", json={"cambi": False, "promemoria_60": True, "promemoria_15": False, "riepilogo": True, "app_nativa": True})
    client.put("/api/avvisi", json={"cambi": True, "promemoria_60": True, "promemoria_15": False, "riepilogo": True})      # un client senza `app_nativa` non la azzera
    assert client.get("/api/avvisi").json()["impostazioni"]["app_nativa"] is True
    assert client.post("/api/avvisi/prova").status_code == 409            # canale non configurato
    monkeypatch.setattr(server.notifiche, "canale", lambda: "x")
    mandati = []
    monkeypatch.setattr(server.notifiche, "invia", lambda *a, **k: mandati.append(a) or True)
    assert client.post("/api/avvisi/prova").json() == {"inviato": True} and len(mandati) == 1


def test_ore_tranquille_uguali_salvate_prima_sono_spente_con_avviso(client, tmp_path, monkeypatch):
    import json
    from datetime import datetime
    f = tmp_path / "avvisi.json"
    monkeypatch.setattr(server.notifiche, "FILE_IMPOSTAZIONI", f)
    monkeypatch.setattr(server.notifiche, "canale", lambda: None)
    monkeypatch.setattr(server.notifiche_web, "FILE_ISCRIZIONI", tmp_path / "push-vuoto.json")
    f.write_text('{"silenzio": true, "silenzio_da": 9, "silenzio_a": 9, "cambi": false}')
    g = client.get("/api/avvisi").json()
    assert g["impostazioni"]["silenzio"] is False and g["impostazioni"]["cambi"] is False and g["ore_tranquille_spente"] is True
    assert not server.notifiche.in_silenzio(datetime(2026, 1, 1, 9), g["impostazioni"])
    assert client.put("/api/avvisi", json={"riepilogo": False}).status_code == 200            # salvare altro non dà errore
    assert "ore_tranquille_spente" not in client.get("/api/avvisi").json()                    # l'avviso si vede una volta sola
    for da, a in ((23, 7), (13, 15)):                                                         # i salvataggi validi restano
        f.write_text(json.dumps({"silenzio": True, "silenzio_da": da, "silenzio_a": a}))
        g = client.get("/api/avvisi").json()
        assert g["impostazioni"]["silenzio"] is True and "ore_tranquille_spente" not in g


def test_ore_tranquille_uguali_riaccese_tornano_quelle_predefinite(client, tmp_path, monkeypatch):
    """#711: web e iPhone non hanno più i selettori delle ore e riaccendendo mandano il solo `silenzio`. Con ore salvate che
    iniziano e finiscono alla stessa ora il server le corregge da solo (dalle 23 alle 7): niente 422, e la fascia mostrata è giusta."""
    from datetime import datetime
    f = tmp_path / "avvisi.json"
    monkeypatch.setattr(server.notifiche, "FILE_IMPOSTAZIONI", f)
    monkeypatch.setattr(server.notifiche, "canale", lambda: None)
    monkeypatch.setattr(server.notifiche_web, "FILE_ISCRIZIONI", tmp_path / "push-vuoto.json")
    for salvate in ('{"silenzio": true, "silenzio_da": 23, "silenzio_a": 23}', '{"silenzio": false, "silenzio_da": 5, "silenzio_a": 5}'):
        f.write_text(salvate)
        g = client.get("/api/avvisi").json()["impostazioni"]
        assert (g["silenzio"], g["silenzio_da"], g["silenzio_a"]) == (False, 23, 7)           # la riga sotto dice «dalle 23 alle 7»
        r = client.put("/api/avvisi", json={"silenzio": True})                               # la richiesta di oggi di web e iPhone
        assert r.status_code == 200, r.text
        o = r.json()["impostazioni"]
        assert (o["silenzio"], o["silenzio_da"], o["silenzio_a"]) == (True, 23, 7)
        g = client.get("/api/avvisi").json()
        assert "ore_tranquille_spente" not in g and server.notifiche.in_silenzio(datetime(2026, 1, 1, 2), g["impostazioni"])
    r = client.put("/api/avvisi", json={"silenzio_da": 4, "silenzio_a": 4})                  # due ore uguali scelte apposta: rifiutate
    assert r.status_code == 422 and "stessa ora" in r.json()["detail"]


def test_valuta_formazione_e_la_mia_scelta(client, tmp_path, monkeypatch):
    monkeypatch.setattr(server.scelte, "FILE_SCELTE", tmp_path / "scelte.json")
    monkeypatch.setattr(server.consigli, "stagione_corrente", lambda: "2026-27")
    monkeypatch.setattr(server.consigli, "valuta", lambda db, regole, rose, titolari, squadra=None, giornata=None, simulazioni=600:
                        {"modulo": "4-3-3", "giornata": 9, "punteggio_atteso": 70.0, "dev": 4.0, "panchina": [], "differenza": -1.0})
    monkeypatch.setattr(server, "_rose", lambda *a: object())
    monkeypatch.setattr(server.fasi, "iniziata", lambda *a, **k: False)     # giornata aperta, qualunque sia il calendario sul disco
    assert client.get("/api/scelta?giornata=9").json() is None
    r = client.post("/api/formazione/valuta", json={"titolari": [1, 2, 3], "giornata": 9, "salva": True})
    assert r.status_code == 200 and r.json()["punteggio_atteso"] == 70.0
    assert client.get("/api/scelta?giornata=9").json()["titolari"] == [1, 2, 3]
    assert client.post("/api/formazione/valuta", json={"titolari": [1], "giornata": 9, "salva": False}).status_code == 200
    assert client.delete("/api/scelta?giornata=9").json() == {"ok": True}
    assert client.get("/api/scelta?giornata=9").json() is None
    senza_intestazione = TestClient(server.app)
    assert senza_intestazione.post("/api/formazione/valuta", json={"titolari": [1]}).status_code == 403


def test_formazione_dopo_la_scadenza_senza_etichette_delle_probabili(client, monkeypatch):
    """La rotta della Formazione passa da fasi.formazione_a_giornata_iniziata: dopo la scadenza `iniziata` è true e le schede
    non hanno più `titolarita` (le etichette delle probabili), prima tutto come sempre."""
    x = {"id": 1, "nome": "Uno", "ruolo": "P", "squadra": "inter", "titolarita": "ballottaggio", "motivi": ["titolare"]}
    f = {"squadra": "Mia", "giornata": 9, "titolari": [x], "panchina": [], "fuori": [], "schede": {"1": x}}
    monkeypatch.setattr(server.consigli, "formazione", lambda *a, **k: f)
    monkeypatch.setattr(server, "_copia_automatica", lambda *a: None)
    monkeypatch.setattr(server, "_rose_da_schierare", lambda *a: object())
    monkeypatch.setattr(server.fasi, "stati_giocatori", lambda *a, **k: {1: "in_corso"})
    monkeypatch.setattr(server.fasi, "iniziata", lambda *a: False)
    r = client.get("/api/formazione").json()
    assert r["iniziata"] is False and r["titolari"][0]["titolarita"] == "ballottaggio"
    monkeypatch.setattr(server.fasi, "iniziata", lambda *a: True)
    r = client.get("/api/formazione").json()
    assert r["iniziata"] is True and r["titolari"][0] | r["schede"]["1"] == x | {"titolarita": None, "motivi": [], "stato_partita": "in_corso", "fv_preso": None,
                                                                                "etichetta": {"codice": "in_corso", "testo": "Partita in corso", "tono": "positivo"}}
    assert f["titolari"][0]["titolarita"] == "ballottaggio"                      # la formazione in cache non cambia


def test_osservati_aggiungi_e_togli(client, tmp_path, monkeypatch, listone_in_archivio):
    monkeypatch.setattr(server.osservati, "FILE_OSSERVATI", tmp_path / "oss.json")
    assert client.put("/api/osservati/5").json() == {"osservati": [5]}
    assert client.put("/api/osservati/5").json() == {"osservati": [5]}
    assert client.delete("/api/osservati/5").json() == {"osservati": []}
    assert TestClient(server.app).put("/api/osservati/5").status_code == 403



def test_osservati_solo_giocatori_del_listone(client, tmp_path, monkeypatch, listone_in_archivio):
    """Collaudo 2/11/2026: un codice inventato veniva salvato, non compariva mai e occupava uno dei 60 posti."""
    import json
    file = tmp_path / "oss.json"
    monkeypatch.setattr(server.osservati, "FILE_OSSERVATI", file)
    r = client.put("/api/osservati/123456")
    assert r.status_code == 404 and r.json()["detail"] == "Giocatore non trovato nel listone"
    assert not file.exists()                                             # niente salvato
    # codici non validi già salvati (versioni vecchie): in lettura si ignorano senza errori...
    file.write_text(json.dumps([123456, 5, 654321]), encoding="utf-8")
    import pandas as pd
    monkeypatch.setattr(server.consigli, "previsioni", lambda *a, **k: (pd.DataFrame(index=[]), 9, False))    # nessuna partita
    r = client.get("/api/osservati")
    assert r.status_code == 200 and [g["id"] for g in r.json()["giocatori"]] == [5]
    # ...e al primo salvataggio si tolgono: non occupano posti
    assert client.put("/api/osservati/7").json() == {"osservati": [5, 7]}
    assert json.loads(file.read_text(encoding="utf-8")) == [5, 7]
    assert client.delete("/api/osservati/123456").status_code == 200    # togliere un codice inventato non è un errore


def test_osservati_letti_senza_doppioni_e_al_massimo_il_tetto(tmp_path):
    """Un file con doppioni o con più di osservati.MASSIMO codici (scritto da fuori dall'app) si legge come lo terrebbe l'app:
    ogni codice una volta, gli ultimi MASSIMO (come osservati.aggiungi)."""
    import json
    from fanta import osservati
    file = tmp_path / "oss.json"
    file.write_text(json.dumps([7] * 1000 + list(range(1, 100))), encoding="utf-8")
    letti = osservati.leggi(file)
    assert letti == list(range(100 - osservati.MASSIMO, 100))
    assert osservati.togli(99, file) == list(range(100 - osservati.MASSIMO, 99))
    file.write_text("[5, Infinity]", encoding="utf-8")                 # file rovinato: l'elenco è vuoto, non un errore
    assert osservati.leggi(file) == []


@pytest.mark.parametrize("percorso, corpo", [
    ("/api/formazione/valuta", {"salva": False}),
    ("/api/diario/schierata", {"giornata": 1, "tipo": "manuale"}),
])
def test_titolari_al_massimo_quanti_una_rosa(client, percorso, corpo):
    """I titolari mandati dall'app non sono mai più dei giocatori di una rosa (limiti.MAX_GIOCATORI_SQUADRA): oltre, 422 subito."""
    from fanta import limiti
    troppi = list(range(1, limiti.MAX_GIOCATORI_SQUADRA + 2))
    assert client.post(percorso, json=corpo | {"titolari": troppi}).status_code == 422
    assert client.post(percorso, json=corpo | {"titolari": troppi[:-1]}).status_code != 422


def test_crediti_delle_squadre(client, tmp_path):
    from fanta import lega
    lega.salva(lega.Rose([lega.Squadra("Mia", []), lega.Squadra("Altra", [])], "Mia"), server.FILE_ROSE)
    nome = "Mia"
    r = client.put("/api/crediti", json={"crediti": {nome: 27}})
    assert r.status_code == 200 and next(s for s in r.json()["squadre"] if s["nome"] == nome)["crediti_residui"] == 27
    assert next(s for s in client.get("/api/squadre").json() if s["nome"] == nome)["crediti_residui"] == 27
    assert client.put("/api/crediti", json={"crediti": {"Inesistente": 3}}).status_code == 400
    assert client.put("/api/crediti", json={"crediti": {nome: -1}}).status_code == 400


def test_icona_dell_app(client, tmp_path, monkeypatch):
    monkeypatch.setattr(server, "FILE_ICONA", tmp_path / "icona.json")
    assert client.get("/api/icona").json()["scelta"] == "verde"
    assert client.put("/api/icona", json={"nome": "viola"}).json()["scelta"] == "viola"
    assert client.put("/api/icona", json={"nome": "arcobaleno"}).status_code == 400
    r = client.get("/icona-180.png")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert r.content == (server.WEB / "icone" / "viola-180.png").read_bytes()
    assert client.get("/icona-999.png").status_code == 404
    assert client.get("/icone/blu-512.png").status_code == 200


def test_endpoint_notifiche_web(client, tmp_path, monkeypatch):
    monkeypatch.setattr(server.notifiche_web, "FILE_VAPID", tmp_path / "v.json")
    monkeypatch.setattr(server.notifiche_web, "FILE_ISCRIZIONI", tmp_path / "p.json")
    chiave = client.get("/api/push/chiave").json()["chiave"]
    assert len(chiave) == 87 and client.get("/api/push/chiave").json()["chiave"] == chiave
    sub = {"endpoint": "https://web.push.apple.com/xyz", "keys": {"p256dh": "P" * 40, "auth": "A" * 20}}
    assert client.post("/api/push/iscrivi", json=sub).json() == {"dispositivi": 1}
    assert client.post("/api/push/iscrivi", json={"endpoint": "http://no", "keys": {"p256dh": "a", "auth": "b"}}).status_code == 400
    assert client.post("/api/push/disiscrivi", json={"endpoint": sub["endpoint"]}).json() == {"dispositivi": 0}
    assert TestClient(server.app).post("/api/push/iscrivi", json=sub).status_code == 403


def test_richieste_troppo_grandi_e_rose_rovinate(client, tmp_path):
    from fanta import lega
    assert client.post("/api/avvisi/prova", content=b"x", headers={"content-length": str(server.LIMITE_RICHIESTA + 1)}).status_code == 413
    server.FILE_ROSE.write_text("non è json", encoding="utf-8")
    r = client.get("/api/squadre")
    assert r.status_code == 400 and "rovinato" in r.json()["detail"]
    with pytest.raises(ValueError):
        lega.carica(server.FILE_ROSE)


def test_head_sulle_pagine_pubbliche_risponde_come_get(client):
    for percorso in ("/", "/privacy", "/termini", "/crediti"):
        r = client.head(percorso)
        assert r.status_code == 200, percorso
        assert client.get(percorso).status_code == 200


def test_formazione_non_valida_ha_il_codice(client, monkeypatch):
    """Scelta non valida (titolari non della rosa, ripetuti, modulo non ammesso): 400 con il testo e `codice` per i client,
    che così non cancellano da soli la scelta salvata. Gli altri errori restano senza `codice`."""
    import pandas as pd
    from types import SimpleNamespace as NS
    ids = list(range(1, 16))
    ruoli = ["P", "P"] + ["D"] * 5 + ["C"] * 5 + ["A"] * 3
    prev = pd.DataFrame({"nome": [f"G{i}" for i in ids], "ruolo": ruoli, "p_voto": 0.9, "mu": 6.0, "mu_voto": 6.0}, index=ids)
    monkeypatch.setattr(server.consigli, "previsioni", lambda db, regole, giornata=None: (prev, 9, True))
    rosa = NS(mia_squadra="Mia", squadra=lambda nome: NS(giocatori=[NS(id=i) for i in ids]) if nome == "Mia" else None)
    monkeypatch.setattr(server, "_rose", lambda *a: rosa)
    r = client.post("/api/formazione/valuta", json={"titolari": [1, 2, 3], "giornata": 9})
    assert r.status_code == 400 and r.json() == {"detail": "Servono 11 titolari diversi, tutti della rosa", "codice": "formazione_non_valida"}
    r = client.post("/api/formazione/valuta", json={"titolari": [1, 2, 3, 4, 5, 8, 9, 10, 13, 14, 15], "giornata": 9})   # due portieri
    assert r.status_code == 400 and r.json()["codice"] == "formazione_non_valida" and "non è ammesso" in r.json()["detail"]
    r = client.post("/api/formazione/valuta", json={"titolari": [1], "squadra": "Altra", "giornata": 9})
    assert r.status_code == 400 and "codice" not in r.json() and r.json()["detail"].startswith("Squadra non trovata")
