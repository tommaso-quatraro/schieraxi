"""Stato dei dati, web: gli indicatori del consiglio di formazione (#366, campo `consiglio` della PR #362). Per ogni indicatore la
media, la soglia e «regge» / «non regge» / «servono ancora N giornate», come il registro delle giornate (#344). I dati vengono dalle
funzioni vere del server (`indicatori_consiglio.giro` e `riepilogo`); la carta la disegna la funzione vera di `app.js`, con node."""
import json
import re
import shutil
import subprocess
from datetime import datetime

import pytest

from fanta import indicatori_consiglio as ic
from fanta import server

WEB = server.WEB
APP = (WEB / "app.js").read_text(encoding="utf-8")
TESTI_JS = (WEB / "testi.js").read_text(encoding="utf-8")
NODE = shutil.which("node")
ST = "2026-27"
C1 = "Punti in più della consigliata rispetto alla scelta semplice"
C2 = "Cambi della consigliata nelle 24 ore prima della scadenza"
C3 = "Titolari che rischiano di non giocare"
C4 = "Scelte strane senza un motivo detto"
# la stessa risposta per i test dell'iPhone (ConsiglioFormazioneTests): 8 giornate, due utenti, C1 e C2 fuori soglia
FIXTURE_IOS = server.WEB.parent.parent / "ios" / "Tests" / "Fixtures" / "stato-dati-consiglio.json"


def _voce(g, meno_s2=1.0, meno_schierata=None, cambi=1, sotto=0, improbabili=0, con_compagno=0, storte=1, spiegate=1,
          senza_motivo=1):
    """Una voce del Diario con i suoi indicatori, come le scrive `diario` (solo quello che serve ai totali)."""
    return {"stagione": ST, "giornata": g, "consiglio": {
        "mostrata": "istantanea", "punti_consigliata": 70.0, "punti_s2": 70.0 - meno_s2,
        "punti_schierata": None if meno_schierata is None else 70.0 - meno_schierata, "cambi": cambi, "cambi_sotto_soglia": sotto,
        "improbabili": improbabili, "con_compagno": con_compagno, "reparti": 4, "storte": storte, "spiegate": spiegate,
        "titolari": 11, "vuoti": 0, "senza_motivo": senza_motivo}}


def _consiglio(tmp_path, diari) -> dict:
    """Il campo `consiglio` di /api/stato-dati dopo il giro del cron sui Diari `diari` (una lista di voci per utente)."""
    file = tmp_path / f"indicatori-{len(list(tmp_path.iterdir()))}.json"
    ic.giro(lambda titolo, testo: True, diari=diari, file=file, adesso=datetime(2026, 11, 5, 21, 0))
    return json.loads(json.dumps(ic.riepilogo(file)))


def _otto(tmp_path) -> dict:
    """8 giornate e due utenti: il primo +1,5 punti sulla scelta semplice, il secondo +0,5 e −0,25 contro la sua schierata nelle
    giornate dispari, 2 cambi a giornata e uno per poco nell'ultima; un titolare improbabile ma senza compagni che giocano."""
    primo = [_voce(g, meno_s2=1.5) for g in range(1, 9)]
    secondo = [_voce(g, meno_s2=0.5, meno_schierata=-0.25 if g % 2 else None, cambi=2, sotto=1 if g == 8 else 0, improbabili=1,
                     senza_motivo=0) for g in range(1, 9)]
    return _consiglio(tmp_path, [primo, secondo])


def _codice() -> str:
    """Le funzioni vere di app.js: `esc`, `num`, `segno` e il blocco del registro e del consiglio (fino a «Stato dei dati»)."""
    esc = APP[APP.index("function esc(x)"):APP.index("\n}\n", APP.index("function esc(x)")) + 3]
    righe = [re.search(rf"^const {n} = .*$", APP, re.M).group(0) for n in ("num", "segno")]
    inizio = APP.index("// Registro delle giornate")
    blocco = APP[inizio:APP.index("// Stato dei dati: da dove arriva tutto", inizio)]
    return esc + "\n".join(righe) + "\n" + blocco


