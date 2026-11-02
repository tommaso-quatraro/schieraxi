"""Copertura della rosa: reparti scoperti o senza ricambi (fanta/copertura.py), voce in «Da fare» e avviso facoltativo."""
import sqlite3
import time
from datetime import datetime

import pandas as pd

from fanta import consigli, copertura, da_fare, lega, notifiche
from fanta.regole import Regole

ST = "2026-27"
ADESSO = datetime(2026, 10, 27, 9, 0)


def _rosa(spec):
    """spec: lista di (ruolo, stato, diffidato). Id progressivi."""
    righe, gioc = [], []
    for n, (ruolo, stato, diff) in enumerate(spec, 1):
        righe.append({"nome": f"{ruolo}{n}", "ruolo": ruolo, "stato": stato, "diffidato": diff})
        gioc.append(lega.GiocatoreRosa(n, f"{ruolo}{n}", ruolo, "ROM", 1))
    return pd.DataFrame(righe, index=range(1, len(spec) + 1)), lega.Rose([lega.Squadra("Mia", gioc)], "Mia")


def _base():
    """3 P, 8 D, 8 C, 6 A tutti disponibili."""
    spec = [("P", None, False)] * 3 + [("D", None, False)] * 8 + [("C", None, False)] * 8 + [("A", None, False)] * 6
    return spec


def _con(spec, ruolo, indisponibili, diffidati=0):
    out, visti = [], 0
    for r, s, d in spec:
        if r == ruolo and visti < indisponibili:
            out.append((r, "infortunato", False))
            visti += 1
        elif r == ruolo and visti < indisponibili + diffidati:
            out.append((r, None, True))
            visti += 1
        else:
            out.append((r, s, d))
    return out


def test_testi_in_inglese_a_richiesta():
    prev, rose = _rosa(_con(_base(), "A", 6))
    assert copertura.analizza(prev, Regole(), rose, "en")["reparti"][0]["testo"].startswith("You have no forward available: you need at least 1.")
    assert copertura.analizza(prev, Regole(), rose)["reparti"][0]["testo"].startswith("Non hai nessun attaccante")      # senza lingua: italiano
    prev, rose = _rosa(_con(_base(), "D", 6))
    assert copertura.analizza(prev, Regole(), rose, "en")["reparti"][0]["testo"].startswith("You have only 2 defenders available: you need at least 3")
    prev, rose = _rosa(_con(_base(), "P", 2))
    assert copertura.analizza(prev, Regole(), rose, "en")["reparti"][0]["testo"] == \
        "You have only 1 goalkeeper available, the minimum to play: if another one is out, you have no cover."
    prev, rose = _rosa(_con(_base(), "D", 4, diffidati=2))
    assert "2 are one yellow card from a ban" in copertura.analizza(prev, Regole(), rose, "en")["reparti"][0]["testo"]


def test_rosa_a_posto_niente_allarme():
    prev, rose = _rosa(_base())
    assert copertura.analizza(prev, Regole(), rose)["reparti"] == []


def test_attaccanti_scoperti_con_plurali_giusti():
    # moduli di base: il meno esigente chiede 1 attaccante (4-5-1)
    prev, rose = _rosa(_con(_base(), "A", 6))
    r = copertura.analizza(prev, Regole(), rose)["reparti"]
    assert r[0]["livello"] == "scoperto" and r[0]["testo"].startswith("Non hai nessun attaccante disponibile: ne servono almeno 1.")
    assert "Fuori: A" in r[0]["testo"]
    prev, rose = _rosa(_con(_base(), "D", 6))                      # restano 2 difensori, ne servono 3
    t = copertura.analizza(prev, Regole(), rose)["reparti"][0]["testo"]
    assert t.startswith("Hai solo 2 difensori disponibili: per giocare ne servono almeno 3.")


