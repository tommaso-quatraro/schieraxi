"""Giornata della lega E giornata di Serie A, come su Leghe (#299): «Giornata 8 · 11ª di Serie A» in ogni schermata della web e nei
testi del server; «11ª giornata di Serie A» quando la lega non c'è (stagioni passate, prima che la lega parta) o si parla solo di
Serie A. Una sola funzione per lato: `frasi.nome_giornata` sul server, `nomeGiornata` in fanta/web/app.js
(docs/COERENZA-WEB-IPHONE.md, «Giornata: le forme»). Dati inventati; la lega di prova parte dalla 4ª di Serie A (Serie A 9 = lega 6)."""
import json
import re
import shutil
import sqlite3
import subprocess
from datetime import datetime

import pandas as pd
import pytest

from fanta import avvisi, consigli, da_fare, frasi, lega, notifiche, rinvii, server
from fanta.frasi_avvisi import NOTIFICHE
from fanta.regole import Regole

ST = "2026-27"
LEGA_DA_4 = Regole(prima_giornata_lega=4)
APP = (server.WEB / "app.js").read_text(encoding="utf-8")
TESTI = (server.WEB / "testi.js").read_text(encoding="utf-8")
IT, EN = TESTI.split("\n  en: {", 1)
NODE = shutil.which("node")


def _testo(blocco: str, chiave: str) -> str:
    return re.search(rf'"{re.escape(chiave)}": "([^"]*)"', blocco).group(1)


# ---------------------------------------------------------------- server: la funzione unica
def test_nome_giornata_del_server():
    assert frasi.nome_giornata(11, 8) == "Giornata 8 · 11ª di Serie A"
    assert frasi.nome_giornata(11, None) == "11ª giornata di Serie A"
    assert frasi.di(frasi.nome_giornata(11, 8)) == {"chiave": "giornata.lega", "param": {"n": 8, "a": 11}}
    assert frasi.di(frasi.nome_giornata(11, None)) == {"chiave": "giornata.serie_a", "param": {"a": 11}}
    avviso = frasi.nome_giornata(11, 8, avviso=True)
    assert avviso == "Giornata 8 · 11ª di Serie A" and avviso.in_lingua("en") == "Matchday 8 · Serie A matchday 11"
    assert frasi.nome_giornata(11, None, avviso=True).in_lingua("en") == "Serie A matchday 11"


def test_le_forme_degli_avvisi_sono_quelle_dell_app():
    assert NOTIFICHE["n.giornata.lega"][0] == frasi.CATALOGO["giornata.lega"] == _testo(IT, "frase.giornata.lega")
    assert NOTIFICHE["n.giornata.serie_a"][0] == frasi.CATALOGO["giornata.serie_a"] == _testo(IT, "frase.giornata.serie_a")
    assert NOTIFICHE["n.giornata.lega"][1] == _testo(EN, "frase.giornata.lega")
    assert NOTIFICHE["n.giornata.serie_a"][1] == _testo(EN, "frase.giornata.serie_a")


# ---------------------------------------------------------------- server: Da fare, testo della formazione, errori
def test_da_fare_diario_con_i_due_numeri(tmp_path, monkeypatch):
    monkeypatch.setattr(rinvii, "giornate_chiuse", lambda db, stagione, regole: [8, 9])
    voce = da_fare._diario(None, ST, tmp_path / "scelte.json", tmp_path / "diario.json", LEGA_DA_4)[0]
    assert voce["testo"] == "Giornata 6 · 9ª di Serie A: è finita, dimmi se hai schierato la consigliata."
    assert voce["frase"] == {"chiave": "dafare.diario", "param": {"giornata": {"chiave": "giornata.lega", "param": {"n": 6, "a": 9}}}}
    assert voce["giornata"] == 9                                                  # il numero per il pulsante resta quello di Serie A


