from fanta import lega, listone, rose
from fanta.regole import Regole

ROSA_PICCOLA = {"P": 1, "D": 1, "C": 1, "A": 1}


def _rose(indice, griglia):
    return lega.da_import(rose.estrai([("ROSE", griglia)], indice, ROSA_PICCOLA))


def test_controlli_rosa(indice):
    griglia = [["Alfa", "costo", None, "Beta", "costo"],
               ["Sommer", 1, None, "Carnesecchi", 1],
               ["Bastoni", 1, None, "Dimarco", 1],
               ["Barella", 1, None, "Barella", 1],      # Barella in due squadre
               ["Kean", 1, None, None, None]]           # B ha un attaccante in meno
    r = _rose(indice, griglia)
    avvisi = lega.controlla(r, Regole(rosa=ROSA_PICCOLA))
    assert any("Barella è in più squadre" in a for a in avvisi)
    assert any(a.startswith("Beta: rosa diversa") and "A 0/1" in a for a in avvisi)
    assert not any(a.startswith("Alfa:") for a in avvisi)


def test_controlli_rosa_giocatore_ripetuto_nella_stessa_squadra(indice):
    # il lettore ora toglie i doppioni (test_rose.py); qui una rosa salvata prima, con Barella due volte
    griglia = [["Alfa", "costo"], ["Sommer", 1], ["Bastoni", 1], ["Barella", 1], ["Kean", 1]]
    r = _rose(indice, griglia)
    r.squadre[0].giocatori.append(next(g for g in r.squadre[0].giocatori if g.nome == "Barella"))
    avvisi = lega.controlla(r, Regole(rosa=ROSA_PICCOLA))
    assert any(a.startswith("Alfa: Barella compare 2 volte") for a in avvisi)
    assert not any("in più squadre" in a for a in avvisi)          # prima: «Barella è in più squadre: Alfa, Alfa»


def test_salva_carica_e_mia_squadra(tmp_path, indice):
    r = _rose(indice, [["Real Esempio", "costo"], ["Sommer", 1], ["Bastoni", 2], ["Barella", 3], ["Kean", 4]])
    r.mia_squadra = r.squadra("real").nome
    f = tmp_path / "rose.json"
    lega.salva(r, f)
    di_nuovo = lega.carica(f)
    assert di_nuovo == r and di_nuovo.mia_squadra == "Real Esempio"
    # reimportando, la scelta della mia squadra resta
    assert lega.da_import(rose.estrai([("ROSE", [["Real Esempio", "costo"], ["Kean", 1]])], indice), di_nuovo).mia_squadra == "Real Esempio"


def test_listone_da_html():
    righe = "".join(
        f'<tr class="player-row" data-filter-role-classic="d" data-filter-role-mantra="dc">'
        f'<th><a class="player-name player-link" href="https://www.fantacalcio.it/serie-a/squadre/inter/gioc-{i}/{i}">'
        f'<span>Gioc {i}</span></a></th><td data-col-key="sq">INT</td><td data-col-key="c_qi">5</td>'
        f'<td data-col-key="c_qa">{i % 40}</td><td data-col-key="c_fvm">10</td></tr>'
        for i in range(1, 351))
    cal = listone.analizza_html(f"<table><tbody>{righe}</tbody></table>")
    assert len(cal) == 350
    c = cal[6]
    assert (c.id, c.nome, c.ruolo, c.squadra, c.squadra_slug, c.quotazione) == (7, "Gioc 7", "D", "INT", "inter", 7)
