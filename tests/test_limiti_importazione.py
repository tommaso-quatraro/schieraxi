"""Limiti per utente sull'importazione delle rose (#514, requisito R3 di #483): lo stesso tetto di lavoro per ogni formato
(celle, memoria, tempo) e nessuna attesa per le scritture degli altri utenti mentre un'importazione lavora.

- celle: un Excel non legge più celle di un testo (`limiti.MAX_CELLE_IMPORTAZIONE`, tutti i fogli insieme);
- memoria: l'uscita del lettore degli Excel si legge al massimo fino a `importa_sicuro.MAX_DECOMPRESSO`, poi il lettore si ferma;
- tempo: il riconoscimento dei giocatori dura al massimo `limiti.MAX_SECONDI_RICONOSCIMENTO` secondi, poi si ferma con un messaggio;
- scritture: il riconoscimento (la parte lenta) si fa fuori dal blocco delle rose.
Mai l'orologio vero: tempi finti o attese brevi. Cartelle temporanee e dati inventati."""
import io
import itertools
import subprocess
import threading

import openpyxl
import pytest

from fanta import importa_sicuro, limiti, nomi, rose, server

from test_limiti import ambiente, nuovo_utente  # noqa: F401 (fixture e utente di prova)

TESTO_LUNGO = f"Il testo è troppo lungo (massimo {importa_sicuro.MAX_TESTO // 1000} mila caratteri): incolla solo le rose"
GRANDE_APERTO = "Il file Excel è troppo grande una volta aperto: carica solo il foglio con le rose"


def excel(cartella, fogli: dict[str, list[list]], nome="rose.xlsx"):
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for titolo, righe in fogli.items():
        ws = wb.create_sheet(titolo)
        for riga in righe:
            ws.append(riga)
    p = cartella / nome
    wb.save(p)
    return p


def tre_fogli_da_15_celle(cartella):
    """Tre fogli da 5 righe e 3 colonne piene: 45 celle in tutto, ognuno dentro i tetti di righe e colonne."""
    righe = [["P", "Sommer", 10]] * 5
    return excel(cartella, {"Uno": righe, "Due": righe, "Tre": righe})


# ---------------------------------------------------------------- celle: lo stesso tetto del testo
def test_il_tetto_di_celle_e_quello_del_testo():
    assert limiti.MAX_CELLE_IMPORTAZIONE == importa_sicuro.MAX_RIGHE * importa_sicuro.MAX_COLONNE


def test_excel_oltre_il_tetto_di_celle_rifiutato(tmp_path, monkeypatch):
    p = tre_fogli_da_15_celle(tmp_path)
    monkeypatch.setenv("FANTA_MAX_CELLE_IMPORTAZIONE", "44")              # un foglio alla volta ci sta, tutti insieme no
    with pytest.raises(ValueError) as e:
        importa_sicuro.leggi_excel(p)
    assert str(e.value) == GRANDE_APERTO
    monkeypatch.setenv("FANTA_MAX_CELLE_IMPORTAZIONE", "45")              # le colonne vuote in fondo non contano
    assert len(importa_sicuro.leggi_excel(p)) == 3


def test_excel_oltre_il_tetto_di_celle_rifiutato_dalla_rotta(ambiente, tmp_path, monkeypatch):  # noqa: F811
    a, _ = nuovo_utente("utentea")
    monkeypatch.setenv("FANTA_MAX_CELLE_IMPORTAZIONE", "44")
    r = a.post("/api/rose/file", files={"file": ("rose.xlsx", tre_fogli_da_15_celle(tmp_path).read_bytes(), "application/octet-stream")})
    assert r.status_code == 400 and r.json()["detail"] == GRANDE_APERTO
    assert a.get("/api/squadre").status_code == 409                       # niente salvato


def test_lo_stesso_tetto_di_celle_vale_per_il_testo(monkeypatch):
    monkeypatch.setenv("FANTA_MAX_CELLE_IMPORTAZIONE", "44")
    griglia = [["P", "Sommer", "10", "", ""]] * 15                       # 45 celle piene, le vuote in fondo non contano
    with pytest.raises(ValueError) as e:
        importa_sicuro.controlla_griglie([("testo", griglia)])
    assert str(e.value) == TESTO_LUNGO
    importa_sicuro.controlla_griglie([("testo", griglia[:14])])


