"""Etichette coerenti nel web (#281, #284), dal collaudo per #167 con la lega inventata:
- il posto in formazione (scelta del confronto, Confronto, sostituzione) si legge «Titolare», «Panchina N», «Non schierato», mai con
  le parole della titolarità («Probabile titolare» per un giocatore al 2%, «Fuori»); la scelta mostra anche l'etichetta del server;
- nel Confronto i numeri negativi hanno il meno tipografico «−1,12», non il trattino;
- la pedina di una partita rinviata dice «Rinviata» al posto di «⚠ gioca 50%»; la carta del rinvio scrive «UDI vs MIL», e così
  anche la riga dei recuperi che mancano nel riepilogo della giornata finita (#310).
Funzioni di app.js provate con node."""
import json
import re
import shutil
import subprocess

import pytest

from fanta import server

APP = (server.WEB / "app.js").read_text(encoding="utf-8")
TESTI = (server.WEB / "testi.js").read_text(encoding="utf-8")
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(not NODE, reason="serve node")


def _pezzo(inizio: str, fine: str) -> str:
    a = APP.index(inizio)
    return APP[a:APP.index(fine, a)]


def _riga(nome: str) -> str:
    return re.search(rf"^const {nome} = .*$", APP, re.M).group(0)


def _esegui(chiamata: str, *pezzi: str, lingua: str = "it"):
    codice = "\n".join([TESTI, f"LINGUA = {json.dumps(lingua)};", _pezzo("function esc(x)", "const sigla ="), _riga("num"),
                        *pezzi, f"console.log(JSON.stringify({chiamata}));"])
    r = subprocess.run([NODE, "-"], input=codice, capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def _testo(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


# ---------------------------------------------------------------- #281: il posto in formazione
def _posto() -> str:
    return _pezzo("// Il posto in formazione a parole", "const inTitolari")


def test_posto_in_formazione_con_parole_proprie():
    it = _esegui('["titolare", "panchina 2", "fuori", ""].map(testoPosto)', _posto())
    assert it == ["Titolare", "Panchina 2", "Non schierato", ""]
    en = _esegui('["titolare", "panchina 2", "fuori"].map(testoPosto)', _posto(), lingua="en")
    assert en == ["Starter", "Bench 2", "Not picked"]
    titolarita = _esegui('[t("tit.titolare"), t("tit.fuori"), t("tit.panchina")]', _posto())
    assert not set(it) & set(titolarita)                       # mai le parole della titolarità


def test_scelta_del_confronto_giocatore_al_2_percento():
    """Lerri gioca al 2% ed è titolare nella formazione che stai guardando: la scelta diceva «Probabile titolare»."""
    stato = ("const stato = {formaz: {modulo: {titolari: [10], panchina: [12, 13]}, f: {schede: {'10': {}, '12': {}, '13': {}, '99': {}}}}};")
    assert _esegui("[10, 13, 99, 5].map(postoInFormazione)", stato, _posto()) == ["Titolare", "Panchina 2", "Non schierato", ""]
    riga = _pezzo("function apriScelta(id)", "async function apriConfronto")
    # accanto al posto, l'etichetta di stato del server (la stessa della Formazione: «Improbabile» per Lerri)
    assert '<span class="etichette">${pillTitolarita(x)}<span class="etichetta ${inTitolari(x.id) ? "" : "neutra"}">${postoInFormazione(x.id)}</span></span>' in riga


def test_confronto_e_sostituzione_usano_le_parole_del_posto():
    confronto = _pezzo("async function apriConfronto", "// ---------------------------------------------------------------- pannello")
    assert "const posto = g => testoPosto(codicePosto(g));" in confronto
    sostituzione = _pezzo("function apriSostituzione(id)", "Object.assign(sc,")
    assert '${postoInFormazione(x.id) || testoPosto("fuori")}' in sostituzione
    for blocco in (confronto, sostituzione, _posto()):
        assert 't("tit.titolare")' not in blocco and 't("tit.fuori")' not in blocco


def test_numeri_negativi_del_confronto_con_il_meno_vero():
    """«Merlo -1,12» e «-1,32 Stoli» nelle barre del Confronto (porta, cartellini): il meno tipografico, mai il trattino."""
    assert _esegui("[numMeno(-1.12, 2), numMeno(1.32, 2), numMeno(-0.001, 2), numMeno(null, 2), numMeno(-0.4)]", _riga("numMeno")) \
        == ["−1,12", "1,32", "0,00", "–", "−0,4"]
    assert _esegui("numMeno(-1.12, 2)", _riga("numMeno"), lingua="en") == "−1.12"
    confronto = _pezzo("async function apriConfronto", "// ---------------------------------------------------------------- pannello")
    assert "const valore = (f, v) => f.percentuale ? perc(v) : numMeno(v, 2);" in confronto


# ---------------------------------------------------------------- #284: partita rinviata
STUB_PEDINA = ("const avatar = () => ''; const attrPerche = () => ''; const distintivo = s => s;"
               "const cognome = x => x.nome; const nomeClub = s => s; const perc = x => `${Math.round((x || 0) * 100)}%`;")
PEDINA = "\n".join([re.search(r"^const TITOLARITA = \{.*?\};$", APP, re.M | re.S).group(0),
                    _pezzo("const STATO_PARTITA =", "// Il tocco sul fantavoto atteso"),
                    _pezzo("const ARTICOLI_CLUB", "// Legenda del campo")])


def test_pedina_di_una_partita_rinviata_dice_rinviata():
    rinviata = {"id": 7, "nome": "Jacopi", "p_voto": 0.5, "fv_atteso": 6.2, "avversario": "milan", "in_casa": True,
                "titolarita": None, "stato_partita": "rinviata", "etichetta": {"codice": "rinviata", "testo": "Rinviata", "tono": "attenzione"}}
    html = _esegui(f"pedina({json.dumps(rinviata)})", STUB_PEDINA, PEDINA)
    visibile = _testo(html)                     # anche la frase per i lettori di schermo dice «Rinviata», non «gioca al 50 per cento»
    assert "Rinviata" in visibile and "gioca" not in visibile and "⚠" not in visibile
    # prima della scadenza (campo `rinvio`) e con un server vecchio senza etichetta: lo stesso
    prima = rinviata | {"stato_partita": None, "titolarita": "titolare", "rinvio": "aspetta"}
    vecchio = {k: v for k, v in rinviata.items() if k != "etichetta"}
    esiti = _esegui(f"[{json.dumps(prima)}, {json.dumps(vecchio)}].map(esitoPedina).map(e => e && e.testo)", STUB_PEDINA, PEDINA)
    assert esiti == ["Rinviata", "Rinviata"]
    # una partita che si gioca resta «gioca N%»
    gioca = {"id": 8, "nome": "Rossi", "p_voto": 0.5, "fv_atteso": 6.0, "avversario": "roma", "in_casa": False, "titolarita": "ballottaggio"}
    assert "⚠ gioca 50%" in _testo(_esegui(f"pedina({json.dumps(gioca)})", STUB_PEDINA, PEDINA))


def test_carta_del_rinvio_scrive_le_squadre_come_le_partite_del_turno():
    rv = {"giornata": 10, "stagione": "2026-27", "modo": "aspetta", "modi": ["aspetta", "senza_voto", "voto_ufficio"], "voto_ufficio": 6,
          "partite": [{"casa": "udinese", "trasferta": "milan", "data": None}], "miei": [{"nome": "Jacopi"}]}
    blocco = "\n".join([_pezzo("const SIGLE =", "const NOMI_DIFF"), _riga("sigla"), _pezzo("function parseData(s)", "// ETag e If-Match"),
                        _pezzo("const MODI_RINVIO", "function collegaRinvio")])
    html = _esegui(f"cardRinvio({json.dumps(rv)})", blocco)
    assert "UDI vs MIL" in _testo(html) and "UDI–MIL" not in html


def test_recuperi_che_mancano_scritti_come_la_carta_del_rinvio():
    """Riepilogo della giornata finita: «Manca il recupero di UDI vs MIL, ATA vs PAR: …», non «UDI–MIL» (#310)."""
    r = {"giornata": 10, "giornata_lega": 7, "formazione_di": "tua", "nel_diario": True, "punti_fatti": 61,
         "recuperi": [{"casa": "udinese", "trasferta": "milan", "data": None}, {"casa": "atalanta", "trasferta": "parma", "data": "2026-11-25 20:45"}]}
    blocco = "\n".join([_pezzo("const SIGLE =", "const NOMI_DIFF"), _riga("sigla"), _pezzo("function parseData(s)", "// ETag e If-Match"),
                        _pezzo("const MODI_RINVIO", "function collegaRinvio"), _pezzo("function nomeGiornata(", "// «la 8ª»"),
                        _pezzo("function cardRiepilogo(", "// Partite rinviate della giornata")])
    html = _esegui(f"cardRiepilogo({json.dumps(r)}, null)", blocco)
    assert "Manca il recupero di UDI vs MIL, ATA vs PAR: i punti possono ancora cambiare." in _testo(html)
    assert "–" not in _testo(html)
    en = _esegui(f"cardRiepilogo({json.dumps(r)}, null)", blocco, lingua="en")
    assert "The make-up game UDI vs MIL, ATA vs PAR is still to be played" in _testo(en)
