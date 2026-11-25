"""Guasti delle fonti che si vedono (#608): ogni passo dell'aggiornamento ha il suo ultimo successo, la riga generale non fa sembrare
freschi i dati di un passo che non riesce, la salute avvisa per nome del passo fermo da più di 24 ore, una pagina web al posto dei
dati dà un errore leggibile. Archivi temporanei, dati inventati, nessuna richiesta in rete."""
import json
import sqlite3
from datetime import datetime
from types import SimpleNamespace

import pytest

from fanta import aggiorna, archivio, consigli, fonti_attive, funzioni, salute, stato_dati
from fanta.fonti import understat as us

ST = "2026-27"


@pytest.fixture
def db(tmp_path):
    d = archivio.apri(tmp_path / "t.sqlite")
    yield d
    d.close()


def _agg(db, monkeypatch, ora, righe=None):
    monkeypatch.setattr(aggiorna, "_ora", lambda: ora)
    return aggiorna.Aggiornamento(db, aggiorna.Stagione(2026), scrivi=(righe if righe is not None else []).append)


def _riga(db, cosa):
    r = db.execute("SELECT quando, dettaglio FROM aggiornamenti WHERE cosa = ?", (cosa,)).fetchone()
    return None if r is None else (r[0], json.loads(r[1]) if r[1] else None)


def _rotto():
    raise ValueError("pagina strana")


def test_un_passo_riuscito_segna_il_suo_ultimo_successo(db, monkeypatch):
    _agg(db, monkeypatch, "2026-11-02T08:03:00")._passo("probabili", lambda: None)
    assert _riga(db, "probabili") == ("2026-11-02T08:03:00", None)


def test_un_passo_che_non_riesce_tiene_l_ultimo_successo_e_dice_da_quando(db, monkeypatch):
    _agg(db, monkeypatch, "2026-11-01T21:03:00")._passo("Understat", lambda: None)
    _agg(db, monkeypatch, "2026-11-02T08:03:00")._passo("Understat", _rotto)
    quando, d = _riga(db, "understat")
    assert quando == "2026-11-01T21:03:00"
    assert d == {"errore": "ValueError: pagina strana", "dal": "2026-11-02T08:03:00", "ultimo": "2026-11-02T08:03:00"}
    righe = []
    a = _agg(db, monkeypatch, "2026-11-04T13:03:00", righe)
    a._passo("Understat", _rotto)
    quando, d = _riga(db, "understat")
    assert quando == "2026-11-01T21:03:00" and d["dal"] == "2026-11-02T08:03:00" and d["ultimo"] == "2026-11-04T13:03:00"
    # nell'errore della corsa (riga generale, registro, avviso) c'è da quando non riesce e l'ultimo successo
    assert a.errori[0].startswith("Understat: ValueError: pagina strana")
    assert "non riesce dal 02/11 alle 08:03" in a.errori[0] and "ultimo riuscito il 01/11 alle 21:03" in a.errori[0]
    assert any("non riesce dal 02/11" in r for r in righe)
    _agg(db, monkeypatch, "2026-11-05T08:03:00")._passo("Understat", lambda: None)
    assert _riga(db, "understat") == ("2026-11-05T08:03:00", None)


def test_un_passo_mai_riuscito_ha_l_ora_vuota(db, monkeypatch):
    _agg(db, monkeypatch, "2026-11-02T08:03:00")._passo("listone", _rotto)
    quando, d = _riga(db, "listone")
    assert quando is None and d["dal"] == "2026-11-02T08:03:00"


def test_solo_i_passi_seguiti_hanno_una_riga(db, monkeypatch):
    a = _agg(db, monkeypatch, "2026-11-02T08:03:00")
    a._passo("risultati 11", lambda: None)
    a._passo("voti 2025-26", _rotto)
    assert db.execute("SELECT COUNT(*) FROM aggiornamenti").fetchone()[0] == 0


