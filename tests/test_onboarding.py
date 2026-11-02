"""Procedura guidata: stato sul server, regole dal regolamento, lega demo, controlli finali, correzione dei giocatori non riconosciuti."""
import contextlib
from dataclasses import asdict

import pytest

from fanta import account, contesto, onboarding, server
from fanta.listone import Calciatore
from fanta.regole import Regole

from test_account_http import PASSWORD, cliente
from test_isolamento import albero
from test_limiti import ambiente, nuovo_utente  # noqa: F401 (fixture e utente di prova)

ROSE = "Mia\nP\tSommer\t10\nD\tBastoni\t15\nAltra\nA\tKean\t30\n"
REGOLAMENTO = """Assist: +1,5
Ammonizione: -0,5
Moduli ammessi: 4-3-3 4-4-2 3-5-2
Panchina: 2 portieri, 3 difensori, 3 centrocampisti, 3 attaccanti
Bonus speciale della casa 12345 punti
"""


def id_di(nome: str) -> int:
    with contextlib.closing(account.apri()) as db:
        return db.execute("SELECT id FROM utenti WHERE nome_utente = ?", (nome,)).fetchone()[0]


def listone_grande():
    """Abbastanza calciatori (finti) per quattro rose da 25: ruoli P, D, C, A."""
    elenco, i = [], 0
    for ruolo, quanti in (("P", 14), ("D", 36), ("C", 36), ("A", 28)):
        for k in range(quanti):
            i += 1
            elenco.append(Calciatore(i, f"{ruolo}{k:02d} Prova", ruolo, "", "ROM", "roma", 40 - k, 10, 100))
    return elenco


# ---------------------------------------------------------------- lo stato sul server
def test_lo_stato_si_riprende_da_un_altro_dispositivo(ambiente):
    a1, _ = nuovo_utente("utentea")
    stato = a1.get("/api/onboarding").json()
    assert (stato["stato"], stato["passo"], stato["tipo"], stato["demo"]) == ("da_fare", "benvenuto", "classic", False)
    assert stato["passi"] == list(onboarding.PASSI)
    assert a1.put("/api/onboarding", json={"passo": "rose", "stato": "in_corso"}).json()["passo"] == "rose"
    a2 = cliente()                                             # un altro telefono, stesso utente
    assert a2.post("/api/account/accedi", json={"nome_utente": "utentea", "password": PASSWORD}).status_code == 200
    assert a2.get("/api/onboarding").json()["passo"] == "rose" and a2.get("/api/onboarding").json()["stato"] == "in_corso"


def test_valori_sbagliati_e_lega_mantra(ambiente):
    a, _ = nuovo_utente("utentea")
    assert a.put("/api/onboarding", json={"passo": "inventato"}).status_code == 400
    assert a.put("/api/onboarding", json={"stato": "finito-male"}).status_code == 400
    r = a.put("/api/onboarding", json={"tipo": "mantra"})
    assert r.status_code == 400 and "Mantra" in r.json()["detail"] and "classic" in r.json()["detail"]
    assert a.put("/api/onboarding", json={"tipo": "classic", "stato": "completato"}).json()["stato"] == "completato"


def test_chi_ha_gia_le_rose_non_deve_rifare_la_procedura(ambiente):
    a, _ = nuovo_utente("utentea")
    assert a.post("/api/rose/testo", json={"testo": ROSE}).status_code == 200
    assert a.get("/api/onboarding").json()["stato"] == "completato"


def test_ognuno_ha_la_sua_procedura(ambiente):
    (a, _), (b, _) = nuovo_utente("utentea"), nuovo_utente("utenteb")
    a.put("/api/onboarding", json={"passo": "controlli", "stato": "in_corso"})
    assert b.get("/api/onboarding").json()["passo"] == "benvenuto"
    b.put("/api/onboarding", json={"passo": "tipo"})
    assert a.get("/api/onboarding").json()["passo"] == "controlli"


def test_eliminando_l_account_sparisce_anche_la_procedura(ambiente):
    a, _ = nuovo_utente("utentea")
    a.get("/api/onboarding")
    with contextlib.closing(account.apri()) as db:
        assert db.execute("SELECT COUNT(*) FROM leghe").fetchone()[0] == 1
    assert a.post("/api/account/elimina", json={"password": PASSWORD}).status_code == 200
    with contextlib.closing(account.apri()) as db:
        assert db.execute("SELECT COUNT(*) FROM leghe").fetchone()[0] == 0


