"""La web in inglese (#949): plurali giusti con un numero solo («1 assist», «1 second»), date con il mese a parole, i nomi del
server di Stato dei dati tradotti, e le stesse parole in tutto il catalogo (voto = grade, giornata = matchday, virgolette “”).
I testi e le funzioni sono quelli veri di `fanta/web/testi.js`, eseguiti con node."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import codice_web
import pytest

TESTI_JS = codice_web.leggi("testi.js")
NODE = shutil.which("node")
CATALOGO = Path(__file__).resolve().parent.parent / "fanta" / "testi"


def _node(lingua: str, espressioni: list[str]) -> list:
    if NODE is None:
        pytest.skip("serve node")
    prova = TESTI_JS + f'\nLINGUA = "{lingua}";\nconsole.log(JSON.stringify([{", ".join(espressioni)}]));'
    r = subprocess.run([NODE, "-"], input=prova, capture_output=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_plurali_con_uno_in_inglese_e_in_italiano():
    casi = ['tp("mercato.prec_assist", 1, { xa: "0.3" })', 'tp("mercato.prec_assist", 2, { xa: "0.3" })',
            'tp("mercato.prec_gol", 1, { xg: "0.8" })', 'tp("mercato.n_gol_rig", 1, { r: 0 })', 'tp("mercato.n_gol_rig", 3, { r: 1 })',
            'tp("comune.attesa_secondi", 1)']
    assert _node("en", casi) == ["1 assist (0.3 expected)", "2 assists (0.3 expected)", "1 goal (0.8 expected)", "goal (0 pen.)",
                                 "goals (1 pen.)", "1 second"]
    assert _node("it", casi) == ["1 assist (0.3 attesi)", "2 assist (0.3 attesi)", "1 gol (0.8 attesi)", "gol (0 rig.)", "gol (1 rig.)",
                                 "1 secondo"]


def test_le_date_con_l_anno_hanno_il_mese_a_parole_in_inglese():
    giorno = 'fDataAnno(new Date("2026-11-26T12:00:00Z"))'
    assert _node("en", [giorno]) == ["26 Nov 2026"]
    assert _node("it", [giorno]) == ["26/11/2026"]                                       # in italiano come prima


def test_i_nomi_di_stato_dei_dati_si_traducono():
    casi = ['traduciFrase({ chiave: "fascia.titolare", param: { da: 90, a: 100 } }, "Titolare 90-100%")',
            'traduciFrase({ chiave: "fascia.panchina_sotto", param: { a: 20 } }, "Panchina sotto 20%")',
            'traduciFrase({ chiave: "aggiornamento.aggiornamento", param: {} }, "Aggiornamento generale")',
            'traduciFrase({ chiave: "aggiornamento.calendario_stagione", param: { stagione: "2026-27" } }, "Calendario completo 2026-27")',
            'traduciFrase({ chiave: "fonte.nome_foto", param: {} }, "Foto dei giocatori")',
            'traduciFrase({ chiave: "uso.funzione_diario", param: {} }, "Diario delle giornate")',
            'traduciFrase({ chiave: "controllo.titolari_per_squadra", param: {} }, "11 titolari per squadra")',
            'traduciFrase(null, "vecchia_funzione")']
    assert _node("en", casi) == ["Starter 90-100%", "Bench below 20%", "Full data refresh", "Full calendar 2026-27", "Player photos",
                                 "Matchdays", "11 starters per team", "vecchia_funzione"]
    assert _node("it", casi[:2]) == ["Titolare 90-100%", "Panchina sotto 20%"]


# parole che in inglese non si usano più (#949): il voto è «grade», la giornata «matchday», le probabili «probable lineups». Dal
# collaudo del 27/11/2026: «senza voto» = «no grade», la formazione «closes» (non «locks»), la rosa è «roster» («expected squad»
# resta: sono i convocati), il calendario «calendar», le previsioni «forecasts»
PAROLE_VIETATE = [(r"[«»]", "virgolette «» (in inglese “”)"), (r"\bratings?\b|\bvotes?\b", "voto = grade"),
                  (r"\brounds?\b", "giornata = matchday"), (r"predicted line-?ups?", "probable lineups"), (r"\bDiaries\b", "Diaries"),
                  (r"recogniz", "recognise"), (r"\bmaluse?s?\b", "malus = deduction"), (r"\bline-ups?\b", "lineup"),
                  (r"\bno score\b", "senza voto = no grade"), (r"\block(s|ed)?\b", "si chiude = closes"),
                  (r"(?<!expected )\bsquads?\b", "rosa = roster"), (r"\bfixtures?\b|fixture list", "calendario = calendar"),
                  (r"\bpredictions?\b", "previsione = forecast")]


def test_nel_catalogo_inglese_le_stesse_parole_dappertutto():
    storte = []
    for percorso in sorted(CATALOGO.glob("*.json")):
        for chiave, voce in json.loads(percorso.read_text(encoding="utf-8")).items():
            storte += [f"{chiave}: {motivo}" for schema, motivo in PAROLE_VIETATE if re.search(schema, voce["en"], re.I)]
    assert not storte, storte