# ---------------------------------------------------------------- memoria: l'uscita del lettore ha un tetto
def test_uscita_del_lettore_oltre_il_tetto_fermata_senza_tenerla_in_memoria(tmp_path, monkeypatch):
    finito = tmp_path / "finito"
    figlio = tmp_path / "figlio_finto.py"
    figlio.write_text("import sys\n"
                      "pezzo = b'x' * 65536\n"
                      "for _ in range(100):\n"                            # 6,4 MB, molto più del tetto
                      "    sys.stdout.buffer.write(pezzo)\n"
                      "    sys.stdout.buffer.flush()\n"
                      f"open({str(finito)!r}, 'w').write('tutto scritto')\n", encoding="utf-8")
    monkeypatch.setattr(importa_sicuro, "FIGLIO", figlio)
    monkeypatch.setattr(importa_sicuro, "MAX_DECOMPRESSO", 256 * 1024)
    avviati = []
    vero = subprocess.Popen

    def spia(*a, **k):
        p = vero(*a, **k)
        avviati.append(p)
        return p
    monkeypatch.setattr(subprocess, "Popen", spia)
    with pytest.raises(ValueError) as e:
        importa_sicuro.leggi_excel(excel(tmp_path, {"Rose": [["Mia"], ["P", "Sommer", 10]]}))
    assert str(e.value) == importa_sicuro.PESANTE
    assert len(avviati) == 1 and avviati[0].poll() is not None            # il lettore è stato fermato, non resta appeso
    assert not finito.exists()                                            # e non ha potuto scrivere tutto


def test_si_legge_al_massimo_il_tetto_piu_un_byte():
    flusso = io.BytesIO(b"x" * 10_000_000)
    assert importa_sicuro.leggi_al_massimo(flusso, 1000) is None
    assert flusso.tell() <= 1001                                          # in memoria mai più del tetto
    assert importa_sicuro.leggi_al_massimo(io.BytesIO(b"x" * 1000), 1000) == b"x" * 1000
    assert importa_sicuro.leggi_al_massimo(io.BytesIO(b""), 1000) == b""


# ---------------------------------------------------------------- tempo: il riconoscimento si ferma
def rose_lunghe(giocatori: int = 60) -> str:
    return "Mia\n" + "D\tBastoni\t5\n" * giocatori


def test_il_riconoscimento_si_ferma_quando_il_tempo_e_finito(indice, calciatori):
    fermo = nomi.Indice(calciatori, scaduto=lambda: True)
    with pytest.raises(nomi.TempoScaduto):
        rose.estrai([("testo", rose.griglia_da_testo(rose_lunghe(3)))], fermo)
    assert rose.estrai([("testo", rose.griglia_da_testo(rose_lunghe(3)))], indice)       # senza tetto: come sempre


def test_riconoscimento_oltre_il_tempo_si_ferma_con_messaggio(ambiente, tmp_path, monkeypatch):  # noqa: F811
    a, _ = nuovo_utente("utentea")
    secondi = itertools.count()                                           # ogni sguardo all'orologio: un secondo dopo
    monkeypatch.setattr(limiti, "_orologio", lambda: float(next(secondi)), raising=False)
    cercati = []
    vera = nomi.Indice.cerca

    def conta(self, *a, **k):
        cercati.append(1)
        return vera(self, *a, **k)
    monkeypatch.setattr(nomi.Indice, "cerca", conta)
    r = a.post("/api/rose/testo", json={"testo": rose_lunghe()})
    assert r.status_code == 400 and r.json()["detail"] == TESTO_LUNGO
    assert len(cercati) <= limiti.MAX_SECONDI_RICONOSCIMENTO + 2          # si è fermato: 60 nomi non li ha cercati tutti
    r = a.post("/api/rose/anteprima", json={"testo": rose_lunghe()})
    assert r.status_code == 400 and r.json()["detail"] == TESTO_LUNGO
    foglio = [["Mia"]] + [["D", "Bastoni", 5]] * 60
    r = a.post("/api/rose/file", files={"file": ("rose.xlsx", excel(tmp_path, {"Rose": foglio}).read_bytes(), "application/octet-stream")})
    assert r.status_code == 400 and r.json()["detail"] == importa_sicuro.PESANTE
    assert a.get("/api/squadre").status_code == 409                       # niente salvato


def test_per_conto_di_un_excel_oltre_il_tempo_ha_il_messaggio_dell_excel(ambiente, tmp_path, monkeypatch):  # noqa: F811
    """Il comando `importa-per-conto-di` legge l'Excel con leggi_excel e passa le griglie: il messaggio è quello dell'Excel."""
    _, id_a = nuovo_utente("utentea")
    griglie = importa_sicuro.leggi_excel(excel(tmp_path, {"Rose": [["Mia"]] + [["D", "Bastoni", 5]] * 60}))
    secondi = itertools.count()
    monkeypatch.setattr(limiti, "_orologio", lambda: float(next(secondi)))
    with pytest.raises(ValueError) as e:
        server.importa_per_conto_di(id_a, griglie, False, None)
    assert str(e.value) == importa_sicuro.PESANTE
    with pytest.raises(ValueError) as e:                                  # il testo resta col messaggio del testo
        server.importa_per_conto_di(id_a, [("testo", rose.griglia_da_testo(rose_lunghe()))], False, None)
    assert str(e.value) == TESTO_LUNGO


