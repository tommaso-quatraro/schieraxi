"""Forma del file delle rose (lega.da_dict): i tipi dei campi si controllano, così un file strano dà un errore chiaro
invece di far andare in errore chi lo usa dopo."""
import pytest

from fanta import lega

GIOCATORE = {"id": 1, "nome": "Rossi", "ruolo": "A", "squadra": "ROM"}


def _rose(squadra: dict | None = None, **campi) -> dict:
    return {"squadre": [{"nome": "Mia", "giocatori": [GIOCATORE]} | (squadra or {})], "mia_squadra": "Mia"} | campi


@pytest.mark.parametrize("dati", [
    _rose(mia_squadra=1),
    _rose(mia_squadra=["Mia"]),
    _rose({"nome": 5}),
    _rose({"nome": None}),
    _rose({"nome_importato": ["Vecchia"]}),
    _rose({"crediti_residui": "100"}),
    _rose({"crediti_residui": float("inf")}),
    _rose({"giocatori": [GIOCATORE | {"id": "1"}]}),
    _rose({"giocatori": [GIOCATORE | {"id": True}]}),
    _rose({"giocatori": [GIOCATORE | {"nome": 7}]}),
    _rose({"giocatori": [GIOCATORE | {"ruolo": 1}]}),
    _rose({"giocatori": [GIOCATORE | {"squadra": {"a": 1}}]}),
    _rose({"giocatori": [GIOCATORE | {"costo": "10"}]}),
    _rose({"giocatori": [GIOCATORE | {"costo": float("nan")}]}),
    _rose({"giocatori": [GIOCATORE | {"riconosciuto": 3}]}),
    _rose({"giocatori": [GIOCATORE | {"avviso": None}]}),
    _rose({"giocatori": {"a": GIOCATORE}}),
    _rose(aggiornato=12),
    {"squadre": {"Mia": {}}},
])
def test_lega_rose_con_tipi_sbagliati_danno_un_errore_chiaro(dati):
    with pytest.raises(ValueError) as e:
        lega.da_dict(dati)
    assert str(e.value) == lega.FORMA_SBAGLIATA


def test_lega_rose_con_i_tipi_giusti_si_leggono():
    r = lega.da_dict(_rose({"crediti_residui": 12.5, "nome_importato": "",
                            "giocatori": [GIOCATORE | {"costo": 10, "riconosciuto": "simile", "avviso": "x"},
                                          {"id": None, "nome": "Ignoto", "ruolo": None, "squadra": None, "costo": None}]},
                           aggiornato=None))
    s = r.squadre[0]
    assert (s.nome, s.crediti_residui, s.nome_importato, r.aggiornato) == ("Mia", 12.5, None, "")
    assert [g.id for g in s.giocatori] == [1, None] and r.squadra(r.mia_squadra) is s
    assert lega.da_dict({"squadre": [], "mia_squadra": None}).mia_squadra is None
