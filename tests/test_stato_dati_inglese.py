"""Stato dei dati in inglese (#949): i nomi che scrive il server (fasce di «gioca N%», righe degli aggiornamenti, fonte delle foto,
conteggi d'uso, controlli sui dati) arrivano con la loro frase (`*_frase`, fanta/frasi.py), così la web li traduce dal catalogo.
Il testo italiano resta quello di prima, parola per parola (lo leggono l'iPhone e chi usa l'app in italiano)."""
import pytest

from fanta import archivio, controlli, fonti_attive, frasi, modello, stato_dati, uso
# `stato_dati.riepilogo` importa la sentinella solo quando serve: importata qui, la fixture di conftest ne sposta il file in una
# cartella temporanea (lanciato da solo, il test aprirebbe `dati/sentinella.json` del repository)
from fanta import sentinella  # noqa: F401

ST = "2026-27"


@pytest.fixture
def db(tmp_path):
    d = archivio.apri(tmp_path / "t.sqlite")
    yield d
    d.close()


def _ha_la_frase(testo, italiano):
    assert isinstance(testo, frasi.Frase), testo
    assert str(testo) == italiano
    assert frasi.da_json(testo.json()) == italiano


def test_le_fasce_di_gioca_hanno_la_frase_con_lo_stesso_italiano(db):
    for nome, *_ in modello.GRUPPI_PROBABILI:
        _ha_la_frase(stato_dati.nome_gruppo(nome), nome)
    gruppi = stato_dati.riepilogo(db, ST)["calibrazione"]["gruppi"]
    assert [g["gruppo"] for g in gruppi] == [nome for nome, *_ in modello.GRUPPI_PROBABILI]     # il nome resta: fa da chiave
    assert gruppi[0]["gruppo_frase"] == {"chiave": "fascia.titolare", "param": {"da": 90, "a": 100}}
    assert gruppi[3]["gruppo_frase"] == {"chiave": "fascia.titolare_sotto", "param": {"a": 50}}
    assert stato_dati.nome_gruppo("Un gruppo che non c'è") == "Un gruppo che non c'è"


AGGIORNAMENTI = {           # i nomi di prima, parola per parola
    "aggiornamento": "Aggiornamento generale", "listone": "Listone e quotazioni", "calendario": "Calendario", "voti": "Voti e bonus",
    "probabili": "Probabili formazioni", "understat": "Statistiche avanzate", "dati-extra": "Statistiche di squadra",
    "controlli": "Controlli sui dati", "probabili-rapido": "Probabili vicino alla scadenza",
    "risultati-rapido": "Risultati la sera stessa", "taratura-probabili": "Taratura di «gioca N%»"}
CONTROLLI = {
    "partite_per_giornata": "10 partite per giornata", "voti_per_giornata": "Voti nelle giornate finite",
    "somma_xg": "Gol attesi dei giocatori e della partita", "titolari_per_squadra": "11 titolari per squadra",
    "gol_dei_voti": "Gol dei voti uguali al risultato", "gol_subiti_portieri": "Gol presi dai portieri uguali al risultato",
    "partite_senza_statistiche": "Statistiche delle partite giocate", "squalificati_cartellini": "Squalificati: cartellini e probabili",
    "sentinella": "Sentinella: risposte dell'app"}


