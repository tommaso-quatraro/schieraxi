"""Giornata chiusa con una scelta salvata che non vale più (#319): un giocatore ceduto o un modulo non ammesso.

Una regola sola nel server (`scelte.motivo_non_valida`, la stessa del controllo della Formazione): una scelta che non si può
schierare non conta, e vale la consigliata congelata alla scadenza, come quando non hai salvato niente. Oggi in diretta, il
riepilogo, il Diario e la Formazione (campo `stato_scelta`) lo dicono e lo mostrano allo stesso modo, su web e iPhone.
Dati finti, file in cartelle temporanee, nessuna rete."""
# ruff: noqa: F811  (le fixture importate da altri file di test arrivano come parametri con lo stesso nome: è il modo di pytest)
import json
import re
import shutil
import subprocess
from datetime import datetime

import pytest

from fanta import consigli, copia_scadenza, diario, fasi, scelte, server
from fanta.regole import Regole
from test_fasi import REGOLE, ROSA, ST, TITOLARI, _giornata_finita, _oggi, ambiente  # noqa: F401  (ambiente = fixture)
from test_diario import _formazione_finta, finto, vero  # noqa: F401  (fixture del Diario con dati finti)
from test_server import client  # noqa: F401  (fixture del server)

CEDUTO = 99                                                   # era in rosa quando l'utente ha salvato, poi è stato ceduto
CON_CEDUTO = TITOLARI[:10] + [CEDUTO]
DUE_PORTIERI = [1, 14, 2, 3, 4, 6, 7, 8, 9, 10, 11]           # Portiere e Port14 insieme: 3-4-2 con 2 portieri
CONSIGLIATA_ALLA_SCADENZA = [1, 2, 3, 4, 5, 6, 7, 8, 12, 10, 11]   # 5-3-2: Dif12 al posto di Cen9 (infortunato)
RUOLI = {i: r for i, (_, r, _, _, _) in ROSA.items()}
NON_VALIDE = pytest.mark.parametrize("salvata", [CON_CEDUTO, DUE_PORTIERI], ids=["giocatore-ceduto", "modulo-non-ammesso"])
APP = (server.WEB / "app.js").read_text(encoding="utf-8")
TESTI = (server.WEB / "testi.js").read_text(encoding="utf-8")
NODE = shutil.which("node")


# ---------------------------------------------------------------- la regola
@pytest.mark.parametrize("titolari, regole, motivo", [
    (TITOLARI, REGOLE, None),
    (CON_CEDUTO, REGOLE, "Servono 11 titolari diversi, tutti della rosa"),
    (TITOLARI[:10] + [1], REGOLE, "Servono 11 titolari diversi, tutti della rosa"),            # un titolare ripetuto
    (TITOLARI[:10], REGOLE, "Servono 11 titolari diversi, tutti della rosa"),                  # dieci soli
    (DUE_PORTIERI, REGOLE, "Il modulo 3-4-2 con 2 portieri non è ammesso nella tua lega"),
    (TITOLARI, Regole(moduli=["4-3-3"]), "Il modulo 4-4-2 con 1 portieri non è ammesso nella tua lega"),   # la lega l'ha tolto
])
def test_regola_unica_della_scelta(titolari, regole, motivo):
    assert scelte.motivo_non_valida(titolari, RUOLI, regole) == motivo


def test_stato_della_scelta():
    assert scelte.stato(None, RUOLI, REGOLE) == "nessuna"
    assert scelte.stato({"titolari": TITOLARI}, RUOLI, REGOLE) == "valida"
    assert scelte.stato({"titolari": CON_CEDUTO}, RUOLI, REGOLE) == "non_valida"
    assert scelte.stato({"titolari": DUE_PORTIERI}, RUOLI, REGOLE) == "non_valida"


