"""Le cartelle senza account fra le invarianti della sentinella (#537).

Con gli account, una cartella `utenti/<numero>` il cui account non c'è più (una cancellazione non finita, o una scrittura che non
passa da `scrivi_sicuro` e la ricrea dopo) la trova `python -m fanta cartelle-senza-account`, ma solo se qualcuno lo lancia.
La sentinella le conta a ogni giro: invariante `cartella_senza_account`, esito «avviso», solo quante sono (mai i numeri degli
account). Account, cartelle, archivio e file di stato in cartelle temporanee; orologio passato come `adesso`."""
import contextlib
import json
import re
import shutil
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from fanta import account, archivio, consigli, contesto, controlli, percorsi, sentinella
from fanta.__main__ import main

ST = "2026-27"
ADESSO = datetime(2026, 11, 15, 20, 0)               # senza fuso, come lo passa il cron


@pytest.fixture
def ambiente(multiutente, dati_isolati, monkeypatch):
    """Account accesi su una cartella temporanea, archivio vuoto, stagione fissa, nessuna copia su file dei risultati in diretta."""
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: ST)
    monkeypatch.setattr(sentinella, "_prepara_live", lambda: None)


@pytest.fixture
def db(tmp_path):
    with contextlib.closing(archivio.apri(tmp_path / "fanta.sqlite")) as d:
        yield d


def nuovo_account(nome: str) -> int:
    """Un account vero nel database temporaneo, con la sua cartella di dati."""
    with contextlib.closing(account.apri()) as adb:
        numero = account.registra(adb, nome, "una password lunga 123", account.crea_invito(adb, "prova"))[0].id
    contesto.cartella_utente(numero).mkdir(parents=True)
    return numero


def cartella_rinata(numero: int) -> Path:
    """La cartella di un account che non c'è più, come la lascia una scrittura arrivata dopo la cancellazione."""
    cartella = contesto.cartella_utente(numero)
    (cartella / "immagini").mkdir(parents=True)
    (cartella / "push.json").write_text("[]", encoding="utf-8")
    return cartella


def trovate(esito: dict) -> list[tuple]:
    return [(r.invariante, r.utente, r.giornata) for r in esito["rotture"]]


def righe_di_stato(db) -> dict:
    return {r["nome"]: r for r in controlli.leggi(db, ST)}


# ---------------------------------------------------------------- il giro le conta
def test_il_giro_conta_le_cartelle_senza_account_e_non_ne_dice_i_numeri(ambiente, db):
    vivo = nuovo_account("utente1")
    orfane = [cartella_rinata(vivo + 50), cartella_rinata(vivo + 51)]
    esito = sentinella.esegui(db, ADESSO)
    assert trovate(esito) == [("cartella_senza_account", None, None)]
    dettaglio = esito["rotture"][0].dettaglio
    assert dettaglio.startswith("2 cartelle ")
    assert re.findall(r"\d+", dettaglio) == ["2"]                     # solo quante sono: nessun numero di account
    for cartella in orfane:                                           # sola lettura: la sentinella non le tocca
        assert (cartella / "push.json").read_text(encoding="utf-8") == "[]" and (cartella / "immagini").is_dir()


def test_le_cartelle_degli_account_vivi_e_quelle_senza_numero_non_contano(ambiente, db):
    nuovo_account("utente1")
    nuovo_account("utente2")
    (percorsi.cartella_utenti() / "non-un-numero").mkdir()
    assert sentinella.esegui(db, ADESSO)["rotture"] == []


# ---------------------------------------------------------------- «Stato dei dati» e avviso
def test_in_stato_dei_dati_e_un_avviso_e_torna_a_posto_quando_la_cartella_sparisce(ambiente, db):
    vivo = nuovo_account("utente1")
    orfana = cartella_rinata(vivo + 50)
    sentinella.registra(db, sentinella.esegui(db, ADESSO), quando="2026-11-15T20:00:00")
    righe = righe_di_stato(db)
    assert righe["sentinella_cartella_senza_account"]["esito"] == "avviso"
    assert re.search(r"\b1 cartella\b", righe["sentinella_cartella_senza_account"]["dettaglio"])
    assert righe["sentinella"]["esito"] == "avviso"                   # da guardare: non è una cosa sbagliata che vede l'utente
    shutil.rmtree(orfana)
    sentinella.registra(db, sentinella.esegui(db, ADESSO + timedelta(hours=1)), quando="2026-11-15T21:00:00")
    righe = righe_di_stato(db)
    assert righe["sentinella_cartella_senza_account"]["esito"] == "ok" and righe["sentinella"]["esito"] == "ok"


