from pathlib import Path

import pytest
import openpyxl

from fanta import rose
from fanta.listone import Calciatore
from fanta.nomi import Indice

ROSA_PICCOLA = {"P": 1, "D": 1, "C": 1, "A": 1}


def _per_nome(squadre):
    return {s.nome: s for s in squadre}


def test_excel_leghe_squadre_affiancate(tmp_path, indice):
    """Come l'export di Leghe Fantacalcio: squadra|costo, giocatori in ordine di ruolo, totale."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "ROSE"
    for riga in [
        ["Real Esempio", "costo", None, "FC Under", "costo"],
        ["Carnesecchi", 43, None, "Martinez Jo.", 58],
        ["Bastoni", 17, None, "N'Dicka", 12],
        ["Barella", 35, None, "Thuram K.", 1],
        ["Thuram", 104, None, "Esposito Se.", 21],
        ["totale", 199, None, "totale", 92],
    ]:
        ws.append(riga)
    f = tmp_path / "rose.xlsx"
    wb.save(f)

    squadre = _per_nome(rose.estrai(rose.leggi_griglie(f), indice, ROSA_PICCOLA))
    assert set(squadre) == {"Real Esempio", "FC Under"}
    b = squadre["Real Esempio"]
    assert [r.esito.calciatore.id for r in b.righe] == [1, 3, 12, 7]
    assert [r.costo for r in b.righe] == [43, 17, 35, 104]
    assert [r.ruolo for r in b.righe] == ["P", "D", "C", "A"]   # dedotti dalla posizione
    assert b.totale_speso == 199
    u = squadre["FC Under"]
    assert [r.esito.calciatore.id for r in u.righe] == [11, 4, 6, 8]
    assert u.totale_speso == 92


def test_omonimo_risolto_dalla_posizione(tmp_path, indice):
    ws_righe = [["Squadra X", "costo"], ["Sommer", 1], ["Rossi", 2], ["Barella", 3], ["Kean", 4]]
    s = rose.estrai([("ROSE", ws_righe)], indice, ROSA_PICCOLA)[0]
    assert s.righe[1].esito.calciatore.id == 15       # il Rossi difensore


def test_tabella_con_colonne_ruolo_squadra_costo_e_crediti(indice):
    testo = (
        "La Banda\n"
        "Ruolo\tCalciatore\tSquadra\tCosto\n"
        "P\tSommer\tInter\t10\n"
        "D\tRossi\tGenoa\t5\n"
        "C\tLaurienté\tSassuolo\t20\n"
        "A\tPinco Pallino\tEstero\t3\n"
        "Crediti residui: 12\n"
        "I Bomber\n"
        "Ruolo\tCalciatore\tSquadra\tCosto\n"
        "A\tRossi\tLecce\t7\n"
    )
    squadre = _per_nome(rose.estrai([("testo", rose.griglia_da_testo(testo))], indice, ROSA_PICCOLA))
    banda = squadre["La Banda"]
    assert [r.testo for r in banda.righe] == ["Sommer", "Rossi", "Laurienté", "Pinco Pallino"]
    assert banda.righe[1].esito.calciatore.id == 15          # ruolo D dal file
    assert not banda.righe[3].esito.trovato                  # giocatore non nel listone, ma tenuto
    assert banda.righe[3].ruolo == "A" and banda.righe[3].costo == 3
    assert banda.crediti_residui == 12
    assert squadre["I Bomber"].righe[0].esito.calciatore.id == 16


def test_riga_dell_allenatore_non_diventa_il_nome_della_squadra(indice):
    """Copiando la pagina delle rose sotto il nome della squadra c'è chi la allena: il nome resta quello della squadra."""
    testo = (
        "La Banda\nAllenatore: marco\nCrediti residui: 12\nRuolo\tCalciatore\tSquadra\tCosto\n"
        "P\tSommer\tInter\t10\nD\tRossi\tGenoa\t5\n\n"
        "I Bomber\nPresidente - luca\nA\tKean\tFiorentina\t30\n"
    )
    squadre = _per_nome(rose.estrai([("testo", rose.griglia_da_testo(testo))], indice, ROSA_PICCOLA))
    assert sorted(squadre) == ["I Bomber", "La Banda"]
    assert len(squadre["La Banda"].righe) == 2 and squadre["La Banda"].crediti_residui == 12
    assert squadre["I Bomber"].righe[0].esito.calciatore.id == 14
    # anche con un valore per riga
    testo = "Real Fagiolo\nAllenatore: marco\nP\nSommer\nInter\n10\nI Bomber\nManager: luca\nA\nKean\nFiorentina\n30\n"
    assert sorted(_per_nome(rose.estrai([("testo", rose.griglia_da_testo(testo))], indice))) == ["I Bomber", "Real Fagiolo"]