def test_un_passo_spento_non_resta_in_errore(db, monkeypatch):
    _agg(db, monkeypatch, "2026-11-02T08:03:00")._passo("Understat", _rotto, "understat")
    monkeypatch.setattr(fonti_attive, "acceso", lambda nome: False)
    _agg(db, monkeypatch, "2026-11-02T13:03:00")._passo("Understat", _rotto, "understat")
    assert _riga(db, "understat") == (None, None)
    assert archivio.passi_fermi(db, datetime(2026, 11, 10, 8, 0)) == []


def _tutti(monkeypatch, riusciti: set[str]):
    """esegui() con passi finti: quelli in `riusciti` vanno, gli altri si rompono."""
    monkeypatch.setattr(fonti_attive, "acceso", lambda nome: True)
    monkeypatch.setattr(funzioni, "acceso", lambda nome: True)
    for metodo in ("listone", "calendario", "voti", "probabili", "understat", "dati_extra", "controlli"):
        monkeypatch.setattr(aggiorna.Aggiornamento, metodo,
                            (lambda self: None) if metodo in riusciti else (lambda self: _rotto()))


def test_la_riga_generale_non_avanza_se_nessun_passo_dei_dati_riesce(db, monkeypatch):
    archivio.segna(db, "aggiornamento", "2026-11-01T21:03:00", "[]")
    db.commit()
    _tutti(monkeypatch, {"controlli"})
    errori = _agg(db, monkeypatch, "2026-11-02T08:03:00").esegui()
    quando, dettaglio = db.execute("SELECT quando, dettaglio FROM aggiornamenti WHERE cosa = 'aggiornamento'").fetchone()
    assert quando == "2026-11-01T21:03:00"                    # i dati sono ancora quelli di ieri sera
    assert json.loads(dettaglio) == errori and len(errori) >= 5


def test_la_riga_generale_avanza_se_un_passo_dei_dati_riesce(db, monkeypatch):
    archivio.segna(db, "aggiornamento", "2026-11-01T21:03:00", "[]")
    db.commit()
    _tutti(monkeypatch, {"probabili", "controlli"})
    _agg(db, monkeypatch, "2026-11-02T08:03:00").esegui()
    quando, dettaglio = db.execute("SELECT quando, dettaglio FROM aggiornamenti WHERE cosa = 'aggiornamento'").fetchone()
    assert quando == "2026-11-02T08:03:00" and any(e.startswith("Understat:") for e in json.loads(dettaglio))


class _ContaVersioni(sqlite3.Connection):
    """Archivio che dopo ogni conferma annota la «versione» dei dati (`consigli._versione`): quando cambia, il riscaldamento ricalcola
    formazioni e mercato."""

    def commit(self):
        super().commit()
        self.versioni.append(consigli._versione(self))


def _cambi_di_versione(versioni: list, prima) -> int:
    return sum(1 for a, b in zip([prima, *versioni], versioni) if a != b)


def test_un_aggiornamento_cambia_la_versione_dei_dati_una_volta_sola(tmp_path, monkeypatch):
    f = tmp_path / "t.sqlite"
    archivio.apri(f).close()
    d = sqlite3.connect(f, factory=_ContaVersioni)
    d.row_factory = sqlite3.Row
    d.versioni = []
    try:
        archivio.segna(d, "aggiornamento", "2026-11-01T21:03:00", "[]")
        d.commit()
        _tutti(monkeypatch, {"listone", "calendario", "voti", "probabili", "understat", "dati_extra", "controlli"})
        for ora in ("2026-11-02T08:03:00", "2026-11-02T13:03:00"):
            prima, d.versioni = consigli._versione(d), []
            _agg(d, monkeypatch, ora).esegui()
            assert _cambi_di_versione(d.versioni, prima) == 1, ora
        # un passo che non riesce non cambia la versione (i dati sono quelli di prima): solo la riga generale a fine giro
        _tutti(monkeypatch, {"listone", "calendario", "voti", "understat", "dati_extra", "controlli"})
        prima, d.versioni = consigli._versione(d), []
        _agg(d, monkeypatch, "2026-11-02T17:03:00").esegui()
        assert _cambi_di_versione(d.versioni, prima) == 1
    finally:
        d.close()