def test_avviso_al_secondo_giro_senza_numeri_e_niente_piu_dopo_la_pulizia(ambiente, tmp_path):
    vivo = nuovo_account("utente1")
    orfane = [cartella_rinata(vivo + 50), cartella_rinata(vivo + 51)]
    stato, mandati = tmp_path / "sentinella.json", []

    def manda(titolo, testo):
        mandati.append(testo)
        return True

    def giro(ore: int) -> dict:
        sentinella.giro(manda=manda, file_stato=stato, adesso=ADESSO + timedelta(hours=ore), scrivi=lambda s: None,
                        db_percorso=tmp_path / "fanta.sqlite")
        return json.loads(stato.read_text(encoding="utf-8"))["giri"][-1]

    assert giro(0)["rotte"] == [] and mandati == []                   # vista una volta sola (cancellazione in corso): non è un allarme
    voce = giro(1)
    assert voce["rotte"] == ["cartella_senza_account"] and voce["inviato"] is True
    assert len(mandati) == 1 and "cartella_senza_account" in mandati[0]
    assert not any(cartella.name in mandati[0] for cartella in orfane)     # nell'avviso nessun numero di account
    main(["cartelle-senza-account", "--esegui"])                      # il comando che le toglie
    assert giro(2)["rotte"] == [] and len(mandati) == 1


# ---------------------------------------------------------------- quando non si può sapere
def test_con_gli_account_spenti_le_cartelle_non_si_guardano(ambiente, db, monkeypatch):
    vivo = nuovo_account("utente1")
    cartella_rinata(vivo + 50)
    monkeypatch.setenv("FANTA_MULTIUTENTE", "0")
    assert sentinella.esegui(db, ADESSO, contesti=[])["rotture"] == []


def test_senza_database_degli_account_nessun_allarme_e_niente_di_scritto(ambiente, db):
    """Installazione nuova: gli account sono accesi ma nessuno è ancora entrato. Il giro non va in errore e non crea il database."""
    assert sentinella.esegui(db, ADESSO)["rotture"] == []
    assert not (percorsi.cartella_account() / "account.sqlite").exists()


def test_database_degli_account_illeggibile_il_giro_del_cron_non_muore_e_avvisa(ambiente, tmp_path):
    """Come lo lancia il cron (`giro`, che non passa `contesti`): con il database degli account rovinato non si leggono né
    l'elenco degli utenti né quello delle cartelle. Il giro non deve morire lasciando solo una traccia nel registro: finisce,
    lo scrive in «Stato dei dati» e al secondo giro avvisa."""
    vivo = nuovo_account("utente1")
    cartella_rinata(vivo + 50)
    (percorsi.cartella_account() / "account.sqlite").write_bytes(b"non sono un database" * 10)
    stato, archivio_di_prova, mandati = tmp_path / "sentinella.json", tmp_path / "fanta.sqlite", []

    def manda(titolo, testo):
        mandati.append(testo)
        return True

    def giro(ore: int) -> dict:
        return sentinella.giro(manda=manda, file_stato=stato, adesso=ADESSO + timedelta(hours=ore), scrivi=lambda s: None,
                               db_percorso=archivio_di_prova)

    esito = giro(0)
    assert esito["controllati"] == [] and set(trovate(esito)) == {("risposta_in_errore", None, None)}
    dettagli = [r.dettaglio for r in esito["rotture"]]
    assert any("utenti" in d and "DatabaseError" in d for d in dettagli)        # l'elenco di chi controllare
    assert any("cartelle" in d and "DatabaseError" in d for d in dettagli)      # il conto delle cartelle senza account
    with contextlib.closing(archivio.apri(archivio_di_prova)) as db:
        righe = righe_di_stato(db)
    assert righe["sentinella_risposta_in_errore"]["esito"] == "errore" and righe["sentinella"]["esito"] == "errore"
    assert "utenti" in righe["sentinella_risposta_in_errore"]["dettaglio"]
    assert mandati == []                                              # un giro solo non basta, come per ogni altra rottura
    giro(1)
    assert len(mandati) == 1 and "risposta_in_errore" in mandati[0]
    ultimo = json.loads(stato.read_text(encoding="utf-8"))["giri"][-1]
    assert ultimo["rotte"] == ["risposta_in_errore"] and ultimo["inviato"] is True
