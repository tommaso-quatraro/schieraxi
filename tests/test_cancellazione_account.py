"""Cancellazione dell'account definitiva anche con lavori in corso (#516, requisito R6 dell'ondata 2).

- Una scrittura partita prima dell'eliminazione (che finisce dopo, o che è a metà quando la cartella sparisce) non fa
  rinascere la cartella dell'utente: il segno di cancellazione lo legge `percorsi.scrivi_sicuro`.
- Se la cartella non si cancella tutta, l'errore non è muto: registro di sicurezza (lo vede l'amministratore) e registro del servizio.
- `python -m fanta cartelle-senza-account` trova le cartelle rimaste senza account; le cancella solo con `--esegui`.
- Le scritture degli utenti vivi restano come prima.
Dati inventati, cartelle temporanee, niente orologio vero.
"""
import contextlib
import json
import logging
import os
import sqlite3
from pathlib import Path

import pytest

from fanta import account, contesto, percorsi, push, registro
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


def test_push_non_ricrea_la_cartella_cancellata(ambiente):
    """Il giro degli avvisi ha già in memoria i dispositivi dell'utente quando lui elimina l'account: riscrivere le iscrizioni
    (dopo un invio, o togliendone una scaduta) non fa rinascere la cartella con i suoi dispositivi."""
    c, uid = nuovo_utente("marco")
    ctx = contesto.Contesto.per_utente(uid)
    dispositivi = [{"endpoint": "https://web.push.example/marco", "keys": {"p256dh": "P" * 40, "auth": "A" * 20}}]
    push.scrivi_sicuro(ctx.iscrizioni_push, json.dumps(dispositivi))
    elimina(c)
    push.scrivi_sicuro(ctx.iscrizioni_push, json.dumps(dispositivi))
    push.togli("https://web.push.example/scaduto", ctx.iscrizioni_push)
    assert not ctx.cartella.exists()


@pytest.mark.parametrize("scrivi", [percorsi.scrivi_sicuro, push.scrivi_sicuro], ids=["percorsi", "push"])
def test_scrittura_a_meta_quando_arriva_la_cancellazione_non_ricrea_la_cartella(ambiente, monkeypatch, scrivi):
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
    scrivi(ctx.cartella / "archivio" / "2025-26" / "scelte.json", "{}")
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


def test_database_illeggibile_la_scrittura_non_va_avanti(ambiente):
    """Account eliminato e database degli account rovinato: non si sa se l'account c'è ancora, quindi non si scrive, la
    cartella non rinasce e lo si dice con un errore (non in silenzio, #542)."""
    c, uid = nuovo_utente("marco")
    elimina(c)
    (percorsi.cartella_account() / "account.sqlite").write_bytes(b"non sono un database" * 10)
    with pytest.raises(percorsi.DatabaseAccountNonRisponde):
        percorsi.scrivi_sicuro(contesto.Contesto.per_utente(uid).scelte, "{}")
    assert not contesto.cartella_utente(uid).exists()


def test_errore_del_database_non_cancella_la_cartella(ambiente, monkeypatch, caplog):
    """Segno rimasto da prima di un ripristino del database e database che per un momento non si apre: la scrittura non va
    avanti e lo dice con un errore (prima si saltava in silenzio e chi chiamava rispondeva «salvato», #542), ma la cartella
    (forse di un utente vivo) resta com'è e l'errore resta nel registro del servizio, con il tipo."""
    _, uid = nuovo_utente("marco")
    cartella = contesto.cartella_utente(uid)
    assert percorsi.segna_cancellato(uid)
    prima = albero(cartella)

    def non_si_apre(*a, **k):
        raise sqlite3.OperationalError("unable to open database file")

    with monkeypatch.context() as m, caplog.at_level(logging.ERROR):
        m.setattr(sqlite3, "connect", non_si_apre)
        with pytest.raises(percorsi.DatabaseAccountNonRisponde):
            percorsi.scrivi_sicuro(cartella / "scelte.json", "{}")
        with pytest.raises(percorsi.DatabaseAccountNonRisponde):
            push.scrivi_sicuro(cartella / "push.json", "[]")
    assert albero(cartella) == prima
    assert any(r.levelno >= logging.ERROR and "OperationalError" in r.getMessage() and str(uid) in r.getMessage()
               for r in caplog.records)


def sola_lettura_che_non_risponde(monkeypatch, buone: int = 0) -> list:
    """Il database degli account non risponde solo a chi lo apre in sola lettura per guardare il segno di cancellazione
    (`percorsi.scrittura_permessa`): l'accesso con la sessione, che lo apre normalmente, va come sempre. Le prime `buone`
    aperture in sola lettura rispondono. Torna l'elenco delle aperture in sola lettura, per contarle."""
    vero, aperture = sqlite3.connect, []

    def connect(base, *a, **k):
        if str(base).endswith("account.sqlite?mode=ro"):
            aperture.append(base)
            if len(aperture) > buone:
                raise sqlite3.OperationalError("unable to open database file")
        return vero(base, *a, **k)

    monkeypatch.setattr(sqlite3, "connect", connect)
    return aperture