@pytest.mark.parametrize("titolari, motivo", [
    (CON_CEDUTO, "Servono 11 titolari diversi, tutti della rosa"),
    (DUE_PORTIERI, "Il modulo 3-4-2 con 2 portieri non è ammesso nella tua lega"),
])
def test_la_formazione_controlla_con_le_stesse_frasi(ambiente, titolari, motivo):
    """`consigli.valuta` (la Formazione, 400 `formazione_non_valida`): stessi casi e stesse frasi della regola unica."""
    with pytest.raises(consigli.FormazioneNonValida, match=f"^{motivo}$"):
        consigli.valuta(ambiente.db, REGOLE, ambiente.rose, titolari, None, 10)


# ---------------------------------------------------------------- alla scadenza
def _copia_alla_scadenza(a):
    """La copia del server negli ultimi minuti prima della scadenza (copia_scadenza.salva) con la consigliata di allora."""
    scheda = lambda i: {"id": i, "nome": ROSA[i][0], "ruolo": ROSA[i][1]}    # noqa: E731
    f = {"giornata": 10, "modulo": "5-3-2", "punteggio_atteso": 68.0, "titolari": [scheda(i) for i in CONSIGLIATA_ALLA_SCADENZA],
         "panchina": [scheda(i) for i in (13, 9, 14)]}
    copia_scadenza.salva(f, ST, a.tmp / "scelte.json", a.tmp / "diario.json")


@NON_VALIDE
def test_alla_scadenza_la_scelta_resta_e_la_consigliata_si_congela(ambiente, salvata):
    scelte.salva(ST, 10, salvata, "4-4-2", ambiente.tmp / "scelte.json")
    _copia_alla_scadenza(ambiente)
    assert scelte.leggi(ST, 10, ambiente.tmp / "scelte.json")["titolari"] == salvata          # mai sopra una scelta vera
    ist = diario.carica(ambiente.tmp / "diario.json")["istantanee"][f"{ST}/10"]
    assert [g["id"] for g in ist["titolari"]] == CONSIGLIATA_ALLA_SCADENZA and ist["atteso"] == 68.0


@NON_VALIDE
def test_in_diretta_vale_la_consigliata_congelata(ambiente, salvata):
    """Prima: con il giocatore ceduto Oggi non aveva la giornata in diretta (`in_corso: null`), con il modulo non ammesso contava la
    scelta salvata («tua») mentre la Formazione mostrava la consigliata."""
    scelte.salva(ST, 10, salvata, "4-4-2", ambiente.tmp / "scelte.json")
    _copia_alla_scadenza(ambiente)
    o = _oggi(ambiente, datetime(2026, 11, 8, 21, 30))
    assert o["fase"] == "in_corso" and o["formazione"]["tua_scelta"] is False
    c = o["in_corso"]
    assert c is not None and c["formazione_di"] == "consigliata"
    assert [g["id"] for g in c["giocatori"] if g["titolare"]] == CONSIGLIATA_ALLA_SCADENZA


@NON_VALIDE
def test_a_giornata_finita_il_riepilogo_e_della_consigliata(ambiente, monkeypatch, salvata):
    """Riepilogo senza il Diario (voti appena usciti): prima con il giocatore ceduto mancava, con il modulo non ammesso era «tua»."""
    scelte.salva(ST, 10, salvata, "4-4-2", ambiente.tmp / "scelte.json")
    _copia_alla_scadenza(ambiente)
    _giornata_finita(ambiente)
    prev, _, _ = consigli.previsioni(None, REGOLE)
    monkeypatch.setattr(consigli, "previsioni", lambda db, regole, giornata=None: (prev, 11, False))
    r = _oggi(ambiente, datetime(2026, 11, 10, 10, 0))["riepilogo"]
    assert r is not None and r["formazione_di"] == "consigliata" and r["nel_diario"] is False
    assert r["punti_attesi"] == 68.0 and r["punti_fatti"] is not None


