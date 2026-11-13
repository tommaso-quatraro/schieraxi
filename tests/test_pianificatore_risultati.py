"""Giro leggero dopo le partite: risultati e voti di una giornata la sera stessa, invece di aspettare l'aggiornamento del mattino
(orari simulati, nessuna rete)."""
import contextlib
import sqlite3
import threading
from datetime import datetime

import pytest

from fanta import aggiorna, consigli, pianificatore

ST = "2026-27"
H = lambda giorno, ora, minuto=0: datetime(2026, 11, giorno, ora, minuto)  # noqa: E731
SABATO = [("2026-11-07 15:00", "inter", "lecce"), ("2026-11-07 15:00", "roma", "como"), ("2026-11-07 20:45", "milan", "genoa")]


def _db(giocate=(), con_voti=()):
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE partite (stagione TEXT, giornata INT, data TEXT, casa TEXT, trasferta TEXT, giocata INT)")
    db.executemany("INSERT INTO partite VALUES (?, 11, ?, ?, ?, ?)", [(ST, d, c, t, int(c in giocate)) for d, c, t in SABATO])
    db.execute("INSERT INTO partite VALUES (?, 12, '2026-11-14 15:00', 'inter', 'roma', 0)", (ST,))
    db.execute("CREATE TABLE voti (stagione TEXT, giornata INT, squadra TEXT)")
    db.executemany("INSERT INTO voti VALUES (?, 11, ?)", [(ST, s) for s in con_voti])
    return db


class Scena:
    def __init__(self, monkeypatch, esito=True):
        monkeypatch.setattr(consigli, "stagione_corrente", lambda: ST)
        self.esito, self.chiamate, self.stato = esito, [], {}

    def aggiorna(self, giornate):
        self.chiamate.append(list(giornate))
        return self.esito

    def giro(self, adesso, db=None):
        return pianificatore.giro_risultati(adesso, db or _db(), self.stato, self.aggiorna)


def test_prima_del_tempo_niente(monkeypatch):
    s = Scena(monkeypatch)
    assert s.giro(H(7, 17, 29)) is None and s.chiamate == []        # 15:00 + 2 ore e 30 = 17:30


def test_un_giro_per_orario_anche_con_piu_partite(monkeypatch):
    s = Scena(monkeypatch)
    assert s.giro(H(7, 17, 30)) == "risultati" and s.chiamate == [[11]]
    for m in range(31, 59):
        s.giro(H(7, 17, m))
    assert s.chiamate == [[11]]                                     # due partite alle 15: un giro solo, una volta


def test_il_secondo_giro_solo_se_mancano_ancora_i_voti(monkeypatch):
    s = Scena(monkeypatch)
    s.giro(H(7, 17, 30))
    dopo_il_primo = {"fatti": list(s.stato["fatti"])}
    tutti = _db(giocate=("inter", "roma"), con_voti=("inter", "lecce", "roma", "como"))
    assert s.giro(H(7, 19, 0), tutti) is None and s.chiamate == [[11]]   # alle 19 (15 + 4 ore) è già tutto arrivato
    s2 = Scena(monkeypatch)
    s2.stato = dopo_il_primo
    mancano = _db(giocate=("inter", "roma"), con_voti=("inter", "lecce"))
    assert s2.giro(H(7, 19, 0), mancano) == "risultati" and s2.chiamate == [[11]]


def test_se_il_cron_ha_gia_portato_tutto_nessuna_richiesta(monkeypatch):
    s = Scena(monkeypatch)
    tutto = _db(giocate=("inter", "roma"), con_voti=("inter", "lecce", "roma", "como"))
    assert s.giro(H(7, 17, 30), tutto) is None and s.chiamate == []
    assert any(k.startswith(f"risultati/{ST}/11/2026-11-07 15:00/") for k in s.stato["fatti"])


def test_dopo_un_riavvio_non_si_rifa(monkeypatch, tmp_path):
    s = Scena(monkeypatch)
    s.giro(H(7, 17, 30))
    pianificatore.salva_stato(s.stato, tmp_path / "p.json")
    s2 = Scena(monkeypatch)
    s2.stato = pianificatore.carica_stato(tmp_path / "p.json")
    assert s2.giro(H(7, 17, 40)) is None and s2.chiamate == []


