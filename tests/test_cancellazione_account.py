"""Cancellazione dell'account definitiva anche con lavori in corso (#516, requisito R6 dell'ondata 2).

- Una scrittura partita prima dell'eliminazione (che finisce dopo, o che è a metà quando la cartella sparisce) non fa
  rinascere la cartella dell'utente: il segno di cancellazione lo legge `percorsi.scrivi_sicuro`.
- Se la cartella non si cancella tutta, l'errore non è muto: registro di sicurezza (lo vede l'amministratore) e registro del servizio.
- `python -m fanta cartelle-senza-account` trova le cartelle rimaste senza account; le cancella solo con `--esegui`.
- Le scritture degli utenti vivi restano come prima.
Dati inventati, cartelle temporanee, niente orologio vero.
"""
import contextlib
import logging
import os
from pathlib import Path

import pytest

from fanta import account, contesto, percorsi, registro
from fanta.__main__ import main

from test_account_http import PASSWORD, cliente, registra


@pytest.fixture
def ambiente(multiutente, dati_isolati):
    return multiutente


def nuovo_utente(nome: str):
    """Un account con il suo dispositivo e la sua cartella (creata scegliendo il colore dell'icona)."""
    c = cliente()
    r = registra(c, nome)
    assert r.status_code == 200, r.text
    uid = r.json()["utente"]["id"]
    assert c.put("/api/icona", json={"nome": "viola"}).status_code == 200
    assert contesto.cartella_utente(uid).is_dir()
    return c, uid


def elimina(c) -> None:
    assert c.post("/api/account/elimina", json={"password": PASSWORD}).status_code == 200


def albero(cartella: Path) -> dict[str, bytes | None]:
    """Ogni file (con il contenuto) e ogni cartella sotto `cartella`, per confrontare prima e dopo."""
    return {p.relative_to(cartella).as_posix(): (p.read_bytes() if p.is_file() else None) for p in sorted(cartella.rglob("*"))}


def righe_elencate(testo: str) -> set[str]:
    return {r.strip() for r in testo.splitlines() if r.startswith("  ")}


# ---------------------------------------------------------------- scritture in corso
def test_scrittura_dopo_la_cancellazione_non_ricrea_la_cartella(ambiente):
    c, uid = nuovo_utente("marco")
    ctx = contesto.Contesto.per_utente(uid)            # la scrittura parte prima: ha già i percorsi dell'utente
    elimina(c)
    assert not ctx.cartella.exists()
    percorsi.scrivi_sicuro(ctx.scelte, "{}")           # e finisce dopo l'eliminazione
    percorsi.scrivi_sicuro(ctx.cartella / "archivio" / "2025-26" / "rose.json", "{}")
    assert not ctx.cartella.exists()


def test_scrittura_a_meta_quando_arriva_la_cancellazione_non_ricrea_la_cartella(ambiente, monkeypatch):
    """La scrittura ha già guardato se l'account c'è e sta creando le cartelle quando l'account viene eliminato e la sua cartella
    tolta: alla fine la cartella non c'è lo stesso."""
    _, uid = nuovo_utente("marco")
    ctx = contesto.Contesto.per_utente(uid)
    vero_mkdir, fatto = Path.mkdir, []

    def mkdir_con_cancellazione(self, *a, **k):
        if not fatto and contesto.cartella_utente(uid) in (self, *self.parents):
            fatto.append(True)
            with contextlib.closing(account.apri()) as db:       # quello che fa la rotta di eliminazione, nello stesso ordine
                account.elimina(db, uid)
            contesto.elimina_cartella(uid)
            assert not contesto.cartella_utente(uid).exists()
        return vero_mkdir(self, *a, **k)

    monkeypatch.setattr(Path, "mkdir", mkdir_con_cancellazione)
    percorsi.scrivi_sicuro(ctx.cartella / "archivio" / "2025-26" / "scelte.json", "{}")
    monkeypatch.setattr(Path, "mkdir", vero_mkdir)
    assert fatto
    assert not contesto.cartella_utente(uid).exists()


# ---------------------------------------------------------------- errori non muti
def test_errore_di_cancellazione_registrato_e_avvisato(ambiente, monkeypatch, caplog, capsys):
    c, uid = nuovo_utente("marco")
    cartella = contesto.cartella_utente(uid)
    vero_unlink = os.unlink

    def unlink_bloccato(percorso, *a, **k):              # un file che il disco non lascia cancellare (in uso, permessi)
        if os.fspath(percorso).endswith("icona.json"):
            raise PermissionError(13, "file in uso")
        return vero_unlink(percorso, *a, **k)

    monkeypatch.setattr(os, "unlink", unlink_bloccato)
    with caplog.at_level(logging.ERROR):
        elimina(c)                                       # l'account è eliminato lo stesso
    assert (cartella / "icona.json").exists()
    eventi = [e for e in registro.ultimi(registro.FILE_SICUREZZA) if e["tipo"] == "cancellazione_dati_non_riuscita"]
    assert len(eventi) == 1 and eventi[0]["utente"] == str(uid) and eventi[0]["errore"] == "PermissionError"
    assert any(r.levelno >= logging.ERROR and str(uid) in r.getMessage() for r in caplog.records)
    percorsi.scrivi_sicuro(cartella / "scelte.json", "{}")      # nella cartella rimasta non entra niente di nuovo
    assert not (cartella / "scelte.json").exists()
    monkeypatch.setattr(os, "unlink", vero_unlink)
    main(["cartelle-senza-account"])                     # e il controllo la trova
    assert str(cartella) in righe_elencate(capsys.readouterr().out)


