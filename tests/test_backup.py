"""Backup e ripristino dei dati della lega, su una cartella temporanea."""
import json

import pytest

from fanta import backup, lega, limiti, movimenti, osservati, scelte, server
from fanta.regole import Regole
from fanta.regole import salva as salva_regole
from fastapi.testclient import TestClient


@pytest.fixture
def radice(tmp_path):
    salva_regole(Regole(), tmp_path / "lega" / "regole.json")
    lega.salva(lega.Rose([lega.Squadra("Mia", []), lega.Squadra("Altra", [])], "Mia"), tmp_path / "lega" / "rose.json")
    (tmp_path / "dati").mkdir()
    (tmp_path / "dati" / "osservati.json").write_text("[5, 7]")
    (tmp_path / "dati" / "scelte.json").write_text('{"2025-26/9": {"titolari": [1], "modulo": "3-4-3"}}')
    (tmp_path / "dati" / "vapid.json").write_text('{"chiave": "segreta"}')
    return tmp_path


def test_il_backup_ha_i_dati_e_non_i_segreti(radice):
    b = backup.crea(radice)
    assert b["formato"] == backup.FORMATO
    assert set(b["file"]) == {"lega/regole.json", "lega/rose.json", "dati/osservati.json", "dati/scelte.json"}
    assert "segreta" not in json.dumps(b)


def test_ripristino_su_una_cartella_vuota_e_ritorno_identico(radice, tmp_path_factory):
    b = backup.crea(radice)
    nuova = tmp_path_factory.mktemp("nuova")
    assert backup.ripristina(b, nuova) == sorted(b["file"])
    assert backup.crea(nuova)["file"] == b["file"]
    assert lega.carica(nuova / "lega" / "rose.json").mia_squadra == "Mia"


def test_ripristino_tiene_la_copia_dello_stato_di_prima(radice):
    b = backup.crea(radice)
    (radice / "dati" / "osservati.json").write_text("[1]")
    backup.ripristina(b, radice)
    assert json.loads((radice / "dati" / "osservati.json").read_text()) == [5, 7]
    prima = json.loads((radice / backup.COPIA_PRIMA).read_text())
    assert prima["file"]["dati/osservati.json"] == [1]


@pytest.mark.parametrize("brutto", [
    [], "ciao", {}, {"formato": "altro", "versione": 1, "file": {"dati/osservati.json": []}},
    {"formato": backup.FORMATO, "versione": 99, "file": {"dati/osservati.json": []}},
    {"formato": backup.FORMATO, "versione": 1, "file": {}},
    {"formato": backup.FORMATO, "versione": 1, "file": {"../fuori.json": []}},
    {"formato": backup.FORMATO, "versione": 1, "file": {"dati/vapid.json": {}}},
    {"formato": backup.FORMATO, "versione": 1, "file": {"dati/osservati.json": {"a": 1}}},
    {"formato": backup.FORMATO, "versione": 1, "file": {"dati/osservati.json": [float("inf")]}},     # «Infinity» o 1e999 nel JSON: era un errore 500
    {"formato": backup.FORMATO, "versione": 1, "file": {"lega/regole.json": {"moduli": ["3-4-4"]}}},
    {"formato": backup.FORMATO, "versione": 1, "file": {"lega/rose.json": {"squadre": [{"giocatori": []}]}}},
    {"formato": backup.FORMATO, "versione": 1, "file": {"lega/rose.json": {"squadre": [], "stagione": "../../altro"}}},
    {"formato": backup.FORMATO, "versione": 1, "file": {"lega/rose.json": {"squadre": [], "stagione": "/tmp/altro"}}},
    {"formato": backup.FORMATO, "versione": 1, "file": {"lega/rose.json": {"squadre": [], "stagione": "2026"}}},
])
def test_un_backup_sbagliato_non_cambia_niente(radice, brutto):
    prima = backup.crea(radice)
    with pytest.raises(ValueError):
        backup.ripristina(brutto, radice)
    dopo = backup.crea(radice)          # una sola chiamata: "creato" cambia al secondo e due chiamate possono cadere in secondi diversi
    assert dopo == {**prima, "creato": dopo["creato"]}
    assert not (radice / backup.COPIA_PRIMA).exists()