def test_occupato_non_segna_e_si_riprova(monkeypatch):
    s = Scena(monkeypatch, esito=None)                               # aggiornamento completo in corso
    assert s.giro(H(7, 17, 30)) is None and s.stato["fatti"] == []
    s.esito = True
    assert s.giro(H(7, 17, 31)) == "risultati" and len(s.chiamate) == 2


def test_servizio_fermo_a_lungo_niente_giri_vecchi(monkeypatch):
    s = Scena(monkeypatch)
    assert s.giro(H(8, 12, 0)) is None and s.chiamate == []          # oltre 12 ore dal calcio d'inizio: ci pensa il cron


def test_partita_serale_giro_dopo_mezzanotte_non_serve_ma_alle_23_15_si(monkeypatch):
    s = Scena(monkeypatch)
    s.stato["fatti"] = [f"risultati/{ST}/11/2026-11-07 15:00/1", f"risultati/{ST}/11/2026-11-07 15:00/2"]
    assert s.giro(H(7, 23, 15)) == "risultati" and s.chiamate == [[11]]


def test_aggiorna_risultati_due_richieste_e_segna(monkeypatch, tmp_path):
    from fanta import archivio, fonti_attive
    vero = archivio.apri
    monkeypatch.setattr(archivio, "apri", lambda *a, **k: vero(tmp_path / "f.sqlite"))
    monkeypatch.setattr(pianificatore, "blocco_processo", lambda: contextlib.nullcontext(True))
    monkeypatch.setattr(fonti_attive, "acceso", lambda nome: True)
    fatte = []
    monkeypatch.setattr(aggiorna.Aggiornamento, "risultati_giornata", lambda self, g: fatte.append(g))
    assert pianificatore.aggiorna_risultati([11]) is True and fatte == [11]
    db = vero(tmp_path / "f.sqlite")
    assert db.execute("SELECT COUNT(*) FROM aggiornamenti WHERE cosa = ?", (pianificatore.CHIAVE_RISULTATI,)).fetchone()[0] == 1


def test_aggiorna_risultati_con_la_rete_giu_lascia_la_riga_con_l_errore(monkeypatch, tmp_path, caplog):
    """#661: il giro della sera che fallisce lascia la sua riga fra gli aggiornamenti (errore, primo fallimento, ultimo successo),
    così la vede «Stato dei dati» (non la salute), e una riga nel registro con il tipo d'errore."""
    import requests

    from fanta import archivio, fonti_attive, stato_dati
    vero = archivio.apri
    monkeypatch.setattr(archivio, "apri", lambda *a, **k: vero(tmp_path / "f.sqlite"))
    monkeypatch.setattr(pianificatore, "blocco_processo", lambda: contextlib.nullcontext(True))
    monkeypatch.setattr(fonti_attive, "acceso", lambda nome: True)
    ora = ["2026-11-07T17:30:00"]
    monkeypatch.setattr(aggiorna, "_ora", lambda: ora[0])
    monkeypatch.setattr(aggiorna.Aggiornamento, "risultati_giornata", lambda self, g: None)
    assert pianificatore.aggiorna_risultati([11]) is True

    def rete_giu(self, g):
        raise requests.ConnectionError("rete giù")
    monkeypatch.setattr(aggiorna.Aggiornamento, "risultati_giornata", rete_giu)
    for quando in ("2026-11-08T17:30:00", "2026-11-08T19:00:00"):
        ora[0] = quando
        assert pianificatore.aggiorna_risultati([12]) is False
    db = vero(tmp_path / "f.sqlite")
    passo = next(p for p in archivio.passi(db) if p["passo"] == pianificatore.CHIAVE_RISULTATI)
    assert (passo["ultimo_successo"], passo["dal"], passo["ultimo"]) == ("2026-11-07T17:30:00", "2026-11-08T17:30:00",
                                                                         "2026-11-08T19:00:00")
    assert "ConnectionError" in passo["errore"] and "risultati 12" in passo["errore"]
    voce = next(a for a in stato_dati.riepilogo(db, ST, adesso=datetime(2026, 11, 8, 20, 0))["aggiornamenti"]
                if a["cosa"] == pianificatore.CHIAVE_RISULTATI)
    assert voce["quando"] == "2026-11-07T17:30:00" and voce["errori"][0].startswith("Non riuscito alle 19:00 del 08/11:")
    assert archivio.passi_fermi(db, datetime(2026, 11, 9, 18, 0)) == []     # fuori dalla salute (revisione #700)
    db.close()
    righe = [rec.getMessage() for rec in caplog.records if rec.name == "fanta.pianificatore"]
    assert righe and all("ConnectionError" in r for r in righe)


