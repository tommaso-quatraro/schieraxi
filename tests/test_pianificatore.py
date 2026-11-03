"""Pianificatore: giri in più di probabili e infortuni a 60, 30 e 15 minuti dalla scadenza (orari simulati, nessuna rete)."""
import contextlib
import sqlite3
import threading
from datetime import datetime, timedelta

from fanta import consigli, pianificatore, regole
from fanta.regole import Regole

ST = "2026-27"
H = lambda ora, minuto=0: datetime(2026, 11, 7, ora, minuto)  # noqa: E731


def _db(rilevato=None):
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE partite (stagione TEXT, giornata INT, data TEXT, giocata INT)")
    db.executemany("INSERT INTO partite VALUES (?,?,?,?)", [(ST, 10, "2026-11-07 18:30", 0), (ST, 10, "2026-11-08 20:45", 0)])
    db.execute("CREATE TABLE probabili (stagione TEXT, giornata INT, fonte TEXT, rilevato TEXT)")
    if rilevato:
        db.execute("INSERT INTO probabili VALUES (?, 10, 'fantacalcio', ?)", (ST, rilevato))
    return db


class Scena:
    def __init__(self, monkeypatch, minuti=10, riesce=True):
        monkeypatch.setattr(consigli, "stagione_corrente", lambda: ST)
        monkeypatch.setattr(consigli, "prossima_giornata", lambda db, st, adesso=None: 10)
        self.regole = regole.imposta(Regole(), "scadenza_minuti", str(minuti))
        self.riesce, self.letture, self.dopo_volte, self.stato = riesce, 0, 0, {}

    def aggiorna(self):
        self.letture += 1
        return self.riesce

    def dopo(self):
        self.dopo_volte += 1

    def giro(self, adesso, db=None, leghe=None):
        return pianificatore.giro(adesso, db or _db(), leghe or [self.regole], self.stato, self.aggiorna, self.dopo)


def test_giro_dovuto_da_n_minuti_prima_fino_alla_scadenza():
    scad = H(18, 20)
    assert pianificatore.giro_dovuto(H(17, 19), scad, set(), "p") == (None, [])
    assert pianificatore.giro_dovuto(H(17, 20), scad, set(), "p") == ("60", ["p/60"])
    assert pianificatore.giro_dovuto(H(17, 20), scad, {"p/60"}, "p") == (None, [])
    assert pianificatore.giro_dovuto(H(17, 50), scad, {"p/60"}, "p") == ("30", ["p/30"])
    assert pianificatore.giro_dovuto(H(18, 20), scad, set(), "p") == (None, [])          # scaduta
    assert pianificatore.giro_dovuto(H(17, 20), None, set(), "p") == (None, [])


def test_tre_giri_alla_scadenza_meno_dieci_minuti_della_regola(monkeypatch):
    s = Scena(monkeypatch)                                     # partita 18:30, scadenza 18:20
    assert s.giro(H(17, 15)) is None and s.letture == 0
    assert s.giro(H(17, 20)) == "60" and (s.letture, s.dopo_volte) == (1, 1)
    assert s.giro(H(17, 21)) is None and s.letture == 1        # non si ripete
    assert s.giro(H(17, 49)) is None
    assert s.giro(H(17, 50)) == "30" and s.letture == 2
    assert s.giro(H(18, 5)) == "15" and (s.letture, s.dopo_volte) == (3, 3)
    assert s.giro(H(18, 6)) is None and s.giro(H(18, 20)) is None and s.giro(H(18, 25)) is None   # dopo la scadenza: mai più
    assert s.letture == 3


def test_servizio_fermo_se_ne_scadono_due_se_ne_fa_uno(monkeypatch):
    s = Scena(monkeypatch)
    assert s.giro(H(18, 10)) == "15" and s.letture == 1        # 60 e 30 sono già passati: non si rifanno a raffica
    assert s.giro(H(18, 11)) is None and s.letture == 1


def test_senza_la_regola_si_conta_dalla_partita(monkeypatch):
    s = Scena(monkeypatch, minuti=0)
    assert s.giro(H(17, 29)) is None
    assert s.giro(H(17, 30)) == "60" and s.giro(H(18, 29)) == "15"


def test_impostazione_spenta_nessun_giro(monkeypatch):
    s = Scena(monkeypatch)
    spenta = regole.imposta(s.regole, "aggiornamenti_vicino_scadenza", "false")
    assert s.giro(H(17, 20), leghe=[spenta]) is None and s.letture == 0
    assert s.giro(H(17, 20), leghe=[spenta, s.regole]) == "60"          # basta una lega con l'impostazione accesa


def test_probabili_lette_da_poco_non_si_rileggono(monkeypatch):
    s = Scena(monkeypatch)
    assert s.giro(H(17, 20), db=_db("2026-11-07 17:15:00")) is None and s.letture == 0     # il cron le ha lette 5 minuti fa
    assert s.giro(H(17, 21)) is None                                                        # e il giro conta come fatto
    assert s.giro(H(17, 50), db=_db("2026-11-07 17:30:00")) == "30" and s.letture == 1