def test_salvataggio_con_il_database_degli_account_che_non_risponde_dice_riprova(ambiente, monkeypatch):
    """#542: segno rimasto (per esempio dopo il ripristino del database degli account) e database che non risponde. Il
    salvataggio di un utente vivo non va e l'app lo dice (503 con «riprova»), invece di rispondere «salvato» e perderlo."""
    c, uid = nuovo_utente("marco")
    assert percorsi.segna_cancellato(uid)
    icona = contesto.Contesto.per_utente(uid).icona
    prima = icona.read_bytes()
    aperture = sola_lettura_che_non_risponde(monkeypatch)
    r = c.put("/api/icona", json={"nome": "verde"})
    assert r.status_code == 503, r.text
    assert r.json() == {"detail": "Il server ha un problema con i suoi file: riprova più tardi. "
                                  "Se succede ancora, avvisa chi gestisce l'app."}
    assert r.headers["cache-control"] == "no-store"
    assert "retry-after" not in r.headers            # niente nuovo tentativo da solo: lo decide chi usa l'app
    assert aperture and icona.read_bytes() == prima  # l'errore viene dal controllo del segno, e il file è quello di prima


def test_scarica_i_tuoi_dati_esce_anche_con_il_database_degli_account_che_non_risponde(ambiente, monkeypatch):
    """«Scarica i tuoi dati» deve consegnare il file anche con il database degli account illeggibile: la data dell'ultimo
    backup (per «Da fare») è un di più, e se non si scrive il file esce lo stesso."""
    c, uid = nuovo_utente("marco")
    assert percorsi.segna_cancellato(uid)
    aperture = sola_lettura_che_non_risponde(monkeypatch)
    r = c.get("/api/backup")
    assert r.status_code == 200, r.text
    assert "attachment" in r.headers["content-disposition"]
    assert aperture                                   # la data del backup ha provato a scriversi e il database non ha risposto
    avvisi = contesto.Contesto.per_utente(uid).impostazioni_avvisi
    assert not avvisi.exists() or "backup_il" not in json.loads(avvisi.read_text(encoding="utf-8"))


def test_backup_notturno_va_avanti_se_la_copia_di_un_utente_non_si_scrive(ambiente, monkeypatch, caplog):
    """`python -m fanta backup` con gli account: la copia di un utente che non si scrive (qui: segno rimasto e database degli
    account che non risponde) non ferma le copie degli utenti dopo né quella del database degli account. L'errore resta nel
    registro del servizio, con l'utente e il tipo, e il comando finisce con errore (lo vede chi controlla il servizio)."""
    _, primo = nuovo_utente("marco")                  # numero più basso: è il primo del giro
    _, secondo = nuovo_utente("luca")
    for uid in (primo, secondo):
        contesto.Contesto.per_utente(uid).scelte.write_text('{"x": 1}', encoding="utf-8")
    assert percorsi.segna_cancellato(primo)
    sola_lettura_che_non_risponde(monkeypatch)
    with caplog.at_level(logging.ERROR), pytest.raises(SystemExit) as uscita:
        main(["backup"])
    assert uscita.value.code not in (0, None)
    assert not list((contesto.cartella_utente(primo) / "backup").glob("schieraxi-backup-*.json"))
    assert len(list((contesto.cartella_utente(secondo) / "backup").glob("schieraxi-backup-*.json"))) == 1
    assert len(list((percorsi.cartella_account() / "backup").glob("account-*.sqlite"))) == 1
    assert any(r.levelno >= logging.ERROR and str(primo) in r.getMessage() and "DatabaseAccountNonRisponde" in r.getMessage()
               for r in caplog.records)


@pytest.mark.parametrize("scrivi", [percorsi.scrivi_sicuro, push.scrivi_sicuro], ids=["percorsi", "push"])
def test_database_che_smette_di_rispondere_dopo_la_scrittura_non_chiede_di_rifarla(ambiente, monkeypatch, scrivi):
    """Il controllo DOPO la scrittura trova il database in errore: il file è già salvato, quindi niente errore «riprova»
    (rifare un'aggiunta, per esempio un movimento di mercato, la scriverebbe due volte)."""
    _, uid = nuovo_utente("marco")
    assert percorsi.segna_cancellato(uid)
    f = contesto.cartella_utente(uid) / "scelte.json"
    aperture = sola_lettura_che_non_risponde(monkeypatch, buone=1)
    scrivi(f, '{"a": 1}')
    assert len(aperture) == 2                         # prima e dopo: il secondo controllo c'è stato e non ha risposto
    assert f.read_text(encoding="utf-8") == '{"a": 1}'


def test_segno_non_scritto_registrato(ambiente):
    c, uid = nuovo_utente("marco")
    (percorsi.cartella_account() / "cancellati").write_text("", encoding="utf-8")    # un file al posto della cartella dei segni
    elimina(c)
    eventi = [e for e in registro.ultimi(registro.FILE_SICUREZZA) if e["tipo"] == "segno_cancellazione_non_riuscito"]
    assert len(eventi) == 1 and eventi[0]["utente"] == str(uid)