def test_testo_della_formazione_per_i_comandi():
    f = {"giornata": 9, "giornata_lega": 6, "schede": {"1": {"nome": "Vicario", "ruolo": "P"}, "2": {"nome": "Bonny", "ruolo": "A"}}}
    assert consigli.testo_formazione(f, "0-0-1", [1, 2], []).splitlines()[0] == "Giornata 6 · 9ª di Serie A · 0-0-1"


def test_errore_senza_previsioni_con_i_due_numeri(monkeypatch):
    monkeypatch.setattr(consigli.modello, "previsioni", lambda *a, **k: pd.DataFrame())
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE probabili (stagione TEXT, giornata INT, fonte TEXT)")
    d = type("D", (), {"calciatori": None})()
    monkeypatch.setattr(consigli.stato_dati, "fattori", lambda *a, **k: None)
    with pytest.raises(ValueError) as e:
        consigli._calcola_previsioni(db, d, LEGA_DA_4, ST, 9, None)
    assert str(e.value) == "Non ci sono ancora previsioni per la Giornata 6 · 9ª di Serie A: riprova più tardi."
    assert _testo(IT, "err.nessuna_previsione") == "Non ci sono ancora previsioni per la {1}: riprova più tardi."
    assert _testo(IT, "err.senza_previsione") == "Giocatore {1} senza previsione per la {2} (la sua squadra non gioca?)"


# ---------------------------------------------------------------- server: avvisi sul telefono
def _db(data_prima_partita: str):
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE partite (stagione TEXT, giornata INT, data TEXT, giocata INT)")
    db.executemany("INSERT INTO partite VALUES (?,?,?,?)", [(ST, 9, data_prima_partita, 0), (ST, 9, "2026-10-29 20:45", 0)])
    return db


ROSE = lega.Rose([lega.Squadra("Mia", [lega.GiocatoreRosa(1, "Castro", "A", "ROM", 10)])], "Mia")


@pytest.fixture
def finto(monkeypatch):
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: ST)
    monkeypatch.setattr(consigli, "prossima_giornata", lambda db, st, adesso=None: 9)
    monkeypatch.setattr(consigli, "formazione", lambda *a, **k: {
        "modulo": "4-3-3", "punteggio_atteso": 71.2, "titolari": [{"id": 1, "nome": "Castro", "titolarita": "titolare", "dubbio": False}]})


def test_promemoria_con_i_due_numeri(tmp_path, finto):
    mandati = []
    manda = lambda titolo, testo, priorita=3, tag="x": mandati.append((titolo, testo)) or True    # noqa: E731
    notifiche.promemoria(_db("2026-10-28 18:30"), LEGA_DA_4, ROSE, datetime(2026, 10, 28, 17, 35), tmp_path / "p.json", manda, {})
    notifiche.promemoria(_db("2026-10-28 18:30"), LEGA_DA_4, ROSE, datetime(2026, 10, 28, 18, 20), tmp_path / "p.json", manda, {})
    (_, un_ora), (_, ultimi) = mandati
    assert un_ora.startswith("Giornata 6 · 9ª di Serie A: la formazione si chiude tra circa un'ora (scadenza alle 18:30).")
    assert ultimi == "Giornata 6 · 9ª di Serie A: la formazione si chiude alle 18:30. L'hai inserita su Leghe?"
    assert frasi.testo(ultimi, "en") == "Matchday 6 · Serie A matchday 9: the lineup closes at 18:30. Have you entered it on Leghe?"


def test_titolare_a_rischio_con_i_due_numeri(tmp_path, finto, monkeypatch):
    monkeypatch.setattr(notifiche, "_gia_schierato", lambda *a, **k: ["Castro"])
    mandati = []
    manda = lambda titolo, testo, priorita=3, tag="x": mandati.append((titolo, testo)) or True    # noqa: E731
    notifiche.promemoria(_db("2026-10-28 18:30"), LEGA_DA_4, ROSE, datetime(2026, 10, 28, 17, 35), tmp_path / "p.json", manda, {})
    assert mandati[0][1] == ("Hai già schierato, ma Castro non è più sicuro come titolare. "
                             "Giornata 6 · 9ª di Serie A: la formazione si chiude alle 18:30, controlla.")


