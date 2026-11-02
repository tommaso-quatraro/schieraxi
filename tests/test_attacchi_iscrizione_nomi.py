"""Attacchi all'iscrizione con email (modo `aperta`): scoprire quali nomi esistono, bloccare l'iscrizione di un altro bruciandogli i codici."""
import re

import pytest

from fanta import account, account_email, posta

from test_account_http import cliente
from test_account_email import codice_di
from test_registrazione_modi import conferma, iscrivi, modo, utenti


@pytest.fixture
def posta_finta(monkeypatch):
    messaggi = []
    monkeypatch.setattr(posta, "invia", lambda m: messaggi.append(m) or True)
    return messaggi


@pytest.fixture
def web(multiutente, dati_isolati, posta_finta):
    return cliente()


def da(ip):
    return cliente(**{"X-Forwarded-For": ip})


def _crea(web, posta_finta, monkeypatch, nome="anna", email="anna@example.com"):
    modo(monkeypatch, "aperta")
    iscrivi(web, nome, email)
    assert conferma(web, email, codice_di(posta_finta[-1])).status_code == 200
    posta_finta.clear()


def test_i_nomi_esistenti_non_si_scoprono(web, posta_finta, monkeypatch):
    """Attacco: provare nomi con indirizzi propri per vedere quale risponde «già preso». La risposta è identica per nome libero e
    nome occupato (stato e corpo, a parte il segreto casuale) e parte la stessa email con codice."""
    _crea(web, posta_finta, monkeypatch)
    occupato = iscrivi(da("5.5.5.1"), "anna", "spia1@example.com")
    libero = iscrivi(da("5.5.5.2"), "carla", "spia2@example.com")
    senza = lambda r: {k: v for k, v in r.json().items() if k != "iscrizione"}
    assert (occupato.status_code, senza(occupato)) == (libero.status_code, senza(libero)) == (200, senza(libero))
    assert "già preso" not in occupato.text
    assert len(posta_finta) == 2 and all(re.search(r"\b\d{6}\b", m.testo) for m in posta_finta)
    assert posta_finta[0].oggetto == posta_finta[1].oggetto                      # stesso oggetto: l'email non svela il nome occupato
    # un nome che si scrive uguale a occhio (maiuscole, larghezza piena) è lo stesso nome: stessa risposta anche così
    assert iscrivi(da("5.5.5.3"), "ANNA", "spia3@example.com").status_code == 200


def test_il_nome_occupato_si_dice_solo_dopo_la_prova_dell_email(web, posta_finta, monkeypatch):
    """Usabilità: chi ha davvero l'email e inserisce il codice riceve il messaggio chiaro; l'account non nasce e nessun dato cambia."""
    _crea(web, posta_finta, monkeypatch)
    c = da("5.5.5.4")
    assert iscrivi(c, "anna", "nuova@example.com").status_code == 200
    # codice sbagliato: messaggio generico, ancora niente sul nome
    sbagliato = conferma(c, "nuova@example.com", "000000" if codice_di(posta_finta[-1]) != "000000" else "111111")
    assert sbagliato.status_code == 403 and "preso" not in sbagliato.text
    r = conferma(c, "nuova@example.com", codice_di(posta_finta[-1]))
    assert r.status_code == 400 and "già preso" in r.json()["detail"] and "ricomincia" in r.json()["detail"]
    assert utenti() == ["anna"]
    # e riprovando con un altro nome funziona
    assert iscrivi(c, "annabella", "nuova@example.com").status_code == 200
    assert conferma(c, "nuova@example.com", codice_di(posta_finta[-1])).status_code == 200
    assert utenti() == ["anna", "annabella"]


def test_stesso_lavoro_per_nome_occupato_e_libero(web, posta_finta, monkeypatch):
    """Temporizzazione: le due richieste fanno le stesse operazioni (stesse istruzioni SQL, stesso numero di password calcolate,
    stesso numero di email), quindi non c'è una differenza di tempo da misurare. Si confrontano le operazioni, non i secondi."""
    _crea(web, posta_finta, monkeypatch)
    istruzioni, password_calcolate = [], []
    apri_vero, hash_vero = account.apri, account.hash_password

    def apri_tracciato(*a, **k):
        db = apri_vero(*a, **k)
        db.set_trace_callback(lambda q: istruzioni.append(re.sub(r"'[^']*'|\b\d+(\.\d+)?\b", "?", q)))
        return db

    def hash_contato(*a, **k):
        password_calcolate.append(1)
        return hash_vero(*a, **k)
    monkeypatch.setattr(account, "apri", apri_tracciato)
    monkeypatch.setattr(account, "hash_password", hash_contato)

    def operazioni(nome, email, ip):
        istruzioni.clear(), password_calcolate.clear()
        n_posta = len(posta_finta)
        assert iscrivi(da(ip), nome, email).status_code == 200
        return (sorted(i for i in istruzioni if not i.startswith(("BEGIN", "COMMIT", "PRAGMA"))), len(password_calcolate),
                len(posta_finta) - n_posta)
    occupato = operazioni("anna", "spia1@example.com", "5.5.6.1")
    libero = operazioni("carla", "spia2@example.com", "5.5.6.2")
    assert occupato == libero


def test_chi_brucia_i_codici_di_un_altro_non_blocca_la_sua_iscrizione(web, posta_finta, monkeypatch, multiutente):
    """Attacco: uno richiede l'iscrizione con l'email della vittima e brucia 3 codici sbagliando i tentativi, così la vittima non
    riceve più codici per un giorno. Il blocco è per indirizzo IP di chi sbaglia (e serve il suo segreto): la vittima non ne risente."""
    modo(monkeypatch, "aperta")
    spia = da("6.6.1.1")
    for giro in range(account_email.CODICI_BRUCIATI[0]):
        multiutente.t += account.ORA + 1
        assert iscrivi(spia, f"spia{giro}", "vittima@example.com").status_code == 200
        giusto = codice_di(posta_finta[-1])
        for k in range(account_email.TENTATIVI_PER_CODICE):
            assert conferma(spia, "vittima@example.com", f"{(int(giusto) + k + 1) % 10 ** 6:06d}").status_code in (403, 429)
    posta_finta.clear()
    multiutente.t += account.ORA + 1
    assert iscrivi(spia, "spia9", "vittima@example.com").status_code == 200
    assert not posta_finta                                                       # l'attaccante, ormai bloccato, non riceve altro
    vittima = da("6.6.2.2")
    assert iscrivi(vittima, "vera", "vittima@example.com").status_code == 200
    assert len(posta_finta) == 1 and re.search(r"\b\d{6}\b", posta_finta[0].testo)
    assert conferma(vittima, "vittima@example.com", codice_di(posta_finta[-1])).status_code == 200
    assert utenti() == ["vera"]
