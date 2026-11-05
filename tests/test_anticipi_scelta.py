"""Formazione salvata e anticipi già cominciati (#373, sotto #166). Un anticipo (turno.py: da 36 ore a 7 giorni prima del gruppo
principale) non fissa la scadenza: la formazione resta aperta, ma nella lega i giocatori di una partita già cominciata non si
spostano più. Rispetto alla formazione che vale in quel momento (la scelta salvata se c'è e vale, altrimenti la consigliata) un
salvataggio che ne sposta uno si rifiuta (400, `codice: "giocatore_bloccato"`), e così il ritorno alla consigliata; `GET
/api/formazione` dice chi è fermo nel campo facoltativo `bloccati`. Senza anticipi cominciati nulla cambia.
«Cominciato» è la regola della consigliata (`consigli._anticipi_iniziati`, #368): calendario e orario.
Rosa, squadre e calendario inventati; file in cartelle temporanee."""
# ruff: noqa: F811  (la fixture `client` importata da test_server arriva come parametro con lo stesso nome: è il modo di pytest)
import json
import shutil
import subprocess
from datetime import datetime, timedelta

import pandas as pd
import pytest

from fanta import archivio, calcolo, consigli, da_fare, diario, lega, scelte, server
from test_da_fare import la_consigliata_cambia
from test_da_fare import mondo as mondo_da_fare  # noqa: F401  (fixture di «Da fare» con dati finti)
from test_da_fare import vai as vai_da_fare
from test_da_fare_consigliata_salvata import _cambia, _salva_la_consigliata
from test_server import client  # noqa: F401  (fixture del server)

ST = "2026-27"
GIORNATA = 10
ANTICIPO = "ant"                  # la squadra di Serie A che gioca l'anticipo
# id: (nome, ruolo, squadra di Serie A)
ROSA = {1: ("Portiere1", "P", "aaa"), 15: ("Portiere15", "P", "bbb"),
        2: ("Dif2", "D", "aaa"), 3: ("Dif3", "D", "aaa"), 4: ("Dif4", "D", "bbb"), 5: ("Dif5", "D", ANTICIPO),
        12: ("Dif12", "D", "bbb"), 16: ("Dif16", "D", ANTICIPO),
        6: ("Cen6", "C", "aaa"), 7: ("Cen7", "C", "bbb"), 8: ("Cen8", "C", "aaa"), 9: ("Cen9", "C", "bbb"), 13: ("Cen13", "C", "aaa"),
        10: ("Att10", "A", "aaa"), 11: ("Att11", "A", "bbb"), 14: ("Att14", "A", "bbb")}
CONSIGLIATA = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]          # 4-4-2: il 5 (anticipo) è titolare
PANCHINA = [12, 13, 16, 15]                                # il 16 (anticipo) è in panchina
BLOCCATI = [5, 16]
FUORI_IL_5 = [1, 2, 3, 4, 12, 6, 7, 8, 9, 10, 11]          # il 5 esce, entra il 12
DENTRO_IL_16 = [1, 2, 3, 16, 5, 6, 7, 8, 9, 10, 11]        # il 16 entra al posto del 4
SENZA_ANTICIPO = [1, 2, 3, 12, 5, 6, 7, 8, 9, 10, 11]      # il 4 esce, entra il 12: nessuno dell'anticipo si sposta
MESSAGGIO = "{} gioca in una partita già cominciata: non si può più spostare."


def _scheda(i: int) -> dict:
    nome, ruolo, squadra = ROSA[i]
    return {"id": i, "nome": nome, "ruolo": ruolo, "squadra": squadra, "punti_attesi": 6.0, "p_voto": 0.9}


CONSIGLIATA_F = {"squadra": "Mia", "giornata": GIORNATA, "modulo": "4-4-2", "punteggio_atteso": 70.0,
                 "titolari": [_scheda(i) for i in CONSIGLIATA], "panchina": [_scheda(i) for i in PANCHINA],
                 "fuori": [_scheda(14)], "moduli": [{"modulo": "4-4-2", "punteggio_atteso": 70.0}],
                 "schede": {str(i): _scheda(i) for i in ROSA}}


