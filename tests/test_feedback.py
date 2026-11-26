"""«Scrivici»: i commenti degli utenti arrivano a chi gestisce il server (decisione del proprietario, 26/11/2026).

Un utente con l'account manda un testo (al massimo 2000 caratteri, 5 al giorno); il server lo salva nel database degli account con
chi, quando, versione dell'app e piattaforma (dall'intestazione che i client mandano già) e avvisa il titolare sul suo canale con una
riga che non contiene né il testo né il nome. Lo legge solo chi gestisce il server (Gestione, e `python -m fanta feedback`).
Solo dati inventati."""
import contextlib
import json
import logging
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from fanta import __main__ as principale
from fanta import account, feedback, sentinella, server

ADESSO = datetime(2026, 11, 26, 20, 30, tzinfo=timezone.utc)
TESTO = "La pagina delle giornate\nnon si apre dopo le 22.\nGrazie!"


def utente(nome: str, ruolo: str = "utente") -> tuple[int, str]:
    """Un account con una sessione aperta (numero, token da mandare come Bearer), senza passare dalla registrazione."""
    with contextlib.closing(account.apri()) as db:
        numero = account.crea_utente(db, nome, nome.capitalize(), "impronta", "recupero", ruolo, ADESSO)
        db.commit()
        return numero, account._apri_sessione(db, numero, "prova", datetime.now(timezone.utc))


def cliente(token: str | None = None, **intestazioni) -> TestClient:
    base = {"X-Fanta": "1"} | ({"Authorization": f"Bearer {token}"} if token else {})
    return TestClient(server.app, headers=base | intestazioni)


@pytest.fixture
def avvisi(multiutente, dati_isolati, monkeypatch):
    """Gli avvisi al titolare mandati durante il test (titolo, testo): mai sulla rete vera."""
    mandati = []
    monkeypatch.setattr(feedback, "_canale", lambda: "canale-finto")
    monkeypatch.setattr(feedback, "_manda", lambda titolo, testo: mandati.append((titolo, testo)) or True)
    return mandati


# ---------------------------------------------------------------- il testo
def test_il_testo_si_pulisce_e_resta_a_capo():
    assert feedback.pulisci("  ciao\r\nseconda riga\x00\x07  ") == "ciao\nseconda riga"
    assert feedback.pulisci("à" * feedback.MAX_CARATTERI) == "à" * feedback.MAX_CARATTERI
    assert feedback.pulisci("a‮b⁦c d") == "abc\nd"          # niente testo girato al contrario; a capo Unicode = a capo


@pytest.mark.parametrize("testo", ["", "   \n\t ", "x" * (feedback.MAX_CARATTERI + 1)])
def test_vuoto_o_troppo_lungo_non_si_salva(testo):
    with pytest.raises(account.ErroreAccount) as e:
        feedback.pulisci(testo)
    assert e.value.stato == 400 and e.value.messaggio


# ---------------------------------------------------------------- salvataggio, elenco, letto
def test_salva_ed_elenco_dal_piu_recente(multiutente):
    marco, _ = utente("marco")
    with contextlib.closing(account.apri()) as db:
        primo = feedback.salva(db, marco, "primo", "web", "1.572", None, ADESSO)
        secondo = feedback.salva(db, marco, TESTO, "ios", "2.1", "formazione", ADESSO.replace(minute=45))
        elenco = feedback.elenco(db)
        assert [c["id"] for c in elenco] == [secondo, primo]
        c = elenco[0]
        assert c["testo"] == TESTO and c["utente"] == "Marco" and c["piattaforma"] == "ios" and c["versione"] == "2.1"
        assert c["schermata"] == "formazione" and c["quando"] == "2026-11-26T20:45:00+00:00" and c["letto"] is False
        assert feedback.da_leggere(db) == 2


def test_segna_letto(multiutente):
    marco, _ = utente("marco")
    with contextlib.closing(account.apri()) as db:
        numero = feedback.salva(db, marco, "ciao", None, None, None, ADESSO)
        assert feedback.segna_letto(db, numero, ADESSO) is True
        assert feedback.elenco(db)[0]["letto"] is True and feedback.da_leggere(db) == 0
        assert feedback.segna_letto(db, numero + 99, ADESSO) is False