def test_dati_extra_una_riga_sola_e_al_massimo_ogni_6_ore(db, monkeypatch):
    """Una sola riga per football-data in «Stato dei dati» («dati-extra», l'esito del passo; prima c'erano «dati extra» e «dati-extra»);
    il limite delle 6 ore si legge dall'ora delle righe salvate."""
    from pathlib import Path
    csv = (Path(__file__).parent / "dati" / "football_data_extra.csv").read_bytes()
    chiamate = []
    monkeypatch.setattr(aggiorna.rete, "scarica", lambda url, *a, **k: chiamate.append(url) or SimpleNamespace(content=csv))
    monkeypatch.setattr(fonti_attive, "acceso", lambda nome: True)
    for ora, attese in (("2026-11-02T08:03:00", 2), ("2026-11-02T13:03:00", 2), ("2026-11-02T17:03:00", 4)):
        a = _agg(db, monkeypatch, ora)
        a.slug_noti = {"como", "sassuolo", "milan", "pisa"}
        a._passo("dati extra", a.dati_extra, "footballdata")
        assert len(chiamate) == attese, ora
    assert [r[0] for r in db.execute("SELECT cosa FROM aggiornamenti")] == ["dati-extra"]
    assert _riga(db, "dati-extra") == ("2026-11-02T17:03:00", None)


def test_passi_fermi_da_piu_di_24_ore_dal_primo_errore(db, monkeypatch):
    _agg(db, monkeypatch, "2026-11-01T21:03:00")._passo("Understat", lambda: None)
    _agg(db, monkeypatch, "2026-11-02T08:03:00")._passo("Understat", _rotto)
    _agg(db, monkeypatch, "2026-11-02T08:03:00")._passo("voti", lambda: None)
    assert archivio.passi_fermi(db, datetime(2026, 11, 3, 8, 0)) == []                    # 24 ore dal primo errore: non ancora
    fermi = archivio.passi_fermi(db, datetime(2026, 11, 3, 9, 0))
    assert [(p["passo"], p["ultimo_successo"], p["dal"]) for p in fermi] == [("understat", "2026-11-01T21:03:00", "2026-11-02T08:03:00")]


def test_una_fonte_riaccesa_non_e_subito_ferma(db, monkeypatch):
    """Spenta apposta per 16 giorni e riaccesa: al primo errore non è «ferma da 16 giorni» (niente avviso subito); lo diventa solo
    dopo 24 ore di errori di fila."""
    _agg(db, monkeypatch, "2026-11-01T21:03:00")._passo("Understat", lambda: None)
    monkeypatch.setattr(fonti_attive, "acceso", lambda nome: False)
    _agg(db, monkeypatch, "2026-11-02T08:03:00")._passo("Understat", _rotto, "understat")
    monkeypatch.setattr(fonti_attive, "acceso", lambda nome: True)
    _agg(db, monkeypatch, "2026-11-18T08:03:00")._passo("Understat", _rotto, "understat")
    assert archivio.passi_fermi(db, datetime(2026, 11, 18, 9, 0)) == []
    _agg(db, monkeypatch, "2026-11-19T08:03:00")._passo("Understat", _rotto, "understat")
    assert [p["passo"] for p in archivio.passi_fermi(db, datetime(2026, 11, 19, 9, 0))] == ["understat"]


def test_passo_mai_riuscito_fermo_dal_primo_errore(db, monkeypatch):
    _agg(db, monkeypatch, "2026-11-02T08:03:00")._passo("probabili", _rotto)
    assert archivio.passi_fermi(db, datetime(2026, 11, 3, 7, 0)) == []
    assert [p["passo"] for p in archivio.passi_fermi(db, datetime(2026, 11, 3, 9, 0))] == ["probabili"]


