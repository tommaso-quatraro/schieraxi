"""Giro leggero dopo le partite: risultati e voti di una giornata la sera stessa, invece di aspettare l'aggiornamento del mattino
(orari simulati, nessuna rete)."""
import contextlib
import sqlite3
import threading
from datetime import datetime

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


def test_aggiorna_risultati_fonte_spenta_o_cron_in_corso(monkeypatch):
    from fanta import fonti_attive
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
