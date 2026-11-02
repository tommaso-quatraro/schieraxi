"""Ruolo degli account: promuovere e declassare (`imposta_ruolo` e il comando `utente-ruolo`), senza lasciare il server senza
amministratori. Il cambio non tocca le sessioni né il token del widget, che restano validi."""
import contextlib
from datetime import datetime, timezone

import pytest

from fanta import __main__ as m
from fanta import account
from fanta.account import ErroreAccount

PASSWORD = "una-password-lunga-9"
ADESSO = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def db(multiutente):
    with contextlib.closing(account.apri()) as d:
        yield d


def nuovo(db, nome, admin=False):
    """Registra un utente con un invito fresco: (utente, token, codice di recupero)."""
    inv = account.crea_invito(db, "prova", admin, ADESSO)
    return account.registra(db, nome, PASSWORD, inv, adesso=ADESSO)


def ruolo_di(db, nome):
    return db.execute("SELECT ruolo FROM utenti WHERE nome_utente = ?", (nome,)).fetchone()[0]


def errore(funzione, *args, **kw) -> ErroreAccount:
    with pytest.raises(ErroreAccount) as e:
        funzione(*args, **kw)
    return e.value


def test_promuove_e_declassa(db):
    nuovo(db, "anna", admin=True)
    nuovo(db, "marco")
    assert account.imposta_ruolo(db, "marco", "amministratore").amministratore
    assert ruolo_di(db, "marco") == "amministratore"
    assert account.imposta_ruolo(db, "anna", "utente").ruolo == "utente"       # ci sono due amministratori: si può
    assert ruolo_di(db, "anna") == "utente"


def test_non_declassa_l_ultimo_amministratore(db):
    nuovo(db, "anna", admin=True)
    e = errore(account.imposta_ruolo, db, "anna", "utente")
    assert "ultimo amministratore" in e.messaggio
    assert ruolo_di(db, "anna") == "amministratore"                             # niente è cambiato


def test_stesso_ruolo_non_fa_nulla(db):
    nuovo(db, "marco")
    assert account.imposta_ruolo(db, "marco", "utente").ruolo == "utente"
    nuovo(db, "anna", admin=True)
    assert account.imposta_ruolo(db, "anna", "amministratore").amministratore   # già amministratore, anche se è l'unico


def test_ruolo_sconosciuto_e_account_inesistente(db):
    nuovo(db, "anna", admin=True)
    assert errore(account.imposta_ruolo, db, "anna", "boss").stato == 400
    assert errore(account.imposta_ruolo, db, "fantasma", "utente").stato == 404


def test_sessioni_e_widget_restano_validi_dopo_il_declassamento(db):
    anna, token_anna, _ = nuovo(db, "anna", admin=True)
    nuovo(db, "marco", admin=True)
    token_widget, _ = account.crea_token_widget(db, anna.id, ADESSO)
    account.imposta_ruolo(db, "anna", "utente")
    da_token = account.utente_da_token(db, token_anna, ADESSO)                 # la sessione di prima non si chiude
    assert da_token is not None and not da_token.amministratore                # e il ruolo è quello nuovo, dal database
    assert account.utente_da_token_widget(db, token_widget, ADESSO) is not None


def test_comando_utente_ruolo(db, capsys):
    nuovo(db, "anna", admin=True)
    nuovo(db, "marco")
    m.main(["utente-ruolo", "--utente", "marco", "--ruolo", "admin"])
    assert "amministratore" in capsys.readouterr().out
    m.main(["utente-ruolo", "--utente", "marco", "--ruolo", "normale"])
    assert "utente normale" in capsys.readouterr().out
    with pytest.raises(SystemExit) as e:                                       # anna è l'unica amministratrice: no
        m.main(["utente-ruolo", "--utente", "anna", "--ruolo", "normale"])
    assert "ultimo amministratore" in str(e.value.code)                        # il messaggio sta in SystemExit.code
    assert ruolo_di(db, "anna") == "amministratore"


def test_comando_con_account_spenti(monkeypatch):
    monkeypatch.delenv("FANTA_MULTIUTENTE", raising=False)
    with pytest.raises(SystemExit) as e:
        m.main(["utente-ruolo", "--utente", "anna", "--ruolo", "admin"])
    assert "FANTA_MULTIUTENTE" in str(e.value.code)


def test_non_elimina_l_ultimo_amministratore(db):
    nuovo(db, "anna", admin=True)
    e = errore(account.elimina, db, account.trova(db, 1).id)
    assert "ultimo amministratore" in e.messaggio
    assert ruolo_di(db, "anna") == "amministratore"                          # l'account c'è ancora


def test_elimina_un_amministratore_se_ne_resta_un_altro(db):
    nuovo(db, "anna", admin=True)
    nuovo(db, "marco", admin=True)
    account.elimina(db, db.execute("SELECT id FROM utenti WHERE nome_utente = 'marco'").fetchone()[0])
    assert db.execute("SELECT COUNT(*) FROM utenti WHERE nome_utente = 'marco'").fetchone()[0] == 0
    assert ruolo_di(db, "anna") == "amministratore"
