"""Importazione protetta di Excel, CSV e testo (file di altri): file ostili finti, creati qui nel test, mai scaricati.
Tutto in cartelle temporanee."""
import random
import zipfile
from pathlib import Path

import openpyxl
import pytest

from fanta import importa_sicuro, rose, server

from test_limiti import ambiente, nuovo_utente  # noqa: F401 (la fixture `ambiente` serve ai test sulle rotte)


def excel_buono(cartella: Path, nome="rose.xlsx") -> Path:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Rose"
    for riga in (["Mia"], ["P", "Sommer", 10], ["D", "Bastoni", 15], ["Altra"], ["A", "Kean", 30]):
        ws.append(riga)
    p = cartella / nome
    wb.save(p)
    return p


def ricostruisci(origine: Path, destinazione: Path, aggiungi=(), sostituisci=None, togli=()) -> Path:
    """Copia l'Excel buono in un altro zip con qualche parte in più, cambiata o tolta."""
    sostituisci = sostituisci or {}
    with zipfile.ZipFile(origine) as a, zipfile.ZipFile(destinazione, "w", zipfile.ZIP_DEFLATED) as b:
        for info in a.infolist():
            if info.filename in togli:
                continue
            b.writestr(info.filename, sostituisci.get(info.filename, a.read(info.filename)))
        for nome, dati in aggiungi:
            b.writestr(nome, dati)
    return destinazione