def test_un_valore_per_riga(indice):
    testo = "Real Esempio\nP\nSommer\nInter\n10\nD\nBastoni\nInter\n15\nI Bomber\nA\nKean\nFiorentina\n30\n"
    squadre = _per_nome(rose.estrai([("testo", rose.griglia_da_testo(testo))], indice))
    assert [(r.esito.calciatore.id, r.ruolo, r.costo) for r in squadre["Real Esempio"].righe] == [(2, "P", 10), (3, "D", 15)]
    assert [(r.esito.calciatore.id, r.costo) for r in squadre["I Bomber"].righe] == [(14, 30)]


DATI = Path(__file__).parent / "dati"


def _da_testo(testo, indice, rosa=None, **k):
    return _per_nome(rose.estrai([("testo", rose.griglia_da_testo(testo))], indice, rosa, **k))


def test_uno_per_riga_un_nome_non_riconosciuto_non_apre_una_squadra(indice):
    """Collaudo del 26/11: nel testo con un nome per riga «Maignan» e «D'Ambrosio» (non nel listone) diventavano squadre e il
    nome in fondo spariva. Un nome non riconosciuto dentro una squadra è un giocatore non trovato; la squadra nuova comincia dopo
    la riga vuota."""
    squadre = _da_testo((DATI / "rose_uno_per_riga.txt").read_text(encoding="utf-8"), indice)
    assert list(squadre) == ["Real Finzione", "Sporting Fantasia"]
    righe = squadre["Real Finzione"].righe
    assert [r.testo for r in righe] == ["Carnesecchi", "Maignan", "Bastoni", "D'Ambrosio", "Dimarco", "Barella", "Mkhitaryan",
                                        "Kean", "Pio Esposito"]
    assert [r.testo for r in righe if r.esito.metodo == "non trovato"][:3] == ["Maignan", "D'Ambrosio", "Mkhitaryan"]
    assert [r.testo for r in squadre["Sporting Fantasia"].righe] == ["Thuram", "Laurienté"]


def test_uno_per_riga_i_crediti_si_leggono_anche_senza_club_ne_costo(indice):
    """Un nome per riga, senza club né costo accanto a nessun giocatore: «Crediti residui: 37» si perdeva in silenzio."""
    squadre = _da_testo("Alfa\nSommer\nBastoni\nCrediti residui: 37\n\nBeta\nKean\nCrediti residui: 12\n", indice)
    assert list(squadre) == ["Alfa", "Beta"]
    assert (squadre["Alfa"].crediti_residui, squadre["Beta"].crediti_residui) == (37, 12)
    assert [r.testo for r in squadre["Alfa"].righe] == ["Sommer", "Bastoni"]
    # con il club e il costo accanto ai giocatori si leggevano già, e restano
    squadre = _da_testo("Alfa\nSommer\nInter\n10\nCrediti residui: 37\n", indice)
    assert squadre["Alfa"].crediti_residui == 37 and squadre["Alfa"].righe[0].costo == 10