def test_formazione_pronta_con_i_due_numeri(tmp_path):
    db = _db("2026-10-28 18:30")
    a = avvisi.da_mandare(db, ST, 9, datetime(2026, 10, 27, 20, 0), tmp_path / "a.json", regole=LEGA_DA_4)
    assert a["testo"] == "Giornata 6 · 9ª di Serie A: la formazione è pronta. Apri l'app e controlla le probabili."
    assert frasi.testo(a["testo"], "en").startswith("Matchday 6 · Serie A matchday 9: the lineup is ready.")
    senza = avvisi.da_mandare(db, ST, 9, datetime(2026, 10, 27, 20, 0), tmp_path / "b.json")      # chi non passa le regole: solo Serie A
    assert senza["testo"].startswith("9ª giornata di Serie A: la formazione è pronta.")


def test_titoli_degli_avvisi_senza_numero():
    assert frasi.F("n.t_cambi") == "SchieraXI · cambi nelle probabili"
    assert frasi.F("n.t_riepilogo") == "SchieraXI · riepilogo della giornata"
    assert frasi.F("n.t_cambi").in_lingua("en") == "SchieraXI · changes in the probable lineups"
    assert frasi.F("n.t_riepilogo").in_lingua("en") == "SchieraXI · matchday recap"


# ---------------------------------------------------------------- web: la funzione unica
def _funzione_js(nome: str) -> str:
    m = re.search(rf"^function {nome}\(.*?^\}}$", APP, re.M | re.S)
    assert m, nome
    return m.group(0)