@pytest.fixture
def mondo(client, monkeypatch, tmp_path):
    """La giornata 10: l'anticipo (ant - ccc) comincia o è già cominciato, il gruppo principale fra tre giorni (la formazione resta
    aperta). `mondo["anticipo"]` = quando comincia l'anticipo; il calendario si riscrive a ogni richiesta."""
    percorso = tmp_path / "fanta.sqlite"
    stato = {"anticipo": datetime.now() - timedelta(hours=1), "principale": datetime.now() + timedelta(days=3)}

    def db():
        d = archivio.apri(percorso)
        d.execute("DELETE FROM partite")
        date = [stato["anticipo"]] + [stato["principale"] + timedelta(hours=3 * k) for k in range(9)]
        squadre = [(ANTICIPO, "ccc")] + [(f"c{k}", f"t{k}") for k in range(9)]
        archivio.inserisci(d, "partite", [{"id": n, "stagione": ST, "giornata": GIORNATA, "data": q.strftime("%Y-%m-%d %H:%M"),
                                           "casa": c, "trasferta": t, "gol_casa": None, "gol_trasferta": None, "giocata": 0,
                                           "understat_id": None} for n, (q, (c, t)) in enumerate(zip(date, squadre))])
        d.commit()
        return d
    prev = pd.DataFrame([{"id": i, "nome": n, "ruolo": r, "squadra": s, "p_voto": 0.9, "mu": 6.0, "mu_voto": 6.0}
                         for i, (n, r, s) in ROSA.items()]).set_index("id")
    rose = lega.Rose([lega.Squadra("Mia", [lega.GiocatoreRosa(i, n, r, s, 1) for i, (n, r, s) in ROSA.items()])], "Mia")
    monkeypatch.setattr(server, "_db", db)
    monkeypatch.setattr(server, "_rose", lambda ctx: rose)
    monkeypatch.setattr(server, "_copia_automatica", lambda *a: None)
    monkeypatch.setattr(consigli, "stagione_corrente", lambda: ST)
    monkeypatch.setattr(consigli, "previsioni", lambda db, regole, giornata=None: (prev, GIORNATA, True))
    monkeypatch.setattr(consigli, "formazione", lambda *a, **k: CONSIGLIATA_F)
    monkeypatch.setattr(scelte, "FILE_SCELTE", tmp_path / "scelte.json")
    monkeypatch.setattr(diario, "FILE", tmp_path / "diario.json")          # il salvataggio legge l'istantanea del Diario (#333)
    calcolo.cache.clear()
    stato["client"], stato["file"] = client, tmp_path / "scelte.json"
    return stato


def _salva(mondo, titolari, salva=True):
    return mondo["client"].post("/api/formazione/valuta", json={"titolari": titolari, "giornata": GIORNATA, "salva": salva})


def _salvata(mondo):
    s = mondo["client"].get("/api/scelta", params={"giornata": GIORNATA}).json()
    return s and s["titolari"]


def _rifiutato(r, nome: str):
    assert r.status_code == 400, r.text
    assert r.json() == {"detail": MESSAGGIO.format(nome), "codice": "giocatore_bloccato"}


# ---------------------------------------------------------------- salvataggio
def test_un_titolare_dell_anticipo_non_esce(mondo):
    _rifiutato(_salva(mondo, FUORI_IL_5), "Dif5")
    assert _salvata(mondo) is None                                      # niente scritto


def test_uno_dell_anticipo_non_entra(mondo):
    _rifiutato(_salva(mondo, DENTRO_IL_16), "Dif16")
    assert _salvata(mondo) is None


def test_gli_altri_si_spostano_come_sempre(mondo):
    assert _salva(mondo, SENZA_ANTICIPO).status_code == 200
    assert _salvata(mondo) == SENZA_ANTICIPO
    assert _salva(mondo, CONSIGLIATA).status_code == 200                # «Salva questa» con la consigliata: nessuno si sposta


def test_valutare_senza_salvare_resta_possibile(mondo):
    assert _salva(mondo, FUORI_IL_5, salva=False).status_code == 200


def test_si_confronta_con_la_scelta_salvata_che_vale(mondo):
    """Salvata prima dell'inizio dell'anticipo con il 16 titolare: ora vale lei, quindi il 16 non può più uscire (nemmeno per
    tornare alla consigliata) e il 5, che la scelta lascia titolare, nemmeno."""
    scelte.salva(ST, GIORNATA, DENTRO_IL_16, "4-4-2", mondo["file"])
    _rifiutato(_salva(mondo, CONSIGLIATA), "Dif16")
    con_il_13 = [13 if i == 9 else i for i in DENTRO_IL_16]           # cambia solo un centrocampista
    assert _salva(mondo, con_il_13).status_code == 200
    assert _salvata(mondo) == con_il_13