def test_uno_per_riga_senza_riga_vuota_la_squadra_nuova_dopo_una_rosa_completa(indice):
    # senza righe vuote: un nome sconosciuto dopo una rosa già completa è la squadra dopo; prima, è un giocatore non trovato
    squadre = _da_testo("Alfa\nSommer\nBastoni\nBarella\nKean\nBeta\nThuram\nDimarco\n", indice, ROSA_PICCOLA)
    assert list(squadre) == ["Alfa", "Beta"] and len(squadre["Beta"].righe) == 2
    squadre = _da_testo("Alfa\nSommer\nPinco Pallino\nBarella\nKean\n", indice, ROSA_PICCOLA)
    assert list(squadre) == ["Alfa"] and [r.testo for r in squadre["Alfa"].righe][1] == "Pinco Pallino"


def test_uno_per_riga_titolo_riconosciuto_dall_allenatore_o_dalle_squadre_salvate(indice):
    assert list(_da_testo("Alfa\nSommer\nBeta\nAllenatore: luca\nKean\n", indice)) == ["Alfa", "Beta"]
    assert list(_da_testo("Alfa\nSommer\nBeta\nKean\n", indice, squadre_note={"Beta"})) == ["Alfa", "Beta"]
    assert list(_da_testo("Alfa\nSommer\nBeta\nKean\n", indice)) == ["Alfa"]


FORSE_SQUADRA = ("Alfa: manca una riga vuota fra le squadre? «Pantere» non è nel listone: se è il nome di una squadra, lascia "
                 "una riga vuota prima e controlla di nuovo.")


def test_uno_per_riga_senza_righe_vuote_avvisa_che_forse_manca_una_riga_vuota(indice):
    """Revisione della #939: squadre una sotto l'altra senza riga vuota diventano una squadra sola. Un nome sconosciuto in mezzo
    ai giocatori potrebbe essere il nome della seconda: l'anteprima lo chiede. Con le righe vuote fra le squadre no: chi le usa
    sa come separarle, e un giocatore sconosciuto ha già la sua riga fra i non trovati."""
    avvisi = []
    squadre = _da_testo("Alfa\nSommer\nBastoni\nPantere\nKean\nDimarco\n", indice, avvisi=avvisi)
    assert list(squadre) == ["Alfa"] and avvisi == [FORSE_SQUADRA]
    avvisi = []
    _da_testo("Alfa\nSommer\nPantere\nBastoni\nKean\n\nBeta\nDimarco\n", indice, avvisi=avvisi)
    assert avvisi == []
    avvisi = []                                                    # rosa più lunga di quella delle regole: anche con le righe vuote
    _da_testo("Alfa\nSommer\nBastoni\nPantere\nKean\nDimarco\n\nBeta\nBarella\n", indice, ROSA_PICCOLA, avvisi=avvisi)
    assert avvisi == [FORSE_SQUADRA]


@pytest.mark.parametrize("testo", ["Alfa\nSommer 15\nPinco Pallino 3\nBastoni 20\nKean 30\n",
                                   "Alfa\n1. Sommer\n2. Pinco Pallino\n3. Bastoni\n4. Kean\n",
                                   "Alfa\n\nSommer\n\nPinco Pallino\n\nBastoni\n\nKean\n"])
def test_uno_per_riga_costo_numero_o_riga_vuota_fra_i_giocatori_non_aprono_squadre(indice, testo):
    # revisione della #939: il costo sulla stessa riga, l'elenco numerato e una riga vuota fra ogni giocatore
    squadre = _da_testo(testo, indice)
    assert list(squadre) == ["Alfa"], testo
    assert len(squadre["Alfa"].righe) == 4 and "Pinco Pallino" in squadre["Alfa"].righe[1].testo


# ---------- fantasquadre che si chiamano come una squadra di Serie A («Roma», «AS Roma», «Inter») ----------
def _giocatori(squadra):
    return [r.testo for r in squadra.righe]