def _solo(nome: str, contenuto) -> dict:
    return {"formato": backup.FORMATO, "versione": 1, "file": {nome: contenuto}}


@pytest.mark.parametrize("impostazioni", [
    [], {"silenzio_da": float("inf")}, {"silenzio_a": float("-inf")}, {"avviso_prima": float("nan")}, {"silenzio_da": 24},
    {"silenzio_a": "7"}, {"silenzio_da": True}, {"avviso_prima": 45}, {"cambi": "si"}, {"riepilogo": 1}, {"lingua": "xx"},
    {"backup_il": float("inf")}, {"primo_avvio": {"aggiornato": float("inf")}},
])
def test_backup_impostazioni_avvisi_non_valide_non_cambiano_niente(radice, impostazioni):
    """Le impostazioni degli avvisi del backup passano gli stessi controlli del salvataggio normale: un valore che non si può
    salvare dall'app (numero non finito, ora fuori dalla giornata, minuti non previsti, tipo sbagliato) è un errore e non si scrive niente."""
    prima = backup.crea(radice)
    with pytest.raises(ValueError, match="avvisi-impostazioni.json non è valido"):
        backup.ripristina(_solo("dati/avvisi-impostazioni.json", impostazioni), radice)
    dopo = backup.crea(radice)
    assert dopo == {**prima, "creato": dopo["creato"]} and not (radice / backup.COPIA_PRIMA).exists()


def test_backup_impostazioni_avvisi_si_ripristinano_senza_le_voci_sconosciute(radice):
    imp = {"cambi": False, "promemoria_60": True, "silenzio": True, "silenzio_da": 22, "silenzio_a": 6, "avviso_prima": 30,
           "lingua": "en", "primo_avvio": {"fatti": ["rose"], "saltati": [], "chiuso": False, "aggiornato": "2026-11-01T10:00:00"},
           "backup_il": "2026-11-01T10:00:00", "mostra_tutte": True}
    backup.ripristina(_solo("dati/avvisi-impostazioni.json", imp | {"voce_sconosciuta": {"x": [1, 2]}}), radice)
    assert json.loads((radice / "dati" / "avvisi-impostazioni.json").read_text(encoding="utf-8")) == imp
    backup.ripristina(_solo("dati/avvisi-impostazioni.json", {}), radice)               # un file vuoto resta vuoto: valgono quelle di base
    assert json.loads((radice / "dati" / "avvisi-impostazioni.json").read_text(encoding="utf-8")) == {}


def _annidato(livelli: int):
    """Una lista dentro una lista, `livelli` volte."""
    d: list = [0]
    for _ in range(livelli - 1):
        d = [d]
    return d


def _scelta(**campi) -> dict:
    return {"2025-26/9": {"titolari": [1, 2, 3], "modulo": "3-4-3", "tipo": "manuale"} | campi}


def _movimento(**campi) -> list:
    return [{"quando": "2026-11-01T10:00:00", "testo": "Passaggio da A a B: Rossi"} | campi]