def _sera_fallita(db):
    """Lunedì sera i due giri dei risultati dell'ultima partita della giornata non riescono."""
    from fanta import archivio
    archivio.segna_passo(db, pianificatore.CHIAVE_RISULTATI, "2026-11-01T17:30:00")
    for quando in ("2026-11-02T23:15:00", "2026-11-03T00:45:00"):
        archivio.segna_passo(db, pianificatore.CHIAVE_RISULTATI, quando, "risultati 11: ConnectionError: x")
    db.commit()


def test_la_salute_non_avvisa_per_il_giro_della_sera_durante_la_sosta(tmp_path):
    """Revisione #700: dopo una sera fallita e due settimane di sosta (nessun giro della sera) la salute non manda avvisi per
    questo passo: Fantacalcio.it giù per un giorno lo segnalano già calendario e voti dell'aggiornamento completo."""
    from fanta import archivio, salute
    db = archivio.apri(tmp_path / "a.sqlite")
    _sera_fallita(db)
    archivio.segna(db, "aggiornamento", "2026-11-19T21:55:00", "[]")
    db.commit()
    mandati = []
    manda = lambda titolo, testo, priorita=3, tag="x": mandati.append(testo) or True    # noqa: E731
    assert salute.controlla(db, datetime(2026, 11, 19, 23, 25), tmp_path / "s.json", manda, lambda: True) == []
    assert mandati == [] and archivio.passi_fermi(db, datetime(2026, 11, 19, 23, 25)) == []
    db.close()


@pytest.mark.parametrize("riusciti, tolto", [({"calendario", "voti"}, True), ({"calendario"}, False), ({"voti"}, False)])
def test_l_aggiornamento_completo_con_calendario_e_voti_toglie_l_errore_della_sera(monkeypatch, tmp_path, riusciti, tolto):
    """Revisione #700: se l'aggiornamento della mattina legge calendario e voti, i risultati sono arrivati lo stesso: «Stato dei
    dati» non deve dire «Fermo da 17 giorni» per il giro della sera (l'ultimo successo del giro resta quello di prima)."""
    from fanta import archivio, fonti_attive, funzioni, stato_dati
    db = archivio.apri(tmp_path / "a.sqlite")
    _sera_fallita(db)
    monkeypatch.setattr(fonti_attive, "acceso", lambda nome: True)
    monkeypatch.setattr(funzioni, "acceso", lambda nome: True)
    monkeypatch.setattr(aggiorna, "_ora", lambda: "2026-11-03T03:55:00")

    def rotto(self):
        raise ValueError("pagina strana")
    for metodo in ("listone", "calendario", "voti", "probabili", "understat", "dati_extra", "controlli"):
        monkeypatch.setattr(aggiorna.Aggiornamento, metodo, (lambda self: None) if metodo in riusciti else rotto)
    aggiorna.Aggiornamento(db, aggiorna.Stagione(2026), scrivi=lambda _: None).esegui()
    passo = next(p for p in archivio.passi(db) if p["passo"] == pianificatore.CHIAVE_RISULTATI)
    assert passo["ultimo_successo"] == "2026-11-01T17:30:00"
    assert (passo["errore"] is None) is tolto
    voce = next(a for a in stato_dati.riepilogo(db, ST, adesso=datetime(2026, 11, 20, 0, 0))["aggiornamenti"]
                if a["cosa"] == pianificatore.CHIAVE_RISULTATI)
    assert (voce["errori"] == []) is tolto
    db.close()