def test_la_salute_avvisa_per_nome_del_passo_fermo_e_ripete_ogni_24_ore(db, monkeypatch, tmp_path):
    archivio.segna(db, "aggiornamento", "2026-11-04T08:03:00", "[]")       # la corsa gira: il resto arriva
    _agg(db, monkeypatch, "2026-11-01T21:03:00")._passo("Understat", lambda: None)
    _agg(db, monkeypatch, "2026-11-02T08:03:00")._passo("Understat", _rotto)
    mandati = []
    manda = lambda titolo, testo, priorita=3, tag="x": mandati.append(testo) or True    # noqa: E731
    f = tmp_path / "salute.json"
    problemi = salute.controlla(db, datetime(2026, 11, 4, 9, 0), f, manda, lambda: True)
    assert len(problemi) == 1 and "«understat»" in problemi[0] and "da 2 giorni" in problemi[0] and len(mandati) == 1
    salute.controlla(db, datetime(2026, 11, 4, 22, 0), f, manda, lambda: True)
    assert len(mandati) == 1                                                  # dopo 13 ore no
    salute.controlla(db, datetime(2026, 11, 5, 9, 30), f, manda, lambda: True)
    assert len(mandati) == 2                                                  # dopo 24 ore sì, finché dura
    _agg(db, monkeypatch, "2026-11-05T13:03:00")._passo("Understat", lambda: None)
    assert salute.controlla(db, datetime(2026, 11, 5, 13, 10), f, manda, lambda: True) == []


def test_stato_dei_dati_mostra_il_passo_fermo_con_l_ora_vera(db, monkeypatch):
    _agg(db, monkeypatch, "2026-11-01T21:03:00")._passo("Understat", lambda: None)
    _agg(db, monkeypatch, "2026-11-02T08:03:00")._passo("Understat", _rotto)
    r = stato_dati.riepilogo(db, ST, adesso=datetime(2026, 11, 4, 9, 0))
    voce = next(a for a in r["aggiornamenti"] if a["cosa"] == "understat")
    assert voce["quando"] == "2026-11-01T21:03:00"                            # l'ultimo successo, non l'ora dell'ultima corsa
    assert voce["errori"] == ["Fermo da 2 giorni (non riesce dal 02/11 alle 08:03): ValueError: pagina strana"]
    r = stato_dati.riepilogo(db, ST, adesso=datetime(2026, 11, 2, 9, 0))
    voce = next(a for a in r["aggiornamenti"] if a["cosa"] == "understat")
    assert voce["errori"] == ["Non riuscito alle 08:03 del 02/11: ValueError: pagina strana"]


def test_le_righe_d_errore_con_l_apostrofo_davanti_all_08_e_all_11(db, monkeypatch):
    """«dall'08/11», «dell'11/11», «l'08/11» (si legge «dall'otto», «dell'undici»), mai «dal 08/11» o «del 11/11» (#859): nella
    riga generale dell'aggiornamento e nelle righe d'errore di Stato dei dati. «il 01/11» e «del 02/11» restano."""
    _agg(db, monkeypatch, "2026-11-01T21:03:00")._passo("Understat", lambda: None)
    _agg(db, monkeypatch, "2026-11-08T08:03:00")._passo("Understat", _rotto)
    a = _agg(db, monkeypatch, "2026-11-11T13:03:00")
    a._passo("Understat", _rotto)
    assert "(non riesce dall'08/11 alle 08:03; ultimo riuscito il 01/11 alle 21:03)" in a.errori[0], a.errori[0]
    r = stato_dati.riepilogo(db, ST, adesso=datetime(2026, 11, 11, 14, 0))
    voce = next(x for x in r["aggiornamenti"] if x["cosa"] == "understat")
    assert voce["errori"] == ["Fermo da 3 giorni (non riesce dall'08/11 alle 08:03): ValueError: pagina strana"]
    _agg(db, monkeypatch, "2026-11-08T21:03:00")._passo("Understat", lambda: None)
    _agg(db, monkeypatch, "2026-11-11T08:03:00")._passo("Understat", _rotto)
    a = _agg(db, monkeypatch, "2026-11-11T13:03:00")
    a._passo("Understat", _rotto)
    assert "(non riesce dall'11/11 alle 08:03; ultimo riuscito l'08/11 alle 21:03)" in a.errori[0], a.errori[0]
    r = stato_dati.riepilogo(db, ST, adesso=datetime(2026, 11, 11, 14, 0))       # non è fermo da più di un giorno
    voce = next(x for x in r["aggiornamenti"] if x["cosa"] == "understat")
    assert voce["errori"] == ["Non riuscito alle 13:03 dell'11/11: ValueError: pagina strana"]