# ---------------------------------------------------------------- Diario
DIARIO_DUE_PORTIERI = [1, 2, 4, 5, 6, 12, 13, 14, 15, 20, 21]      # nel Diario finto gli id 1-3 sono portieri
DIARIO_CEDUTO = [1, 4, 5, 6, 12, 13, 14, 15, 20, 21, 99]


def test_diario_scelta_con_modulo_non_ammesso_non_conta(finto):
    v = diario.calcola_giornata(finto.dati, ST, 1, Regole(), None, list(range(1, 26)), {"titolari": DIARIO_DUE_PORTIERI},
                                simulazioni=50)
    assert v["schierata"] is None and v["consigliata"]


@pytest.mark.parametrize("salvata", [DIARIO_CEDUTO, DIARIO_DUE_PORTIERI], ids=["giocatore-ceduto", "modulo-non-ammesso"])
def test_diario_una_scelta_non_valida_non_fa_rifare_la_giornata_a_ogni_giro(finto, monkeypatch, salvata):
    """Prima la giornata con una scelta non valida si ricalcolava (con le simulazioni) a ogni giro del Diario."""
    monkeypatch.setattr(diario.scelte, "leggi", lambda st, g, *a, **k: {"titolari": salvata, "tipo": "manuale"} if g == 2 else None)
    assert diario.aggiorna(finto.db, Regole(), finto.rose, finto.file, simulazioni=50) == 2
    assert diario.carica(finto.file)["giornate"][f"{ST}/2"]["schierata"] is None
    assert diario.aggiorna(finto.db, Regole(), finto.rose, finto.file, simulazioni=50) == 0


@pytest.mark.parametrize("salvata", [DIARIO_CEDUTO, DIARIO_DUE_PORTIERI], ids=["giocatore-ceduto", "modulo-non-ammesso"])
def test_diario_gia_calcolato_con_la_consigliata_congelata_come_oggi(vero, salvata):
    """Revisione della #320: con una scelta non valida il Diario usava la consigliata ricostruita con la rosa di adesso (punti
    diversi da quelli visti in Oggi durante la giornata, e «non salvata»). Ora usa la consigliata congelata alla scadenza, come
    per chi non ha salvato niente: stessi punti nel Diario e nel riepilogo di Oggi."""
    congelata = [1, 4, 5, 6, 12, 13, 14, 15, 20, 21, 22]               # 3-4-3 senza l'attaccante da 9: undici da 6
    diario.salva_istantanea(_formazione_finta(1, congelata), ST, vero.file)
    scelte.salva(ST, 1, salvata, "3-4-3", vero.scelte)
    assert diario.aggiorna(vero.db, Regole(), vero.rose, vero.file, simulazioni=50, file_scelte=vero.scelte) == 2
    v = diario.carica(vero.file)["giornate"][f"{ST}/1"]
    assert v["schierata"] is None and v["automatica"] is not None                  # prima: vuota, e il Diario diceva «non salvata»
    assert [t["id"] for t in v["automatica"]["titolari"]] == congelata
    assert v["automatica"]["reale"] == 11 * 6 and v["consigliata"]["reale"] != 11 * 6       # la ricostruzione è un'altra
    r = fasi.blocco_riepilogo(vero.db, Regole(), vero.rose, ST, 1, vero.scelte, vero.file)  # il riepilogo di Oggi
    assert r["nel_diario"] is True and r["formazione_di"] == "consigliata" and r["punti_fatti"] == 11 * 6
    assert diario.aggiorna(vero.db, Regole(), vero.rose, vero.file, simulazioni=50, file_scelte=vero.scelte) == 0   # resta ferma


def test_diario_ho_schierato_con_un_modulo_non_ammesso(finto, monkeypatch, tmp_path):
    with pytest.raises(diario.SchierataNonValida, match="Il modulo 3-4-2 con 2 portieri non è ammesso nella tua lega"):
        diario.prepara_schierata(finto.db, Regole(), finto.rose, 1, "manuale", DIARIO_DUE_PORTIERI, finto.file, simulazioni=50)