def _carta(consiglio, lingua="it") -> str:
    if NODE is None:
        pytest.skip("serve node")
    prova = TESTI_JS + f'\nLINGUA = "{lingua}";\n' + _codice() + f"\nconsole.log(JSON.stringify(cartaConsiglio({json.dumps(consiglio)})));"
    r = subprocess.run([NODE, "-"], input=prova, capture_output=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def _testi(html: str) -> list[str]:
    """I pezzi di testo della carta, nell'ordine in cui si leggono."""
    return [p.strip() for p in re.sub(r"<[^>]+>", "\n", html).split("\n") if p.strip()]


def _dopo(pezzi: list[str], testo: str) -> str:
    """Il pezzo che segue `testo` (lo stato accanto al nome dell'indicatore)."""
    assert testo in pezzi, pezzi
    return pezzi[pezzi.index(testo) + 1]


def test_con_8_giornate_medie_soglie_e_verdetto_del_server(tmp_path):
    c = _otto(tmp_path)
    assert c["verdetto"] and c["regge"] == {"C1": False, "C2": False, "C3": True, "C4": True}
    html = _carta(c)
    pezzi = _testi(html)
    assert pezzi[0] == "Consiglio di formazione"
    assert "Media delle ultime 8 giornate, su 16 formazioni." in pezzi
    assert (_dopo(pezzi, C1), _dopo(pezzi, C2), _dopo(pezzi, C3), _dopo(pezzi, C4)) == ("non regge", "non regge", "regge", "regge")
    assert _dopo(pezzi, "non regge") == ("+1,00 punti a giornata (deve stare a 0 o più) · −0,25 rispetto alla formazione schierata, "
                                         "quando è diversa")
    assert ("1,5 a formazione, in media · per meno di 1 punto atteso, senza un titolare diventato fuori o improbabile: 1 "
            "(devono essere 0)") in pezzi
    assert "sotto il 20% o fuori: 8 · con un compagno di ruolo al 50% o più tra gli esclusi: 0 (devono essere 0)" in pezzi
    assert ("spiegate 16 su 16 (devono essere tutte) · titolari senza un motivo loro in «Perché questo numero»: 4,5% "
            "(al massimo 10%)") in pezzi
    assert re.search(r'style="color:var\(--rosso\)">non regge<', html)          # il colore accompagna la parola, non la sostituisce
    assert re.search(r'style="color:var\(--verde\)">regge<', html)


def test_il_verdetto_viene_dal_server_non_dal_client(tmp_path):
    """Se il server dice «regge» per un numero fuori soglia, la web scrive «regge»: le soglie non si ricalcolano qui."""
    c = _otto(tmp_path)
    c["regge"] = {"C1": True, "C2": None, "C3": False, "C4": True}
    pezzi = _testi(_carta(c))
    assert (_dopo(pezzi, C1), _dopo(pezzi, C2), _dopo(pezzi, C3), _dopo(pezzi, C4)) == ("regge", "ancora nessun dato", "non regge",
                                                                                       "regge")


def test_prima_di_8_giornate_quante_ne_servono(tmp_path):
    c = _consiglio(tmp_path, [[_voce(g) for g in range(1, 4)]])
    assert not c["verdetto"]
    pezzi = _testi(_carta(c))
    assert "Media delle ultime 3 giornate, su 3 formazioni." in pezzi
    for nome in (C1, C2, C3, C4):
        assert _dopo(pezzi, nome) == "servono ancora 5 giornate"
    assert "+1,00 punti a giornata (deve stare a 0 o più)" in pezzi                # senza schierata diversa: solo la scelta semplice
    assert "rispetto alla formazione schierata" not in " ".join(pezzi)


@pytest.mark.parametrize(("giornate", "riga", "stato"), [
    (1, "Media di 1 giornata, su 1 formazione.", "servono ancora 7 giornate"),
    (7, "Media delle ultime 7 giornate, su 7 formazioni.", "serve ancora 1 giornata"),
])
def test_plurali(tmp_path, giornate, riga, stato):
    pezzi = _testi(_carta(_consiglio(tmp_path, [[_voce(g) for g in range(1, giornate + 1)]])))
    assert riga in pezzi and _dopo(pezzi, C1) == stato


def test_senza_giornate_misurate_solo_la_spiegazione(tmp_path):
    pezzi = _testi(_carta(_consiglio(tmp_path, [])))
    assert pezzi[0] == "Consiglio di formazione"
    assert any(p.startswith("Ancora nessuna giornata misurata") for p in pezzi)
    assert C1 not in pezzi and "–" not in " ".join(pezzi)


def test_numeri_che_mancano_si_scrivono_con_la_lineetta(tmp_path):
    """Voci di prima degli indicatori (senza punti né istantanea): la riga c'è, i numeri sono «–», mai «null» o «NaN»."""
    voci = [{"stagione": ST, "giornata": g, "consiglio": dict.fromkeys(_voce(g)["consiglio"]) | {"mostrata": "ricostruita"}}
            for g in range(1, 9)]
    c = _consiglio(tmp_path, [voci])
    assert c["verdetto"] and c["meno_s2"] is None and c["regge"]["C1"] is None
    pezzi = _testi(_carta(c))
    assert _dopo(pezzi, C1) == "ancora nessun dato"
    assert "– punti a giornata (deve stare a 0 o più)" in pezzi
    assert "null" not in " ".join(pezzi) and "NaN" not in " ".join(pezzi)


def test_senza_campo_consiglio_niente_carta():
    assert _carta(None) == ""


@pytest.mark.parametrize("lingua", ["it", "en"])
def test_niente_chiavi_mancanti_ne_numeri_rotti(tmp_path, lingua):
    for c in (_consiglio(tmp_path, [[_voce(g) for g in range(1, 4)]]), _otto(tmp_path), _consiglio(tmp_path, [])):
        testo = " ".join(_testi(_carta(c, lingua)))
        assert "sd.cons_" not in testo and "sd.reg_" not in testo
        assert "undefined" not in testo and "NaN" not in testo and "null" not in testo


def test_niente_sigle_degli_indicatori():
    """Per chi legge ci sono le parole, mai «C1»... «C4»."""
    carta = APP[APP.index("function cartaConsiglio"):APP.index("// Stato dei dati: da dove arriva tutto")]
    chiavi = re.findall(r'"(sd\.cons_[\w.]+)":\s*"((?:[^"\\]|\\.)*)"', TESTI_JS)
    assert chiavi and carta
    assert not [k for k, v in chiavi if re.search(r"\bC[1-4]\b", v)]


def test_la_fixture_dell_iphone_e_la_risposta_vera_del_server(tmp_path):
    """Se il server cambia il campo `consiglio`, la fixture dei test iOS va rifatta: dentro va {"stagione", "consiglio"} come qui."""
    salvata = json.loads(FIXTURE_IOS.read_text(encoding="utf-8"))
    assert salvata == {"stagione": ST, "consiglio": _otto(tmp_path)}


def test_la_pagina_mostra_la_carta():
    corpo = APP[APP.index("async function apriStatoDati"):APP.index("// Aspetto: tema")]
    assert "${cartaConsiglio(s.consiglio)}" in corpo
    assert corpo.index("${cartaRegistro(s.registro)}") < corpo.index("${cartaConsiglio(s.consiglio)}")