def test_una_scelta_che_non_vale_piu_conta_come_nessuna(mondo):
    """La scelta salvata ha un giocatore ceduto (99): non vale, quindi il riferimento è la consigliata."""
    scelte.salva(ST, GIORNATA, CONSIGLIATA[:10] + [99], "4-4-2", mondo["file"])
    assert _salva(mondo, CONSIGLIATA).status_code == 200
    _rifiutato(_salva(mondo, FUORI_IL_5), "Dif5")


def test_la_copia_automatica_non_e_una_scelta(mondo):
    """La copia della consigliata fatta dal server (tipo «automatica») non è una scelta dell'utente: vale la consigliata."""
    scelte.salva_automatica(ST, GIORNATA, DENTRO_IL_16, "4-4-2", mondo["file"])
    _rifiutato(_salva(mondo, DENTRO_IL_16), "Dif16")


def test_prima_che_l_anticipo_cominci_nulla_cambia(mondo):
    mondo["anticipo"] = datetime.now() + timedelta(hours=2)
    assert _salva(mondo, FUORI_IL_5).status_code == 200
    assert _salva(mondo, DENTRO_IL_16).status_code == 200


def test_senza_anticipi_nulla_cambia(mondo):
    """L'unica partita «prima» sta nel gruppo principale (nessun anticipo): si salva come sempre."""
    mondo["anticipo"] = mondo["principale"] - timedelta(hours=2)
    assert _salva(mondo, FUORI_IL_5).status_code == 200


# ---------------------------------------------------------------- ritorno alla consigliata
def test_tornare_alla_consigliata_non_sposta_chi_ha_gia_cominciato(mondo):
    scelte.salva(ST, GIORNATA, DENTRO_IL_16, "4-4-2", mondo["file"])
    r = mondo["client"].delete("/api/scelta", params={"giornata": GIORNATA})
    _rifiutato(r, "Dif16")
    assert _salvata(mondo) == DENTRO_IL_16                               # la scelta resta


def test_tornare_alla_consigliata_si_puo_se_non_sposta_nessuno_dell_anticipo(mondo):
    scelte.salva(ST, GIORNATA, SENZA_ANTICIPO, "4-4-2", mondo["file"])
    assert mondo["client"].delete("/api/scelta", params={"giornata": GIORNATA}).status_code == 200
    assert _salvata(mondo) is None


# ---------------------------------------------------------------- GET /api/formazione: campo `bloccati`
def _formazione(mondo):
    r = mondo["client"].get("/api/formazione")
    assert r.status_code == 200, r.text
    return r.json()


def test_la_formazione_dice_chi_e_bloccato(mondo):
    f = _formazione(mondo)
    assert f["iniziata"] is False and f["bloccati"] == BLOCCATI
    assert "bloccati" not in CONSIGLIATA_F                              # la formazione in cache non cambia


def test_senza_anticipi_cominciati_niente_campo(mondo):
    mondo["anticipo"] = datetime.now() + timedelta(hours=2)
    assert "bloccati" not in _formazione(mondo)


def test_a_formazione_chiusa_niente_campo(mondo):
    """Dopo la scadenza è chiusa tutta (`iniziata: true`): il campo non serve."""
    mondo["anticipo"], mondo["principale"] = datetime.now() - timedelta(days=3), datetime.now() - timedelta(hours=1)
    f = _formazione(mondo)
    assert f["iniziata"] is True and "bloccati" not in f


# ---------------------------------------------------------------- web: i bloccati non si sostituiscono
APP = (server.WEB / "app.js").read_text(encoding="utf-8")
NODE = shutil.which("node")