@pytest.mark.parametrize("nome, contenuto", [
    pytest.param("dati/scelte.json", _scelta(titolari=[float("inf")] * 11), id="scelte-titolari-non-finiti"),
    pytest.param("dati/scelte.json", _scelta(titolari=[1.5, 2]), id="scelte-titolari-non-interi"),
    pytest.param("dati/scelte.json", _scelta(titolari=[True, 2]), id="scelte-titolari-vero-falso"),
    pytest.param("dati/scelte.json", _scelta(titolari=[0, 2]), id="scelte-titolari-fuori-misura"),
    pytest.param("dati/scelte.json", _scelta(titolari="1,2,3"), id="scelte-titolari-testo"),
    pytest.param("dati/scelte.json", _scelta(titolari=list(range(1, limiti.MAX_GIOCATORI_SQUADRA + 2))), id="scelte-titolari-troppi"),
    pytest.param("dati/scelte.json", _scelta(panchina=[float("inf")]), id="scelte-panchina-non-finita"),
    pytest.param("dati/scelte.json", _scelta(modulo=[3, 4, 3]), id="scelte-modulo-non-testo"),
    pytest.param("dati/scelte.json", {"2025-26/9": {"modulo": "3-4-3"}}, id="scelte-senza-titolari"),
    pytest.param("dati/scelte.json", {"2025-26/9": [1, 2, 3]}, id="scelte-voce-non-dizionario"),
    pytest.param("dati/scelte.json", {"x0": _scelta()["2025-26/9"]}, id="scelte-chiave-sbagliata"),
    pytest.param("lega/movimenti.json", [1, 2, 3], id="movimenti-numeri"),
    pytest.param("lega/movimenti.json", {"a": 1}, id="movimenti-dizionario"),
    pytest.param("lega/movimenti.json", [None], id="movimenti-voce-vuota"),
    pytest.param("lega/movimenti.json", _movimento(scambi=5), id="movimenti-scambi-numero"),
    pytest.param("lega/movimenti.json", _movimento(scambi=[{"squadre": ["A"], "da_a": [], "da_b": []}]), id="movimenti-scambio-una-squadra"),
    pytest.param("lega/movimenti.json", _movimento(tagliati=[{"squadra": "A", "giocatori": [{"id": "x", "nome": "Rossi"}]}]),
                 id="movimenti-giocatore-codice-testo"),
    pytest.param("lega/movimenti.json", _movimento(svincolati_presi=[{"squadra": "A", "giocatori": [{"id": 1}]}]),
                 id="movimenti-giocatore-senza-nome"),
    pytest.param("lega/movimenti.json", _movimento(crediti=[{"squadra": "A", "prima": "molti", "dopo": 3}]), id="movimenti-crediti-testo"),
    pytest.param("lega/movimenti.json", _movimento(squadre_nuove="A"), id="movimenti-squadre-nuove-testo"),
    pytest.param("lega/movimenti.json", _movimento(quando=5), id="movimenti-data-numero"),
    pytest.param("lega/movimenti.json", _movimento() * (movimenti.MAX_STORICO + 1), id="movimenti-troppe-voci"),
    pytest.param("lega/movimenti.json", _movimento(testo="t" * (backup.MAX_TESTO_MOVIMENTO + 1)), id="movimenti-testo-troppo-lungo"),
    pytest.param("lega/movimenti.json", _movimento(tagliati=[{"squadra": "A", "giocatori": [{"id": None, "nome": "Rossi"}] * (
        backup.MAX_GIOCATORI_MOVIMENTO + 1)}]), id="movimenti-troppi-giocatori-in-un-gruppo"),
    pytest.param("lega/movimenti.json", _movimento(tagliati=[{"squadra": "A", "giocatori": [{"id": None, "nome": "R" * (
        backup.MAX_TESTO_ROSE + 1)}]}]), id="movimenti-nome-troppo-lungo"),
    pytest.param("dati/osservati.json", [True], id="osservati-vero-falso"),
    pytest.param("dati/osservati.json", [1.5], id="osservati-non-interi"),
    pytest.param("dati/osservati.json", ["5"], id="osservati-testo"),
    pytest.param("dati/osservati.json", list(range(1, osservati.MASSIMO + 2)), id="osservati-troppi"),
])
def test_backup_con_dati_di_forma_sbagliata_non_cambia_niente(radice, nome, contenuto):
    """Scelte, movimenti e osservati del backup hanno la forma che scrive l'app: altrimenti un errore che dice quale file non va
    e niente scritto."""
    prima = backup.crea(radice)
    with pytest.raises(ValueError, match=f"{nome} non è valido"):
        backup.ripristina(_solo(nome, contenuto), radice)
    dopo = backup.crea(radice)
    assert dopo == {**prima, "creato": dopo["creato"]} and not (radice / backup.COPIA_PRIMA).exists()


def _rose_con(nome="Mia", giocatore: dict | None = None, **campi) -> dict:
    g = {"id": 1, "nome": "Rossi", "ruolo": "A", "squadra": "ROM"} | (giocatore or {})
    return {"squadre": [{"nome": nome, "giocatori": [g]} | campi], "mia_squadra": nome}


LUNGO = backup.MAX_TESTO_ROSE + 1


