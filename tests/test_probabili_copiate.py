"""Probabili copiate dalla giornata prima (#608): la mattina dopo una giornata la pagina ha già il numero della giornata nuova ma
tiene le formazioni di quella finita. Quella lettura resta nella storia con il segno `copia`, ma per il resto dell'app la giornata
è ancora «senza probabili». Dati inventati, nessuna richiesta in rete."""
import sqlite3
from types import SimpleNamespace

import pandas as pd
import pytest

from fanta import aggiorna, archivio, consigli, lega, notifiche
from fanta.regole import Regole

ST = "2026-27"
PARTITA = {11: 1101, 12: 1201}          # una partita per giornata (codici inventati)
DATA = {11: "2026-11-07 15:00", 12: "2026-11-14 15:00"}


def _righe(giornata: int, cambiati: int = 0) -> list[dict]:
    """Una partita: 22 titolari e 8 in panchina. `cambiati` = quanti titolari diventano panchina (lettura nuova)."""
    righe = []
    for i in range(30):
        titolare = i < 22 and i >= cambiati
        righe.append({"calciatore_id": 100 + i, "squadra": "casa" if i % 2 else "ospite", "partita_id": PARTITA[giornata],
                      "stato": "titolare" if titolare else "panchina", "percentuale": 90.0 if titolare else 30.0,
                      "in_dubbio": 0, "diffidato": 0, "nota": None})
    if cambiati:                                  # chi esce dai titolari è sostituito da uno della panchina
        for r in righe[22:22 + cambiati]:
            r.update(stato="titolare", percentuale=60.0)
    return righe


@pytest.fixture
def db(tmp_path):
    d = archivio.apri(tmp_path / "t.sqlite")
    for g, pid in PARTITA.items():
        d.execute("INSERT INTO partite (id, stagione, giornata, data, casa, trasferta, giocata) VALUES (?, ?, ?, ?, 'casa', "
                  "'ospite', ?)", (pid, ST, g, DATA[g], int(g == 11)))
    d.commit()
    yield d
    d.close()


def _leggi(db, monkeypatch, giornata, righe, ora):
    monkeypatch.setattr(aggiorna.rete, "scarica", lambda *a, **k: SimpleNamespace(text=""))
    monkeypatch.setattr(aggiorna.fc, "leggi_probabili", lambda html: (giornata, [dict(r) for r in righe]))
    monkeypatch.setattr(aggiorna, "_ora", lambda: ora)
    scritte = []
    aggiorna.Aggiornamento(db, aggiorna.Stagione(2026), scrivi=scritte.append).probabili()
    db.commit()
    return scritte


def _giornata_11_e_copia(db, monkeypatch):
    _leggi(db, monkeypatch, 11, _righe(11), "2026-11-07T13:00:00")              # le probabili vere della giornata 11
    return _leggi(db, monkeypatch, 12, _righe(12), "2026-11-09T08:03:00")       # il mattino dopo: stesse formazioni, giornata 12


def test_la_copia_resta_nella_storia_con_il_segno_ma_non_diventa_le_probabili(db, monkeypatch):
    scritte = _giornata_11_e_copia(db, monkeypatch)
    assert db.execute("SELECT COUNT(*) FROM probabili WHERE stagione = ? AND giornata = 12", (ST,)).fetchone()[0] == 0
    storia = db.execute("SELECT COUNT(*), MIN(copia), MAX(copia) FROM probabili_storia WHERE giornata = 12").fetchone()
    assert tuple(storia) == (30, 1, 1)
    assert db.execute("SELECT MAX(copia) FROM probabili_storia WHERE giornata = 11").fetchone()[0] == 0
    assert any("copia" in s and "giornata 11" in s for s in scritte)
    # la giornata 11 resta com'era
    assert db.execute("SELECT COUNT(*) FROM probabili WHERE giornata = 11").fetchone()[0] == 30


