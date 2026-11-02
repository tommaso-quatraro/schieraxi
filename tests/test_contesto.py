"""Contesto: i file personali di un utente, la migrazione dalla lega di oggi, il backup per utente."""
import contextlib
import json

import pytest

from fanta import account, backup, contesto
from fanta.__main__ import main

PASSWORD = "una-password-lunga-9"


def lega_di_oggi(radice):
    """Una finta installazione "di sempre": lega/ e dati/ con i file personali (e qualche file che NON va copiato)."""
    (radice / "lega" / "immagini").mkdir(parents=True)
    (radice / "lega" / "archivio" / "2025-26").mkdir(parents=True)
    (radice / "dati").mkdir()
    (radice / "lega" / "regole.json").write_text(json.dumps({"nome_lega": "MIA"}), encoding="utf-8")
    (radice / "lega" / "rose.json").write_text(json.dumps({"squadre": [], "mia_squadra": None}), encoding="utf-8")
    (radice / "lega" / "rose.json.bak").write_text("vecchia", encoding="utf-8")
    (radice / "lega" / "immagini" / "real-stemma.png").write_bytes(b"\x89PNG")
    (radice / "lega" / "archivio" / "2025-26" / "rose.json").write_text("{}", encoding="utf-8")
    (radice / "dati" / "scelte.json").write_text("{}", encoding="utf-8")
    (radice / "dati" / "osservati.json").write_text("[5]", encoding="utf-8")
    (radice / "dati" / "icona.json").write_text(json.dumps({"nome": "blu"}), encoding="utf-8")
    (radice / "dati" / "vapid.json").write_text("CHIAVE-PRIVATA-DEL-SERVER", encoding="utf-8")        # non è dell'utente
    (radice / "dati" / "chiave-prova.txt").write_text("CHIAVE-PROVA", encoding="utf-8")
    (radice / "dati" / "fanta.sqlite").write_bytes(b"db")


def test_percorsi_dell_utente(multiutente):
    a, b = contesto.Contesto.per_utente(1), contesto.Contesto.per_utente(2)
    base = contesto.cartella_utente(1)
    assert base.name == "1" and base.parent.name == "utenti" and base.parent.parent == account.percorsi.cartella_account()
    for campo in ("regole", "rose", "movimenti", "scelte", "osservati", "impostazioni_avvisi", "icona", "iscrizioni_push", "diario",
                  "affidabilita", "immagini", "copia_prima"):
        assert base in getattr(a, campo).parents, campo
        assert getattr(a, campo) != getattr(b, campo)
    assert a.utente_id == 1 and a.ntfy is False and a.cartella == base


def test_il_numero_dell_utente_deve_essere_un_numero(multiutente):
    for strano in ("../x", "1/../2", "1; rm", None):
        with pytest.raises((ValueError, TypeError)):
            contesto.cartella_utente(strano)
    assert contesto.cartella_utente("7") == contesto.cartella_utente(7)


def test_nomi_coerenti_con_il_backup_e_la_migrazione():
    assert set(contesto.NOMI_BACKUP.values()) == set(backup.CONTROLLI)                 # lo stesso elenco del backup
    destinazioni = {b for _, b in contesto.DA_MIGRARE}
    assert set(contesto.FILE_UTENTE.values()) <= destinazioni                          # ogni file personale viene portato dalla migrazione
    assert {"vapid.json", "chiave-prova.txt", "fanta.sqlite"}.isdisjoint(destinazioni)   # quel che è del server no


def test_migra_copia_e_non_sposta(multiutente, tmp_path):
    radice = tmp_path / "oggi"
    lega_di_oggi(radice)
    copiati = contesto.migra(3, radice)
    dest = contesto.cartella_utente(3)
    assert {"regole.json", "rose.json", "immagini", "archivio", "scelte.json", "osservati.json", "icona.json"} == set(copiati)
    assert json.loads((dest / "regole.json").read_text(encoding="utf-8"))["nome_lega"] == "MIA"
    assert (dest / "immagini" / "real-stemma.png").read_bytes() == b"\x89PNG"
    assert (dest / "archivio" / "2025-26" / "rose.json").exists()
    for non_va in ("rose.json.bak", "vapid.json", "chiave-prova.txt", "fanta.sqlite"):
        assert not (dest / non_va).exists(), non_va
    # i file di oggi sono ancora tutti lì
    assert (radice / "lega" / "regole.json").exists() and (radice / "dati" / "osservati.json").read_text(encoding="utf-8") == "[5]"
    assert (radice / "lega" / "immagini" / "real-stemma.png").exists()