def test_se_la_lettura_fallisce_niente_ricalcolo_e_niente_ripetizioni(monkeypatch):
    s = Scena(monkeypatch, riesce=False)
    assert s.giro(H(17, 20)) == "60" and (s.letture, s.dopo_volte) == (1, 0)
    assert s.giro(H(17, 22)) is None and s.letture == 1       # il giro è segnato: la fonte non viene martellata


def test_leghe_con_scadenze_diverse_una_sola_lettura(monkeypatch):
    s = Scena(monkeypatch)
    altra = regole.imposta(Regole(), "scadenza_minuti", "0")
    assert s.giro(H(17, 20), leghe=[s.regole, altra]) == "60" and s.letture == 1


def test_interruttore_ambiente(monkeypatch):
    monkeypatch.delenv("FANTA_PIANIFICATORE", raising=False)
    assert pianificatore.acceso()
    for v in ("0", "no", "off", "False"):
        monkeypatch.setenv("FANTA_PIANIFICATORE", v)
        assert not pianificatore.acceso()
    monkeypatch.setenv("FANTA_PIANIFICATORE", "1")
    assert pianificatore.acceso()


def test_il_thread_fa_il_giro_ricorda_lo_stato_e_si_ferma(tmp_path, monkeypatch):
    s = Scena(monkeypatch)
    monkeypatch.setattr(pianificatore, "FILE_STATO", tmp_path / "pianificatore.json")
    monkeypatch.setattr(pianificatore, "blocco_processo", lambda: contextlib.nullcontext(True))
    monkeypatch.delenv("FANTA_PIANIFICATORE", raising=False)
    fermo = threading.Event()
    giri = []

    def dopo():
        giri.append(1)
        fermo.set()

    t = threading.Thread(target=pianificatore.sorveglia, args=(fermo, lambda: [s.regole], _db, lambda: True, dopo, 0, lambda: H(17, 25)))
    t.start()
    t.join(10)
    assert not t.is_alive() and giri == [1]
    assert pianificatore.carica_stato()["fatti"] == [f"{ST}/10/10/60"]


def test_spento_con_la_variabile_il_thread_non_fa_niente(tmp_path, monkeypatch):
    s = Scena(monkeypatch)
    monkeypatch.setattr(pianificatore, "FILE_STATO", tmp_path / "pianificatore.json")
    monkeypatch.setenv("FANTA_PIANIFICATORE", "0")
    fermo = threading.Event()
    chiamate = []
    t = threading.Thread(target=pianificatore.sorveglia, args=(fermo, lambda: [s.regole], _db, lambda: chiamate.append(1) or True, lambda: None, 0.01,
                                                              lambda: H(17, 25)))
    t.start()
    fermo.wait(0.2)
    fermo.set()
    t.join(10)
    assert chiamate == [] and not (tmp_path / "pianificatore.json").exists()


def test_distanza_minima_tra_le_letture():
    assert pianificatore.DISTANZA_MINIMA >= timedelta(minutes=5)


def test_occupato_non_segna_il_giro_e_si_riprova(monkeypatch):
    s = Scena(monkeypatch)
    s.aggiorna = lambda: None                                   # aggiornamento completo in corso
    assert s.giro(H(17, 20)) is None and s.stato["fatti"] == []
    s.aggiorna = lambda: True
    assert s.giro(H(17, 21)) == "60"                            # al controllo dopo riprova


def test_il_blocco_di_file_si_tiene_solo_durante_il_download(monkeypatch):
    eventi = []

    @contextlib.contextmanager
    def blocco():
        eventi.append("preso")
        yield True
        eventi.append("rilasciato")

    monkeypatch.setattr(pianificatore, "blocco_processo", blocco)
    monkeypatch.setattr(pianificatore, "_scarica_probabili", lambda scrivi: eventi.append("scarico") or True)
    assert pianificatore.aggiorna_probabili() is True
    assert eventi == ["preso", "scarico", "rilasciato"]
    monkeypatch.setattr(pianificatore, "blocco_processo", lambda: contextlib.nullcontext(False))
    assert pianificatore.aggiorna_probabili() is None           # cron in corso: si rinuncia


def test_stato_salvato_anche_se_il_giro_va_in_errore(tmp_path, monkeypatch, caplog):
    s = Scena(monkeypatch)
    monkeypatch.setattr(pianificatore, "FILE_STATO", tmp_path / "pianificatore.json")
    monkeypatch.delenv("FANTA_PIANIFICATORE", raising=False)
    fermo = threading.Event()

    def aggiorna():
        fermo.set()
        raise RuntimeError("dati segreti")

    with caplog.at_level("WARNING"):
        pianificatore.sorveglia(fermo, lambda: [s.regole], _db, aggiorna, lambda: None, 0, lambda: H(17, 25))
    assert pianificatore.carica_stato()["fatti"] == [f"{ST}/10/10/60"]
    assert "RuntimeError" in caplog.text and "dati segreti" not in caplog.text


def test_lega_a_serie_a_solo_giornate_vere():
    r = regole.imposta(Regole(), "prima_giornata_lega", "4")
    assert regole.lega_a_serie_a(1, r) == 4 and regole.lega_a_serie_a(35, r) == 38
    assert regole.lega_a_serie_a(36, r) is None and regole.lega_a_serie_a(0, r) is None
