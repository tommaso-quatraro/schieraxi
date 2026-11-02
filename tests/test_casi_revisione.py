"""I casi limite trovati dalla revisione del codice della fase 1: ognuno prima falliva in silenzio."""
import json

import pytest

from fanta import lega, listone, regole, rose
from fanta.regole import Regole

ROSA_PICCOLA = {"P": 1, "D": 1, "C": 1, "A": 1}


def _estrai(testo, indice, rosa=None):
    avvisi = []
    squadre = rose.estrai([("testo", rose.griglia_da_testo(testo))], indice, rosa, avvisi)
    return {s.nome: s for s in squadre}, avvisi


# 1. un import parziale non deve cancellare le altre squadre
def test_import_parziale_tiene_le_altre_squadre(indice):
    tutte = lega.da_import(rose.estrai([("ROSE", [["Alfa", "costo", None, "Beta", "costo"],
                                                  ["Sommer", 1, None, "Kean", 2]])], indice))
    tutte.mia_squadra = "Alfa"
    solo_a = rose.estrai([("ROSE", [["Alfa", "costo"], ["Carnesecchi", 5]])], indice)
    unite = lega.da_import(solo_a, tutte)
    assert [s.nome for s in unite.squadre] == ["Alfa", "Beta"]
    assert unite.squadra("Alfa").giocatori[0].id == 1          # A aggiornata
    assert unite.squadra("Beta").giocatori[0].id == 14         # B intatta
    assert unite.mia_squadra == "Alfa"
    sostituite = lega.da_import(solo_a, tutte, sostituisci_tutto=True)
    assert [s.nome for s in sostituite.squadre] == ["Alfa"]


def test_copia_di_riserva(tmp_path, indice):
    f = tmp_path / "rose.json"
    r = lega.da_import(rose.estrai([("ROSE", [["Alfa", "costo"], ["Sommer", 1]])], indice))
    lega.salva(r, f)
    lega.salva(lega.Rose(), f, copia_di_riserva=True)
    assert lega.carica(f.with_name("rose.json.bak")) == r


# 2. un nome non trovato non deve agganciarsi a un altro giocatore senza avviso
def test_somigliante_con_ruolo_diverso_non_accettato(indice):
    e = indice.cerca("Martinez", ruolo="D")       # i due Martinez sono un attaccante e un portiere: nessun difensore
    assert not e.trovato and e.metodo == "ambiguo"
    e = indice.cerca("Martinex L.", ruolo="D")    # solo somigliante a "Martinez L." (attaccante)
    assert not e.trovato and e.metodo == "ambiguo"


def test_nome_esatto_con_ruolo_diverso_accettato_con_avviso(indice):
    e = indice.cerca("Kean", squadra="JUV", ruolo="C")
    assert e.calciatore.id == 14 and "ruolo diverso" in e.avviso and "squadra diversa" in e.avviso
    # «Thuram» con ruolo e squadra di «Thuram K.»: l'iniziale si è persa, è un dubbio tra i due (prima quello che torna), mai sicuro
    e = indice.cerca("Thuram", squadra="JUV", ruolo="C")
    assert e.calciatore is None and e.metodo == "ambiguo" and [c.id for c in e.alternative] == [6, 7]


def test_somiglianza_segnalata_nei_controlli(indice):
    # «Pellegrino Lu.»: errore di battitura nel cognome. («Pellegrini Lo.» invece è un'altra persona: non si propone Lu.)
    assert not indice.cerca("Pellegrini Lo.").trovato
    lette = rose.estrai([("ROSE", [["Alfa", "costo"], ["Pellegrino Lu.", 3]])], indice)
    r = lega.da_import(lette)
    g = r.squadra("Alfa").giocatori[0]
    assert g.id == 17 and g.riconosciuto == "simile"
    assert any("Pellegrini Lu." in a and "somiglianza" in a for a in lega.controlla(r, Regole()))


def test_ambiguo_segnalato_con_alternative(indice):
    r = lega.da_import(rose.estrai([("ROSE", [["Alfa", "costo"], ["Rossi", 3]])], indice))
    g = r.squadra("Alfa").giocatori[0]
    assert g.id is None and "Rossi (D, GEN)" in g.avviso and "Rossi (A, LEC)" in g.avviso