@pytest.mark.parametrize("rose", [
    _rose_con("S" * LUNGO),
    _rose_con(nome_importato="I" * LUNGO),
    _rose_con(giocatore={"nome": "G" * LUNGO}),
    _rose_con(giocatore={"squadra": "Q" * LUNGO}),
    _rose_con(giocatore={"ruolo": "R" * LUNGO}),
    _rose_con(giocatore={"riconosciuto": "x" * LUNGO}),
    _rose_con(giocatore={"avviso": "A" * (backup.MAX_AVVISO_ROSE + 1)}),
    _rose_con() | {"mia_squadra": "M" * LUNGO},
    _rose_con() | {"aggiornato": "2" * LUNGO},
])
def test_backup_rose_con_testi_troppo_lunghi_non_cambiano_niente(radice, rose):
    """Nomi e testi delle rose del backup hanno gli stessi tetti dell'importazione (una cella: 200 caratteri)."""
    prima = backup.crea(radice)
    with pytest.raises(ValueError, match="rose.json non è valido"):
        backup.ripristina(_solo("lega/rose.json", rose), radice)
    dopo = backup.crea(radice)
    assert dopo == {**prima, "creato": dopo["creato"]} and not (radice / backup.COPIA_PRIMA).exists()


def test_backup_rose_con_testi_al_tetto_si_ripristinano(radice):
    n = backup.MAX_TESTO_ROSE
    rose = _rose_con("S" * n, giocatore={"nome": "G" * n, "squadra": "Q" * n, "avviso": "A" * backup.MAX_AVVISO_ROSE},
                     nome_importato="I" * n)
    assert backup.ripristina(_solo("lega/rose.json", rose), radice) == ["lega/rose.json"]
    r = lega.carica(radice / "lega" / "rose.json")
    assert r.mia_squadra == "S" * n and r.squadra(r.mia_squadra).giocatori[0].nome == "G" * n


def _regole_con(**campi) -> dict:
    from dataclasses import asdict
    r = asdict(Regole())
    for chiave, valore in campi.items():
        if chiave == "soglie":
            r["modificatore_difesa"]["soglie"] = valore
        else:
            r[chiave] = valore
    return r


@pytest.mark.parametrize("campi", [
    {"nome_lega": "L" * 150},
    {"soglie": [[6 + i / 100, 1] for i in range(25)]},
    {"moduli": ["3-4-3" + " " * 40, "4-4-2"]},
    {"moduli": [f"{d}-{c}-{a}" for d in range(3, 6) for c in range(2, 7) for a in range(1, 4)][:31]},
])
def test_backup_regole_oltre_i_tetti_danno_un_errore_chiaro_e_niente_scritto(radice, campi):
    """Le regole del backup hanno gli stessi tetti di misura di quelle salvate dall'app (#480), anche se il backup è di prima:
    oltre i tetti un errore che lo dice, e niente scritto (nemmeno gli altri file del backup)."""
    prima = backup.crea(radice)
    b = {"formato": backup.FORMATO, "versione": 1, "file": {"lega/regole.json": _regole_con(**campi), "dati/osservati.json": [1]}}
    with pytest.raises(ValueError) as e:
        backup.ripristina(b, radice)
    assert str(e.value) == backup.REGOLE_OLTRE_I_TETTI and "L" * 150 not in str(e.value)       # il messaggio non ripete i valori
    dopo = backup.crea(radice)
    assert dopo == {**prima, "creato": dopo["creato"]} and not (radice / backup.COPIA_PRIMA).exists()


def test_backup_regole_ai_tetti_si_ripristinano(radice):
    from fanta import regole
    b = _solo("lega/regole.json", _regole_con(nome_lega="L" * regole.MAX_NOME_LEGA,
                                              soglie=[[6 + i / 100, 1] for i in range(regole.MAX_SOGLIE)]))
    assert backup.ripristina(b, radice) == ["lega/regole.json"]
    r = regole.carica(radice / "lega" / "regole.json")
    assert len(r.nome_lega) == regole.MAX_NOME_LEGA and len(r.modificatore_difesa.soglie) == regole.MAX_SOGLIE


@pytest.mark.parametrize("nome, contenuto", [
    pytest.param("lega/rose.json", _rose_con() | {"in_piu": _annidato(30)}, id="rose"),
    pytest.param("dati/avvisi-impostazioni.json", {"in_piu": _annidato(30)}, id="impostazioni"),
])
def test_backup_con_campi_troppo_annidati_non_cambia_niente(radice, nome, contenuto):
    """I campi che l'app non conosce (scritti da una versione più nuova) passano, ma non annidati oltre backup.MAX_PROFONDITA livelli.
    Vale per ogni file (le regole rifiutano già i campi sconosciuti)."""
    prima = backup.crea(radice)
    with pytest.raises(ValueError, match=f"{nome} non è valido"):
        backup.ripristina(_solo(nome, contenuto), radice)
    dopo = backup.crea(radice)
    assert dopo == {**prima, "creato": dopo["creato"]} and not (radice / backup.COPIA_PRIMA).exists()


