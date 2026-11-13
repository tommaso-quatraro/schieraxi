"""#331: il riepilogo dopo la giornata usa la consigliata fissata alla scadenza (istantanea del Diario), come Oggi e il Diario; promemoria
e «Da fare» hanno una frase propria quando la scelta salvata non vale più.
Dati finti, file in cartelle temporanee, nessun invio vero."""
# ruff: noqa: F811  (le fixture importate da altri file di test arrivano come parametri con lo stesso nome: è il modo di pytest)
import json
import re
from datetime import datetime

import pytest

from fanta import diario, notifiche, scelte
from fanta.frasi import CATALOGO, F, nome_giornata
from fanta.frasi_avvisi import NOTIFICHE
from fanta.regole import Regole
from test_da_fare import STAGIONE, mondo, vai  # noqa: F401  (mondo = fixture di «Da fare»)
from test_notifiche import ST, _db
from test_scelta_non_valida_avvisi import (CEDUTO, CHIUSURA, CONSIGLIATA_8, DUE_PORTIERI, OPZ, ROSE, SCELTA_8, TITOLARI, _giornata_8_finita,
                                           _prima_della_scadenza, _registro)

ALTRA_8 = [1, 3, 4, 5, 6, 8, 9, 10, 11, 14, 15]          # un 4-4-2 senza il giocatore 13, l'unico che ha segnato: fa meno punti
NON_VALIDA_8 = [SCELTA_8[:10] + [CEDUTO], [1, 2, 3, 4, 5, 8, 9, 10, 13, 14, 15]]    # giocatore ceduto; due portieri
ADESSO_8 = datetime(2026, 10, 21, 8, 0)


def _istantanea(tmp_path, titolari, panchina=(), nome="diario.json"):
    """Il file del Diario con la consigliata congelata alla scadenza della giornata 8."""
    f = {"giornata": 8, "modulo": "4-4-2", "punteggio_atteso": 70.0,
         "titolari": [{"id": i, "nome": f"g{i}", "ruolo": "x"} for i in titolari],
         "panchina": [{"id": i, "nome": f"g{i}", "ruolo": "x"} for i in panchina]}
    file = tmp_path / nome
    assert diario.salva_istantanea(f, ST, file)
    return file


def _riepilogo(tmp_path, db, rose, nome, *, visti=None, salvata=None, file_diario=None, automatica=None):
    """Il testo del riepilogo della giornata 8, o None se non parte. `visti`: la consigliata che l'avviso dei cambi aveva visto."""
    fs, cambi = tmp_path / f"scelte-{nome}.json", tmp_path / f"cambi-{nome}.json"
    if salvata:
        scelte.salva(ST, 8, salvata, "4-3-3", fs)
    if automatica:
        scelte.salva_automatica(ST, 8, automatica, "4-4-2", fs)
    if visti:
        cambi.write_text(json.dumps({"cambi": {f"{ST}/8": {"titolari": visti}}}), encoding="utf-8")
    mandati, manda = _registro()
    r = notifiche.riepilogo(db, Regole(), rose, ADESSO_8, tmp_path / f"r-{nome}.json", manda, {"riepilogo": True}, cambi, fs, file_diario)
    return str(r[0]) if r else None


def _punti(testo):
    return float(re.search(r"ha fatto circa (\d+,\d) punti", testo).group(1).replace(",", "."))


# ---------------------------------------------------------------- 1. il riepilogo usa l'istantanea della scadenza
@pytest.mark.parametrize("salvata", [None, *NON_VALIDA_8], ids=["nessuna-scelta", "giocatore-ceduto", "due-portieri"])
def test_riepilogo_usa_la_consigliata_della_scadenza_non_quella_dei_cambi(tmp_path, monkeypatch, salvata):
    """L'avviso dei cambi aveva visto una consigliata più vecchia (ALTRA_8); alla scadenza è stata congelata CONSIGLIATA_8 (istantanea),
    quella che mostrano Oggi e il Diario. Il riepilogo deve contare i punti di quella, non dell'ultima vista dai cambi."""
    db, rose = _giornata_8_finita(tmp_path, monkeypatch)
    con_istantanea = _istantanea(tmp_path, CONSIGLIATA_8)
    atteso = _riepilogo(tmp_path, db, rose, "a", visti=CONSIGLIATA_8, salvata=salvata)            # i cambi avevano visto proprio quella
    vecchia = _riepilogo(tmp_path, db, rose, "b", visti=ALTRA_8, salvata=salvata)                 # i cambi avevano visto un'altra
    assert atteso and vecchia and _punti(atteso) != _punti(vecchia)                               # la prova distingue le due
    assert atteso.startswith("Giornata 8 · 8ª di Serie A: la formazione consigliata ha fatto circa")
    assert _riepilogo(tmp_path, db, rose, "c", visti=ALTRA_8, salvata=salvata, file_diario=con_istantanea) == atteso


