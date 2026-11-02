"""Asta (stime) e passaggio di stagione."""
import pandas as pd

from fanta import asta, lega, scambi, stagione
from fanta.regole import Regole


def _valori():
    tab = {}
    righe = []
    i = 1
    for ruolo, n, base in (("P", 4, 5.0), ("D", 12, 5.5), ("C", 12, 6.0), ("A", 10, 6.5)):
        for k in range(n):
            tab[i] = (ruolo, 0.9, base + (n - k) * 0.1)
            righe.append({"id": i, "nome": f"{ruolo}{k}", "ruolo": ruolo, "squadra": "X", "quotazione": 10 + (n - k)})
            i += 1
    info = pd.DataFrame(righe).set_index("id")
    return scambi.Valori([1, 2, 3], 10, [tab, tab, tab], info)


def test_asta_divide_il_budget_in_proporzione_al_valore():
    p = asta.piano(_valori(), Regole(), squadre=2)
    assert p["crediti"] == 500 and [r["ruolo"] for r in p["ruoli"]] == ["P", "D", "C", "A"]
    assert abs(sum(r["quota"] for r in p["ruoli"]) - 1) < 0.01
    assert sum(r["crediti"] for r in p["ruoli"]) in range(430, 450)               # 500 meno la panchina (12%)
    attaccanti = next(r for r in p["ruoli"] if r["ruolo"] == "A")["giocatori"]
    assert attaccanti[0]["prezzo"] >= attaccanti[-1]["prezzo"] >= 1 and attaccanti[0]["nome"] == "A0"


def test_passaggio_di_stagione_archivia_e_riparte(tmp_path):
    cartella = tmp_path / "lega"
    cartella.mkdir()
    rose = lega.Rose([lega.Squadra("Mia", [lega.GiocatoreRosa(1, "Castro", "A", "ROM", 20)], 3), lega.Squadra("Altra", [])], "Mia", "", "2026-27")
    file = cartella / "rose.json"
    lega.salva(rose, file)
    (cartella / "regole.json").write_text("{}", encoding="utf-8")
    scelta = tmp_path / "scelte.json"
    scelta.write_text("[]", encoding="utf-8")
    assert stagione.stato(rose, file, "2026-27")["nuova"] is False
    s = stagione.stato(rose, file, "2027-28")
    assert s["nuova"] is True and s["rose"] == "2026-27"
    r = stagione.archivia_e_riparti(rose, file, "2027-28", 500, [scelta])
    assert r["squadre"] == 2 and (cartella / "archivio" / "2026-27" / "rose.json").exists() and (cartella / "archivio" / "2026-27" / "scelte.json").exists()
    assert not scelta.exists()
    nuove = lega.carica(file)
    assert nuove.stagione == "2027-28" and nuove.mia_squadra == "Mia" and all(not s.giocatori and s.crediti_residui == 500 for s in nuove.squadre)
    assert stagione.stato(nuove, file, "2027-28")["nuova"] is False                 # rose vuote: niente banner


def test_riparazione_di_febbraio_solo_svincolati_e_per_te():
    v = _valori()
    mie = [lega.GiocatoreRosa(i, f"g{i}", v.info.at[i, "ruolo"], "X") for i in (1, 5, 17, 29)]       # P, D, C, A: i più deboli di ogni reparto sono gli ultimi della lista
    altre = [lega.GiocatoreRosa(i, f"g{i}", v.info.at[i, "ruolo"], "X") for i in (2, 6, 18, 30)]
    rose = lega.Rose([lega.Squadra("Mia", mie, 40), lega.Squadra("Altra", altre, 25)], "Mia")
    p = asta.piano_riparazione(v, Regole(), rose)
    assert p["tuoi_crediti"] == 40 and p["crediti_lega"] == 65 and p["posti_liberi"] > 0
    ids = {g["id"] for r in p["ruoli"] for g in r["giocatori"]}
    assert not ids & {1, 2, 5, 6, 17, 18, 29, 30}                       # chi è già in una rosa non è svincolato
    assert all(g["prezzo"] <= 65 for r in p["ruoli"] for g in r["giocatori"])
    assert all(g["prezzo"] <= 40 and g["miglioramento"] > 0 for g in p["per_te"])
    senza_crediti = lega.Rose([lega.Squadra("Mia", mie), lega.Squadra("Altra", altre)], "Mia")
    q = asta.piano_riparazione(v, Regole(), senza_crediti)
    assert q["crediti_lega"] is None and "quotazione" in q["nota"]


def test_importazione_dopo_il_passaggio_di_stagione_non_riempie_lo_storico(tmp_path):
    from fanta import movimenti
    vuote = lega.Rose([lega.Squadra("Mia", [])], "Mia", "", "2027-28")
    piene = lega.Rose([lega.Squadra("Mia", [lega.GiocatoreRosa(1, "Castro", "A", "ROM", 20)])], "Mia", "", "2027-28")
    assert movimenti.differenze(vuote, piene)                      # il confronto vede tutti come "nuovi"...
    assert not any(s.giocatori for s in vuote.squadre)            # ...ma il server non lo registra se prima le rose erano vuote (vedi _importa)


def test_offerta_scritta_a_parole():
    G = lega.GiocatoreRosa
    rose = lega.Rose([lega.Squadra("Mia", [G(1, "Rowe", "C", "ATA"), G(2, "Politano", "C", "NAP"), G(3, "Castro S.", "A", "ROM")]),
                      lega.Squadra("Giovi", [G(4, "De Bruyne", "C", "NAP"), G(5, "Esposito Se.", "A", "INT"), G(6, "Martinez L.", "A", "INT"), G(7, "Martinez J.", "A", "ROM")]),
                      lega.Squadra("Altra", [G(8, "Maldini", "A", "MIL")])], "Mia")
    r = scambi.riconosci_nel_testo("Ciao! Ti do Rowe e Politano, mi dai de bruyne + Esposito? ", rose, "Mia")
    assert r["con"] == "Giovi" and r["do"] == [1, 2] and sorted(r["ricevo"]) == [4, 5] and r["ambigui"] == []
    assert scambi.riconosci_nel_testo("Voglio Martinez", rose, "Mia", "Giovi")["ambigui"] == ["Martinez L. / Martinez J."]    # due Martinez: non si indovina
    assert scambi.riconosci_nel_testo("niente di che", rose, "Mia")["con"] is None