def test_excel_affiancate_squadra_che_si_chiama_come_un_club(indice):
    """Nell'Excel con le squadre affiancate «Roma | costo» non era un titolo: i suoi giocatori finivano in «Squadra senza nome»,
    e quelli di «Inter» (sotto «Lupi», dopo il totale e una riga vuota) dentro «Lupi». In cima a un blocco, dopo il totale o
    dopo una riga vuota il nome di un club è il titolo di una squadra."""
    griglia = [
        ["Lupi", "costo", None, "Roma", "costo"],
        ["Carnesecchi", 43, None, "Martinez Jo.", 58],
        ["Bastoni", 17, None, "N'Dicka", 12],
        ["totale", 60, None, "totale", 70],
        [None, None, None, None, None],
        ["AS Roma", "costo", None, "Tigri", "costo"],
        ["Sommer", 10, None, "Barella", 35],
        ["Kean", 30, None, "Thuram", 20],
        ["totale", 40, None, "totale", 55],
    ]
    avvisi = []
    squadre = _per_nome(rose.estrai([("ROSE", griglia)], indice, avvisi=avvisi))
    assert {n: _giocatori(s) for n, s in squadre.items()} == {
        "Lupi": ["Carnesecchi", "Bastoni"], "Roma": ["Martinez Jo.", "N'Dicka"],
        "AS Roma": ["Sommer", "Kean"], "Tigri": ["Barella", "Thuram"]}
    assert squadre["Lupi"].totale_speso == 60 and squadre["AS Roma"].totale_speso == 40
    assert avvisi == []


def test_testo_uno_per_riga_squadra_che_si_chiama_come_un_club(indice):
    """Nel testo con un nome per riga «Roma» dopo la riga vuota diventava la squadra di Serie A del giocatore sopra, e i giocatori
    sotto si univano alla squadra di prima, senza avviso."""
    squadre = _da_testo("Lupi\nSommer\nBastoni\n\nRoma\nKean\nThuram\n", indice)
    assert {n: _giocatori(s) for n, s in squadre.items()} == {"Lupi": ["Sommer", "Bastoni"], "Roma": ["Kean", "Thuram"]}
    assert squadre["Lupi"].righe[1].squadra is None                       # «Roma» non è la squadra di Bastoni
    # in prima riga, dopo i crediti, dopo un giocatore che ha già la sua squadra, dopo una rosa completa (solo nomi)
    assert list(_da_testo("AS Roma\nSommer\nKean\n", indice)) == ["AS Roma"]
    assert list(_da_testo("Lupi\nSommer\nCrediti residui: 5\nRoma\nKean\n", indice)) == ["Lupi", "Roma"]
    squadre = _da_testo("Lupi\nP\nSommer\nInter\n10\nInter\nA\nKean\nFiorentina\n30\n", indice)
    assert list(squadre) == ["Lupi", "Inter"] and squadre["Lupi"].righe[0].squadra == "Inter"
    assert list(_da_testo("Lupi\nSommer\nBastoni\nBarella\nKean\nRoma\nThuram\nDimarco\n", indice, ROSA_PICCOLA)) == ["Lupi", "Roma"]
    # nel testo con la squadra di Serie A sotto ogni giocatore, quella resta del giocatore
    squadre = _da_testo("Lupi\nP\nSommer\nInter\n10\nD\nN'Dicka\nRoma\n12\n", indice)
    assert list(squadre) == ["Lupi"] and [r.squadra for r in squadre["Lupi"].righe] == ["Inter", "Roma"]


def test_tabella_con_il_club_accanto_ai_giocatori_squadra_che_si_chiama_come_un_club(indice):
    """Con il club scritto sulla riga di ogni giocatore, una riga con il solo nome di un club non può essere il club di nessuno:
    è il titolo di una squadra, anche senza riga vuota prima."""
    squadre = _da_testo("Lupi\nP\tSommer\tInter\t10\nRoma\nA\tKean\tFiorentina\t30\nD\tN'Dicka\tRoma\t5\n", indice)
    assert {n: _giocatori(s) for n, s in squadre.items()} == {"Lupi": ["Sommer"], "Roma": ["Kean", "N'Dicka"]}
    assert squadre["Roma"].righe[1].squadra == "Roma"
    # una riga di giocatore senza il nome (club e costo) in mezzo alla rosa non apre una squadra che si porta via il resto
    squadre = _da_testo("Lupi\nP\tSommer\tInter\t10\n\t\tRoma\t5\nA\tKean\tFiorentina\t30\n", indice)
    assert {n: _giocatori(s) for n, s in squadre.items()} == {"Lupi": ["Sommer", "Kean"]}