def test_riepilogo_con_la_tua_scelta_valida_non_guarda_l_istantanea(tmp_path, monkeypatch):
    db, rose = _giornata_8_finita(tmp_path, monkeypatch)
    solo_scelta = _riepilogo(tmp_path, db, rose, "a", salvata=ALTRA_8)
    assert solo_scelta.startswith("Giornata 8 · 8ª di Serie A: la tua scelta salvata ha fatto circa")
    con_istantanea = _istantanea(tmp_path, CONSIGLIATA_8)
    assert _riepilogo(tmp_path, db, rose, "b", visti=CONSIGLIATA_8, salvata=ALTRA_8, file_diario=con_istantanea) == solo_scelta


def test_riepilogo_senza_istantanea_usa_la_copia_automatica_poi_i_cambi(tmp_path, monkeypatch):
    """Stesso ordine di Oggi: scelta tua, istantanea, copia automatica della consigliata; l'ultima vista dai cambi resta l'ultimo ripiego."""
    db, rose = _giornata_8_finita(tmp_path, monkeypatch)
    atteso = _riepilogo(tmp_path, db, rose, "a", visti=CONSIGLIATA_8)
    assert _riepilogo(tmp_path, db, rose, "b", visti=ALTRA_8, automatica=CONSIGLIATA_8) == atteso        # copia automatica, non i cambi
    assert _riepilogo(tmp_path, db, rose, "c", visti=ALTRA_8) != atteso                                  # solo i cambi: come prima
    assert _riepilogo(tmp_path, db, rose, "d") is None                                                    # niente da cui partire: non si manda


def test_riepilogo_usa_la_panchina_dell_istantanea_come_il_diario(tmp_path, monkeypatch):
    """Il giocatore 14 non ha voto: entra il primo attaccante della panchina. Il Diario e Oggi usano la panchina congelata alla scadenza
    (non quella ricalcolata dopo): il 16 ha segnato, il 15 no."""
    db, rose = _giornata_8_finita(tmp_path, monkeypatch)
    db.execute("DELETE FROM voti WHERE giornata = 8 AND calciatore_id = 14")
    db.execute("UPDATE voti SET gol = 1 WHERE giornata = 8 AND calciatore_id = 16")
    prima_16 = _istantanea(tmp_path, CONSIGLIATA_8, panchina=[2, 16, 15, 7, 12], nome="a.json")
    prima_15 = _istantanea(tmp_path, CONSIGLIATA_8, panchina=[2, 15, 16, 7, 12], nome="b.json")
    con_16 = _riepilogo(tmp_path, db, rose, "a", file_diario=prima_16)
    con_15 = _riepilogo(tmp_path, db, rose, "b", file_diario=prima_15)
    assert _punti(con_16) > _punti(con_15)


def test_riepilogo_con_un_giocatore_non_piu_in_rosa_nell_istantanea_non_parte(tmp_path, monkeypatch):
    """Come prima: se la consigliata di allora ha un giocatore che non è più in rosa non si inventano punti."""
    db, rose = _giornata_8_finita(tmp_path, monkeypatch)
    ceduto = _istantanea(tmp_path, CONSIGLIATA_8[:10] + [CEDUTO])
    assert _riepilogo(tmp_path, db, rose, "a", file_diario=ceduto) is None


# ---------------------------------------------------------------- 2. frase propria per la scelta salvata che non vale più
NON_VALIDE_9 = [pytest.param([*TITOLARI[:10], CEDUTO], id="giocatore-ceduto"), pytest.param(DUE_PORTIERI, id="modulo-non-ammesso")]


def _promemoria(tmp_path, monkeypatch, salvata, quando, stato="p.json"):
    _prima_della_scadenza(monkeypatch)
    fs = tmp_path / "scelte.json"
    if salvata:
        scelte.salva(ST, 9, salvata, "4-4-2", fs)
    mandati, manda = _registro()
    r = notifiche.promemoria(_db(CHIUSURA), Regole(), ROSE, quando, tmp_path / stato, manda, OPZ, fs)
    return r, mandati