def test_le_righe_degli_aggiornamenti_hanno_la_frase(db):
    assert set(stato_dati.ETICHETTE_AGGIORNAMENTI) == set(AGGIORNAMENTI)
    for cosa, italiano in AGGIORNAMENTI.items():
        _ha_la_frase(stato_dati.etichetta_aggiornamento(cosa), italiano)
    _ha_la_frase(stato_dati.etichetta_aggiornamento("calendario 2026-27"), "Calendario completo 2026-27")
    _ha_la_frase(stato_dati.etichetta_aggiornamento("dati-extra 2025-26"), "Statistiche di squadra 2025-26")
    sconosciuta = stato_dati.etichetta_aggiornamento("passo-nuovo")
    assert sconosciuta == "Passo nuovo" and not isinstance(sconosciuta, frasi.Frase)
    db.execute("INSERT INTO aggiornamenti (cosa, quando, dettaglio) VALUES ('aggiornamento', '2026-11-26T10:00:00', NULL)")
    db.execute("INSERT INTO aggiornamenti (cosa, quando, dettaglio) VALUES ('calendario 2026-27', '2026-11-26T10:00:00', NULL)")
    db.execute("INSERT INTO aggiornamenti (cosa, quando, dettaglio) VALUES ('passo-nuovo', '2026-11-26T10:00:00', NULL)")
    righe = {a["cosa"]: a for a in stato_dati.riepilogo(db, ST)["aggiornamenti"]}
    assert righe["aggiornamento"]["etichetta"] == "Aggiornamento generale"
    assert righe["aggiornamento"]["etichetta_frase"] == {"chiave": "aggiornamento.aggiornamento", "param": {}}
    assert righe["calendario 2026-27"]["etichetta_frase"] == {"chiave": "aggiornamento.calendario_stagione",
                                                              "param": {"stagione": "2026-27"}}
    assert righe["passo-nuovo"]["etichetta_frase"] is None


def test_la_fonte_delle_foto_ha_il_nome_con_la_frase(monkeypatch):
    """La riga delle foto c'è solo nelle copie con il loro modulo (`fonti_attive.disponibile`): qui si fa finta che ci sia."""
    monkeypatch.setattr(fonti_attive, "disponibile", lambda fonte: True)
    righe = {f["id"]: f for f in fonti_attive.stato()}
    assert righe["foto"]["nome"] == "Foto dei giocatori"
    assert righe["foto"]["nome_frase"] == {"chiave": "fonte.nome_foto", "param": {}}
    assert righe["understat"]["nome"] == "Understat" and righe["understat"]["nome_frase"] is None      # i nomi propri restano


def test_i_conteggi_d_uso_hanno_il_nome_con_la_frase():
    """Il nome di ogni funzione contata è quello di `funzioni.FUNZIONI`, parola per parola, con la sua frase per tradurlo."""
    from fanta import funzioni
    uso.conta("GET", "/api/diario", 200)
    uso.conta("GET", "/api/novita", 200)
    per_funzione = {f["funzione"]: f for f in uso.riepilogo()["per_funzione"]}
    assert per_funzione["diario"]["etichetta"] == "Diario delle giornate"
    assert per_funzione["diario"]["etichetta_frase"] == {"chiave": "uso.funzione_diario", "param": {}}
    assert per_funzione["novita"]["etichetta"] == "Novità"
    for funzione in set(uso.FUNZIONE_DI_ROTTA.values()):                  # ogni funzione contata ha la frase, con lo stesso nome
        _ha_la_frase(uso.nome_funzione(funzione), funzioni.FUNZIONI[funzione][0])
    assert uso.nome_funzione("vecchia_funzione") == "vecchia funzione"     # un nome di prima, rimasto nel file: senza frase


def test_i_controlli_sui_dati_hanno_la_frase(db):
    assert set(controlli.ETICHETTE) == set(CONTROLLI)
    for nome, italiano in CONTROLLI.items():
        _ha_la_frase(controlli.etichetta(nome), italiano)
    assert not isinstance(controlli.etichetta("sentinella_qualcosa"), frasi.Frase)
    for i in range(10):                                                    # una giornata intera: il controllo ha qualcosa da dire
        db.execute("INSERT INTO partite (id, stagione, giornata, data, casa, trasferta, giocata) VALUES (?, ?, 1, ?, ?, ?, 1)",
                   (100 + i, ST, "2026-09-01 15:00", f"c{i}", f"t{i}"))
    controlli.esegui(db)
    righe = {c["nome"]: c for c in stato_dati.riepilogo(db, ST)["controlli"]}
    assert righe["partite_per_giornata"]["etichetta_frase"] == {"chiave": "controllo.partite_per_giornata", "param": {}}