# ---------------------------------------------------------------- Formazione: campo `stato_scelta`
def test_formazione_dice_lo_stato_della_scelta(client, monkeypatch, tmp_path):
    x = lambda i: {"id": i, "nome": ROSA[i][0], "ruolo": ROSA[i][1], "squadra": ROSA[i][2]}    # noqa: E731
    f = {"squadra": "Mia", "giornata": 10, "titolari": [x(i) for i in TITOLARI], "panchina": [], "fuori": [],
         "schede": {str(i): x(i) for i in ROSA}}
    monkeypatch.setattr(server.consigli, "formazione", lambda *a, **k: f)
    monkeypatch.setattr(server.consigli, "stagione_corrente", lambda: ST)
    monkeypatch.setattr(server, "_copia_automatica", lambda *a: None)
    monkeypatch.setattr(server, "_rose", lambda *a: object())
    monkeypatch.setattr(server.fasi, "iniziata", lambda *a: True)
    monkeypatch.setattr(server.fasi, "stati_giocatori", lambda *a, **k: {})
    monkeypatch.setattr(scelte, "FILE_SCELTE", tmp_path / "scelte.json")

    def stato(**p):
        r = client.get("/api/formazione", params=p)
        assert r.status_code == 200, r.text
        assert r.json()["iniziata"] is True                           # giornata chiusa
        return r.json().get("stato_scelta", "manca")
    assert stato() == "nessuna"
    scelte.salva_automatica(ST, 10, TITOLARI, "4-4-2", tmp_path / "scelte.json")
    assert stato() == "nessuna"                                       # la copia automatica non è una scelta dell'utente
    scelte.salva(ST, 10, TITOLARI, "4-4-2", tmp_path / "scelte.json")
    assert stato() == "valida"
    scelte.salva(ST, 10, CON_CEDUTO, "4-4-2", tmp_path / "scelte.json")
    assert stato() == "non_valida"
    scelte.salva(ST, 10, DUE_PORTIERI, "4-4-2", tmp_path / "scelte.json")
    assert stato() == "non_valida"
    assert stato(squadra="Altra") == "manca"                          # la formazione di un'altra squadra non ha la tua scelta
    assert "stato_scelta" not in f                                    # la formazione in cache non cambia


# ---------------------------------------------------------------- web: la riga dello stato a giornata chiusa
@pytest.mark.skipif(NODE is None, reason="node non installato")
def test_web_giornata_chiusa_dice_quale_formazione_vale():
    funz = APP[APP.index("const SEGNI_SCELTA"):APP.index("function mostraFormazione(")]
    base = "const t = k => k; const quandoSalvata = () => '';"
    casi = ("[rigaStatoScelta('chiusa', null), rigaStatoScelta('chiusa', {titolari: [1]}),"
            " rigaStatoScelta('chiusa', {titolari: [1]}, true), rigaStatoScelta('chiusa', null, true)]")
    r = subprocess.run([NODE, "-e", base + funz + f"console.log(JSON.stringify({casi}))"], capture_output=True, text=True,
                       encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    frasi = [re.search(r'</span><span>([^<]*)</span>', h).group(1) for h in json.loads(r.stdout)]
    assert frasi == ["formazione.stato_chiusa", "formazione.stato_chiusa_tua", "formazione.stato_chiusa_non_valida",
                     "formazione.stato_chiusa_non_valida"]
    # la Formazione passa la regola del server (`stato_scelta`) e il «non valida» che il server ha già detto rileggendo la scelta
    assert 'rigaStatoScelta(st, sc.salvata, f.stato_scelta === "non_valida" || sc.nonValida)' in APP
    assert TESTI.count('"formazione.stato_chiusa_non_valida"') == 2
    assert ('"formazione.stato_chiusa_non_valida": "Giornata iniziata: la formazione è chiusa · vale la consigliata, la tua non è '
            'più valida"') in TESTI
