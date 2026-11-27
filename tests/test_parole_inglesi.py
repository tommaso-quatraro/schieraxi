"""Le parole vietate dei testi in inglese (`tests/parole_inglesi.py`, usate da `test_inglese_web.py` e `test_novita_inglese.py`)
prendono solo il senso sbagliato: «round» per la giornata, «lock» per la chiusura della formazione. Revisione della #975: «year-round»,
«round to 6.3» e «Lock Screen» davano falsi allarmi, e «Lock Screen» con il motivo sbagliato."""
import pytest

import parole_inglesi as p


@pytest.mark.parametrize("testo", ["When a round is over", "the previous round", "Round 12", "rounds played so far",
                                   "every round", "a match of the round has been brought forward"])
def test_round_per_la_giornata_si_trova(testo):
    assert p.ROUND.search(testo), testo


@pytest.mark.parametrize("testo", ["available year-round", "numbers round to 6.3", "we round up the points", "a round number",
                                   "a round-trip", "rounded to one decimal", "all around the league", "a roundup"])
def test_round_in_altri_sensi_no(testo):
    assert not p.ROUND.search(testo), testo


@pytest.mark.parametrize("testo", ["When does the lineup lock?", "The lineup locks in 3 hours", "lineup locked",
                                   "we lock your lineup at the deadline", "the formation locks"])
def test_lock_per_la_chiusura_della_formazione_si_trova(testo):
    assert p.LOCK.search(testo), testo


@pytest.mark.parametrize("testo", ["Add the widget to the Lock Screen", "Lock Screen widget", "the account is locked",
                                   "unlock the phone", "a lock icon"])
def test_lock_in_altri_sensi_no(testo):
    assert not p.LOCK.search(testo), testo


@pytest.mark.parametrize(("testo", "trovato"), [("Line-ups and predictions", True), ("line-up", True), ("Lineups", False),
                                                ("«Refresh the data»", True), ("“Refresh the data”", False)])
def test_line_up_e_virgolette(testo, trovato):
    assert bool(p.LINE_UP.search(testo) or p.VIRGOLETTE.search(testo)) is trovato, testo