def test_un_solo_portiere_e_a_rischio_con_singolare():
    prev, rose = _rosa(_con(_base(), "P", 2))
    r = copertura.analizza(prev, Regole(), rose)["reparti"]
    assert [(x["ruolo"], x["livello"]) for x in r] == [("P", "rischio")]
    assert r[0]["testo"] == "Hai solo 1 portiere disponibile, il minimo per giocare: se un altro salta, resti senza ricambi."


def test_diffidati_contano_come_rischio():
    prev, rose = _rosa(_con(_base(), "P", 0, diffidati=2))         # 3 portieri, 2 diffidati: ne restano 1 sicuro, il minimo e' 1 -> ok
    assert copertura.analizza(prev, Regole(), rose)["reparti"] == []
    prev, rose = _rosa(_con(_base(), "D", 4, diffidati=2))          # 4 disponibili, 2 diffidati: 2 sicuri < 3
    r = copertura.analizza(prev, Regole(), rose)["reparti"][0]
    assert r["livello"] == "rischio" and r["testo"].startswith("Hai 4 difensori disponibili, ma 2 sono diffidati")


def test_i_moduli_della_lega_decidono_il_minimo():
    r = Regole(moduli=["4-4-2"])
    prev, rose = _rosa(_con(_base(), "D", 4))                      # 4 difensori: per il solo 4-4-2 sono il minimo
    x = copertura.analizza(prev, r, rose)["reparti"]
    assert [(y["ruolo"], y["livello"]) for y in x] == [("D", "rischio")]
    prev, rose = _rosa(_con(_base(), "D", 5))
    assert copertura.analizza(prev, r, rose)["reparti"][0]["livello"] == "scoperto"
    # con tutti i moduli normali gli stessi 4 difensori hanno un ricambio
    prev, rose = _rosa(_con(_base(), "D", 4))
    assert copertura.analizza(prev, Regole(), rose)["reparti"] == []


def test_nessun_modulo_possibile_pur_con_ogni_reparto_sufficiente():
    r = Regole(moduli=["3-5-2", "5-3-2"])
    spec = [("P", None, False)] * 2 + [("D", None, False)] * 4 + [("C", None, False)] * 4 + [("A", None, False)] * 3
    prev, rose = _rosa(spec)
    x = copertura.analizza(prev, r, rose)
    assert x["moduli_possibili"] == []
    assert x["reparti"][0]["livello"] == "scoperto" and x["reparti"][0]["ruolo"] is None


def test_senza_previsioni_della_rosa_tace():
    prev, rose = _rosa(_base())
    assert copertura.analizza(prev.iloc[0:0], Regole(), rose) is None


def test_e_veloce():
    prev, rose = _rosa(_con(_base(), "A", 4))
    grande = pd.concat([prev] * 1, ignore_index=False)
    t = time.perf_counter()
    for _ in range(50):
        copertura.analizza(grande, Regole(), rose)
    assert (time.perf_counter() - t) / 50 < 0.05


# ---------------------------------------------------------------- Da fare
def test_voce_da_fare_urgente_e_con_destinazione(monkeypatch):
    prev, rose = _rosa(_con(_con(_base(), "A", 6), "P", 2))
    monkeypatch.setattr(consigli, "previsioni", lambda db, r: (prev, 9, True))
    voci = da_fare._copertura(None, Regole(), rose)
    assert [(v["id"], v["priorita"], v["tipo"]) for v in voci] == [("copertura:A", 1, "copertura"), ("copertura:P", 2, "copertura")]
    assert voci[0]["destinazione"]["scheda"] == "mercato" and voci[0]["azione"] == "Cerca un rimpiazzo" and voci[0]["reparto"] == "A"


# ---------------------------------------------------------------- avviso
def _db():
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE partite (stagione TEXT, giornata INT, data TEXT, giocata INT)")
    db.executemany("INSERT INTO partite VALUES (?,?,?,?)", [(ST, 9, "2026-10-28 18:30", 0), (ST, 9, "2026-10-29 20:45", 0)])
    return db