def test_backup_con_un_testo_che_non_si_puo_salvare_non_cambia_niente(radice):
    """Un testo che non si può scrivere su file (un carattere spezzato) si scopre prima di scrivere il primo file: niente a metà."""
    prima = backup.crea(radice)
    b = {"formato": backup.FORMATO, "versione": 1,
         "file": {"dati/osservati.json": [9], "lega/rose.json": _rose_con("Mia\ud800")}}
    with pytest.raises(ValueError, match="lega/rose.json non è valido"):
        backup.ripristina(b, radice)
    dopo = backup.crea(radice)
    assert dopo == {**prima, "creato": dopo["creato"]} and not (radice / backup.COPIA_PRIMA).exists()


def test_backup_osservati_senza_doppioni_e_senza_numeri_fuori_misura(radice):
    """Come la lettura dell'elenco: i doppioni e i codici che non possono essere giocatori si tolgono, l'ordine resta."""
    backup.ripristina(_solo("dati/osservati.json", [5, 5, 7, 0, osservati.ID_MASSIMO + 1, 5]), radice)
    assert json.loads((radice / "dati" / "osservati.json").read_text()) == [5, 7]


def test_backup_osservati_al_tetto_si_ripristinano(radice):
    tutti = list(range(1, osservati.MASSIMO + 1)) + [1, 2]          # doppioni: contano una volta
    backup.ripristina(_solo("dati/osservati.json", tutti), radice)
    assert json.loads((radice / "dati" / "osservati.json").read_text()) == list(range(1, osservati.MASSIMO + 1))


def test_backup_scelte_tiene_le_ultime_giornate_come_l_app(radice):
    """Il file delle scelte tiene le ultime scelte.MAX_GIORNATE giornate (come scelte.salva): un backup con più voci si ripristina
    con le più recenti."""
    voce = {"titolari": [1, 2, 3], "modulo": "3-4-3"}
    tante = {f"2024-25/{g}": voce for g in range(1, 39)} | {f"2025-26/{g}": voce for g in range(1, 39)}
    backup.ripristina(_solo("dati/scelte.json", tante), radice)
    dopo = json.loads((radice / "dati" / "scelte.json").read_text())
    assert len(dopo) == scelte.MAX_GIORNATE and "2025-26/38" in dopo and "2024-25/16" not in dopo and "2024-25/17" in dopo


def test_backup_con_le_forme_scritte_dall_app_si_ripristina(radice, tmp_path_factory):
    """Scelte e movimenti scritti dall'app (con tutti i loro campi) passano i controlli e tornano uguali."""
    s = radice / "dati" / "scelte.json"
    s.unlink()
    scelte.salva("2025-26", 9, list(range(1, 12)), "3-4-3", s, panchina=[12, 13], era_consigliata=True)
    scelte.salva_automatica("2025-26", 10, list(range(1, 12)), "4-4-2", s)
    tutte = json.loads(s.read_text())
    tutte["2025-26/9"] |= {"messa": True, "messa_il": "2026-11-01T10:00:00"}      # campi semplici di una versione più nuova
    s.write_text(json.dumps(tutte))
    prima = lega.Rose([lega.Squadra("A", [lega.GiocatoreRosa(1, "Rossi", "D", "ROM", 10)], 50),
                       lega.Squadra("B", [lega.GiocatoreRosa(2, "Bianchi", "C", "MIL", 5)], 40)], "A")
    dopo = lega.Rose([lega.Squadra("A", [lega.GiocatoreRosa(2, "Bianchi", "C", "MIL", 5), lega.GiocatoreRosa(None, "Nuovo", "A", None)], 45),
                      lega.Squadra("B", [lega.GiocatoreRosa(1, "Rossi", "D", "ROM", 10)], 40), lega.Squadra("C", [])], "A")
    movimenti.registra(radice / "lega" / "movimenti.json", movimenti.differenze(prima, dopo))
    b = backup.crea(radice)
    assert set(b["file"]) >= {"dati/scelte.json", "lega/movimenti.json"}
    nuova = tmp_path_factory.mktemp("nuova")
    assert backup.ripristina(b, nuova) == sorted(b["file"])
    assert backup.crea(nuova)["file"] == b["file"]