def test_l_account_eliminato_porta_via_i_suoi_commenti(multiutente):
    """Il commento è un dato personale: con l'account se ne va anche lui (come sessioni e contatori)."""
    marco, _ = utente("marco")
    utente("capo", "amministratore")
    with contextlib.closing(account.apri()) as db:
        feedback.salva(db, marco, "ciao", None, None, None, ADESSO)
        account.elimina(db, marco)
        assert feedback.elenco(db) == []


def test_i_commenti_entrano_in_scarica_i_tuoi_dati(avvisi):
    """Portabilità: in «Scarica i tuoi dati» (`GET /api/backup`, sezione `account`) i commenti di chi chiede, mai quelli di un altro."""
    _, marco = utente("marco")
    _, anna = utente("anna")
    cliente(marco, **{"X-Schieraxi-Client": "ios"}).post("/api/feedback", json={"testo": TESTO, "versione": "2.1"})
    cliente(anna).post("/api/feedback", json={"testo": "commento di anna"})
    commenti = cliente(marco).get("/api/backup").json()["account"]["commenti"]
    assert len(commenti) == 1
    c = commenti[0]
    assert c["testo"] == TESTO and c["piattaforma"] == "ios" and c["versione"] == "2.1" and c["quando"] and c["letto"] is False
    assert set(c) == {"testo", "quando", "piattaforma", "versione", "schermata", "letto"}
    assert cliente(anna).get("/api/backup").json()["account"]["commenti"][0]["testo"] == "commento di anna"


def test_la_tabella_gia_presente_non_ferma_il_database(multiutente, tmp_path):
    """Se la tabella c'è già (creata a mano o da una prova a metà) la migrazione non deve fallire: altrimenti il database degli
    account risponderebbe 503 a tutti."""
    import sqlite3
    percorso = tmp_path / "account.sqlite"
    db = sqlite3.connect(percorso)
    for numero, voce in enumerate(account.MIGRAZIONI[:-1]):
        if callable(voce):
            voce(db)
        else:
            db.executescript(voce)
        db.execute(f"PRAGMA user_version = {numero + 1}")
    db.executescript("CREATE TABLE feedback (id INTEGER PRIMARY KEY AUTOINCREMENT, utente_id INTEGER NOT NULL REFERENCES utenti(id) "
                     "ON DELETE CASCADE, testo TEXT NOT NULL, creato TEXT NOT NULL, piattaforma TEXT, versione TEXT, schermata TEXT, "
                     "letto TEXT); CREATE INDEX feedback_utente ON feedback(utente_id);")
    db.commit()
    db.close()
    with contextlib.closing(account.apri(percorso)) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == len(account.MIGRAZIONI)


# ---------------------------------------------------------------- la rotta dell'utente
def test_serve_l_accesso(avvisi):
    assert cliente().post("/api/feedback", json={"testo": "ciao"}).status_code == 401
    assert avvisi == []


def test_senza_account_la_rotta_non_c_e(monkeypatch, dati_isolati):
    monkeypatch.delenv("FANTA_MULTIUTENTE", raising=False)
    assert cliente().post("/api/feedback", json={"testo": "ciao"}).status_code == 404


def test_invio_dall_iphone_e_lettura_del_titolare(avvisi):
    _, token = utente("marco")
    _, capo = utente("capo", "amministratore")
    r = cliente(token, **{"X-Schieraxi-Client": "ios"}).post("/api/feedback", json={"testo": TESTO, "versione": "2.1"})
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True
    elenco = cliente(capo).get("/api/admin/feedback")
    assert elenco.status_code == 200 and "no-store" in elenco.headers["cache-control"]
    corpo = elenco.json()
    assert corpo["da_leggere"] == 1
    c = corpo["commenti"][0]
    assert (c["testo"], c["utente"], c["piattaforma"], c["versione"]) == (TESTO, "Marco", "ios", "2.1")


def test_dal_browser_la_piattaforma_e_web(avvisi):
    _, token = utente("marco")
    _, capo = utente("capo", "amministratore")
    cliente(token, **{"Sec-Fetch-Mode": "cors"}).post("/api/feedback", json={"testo": "dal browser", "schermata": "impostazioni"})
    cliente(token).post("/api/feedback", json={"testo": "non si sa"})
    commenti = cliente(capo).get("/api/admin/feedback").json()["commenti"]
    assert [(c["testo"], c["piattaforma"], c["schermata"]) for c in commenti] == [("non si sa", None, None),
                                                                                  ("dal browser", "web", "impostazioni")]


