"""Iscrizioni alle notifiche web: un tetto all'ora per utente e i nomi dei servizi che non si risolvono ricordati per qualche minuto.
Mai la rete vera (il nome del servizio lo «risolve» una funzione finta), mai l'orologio vero per il tetto. Dati inventati."""
import contextlib
import time
from datetime import datetime

import pytest

from fanta import account, limiti, push

from test_account_http import PASSWORD, cliente

ORA_FISSA = datetime(2026, 11, 8, 10, 15)          # il tetto orario non deve cambiare ora a metà test
CHIAVI = {"p256dh": "P" * 40, "auth": "A" * 20}


@pytest.fixture
def web(multiutente, dati_isolati, monkeypatch):
    monkeypatch.setattr(limiti, "_adesso", lambda: ORA_FISSA)


def utente(nome: str):
    with contextlib.closing(account.apri()) as db:
        inv = account.crea_invito(db, nome)
    c = cliente()
    assert c.post("/api/account/registra", json={"nome_utente": nome, "password": PASSWORD, "invito": inv}).status_code == 200
    return c


def iscrivi(c, i):
    return c.post("/api/push/iscrivi", json={"endpoint": f"https://push{i}.example.org/x/{i}", "keys": CHIAVI})


# ================================================================ tetto all'ora
def test_push_iscrizioni_oltre_il_tetto_dell_ora_429(web):
    a, b = utente("utentea"), utente("utenteb")
    tetto = limiti.MAX_ISCRIZIONI_PUSH_ORA
    assert [iscrivi(a, i).status_code for i in range(tetto)] == [200] * tetto
    r = iscrivi(a, tetto)
    assert r.status_code == 429 and int(r.headers["retry-after"]) == 45 * 60       # alle 10:15 si riparte alle 11
    assert iscrivi(b, 0).status_code == 200                                         # il tetto è di ciascuno


def test_push_la_stessa_iscrizione_ripetuta_conta_una_volta(web):
    a = utente("utentea")
    esiti = [iscrivi(a, 1).status_code for _ in range(limiti.MAX_ISCRIZIONI_PUSH_ORA + 3)]
    assert esiti == [200] * len(esiti)


def test_push_il_tetto_delle_iscrizioni_si_cambia_con_la_variabile(web, monkeypatch):
    monkeypatch.setenv("FANTA_MAX_ISCRIZIONI_PUSH_ORA", "2")
    a = utente("utentea")
    assert [iscrivi(a, i).status_code for i in range(3)] == [200, 200, 429]


def test_push_senza_account_nessun_tetto_alle_iscrizioni(dati_isolati, monkeypatch):
    monkeypatch.delenv("FANTA_MULTIUTENTE", raising=False)
    monkeypatch.setattr(limiti, "_adesso", lambda: ORA_FISSA)
    c = cliente()
    n = limiti.MAX_ISCRIZIONI_PUSH_ORA + 2
    assert [iscrivi(c, i).status_code for i in range(n)] == [200] * n


# ================================================================ nomi che non si risolvono
@pytest.mark.parametrize("errore", [ValueError("Nome non risolto in tempo"), OSError("nessuna risposta")])
def test_push_un_nome_che_non_si_risolve_si_ricorda_per_qualche_minuto(monkeypatch, errore):
    chiamate = []

    def non_risponde(host):
        chiamate.append(host)
        raise errore
    monkeypatch.setattr(push, "_risolvi_host", non_risponde)
    ep = "https://muto.example.org/x"
    assert not push.indirizzo_consentito(ep)
    assert not push.indirizzo_consentito(ep)
    with pytest.raises(ValueError):
        push.iscrivi({"endpoint": ep, "keys": CHIAVI}, None)
    assert chiamate == ["muto.example.org"]                              # una sola attesa: le altre richieste rispondono subito
    quando, _ = push._cache_dns["muto.example.org"]
    push._cache_dns["muto.example.org"] = (quando - push.DURATA_CACHE_NEGATIVA - 1, [])    # passati i minuti: si riprova
    assert not push.indirizzo_consentito(ep)
    assert len(chiamate) == 2


def test_push_un_nome_risolto_dopo_un_errore_vale_di_nuovo(monkeypatch):
    risposte = iter([OSError("nessuna risposta"), ["93.184.216.34"]])

    def risolvi(host):
        r = next(risposte)
        if isinstance(r, Exception):
            raise r
        return r
    monkeypatch.setattr(push, "_risolvi_host", risolvi)
    ep = "https://torna.example.org/x"
    assert not push.indirizzo_consentito(ep)
    push._cache_dns["torna.example.org"] = (time.monotonic() - push.DURATA_CACHE_NEGATIVA - 1, [])
    assert push.indirizzo_consentito(ep)
