"""Isolamento fra utenti: l'utente A non legge né scrive niente di B (e viceversa), su OGNI rotta che tocca dati personali.

Come funziona: si scoprono da soli tutti i percorsi dell'app che usano `lega_corrente` (i dati personali) e il test li vuole
tutti classificati, così una rotta nuova obbliga a decidere. Poi A e B fanno le stesse cose con dati diversi (ognuno con il suo
marchio, «A» o «B»): si controlla che le risposte di uno non contengano niente dell'altro, che i file di A non cambino mentre
lavora B e che nessun file personale finisca nella posizione "di sempre"."""
import contextlib
import hashlib
import json
import re
import sqlite3
from dataclasses import asdict
from pathlib import Path

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from fanta import account, contesto, server
from fanta.regole import Regole

from test_account_http import _tutte_le_rotte, cliente

PASSWORD = "una-password-lunga-9"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 24


# ---------------------------------------------------------------- le rotte
def rotte_personali() -> set[tuple[str, str]]:
    trovate = set()
    for prefisso, r in _tutte_le_rotte(server.app.routes):
        if isinstance(r, APIRoute) and any(d.call is server.lega_corrente for d in r.dependant.dependencies):
            trovate |= {(m, prefisso + r.path) for m in r.methods - {"HEAD", "OPTIONS"}}
    return trovate


def tutte_le_rotte_api() -> set[tuple[str, str]]:
    return {(m, prefisso + r.path) for prefisso, r in _tutte_le_rotte(server.app.routes)
            if isinstance(r, APIRoute) and (prefisso + r.path).startswith("/api/") for m in r.methods - {"HEAD", "OPTIONS"}}


# le rotte che NON toccano dati personali: dati comuni a tutti, riservate all'amministratore, o degli account
NON_PERSONALI = {
    ("GET", "/api/novita"), ("GET", "/api/salute"), ("GET", "/api/live"), ("GET", "/api/stato-dati"), ("GET", "/api/aggiorna"), ("POST", "/api/aggiorna"),
    ("GET", "/api/giocatori"), ("GET", "/api/avatar"),
    ("GET", "/api/push/chiave"), ("POST", "/api/regole/riconosci"),
    ("GET", "/api/account/me"), ("POST", "/api/account/registra"), ("POST", "/api/account/accedi"), ("POST", "/api/account/esci"),
    ("POST", "/api/account/esci-da-tutti"), ("POST", "/api/account/cambia-password"), ("POST", "/api/account/codice-recupero"),
    ("POST", "/api/account/elimina"), ("POST", "/api/account/recupero"), ("PUT", "/api/account/nome"),
    ("POST", "/api/account/token-widget"), ("GET", "/api/account/token-widget"), ("DELETE", "/api/account/token-widget"),
    ("POST", "/api/account/email"), ("POST", "/api/account/email/conferma"), ("POST", "/api/account/email/togli"),
    ("POST", "/api/account/recupero-email"), ("POST", "/api/account/recupero-email/conferma"), ("POST", "/api/account/registra/conferma"),
    ("POST", "/api/admin/inviti"), ("GET", "/api/admin/inviti"), ("DELETE", "/api/admin/inviti/{invito_id}"), ("POST", "/api/admin/utenti/{utente_id}/rose"), ("GET", "/api/admin/utenti"), ("GET", "/api/admin/registro"), ("GET", "/api/admin/fonti"), ("PUT", "/api/admin/fonti"), ("POST", "/api/admin/reset-password"),
    ("GET", "/api/admin/funzioni"), ("PUT", "/api/admin/funzioni"),
    # accesso con Google: parlano solo di account e identità, nessun dato della lega
    ("POST", "/api/account/social/google/inizia"), ("GET", "/api/account/social/google/ritorno"), ("POST", "/api/account/social/scambio"),
    ("POST", "/api/account/social/completa"), ("GET", "/api/account/social/accessi"), ("DELETE", "/api/account/social/{provider}"),
    ("POST", "/api/account/imposta-password"),
}


# le rotte delle foto (dati comuni) esistono solo nelle copie private: la versione pubblica non ha fanta/rotte_foto.py
if (RADICE_PROVE := Path(__file__).resolve().parent.parent / "fanta" / "rotte_foto.py").exists():
    NON_PERSONALI |= {("GET", "/api/foto-disponibili"), ("GET", "/api/foto/{calciatore_id}")}


def test_ogni_rotta_e_classificata():
    """Una rotta nuova deve dichiarare se tocca dati personali (e allora usa lega_corrente ed entra nelle prove qui sotto)."""
    personali = rotte_personali()
    assert personali.isdisjoint(NON_PERSONALI)
    assert tutte_le_rotte_api() == personali | NON_PERSONALI, tutte_le_rotte_api() ^ (personali | NON_PERSONALI)
    assert len(personali) > 40