def test_stato_dei_dati_ha_un_nome_leggibile_per_ogni_riga_e_ogni_controllo(db, monkeypatch):
    """Le etichette nascono sul server (campo `etichetta`): i client non mostrano più chiavi grezze come «dati-extra» o
    «gol_dei_voti»."""
    from fanta import controlli
    for cosa in ("aggiornamento", "listone", "calendario", "voti", "probabili", "understat", "dati-extra", "controlli",
                 "calendario 2026-27", "dati-extra 2025-26", "probabili-rapido", "risultati-rapido", "taratura-probabili",
                 "cosa-mai-vista"):
        archivio.segna(db, cosa, "2026-11-02T08:03:00")
    for nome in list(controlli.CONTROLLI) + ["sentinella", "sentinella_voti_mancanti"]:
        db.execute("INSERT INTO controlli VALUES (?, ?, 'ok', 0, 'x', '2026-11-02T08:03:00')", (ST, nome))
    r = stato_dati.riepilogo(db, ST, adesso=datetime(2026, 11, 2, 9, 0))
    etichette = {a["cosa"]: a["etichetta"] for a in r["aggiornamenti"]}
    assert etichette["dati-extra"] == "Statistiche di squadra" and etichette["understat"] == "Statistiche avanzate"
    assert etichette["calendario 2026-27"] == "Calendario completo 2026-27"
    assert etichette["dati-extra 2025-26"] == "Statistiche di squadra 2025-26"
    assert etichette["cosa-mai-vista"] == "Cosa mai vista"                       # chiave sconosciuta: almeno leggibile
    nomi = {c["nome"]: c["etichetta"] for c in r["controlli"]}
    assert nomi["gol_dei_voti"] == "Gol dei voti uguali al risultato"
    assert nomi["gol_subiti_portieri"] == "Gol presi dai portieri uguali al risultato"
    assert nomi["sentinella_voti_mancanti"] == "Sentinella: voti mancanti"
    for testo in [*etichette.values(), *nomi.values()]:
        assert testo and "_" not in testo and testo[0].isupper() or testo[0].isdigit(), testo


# ---------------- una pagina web al posto dei dati ----------------
MANUTENZIONE = b"<!DOCTYPE html>\n<html><head><title>  Sito in\nmanutenzione </title></head><body>Torniamo presto</body></html>"


def test_understat_pagina_web_al_posto_dei_dati():
    with pytest.raises(us.RispostaNonDati, match="pagina web al posto dei dati") as e:
        us.dati_json(MANUTENZIONE)
    assert "«Sito in manutenzione»" in str(e.value)
    with pytest.raises(us.RispostaNonDati, match="non si leggono"):
        us.dati_json(b"Errore 42")
    with pytest.raises(us.RispostaNonDati, match="vuota"):
        us.dati_json(b"  ")
    assert us.dati_json('{"dates": [], "players": []}'.encode()) == {"dates": [], "players": []}
    assert us.dati_json("{\"nome\": \"Martínez\"}".encode("utf-8")) == {"nome": "Martínez"}


# inventata e corta, con la forma di quella che Understat dà dal novembre 2026 su ogni indirizzo: titolo col solo nome del sito,
# stile, un disegno, una frase
PAGINA_DI_ATTESA = (b"<!DOCTYPE html>\n<html><head><title>Sito</title><style>body { color: #fff }</style></head>"
                    b"<body class=\"scuro\"><div><?xml version=\"1.0\"?><svg><text>logo</text></svg></div>\n"
                    b"<p>Torniamo\n   presto &amp; bene</p><!-- nota --><script>var x = 1;</script></body></html>")


