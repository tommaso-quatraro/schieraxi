"""Chi gestisce il server blocca, sblocca o elimina l'account di un altro (Impostazioni › Gestione › Utenti, e da riga di comando).

- Solo il titolare (un amministratore), mai su sé stesso; l'ultimo amministratore non si blocca né si elimina.
- Bloccato: le sue sessioni e il token del widget si chiudono subito e non entra più (né con la password né con Google);
  sbloccato rientra con la sua password. Chi sbaglia la password non scopre che l'account è bloccato.
- Eliminato: sparisce con tutti i suoi dati, con gli stessi passi di «Elimina il mio account» (account, cartella dei dati, numero
  nelle consigliate già mostrate, sessioni, token del widget).
- Una riga nel registro di sicurezza per ogni blocco, sblocco ed eliminazione, con chi l'ha fatto.
Dati inventati, cartelle temporanee."""
import contextlib
import json
from datetime import datetime

import pytest

from fanta import account, contesto, frasi, fuso, percorsi, push, registro
from fanta.__main__ import main

from test_account_http import PASSWORD, cliente, registra
from test_cancellazione_account import albero, numeri_nelle_consigliate, ora_fissa, ricorda  # noqa: F401  (ora_fissa è una fixture)
from test_social import cliente as cliente_google, giro, iscrivi_con_google, scena  # noqa: F401  (scena è una fixture)
from test_social import invito as invito_google


@pytest.fixture
def titolare(multiutente, dati_isolati):
    c = cliente()
    assert registra(c, "capo", amministratore=True).status_code == 200
    return c


def amico(nome: str = "luca"):
    """Un account con la sua sessione e la sua cartella (nasce scegliendo il colore dell'icona)."""
    c = cliente()
    r = registra(c, nome)
    assert r.status_code == 200, r.text
    uid = r.json()["utente"]["id"]
    assert c.put("/api/icona", json={"nome": "viola"}).status_code == 200
    assert contesto.cartella_utente(uid).is_dir()
    return c, uid


def utenti(c) -> dict[str, dict]:
    r = c.get("/api/admin/utenti")
    assert r.status_code == 200, r.text
    return {u["nome_utente"]: u for u in r.json()["utenti"]}


def eventi(tipo: str) -> list[dict]:
    return [e for e in registro.ultimi(registro.FILE_SICUREZZA, 200) if e["tipo"] == tipo]


def accedi(nome: str, password: str = PASSWORD, **extra):
    return cliente().post("/api/account/accedi", json={"nome_utente": nome, "password": password} | extra)


def token_widget_valido(token: str) -> bool:
    with contextlib.closing(account.apri()) as db:
        return account.utente_da_token_widget(db, token) is not None


# ---------------------------------------------------------------- chi può
def test_solo_il_titolare(titolare):
    luca, _ = amico("luca")
    _, sara = amico("sara")
    for chi, atteso in ((luca, 403), (cliente(), 401)):
        assert chi.get("/api/admin/utenti").status_code == atteso
        assert chi.post(f"/api/admin/utenti/{sara}/blocca").status_code == atteso
        assert chi.post(f"/api/admin/utenti/{sara}/sblocca").status_code == atteso
        assert chi.delete(f"/api/admin/utenti/{sara}").status_code == atteso
    assert utenti(titolare)["sara"]["bloccato"] is False
    assert accedi("sara").status_code == 200


def test_il_titolare_non_blocca_ne_elimina_se_stesso(titolare):
    io = titolare.get("/api/account/me").json()["utente"]["id"]
    r = titolare.post(f"/api/admin/utenti/{io}/blocca")
    assert r.status_code == 400 and r.json()["detail"] == "Non puoi bloccare il tuo account", r.text
    r = titolare.delete(f"/api/admin/utenti/{io}")
    assert r.status_code == 400 and "Il tuo account" in r.json()["detail"], r.text
    assert titolare.get("/api/account/me").status_code == 200
    assert utenti(titolare)["capo"]["bloccato"] is False and not eventi("account_bloccato") and not eventi("account_eliminato")


def test_account_che_non_c_e(titolare):
    for r in (titolare.post("/api/admin/utenti/999/blocca"), titolare.post("/api/admin/utenti/999/sblocca"),
              titolare.delete("/api/admin/utenti/999")):
        assert r.status_code == 404, r.text
    assert titolare.post("/api/admin/utenti/0/blocca").status_code == 422


