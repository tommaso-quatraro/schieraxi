"""Pagina «Novità» del web: solo le ultime versioni (le altre a richiesta) e, alla prima visita, «Nuovo» solo sull'ultima.
Collaudo del 1/11/2026: la pagina disegnava tutte le 260 e più versioni, tutte con l'etichetta «Nuovo» alla prima visita."""
import re

from fanta import server

WEB = server.WEB
APP = (WEB / "app.js").read_text(encoding="utf-8")
TESTI = (WEB / "testi.js").read_text(encoding="utf-8")


def _vista():
    inizio = APP.index("async function vistaNovita(")
    return APP[inizio:APP.index("\n}\n", inizio)]


def test_mostra_solo_le_ultime_versioni_con_il_pulsante_per_le_altre():
    m = re.search(r"const NOVITA_VISIBILI = (\d+);", APP)
    assert m and 5 <= int(m.group(1)) <= 20
    v = _vista()
    assert "elenco.slice(0, visibili)" in v and "elenco.map(" not in v      # mai tutto lo storico in una volta
    assert 'id="novita-altre"' in v and 'tp("novita.precedenti", resto)' in v
    assert "elenco.slice(visibili)" in v                                    # al tocco arrivano le altre


def test_prima_visita_nuovo_solo_sull_ultima():
    v = _vista()
    assert "!ultima ? Math.min(1, elenco.length)" in v
    assert "nuoveDa < 0 ||" not in v                                         # niente più «tutto nuovo» se la versione vista non c'è


def test_testi_del_pulsante_in_italiano_e_inglese_con_il_plurale():
    for chiave in ("novita.precedenti.one", "novita.precedenti.other"):
        assert TESTI.count(f'"{chiave}"') == 2                               # blocco it e blocco en
    assert '"novita.precedenti.other": "Mostra le {n} versioni precedenti"' in TESTI