def test_understat_pagina_web_dice_anche_il_testo_che_mostra():
    """Il solo titolo («Understat.com») non diceva cosa c'era scritto sulla pagina: il messaggio riporta anche il testo visibile,
    senza stile, disegni, commenti e codice, con un tetto di lunghezza."""
    with pytest.raises(us.RispostaNonDati) as e:
        us.dati_json(PAGINA_DI_ATTESA)
    assert "(titolo «Sito», testo «Torniamo presto & bene»): " in str(e.value)
    for scarto in ("logo", "color", "var x", "nota", "xml", "scuro"):
        assert scarto not in str(e.value)
    with pytest.raises(us.RispostaNonDati) as e:
        us.dati_json(b"<html><body><p>" + b"parola " * 100 + b"</p></body></html>")
    testo = str(e.value).split("testo «")[1].split("»")[0]
    assert testo.startswith("parola parola") and len(testo) <= 120
    with pytest.raises(us.RispostaNonDati) as e:                               # niente testo visibile: solo il titolo, come prima
        us.dati_json(b"<html><head><title>Vuota</title></head><body><svg></svg></body></html>")
    assert "(titolo «Vuota»): " in str(e.value) and "testo" not in str(e.value)


def test_understat_pagina_web_con_un_disegno_grande_prima_della_frase_dice_la_frase():
    """La pagina di attesa di Understat (#862) ha un disegno lungo decine di migliaia di caratteri prima della frase: leggendo solo
    l'inizio della pagina il disegno restava aperto, la frase fuori e il messaggio diceva solo il titolo. Pagina inventata."""
    disegno = b"<svg viewBox=\"0 0 800 600\">" + b"<path d=\"M10 10 L20 20 L30 10 Z\" fill=\"#123456\"/>" * 2_000 + b"</svg>"
    assert len(disegno) > 3 * us.PAGINA_LETTA
    pagina = (b"<!DOCTYPE html>\n<html><head><title>Sito</title><style>body { color: #fff }</style></head><body><div>" + disegno
              + b"</div><h1>Torniamo presto</h1><p>Stiamo sistemando il sito.</p></body></html>")
    with pytest.raises(us.RispostaNonDati) as e:
        us.dati_json(pagina)
    assert "(titolo «Sito», testo «Torniamo presto Stiamo sistemando il sito.»): " in str(e.value)
    assert "path" not in str(e.value) and "123456" not in str(e.value)


@pytest.mark.parametrize("pezzo", [b"<svg>", b"<title>", b"<title", b"<title>x</titl", b"<!--", b"<?", b"<", b"<style>x"])
def test_understat_pagina_web_enorme_o_storta_si_legge_subito(pezzo):
    """Una risposta grande fatta di aperture mai chiuse (rete.scarica non ha un tetto di dimensione) prima costava decine di
    secondi di espressioni regolari: il titolo si cerca solo all'inizio della pagina e il testo visibile, che si cerca più in là
    (#862), con espressioni che crescono solo con la lunghezza, fino a un tetto. Limite largo: bastano centesimi."""
    import time
    pagina = b"<html><body><p>Fermi</p>" + pezzo * ((us.TESTO_LETTO + 300_000) // len(pezzo))
    inizio = time.perf_counter()
    with pytest.raises(us.RispostaNonDati, match="pagina web al posto dei dati") as e:
        us.dati_json(pagina)
    assert time.perf_counter() - inizio < 1.0
    assert "testo «Fermi" in str(e.value)


def test_aggiornamento_understat_con_pagina_web_una_richiesta_sola_e_errore_chiaro(db, monkeypatch):
    chiamate = []
    monkeypatch.setattr(aggiorna.rete, "scarica", lambda url, *a, **k: chiamate.append(url) or SimpleNamespace(content=MANUTENZIONE))
    monkeypatch.setattr(fonti_attive, "acceso", lambda nome: True)
    a = _agg(db, monkeypatch, "2026-11-04T17:03:00")
    a._passo("Understat", a.understat, "understat")
    assert chiamate == [us.url_lega(2026)]                                     # niente altre richieste dopo la pagina sbagliata
    assert a.errori[0].startswith("Understat: RispostaNonDati: Understat ha risposto con una pagina web al posto dei dati")