def test_spento_non_c_e_niente(monkeypatch, tmp_path, dati_isolati):
    monkeypatch.delenv("FANTA_MULTIUTENTE", raising=False)
    monkeypatch.setenv("FANTA_DATI_UTENTI", str(tmp_path / "non-deve-esistere"))
    c = cliente()
    for metodo, percorso in (("GET", "/api/onboarding"), ("PUT", "/api/onboarding"), ("POST", "/api/onboarding/regole"),
                             ("GET", "/api/onboarding/controlli"), ("POST", "/api/onboarding/demo"), ("DELETE", "/api/onboarding/demo")):
        assert c.request(metodo, percorso, json={"testo": "x"} if metodo != "GET" else None).status_code == 404, percorso
    assert not (tmp_path / "non-deve-esistere").exists()


# ---------------------------------------------------------------- regole dal regolamento
def test_il_regolamento_diventa_una_proposta_senza_salvare(ambiente):
    a, _ = nuovo_utente("utentea")
    r = a.post("/api/onboarding/regole", json={"testo": REGOLAMENTO})
    assert r.status_code == 200, r.text
    esito = r.json()
    chiavi = {m["chiave"]: m for m in esito["riconosciute"]}
    assert chiavi["bonus.assist"]["valore"] == 1.5 and "Assist" in chiavi["bonus.assist"]["riga"]
    assert esito["regole"]["bonus"]["assist"] == 1.5 and esito["regole"]["bonus"]["ammonizione"] == -0.5
    assert esito["regole"]["panchina"]["posti"] == {"P": 2, "D": 3, "C": 3, "A": 3} and esito["regole"]["panchina"]["numero"] == 11
    assert sorted(esito["regole"]["moduli"]) == ["3-5-2", "4-3-3", "4-4-2"]
    assert any("12345" in riga for riga in esito["da_confermare"])             # la riga che non so leggere resta da guardare
    assert not contesto.cartella_utente(id_di("utentea")).joinpath("regole.json").exists()      # e non è stato salvato niente
    # l'utente la conferma: PUT delle regole proposte
    assert a.put("/api/regole", json=esito["regole"]).status_code == 200
    assert a.get("/api/regole").json()["bonus"]["assist"] == 1.5


def test_un_testo_senza_regole_e_regole_che_non_stanno_in_piedi():
    r = onboarding.proponi_regole(Regole(), "Benvenuti nella nostra lega, buon divertimento")
    assert r["riconosciute"] == [] and r["regole"] == asdict(Regole())
    with pytest.raises(ValueError, match="sconosciuta"):
        onboarding.applica_modifiche(Regole(), [{"chiave": "bonus.inventato", "valore": 1}])
    with pytest.raises(ValueError, match="sconosciuta"):
        onboarding.applica_modifiche(Regole(), [{"chiave": "niente.assist", "valore": 1}])
    with pytest.raises(ValueError, match="non valide"):
        onboarding.applica_modifiche(Regole(), [{"chiave": "moduli", "valore": ["9-9-9"]}])


# ---------------------------------------------------------------- controlli finali
def test_i_controlli_finali(ambiente):
    a, _ = nuovo_utente("utentea")

    def spunte():
        return {c["id"]: c for c in a.get("/api/onboarding/controlli").json()}
    c = spunte()
    assert [k for k, v in c.items() if v["obbligatorio"]] == ["regole", "rose", "squadra"]
    assert not any(v["ok"] for k, v in c.items() if v["obbligatorio"])
    assert a.put("/api/regole", json=asdict(Regole())).status_code == 200
    assert a.post("/api/rose/testo", json={"testo": ROSE + "Terza\nD\tPinco Pallino\t5\n"}).status_code == 200
    c = spunte()
    assert c["regole"]["ok"] and c["rose"]["ok"] and not c["squadra"]["ok"]
    assert not c["riconosciuti"]["ok"] and "Pinco Pallino" in c["riconosciuti"]["dettaglio"] and not c["riconosciuti"]["obbligatorio"]
    assert not c["complete"]["ok"]                                                # le rose sono corte rispetto alle regole: un avviso, non un blocco
    a.put("/api/mia-squadra", json={"nome": "Mia"})
    c = spunte()
    assert all(v["ok"] for v in c.values() if v["obbligatorio"])