def test_senza_account_nessun_tempo_massimo(monkeypatch):
    class Ctx:
        utente_id = None
    assert limiti.tempo_riconoscimento(Ctx()) is None                     # l'app di sempre non ha un tempo massimo
    Ctx.utente_id = 7
    adesso = [100.0]
    monkeypatch.setattr(limiti, "_orologio", lambda: adesso[0])
    scaduto = limiti.tempo_riconoscimento(Ctx())
    assert scaduto() is False
    adesso[0] += limiti.MAX_SECONDI_RICONOSCIMENTO
    assert scaduto() is False
    adesso[0] += 0.5
    assert scaduto() is True


# ---------------------------------------------------------------- uso normale: nessun limite
def listone_di(quanti: int) -> list:
    """Calciatori inventati con nomi distinti (solo lettere), ruoli a rotazione, codici di 4 cifre come quelli veri."""
    from fanta.listone import Calciatore
    sillabe = ["ba", "ce", "di", "fo", "gu", "la", "me", "ni", "po", "ru"]
    return [Calciatore(1000 + i, "".join(sillabe[int(c)] for c in f"{i:03d}").capitalize() + "ni", "PDCA"[i % 4], "", "ROM",
                       "roma", 10, 10, 100) for i in range(quanti)]


def test_uso_normale_excel_passa(ambiente, tmp_path, monkeypatch):  # noqa: F811
    """Un Excel grande ma normale: 20 squadre da 40 giocatori, più due fogli che non sono rose (regolamento e punteggi di
    ogni giornata). Con i limiti di sempre e gli account accesi entra: nessun tetto di celle né di tempo lo tocca.
    (Un foglio col listone qui non va: il lettore di sempre legge ogni foglio e ne farebbe una squadra da 800 giocatori.)"""
    calciatori = listone_di(800)
    monkeypatch.setattr(server.listone, "carica", lambda *a, **k: (calciatori, "oggi"))
    rose_foglio = []
    for s in range(20):
        rose_foglio.append([f"Squadra {s + 1}"])
        rose_foglio += [[c.ruolo, c.nome, "ROM", 5] for c in calciatori[s * 40:(s + 1) * 40]]
    regolamento = [[f"Regola {k + 1}: bonus e malus come da regolamento della lega, panchina lunga e modificatore spento"]
                   for k in range(60)]
    punteggi = [["Giornata"] + [f"Squadra {k + 1}" for k in range(20)]] + [[g] + [66.5 + k for k in range(20)] for g in range(1, 39)]
    p = excel(tmp_path, {"Rose": rose_foglio, "Regolamento": regolamento, "Punteggi": punteggi})
    a, _ = nuovo_utente("utentea")
    r = a.post("/api/rose/file", files={"file": ("lega.xlsx", p.read_bytes(), "application/octet-stream")})
    assert r.status_code == 200, r.text
    assert r.json()["totale_squadre"] == 20
    squadre = a.get("/api/squadre").json()
    assert len(squadre) == 20 and all(len(a.get("/api/rosa", params={"squadra": s["nome"]}).json()["giocatori"]) == 40 for s in squadre[:3])


# ---------------------------------------------------------------- scritture degli altri: non aspettano
@pytest.mark.parametrize("come", ["testo", "file", "per_conto_di"])
def test_le_scritture_degli_altri_non_aspettano_il_riconoscimento(ambiente, monkeypatch, come):  # noqa: F811
    (a, id_a), (b, _) = nuovo_utente("utentea"), nuovo_utente("utenteb")
    assert b.post("/api/rose/testo", json={"testo": "Mia\nP\tSommer\t10\nAltra\nA\tKean\t30\n"}).status_code == 200
    partito, via = threading.Event(), threading.Event()
    vera = rose.estrai

    def lenta(griglie, *x, **k):                                          # riconoscimento lento finto: aspetta il «via»
        if any("Lenta" in c for _, g in griglie for riga in g for c in riga):
            partito.set()
            via.wait(10)
        return vera(griglie, *x, **k)
    monkeypatch.setattr(rose, "estrai", lenta)
    testo = "Lenta\nP\tSommer\t10\n"
    esiti = {}

    def importa_lenta():
        if come == "testo":
            esiti["a"] = a.post("/api/rose/testo", json={"testo": testo}).status_code
        elif come == "file":
            esiti["a"] = a.post("/api/rose/file", files={"file": ("rose.csv", testo.encode(), "text/csv")}).status_code
        else:
            esiti["a"] = len(server.importa_per_conto_di(id_a, [("testo", rose.griglia_da_testo(testo))], False, None)["squadre_importate"])

    def scrive_b():
        esiti["b"] = b.put("/api/mia-squadra", json={"nome": "Altra"}).status_code

    filo_a = threading.Thread(target=importa_lenta)
    filo_a.start()
    try:
        assert partito.wait(5)
        filo_b = threading.Thread(target=scrive_b)
        filo_b.start()
        filo_b.join(3)
        assert esiti.get("b") == 200 and "a" not in esiti                 # B ha finito mentre A riconosce ancora
    finally:
        via.set()
        filo_a.join(20)
    assert esiti["a"] in (200, 1)
    assert [s["nome"] for s in a.get("/api/squadre").json()] == ["Lenta"]