def test_l_ultimo_amministratore_non_si_blocca(titolare):
    """Dal comando del server (dove non c'è un «sé stesso»): bloccare l'unico amministratore lascerebbe il server senza nessuno
    che lo gestisca."""
    io = titolare.get("/api/account/me").json()["utente"]["id"]
    with contextlib.closing(account.apri()) as db, pytest.raises(account.ErroreAccount, match="ultimo amministratore"):
        account.blocca(db, io)
    assert titolare.get("/api/account/me").status_code == 200


# ---------------------------------------------------------------- l'elenco
def test_elenco_con_iscrizione_ultimo_accesso_e_blocco(titolare):
    _, uid = amico("luca")
    u = utenti(titolare)["luca"]
    assert u["id"] == uid and u["bloccato"] is False and u["bloccato_il"] is None
    assert u["ultimo_accesso"] and u["creato"]
    giorno = lambda testo: frasi.giorno_mese(datetime.fromisoformat(testo).astimezone(fuso.FUSO))  # noqa: E731
    atteso = frasi.F("admin.utente_dettaglio", creato=giorno(u["creato"]), accesso=giorno(u["ultimo_accesso"]))
    assert u["dettaglio"] == str(atteso) and u["dettaglio"].startswith("Iscrizione ") and ", ultimo accesso " in u["dettaglio"]
    assert u["dettaglio_frase"] == frasi.di(atteso)
    assert u["blocco"] is None and u["blocco_frase"] is None
    assert titolare.post(f"/api/admin/utenti/{uid}/blocca").status_code == 200
    u = utenti(titolare)["luca"]
    assert u["bloccato"] is True and u["bloccato_il"]
    assert u["blocco_frase"] == frasi.di(frasi.F("admin.utente_bloccato", quando=giorno(u["bloccato_il"])))
    assert u["blocco"].startswith("Bloccato ") and u["blocco"].endswith(": non può entrare.")


def test_senza_sessioni_rimaste_niente_ultimo_accesso(titolare):
    """Le sessioni scadute si cancellano: allora l'ultimo accesso non si sa e la riga non inventa una data."""
    _, uid = amico("luca")
    with contextlib.closing(account.apri()) as db:
        db.execute("DELETE FROM sessioni WHERE utente_id = ?", (uid,))
        db.commit()
    u = utenti(titolare)["luca"]
    assert u["ultimo_accesso"] is None
    assert u["dettaglio_frase"]["chiave"] == "admin.utente_dettaglio_senza_accesso"
    assert u["dettaglio"].endswith(", nessun accesso recente.")


# ---------------------------------------------------------------- blocco
def test_bloccato_perde_le_sessioni_e_il_widget_e_non_entra(titolare):
    luca, uid = amico("luca")
    nativo = accedi("luca", nativo=True).json()["token"]
    widget = luca.post("/api/account/token-widget").json()["token"]
    assert token_widget_valido(widget)
    r = titolare.post(f"/api/admin/utenti/{uid}/blocca")
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True, "sessioni_chiuse": 2}
    assert luca.get("/api/account/me").status_code == 401                                          # il web
    assert cliente().get("/api/account/me", headers={"Authorization": f"Bearer {nativo}"}).status_code == 401   # l'app
    assert not token_widget_valido(widget)
    assert cliente().get("/api/oggi", headers={"Authorization": f"Bearer {widget}"}).status_code == 401
    r = accedi("luca")
    assert r.status_code == 403 and r.json()["codice"] == "account_bloccato", r.text
    assert r.json()["detail"] == account.BLOCCATO
    sbagliata = accedi("luca", "password-sbagliata-1")
    assert sbagliata.status_code == 401 and sbagliata.json()["detail"] == account.ACCESSO_SBAGLIATO   # non dice niente del blocco
    assert eventi("accesso_negato_bloccato")[0]["nome"] == "luca"


