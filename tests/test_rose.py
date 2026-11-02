import pytest
import openpyxl

from fanta import rose

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