def _sostituti(f: dict, uscente: int, titolari: list[int]) -> list[int]:
    """`sostituti` di app.js (chi può prendere il posto di un titolare nella modifica a mano), eseguita con node."""
    funz = APP[APP.index("const giocatoriFermi"):APP.index("function mostraFormazione(")]
    prova = (f"{funz}\nconst f = {json.dumps(f)};\n"
             f"console.log(JSON.stringify(sostituti(f, f.schede['{uscente}'], new Set({titolari})).map(x => x.id)));")
    r = subprocess.run([NODE, "-e", prova], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


@pytest.mark.skipif(NODE is None, reason="node non installato")
def test_web_chi_e_bloccato_non_esce_e_non_entra():
    f = CONSIGLIATA_F | {"bloccati": BLOCCATI}
    assert _sostituti(f, 5, CONSIGLIATA) == []                          # il 5 (anticipo cominciato) non si sostituisce
    assert 16 not in _sostituti(f, 4, CONSIGLIATA) and 12 in _sostituti(f, 4, CONSIGLIATA)    # il 16 non entra, il 12 sì
    assert set(_sostituti(CONSIGLIATA_F, 4, CONSIGLIATA)) == {12, 16}   # senza il campo (server vecchio, niente anticipi): come prima


def test_web_formazione_usa_i_bloccati():
    """Nella modifica a mano un titolare bloccato ha il ⇄ del confronto al posto del ✎, e una riga dice perché."""
    assert "voceGiocatore(x, null, true, modificabile && !fermi.has(x.id))" in APP
    assert 'modificabile && fermi.size ? `<div class="debole piccolo">${t("formazione.bloccati")}</div>` : ""' in APP
    assert "sostituti(f, base, dentro)" in APP


def _torna_alla_consigliata(codice: str | None) -> dict:
    """Il gestore vero di «Torna alla consigliata» (app.js), eseguito con node: la DELETE risponde con l'errore `codice` (None =
    riesce). Le funzioni intorno sono finte e annotano cosa succede."""
    inizio = APP.index('bottone("#torna-consigliata", ') + len('bottone("#torna-consigliata", ')
    gestore = APP[inizio:APP.index("collegaLegenda();", inizio)].rstrip().removesuffix(");")
    prova = f"""
    const registro = [];
    const sc = {{ salvata: {{ titolari: [1, 2, 3] }}, manuale: null, livello: 1, modulo: "3-4-3", nonValida: false }};
    const f = {{ giornata: {GIORNATA} }}, squadra = null;
    const annullaRichieste = () => registro.push("annulla");
    const disegna = () => registro.push(sc.manuale ? "disegna la tua" : "disegna la consigliata");
    const avviso = m => registro.push("avviso: " + m);
    const valutaManuale = (ids, salva, silenzioso) => {{ sc.manuale = {{ titolari: ids }}; registro.push("valuta " + JSON.stringify([ids, salva, silenzioso])); }};
    const vistaFormazione = () => registro.push("ricarica");
    const $ = () => ({{}}), document = {{ body: {{ contains: () => true }} }};
    const codice = {json.dumps(codice)};
    const api = async () => {{ if (codice === null) return {{ ok: true }}; const e = new Error("rifiutato"); e.codice = codice; throw e; }};
    ({gestore})().then(() => console.log(JSON.stringify({{ registro, salvata: sc.salvata }})));
    """
    r = subprocess.run([NODE, "-e", prova], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


@pytest.mark.skipif(NODE is None, reason="node non installato")
def test_web_ritorno_alla_consigliata_rifiutato_rimette_la_tua():
    """Il server rifiuta il ritorno (la consigliata sposterebbe chi gioca un anticipo già cominciato): vale ancora la scelta salvata,
    quindi sullo schermo torna lei (come «Annulla modifiche» e come l'iPhone), non la consigliata con «Modifiche non salvate»."""
    esito = _torna_alla_consigliata("giocatore_bloccato")
    assert esito["salvata"] == {"titolari": [1, 2, 3]}
    assert "avviso: rifiutato" in esito["registro"]
    dopo = esito["registro"][esito["registro"].index("avviso: rifiutato") + 1:]
    assert dopo == ["valuta [[1,2,3],false,true]"]                     # si rimette la tua, senza ridisegnare la consigliata


# ---------------------------------------------------------------- «Da fare»: nessun cambio su chi è bloccato
def _con_anticipo(m, monkeypatch, *ids):
    """Nel `mondo` di test_da_fare.py i giocatori `ids` giocano l'anticipo già cominciato (squadra ANTICIPO), gli altri no."""
    vecchia = da_fare.consigli.scheda_previsione
    monkeypatch.setattr(da_fare.consigli, "scheda_previsione",
                        lambda i, x: vecchia(i, x) | {"squadra": ANTICIPO if i in ids else "aaa"})
    monkeypatch.setattr(da_fare.consigli, "_anticipi_iniziati", lambda db, st, g: (ANTICIPO,) if ids else ())


def _dubbi(m):
    return [v for v in vai_da_fare(m) if v["tipo"] == "dubbio"]


def test_da_fare_niente_cambio_su_un_titolare_bloccato(mondo_da_fare, monkeypatch):
    """Rossi (5, in dubbio) e Bianchi (6, infortunato): la consigliata li toglie. Rossi gioca l'anticipo già cominciato: non si
    sposta più (il server rifiuterebbe il salvataggio), quindi niente voce su di lui; per Bianchi il cambio resta."""
    la_consigliata_cambia(mondo_da_fare, (6, 14), (5, 12))
    _con_anticipo(mondo_da_fare, monkeypatch, 5)
    d = _dubbi(mondo_da_fare)
    assert [v["id"] for v in d] == ["dubbio:6"]
    assert d[0]["alternativa"]["id"] == 14 and d[0]["azione"] == "Sostituisci"


def test_da_fare_chi_e_bloccato_non_entra(mondo_da_fare, monkeypatch):
    """Il 14 (quello che la consigliata mette al posto di Bianchi) gioca l'anticipo già cominciato: non può entrare."""
    la_consigliata_cambia(mondo_da_fare, (6, 14), (5, 12))
    _con_anticipo(mondo_da_fare, monkeypatch, 14)
    d = _dubbi(mondo_da_fare)
    assert {v["id"] for v in d} == {"dubbio:5", "dubbio:6"}
    assert all(v.get("alternativa", {}).get("id") != 14 for v in d)


def test_da_fare_senza_anticipi_come_prima(mondo_da_fare, monkeypatch):
    la_consigliata_cambia(mondo_da_fare, (6, 14), (5, 12))
    _con_anticipo(mondo_da_fare, monkeypatch)
    d = _dubbi(mondo_da_fare)
    assert [(v["id"], v["alternativa"]["id"]) for v in d] == [("dubbio:6", 14), ("dubbio:5", 12)]


def _consigliata_cambiata(m):
    return [v for v in vai_da_fare(m) if v["id"].startswith("consigliata:")]


@pytest.mark.parametrize("fermo", [7, 14], ids=["esce-un-bloccato", "entra-un-bloccato"])
def test_da_fare_consigliata_cambiata_solo_sui_bloccati_niente_voce(mondo_da_fare, monkeypatch, fermo):
    """Hai salvato la consigliata; ora schiera il 14 al posto del 7. Se uno dei due gioca l'anticipo già cominciato il cambio non
    si può fare: niente «La consigliata è cambiata»."""
    _salva_la_consigliata(mondo_da_fare)
    _cambia(mondo_da_fare, (7, 14))
    _con_anticipo(mondo_da_fare, monkeypatch)
    assert len(_consigliata_cambiata(mondo_da_fare)) == 1                 # senza anticipi la voce c'è (#333)
    _con_anticipo(mondo_da_fare, monkeypatch, fermo)
    assert _consigliata_cambiata(mondo_da_fare) == []


def test_da_fare_consigliata_cambiata_nomina_solo_chi_si_sposta(mondo_da_fare, monkeypatch):
    """Due cambi fra centrocampisti (14 per il 7, 12 per l'8) e il 7 gioca l'anticipo già cominciato: resta titolare, quindi entra
    un centrocampista solo, il più utile (il 14, 6,0 punti attesi contro i 4,5 del 12), al posto dell'8. Il 7 non si nomina."""
    _salva_la_consigliata(mondo_da_fare)
    _cambia(mondo_da_fare, (7, 14), (8, 12))
    _con_anticipo(mondo_da_fare, monkeypatch, 7)
    v = _consigliata_cambiata(mondo_da_fare)
    assert len(v) == 1
    assert v[0]["entrano"] == [{"id": 14, "nome": "g14"}] and v[0]["escono"] == [{"id": 8, "nome": "g8"}]
    assert v[0]["testo"] == "La consigliata è cambiata da quando l'hai salvata: rivedila. Ora schiera g14 al posto di g8."


def test_da_fare_consigliata_cambiata_se_non_entra_un_bloccato_resta_il_piu_utile(mondo_da_fare, monkeypatch):
    """La consigliata fa entrare il 14 (bloccato) e il 12 al posto del 7 e dell'8: il 14 non entra, quindi esce un centrocampista solo,
    il meno utile. Qui il 7 e l'8 valgono uguale: si dice «Riserva al posto di …» di uno solo dei due."""
    _salva_la_consigliata(mondo_da_fare)
    _cambia(mondo_da_fare, (7, 14), (8, 12))
    _con_anticipo(mondo_da_fare, monkeypatch, 14)
    v = _consigliata_cambiata(mondo_da_fare)
    assert len(v) == 1 and v[0]["entrano"] == [{"id": 12, "nome": "Riserva"}] and len(v[0]["escono"]) == 1
    assert v[0]["escono"][0]["id"] in (7, 8)


@pytest.mark.skipif(NODE is None, reason="node non installato")
def test_web_ritorno_alla_consigliata_negli_altri_casi_come_prima():
    riuscito = _torna_alla_consigliata(None)
    assert riuscito["salvata"] is None and riuscito["registro"][-1] == "disegna la consigliata"
    assert _torna_alla_consigliata("formazione_chiusa")["registro"][-1] == "ricarica"