@pytest.mark.parametrize("salvata", NON_VALIDE_9)
def test_promemoria_un_ora_dice_che_la_formazione_salvata_non_vale(tmp_path, monkeypatch, salvata):
    r, mandati = _promemoria(tmp_path, monkeypatch, salvata, datetime(2026, 10, 28, 17, 35))
    testo = mandati[0][1]
    assert len(r) == 1 and mandati[0][0] == "SchieraXI · formazione tra un'ora"
    assert testo.startswith("Giornata 9 · 9ª di Serie A: la formazione si chiude tra circa un'ora (scadenza alle 18:30), ma quella che hai salvato "
                            "non è più valida: salvane un'altra.")
    assert "Consigliato: 4-4-2, 71,2 punti attesi." in testo                    # il consiglio resta, serve a sceglierne un'altra
    assert "L'hai inserita" not in testo


@pytest.mark.parametrize("salvata", NON_VALIDE_9)
def test_promemoria_ultimi_minuti_dice_che_la_formazione_salvata_non_vale(tmp_path, monkeypatch, salvata):
    r, mandati = _promemoria(tmp_path, monkeypatch, salvata, datetime(2026, 10, 28, 18, 20))
    assert len(r) == 1 and mandati[0][0] == "SchieraXI · ultimi minuti per la formazione"
    assert mandati[0][1] == ("Giornata 9 · 9ª di Serie A: la formazione si chiude alle 18:30 e quella che hai salvato non è più valida. "
                             "Salvane un'altra.")


def test_promemoria_senza_scelta_resta_come_prima(tmp_path, monkeypatch):
    _, mandati = _promemoria(tmp_path, monkeypatch, None, datetime(2026, 10, 28, 17, 35))
    assert mandati[0][1].startswith("Giornata 9 · 9ª di Serie A: la formazione si chiude tra circa un'ora (scadenza alle 18:30).")
    _, mandati = _promemoria(tmp_path, monkeypatch, None, datetime(2026, 10, 28, 18, 20))
    assert mandati[0][1] == "Giornata 9 · 9ª di Serie A: la formazione si chiude alle 18:30. L'hai inserita su Leghe?"


def test_promemoria_con_scelta_valida_non_cambia(tmp_path, monkeypatch):
    """Scelta a posto: nessun promemoria (come prima)."""
    r, mandati = _promemoria(tmp_path, monkeypatch, TITOLARI, datetime(2026, 10, 28, 17, 35))
    assert r == [] and mandati == []


def test_le_frasi_nuove_hanno_italiano_e_inglese():
    for chiave in ("n.non_valida_tra_un_ora", "n.non_valida_ultimi_minuti"):
        it, en = NOTIFICHE[chiave]
        assert "non è più valida" in it and "no longer valid" in en
        f = F(chiave, giornata=nome_giornata(9, 6, avviso=True), ora="18:30")                  # la giornata con i due numeri (#299)
        assert str(f).startswith("Giornata 6 · 9ª di Serie A: ") and f.in_lingua("en").startswith("Matchday 6 · Serie A matchday 9: ")
        assert "{" not in str(f) and "{" not in f.in_lingua("en") and "18:30" in f.in_lingua("en")
    assert "dafare.formazione_non_valida" in CATALOGO


def test_da_fare_formazione_salvata_non_valida_ha_la_sua_frase(mondo):
    """Vicino alla scadenza: con una scelta che non vale la voce dice che quella salvata non è più valida; senza scelta resta
    «non l'hai ancora salvata»."""
    mondo.oggi["ore_mancanti"] = 2.0
    senza = [x for x in vai(mondo) if x["tipo"] == "formazione"]
    assert len(senza) == 1 and senza[0]["frase"]["chiave"] == "dafare.formazione_chiude" and "non l'hai ancora salvata" in senza[0]["testo"]
    scelte.salva(STAGIONE, 9, [1, 2, 3, 4, 7, 8, 9, 10, 11, 12, CEDUTO], "3-5-2", mondo.ctx.scelte)
    voce = [x for x in vai(mondo) if x["tipo"] == "formazione"]
    assert len(voce) == 1 and voce[0]["priorita"] == 1 and voce[0]["azione"] == "Apri la formazione"
    assert voce[0]["testo"] == "La formazione si chiude tra 2 ore e quella che hai salvato non è più valida: salvane un'altra."
    assert voce[0]["frase"] == F("dafare.formazione_non_valida", tempo=F("tempo.ore", n=2)).json()