def test_l_elenco_e_solo_di_chi_gestisce(avvisi):
    _, token = utente("marco")
    cliente(token).post("/api/feedback", json={"testo": "ciao"})
    assert cliente(token).get("/api/admin/feedback").status_code == 403
    assert cliente(token).post("/api/admin/feedback/1/letto").status_code == 403
    assert cliente().get("/api/admin/feedback").status_code == 401


def test_da_leggere_conta_quelli_mostrati_e_torna_a_zero(avvisi):
    """L'elenco mostra gli ultimi 100: «da leggere» conta quelli, così segnandoli tutti letti torna a zero anche con più commenti."""
    marco, _ = utente("marco")
    _, capo = utente("capo", "amministratore")
    with contextlib.closing(account.apri()) as db:
        for i in range(feedback.MAX_ELENCO + 1):
            feedback.salva(db, marco, f"commento {i}", None, None, None, ADESSO.replace(minute=i % 60, second=i // 60))
    c = cliente(capo)
    corpo = c.get("/api/admin/feedback").json()
    assert len(corpo["commenti"]) == feedback.MAX_ELENCO and corpo["da_leggere"] == feedback.MAX_ELENCO
    for commento in corpo["commenti"]:
        assert c.post(f"/api/admin/feedback/{commento['id']}/letto").status_code == 200
    assert c.get("/api/admin/feedback").json()["da_leggere"] == 0


def test_segna_letto_dalla_gestione(avvisi):
    _, token = utente("marco")
    _, capo = utente("capo", "amministratore")
    cliente(token).post("/api/feedback", json={"testo": "ciao"})
    numero = cliente(capo).get("/api/admin/feedback").json()["commenti"][0]["id"]
    assert cliente(capo).post(f"/api/admin/feedback/{numero}/letto").json() == {"ok": True}
    corpo = cliente(capo).get("/api/admin/feedback").json()
    assert corpo["commenti"][0]["letto"] is True and corpo["da_leggere"] == 0
    assert cliente(capo).post(f"/api/admin/feedback/{numero + 50}/letto").status_code == 404


def test_cinque_al_giorno(avvisi):
    _, token = utente("marco")
    c = cliente(token)
    for i in range(feedback.MAX_AL_GIORNO):
        assert c.post("/api/feedback", json={"testo": f"commento {i}"}).status_code == 200
    troppi = c.post("/api/feedback", json={"testo": "uno di troppo"})
    assert troppi.status_code == 429 and int(troppi.headers["retry-after"]) >= 1
    assert "commenti" in troppi.json()["detail"]
    with contextlib.closing(account.apri()) as db:
        assert "uno di troppo" not in [x["testo"] for x in feedback.elenco(db)]


def test_un_testo_sbagliato_non_consuma_il_tetto(avvisi):
    _, token = utente("marco")
    c = cliente(token)
    assert c.post("/api/feedback", json={"testo": "   "}).status_code == 400
    assert c.post("/api/feedback", json={"testo": "x" * (feedback.MAX_CARATTERI + 1)}).status_code == 400
    for i in range(feedback.MAX_AL_GIORNO):
        assert c.post("/api/feedback", json={"testo": f"commento {i}"}).status_code == 200


def test_corpo_enorme_rifiutato_prima(avvisi):
    _, token = utente("marco")
    r = cliente(token).post("/api/feedback", content=b'{"testo": "' + b"x" * 40_000 + b'"}',
                            headers={"Content-Type": "application/json"})
    assert r.status_code == 413


# ---------------------------------------------------------------- l'avviso al titolare
def test_avviso_al_titolare_senza_testo_ne_nome(avvisi):
    _, token = utente("marco")
    cliente(token).post("/api/feedback", json={"testo": "Un segreto da non far girare"})
    assert len(avvisi) == 1
    titolo, testo = avvisi[0]
    assert "commento" in titolo.lower() and "Gestione" in testo
    assert "sulla web" in testo                                       # sull'iPhone l'elenco dei commenti non c'è
    assert "segreto" not in titolo + testo and "marco" not in (titolo + testo).lower()


def test_al_massimo_sei_avvisi_all_ora_per_tutto_il_server(avvisi, multiutente):
    """Con la registrazione aperta chiunque può scrivere: oltre MAX_AVVISI_ORA avvisi in un'ora (per tutto il server) i commenti
    si salvano ma l'avviso non parte; passata l'ora riparte."""
    _, capo = utente("capo", "amministratore")                        # chi gestisce non ha il tetto dei 5 al giorno
    c = cliente(capo)
    for i in range(7):
        assert c.post("/api/feedback", json={"testo": f"commento {i}"}).status_code == 200
    assert len(avvisi) == 6
    with contextlib.closing(account.apri()) as db:
        assert len(feedback.elenco(db)) == 7                          # salvati tutti
    multiutente.t += 3601
    assert c.post("/api/feedback", json={"testo": "un'ora dopo"}).status_code == 200
    assert len(avvisi) == 7


def test_il_testo_non_finisce_nel_registro(avvisi, caplog):
    _, token = utente("marco")
    with caplog.at_level(logging.DEBUG):
        cliente(token).post("/api/feedback", json={"testo": "Frase privatissima"})
    assert "privatissima" not in caplog.text


def test_avviso_non_partito_si_vede_nel_registro(multiutente, dati_isolati, monkeypatch, caplog):
    """Canale configurato ma ntfy non risponde: il commento resta salvato e il guasto si legge nel registro (senza il testo)."""
    monkeypatch.setattr(feedback, "_manda", lambda titolo, testo: False)
    monkeypatch.setattr(feedback, "_canale", lambda: "canale-finto")
    _, token = utente("marco")
    with caplog.at_level(logging.WARNING):
        assert cliente(token).post("/api/feedback", json={"testo": "ciao"}).status_code == 200
    assert "avviso" in caplog.text.lower() and "ciao" not in caplog.text


def test_senza_canale_niente_avviso(multiutente, dati_isolati, monkeypatch):
    """Sul PC e nell'ambiente di prova il canale non c'è: il commento si salva e non si prova nemmeno a mandare."""
    mandati = []
    monkeypatch.setattr(feedback, "_canale", lambda: None)
    monkeypatch.setattr(feedback, "_manda", lambda titolo, testo: mandati.append(titolo) or True)
    _, token = utente("marco")
    assert cliente(token).post("/api/feedback", json={"testo": "ciao"}).status_code == 200
    assert mandati == []


def test_l_avviso_va_sul_canale_del_titolare_con_priorita_normale(monkeypatch, tmp_path):
    """Lo stesso canale della sentinella e degli script del server, ma senza la priorità alta di un guasto."""
    canale = tmp_path / "canale"
    canale.write_text("canale-finto\n", encoding="utf-8")
    monkeypatch.setenv("SCHIERAXI_CANALE", str(canale))
    corpi = []

    class Risposta:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(sentinella.urllib.request, "urlopen", lambda r, timeout: corpi.append(json.loads(r.data)) or Risposta())
    assert feedback._canale() == "canale-finto"
    assert feedback._manda("SchieraXI · un commento nuovo", "riga") is True
    assert corpi[0]["topic"] == "canale-finto" and corpi[0]["priority"] == 3 and corpi[0]["tags"] == ["speech_balloon"]
    assert sentinella.manda_ntfy("guasto", "riga") is True
    assert corpi[1]["priority"] == 4 and corpi[1]["tags"] == ["mag"]          # la sentinella resta com'era


# ---------------------------------------------------------------- il comando per il coordinatore
def test_comando_ultimi(multiutente, capsys):
    marco, _ = utente("marco")
    with contextlib.closing(account.apri()) as db:
        feedback.salva(db, marco, "il più vecchio", "web", "1.570", None, ADESSO)
        feedback.salva(db, marco, "di mezzo", "web", "1.571", None, ADESSO.replace(minute=40))
        feedback.salva(db, marco, TESTO, "ios", "2.1", None, ADESSO.replace(minute=50))
    principale.main(["feedback", "--ultimi", "2"])
    uscita = capsys.readouterr().out
    assert TESTO.split("\n")[1] in uscita and "di mezzo" in uscita and "il più vecchio" not in uscita
    assert uscita.index("Grazie!") < uscita.index("di mezzo")              # il più recente in alto
    assert "Marco" in uscita and "iPhone" in uscita and "21:50" in uscita     # ora italiana
