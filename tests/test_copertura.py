"""Copertura della rosa: reparti scoperti o senza ricambi (fanta/copertura.py) e voce in «Da fare». (L'avviso del reparto scoperto
non parte più dalla #693.)"""
import time

import pandas as pd

from fanta import consigli, copertura, da_fare, lega
from fanta.regole import Regole


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