def test_dopo_la_copia_l_ora_delle_probabili_non_avanza(db, monkeypatch):
    _giornata_11_e_copia(db, monkeypatch)
    # la stessa lettura di gestione.py («Probabili aggiornate alle…») e di pianificatore.probabili_recenti
    assert db.execute("SELECT MAX(rilevato) FROM probabili WHERE stagione = ? AND giornata = 12 AND fonte = 'fantacalcio'",
                      (ST,)).fetchone()[0] is None
    assert db.execute("SELECT MAX(rilevato) FROM probabili WHERE fonte = 'fantacalcio'").fetchone()[0] == "2026-11-07T13:00:00"


def test_la_copia_non_fa_partire_falsi_avvisi_di_cambi(db, monkeypatch, tmp_path):
    """Prima: la copia diventava le probabili della giornata 12, il giro dei cambi la memorizzava e alla lettura vera di mezzogiorno
    avvisava di «cambi» che erano solo la differenza tra la giornata finita e quella nuova. Ora la copia non conta: il primo giro
    trova la giornata «senza probabili» e non memorizza niente; la lettura vera è la prima, e la prima non avvisa.
    `consigli.previsioni` qui è finta (niente modello), ma stati e «con probabili» si leggono davvero dalla tabella `probabili`,
    con la regola di consigli._calcola_previsioni (`not prob.empty`)."""
    from datetime import datetime
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: ST)
    monkeypatch.setattr(consigli, "giornata_da_giocare", lambda d, st, regole=None, adesso=None: 12)
    def previsioni(d, regole, g):
        prob = pd.read_sql_query("SELECT calciatore_id AS id, stato, percentuale, in_dubbio AS dubbio, diffidato FROM probabili "
                                 "WHERE stagione = ? AND giornata = ? AND fonte = 'fantacalcio'", d, params=(ST, g))
        prob["nome"] = [f"Finto{i}" for i in prob["id"]]
        return prob.set_index("id"), g, not prob.empty
    monkeypatch.setattr(consigli, "previsioni", previsioni)

    def formazione(d, regole, rose, *a, giornata=None, **k):
        """La consigliata finta: il giocatore 100 se gioca, come la vera lo toglie quando non gioca più (l'avviso dei cambi parte
        solo quando la consigliata cambia, #676: se la copia fosse memorizzata, il suo passaggio in panchina lo farebbe partire)."""
        prev, _, _ = previsioni(d, regole, giornata)
        gioca = 100 in prev.index and prev.at[100, "stato"] not in notifiche.MOTIVI_FUORI
        return {"modulo": "4-3-3", "titolari": [{"id": 100, "nome": "Finto100"}] if gioca else []}
    monkeypatch.setattr(consigli, "formazione", formazione)
    mandati = []
    rose = lega.Rose([lega.Squadra("Mia", [lega.GiocatoreRosa(100, "Finto100", "C", "CAS", 10)])], "Mia")

    def giro(ora):
        return notifiche.cambi(db, Regole(), rose, adesso=ora, file_stato=tmp_path / "n.json",
                               manda=lambda *a, **k: mandati.append(a) or True, opzioni={"cambi": True},
                               file_scelte=tmp_path / "s.json")
    _giornata_11_e_copia(db, monkeypatch)
    giro(datetime(2026, 11, 9, 9, 0))
    _leggi(db, monkeypatch, 12, _righe(12, cambiati=6), "2026-11-09T13:03:00")    # il giocatore 100 passa in panchina
    giro(datetime(2026, 11, 9, 14, 0))
    assert mandati == []


def test_una_lettura_nuova_della_giornata_vale_subito(db, monkeypatch):
    _leggi(db, monkeypatch, 11, _righe(11), "2026-11-07T13:00:00")
    _leggi(db, monkeypatch, 12, _righe(12, cambiati=6), "2026-11-09T13:03:00")    # 6 titolari su 22 cambiati: 80% uguale
    assert db.execute("SELECT COUNT(*), MAX(rilevato) FROM probabili WHERE giornata = 12").fetchone()[:] == (30, "2026-11-09T13:03:00")
    assert db.execute("SELECT MAX(copia) FROM probabili_storia WHERE giornata = 12").fetchone()[0] == 0