def test_bloccato_non_riceve_piu_le_notifiche(titolare):
    """Le iscrizioni alle notifiche web dei suoi dispositivi si tolgono: il giro degli avvisi non gli manda più niente."""
    _, uid = amico("luca")
    file = contesto.Contesto.per_utente(uid).iscrizioni_push
    push.scrivi_sicuro(file, json.dumps([{"endpoint": "https://web.push.example/luca", "keys": {"p256dh": "P" * 40, "auth": "A" * 20}}]))
    assert push.iscrizioni(file)
    assert titolare.post(f"/api/admin/utenti/{uid}/blocca").status_code == 200
    assert push.iscrizioni(file) == []


def test_sbloccato_rientra(titolare):
    _, uid = amico("luca")
    assert titolare.post(f"/api/admin/utenti/{uid}/blocca").status_code == 200
    r = titolare.post(f"/api/admin/utenti/{uid}/sblocca")
    assert r.status_code == 200 and r.json() == {"ok": True}, r.text
    assert utenti(titolare)["luca"]["bloccato"] is False
    nuovo = cliente()
    assert nuovo.post("/api/account/accedi", json={"nome_utente": "luca", "password": PASSWORD}).status_code == 200
    assert nuovo.get("/api/account/me").json()["utente"]["nome_utente"] == "luca"


def test_bloccare_due_volte_non_cambia_niente(titolare):
    _, uid = amico("luca")
    assert titolare.post(f"/api/admin/utenti/{uid}/blocca").status_code == 200
    quando = utenti(titolare)["luca"]["bloccato_il"]
    r = titolare.post(f"/api/admin/utenti/{uid}/blocca")
    assert r.status_code == 200 and r.json()["sessioni_chiuse"] == 0
    assert utenti(titolare)["luca"]["bloccato_il"] == quando and len(eventi("account_bloccato")) == 1
    assert titolare.post(f"/api/admin/utenti/{uid}/sblocca").status_code == 200
    assert titolare.post(f"/api/admin/utenti/{uid}/sblocca").status_code == 200
    assert len(eventi("account_sbloccato")) == 1


def test_una_sessione_rimasta_aperta_non_vale_per_un_bloccato(titolare):
    """Anche se una sessione o il token del widget restassero (nati un attimo prima del blocco), un bloccato non passa."""
    luca, uid = amico("luca")
    widget = luca.post("/api/account/token-widget").json()["token"]
    with contextlib.closing(account.apri()) as db:
        db.execute("UPDATE utenti SET bloccato = '2026-11-26T09:00:00+00:00' WHERE id = ?", (uid,))
        db.commit()
    assert luca.get("/api/account/me").status_code == 401
    assert not token_widget_valido(widget)


def test_il_bloccato_non_entra_nemmeno_con_google(scena):  # noqa: F811
    c = cliente_google()
    nuovo = iscrivi_con_google(c, scena)
    r = c.post("/api/account/social/completa", json={"iscrizione": nuovo["iscrizione"], "nome_utente": "mario",
                                                     "invito": invito_google(), "accetto_termini": True})
    assert r.status_code == 200, r.text
    uid = r.json()["utente"]["id"]
    with contextlib.closing(account.apri()) as db:
        account.blocca(db, uid)
    assert c.get("/api/account/me").status_code == 401
    r = giro(cliente_google("2.2.2.2"), scena)
    assert r.status_code == 403 and r.json()["codice"] == "account_bloccato", r.text


# ---------------------------------------------------------------- eliminazione
def test_eliminato_sparisce_con_tutti_i_suoi_dati(titolare, ora_fissa):  # noqa: F811
    luca, uid = amico("luca")
    sara_c, sara = amico("sara")
    nativo = accedi("luca", nativo=True).json()["token"]
    widget = luca.post("/api/account/token-widget").json()["token"]
    ricorda(uid, "solo-sua", propria=True)
    ricorda(uid, "della-stessa-lega", propria=True)
    ricorda(sara, "della-stessa-lega", propria=True)
    ctx = contesto.Contesto.per_utente(uid)
    prima_sara = albero(contesto.cartella_utente(sara))
    r = titolare.delete(f"/api/admin/utenti/{uid}")
    assert r.status_code == 200 and r.json() == {"ok": True}, r.text
    assert not ctx.cartella.exists()                                                     # la cartella dei dati
    assert luca.get("/api/account/me").status_code == 401                                 # le sessioni
    assert cliente().get("/api/account/me", headers={"Authorization": f"Bearer {nativo}"}).status_code == 401
    assert not token_widget_valido(widget)                                                # il token del widget
    assert uid not in numeri_nelle_consigliate() and sara in numeri_nelle_consigliate()   # le consigliate già mostrate
    with contextlib.closing(account.apri()) as db:
        for tabella in ("utenti WHERE id", "sessioni WHERE utente_id", "token_widget WHERE utente_id"):
            assert db.execute(f"SELECT COUNT(*) FROM {tabella} = ?", (uid,)).fetchone()[0] == 0, tabella
    assert accedi("luca").status_code == 401
    assert "luca" not in utenti(titolare)
    percorsi.scrivi_sicuro(ctx.scelte, "{}")                                              # una scrittura in ritardo non la fa rinascere
    assert not ctx.cartella.exists()
    assert albero(contesto.cartella_utente(sara)) == prima_sara and sara_c.get("/api/account/me").status_code == 200
    assert titolare.delete(f"/api/admin/utenti/{uid}").status_code == 404


