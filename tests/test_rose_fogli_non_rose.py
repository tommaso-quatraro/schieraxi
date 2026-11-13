"""Excel esportati dalla lega con altri fogli oltre alle rose (#543): listone, calendario e classifica non sono rose e si saltano
in silenzio (niente squadre finte, niente avvisi); le rose dello stesso file si leggono come sempre. Se ci sono solo quei fogli
il messaggio dice quali; i messaggi d'errore dell'importazione arrivano interi all'app (#579).
Squadre, persone e giocatori inventati; i file stanno in cartelle temporanee."""
import ast
import json
from pathlib import Path

import openpyxl
import pytest

from fanta import importa_sicuro, rose, server
from fanta.listone import Calciatore
from fanta.nomi import Indice

from test_limiti import ambiente, nuovo_utente  # noqa: F401 (fixture e utente di prova)

CLUB = [("INT", "inter"), ("GEN", "genoa"), ("FIO", "fiorentina"), ("ATA", "atalanta"), ("ROM", "roma")]
SILLABE = ["ba", "ce", "di", "fo", "gu", "la", "me", "ni", "po", "ru", "sa", "te", "vi", "zo"]


def giocatori_inventati(quanti: int = 300) -> list[Calciatore]:
    """Centinaia di giocatori con nomi inventati («Bacedetti»...), codici da 1000 in su (fuori da quelli del listone di prova)."""
    out = []
    for i in range(quanti):
        nome = (SILLABE[i % 14] + SILLABE[i // 14 % 14] + SILLABE[i // 196 % 14] + "tti").capitalize()
        sigla, slug = CLUB[i % len(CLUB)]
        out.append(Calciatore(1000 + i, nome, "PDCA"[i % 4], "", sigla, slug, 10, 10, 100))
    return out


def foglio_listone(giocatori: list[Calciatore]) -> list[list]:
    """Come il file delle quotazioni: un titolo, l'intestazione, poi una riga per giocatore con codice, ruolo e quotazioni."""
    righe = [["Quotazioni Esempio Stagione 2026 27"], ["Id", "R", "Nome", "Squadra", "Qt.A", "Qt.I", "Diff.", "FVM"]]
    for i, c in enumerate(giocatori):
        qa = 1 + i % 40
        righe.append([c.id, c.ruolo, c.nome, c.squadra_slug.capitalize(), qa, qa - (i % 7 - 3), i % 7 - 3, 1 + i % 200])
    return righe


# due giornate affiancate, con i punteggi delle giocate e i trattini di quelle ancora da giocare
CALENDARIO = [
    ["Calendario Lega Esempio"],
    ["1ª Giornata lega", None, None, None, None, "2ª Giornata lega"],
    ["Real Esempio", 72.5, 66, "FC Under", None, "Real Esempio", 68, 70.5, "I Bomber"],
    ["I Bomber", 64, 71.5, "La Banda", None, "FC Under", 74, 61, "La Banda"],
    [],
    ["3ª Giornata lega", None, None, None, None, "4ª Giornata lega"],
    ["Real Esempio", "-", "-", "La Banda", None, "FC Under", "-", "-", "Real Esempio"],
    ["I Bomber", "-", "-", "FC Under", None, "La Banda", "-", "-", "I Bomber"],
]

CLASSIFICA = [
    ["Classifica Lega Esempio"],
    ["Pos", "Squadra", "G", "V", "N", "P", "Gf", "Gs", "Dr", "Pt", "Pt. totali"],
    [1, "Real Esempio", 10, 7, 2, 1, 20, 9, 11, 23, 765.5],
    [2, "FC Under", 10, 6, 2, 2, 18, 12, 6, 20, 742],
    [3, "I Bomber", 10, 4, 3, 3, 15, 14, 1, 15, 720.5],
    [4, "La Banda", 10, 1, 1, 8, 8, 26, -18, 4, 690],
]

# le rose come le esporta la lega: due squadre affiancate, intestazione, un giocatore per ruolo, crediti rimasti
ROSE = [
    ["Real Esempio", None, None, None, None, "FC Under"],
    ["Ruolo", "Calciatore", "Squadra", "Costo", None, "Ruolo", "Calciatore", "Squadra", "Costo"],
    ["P", "Carnesecchi", "Atalanta", 43, None, "P", "Martinez Jo.", "Inter", 58],
    ["D", "Bastoni", "Inter", 17, None, "D", "N'Dicka", "Roma", 12],
    ["C", "Barella", "Inter", 35, None, "C", "Thuram K.", "Juventus", 1],
    ["A", "Thuram", "Inter", 104, None, "A", "Esposito Se.", "Inter", 21],
    ["Crediti Residui: 12", None, None, None, None, "Crediti Residui: 3"],
]


def _excel(cartella, fogli: dict[str, list[list]]):
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for titolo, righe in fogli.items():
        ws = wb.create_sheet(titolo)
        for riga in righe:
            ws.append(riga)
    p = cartella / "lega.xlsx"
    wb.save(p)
    return p


def _excel_misto(cartella, calciatori):
    return _excel(cartella, {"Rose": ROSE, "Listone": foglio_listone(calciatori + giocatori_inventati()),
                             "Calendario": CALENDARIO, "Classifica": CLASSIFICA})


def _riassunto(squadre):
    return {s.nome: ([r.esito.calciatore.id if r.esito.trovato else r.testo for r in s.righe], s.crediti_residui)
            for s in squadre}


ROSE_LETTE = {"Real Esempio": ([1, 3, 12, 7], 12), "FC Under": ([11, 4, 6, 8], 3)}


# ---------------------------------------------------------------- un tipo di foglio alla volta, accanto alle rose
def test_foglio_del_listone_si_salta(calciatori):
    """Centinaia di giocatori con le quotazioni, senza nomi di squadra in mezzo: prima diventavano una squadra sola (e con gli
    account l'importazione si fermava: più di 40 giocatori)."""
    tutti = calciatori + giocatori_inventati()
    avvisi = []
    squadre = rose.estrai([("Rose", ROSE), ("Tutti", foglio_listone(tutti))], Indice(tutti), avvisi=avvisi)
    assert _riassunto(squadre) == ROSE_LETTE and avvisi == []


def test_foglio_del_calendario_si_salta(indice):
    """Giornate e coppie di fantasquadre con i punteggi: prima ogni giornata diventava una squadra di «giocatori» non trovati."""
    avvisi = []
    squadre = rose.estrai([("Rose", ROSE), ("Calendario", CALENDARIO)], indice, avvisi=avvisi)
    assert _riassunto(squadre) == ROSE_LETTE and avvisi == []


def test_foglio_della_classifica_si_salta(indice):
    """Fantasquadre con posizione e punti: prima la prima squadra della classifica prendeva le altre come «giocatori», anche
    la squadra vera con lo stesso nome nelle rose."""
    avvisi = []
    squadre = rose.estrai([("Classifica", CLASSIFICA), ("Rose", ROSE)], indice, avvisi=avvisi)
    assert _riassunto(squadre) == ROSE_LETTE and avvisi == []


# ---------------------------------------------------------------- il file intero: solo le rose
@pytest.mark.parametrize("leggi", [rose.leggi_griglie, importa_sicuro.leggi_excel], ids=["senza-account", "con-account"])
def test_excel_con_rose_listone_calendario_e_classifica_legge_solo_le_rose(tmp_path, calciatori, leggi):
    """Le stesse fantasquadre compaiono anche in calendario e classifica: le loro rose non prendono «giocatori» da quei fogli."""
    tutti = calciatori + giocatori_inventati()
    avvisi = []
    squadre = rose.estrai(leggi(_excel_misto(tmp_path, calciatori)), Indice(tutti), avvisi=avvisi)
    assert _riassunto(squadre) == ROSE_LETTE
    assert avvisi == []


def test_excel_misto_si_importa_con_gli_account(ambiente, tmp_path, calciatori, monkeypatch):  # noqa: F811
    """Dalla rotta, con gli account: niente più «ha 317 giocatori: il massimo è 40», si salvano le due rose."""
    monkeypatch.setattr(server.listone, "carica", lambda *a, **k: (calciatori + giocatori_inventati(), "oggi"))
    a, _ = nuovo_utente("utentea")
    contenuto = _excel_misto(tmp_path, calciatori).read_bytes()
    r = a.post("/api/rose/file", files={"file": ("lega.xlsx", contenuto, "application/octet-stream")})
    assert r.status_code == 200, r.text
    assert {(s["nome"], s["giocatori"]) for s in a.get("/api/squadre").json()} == {("Real Esempio", 4), ("FC Under", 4)}


# ---------------------------------------------------------------- le rose vere restano rose
def test_un_foglio_con_tutte_le_rose_non_e_un_listone():
    """Dieci squadre da 25 nello stesso foglio (250 giocatori): sono tante, ma divise dai nomi delle squadre."""
    giocatori = giocatori_inventati(250)
    nomi = ["Real Esempio", "FC Under", "I Bomber", "La Banda", "Lupi Grigi",
            "Orsi Bianchi", "Gufi Neri", "Volpi Rosse", "Aquile Blu", "Falchi Verdi"]
    righe = []
    for coppia in range(5):                                    # due squadre affiancate, una coppia sotto l'altra
        sinistra, destra = 2 * coppia, 2 * coppia + 1
        righe.append([nomi[sinistra], "Costo", None, nomi[destra], "Costo"])
        for k in range(25):
            g1, g2 = giocatori[sinistra * 25 + k], giocatori[destra * 25 + k]
            righe.append([g1.nome, 10, None, g2.nome, 5])
        righe.append([])
    squadre = rose.estrai([("TutteLeRose", righe)], Indice(giocatori))
    assert sorted((s.nome, len(s.righe)) for s in squadre) == sorted((n, 25) for n in nomi)


def test_la_stessa_squadra_in_due_fogli_resta_una(indice):
    """Ogni foglio si legge a parte e poi si unisce: la stessa squadra in due fogli prende le righe di tutti e due, e i crediti
    dell'ultimo che li scrive."""
    primo = [["Real Esempio", "Costo"], ["Sommer", 10], ["Bastoni", 15], ["Crediti residui: 40"]]
    secondo = [["Real Esempio", "Costo"], ["Barella", 20], ["Kean", 30], ["Crediti residui: 12"]]
    assert _riassunto(rose.estrai([("Andata", primo), ("Ritorno", secondo)], indice)) == {
        "Real Esempio": ([2, 3, 12, 14], 12)}


def test_una_rosa_di_nomi_non_riconosciuti_resta_una_rosa(indice):
    """Una rosa con ruolo e costo ma nomi che il listone non conosce (scritti in un altro modo): non è una classifica."""
    righe = [["Real Esempio"], ["Ruolo", "Calciatore", "Costo"]] + [["D", f"Sconosciuto {chr(65 + k)}", 5 + k] for k in range(8)]
    squadre = rose.estrai([("Rose", righe)], indice)
    assert [(s.nome, len(s.righe)) for s in squadre] == [("Real Esempio", 8)]


# costi sopra 17: con il listone di prova (codici 1-17) righe «nome, numero, numero» sembrerebbero l'esportazione «rosters»
SCONOSCIUTI = [["Ugo Inventato", 21, 22], ["Leo Fittizio", 27, 29], ["Gino Immaginario", 35, 30], ["Pio Ipotetico", 23, 24],
               ["Ivo Supposto", 45, 44], ["Ezio Presunto", 19, 20], ["Rino Teorico", 60, 58], ["Dino Figurato", 25, 26]]


@pytest.mark.parametrize("fogli, nomi", [
    ([("Rose", [["Real Esempio"], ["Calciatore", "Costo", "Quotazione"]] + SCONOSCIUTI)],    # squadre in colonna
     [r[0] for r in SCONOSCIUTI]),
    # un foglio per squadra: il nome è quello del foglio (il primo giocatore è nel listone, se no sarebbe preso per il nome)
    ([("Real Esempio", [["Giocatore", "Prezzo", "Quotazione"], ["Sommer", 18, 20]] + SCONOSCIUTI)],
     ["Sommer"] + [r[0] for r in SCONOSCIUTI]),
], ids=["squadre-in-colonna", "un-foglio-per-squadra"])
def test_rosa_senza_ruolo_con_nomi_sconosciuti_resta_una_rosa(indice, fogli, nomi):
    """Nome, costo e quotazione, senza ruolo né squadra di Serie A, con nomi che il listone non conosce (per esteso): ogni riga
    sembra quella di una classifica, ma l'intestazione da rosa (calciatore, giocatore, costo, prezzo) dice che è una rosa."""
    squadre = rose.estrai(fogli, indice)
    assert [(s.nome, [r.testo for r in s.righe]) for s in squadre] == [("Real Esempio", nomi)]


# ---------------------------------------------------------------- solo fogli saltati: il messaggio dice quali e perché
def test_solo_fogli_saltati_il_messaggio_dice_quali(calciatori):
    tutti = calciatori + giocatori_inventati()
    fogli = [("Calendario", CALENDARIO), ("Classifica", CLASSIFICA), ("Quotazioni", foglio_listone(tutti)), ("Vuoto", [])]
    with pytest.raises(ValueError) as e:
        rose.estrai(fogli, Indice(tutti))
    assert str(e.value) == ("Nel file non ho trovato rose. Ho saltato i fogli che sono listone, calendario o classifica: "
                            "«Calendario», «Classifica», «Quotazioni». Carica il file delle rose esportato dalla lega.")


@pytest.mark.parametrize("testo, tipo", [
    ("Pos,Squadra,Punti\n1,Alfa,30\n2,Beta,25\n3,Gamma,20\n", "una classifica"),
    ("1ª giornata;;;\nAlfa;66;72;Beta\nGamma;70;61;Delta\n2ª giornata;;;\nAlfa;68;64;Gamma\nBeta;71;69;Delta\n", "un calendario"),
], ids=["classifica", "calendario"])
def test_un_csv_che_non_e_una_rosa_dice_cosa_sembra(indice, testo, tipo):
    """Un CSV o un testo incollato non ha fogli: il messaggio dice che cosa sembra il file."""
    with pytest.raises(ValueError) as e:
        rose.estrai(rose.griglie_da_bytes(testo.encode()), indice)
    assert str(e.value) == f"Il file sembra {tipo}, non le rose: carica il file delle rose esportato dalla lega."


def test_excel_di_soli_fogli_non_rose_dalla_rotta_dice_quali(ambiente, tmp_path):  # noqa: F811
    """Il messaggio arriva intero all'app (non quello generico «La richiesta non è valida»)."""
    a, _ = nuovo_utente("utentea")
    contenuto = _excel(tmp_path, {"Calendario": CALENDARIO, "Classifica": CLASSIFICA}).read_bytes()
    r = a.post("/api/rose/file", files={"file": ("lega.xlsx", contenuto, "application/octet-stream")})
    assert r.status_code == 400
    assert r.json()["detail"] == ("Nel file non ho trovato rose. Ho saltato i fogli che sono listone, calendario o classifica: "
                                  "«Calendario», «Classifica». Carica il file delle rose esportato dalla lega.")


# ---------------------------------------------------------------- i messaggi arrivano interi (#579)
def _limite_del_server() -> int:
    """Quanti caratteri di un messaggio d'errore dell'importazione arrivano all'app: un messaggio lunghissimo, scritto da
    rose.py, passato al gestore degli errori del server."""
    try:
        rose.decodifica(b"%PDF-1.4 finto")
    except ValueError as e:
        e.args = ("x" * 5000,)
        risposta = server._errore_valore(None, e)
    return len(json.loads(risposta.body)["detail"])


def _messaggi_scritti(modulo) -> set[str]:
    """I messaggi dei `raise ...("...")` di un modulo (le parti variabili delle f-string contano 9 caratteri)."""
    albero = ast.parse(Path(modulo.__file__).read_text(encoding="utf-8"))
    costanti = {n.targets[0].id: n.value for n in albero.body
                if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name)}

    def testo(n):
        if isinstance(n, ast.Name) and n.id in costanti:
            return testo(costanti[n.id])
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            return n.value
        if isinstance(n, ast.JoinedStr):
            return "".join(v.value if isinstance(v, ast.Constant) else "x" * 9 for v in n.values)
        return None
    return {s for n in ast.walk(albero) if isinstance(n, ast.Raise) and isinstance(n.exc, ast.Call) and n.exc.args
            if (s := testo(n.exc.args[0]))}


def test_nessun_messaggio_dell_importazione_viene_tagliato(indice):
    limite = _limite_del_server()
    messaggi = _messaggi_scritti(rose) | _messaggi_scritti(importa_sicuro) | {rose.NESSUNA_ROSA}
    assert rose.NESSUNA_ROSA in messaggi and len(messaggi) > 15
    fogli = [(f"{k} Calendario con un nome lunghissimo", CALENDARIO) for k in range(rose.MAX_FOGLI + 3)]
    with pytest.raises(ValueError) as e:                                   # il più lungo possibile: tanti fogli dai nomi lunghi
        rose.estrai(fogli, indice)
    messaggi.add(str(e.value))
    assert {m: len(m) for m in messaggi if len(m) > limite} == {}


def test_il_messaggio_senza_rose_arriva_intero(ambiente):  # noqa: F811
    a, _ = nuovo_utente("utentea")
    r = a.post("/api/rose/testo", json={"testo": "Data;Nota\n1 settembre;Asta di riparazione\n2 settembre;Mercato chiuso\n"})
    assert r.status_code == 400 and r.json()["detail"] == rose.NESSUNA_ROSA


# ---------------------------------------------------------------- più fogli del tetto: mai tagliati in silenzio (#662)
DODICI = ["Lupi Grigi", "Orsi Bianchi", "Gufi Neri", "Volpi Rosse", "Aquile Blu", "Falchi Verdi",
          "Tigri Gialle", "Leoni Rossi", "Cervi Bianchi", "Lepri Nere", "Delfini Blu", "Squali Grigi"]
TAGLIO = "Ho letto solo i primi 10 fogli su 12"


def _excel_dodici(cartella):
    """Una lega da 12 squadre con un foglio per squadra: due fogli oltre il tetto (rose.MAX_FOGLI = 10)."""
    return _excel(cartella, {nome: [[nome], ["P", "Sommer", 10], ["D", "Bastoni", 15]] for nome in DODICI})


@pytest.mark.parametrize("leggi", [rose.leggi_griglie, importa_sicuro.leggi_excel], ids=["senza-account", "con-account"])
def test_chi_legge_l_excel_dice_quanti_fogli_ha(tmp_path, leggi):
    griglie = leggi(_excel_dodici(tmp_path))
    assert len(griglie) == rose.MAX_FOGLI == 10                    # il tetto resta
    assert rose.avviso_fogli(griglie).startswith(TAGLIO)
    assert rose.avviso_fogli(leggi(_excel(tmp_path, {n: [[n], ["P", "Sommer", 10]] for n in DODICI[:10]}))) is None


def test_excel_con_piu_fogli_del_tetto_lo_dice_e_non_toglie_squadre(ambiente, tmp_path):  # noqa: F811
    a, _ = nuovo_utente("utentea")
    file = {"file": ("lega.xlsx", _excel_dodici(tmp_path).read_bytes(), "application/octet-stream")}
    r = a.post("/api/rose/anteprima/file", files=file)
    assert r.status_code == 200, r.text
    assert r.json()["totale_squadre"] == 10 and any(x.startswith(TAGLIO) for x in r.json()["avvisi"])
    r = a.post("/api/rose/file", files=file)                      # le squadre degli altri fogli non si toccano: si salva, e lo dice
    assert r.status_code == 200, r.text
    assert any(x.startswith(TAGLIO) for x in r.json()["avvisi"])
    for rotta in ("/api/rose/anteprima/file", "/api/rose/file"):   # «togli le squadre che non sono nel file»: toglierebbe anche quelle
        r = a.post(f"{rotta}?sostituisci_tutto=true", files=file)
        assert r.status_code == 400 and "12 fogli" in r.json()["detail"], r.text
    assert len(a.get("/api/squadre").json()) == 10


def test_excel_con_piu_fogli_del_tetto_dalla_riga_di_comando(tmp_path, calciatori, monkeypatch, capsys):
    """`python -m fanta importa`: lo stesso avviso, e con --sostituisci-tutto si ferma senza salvare."""
    import argparse
    import shutil

    from fanta import __main__ as comandi
    regole = tmp_path / "regole.json"
    shutil.copy(Path(comandi.__file__).parent.parent / "lega" / "esempio" / "regole.json", regole)
    monkeypatch.setattr(comandi, "FILE_REGOLE", regole)
    monkeypatch.setattr(comandi, "FILE_ROSE", tmp_path / "rose.json")
    monkeypatch.setattr(comandi, "FILE_MOVIMENTI", tmp_path / "movimenti.json")
    monkeypatch.setattr(comandi.listone, "carica", lambda *a, **k: (calciatori, "oggi"))
    file = str(_excel_dodici(tmp_path))
    with pytest.raises(SystemExit) as e:
        comandi.cmd_importa(argparse.Namespace(file=file, sostituisci_tutto=True))
    assert "12 fogli" in str(e.value) and not (tmp_path / "rose.json").exists()
    comandi.cmd_importa(argparse.Namespace(file=file, sostituisci_tutto=False))
    assert TAGLIO in capsys.readouterr().out


def test_excel_con_piu_fogli_del_tetto_senza_account(dati_isolati, calciatori, tmp_path, monkeypatch):
    monkeypatch.delenv("FANTA_MULTIUTENTE", raising=False)
    monkeypatch.setattr(server.listone, "carica", lambda *a, **k: (calciatori, "oggi"))
    from test_account_http import cliente
    r = cliente().post("/api/rose/anteprima/file",
                       files={"file": ("lega.xlsx", _excel_dodici(tmp_path).read_bytes(), "application/octet-stream")})
    assert r.status_code == 200, r.text
    assert any(x.startswith(TAGLIO) for x in r.json()["avvisi"])