# 3. giocatore non riconosciuto nel testo "un valore per riga"
def test_un_valore_per_riga_con_giocatore_sconosciuto(indice):
    squadre, _ = _estrai("Team A\nP\nSommer\nINT\n10\nD\nPinco Pallo\n5\nC\nBarella\nINT\n7\n", indice)
    assert list(squadre) == ["Team A"]
    righe = squadre["Team A"].righe
    assert [r.testo for r in righe] == ["Sommer", "Pinco Pallo", "Barella"]
    assert (righe[1].ruolo, righe[1].costo, righe[1].esito.trovato) == ("D", 5, False)


# 4. intestazioni sconosciute non devono diventare nomi di squadra
def test_intestazioni_composte(indice):
    testo = ("Team A\nRuolo\tNome calciatore\tSquadra Serie A\tCosto\nP\tSommer\tInter\t10\n"
             "Team B\nRuolo\tNome calciatore\tSquadra Serie A\tCosto\nA\tKean\tFiorentina\t20\n")
    squadre, _ = _estrai(testo, indice)
    assert set(squadre) == {"Team A", "Team B"}
    assert squadre["Team A"].righe[0].esito.calciatore.id == 2
    assert squadre["Team B"].righe[0].esito.calciatore.id == 14


# 5. squadre affiancate senza colonna vuota: avviso invece di silenzio
def test_affiancate_senza_separatore_avvisa(indice):
    _, avvisi = _estrai("Team A\tcosto\tTeam B\tcosto\nSommer\t1\tKean\t2\n", indice)
    assert any("colonna vuota" in a for a in avvisi)


# 6. il costo si prende dalla colonna "costo", non dal primo numero
def test_costo_dalla_colonna_giusta(indice):
    squadre, _ = _estrai("Team A\nCalciatore\tQt\tCosto\nSommer\t15\t1\nKean\t30\t44\n", indice)
    assert [r.costo for r in squadre["Team A"].righe] == [1, 44]


# 7. regole: tipi sbagliati rifiutati con un messaggio chiaro
@pytest.mark.parametrize("chiave,valore", [
    ("voto_senza_sostituto", "ciao"),
    ("modificatore_difesa.soglie", '[["a", "b"]]'),
    ("rosa", '{"P": "3", "D": 8, "C": 8, "A": 6}'),
    ("moduli", "[343]"),
    ("panchina.cambio_modulo", "1"),
    ("rosa", "3"),
])
def test_regole_tipi_sbagliati(chiave, valore):
    with pytest.raises(ValueError):
        regole.imposta(Regole(), chiave, valore)


def test_regole_file_con_gruppo_sbagliato(tmp_path):
    f = tmp_path / "regole.json"
    f.write_text(json.dumps({"bonus": 5}), encoding="utf-8")
    with pytest.raises(ValueError):
        regole.carica(f)


# 8. crediti spesi e crediti residui non si confondono
def test_crediti_spesi_e_residui(indice):
    squadre, _ = _estrai("Team A\nSommer\t10\nCrediti spesi 480\nCrediti residui: 20\n", indice)
    assert (squadre["Team A"].totale_speso, squadre["Team A"].crediti_residui) == (480, 20)


def test_crediti_sulla_riga_del_nome(indice):
    squadre, _ = _estrai("Team A\tCrediti: 10\nSommer\t10\n", indice)
    assert squadre["Team A"].crediti_residui == 10


# 9. un titolo sopra le rose non crea una squadra vuota
def test_titolo_non_diventa_squadra(indice):
    squadre, _ = _estrai("Rose lega XYZ\n\nTeam A\nSommer\t10\n", indice)
    assert list(squadre) == ["Team A"]


# 10. cache del listone rovinata: vale come assente invece di bloccare tutto
def test_cache_rovinata(tmp_path):
    f = tmp_path / "listone.json"
    f.write_text('{"scaricato": "2026-10-26T10:00:00", "calciatori": [{"id": 1', encoding="utf-8")
    assert listone._leggi_cache(f) is None
    f.write_text(json.dumps({"scaricato": "2026-10-26T10:00:00", "calciatori": [{"campo_vecchio": 1}]}),
                 encoding="utf-8")
    assert listone._leggi_cache(f) is None