@pytest.mark.skipif(NODE is None, reason="node non installato")
@pytest.mark.parametrize("lingua", ["it", "en"])
def test_nome_giornata_della_web(lingua):
    codice = (f'globalThis.localStorage = {{ getItem: () => "{lingua}", setItem() {{}} }};' + TESTI + _funzione_js("nomeGiornata")
              + 'console.log(JSON.stringify([nomeGiornata(8, 11), nomeGiornata(null, 11), nomeGiornata(undefined, "11"), nomeGiornata(8, null),'
              + ' nomeGiornata(null, null), nomeGiornata(1, 1), nomeGiornata("x", 11)]))')
    r = subprocess.run([NODE, "-"], input=codice, capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    if lingua == "it":
        attesi = ["Giornata 8 · 11ª di Serie A", "11ª giornata di Serie A", "11ª giornata di Serie A", "Giornata 8", "",
                  "Giornata 1 · 1ª di Serie A", "11ª giornata di Serie A"]
    else:
        attesi = ["Matchday 8 · Serie A matchday 11", "Serie A matchday 11", "Serie A matchday 11", "Matchday 8", "",
                  "Matchday 1 · Serie A matchday 1", "Serie A matchday 11"]
    assert json.loads(r.stdout) == attesi


def test_ogni_giornata_della_web_passa_da_nome_giornata():
    """Nessun «Giornata N» scritto a mano: l'unico `testata.giornata` sta dentro nomeGiornata, nessun ripiego `giornata_lega || giornata`."""
    corpo = _funzione_js("nomeGiornata")
    assert APP.count('t("testata.giornata"') == corpo.count('t("testata.giornata"') == 1
    resto = APP.replace(corpo, "").replace("formazione-giornata-${f.giornata_lega || f.giornata}.png", "")     # il nome del file resta corto
    assert not re.search(r"(?<!prima_)giornata_lega\)?\s*(\|\||\?\?)", resto)     # `prima_giornata_lega` è una regola, non una giornata
    usi = {
        "testata": "nomeGiornata(i.prossima_giornata_lega, i.prossima_giornata)",
        "Oggi, sopra il conto": '<div class="debole">${nomeGiornata(o.giornata_lega, o.giornata)}</div>',
        "Oggi, prossima": 't("oggi.prossima_chiude", { g: nomeGiornata(p.giornata_lega, p.giornata),',
        "Oggi, finita": 't("oggi.giornata_finita", { g: nomeGiornata(r.giornata_lega, r.giornata) })',
        "Formazione, saltata": "g: nomeGiornata(f.giornata_saltata_lega, f.giornata_saltata), m: nomeGiornata(f.giornata_lega, f.giornata)",
        "Formazione, testo e intestazione": "${nomeGiornata(f.giornata_lega, f.giornata)} · ",
        "immagine, titolo della condivisione": 't("avv.img_titolo", { g: nomeGiornata(f.giornata_lega, f.giornata) })',
        "scheda": "{ g: nomeGiornata(pr.giornata_lega, pr.giornata), avv:",
        "Confronto": 't("mercato.chi_schierare", { g: nomeGiornata(c.giornata_lega, c.giornata) })',
        "Diario": '<h2 style="margin:0">${nomeGiornata(g.giornata_lega, g.giornata)}</h2>',
        "Diario, correggi": 't("diario.correggi_spiega", { g: nomeGiornata(g.giornata_lega, g.giornata) })',
        "Diario, scelte diverse": "<b>${nomeGiornata(g.giornata_lega, g.giornata)}</b>",
        "Diario, quanto ci abbiamo preso": "const nomeG = g => nomeGiornata(g.giornata_lega, g.giornata);",
        "Diario, righe giornata per giornata": "<li><b>${nomeG(g)}</b> · <span",
        "stato dei dati": "<span>${nomeGiornata(null, p.giornata)}</span>",
        "calendario": '<span aria-hidden="true">G${Number(g)}</span><span class="solo-lettori">${nomeGiornata(null, g)}</span>',
        "grafico dei voti": "${nomeGiornata(null, v.giornata)}",
    }
    mancano = [dove for dove, codice in usi.items() if codice not in APP]
    assert mancano == [], mancano
    assert APP.count("${nomeGiornata(f.giornata_lega, f.giornata)} · ") == 3     # testo da condividere, intestazione, immagine


def test_testi_con_la_giornata_intera():
    attesi_it = {
        "frase.giornata.lega": "Giornata {n} · {a}ª di Serie A",
        "frase.giornata.serie_a": "{a}ª giornata di Serie A",
        "frase.dafare.diario": "{giornata}: è finita, dimmi se hai schierato la consigliata.",
        "oggi.prossima_chiude": "{g}: la formazione si chiude {quando}.",
        "oggi.giornata_finita": "{g}: finita",
        "oggi.chiusa_dettaglio": "La formazione si è chiusa {quando}",
        "formazione.per_la_prossima": "{g}: è già iniziata. Questa è la formazione per la {m}.",
        "mercato.partita_casa": "{g} · in casa contro {avv} · {quando}",
        "mercato.partita_fuori": "{g} · in trasferta contro {avv} · {quando}",
        "mercato.chi_schierare": "Chi schierare? {g}",
        "diario.correggi_spiega": "{g}: tocca i giocatori che hai schierato. Servono 11 titolari.",
        "diario.qp_su.other": "Calcolato su {n} giornate, dalla {da} alla {a}.",
        "avv.img_titolo": "Formazione · {g}",
        "avv.giornate_da_a": "dalla {a}ª alla {b}ª giornata di Serie A",
    }
    for chiave, testo in attesi_it.items():
        assert _testo(IT, chiave) == testo, chiave
        segnaposto = set(re.findall(r"\{(\w+)\}", testo))
        assert set(re.findall(r"\{(\w+)\}", _testo(EN, chiave))) == segnaposto, chiave
    assert _testo(EN, "frase.giornata.lega") == "Matchday {n} · Serie A matchday {a}"
    assert _testo(EN, "frase.giornata.serie_a") == "Serie A matchday {a}"