def test_squadra_gia_salvata_che_si_chiama_come_un_club_e_un_titolo(indice):
    """Il nome di una squadra già salvata della lega è un titolo anche dove la struttura del file non lo dice. Senza, il testo
    resta com'era ma l'anteprima lo dice con un avviso chiaro."""
    testo = "Lupi\nSommer\nBastoni\nRoma\nKean\n"
    squadre = _da_testo(testo, indice, squadre_note={"Roma", "Lupi"})
    assert {n: _giocatori(s) for n, s in squadre.items()} == {"Lupi": ["Sommer", "Bastoni"], "Roma": ["Kean"]}
    griglia = [["Lupi", "costo"], ["Sommer", 10], ["Bastoni", 5], ["Roma", None], ["Kean", 30]]
    squadre = _per_nome(rose.estrai([("ROSE", griglia)], indice, squadre_note={"Roma"}))
    assert {n: _giocatori(s) for n, s in squadre.items()} == {"Lupi": ["Sommer", "Bastoni"], "Roma": ["Kean"]}
    avvisi = []
    squadre = _da_testo(testo, indice, avvisi=avvisi)
    assert list(squadre) == ["Lupi"] and squadre["Lupi"].club_dubbi == ["Roma"]
    assert avvisi == ["Lupi: manca una riga vuota fra le squadre? «Roma» si chiama come una squadra di Serie A e l'ho preso per "
                      "quella: se è una vostra squadra, lascia una riga vuota prima del suo nome e controlla di nuovo."]
    avvisi = []
    rose.estrai([("ROSE", griglia)], indice, avvisi=avvisi)
    assert [a.chiave for a in avvisi] == ["rose.club_forse_squadra"] and "«Roma»" in avvisi[0]


def test_listone_diviso_per_club_non_diventa_una_lega(calciatori):
    """Un foglio diviso per squadra di Serie A (un titolo per club e sotto i suoi giocatori) non è una lega con squadre che si
    chiamano come i club: si salta come il listone."""
    romanisti = [Calciatore(100 + i, nome, "C", "", "ROM", "roma", 10, 10, 100) for i, nome in enumerate(["Bacedi", "Fiorlani", "Ruschetto"])]
    indice = Indice(calciatori + romanisti)
    griglia = [["Inter", None], ["Sommer", 10], ["Bastoni", 12], ["Barella", 20], [None, None],
               ["Roma", None], ["N'Dicka", 12], ["Bacedi", 3], ["Fiorlani", 4], ["Ruschetto", 5]]
    ok = [["Lupi", "costo"], ["Kean", 3], ["Thuram", 3]]
    assert list(_per_nome(rose.estrai([("Rose", ok), ("Per club", griglia)], indice))) == ["Lupi"]
    # una lega vera con due squadre che si chiamano come i club ha giocatori di tante squadre: resta una lega
    lega_vera = [["Inter", None], ["Sommer", 10], ["Kean", 12], ["Bacedi", 20], [None, None],
                 ["Roma", None], ["N'Dicka", 12], ["Barella", 3], ["Carnesecchi", 4]]
    assert list(_per_nome(rose.estrai([("Rose", lega_vera)], indice))) == ["Inter", "Roma"]