# ---------------------------------------------------------------- lega demo
def test_la_lega_demo(ambiente, monkeypatch):
    monkeypatch.setattr(server.listone, "carica", lambda *a, **k: (listone_grande(), "oggi"))
    (a, _), (b, _) = nuovo_utente("utentea"), nuovo_utente("utenteb")
    prima_b = albero(contesto.cartella_utente(id_di("utenteb")))
    stato = a.post("/api/onboarding/demo").json()
    assert stato["demo"] is True and stato["passo"] == "formazione" and stato["stato"] == "in_corso"
    squadre = a.get("/api/squadre").json()
    assert [s["nome"] for s in squadre] == list(onboarding.SQUADRE_DEMO) and [s["giocatori"] for s in squadre] == [25] * 4
    assert next(s for s in squadre if s["mia"])["nome"] == onboarding.SQUADRE_DEMO[0]
    tutti = [g["id"] for s in squadre for g in a.get("/api/rosa", params={"squadra": s["nome"]}).json()["giocatori"]]
    assert len(tutti) == len(set(tutti)) == 100                                   # nessun giocatore in due squadre
    assert a.get("/api/regole").status_code == 200 and contesto.cartella_utente(id_di("utentea")).joinpath("regole.json").exists()
    assert albero(contesto.cartella_utente(id_di("utenteb"))) == prima_b          # B non si accorge di niente
    # togliere la demo ricomincia dall'inizio e cancella solo i dati della demo
    stato = a.delete("/api/onboarding/demo").json()
    assert stato["demo"] is False and stato["passo"] == "tipo"
    assert a.get("/api/squadre").status_code == 409
    assert a.delete("/api/onboarding/demo").status_code == 409                    # non c'è più


def test_la_demo_non_sostituisce_mai_rose_vere(ambiente, monkeypatch):
    monkeypatch.setattr(server.listone, "carica", lambda *a, **k: (listone_grande(), "oggi"))
    a, _ = nuovo_utente("utentea")
    a.post("/api/rose/testo", json={"testo": ROSE})
    prima = albero(contesto.cartella_utente(id_di("utentea")))
    r = a.post("/api/onboarding/demo")
    assert r.status_code == 409 and "tue rose" in r.json()["detail"]
    assert albero(contesto.cartella_utente(id_di("utentea"))) == prima
    assert a.delete("/api/onboarding/demo").status_code == 409                   # e nemmeno si cancellano rose che non sono demo
    assert albero(contesto.cartella_utente(id_di("utentea"))) == prima


# ---------------------------------------------------------------- giocatori non riconosciuti
def test_correggere_un_giocatore_non_riconosciuto(ambiente):
    (a, _), (b, _) = nuovo_utente("utentea"), nuovo_utente("utenteb")
    for c in (a, b):
        assert c.post("/api/rose/testo", json={"testo": ROSE + "Terza\nD\tPinco Pallino\t5\n"}).status_code == 200
    prima_b = albero(contesto.cartella_utente(id_di("utenteb")))
    giusta = {"squadra": "Terza", "nome": "Pinco Pallino", "id": 12}                  # 12 = Barella nel listone di prova
    sbagliate = [giusta | {"id": 9999}, giusta | {"nome": "Chi?"}, giusta | {"squadra": "Non esiste"}, giusta | {"nome": "Sommer", "squadra": "Mia"}]
    for s in sbagliate:
        assert a.post("/api/rose/correggi", json=s).status_code == 404, s
    assert a.post("/api/rose/correggi", json=giusta, headers={"If-Match": '"vecchio"'}).status_code == 412
    r = a.post("/api/rose/correggi", json=giusta)
    assert r.status_code == 200, r.text
    g = r.json()["giocatore"]
    assert (g["id"], g["nome"], g["ruolo"], g["riconosciuto"], g["avviso"]) == (12, "Barella", "C", "manuale", "")
    assert not any("Pinco" in x for x in r.json()["avvisi"])
    rosa = a.get("/api/rosa", params={"squadra": "Terza"}).json()["giocatori"]
    assert [x["nome"] for x in rosa] == ["Barella"]
    assert a.post("/api/rose/correggi", json=giusta).status_code == 404                # ormai è a posto
    assert albero(contesto.cartella_utente(id_di("utenteb"))) == prima_b               # la rosa di B è intatta
    assert [x["nome"] for x in b.get("/api/rosa", params={"squadra": "Terza"}).json()["giocatori"]] == ["Pinco Pallino"]


def test_dopo_la_demo_le_rose_vere_non_si_cancellano_ne_si_sostituiscono(ambiente, monkeypatch):
    """Il segno «demo» resta anche se poi l'utente importa le sue rose: togliere o rifare la demo non deve toccarle."""
    monkeypatch.setattr(server.listone, "carica", lambda *a, **k: (listone_grande(), "oggi"))
    a, _ = nuovo_utente("utentea")
    assert a.post("/api/onboarding/demo").status_code == 200
    assert a.post("/api/rose/testo", json={"testo": ROSE, "sostituisci_tutto": True}).status_code == 200
    prima = albero(contesto.cartella_utente(id_di("utentea")))
    assert a.post("/api/onboarding/demo").status_code == 409                      # non sostituisce le rose vere
    r = a.delete("/api/onboarding/demo")
    assert r.status_code == 200 and r.json()["demo"] is False and r.json()["passo"] == "tipo"
    assert albero(contesto.cartella_utente(id_di("utentea"))) == prima            # e non cancella niente
    assert [s["nome"] for s in a.get("/api/squadre").json()] == ["Mia", "Altra"]