def test_il_ripristino_scrive_quanto_misura(radice):
    """Il ripristino dice a `spazio` quanti byte sta per scrivere (i file come andranno su disco), prima di scrivere qualsiasi cosa:
    se `spazio` alza un errore non cambia niente. I file si scrivono in forma compatta."""
    contenuto = _rose_con()
    b = _solo("lega/rose.json", contenuto)
    prima = backup.crea(radice)

    def troppo(n):
        raise ValueError("spazio finito")
    with pytest.raises(ValueError, match="spazio finito"):
        backup.ripristina_esito(b, radice, spazio=troppo)
    dopo = backup.crea(radice)
    assert dopo == {**prima, "creato": dopo["creato"]} and not (radice / backup.COPIA_PRIMA).exists()
    misurati = []
    backup.ripristina_esito(b, radice, spazio=misurati.append)
    file = radice / "lega" / "rose.json"
    assert misurati == [file.stat().st_size] and file.read_text(encoding="utf-8") == json.dumps(contenuto, ensure_ascii=False)


def test_un_file_alla_volta_il_resto_resta(radice):
    parziale = {"formato": backup.FORMATO, "versione": 1, "file": {"dati/osservati.json": [9]}}
    backup.ripristina(parziale, radice)
    assert json.loads((radice / "dati" / "osservati.json").read_text()) == [9]
    assert json.loads((radice / "dati" / "scelte.json").read_text())["2025-26/9"]


def test_indirizzi_del_server(dati_isolati, radice, monkeypatch):
    monkeypatch.setattr(server, "RADICE", radice)
    client = TestClient(server.app, headers={"X-Fanta": "1"})
    r = client.get("/api/backup")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    b = r.json()
    (radice / "dati" / "osservati.json").write_text("[1]")
    assert client.post("/api/backup/ripristina", json=b).json()["ripristinati"]
    assert json.loads((radice / "dati" / "osservati.json").read_text()) == [5, 7]
    assert client.post("/api/backup/ripristina", json={"formato": "x"}).status_code == 400
    assert TestClient(server.app).post("/api/backup/ripristina", json=b).status_code == 403


def test_il_ripristino_rifiuta_rose_con_una_stagione_strana(dati_isolati, radice, monkeypatch):
    monkeypatch.setattr(server, "RADICE", radice)
    client = TestClient(server.app, headers={"X-Fanta": "1"})
    b = client.get("/api/backup").json()
    prima = backup.crea(radice)["file"]
    b["file"]["lega/rose.json"]["stagione"] = "../../altro"
    b["file"]["dati/osservati.json"] = [1, 2, 3]
    r = client.post("/api/backup/ripristina", json=b)
    assert r.status_code == 400 and r.json()["detail"] == "lega/rose.json non è valido: controlla di aver scelto il file di backup giusto"
    assert backup.crea(radice)["file"] == prima and not (radice / backup.COPIA_PRIMA).exists()


def test_nome_del_file_e_formato():
    assert backup.nome_file("2026-10-31T10:00:00") == "schieraxi-backup-2026-10-31.json"
    assert backup.FORMATO == "schieraxi-backup"
    assert backup.controlla({"formato": backup.FORMATO, "versione": 1, "file": {"dati/osservati.json": [1]}})
    with pytest.raises(ValueError):
        backup.controlla({"formato": "altro-backup", "versione": 1, "file": {"dati/osservati.json": [1]}})