@pytest.mark.parametrize("con_intestazione", [True, False])
def test_csv_colonna_fantasquadra_con_il_nome_di_un_club(indice, con_intestazione):
    """CSV con la fantasquadra su ogni riga: la squadra «Roma» dava il club «Roma» a tutti i suoi giocatori (con l'intestazione)
    o finiva con le altre in «Squadra senza nome» (senza)."""
    testo = ("Fantasquadra;Ruolo;Calciatore;Squadra;Costo\n" if con_intestazione else "") + (
        "Roma;P;Sommer;Inter;2\nRoma;D;Bastoni;Inter;3\nRoma;A;Kean;Fiorentina;3\n"
        "Lupi;P;Carnesecchi;Atalanta;1\nLupi;C;Barella;Inter;9\nLupi;A;Thuram;Inter;14\n")
    squadre = _per_nome(rose.estrai(rose.griglie_da_bytes(testo.encode()), indice))
    assert {n: _giocatori(s) for n, s in squadre.items()} == {"Roma": ["Sommer", "Bastoni", "Kean"],
                                                              "Lupi": ["Carnesecchi", "Barella", "Thuram"]}
    assert [r.squadra for r in squadre["Roma"].righe] == ["Inter", "Inter", "Fiorentina"]


def test_csv_con_punto_e_virgola(tmp_path, indice):
    f = tmp_path / "rose.csv"
    f.write_text("Squadra Uno;;\nCalciatore;Ruolo;Costo\nSommer;P;10\nKean;A;20\n", encoding="utf-8")
    s = rose.estrai(rose.leggi_griglie(f), indice)[0]
    assert s.nome == "Squadra Uno"
    assert [(r.esito.calciatore.id, r.ruolo, r.costo) for r in s.righe] == [(2, "P", 10), (14, "A", 20)]


def test_senza_nome_squadra_usa_il_foglio(indice):
    s = rose.estrai([("I Bomber", [["Sommer", "1"], ["Kean", "2"]])], indice)[0]
    assert s.nome == "I Bomber" and len(s.righe) == 2


def test_ruolo_non_dedotto_se_l_ordine_non_torna(indice):
    # ordine A, C, D, P: la posizione non corrisponde ai ruoli, quindi il ruolo resta quello del listone
    griglia = [["X", "costo"], ["Kean", 1], ["Barella", 1], ["Bastoni", 1], ["Sommer", 1]]
    s = rose.estrai([("ROSE", griglia)], indice, ROSA_PICCOLA)[0]
    assert all(r.ruolo is None for r in s.righe)


def test_excel_enorme_o_rovinato_non_esaurisce_la_memoria(tmp_path):
    import openpyxl
    from fanta import rose
    from fanta.rose import leggi_griglie
    f = tmp_path / "rose.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws["A1"], ws["XFD1"] = "Squadra", "lontanissima"                   # una cella a 16384 colonne di distanza
    for i in range(2, 2000):
        ws.cell(row=i, column=1, value=f"g{i}")
    for k in range(15):
        wb.create_sheet(f"extra{k}")
    wb.save(f)
    fogli = leggi_griglie(f)
    assert len(fogli) == rose.MAX_FOGLI and len(fogli[0][1]) <= rose.MAX_RIGHE and max(len(r) for r in fogli[0][1]) <= rose.MAX_COLONNE
    rovinato = tmp_path / "rotto.xlsx"
    rovinato.write_bytes(b"questo non e' un file excel")
    with pytest.raises(ValueError, match="non leggibile"):
        leggi_griglie(rovinato)


def test_numeri_assurdi_nelle_celle_si_scartano():
    from fanta.rose import _intero
    assert _intero("25") == 25 and _intero("12,5") == 12 and _intero("0") == 0
    assert _intero("-50") is None and _intero("1e400") is None and _intero("9" * 400) is None and _intero("abc") is None


def test_doppione_nella_stessa_rosa_tenuto_una_volta(indice):
    """Una riga incollata due volte non deve dare un giocatore in più (formazione e scambi farebbero i conti con 26)."""
    testo = "Mia\nP\tSommer\t10\nA\tKean\t20\nA\tKean\t20\nAltra\nA\tKean\t5\n"
    avvisi = []
    squadre = _per_nome(rose.estrai([("testo", rose.griglia_da_testo(testo))], indice, avvisi=avvisi))
    assert [r.esito.calciatore.id for r in squadre["Mia"].righe] == [2, 14]
    assert [r.esito.calciatore.id for r in squadre["Altra"].righe] == [14]       # in un'altra squadra non è un doppione
    assert any(a.startswith("Mia: Kean compare due volte") for a in avvisi)
