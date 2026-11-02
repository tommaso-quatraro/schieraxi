"""Il nome utente si mostra con le maiuscole scelte; accesso e unicità restano sul nome normalizzato."""
import contextlib
import sqlite3

import pytest

from fanta import account
from test_account_http import PASSWORD, cliente, registra, web  # noqa: F401


def test_iscrizione_conserva_le_maiuscole(web):
    r = registra(web, nome="  MarioRossi ")
    assert r.status_code == 200, r.text
    u = r.json()["utente"]
    assert u["nome_utente"] == "mariorossi" and u["nome_visualizzato"] == "MarioRossi"
    assert web.get("/api/account/me").json()["utente"]["nome_visualizzato"] == "MarioRossi"


def test_accesso_e_unicita_senza_distinzione_di_maiuscole(web):
    registra(web, nome="MarioRossi")
    for nome in ("mariorossi", "MarioRossi", "MarioRossi".upper()):
        c = cliente()
        r = c.post("/api/account/accedi", json={"nome_utente": nome, "password": PASSWORD})
        assert r.status_code == 200, (nome, r.text)
        assert r.json()["utente"]["nome_visualizzato"] == "MarioRossi"
    altro = registra(cliente(), nome="MarioRossi".upper())
    assert altro.status_code == 400 and "già preso" in altro.json()["detail"]


def test_elenco_admin_mostra_il_nome_visualizzato(web):
    registra(web, nome="Capo", amministratore=True)
    u = web.get("/api/admin/utenti").json()["utenti"][0]
    assert u["nome_visualizzato"] == "Capo" and u["nome_utente"] == "capo"


def test_cambia_solo_le_maiuscole(web):
    registra(web, nome="marco")
    r = web.put("/api/account/nome", json={"nome_utente": "MarCo"})
    assert r.status_code == 200 and r.json()["utente"]["nome_visualizzato"] == "MarCo"
    assert web.get("/api/account/me").json()["utente"]["nome_visualizzato"] == "MarCo"
    for sbagliato in ("luca", "Marco2", "Mar co", "", "MARCO\n; DROP"):
        assert web.put("/api/account/nome", json={"nome_utente": sbagliato}).status_code == 400, sbagliato
    assert web.get("/api/account/me").json()["utente"]["nome_visualizzato"] == "MarCo"


def test_cambio_nome_richiede_la_sessione(web):
    assert cliente().put("/api/account/nome", json={"nome_utente": "Marco"}).status_code == 401


def test_nome_visualizzato_vuoto_ripiega_sul_normalizzato(web):
    registra(web, nome="Marco")
    with contextlib.closing(account.apri()) as db:
        db.execute("UPDATE utenti SET nome_visualizzato = NULL")
        db.commit()
    assert web.get("/api/account/me").json()["utente"]["nome_visualizzato"] == "marco"
    assert web.get("/api/admin/utenti").status_code in (200, 403)


def test_nome_da_mostrare_scarta_i_caratteri_strani():
    assert account.nome_da_mostrare("ＭＡＲＣＯ", "marco") == "MARCO"          # NFKC: largo -> normale
    assert account.nome_da_mostrare("Marco", "luca") == "luca"
    assert account.nome_da_mostrare("Março", "março") == "março"         # lettere con accento: resta il nome normalizzato
    assert account.nome_da_mostrare(None, "marco") == "marco"


def test_migrazione_con_copia_e_dati_intatti(multiutente):
    percorso = account.percorsi.cartella_account() / "account.sqlite"
    percorso.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(percorso)
    for m in account.MIGRAZIONI[:5]:     # da nome_visualizzato (la sesta) in poi sono quelle da applicare
        db.executescript(m)
    db.execute("PRAGMA user_version = 5")
    db.execute("INSERT INTO utenti (nome_utente, password_hash, recupero_hash, creato) VALUES ('vecchio', 'x', 'y', 'z')")
    db.commit()
    db.close()
    with contextlib.closing(account.apri()) as d:
        r = d.execute("SELECT nome_utente, password_hash, nome_visualizzato FROM utenti").fetchone()
        assert tuple(r) == ("vecchio", "x", None)
        assert account.elenco(d)[0]["nome_visualizzato"] == "vecchio"
    copie = list((percorso.parent / "backup").glob("account-prima-della-migrazione-*.sqlite"))
    assert len(copie) == 1
    vecchia = sqlite3.connect(copie[0])
    assert vecchia.execute("SELECT nome_utente FROM utenti").fetchall() == [("vecchio",)]
    assert "nome_visualizzato" not in [c[1] for c in vecchia.execute("PRAGMA table_info(utenti)")]
    vecchia.close()


def test_database_nuovo_non_fa_copie(multiutente):
    with contextlib.closing(account.apri()):
        pass
    assert not (account.percorsi.cartella_account() / "backup").exists()


def test_comando_utente_nome(web, capsys):
    registra(web, nome="mariorossi")
    from fanta import __main__ as m
    m.main(["utente-nome", "--utente", "mariorossi", "--nome", "MarioRossi"])
    assert "MarioRossi" in capsys.readouterr().out
    assert web.get("/api/account/me").json()["utente"]["nome_visualizzato"] == "MarioRossi"
    with pytest.raises(SystemExit):
        m.main(["utente-nome", "--utente", "mariorossi", "--nome", "AltroNome"])