# ---------------------------------------------------------------- le prove: (metodo, rotta, cosa mandare); m = «A» o «B»
def dati_di(m: str) -> dict:
    a = m == "A"
    regole = asdict(Regole())
    regole["nome_lega"] = f"LEGA-DI-{m}"
    return {
        "regole": regole,
        "rose": f"Real Esempio {m}\nP\tSommer\t10\nD\tBastoni\t15\nAltra {m}\nA\tKean\t30\n",
        "crediti": {f"Real Esempio {m}": 11 if a else 22},
        "osservato": 5 if a else 6,
        "titolari": [1, 2, 3] if a else [4, 5, 6],
        "cambi": not a,
        "icona": "viola" if a else "rosso",
        "stemma": PNG + m.encode() * 8,
        "push": {"endpoint": f"https://web.push.example/{m}", "keys": {"p256dh": "P" * 40, "auth": "A" * 20}},
    }


def scritture(m: str):
    """Tutto ciò che un utente può scrivere, nell'ordine giusto."""
    d = dati_di(m)
    nome = f"Real Esempio {m}"
    return [
        ("PUT", "/api/regole", dict(json=d["regole"])),
        ("PUT", "/api/regole/rinvio", dict(json={"giornata": 9 if m == "A" else 10, "modo": "voto_ufficio"})),
        ("POST", "/api/rose/testo", dict(json={"testo": d["rose"]})),
        ("PUT", "/api/mia-squadra", dict(json={"nome": nome})),
        ("PUT", "/api/squadre/nome", dict(json={"nome": nome, "nuovo": nome})),
        ("PUT", "/api/crediti", dict(json={"crediti": d["crediti"]})),
        ("PUT", "/api/osservati/{i}", dict(i=d["osservato"])),
        ("DELETE", "/api/osservati/{i}", dict(i=99)),
        ("POST", "/api/formazione/valuta", dict(json={"titolari": d["titolari"], "giornata": 9, "salva": True})),
        ("POST", "/api/diario/schierata", dict(json={"giornata": 9, "tipo": "consigliata"})),          # giornata non finita: 400, ma la rotta è personale e coperta qui
        ("DELETE", "/api/scelta", dict(params={"giornata": 8})),
        ("PUT", "/api/avvisi", dict(json={"cambi": d["cambi"]})),
        ("POST", "/api/avvisi/prova", dict()),
        ("PUT", "/api/icona", dict(json={"nome": d["icona"]})),
        ("POST", "/api/squadre/immagine", dict(params={"squadra": nome, "tipo": "stemma"}, files={"file": ("s.png", d["stemma"], "image/png")})),
        ("POST", "/api/push/iscrivi", dict(json=d["push"])),
        ("POST", "/api/push/disiscrivi", dict(json={"endpoint": "https://web.push.example/mai-iscritto"})),
        ("POST", "/api/rose/file", dict(files={"file": ("rose.txt", d["rose"].encode(), "text/plain")})),
        ("PUT", "/api/onboarding", dict(json={"passo": "rose" if m == "A" else "squadra", "stato": "in_corso"})),
        ("PUT", "/api/primo-avvio", dict(json={"saltati": ["widget" if m == "A" else "stemma"]})),
        ("PUT", "/api/funzioni", dict(json={"mostra_tutte": m == "A"})),
    ]


def letture(m: str):
    nome = f"Real Esempio {m}"
    return [
        ("GET", "/api/stato", {}), ("GET", "/api/formazione", {}), ("GET", "/api/scelta", dict(params={"giornata": 9})),
        ("GET", "/api/osservati", {}), ("GET", "/api/affidabilita", {}), ("GET", "/api/sotto-il-cofano", {}), ("GET", "/api/diario", {}), ("GET", "/api/stagione", {}),
        ("GET", "/api/asta", {}), ("GET", "/api/formazione/testo", {}), ("GET", "/api/confronto", dict(params={"a": 1, "b": 2})),
        ("GET", "/api/oggi", {}), ("GET", "/api/widget", {}), ("GET", "/api/calendario", {}), ("GET", "/api/mercato", {}), ("GET", "/api/classifica", {}),
        ("GET", "/api/giocatore/{calciatore_id}", dict(calciatore_id=2)), ("GET", "/api/scambi/proposte", {}), ("GET", "/api/scambi/limite", {}),
        ("GET", "/api/scambi/analizza", dict(params={"con": "x", "do": "1", "ricevo": "2"})),
        ("POST", "/api/scambi/da-testo", dict(json={"testo": f"ti do Sommer per Kean {m}"})),
        ("GET", "/api/squadre", {}), ("GET", "/api/squadre/immagine", dict(params={"squadra": nome, "tipo": "stemma"})),
        ("GET", "/api/rosa", {}), ("GET", "/api/avvisi", {}), ("GET", "/api/movimenti", {}), ("GET", "/api/regole", {}),
        ("GET", "/api/backup", {}), ("GET", "/api/icona", {}),
        ("GET", "/api/onboarding", {}), ("GET", "/api/onboarding/controlli", {}), ("GET", "/api/primo-avvio", {}), ("GET", "/api/funzioni", {}),
        ("POST", "/api/onboarding/regole", dict(json={"testo": f"Assist {2 if m == 'A' else 3}"})),
        # l'anteprima delle rose non salva niente: confronta solo con le rose di chi chiede (mai con quelle dell'altro)
        ("POST", "/api/rose/anteprima", dict(json={"testo": f"Real Esempio {m}\nP\tSommer\t10\nNuova {m}\nA\tKean\t30\n"})),
        ("POST", "/api/rose/anteprima/file", dict(files={"file": ("rose.txt", f"Real Esempio {m}\nD\tBastoni\t5\n".encode(), "text/plain")})),
    ]