def test_si_elimina_anche_un_bloccato(titolare):
    _, uid = amico("luca")
    assert titolare.post(f"/api/admin/utenti/{uid}/blocca").status_code == 200
    assert titolare.delete(f"/api/admin/utenti/{uid}").status_code == 200
    assert not contesto.cartella_utente(uid).exists() and "luca" not in utenti(titolare)


# ---------------------------------------------------------------- registro di sicurezza
def test_una_riga_nel_registro_per_ogni_blocco_sblocco_ed_eliminazione(titolare):
    _, uid = amico("luca")
    assert titolare.post(f"/api/admin/utenti/{uid}/blocca").status_code == 200
    assert titolare.post(f"/api/admin/utenti/{uid}/sblocca").status_code == 200
    assert titolare.delete(f"/api/admin/utenti/{uid}").status_code == 200
    for tipo in ("account_bloccato", "account_sbloccato", "account_eliminato"):
        righe = eventi(tipo)
        assert len(righe) == 1, tipo
        assert righe[0]["nome"] == "luca" and righe[0]["da"] == "capo", righe[0]
    sicurezza = titolare.get("/api/admin/registro").json()["sicurezza"]
    assert {"account_bloccato", "account_sbloccato", "account_eliminato"} <= {e["tipo"] for e in sicurezza}


# ---------------------------------------------------------------- dalla riga di comando
def test_comando_chiede_conferma_con_il_nome(titolare, monkeypatch, capsys):
    luca, uid = amico("luca")
    monkeypatch.setattr("builtins.input", lambda domanda: "sara")
    with pytest.raises(SystemExit, match="Non ho fatto niente"):
        main(["utente-blocca", "luca"])
    with pytest.raises(SystemExit, match="Non ho fatto niente"):
        main(["utente-elimina", "luca"])
    assert luca.get("/api/account/me").status_code == 200 and contesto.cartella_utente(uid).is_dir()
    assert not eventi("account_bloccato") and not eventi("account_eliminato")


def test_comando_blocca_sblocca_elimina(titolare, monkeypatch, capsys):
    luca, uid = amico("luca")
    domande = []
    monkeypatch.setattr("builtins.input", lambda domanda: domande.append(domanda) or "luca")
    main(["utente-blocca", "luca"])
    assert "luca" in domande[-1]
    assert luca.get("/api/account/me").status_code == 401 and accedi("luca").status_code == 403
    assert eventi("account_bloccato")[0]["via"] == "comando"
    main(["utente-sblocca", "luca"])
    assert accedi("luca").status_code == 200 and eventi("account_sbloccato")[0]["via"] == "comando"
    main(["utente-elimina", "luca"])
    assert not contesto.cartella_utente(uid).exists() and accedi("luca").status_code == 401
    assert eventi("account_eliminato")[0]["via"] == "comando"
    assert "Fatto" in capsys.readouterr().out
    with pytest.raises(SystemExit, match="non esiste"):
        main(["utente-elimina", "luca"])


def test_comando_non_elimina_l_ultimo_amministratore(titolare, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda domanda: "capo")
    for comando in ("utente-blocca", "utente-elimina"):
        with pytest.raises(SystemExit, match="ultimo amministratore"):
            main([comando, "capo"])
    assert titolare.get("/api/account/me").status_code == 200
