"""Server dell'app: regole e importazione rose, su file temporanei (la lega vera non viene toccata)."""
import pytest
from fastapi.testclient import TestClient

from fanta import server
from fanta.regole import Regole


@pytest.fixture
def client(tmp_path, monkeypatch, calciatori):
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


def test_messaggio_senza_rose_dice_dove_importarle():
    from pathlib import Path
    testi = (Path(server.__file__).parent / "web" / "testi.js").read_text(encoding="utf-8")
    assert "sezione Lega" not in testi
    assert "Squadra > Aggiorna le rose" in testi


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
    assert prova(moduli=["4-4-2"] * 31).status_code == 400
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


def test_avvisi_impostazioni_e_prova(client, tmp_path, monkeypatch):
    monkeypatch.setattr(server.notifiche, "FILE_IMPOSTAZIONI", tmp_path / "avvisi.json")
    monkeypatch.setattr(server.notifiche, "canale", lambda: None)
    monkeypatch.setattr(server.notifiche_web, "FILE_ISCRIZIONI", tmp_path / "push-vuoto.json")
    assert client.get("/api/avvisi").json() == {"impostazioni": {"cambi": True, "promemoria_60": True, "promemoria_15": True, "riepilogo": True, "app_nativa": False, "silenzio": False, "copertura": True, "silenzio_da": 23, "silenzio_a": 7, "avviso_prima": 60, "lingua": "it"}, "canale": False, "dispositivi": 0}
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
    monkeypatch.setattr(server, "_rose", lambda *a: object())
    monkeypatch.setattr(server.fasi, "stati_giocatori", lambda *a, **k: {1: "in_corso"})
    monkeypatch.setattr(server.fasi, "iniziata", lambda *a: False)
    r = client.get("/api/formazione").json()
    assert r["iniziata"] is False and r["titolari"][0]["titolarita"] == "ballottaggio"
    monkeypatch.setattr(server.fasi, "iniziata", lambda *a: True)
    r = client.get("/api/formazione").json()
    assert r["iniziata"] is True and r["titolari"][0] | r["schede"]["1"] == x | {"titolarita": None, "motivi": [], "stato_partita": "in_corso", "fv_preso": None,
                                                                                "etichetta": {"codice": "in_corso", "testo": "Partita in corso", "tono": "positivo"}}
    assert f["titolari"][0]["titolarita"] == "ballottaggio"                      # la formazione in cache non cambia


def test_osservati_aggiungi_e_togli(client, tmp_path, monkeypatch):
    monkeypatch.setattr(server.osservati, "FILE_OSSERVATI", tmp_path / "oss.json")
    assert client.put("/api/osservati/5").json() == {"osservati": [5]}
    assert client.put("/api/osservati/5").json() == {"osservati": [5]}
    assert client.delete("/api/osservati/5").json() == {"osservati": []}
    assert TestClient(server.app).put("/api/osservati/5").status_code == 403


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