def esegui(c: TestClient, metodo: str, rotta: str, argomenti: dict):
    argomenti = dict(argomenti)
    segnaposto = {k: argomenti.pop(k) for k in list(argomenti) if "{" + k + "}" in rotta}
    percorso = rotta.format(**segnaposto)
    return c.request(metodo, percorso, **argomenti)


def albero(cartella: Path) -> dict[str, str]:
    """Ogni file della cartella con la sua impronta."""
    return {str(p.relative_to(cartella)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(cartella.rglob("*")) if p.is_file()}


@pytest.fixture
def due(multiutente, dati_isolati, listone_in_archivio, calciatori, monkeypatch):
    """Due utenti registrati, ognuno con il suo dispositivo (cookie), e un po' di finti per non toccare la rete e il calcolo."""
    monkeypatch.setattr(server.listone, "carica", lambda *a, **k: (calciatori, "oggi"))
    monkeypatch.setattr(server.consigli, "stagione_corrente", lambda: "2026-27")
    monkeypatch.setattr(server.consigli, "valuta", lambda db, regole, rose, titolari, squadra=None, giornata=None, simulazioni=600:
                        {"modulo": "4-3-3", "giornata": 9, "punteggio_atteso": 70.0, "dev": 4.0, "panchina": [], "differenza": -1.0})
    # il calcolo della formazione, che vuole il calendario vero, è sostituito da uno che dice solo di chi è la rosa
    monkeypatch.setattr(server.consigli, "formazione", lambda db, regole, rose, *a, **k: {
        "squadra": rose.mia_squadra, "lega": regole.nome_lega, "giornata": 9, "modulo": "4-3-3",
        "moduli": [{"modulo": "4-3-3", "titolari": [], "panchina": []}]})
    monkeypatch.setattr(server.consigli, "testo_formazione", lambda f, *a, **k: f"formazione di {f['squadra']} ({f['lega']})")
    clienti = {}
    for m in "AB":
        with contextlib.closing(account.apri()) as db:
            inv = account.crea_invito(db, f"utente {m}")
        c = cliente()
        r = c.post("/api/account/registra", json={"nome_utente": f"utente{m.lower()}", "password": PASSWORD, "invito": inv})
        assert r.status_code == 200, r.text
        clienti[m] = (c, r.json()["utente"]["id"])
    return clienti


def cartella_di(due, m: str) -> Path:
    return contesto.cartella_utente(due[m][1])


def esegui_tutto(c, voci, atteso_ok=False) -> dict[tuple[str, str], object]:
    risposte = {}
    for metodo, rotta, arg in voci:
        r = esegui(c, metodo, rotta, arg)
        assert r.status_code < 500, (metodo, rotta, r.status_code, r.text[:300])
        if atteso_ok:
            assert r.status_code in (200, 409), (metodo, rotta, r.status_code, r.text[:300])
        risposte[(metodo, rotta)] = r
    return risposte


def tutto_il_testo(risposte) -> str:
    return " ".join(r.text if "image" not in r.headers.get("content-type", "") else r.content.decode("latin1") for r in risposte.values())


def test_a_e_b_non_si_vedono(due, dati_isolati):
    (ca, _), (cb, _) = due["A"], due["B"]
    prove = {(m, r) for m, r, _ in scritture("A") + letture("A")}
    # ogni rotta personale è provata qui o nei test sotto (ripristino del backup, nuova stagione)
    assert rotte_personali() <= prove | {("POST", "/api/backup/ripristina"), ("POST", "/api/nuova-stagione"),
                                                                ("POST", "/api/onboarding/demo"), ("DELETE", "/api/onboarding/demo"), ("POST", "/api/rose/correggi"),
                                                                ("POST", "/api/squadre/immagine/da-url"), ("DELETE", "/api/squadre/immagine"),
                                                                ("GET", "/api/squadre/immagine/in-attesa"), ("DELETE", "/api/squadre/immagine/in-attesa"),
                                                                ("POST", "/api/squadre/immagine/condivisa")}, rotte_personali() - prove

    # 1. A lavora: scrive e rilegge
    esegui_tutto(ca, scritture("A"))
    risposte_a = esegui_tutto(ca, letture("A"))
    assert risposte_a[("GET", "/api/regole")].json()["nome_lega"] == "LEGA-DI-A"
    assert [k.split("/")[1] for k in risposte_a[("GET", "/api/regole")].json()["rinvii_giornate"]] == ["9"]
    assert [s["nome"] for s in risposte_a[("GET", "/api/squadre")].json()] == ["Real Esempio A", "Altra A"]
    assert risposte_a[("GET", "/api/scelta")].json()["titolari"] == [1, 2, 3]
    assert risposte_a[("GET", "/api/icona")].json()["scelta"] == "viola"
    assert risposte_a[("GET", "/api/primo-avvio")].json()["primo_avvio"]["saltati"] == ["widget"]
    assert risposte_a[("GET", "/api/funzioni")].json()["mostra_tutte"] is True
    assert risposte_a[("GET", "/api/avvisi")].json()["impostazioni"]["cambi"] is False
    assert risposte_a[("GET", "/api/avvisi")].json()["dispositivi"] == 1
    assert risposte_a[("GET", "/api/formazione")].json()["squadra"] == "Real Esempio A"
    assert risposte_a[("GET", "/api/formazione/testo")].text == "formazione di Real Esempio A (LEGA-DI-A)"
    assert risposte_a[("GET", "/api/squadre/immagine")].content == dati_di("A")["stemma"]
    anteprima_a = risposte_a[("POST", "/api/rose/anteprima")].json()
    assert [s["nuova"] for s in anteprima_a["squadre"]] == [False, True] and anteprima_a["totale_squadre"] == 3   # confronta con le SUE rose
    assert "Real Esempio A" in risposte_a[("GET", "/api/backup")].text
    prima = albero(cartella_di(due, "A"))
    assert {"regole.json", "rose.json", "scelte.json", "osservati.json", "avvisi-impostazioni.json", "icona.json", "push.json"} <= set(prima)

    # 2. B, che non ha ancora fatto niente, non vede nulla di A
    vuote = esegui_tutto(cb, letture("B"))
    assert not re.search(r"Real Esempio A|Altra A|LEGA-DI-A|web\.push\.example/A", tutto_il_testo(vuote)), tutto_il_testo(vuote)[:300]
    assert vuote[("GET", "/api/squadre")].status_code == 409                      # nessuna rosa: non quelle di A
    assert vuote[("GET", "/api/rosa")].status_code == 409
    assert vuote[("GET", "/api/formazione")].status_code == 409
    assert vuote[("GET", "/api/scelta")].json() is None
    assert vuote[("GET", "/api/regole")].json()["nome_lega"] != "LEGA-DI-A"
    assert vuote[("GET", "/api/icona")].json()["scelta"] == "verde"
    assert vuote[("GET", "/api/primo-avvio")].json()["primo_avvio"] is None
    assert vuote[("GET", "/api/funzioni")].json()["mostra_tutte"] is False
    assert vuote[("GET", "/api/avvisi")].json()["dispositivi"] == 0
    assert vuote[("GET", "/api/squadre/immagine")].status_code == 409
    assert "Real Esempio A" not in vuote[("GET", "/api/backup")].text
    anteprima_b = vuote[("POST", "/api/rose/anteprima")].json()
    assert anteprima_b["differenze"]["prima_importazione"] is True and anteprima_b["totale_squadre"] == 2   # le rose di A non contano
    assert not (cartella_di(due, "B") / "rose.json").exists()                     # l'anteprima non ha salvato niente
    assert albero(cartella_di(due, "A")) == prima                                 # B ha solo letto: i file di A sono quelli di prima

    # 3. B scrive le sue cose (con gli stessi nomi di squadra come caso peggiore) e A non cambia
    esegui_tutto(cb, scritture("B"))
    assert albero(cartella_di(due, "A")) == prima
    risposte_b = esegui_tutto(cb, letture("B"))
    assert not re.search(r"Real Esempio A|Altra A|LEGA-DI-A|web\.push\.example/A", tutto_il_testo(risposte_b))
    assert risposte_b[("GET", "/api/regole")].json()["nome_lega"] == "LEGA-DI-B"
    assert [k.split("/")[1] for k in risposte_b[("GET", "/api/regole")].json()["rinvii_giornate"]] == ["10"]     # non vede la 9 di A
    assert [s["nome"] for s in risposte_b[("GET", "/api/squadre")].json()] == ["Real Esempio B", "Altra B"]
    assert risposte_b[("GET", "/api/scelta")].json()["titolari"] == [4, 5, 6]
    assert risposte_b[("GET", "/api/icona")].json()["scelta"] == "rosso"
    assert risposte_b[("GET", "/api/primo-avvio")].json()["primo_avvio"]["saltati"] == ["stemma"]
    assert risposte_b[("GET", "/api/formazione")].json()["lega"] == "LEGA-DI-B"
    assert risposte_b[("GET", "/api/squadre/immagine")].content == dati_di("B")["stemma"]

    # 4. A rilegge: niente di B, tutto come prima
    ancora_a = esegui_tutto(ca, letture("A"))
    assert not re.search(r"Real Esempio B|Altra B|LEGA-DI-B|web\.push\.example/B", tutto_il_testo(ancora_a))
    assert albero(cartella_di(due, "A")) == prima
    for nome, impronta in albero(cartella_di(due, "B")).items():                   # e viceversa: i file di B non sono quelli di A
        if nome.endswith(".lock"):                 # file di blocco (blocco.BloccoFile, per esempio push.json.lock): vuoti, senza dati
            assert (cartella_di(due, "B") / nome).stat().st_size == 0, nome
            continue
        assert nome not in prima or prima[nome] != impronta, nome

    # 5. nessun file personale è finito nelle posizioni "di sempre" (lega/, dati/ della radice)
    assert [p for p in dati_isolati.rglob("*") if p.is_file()] == []


def test_il_backup_si_ripristina_solo_nei_propri_file(due, dati_isolati):
    (ca, _), (cb, _) = due["A"], due["B"]
    esegui_tutto(ca, scritture("A"))
    esegui_tutto(cb, scritture("B"))
    prima_a = albero(cartella_di(due, "A"))
    copia_b = cb.get("/api/backup").json()
    assert "Real Esempio B" in json.dumps(copia_b) and "Real Esempio A" not in json.dumps(copia_b)
    # B modifica le regole e poi ripristina la sua copia: torna come prima, A non si accorge di niente
    cb.put("/api/regole", json=dati_di("A")["regole"])
    r = cb.post("/api/backup/ripristina", json=copia_b)
    assert r.status_code == 200 and "lega/regole.json" in r.json()["ripristinati"]
    assert cb.get("/api/regole").json()["nome_lega"] == "LEGA-DI-B"
    assert albero(cartella_di(due, "A")) == prima_a
    assert (cartella_di(due, "B") / "backup-prima-del-ripristino.json").exists()
    assert [p for p in dati_isolati.rglob("*") if p.is_file()] == []


def test_scarica_i_tuoi_dati_solo_i_propri(due):
    """«Scarica i tuoi dati» (Impostazioni > Il tuo account): il file ha solo i dati di chi lo chiede; un altro o chi non è dentro no."""
    (ca, _), (cb, _) = due["A"], due["B"]
    esegui_tutto(ca, scritture("A"))
    esegui_tutto(cb, scritture("B"))
    r = ca.get("/api/backup")
    assert r.status_code == 200 and r.headers["content-disposition"].startswith("attachment;")
    file_a = r.json()
    assert set(file_a) >= {"formato", "versione", "creato", "file"}
    assert set(file_a["file"]) <= set(contesto.NOMI_BACKUP.values()) and "lega/rose.json" in file_a["file"]
    testo_a = json.dumps(file_a, ensure_ascii=False)
    assert "Real Esempio A" in testo_a and "Real Esempio B" not in testo_a and "LEGA-DI-B" not in testo_a
    assert "web.push.example" not in testo_a                                            # niente iscrizioni alle notifiche
    # la sezione account: solo i dati di A, separata dai file della lega
    acc = file_a["account"]
    assert acc["nome_utente"] == "utentea" and acc["nome_visualizzato"] == "utentea" and acc["ruolo"] == "utente"
    assert acc["email"] is None and acc["email_verificata"] is False and acc["creato"] and acc["accessi_collegati"] == []
    assert set(acc["termini"]) == {"accettati", "versione"} and acc["impostazioni"]["mostra_tutte_le_funzioni"] is True
    assert "utenteb" not in testo_a
    # niente segreti: né nei nomi dei campi né nei valori
    minuscolo = testo_a.lower()
    for vietata in ("hash", "token", "sessione", "segreto", "soggetto", "indirizz", "recupero", PASSWORD):
        assert vietata not in minuscolo, vietata
    testo_b = cb.get("/api/backup").text
    assert "Real Esempio B" in testo_b and "Real Esempio A" not in testo_b and "LEGA-DI-A" not in testo_b and "utentea" not in testo_b
    assert json.loads(testo_b)["account"]["nome_utente"] == "utenteb"
    assert cliente().get("/api/backup").status_code == 401                             # senza sessione: niente


def test_dati_account_con_email_google_e_termini(due):
    """Email confermata, Google collegato (solo servizio ed email, mai l'identificativo) e termini accettati finiscono nel file."""
    (ca, id_a), (_, id_b) = due["A"], due["B"]
    with contextlib.closing(account.apri()) as db:
        db.execute("UPDATE utenti SET email = 'a@example.com', termini_accettati = '2026-10-31T10:00:00', termini_versione = '3' WHERE id = ?", (id_a,))
        db.execute("INSERT INTO identita_esterne (utente_id, provider, soggetto, email, email_verificata, creata) "
                   "VALUES (?, 'google', 'SOGGETTO-SEGRETO-123', 'a@posta.example', 1, '2026-10-30T09:00:00')", (id_a,))
        db.execute("INSERT INTO identita_esterne (utente_id, provider, soggetto, email, email_verificata, creata) "
                   "VALUES (?, 'google', 'SOGGETTO-B', 'b@posta.example', 1, '2026-10-30T09:00:00')", (id_b,))
        db.commit()
    r = ca.get("/api/backup")
    acc = r.json()["account"]
    assert acc["email"] == "a@example.com" and acc["email_verificata"] is True
    assert acc["accessi_collegati"] == [{"servizio": "google", "email": "a@posta.example", "collegato": "2026-10-30T09:00:00"}]
    assert acc["termini"] == {"accettati": "2026-10-31T10:00:00", "versione": "3"}
    assert "SOGGETTO" not in r.text and "b@posta.example" not in r.text


def test_scarica_i_tuoi_dati_intestazioni_e_amministratore(due):
    """Il file non resta in nessuna copia (no-store) e si scarica come allegato; anche l'amministratore riceve solo i suoi dati."""
    (ca, id_a), (cb, _) = due["A"], due["B"]
    esegui_tutto(ca, scritture("A"))
    esegui_tutto(cb, scritture("B"))
    with contextlib.closing(account.apri()) as db:
        db.execute("UPDATE utenti SET ruolo = 'amministratore' WHERE id = ?", (id_a,))
        db.commit()
    r = ca.get("/api/backup")
    assert r.status_code == 200
    assert "no-store" in r.headers["cache-control"] and r.headers["content-disposition"].startswith("attachment;")
    assert r.json()["account"]["ruolo"] == "amministratore" and r.json()["account"]["nome_utente"] == "utentea"
    assert "utenteb" not in r.text and "Real Esempio B" not in r.text and "LEGA-DI-B" not in r.text


def test_scarica_i_tuoi_dati_senza_database_degli_account(due, monkeypatch):
    """Se il database degli account non si legge, esce il file della lega senza la sezione `account` (niente errore 500)."""
    (ca, _), _ = due["A"], due["B"]
    esegui_tutto(ca, scritture("A"))
    def rotto(*a, **k):
        raise sqlite3.OperationalError("database rovinato")
    monkeypatch.setattr(account, "esporta", rotto)
    r = ca.get("/api/backup")
    assert r.status_code == 200 and "account" not in r.json() and "Real Esempio A" in r.text


def test_il_ripristino_ignora_la_sezione_account(due):
    """Un file modificato a mano non può cambiare l'account: nome, ruolo ed email restano quelli di prima."""
    (ca, _), _ = due["A"], due["B"]
    esegui_tutto(ca, scritture("A"))
    copia = ca.get("/api/backup").json()
    copia["account"] |= {"nome_utente": "utenteb", "ruolo": "amministratore", "email": "x@example.com", "nome_visualizzato": "Capo"}
    r = ca.post("/api/backup/ripristina", json=copia)
    assert r.status_code == 200 and all(n.startswith(("lega/", "dati/")) for n in r.json()["ripristinati"])
    me = ca.get("/api/account/me").json()["utente"]
    assert me["nome_utente"] == "utentea" and me["ruolo"] == "utente" and me["nome_visualizzato"] == "utentea"
    assert ca.get("/api/backup").json()["account"]["email"] is None


def test_la_cartella_non_si_sceglie_con_i_parametri(due):
    """Nessun parametro, intestazione o nome può far leggere o scrivere i file di un altro."""
    (ca, id_a), (cb, _) = due["A"], due["B"]
    esegui_tutto(ca, scritture("A"))
    prima = albero(cartella_di(due, "A"))
    furbi = {"utente": id_a, "utente_id": id_a, "id": id_a, "user": id_a, "cartella": f"../{id_a}", "lega": id_a}
    for percorso in ("/api/squadre", "/api/regole", "/api/scelta", "/api/icona", "/api/avvisi", "/api/backup", "/api/rosa"):
        r = cb.get(percorso, params=furbi | ({"giornata": 9} if "scelta" in percorso else {}),
                   headers={"X-Utente": str(id_a), "X-Fanta-Utente": str(id_a)})
        assert "Real Esempio A" not in r.text and "LEGA-DI-A" not in r.text, percorso
    # nomi di squadra pensati per uscire dalla cartella
    esegui_tutto(cb, scritture("B"))
    for sq in ("../../utenti/%d/rose" % id_a, "..\\..\\x", "../" * 6 + "etc/passwd", "real esempio a"):
        for tipo in ("stemma", "maglia"):
            assert cb.get("/api/squadre/immagine", params={"squadra": sq, "tipo": tipo}).status_code in (404, 400)
        assert cb.post("/api/squadre/immagine", params={"squadra": sq, "tipo": "stemma"},
                       files={"file": ("s.png", PNG, "image/png")}).status_code == 404
    assert albero(cartella_di(due, "A")) == prima


def test_chi_non_e_registrato_non_ha_cartella(due, tmp_path):
    """Una sessione finta, scaduta o revocata non arriva a nessuna cartella (e non ne crea)."""
    anonimo = cliente()
    for r in (anonimo.get("/api/squadre"), anonimo.get("/api/regole", headers={"Authorization": "Bearer inventato"}),
              anonimo.put("/api/osservati/5")):
        assert r.status_code == 401
    assert not (cartella_di(due, "A").parent / "0").exists()
    ca, _ = due["A"]
    ca.post("/api/account/esci")
    assert ca.get("/api/regole").status_code == 401


def test_eliminare_l_account_cancella_solo_i_suoi_dati(due, dati_isolati):
    (ca, _), (cb, _) = due["A"], due["B"]
    esegui_tutto(ca, scritture("A"))
    esegui_tutto(cb, scritture("B"))
    prima_b = albero(cartella_di(due, "B"))
    assert ca.post("/api/account/elimina", json={"password": "sbagliata-sbagliata"}).status_code == 403
    assert cartella_di(due, "A").exists()
    assert ca.post("/api/account/elimina", json={"password": PASSWORD}).status_code == 200
    assert not cartella_di(due, "A").exists()
    assert ca.get("/api/account/me").status_code == 401                              # e la sessione non vale più
    assert albero(cartella_di(due, "B")) == prima_b and cb.get("/api/account/me").status_code == 200
    nuovo = cliente()
    assert nuovo.post("/api/account/accedi", json={"nome_utente": "utentea", "password": PASSWORD}).status_code == 401


def test_nuova_stagione_archivia_nella_cartella_dell_utente(due, dati_isolati):
    (ca, _), (cb, _) = due["A"], due["B"]
    esegui_tutto(ca, scritture("A"))
    esegui_tutto(cb, scritture("B"))
    prima_b = albero(cartella_di(due, "B"))
    r = ca.post("/api/nuova-stagione")
    assert r.status_code == 200, r.text
    assert (cartella_di(due, "A") / "archivio").is_dir()
    assert albero(cartella_di(due, "B")) == prima_b
    assert [p for p in dati_isolati.rglob("*") if p.is_file()] == []
    assert r.json()["archivio"] == "2026-27"                    # il nome della stagione, non dove sta sul server


def test_nuova_stagione_resta_nella_cartella_dell_utente_qualunque_stagione_abbiano_le_rose(due, dati_isolati):
    (ca, _), (cb, id_b) = due["A"], due["B"]
    esegui_tutto(ca, scritture("A"))
    esegui_tutto(cb, scritture("B"))
    radice = cartella_di(due, "A").parent
    copia = ca.get("/api/backup").json()                       # lo scarico segna la data del backup: prima di prendere le impronte
    prima_b, prima_a = albero(cartella_di(due, "B")), albero(cartella_di(due, "A"))
    for strana in (f"../../{id_b}", str(cartella_di(due, "B")), "2026"):
        copia["file"]["lega/rose.json"]["stagione"] = strana
        r = ca.post("/api/backup/ripristina", json=copia)
        assert r.status_code == 400, (strana, r.text)
        assert albero(cartella_di(due, "A")) == prima_a
        # rose già salvate con una stagione così (per esempio da una versione di prima): il passaggio di stagione non scrive niente
        file_rose = cartella_di(due, "A") / "rose.json"
        originale = file_rose.read_bytes()
        file_rose.write_text(json.dumps(json.loads(originale) | {"stagione": strana}), encoding="utf-8")
        r = ca.post("/api/nuova-stagione")
        assert r.status_code == 400 and r.json()["detail"] == server.lega.FORMA_SBAGLIATA, (strana, r.text)
        assert not (cartella_di(due, "A") / "archivio").exists()
        file_rose.write_bytes(originale)
    assert albero(cartella_di(due, "B")) == prima_b
    assert sorted(p.name for p in radice.iterdir()) == sorted({cartella_di(due, "A").name, cartella_di(due, "B").name})
    assert [p for p in dati_isolati.rglob("*") if p.is_file()] == []


# ---------------------------------------------------------------- gli avvisi non escono dal perimetro dell'utente
def test_gli_avvisi_degli_utenti_non_vanno_sul_canale_del_proprietario(due, monkeypatch):
    from fanta import notifiche, push
    ntfy = []
    monkeypatch.setattr(notifiche, "canale", lambda: "canale-del-proprietario")
    monkeypatch.setattr(notifiche, "_invia_ntfy", lambda *a, **k: ntfy.append(a) or True)
    ca = due["A"][0]
    ca.put("/api/avvisi", json={"app_nativa": True})
    assert ca.get("/api/avvisi").json()["canale"] is False                  # senza dispositivi iscritti, per lui non c'è nessun canale
    assert ca.post("/api/avvisi/prova").status_code == 409
    assert ntfy == []
    ca.post("/api/push/iscrivi", json=dati_di("A")["push"])
    monkeypatch.setattr(push, "invia", lambda *a, **k: 0)                     # il dispositivo non riceve: per l'utente non c'è il ripiego su ntfy
    assert ca.post("/api/avvisi/prova").json() == {"inviato": False}
    assert ntfy == []


def test_le_iscrizioni_push_sono_per_utente(due):
    (ca, _), (cb, _) = due["A"], due["B"]
    assert ca.post("/api/push/iscrivi", json=dati_di("A")["push"]).json() == {"dispositivi": 1}
    assert cb.post("/api/push/iscrivi", json=dati_di("B")["push"]).json() == {"dispositivi": 1}
    assert cb.post("/api/push/disiscrivi", json={"endpoint": dati_di("A")["push"]["endpoint"]}).json() == {"dispositivi": 1}   # non toglie quella di A
    assert ca.get("/api/avvisi").json()["dispositivi"] == 1


def test_quanto_ci_abbiamo_preso_e_per_utente(due):
    """Il riassunto del Diario (campo `precisione`) si calcola SOLO dal diario di chi chiede."""
    for m, reale, fv in (("A", 61.0, 9.0), ("B", 77.0, 6.5)):
        cartella = cartella_di(due, m)
        cartella.mkdir(parents=True, exist_ok=True)
        voce = {"stagione": "2026-27", "giornata": 5, "consigliata": {"atteso": 70.0, "reale": reale, "titolari": []},
                "schierata": None, "giocatori": [{"id": 1, "p_voto": 0.9, "fv_atteso": 6.0, "fv": fv}]}
        (cartella / "diario.json").write_text(json.dumps({"giornate": {"2026-27/5": voce}}), encoding="utf-8")
    for m, reale, errore in (("A", 61.0, 3.0), ("B", 77.0, 0.5)):
        p = due[m][0].get("/api/diario").json()["precisione"]
        assert p["giornate"] == 1 and p["per_giornata"][0]["fatti"] == reale and p["fantavoto"]["errore_medio"] == errore


# ---------------------------------------------------------------- interruttore spento: tutto come prima
@pytest.mark.percorsi_veri
def test_spento_i_percorsi_sono_quelli_di_sempre(monkeypatch):
    monkeypatch.delenv("FANTA_MULTIUTENTE", raising=False)
    from fanta.percorsi import CARTELLA_LEGA, RADICE
    ctx = server._contesto_locale()
    assert ctx.utente_id is None and ctx.ntfy is True and ctx.file_backup is None and ctx.copia_prima is None
    assert (ctx.regole, ctx.rose, ctx.movimenti, ctx.immagini) == (CARTELLA_LEGA / "regole.json", CARTELLA_LEGA / "rose.json",
                                                                  CARTELLA_LEGA / "movimenti.json", CARTELLA_LEGA / "immagini")
    dati = RADICE / "dati"
    assert (ctx.scelte, ctx.osservati, ctx.impostazioni_avvisi, ctx.icona, ctx.iscrizioni_push, ctx.diario, ctx.affidabilita) == (
        dati / "scelte.json", dati / "osservati.json", dati / "avvisi-impostazioni.json", dati / "icona.json", dati / "push.json",
        dati / "diario.json", dati / "affidabilita.json")


def test_spento_la_dipendenza_da_il_contesto_locale_senza_sessione(monkeypatch):
    monkeypatch.delenv("FANTA_MULTIUTENTE", raising=False)
    request = type("R", (), {"state": type("S", (), {})()})()
    assert server.lega_corrente(request).utente_id is None