def test_migra_non_sovrascrive_senza_forza(multiutente, tmp_path):
    radice = tmp_path / "oggi"
    lega_di_oggi(radice)
    contesto.migra(3, radice)
    (contesto.cartella_utente(3) / "osservati.json").write_text("[9]", encoding="utf-8")        # l'utente nel frattempo ha cambiato qualcosa
    with pytest.raises(ValueError, match="--forza"):
        contesto.migra(3, radice)
    assert (contesto.cartella_utente(3) / "osservati.json").read_text(encoding="utf-8") == "[9]"
    contesto.migra(3, radice, forza=True)
    assert (contesto.cartella_utente(3) / "osservati.json").read_text(encoding="utf-8") == "[5]"


def test_migra_con_poco_da_copiare(multiutente, tmp_path):
    radice = tmp_path / "vuota"
    radice.mkdir()
    assert contesto.migra(3, radice) == []
    (radice / "dati").mkdir()
    (radice / "dati" / "osservati.json").write_text("[1]", encoding="utf-8")
    assert contesto.migra(3, radice) == ["osservati.json"]


def test_comando_migra(multiutente, tmp_path, monkeypatch, capsys):
    radice = tmp_path / "oggi"
    lega_di_oggi(radice)
    vera = contesto.migra
    monkeypatch.setattr(contesto, "migra", lambda uid, forza=False: vera(uid, radice, forza))        # la lega vera non si tocca
    with pytest.raises(SystemExit, match="non esiste"):
        main(["multiutente-migra", "--utente", "marco"])
    with contextlib.closing(account.apri()) as db:
        utente, _, _ = account.registra(db, "marco", PASSWORD, account.crea_invito(db, "io", True))
    main(["multiutente-migra", "--utente", "Marco"])
    assert "originali sono rimasti" in capsys.readouterr().out
    assert (contesto.cartella_utente(utente.id) / "rose.json").exists()
    with pytest.raises(SystemExit, match="--forza"):
        main(["multiutente-migra", "--utente", "marco"])
    main(["multiutente-migra", "--utente", "marco", "--forza"])


def test_elimina_cartella(multiutente, tmp_path):
    radice = tmp_path / "oggi"
    lega_di_oggi(radice)
    contesto.migra(3, radice)
    contesto.migra(4, radice)
    contesto.elimina_cartella(3)
    assert not contesto.cartella_utente(3).exists() and contesto.cartella_utente(4).exists()
    contesto.elimina_cartella(3)                                                      # già sparita: nessun errore


def test_backup_di_un_utente_usa_i_suoi_file(multiutente, tmp_path):
    ctx = contesto.Contesto.per_utente(5)
    ctx.regole.parent.mkdir(parents=True)
    ctx.osservati.write_text("[7]", encoding="utf-8")
    ctx.scelte.write_text("{}", encoding="utf-8")
    altra_radice = tmp_path / "radice"                                                  # nemmeno lì deve finire qualcosa
    b = backup.crea(altra_radice, ctx.file_backup)
    assert b["file"] == {"dati/osservati.json": [7], "dati/scelte.json": {}}
    b["file"]["dati/osservati.json"] = [8]
    assert backup.ripristina(b, altra_radice, ctx.file_backup, ctx.copia_prima) == ["dati/osservati.json", "dati/scelte.json"]
    assert json.loads(ctx.osservati.read_text(encoding="utf-8")) == [8]
    assert json.loads(ctx.copia_prima.read_text(encoding="utf-8"))["file"]["dati/osservati.json"] == [7]       # lo stato di prima
    assert not altra_radice.exists()


def test_backup_di_sempre_invariato(tmp_path):
    (tmp_path / "dati").mkdir()
    (tmp_path / "dati" / "osservati.json").write_text("[1]", encoding="utf-8")
    b = backup.crea(tmp_path)
    assert b["file"] == {"dati/osservati.json": [1]}
    backup.ripristina(b, tmp_path)
    assert (tmp_path / backup.COPIA_PRIMA).exists()