def test_dopo_la_copia_arrivano_quelle_vere(db, monkeypatch):
    _giornata_11_e_copia(db, monkeypatch)
    _leggi(db, monkeypatch, 12, _righe(12, cambiati=6), "2026-11-09T13:03:00")
    assert db.execute("SELECT COUNT(*), MAX(rilevato) FROM probabili WHERE giornata = 12").fetchone()[:] == (30, "2026-11-09T13:03:00")
    segni = db.execute("SELECT rilevato, MAX(copia) FROM probabili_storia WHERE giornata = 12 GROUP BY rilevato ORDER BY 1").fetchall()
    assert [tuple(r) for r in segni] == [("2026-11-09T08:03:00", 1), ("2026-11-09T13:03:00", 0)]


def test_la_copia_si_riconosce_finche_la_giornata_non_ha_probabili_vere(db, monkeypatch):
    """Se a mezzogiorno la redazione non ha ancora riscritto la pagina, anche la seconda lettura è una copia."""
    _giornata_11_e_copia(db, monkeypatch)
    _leggi(db, monkeypatch, 12, _righe(12), "2026-11-09T13:03:00")
    assert db.execute("SELECT COUNT(*) FROM probabili WHERE giornata = 12").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM probabili_storia WHERE giornata = 12 AND copia = 1").fetchone()[0] == 60


def test_una_giornata_gia_accettata_non_si_confronta_piu(db, monkeypatch):
    """Dopo una lettura vera, le letture dopo valgono sempre (anche se per caso somigliano alla giornata prima)."""
    _leggi(db, monkeypatch, 11, _righe(11), "2026-11-07T13:00:00")
    _leggi(db, monkeypatch, 12, _righe(12, cambiati=6), "2026-11-09T13:03:00")
    _leggi(db, monkeypatch, 12, _righe(12), "2026-11-09T17:03:00")
    assert db.execute("SELECT MAX(rilevato) FROM probabili WHERE giornata = 12").fetchone()[0] == "2026-11-09T17:03:00"


def test_prima_giornata_senza_giornata_prima_vale_sempre(db, monkeypatch):
    _leggi(db, monkeypatch, 11, _righe(11), "2026-11-07T13:00:00")
    assert db.execute("SELECT COUNT(*) FROM probabili WHERE giornata = 11").fetchone()[0] == 30


def test_archivio_vecchio_riceve_il_segno_senza_perdere_nulla(tmp_path):
    """Un archivio con `probabili_storia` senza la colonna `copia` si apre, riceve la colonna (le letture di prima valgono 0) e
    tiene i dati."""
    f = tmp_path / "vecchio.sqlite"
    c = sqlite3.connect(f)
    c.execute("CREATE TABLE probabili_storia (stagione TEXT, giornata INTEGER, fonte TEXT, calciatore_id INTEGER, squadra TEXT, "
              "partita_id INTEGER, stato TEXT, percentuale REAL, in_dubbio INTEGER, diffidato INTEGER, nota TEXT, rilevato TEXT, "
              "PRIMARY KEY (stagione, giornata, fonte, calciatore_id, rilevato))")
    c.execute("INSERT INTO probabili_storia VALUES ('2026-27', 9, 'fantacalcio', 1, 'x', 1, 'titolare', 90, 0, 0, NULL, 't')")
    c.commit()
    c.close()
    for _ in range(2):                                            # la seconda apertura non rifà niente
        d = archivio.apri(f)
        try:
            assert tuple(d.execute("SELECT COUNT(*), MAX(copia) FROM probabili_storia").fetchone()) == (1, 0)
        finally:
            d.close()