def casuale(n: int) -> bytes:
    """Byte che non si comprimono (esadecimale di numeri a caso, senza due trattini di fila): un commento XML che non fa scattare il controllo sul rapporto."""
    return random.Random(7).randbytes(n // 2 + 1).hex().encode()[:n]


def rifiutato(percorso: Path, frammento: str = "") -> str:
    with pytest.raises(ValueError) as e:
        importa_sicuro.leggi_excel(percorso)
    assert frammento in str(e.value), str(e.value)
    return str(e.value)


# ---------------------------------------------------------------- il file giusto passa
def test_un_excel_normale_si_legge_come_prima(tmp_path):
    p = excel_buono(tmp_path)
    assert importa_sicuro.leggi_excel(p) == rose.leggi_griglie(p)
    assert importa_sicuro.leggi_excel(p)[0][1][1][:3] == ["P", "Sommer", "10"]


# ---------------------------------------------------------------- bombe zip e strutture strane
def test_bomba_zip_dimensione_totale(tmp_path):
    buono = excel_buono(tmp_path)
    # tre parti da 8 MB: ognuna sta nel suo limite, insieme no
    p = ricostruisci(buono, tmp_path / "b.xlsx", [(f"xl/extra{i}.xml", b"<a>" + b" " * (8 * 1024 * 1024) + b"</a>") for i in range(3)])
    rifiutato(p, "troppo grande")


def test_una_parte_gigante(tmp_path):
    p = ricostruisci(excel_buono(tmp_path), tmp_path / "b.xlsx", [("xl/extra.xml", b"<a>" + b" " * (13 * 1024 * 1024) + b"</a>")])
    rifiutato(p, "troppo grande")


def test_rapporto_di_compressione_sospetto(tmp_path):
    p = ricostruisci(excel_buono(tmp_path), tmp_path / "b.xlsx", [("xl/extra.xml", b"<a>" + b" " * (6 * 1024 * 1024) + b"</a>")])
    assert p.stat().st_size < 100_000                  # pochi KB che diventano 6 MB
    rifiutato(p, "sospetto")


def test_troppe_parti(tmp_path):
    p = ricostruisci(excel_buono(tmp_path), tmp_path / "b.xlsx", [(f"xl/extra{i}.txt", b"x") for i in range(importa_sicuro.MAX_PARTI)])
    rifiutato(p, "struttura strana")


def test_non_e_uno_zip_o_e_rovinato(tmp_path):
    finto = tmp_path / "finto.xlsx"
    finto.write_bytes(b"questo non e' un Excel")
    rifiutato(finto, "non leggibile")
    buono = excel_buono(tmp_path)
    troncato = tmp_path / "troncato.xlsx"
    troncato.write_bytes(buono.read_bytes()[:200])
    rifiutato(troncato, "non leggibile")


def test_protetto_da_password(tmp_path):
    p = excel_buono(tmp_path)
    dati = bytearray(p.read_bytes())
    i = dati.find(b"PK")
    while i != -1:                                       # nell'indice dell'archivio segna ogni parte come cifrata
        dati[i + 8] |= 0x1
        i = dati.find(b"PK", i + 4)
    p.write_bytes(bytes(dati))
    rifiutato(p, "password")


@pytest.mark.parametrize("nome", ["../fuori.xml", "/assoluto.xml", "C:evil.xml"])
def test_nomi_di_parti_pericolosi(tmp_path, nome):
    p = ricostruisci(excel_buono(tmp_path), tmp_path / "b.xlsx", [(nome, b"<a/>")])
    rifiutato(p, "nomi di parti")


# ---------------------------------------------------------------- macro e oggetti incorporati
@pytest.mark.parametrize("nome", ["xl/vbaProject.bin", "xl/embeddings/oleObject1.bin", "xl/externalLinks/externalLink1.xml",
                                  "xl/activeX/activeX1.xml"])
def test_macro_oggetti_e_collegamenti_esterni(tmp_path, nome):
    p = ricostruisci(excel_buono(tmp_path), tmp_path / "b.xlsx", [(nome, b"x")])
    rifiutato(p, "macro")


def test_tipo_con_macro_dichiarato_nei_content_types(tmp_path):
    buono = excel_buono(tmp_path)
    with zipfile.ZipFile(buono) as z:
        tipi = z.read("[Content_Types].xml").replace(b"spreadsheetml.sheet.main+xml", b"ms-excel.sheet.macroEnabled.main+xml")
    p = ricostruisci(buono, tmp_path / "b.xlsm", sostituisci={"[Content_Types].xml": tipi})
    rifiutato(p, "macro")


# ---------------------------------------------------------------- XML ostili
BOMBA_XML = (b'<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE lolz [<!ENTITY a "aaaaaaaaaa"><!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;">]>'
             b'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>&b;</sheetData></worksheet>')


def test_xml_con_entita_si_rifiuta(tmp_path):
    p = ricostruisci(excel_buono(tmp_path), tmp_path / "b.xlsx", sostituisci={"xl/worksheets/sheet1.xml": BOMBA_XML})
    rifiutato(p, "dichiarazioni XML")


def test_la_dichiarazione_nascosta_dopo_un_lungo_commento(tmp_path):
    xml = b'<?xml version="1.0"?><!--' + casuale(2 * 1024 * 1024) + b"-->" + BOMBA_XML.split(b"?>", 1)[1]
    p = ricostruisci(excel_buono(tmp_path), tmp_path / "b.xlsx", sostituisci={"xl/worksheets/sheet1.xml": xml})
    rifiutato(p, "dichiarazioni XML")


def test_la_dichiarazione_a_cavallo_dei_blocchi_di_lettura(tmp_path):
    riempimento = casuale(1024 * 1024 - len(b'<?xml version="1.0"?><!--') - 3 - 5)       # il DOCTYPE inizia 5 byte prima del confine
    xml = b'<?xml version="1.0"?><!--' + riempimento + b"--><!DOCTYPE a><a/>"
    p = ricostruisci(excel_buono(tmp_path), tmp_path / "b.xlsx", sostituisci={"xl/worksheets/sheet1.xml": xml})
    rifiutato(p, "dichiarazioni XML")


def test_codifiche_che_nascondono_il_doctype(tmp_path):
    utf16 = BOMBA_XML.decode().replace("UTF-8", "UTF-16").encode("utf-16")
    cambio = b'<?xml version="1.0" encoding="ebcdic-cp-us"?><a/>'
    for nome, xml in (("utf16.xlsx", utf16), ("cambio.xlsx", cambio)):
        p = ricostruisci(excel_buono(tmp_path), tmp_path / nome, sostituisci={"xl/worksheets/sheet1.xml": xml})
        rifiutato(p, "codifica")


# ---------------------------------------------------------------- tempo massimo
def test_tempo_massimo(tmp_path, monkeypatch):
    p = excel_buono(tmp_path)
    monkeypatch.setattr(importa_sicuro, "TEMPO_MASSIMO", 0.001)           # il processo non fa in tempo nemmeno ad avviarsi
    rifiutato(p, "troppo pesante")


def test_il_processo_figlio_che_fallisce_non_porta_giu_il_server(tmp_path, monkeypatch):
    p = excel_buono(tmp_path)
    monkeypatch.setattr(importa_sicuro, "FIGLIO", tmp_path / "non-esiste.py")      # il figlio parte ma esce con errore
    rifiutato(p, "troppo pesante")


# ---------------------------------------------------------------- testo e CSV
def test_limiti_di_testo_righe_e_colonne():
    importa_sicuro.controlla_testo("Mia\nP\tSommer\t10\n")
    with pytest.raises(ValueError, match="troppo lungo"):
        importa_sicuro.controlla_testo("x" * (importa_sicuro.MAX_TESTO + 1))
    with pytest.raises(ValueError, match="troppe righe"):
        importa_sicuro.controlla_griglie([("testo", [["a"]] * (importa_sicuro.MAX_RIGHE + 1))])
    with pytest.raises(ValueError, match="troppe colonne"):
        importa_sicuro.controlla_griglie([("testo", [["a"] * (importa_sicuro.MAX_COLONNE + 1)])])
    importa_sicuro.controlla_griglie([("testo", [["a"] * importa_sicuro.MAX_COLONNE] * importa_sicuro.MAX_RIGHE)])


# ---------------------------------------------------------------- dalle rotte
def invia(c, nome: str, dati: bytes):
    return c.post("/api/rose/file", files={"file": (nome, dati, "application/octet-stream")})


def test_dalla_rotta_un_excel_buono_entra(ambiente, tmp_path):
    a, _ = nuovo_utente("utentea")
    r = invia(a, "rose.xlsx", excel_buono(tmp_path).read_bytes())
    assert r.status_code == 200, r.text
    assert [s["nome"] for s in a.get("/api/squadre").json()] == ["Mia", "Altra"]


def test_dalla_rotta_xlsm_e_file_ostili_si_rifiutano(ambiente, tmp_path):
    a, _ = nuovo_utente("utentea")
    buono = excel_buono(tmp_path)
    r = invia(a, "rose.xlsm", buono.read_bytes())
    assert r.status_code == 400 and ".xlsm" in r.json()["detail"]
    macro = ricostruisci(buono, tmp_path / "m.xlsx", [("xl/vbaProject.bin", b"x")])
    assert invia(a, "rose.xlsx", macro.read_bytes()).status_code == 400
    bomba = ricostruisci(buono, tmp_path / "x.xlsx", sostituisci={"xl/worksheets/sheet1.xml": BOMBA_XML})
    r = invia(a, "rose.xlsx", bomba.read_bytes())
    assert r.status_code == 400 and "XML" in r.json()["detail"]
    assert a.get("/api/squadre").status_code == 409                   # nessuna rosa salvata
    assert list((server.RADICE / "dati" / "cache").glob("*")) == []   # e nessun file temporaneo rimasto in giro


def test_dalla_rotta_testo_e_csv_troppo_grandi(ambiente):
    a, _ = nuovo_utente("utentea")
    assert a.post("/api/rose/testo", json={"testo": "x" * (importa_sicuro.MAX_TESTO + 1)}).status_code == 400
    righe = "Mia\n" + "P;Sommer;10\n" * (importa_sicuro.MAX_RIGHE + 1)
    assert invia(a, "rose.csv", righe.encode()).status_code == 400
    larghe = "Mia\n" + ";".join(["P"] * (importa_sicuro.MAX_COLONNE + 1)) + "\n"
    assert invia(a, "rose.csv", larghe.encode()).status_code == 400
    assert invia(a, "rose.csv", b"x" * (importa_sicuro.MAX_TESTO + 1)).status_code == 400
    assert invia(a, "rose.csv", b"Mia\nP;Sommer;10\n").status_code == 200


# ---------------------------------------------------------------- interruttore spento: come prima
def test_spento_si_legge_come_prima(monkeypatch, tmp_path, dati_isolati, calciatori):
    monkeypatch.delenv("FANTA_MULTIUTENTE", raising=False)
    monkeypatch.setattr(server.listone, "carica", lambda *a, **k: (calciatori, "oggi"))
    monkeypatch.setattr(server.consigli, "stagione_corrente", lambda: "2026-27")

    def non_deve_succedere(*a, **k):
        raise AssertionError("a interruttore spento nessun controllo in più")
    for nome in ("leggi_excel", "controlla_zip", "controlla_testo", "controlla_griglie"):
        monkeypatch.setattr(importa_sicuro, nome, non_deve_succedere)
    from test_account_http import cliente
    c = cliente()
    buono = excel_buono(tmp_path)
    assert invia(c, "rose.xlsx", buono.read_bytes()).status_code == 200
    assert invia(c, "rose.xlsm", buono.read_bytes()).status_code == 200        # come prima
    assert c.post("/api/rose/testo", json={"testo": "Mia\nP\tSommer\t10\n" + " " * 300_000}).status_code == 200


def test_anche_i_disegni_vml_si_controllano(tmp_path):
    p = ricostruisci(excel_buono(tmp_path), tmp_path / "b.xlsx", [("xl/drawings/vmlDrawing1.vml", BOMBA_XML)])
    rifiutato(p, "dichiarazioni XML")
