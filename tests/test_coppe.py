"""Turnover: partite di coppa vicine a quelle di campionato."""
from datetime import datetime

from fanta import coppe


def test_finestra_di_tre_giorni():
    assert coppe.coppa_vicina("inter", "2026-11-06 20:45")          # 3 giorni dopo il 3/11
    assert not coppe.coppa_vicina("inter", "2026-11-07 15:00")      # 4 giorni
    assert coppe.coppa_vicina("napoli", datetime(2026, 11, 1, 12, 0))   # 3 giorni prima del 4/11
    assert not coppe.coppa_vicina("lazio", "2026-11-04 18:00")      # la Lazio non gioca in coppa
    assert not coppe.coppa_vicina("inter", None) and not coppe.coppa_vicina("inter", "boh")
    assert coppe.fattore_turnover("milan", "2026-11-07 18:00") == coppe.FATTORE_TURNOVER
    assert coppe.fattore_turnover("lazio", "2026-11-07 18:00") == 1.0