def _scena(monkeypatch, spec):
    prev, rose = _rosa(spec)
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: ST)
    monkeypatch.setattr(consigli, "prossima_giornata", lambda db, st: 9)
    monkeypatch.setattr(consigli, "previsioni", lambda db, r, g=None: (prev, 9, True))
    mandati = []
    manda = lambda titolo, testo, priorita=3, tag="x": mandati.append((titolo, testo, tag)) or True    # noqa: E731
    return rose, mandati, manda


def test_avviso_una_volta_sola_per_situazione(tmp_path, monkeypatch):
    rose, mandati, manda = _scena(monkeypatch, _con(_base(), "P", 2))
    f = tmp_path / "n.json"
    assert notifiche.copertura(_db(), Regole(), rose, ADESSO, f, manda, {})
    assert len(mandati) == 1 and mandati[0][0] == "SchieraXI · un reparto della rosa è a rischio" and "1 portiere disponibile" in mandati[0][1]
    assert notifiche.copertura(_db(), Regole(), rose, ADESSO, f, manda, {}) == []
    assert len(mandati) == 1                                       # mai ripetuto


def test_se_peggiora_riavvisa_e_se_e_spento_tace(tmp_path, monkeypatch):
    rose, mandati, manda = _scena(monkeypatch, _con(_base(), "P", 2))
    f = tmp_path / "n.json"
    notifiche.copertura(_db(), Regole(), rose, ADESSO, f, manda, {})
    prev, _ = _rosa(_con(_base(), "P", 3))
    monkeypatch.setattr(consigli, "previsioni", lambda db, r, g=None: (prev, 9, True))
    notifiche.copertura(_db(), Regole(), rose, ADESSO, f, manda, {})
    assert len(mandati) == 2 and "scoperto" in mandati[1][0]
    rose2, m2, manda2 = _scena(monkeypatch, _con(_base(), "A", 6))
    assert notifiche.copertura(_db(), Regole(), rose2, ADESSO, tmp_path / "x.json", manda2, {"copertura": False}) == [] and m2 == []


def test_ore_tranquille_riprova_dopo_e_dopo_la_scadenza_non_avvisa(tmp_path, monkeypatch):
    rose, mandati, manda = _scena(monkeypatch, _con(_base(), "P", 2))
    f = tmp_path / "n.json"
    notifiche.copertura(_db(), Regole(), rose, ADESSO, f, lambda *a, **k: False, {})        # invio bloccato
    assert mandati == []
    notifiche.copertura(_db(), Regole(), rose, ADESSO, f, manda, {})
    assert len(mandati) == 1
    assert notifiche.copertura(_db(), Regole(), rose, datetime(2026, 10, 28, 19, 0), tmp_path / "y.json", manda, {}) == []   # formazione chiusa


def test_copertura_si_ferma_alla_scadenza_non_alla_partita(tmp_path, monkeypatch):
    """La formazione si chiude `scadenza_minuti` PRIMA della prima partita (18:30 - 10 = 18:20): dopo non serve più avvisare."""
    rose, mandati, manda = _scena(monkeypatch, _con(_base(), "P", 2))
    regole = Regole(scadenza_minuti=10)
    assert notifiche.copertura(_db(), regole, rose, datetime(2026, 10, 28, 18, 25), tmp_path / "chiusa.json", manda, {}) == []
    assert mandati == []
    assert notifiche.copertura(_db(), regole, rose, datetime(2026, 10, 28, 18, 15), tmp_path / "aperta.json", manda, {})
    assert len(mandati) == 1


def test_copertura_usa_la_giornata_della_lega(tmp_path, monkeypatch):
    """Prima che la lega parta la giornata da giocare è la sua prima (qui 9), non la prossima della Serie A (qui 1)."""
    rose, mandati, manda = _scena(monkeypatch, _con(_base(), "P", 2))
    monkeypatch.setattr(consigli, "prossima_giornata", lambda db, st: 1)
    assert notifiche.copertura(_db(), Regole(prima_giornata_lega=9), rose, ADESSO, tmp_path / "n.json", manda, {})
    assert len(mandati) == 1