def test_fonte_spenta_apposta_toglie_l_errore_del_giro_della_sera(monkeypatch, tmp_path):
    """Come gli altri passi seguiti: una fonte spenta apposta non è un guasto, l'errore di prima si toglie (l'ultimo successo resta)
    e la salute non avvisa più per quel giro."""
    from fanta import archivio, fonti_attive
    vero = archivio.apri
    monkeypatch.setattr(archivio, "apri", lambda *a, **k: vero(tmp_path / "f.sqlite"))
    monkeypatch.setattr(pianificatore, "blocco_processo", lambda: contextlib.nullcontext(True))
    db = vero(tmp_path / "f.sqlite")
    archivio.segna_passo(db, pianificatore.CHIAVE_RISULTATI, "2026-11-07T17:30:00")
    archivio.segna_passo(db, pianificatore.CHIAVE_RISULTATI, "2026-11-08T17:30:00", "risultati 12: ConnectionError: rete giù")
    db.commit()
    db.close()
    monkeypatch.setattr(fonti_attive, "acceso", lambda nome: False)
    assert pianificatore.aggiorna_risultati([12]) is False
    db = vero(tmp_path / "f.sqlite")
    passo = next(p for p in archivio.passi(db) if p["passo"] == pianificatore.CHIAVE_RISULTATI)
    assert passo["errore"] is None and passo["ultimo_successo"] == "2026-11-07T17:30:00"
    assert archivio.passi_fermi(db, datetime(2026, 11, 12, 9, 0)) == []
    db.close()


def test_aggiorna_risultati_fonte_spenta_o_cron_in_corso(monkeypatch, tmp_path):
    from fanta import archivio, fonti_attive
    vero = archivio.apri
    monkeypatch.setattr(archivio, "apri", lambda *a, **k: vero(tmp_path / "f.sqlite"))     # mai l'archivio vero
    monkeypatch.setattr(pianificatore, "blocco_processo", lambda: contextlib.nullcontext(False))
    assert pianificatore.aggiorna_risultati([11]) is None
    monkeypatch.setattr(pianificatore, "blocco_processo", lambda: contextlib.nullcontext(True))
    monkeypatch.setattr(fonti_attive, "acceso", lambda nome: False)
    assert pianificatore.aggiorna_risultati([11]) is False


def test_risultati_giornata_fa_due_richieste(monkeypatch, tmp_path):
    from fanta import archivio, rete
    from fanta.fonti import fantacalcio as fc
    db = archivio.apri(tmp_path / "f.sqlite")
    url = []
    monkeypatch.setattr(rete, "scarica", lambda u, *a, **k: url.append(u) or type("R", (), {"text": ""})())
    partite = [{"id": i, "giornata": 11, "data": "2026-11-07 15:00", "casa": f"c{i}", "trasferta": f"t{i}", "gol_casa": 1,
                "gol_trasferta": 0, "giocata": True} for i in range(10)]
    monkeypatch.setattr(fc, "leggi_calendario", lambda html, g, st: partite)
    monkeypatch.setattr(fc, "leggi_voti", lambda html, g: [])
    agg = aggiorna.Aggiornamento(db, aggiorna.Stagione(2026), lambda _: None)
    monkeypatch.setattr(agg, "_salva_partite", lambda p, st: len(p))
    agg.risultati_giornata(11)
    assert url == [fc.url_calendario(11), fc.url_voti(ST, 11)]


def test_il_thread_fa_anche_il_giro_dei_risultati(tmp_path, monkeypatch):
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: ST)
    monkeypatch.setattr(pianificatore, "FILE_STATO", tmp_path / "pianificatore.json")
    monkeypatch.delenv("FANTA_PIANIFICATORE", raising=False)
    fermo = threading.Event()
    giri = []

    def risultati(giornate):
        giri.append(giornate)
        fermo.set()
        return True

    t = threading.Thread(daemon=True, target=pianificatore.sorveglia, args=(fermo, lambda: [], _db, lambda: True, lambda: None, 0, lambda: H(7, 17, 30)),
                         kwargs={"risultati": risultati})
    t.start()
    t.join(10)
    assert not t.is_alive() and giri == [[11]]
    assert any(k.startswith("risultati/") for k in pianificatore.carica_stato()["fatti"])