def test_copia_serale_una_al_giorno_e_si_tengono_le_ultime(radice, monkeypatch):
    cartella = radice / "dati" / "backup"
    cartella.mkdir()
    for giorno in range(1, 10):
        (cartella / f"schieraxi-backup-2026-10-0{giorno}.json").write_text("{}")
    monkeypatch.setattr(backup, "datetime", type("D", (), {"now": staticmethod(lambda: __import__("datetime").datetime(2026, 10, 29, 3, 30))}))
    f = backup.salva_copia(radice, tieni=7)
    assert f.name == "schieraxi-backup-2026-10-29.json"
    assert len(list(cartella.glob("*.json"))) == 7 and f.exists()
    assert backup.controlla(json.loads(f.read_text()))                      # è un backup ripristinabile
    assert backup.salva_copia(radice, tieni=7) == f and len(list(cartella.glob("*.json"))) == 7      # stesso giorno: si sostituisce


def test_copia_serale_senza_dati_non_scrive(tmp_path):
    assert backup.salva_copia(tmp_path) is None and not (tmp_path / "dati" / "backup").exists()


def test_il_ripristino_non_cambia_le_formazioni_delle_giornate_chiuse(dati_isolati, radice, monkeypatch):
    """Revisione 2/11: dopo la scadenza un backup con `scelte.json` modificato cambiava la scelta di una giornata chiusa
    (aggirava il 409 `formazione_chiusa`). Ora le giornate chiuse restano come sul server, le altre si ripristinano."""
    from fanta import archivio, consigli
    st = consigli.stagione_corrente()
    monkeypatch.setattr(server, "RADICE", radice)
    monkeypatch.setattr(server, "FILE_REGOLE", radice / "lega" / "regole.json")
    monkeypatch.setattr(server, "_db", lambda: archivio.apri(radice / "dati" / "fanta.sqlite"))
    monkeypatch.setattr(server.fasi, "iniziata", lambda db, r, stagione, g, adesso: g <= 9)     # la 9 è chiusa, dalla 10 aperte
    scelte = radice / "dati" / "scelte.json"
    sul_server = {f"{st}/9": {"titolari": [1], "modulo": "3-4-3"}, f"{st}/10": {"titolari": [2], "modulo": "3-4-3"}}
    scelte.write_text(json.dumps(sul_server))
    client = TestClient(server.app, headers={"X-Fanta": "1"})
    b = client.get("/api/backup").json()
    b["file"]["dati/scelte.json"] = {f"{st}/9": {"titolari": [99], "modulo": "4-4-2"}, f"{st}/10": {"titolari": [98], "modulo": "4-4-2"},
                                     f"{st}/11": {"titolari": [97], "modulo": "4-4-2"}, "2020-21/5": {"titolari": [96], "modulo": "4-4-2"}}
    r = client.post("/api/backup/ripristina", json=b)
    assert r.status_code == 200
    d = r.json()
    assert d["formazioni_chiuse_tenute"] is True and "giornate già chiuse non sono state cambiate" in d["messaggio"]
    dopo = json.loads(scelte.read_text())
    assert dopo[f"{st}/9"]["titolari"] == [1]                     # chiusa: resta quella del server
    assert dopo[f"{st}/10"]["titolari"] == [98] and dopo[f"{st}/11"]["titolari"] == [97]      # aperte: dal backup
    assert "2020-21/5" not in dopo                                 # stagione passata: chiusa, sul server non c'era
    assert json.loads((radice / "dati" / "osservati.json").read_text()) == [5, 7]           # il resto si ripristina come sempre
    # un backup che non tocca le giornate chiuse: messaggio semplice
    b["file"]["dati/scelte.json"] = dopo | {f"{st}/10": {"titolari": [3], "modulo": "4-4-2"}}
    d = client.post("/api/backup/ripristina", json=b).json()
    assert d["formazioni_chiuse_tenute"] is False and d["messaggio"] == server.RIPRISTINO_FATTO
    assert json.loads(scelte.read_text())[f"{st}/10"]["titolari"] == [3]


def test_unisci_scelte_tiene_le_chiuse_del_server():
    chiusa = lambda k: k.endswith("/1")
    unite, tenute = backup.unisci_scelte({"s/1": "nuova", "s/2": "nuova"}, {"s/1": "vecchia", "s/3": "vecchia"}, chiusa)
    assert unite == {"s/1": "vecchia", "s/2": "nuova"} and tenute is True
    assert backup.unisci_scelte({"s/1": "x"}, {"s/1": "x"}, chiusa) == ({"s/1": "x"}, False)
    assert backup.unisci_scelte({"s/1": "x"}, {}, chiusa) == ({}, True)                     # chiusa e assente sul server: resta assente