# ---------------------------------------------------------------- il comando di controllo
def test_cartelle_senza_account_elencate_non_toccate_senza_esegui(ambiente, capsys):
    _, vivo = nuovo_utente("marco")
    utenti = contesto.cartella_utente(vivo).parent
    orfana = contesto.cartella_utente(vivo + 50)
    (orfana / "immagini").mkdir(parents=True)
    (orfana / "rose.json").write_text("{}", encoding="utf-8")
    (utenti / "non-un-numero").mkdir()
    (utenti / "non-un-numero" / "x.txt").write_text("x", encoding="utf-8")
    prima = albero(utenti)
    main(["cartelle-senza-account"])
    assert righe_elencate(capsys.readouterr().out) == {str(orfana)}
    assert albero(utenti) == prima


def test_cartelle_senza_account_cancellate_con_esegui(ambiente, capsys):
    _, vivo = nuovo_utente("marco")
    utenti = contesto.cartella_utente(vivo).parent
    orfana = contesto.cartella_utente(vivo + 50)
    (orfana / "immagini").mkdir(parents=True)
    (orfana / "rose.json").write_text("{}", encoding="utf-8")
    (utenti / "non-un-numero").mkdir()
    prima_vivo = albero(contesto.cartella_utente(vivo))
    main(["cartelle-senza-account", "--esegui"])
    assert not orfana.exists()
    assert albero(contesto.cartella_utente(vivo)) == prima_vivo and (utenti / "non-un-numero").is_dir()
    capsys.readouterr()
    main(["cartelle-senza-account"])
    assert righe_elencate(capsys.readouterr().out) == set()


@pytest.mark.parametrize("database", ["mancante", "senza-account"])
def test_esegui_non_cancella_niente_se_il_database_degli_account_non_li_conosce(multiutente, database):
    """Database degli account mancante o vuoto (perso e ricreato): tutte le cartelle sembrerebbero senza account. Non si cancella niente."""
    orfana = contesto.cartella_utente(3)
    orfana.mkdir(parents=True)
    (orfana / "rose.json").write_text("{}", encoding="utf-8")
    if database == "senza-account":
        account.apri().close()
    with pytest.raises(SystemExit, match="Non ho cancellato niente"):
        main(["cartelle-senza-account", "--esegui"])
    assert (orfana / "rose.json").exists()


# ---------------------------------------------------------------- gli altri non cambiano
def test_le_scritture_degli_utenti_vivi_non_cambiano(ambiente, tmp_path):
    _, vivo = nuovo_utente("marco")
    c_via, via = nuovo_utente("luca")
    elimina(c_via)
    ctx = contesto.Contesto.per_utente(vivo)
    percorsi.scrivi_sicuro(ctx.scelte, '{"a": 1}')
    percorsi.scrivi_sicuro(ctx.scelte, '{"a": 2}')                                   # sovrascrive
    percorsi.scrivi_sicuro(ctx.cartella / "archivio" / "2025-26" / "rose.json", "{}")  # crea le cartelle che mancano
    assert ctx.scelte.read_text(encoding="utf-8") == '{"a": 2}'
    assert sorted(k for k, v in albero(ctx.cartella).items() if v is not None) == [
        "archivio/2025-26/rose.json", "icona.json", "scelte.json"]                      # niente file temporanei rimasti
    _, nuovo = nuovo_utente("anna")                                                    # un account nuovo, dopo l'eliminazione
    assert nuovo != via
    percorsi.scrivi_sicuro(contesto.Contesto.per_utente(nuovo).scelte, "{}")
    assert contesto.Contesto.per_utente(nuovo).scelte.exists()
    for f in (contesto.cartella_utente(int(f"{via}0")) / "rose.json",                 # numero che comincia come quello eliminato
              tmp_path / "lega" / "rose.json"):                                        # e fuori dalle cartelle degli utenti
        percorsi.scrivi_sicuro(f, "x")
        assert f.read_text(encoding="utf-8") == "x"


def test_eliminare_un_numero_senza_account_non_lascia_il_segno(ambiente):
    """Il segno vale solo per un account che c'era: un numero mai usato resta libero per chi si iscriverà."""
    with contextlib.closing(account.apri()) as db:
        account.elimina(db, 999)
    f = contesto.cartella_utente(999) / "scelte.json"
    percorsi.scrivi_sicuro(f, "{}")
    assert f.read_text(encoding="utf-8") == "{}"


def test_segno_rimasto_da_prima_non_blocca_un_account_con_lo_stesso_numero(ambiente):
    """Dopo un ripristino del database degli account da una copia vecchia, il numero di un account eliminato dopo la copia può
    tornare a un account nuovo: il segno rimasto non gli toglie i salvataggi."""
    _, uid = nuovo_utente("marco")
    assert percorsi.segna_cancellato(uid)
    f = contesto.Contesto.per_utente(uid).scelte
    percorsi.scrivi_sicuro(f, "{}")
    assert f.read_text(encoding="utf-8") == "{}"


def test_database_illeggibile_vale_il_segno(ambiente):
    c, uid = nuovo_utente("marco")
    elimina(c)
    (percorsi.cartella_account() / "account.sqlite").write_bytes(b"non sono un database" * 10)
    percorsi.scrivi_sicuro(contesto.Contesto.per_utente(uid).scelte, "{}")
    assert not contesto.cartella_utente(uid).exists()


def test_segno_non_scritto_registrato(ambiente):
    c, uid = nuovo_utente("marco")
    (percorsi.cartella_account() / "cancellati").write_text("", encoding="utf-8")    # un file al posto della cartella dei segni
    elimina(c)
    eventi = [e for e in registro.ultimi(registro.FILE_SICUREZZA) if e["tipo"] == "segno_cancellazione_non_riuscito"]
    assert len(eventi) == 1 and eventi[0]["utente"] == str(uid)
