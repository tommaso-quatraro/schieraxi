"""Excel esportati dalla lega con altri fogli oltre alle rose (#543): listone, calendario e classifica non sono rose e si saltano
in silenzio (niente squadre finte, niente avvisi); le rose dello stesso file si leggono come sempre.
Squadre, persone e giocatori inventati; i file stanno in cartelle temporanee."""
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


# ---------------------------------------------------------------- un foglio alla volta: nessuna squadra, nessun avviso
def test_foglio_del_listone_si_salta(calciatori):
    """Centinaia di giocatori con le quotazioni, senza nomi di squadra in mezzo: prima diventavano una squadra sola (e con gli
    account l'importazione si fermava: più di 40 giocatori)."""
    tutti = calciatori + giocatori_inventati()
    avvisi = []
    assert rose.estrai([("Tutti", foglio_listone(tutti))], Indice(tutti), avvisi=avvisi) == []
    assert avvisi == []


def test_foglio_del_calendario_si_salta(indice):
    """Giornate e coppie di fantasquadre con i punteggi: prima ogni giornata diventava una squadra di «giocatori» non trovati."""
    avvisi = []
    assert rose.estrai([("Calendario", CALENDARIO)], indice, avvisi=avvisi) == []
    assert avvisi == []


def test_foglio_della_classifica_si_salta(indice):
    """Fantasquadre con posizione e punti: prima il titolo diventava una squadra con le altre come «giocatori»."""
    avvisi = []
    assert rose.estrai([("Classifica", CLASSIFICA)], indice, avvisi=avvisi) == []
    assert avvisi == []


# ---------------------------------------------------------------- il file intero: solo le rose
@pytest.mark.parametrize("leggi", [rose.leggi_griglie, importa_sicuro.leggi_excel], ids=["senza-account", "con-account"])
def test_excel_con_rose_listone_calendario_e_classifica_legge_solo_le_rose(tmp_path, calciatori, leggi):
    """Le stesse fantasquadre compaiono anche in calendario e classifica: le loro rose non prendono «giocatori» da quei fogli."""
    tutti = calciatori + giocatori_inventati()
    avvisi = []
    squadre = rose.estrai(leggi(_excel_misto(tmp_path, calciatori)), Indice(tutti), avvisi=avvisi)
    assert _riassunto(squadre) == {"Real Esempio": ([1, 3, 12, 7], 12), "FC Under": ([11, 4, 6, 8], 3)}
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
