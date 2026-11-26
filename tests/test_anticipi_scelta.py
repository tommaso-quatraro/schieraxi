"""Formazione salvata e anticipi già cominciati (#373, sotto #166). Un anticipo (turno.py: da 36 ore a 7 giorni prima del gruppo
principale) non fissa la scadenza: la formazione resta aperta, ma nella lega i giocatori di una partita già cominciata non si
spostano più. Rispetto alla formazione che vale in quel momento (la scelta salvata se c'è e vale, altrimenti la consigliata) un
salvataggio che ne sposta uno si rifiuta (400, `codice: "giocatore_bloccato"`), e così il ritorno alla consigliata; `GET
/api/formazione` dice chi è fermo nel campo facoltativo `bloccati`. Senza anticipi cominciati nulla cambia.
«Cominciato» è la regola della consigliata (`consigli._anticipi_iniziati`, #368): calendario e orario.
Rosa, squadre e calendario inventati; file in cartelle temporanee."""
# ruff: noqa: F811  (la fixture `client` importata da test_server arriva come parametro con lo stesso nome: è il modo di pytest)
from datetime import datetime, timedelta

import pandas as pd
import pytest

from fanta import archivio, calcolo, consigli, da_fare, diario, lega, scelte, server
from fanta.regole import Regole
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
        giocate = [stato.get("anticipo_giocato", 0)] + [0] * 9
        righe = [(GIORNATA, q, c, t, g) for q, (c, t), g in zip(date, squadre, giocate)]
        if stato.get("giornate_vicine"):            # la 9, giocata intorno all'anticipo, e la 11, una settimana dopo il gruppo principale
            righe += [(GIORNATA - 1, stato["anticipo"] - timedelta(days=1) + timedelta(hours=3 * k), f"f{k}", f"g{k}", 1)
                      for k in range(10)]
            righe += [(GIORNATA + 1, stato["principale"] + timedelta(days=7, hours=3 * k), f"d{k}", f"e{k}", 0) for k in range(10)]
        archivio.inserisci(d, "partite", [{"id": n, "stagione": ST, "giornata": g, "data": q.strftime("%Y-%m-%d %H:%M"),
                                           "casa": c, "trasferta": t, "gol_casa": None, "gol_trasferta": None, "giocata": gi,
                                           "understat_id": None} for n, (g, q, c, t, gi) in enumerate(righe)])
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


def test_anticipo_di_settimane_la_formazione_si_salva_e_i_suoi_giocatori_restano_fermi(mondo):
    """Coordinatore, #695 (difetto già su main): l'anticipo è stato giocato due settimane fa, insieme alla giornata 9 (Supercoppa,
    coppe), il gruppo principale è fra tre giorni e la giornata 11 una settimana dopo. La scadenza viene dal gruppo principale: la
    formazione si salva (prima: 409, giornata già iniziata dal giorno dell'anticipo), e chi ha giocato l'anticipo resta fermo."""
    mondo |= {"anticipo": datetime.now() - timedelta(days=14), "anticipo_giocato": 1, "giornate_vicine": True}
    assert _salva(mondo, SENZA_ANTICIPO).status_code == 200
    assert _salvata(mondo) == SENZA_ANTICIPO
    _rifiutato(_salva(mondo, DENTRO_IL_16), "Dif16")
    f = _formazione(mondo)
    assert f["iniziata"] is False and f["bloccati"] == BLOCCATI


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


# Chi può prendere il posto di un titolare in «Sostituisci» lo dice il server dal 26/11 (POST /api/formazione/sostituisci): i
# bloccati non escono e non entrano, provato in tests/test_sostituisci.py (prima qui con la funzione `sostituti` della web, tolta).


# ---------------------------------------------------------------- «Da fare»: nessun cambio su chi è bloccato
def _con_anticipo(m, monkeypatch, *ids):
    """Nel `mondo` di test_da_fare.py i giocatori `ids` giocano l'anticipo già cominciato (squadra ANTICIPO), gli altri no."""
    vecchia = da_fare.consigli.scheda_previsione
    monkeypatch.setattr(da_fare.consigli, "scheda_previsione",
                        lambda i, x: vecchia(i, x) | {"squadra": ANTICIPO if i in ids else "aaa"})
    monkeypatch.setattr(da_fare.consigli, "_anticipi_iniziati", lambda db, st, g, adesso=None: (ANTICIPO,) if ids else ())


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


@pytest.mark.parametrize("fermo", [10, 14], ids=["esce-un-bloccato", "entra-un-bloccato"])
def test_da_fare_consigliata_cambiata_con_un_cambio_di_ruolo_impossibile_niente_voce(mondo_da_fare, monkeypatch, fermo):
    """#816: la consigliata cambia modulo, entra il centrocampista 14 ed esce l'attaccante 10. Se uno dei due gioca l'anticipo già
    cominciato non si sposta, e nessun cambio dello stesso ruolo lo sostituisce: togliere solo l'altro lascerebbe 12 titolari
    («Ora schiera g14 al posto di .») o 10 («Ora schiera  al posto di g10.»). Niente voce, mai una frase con un nome vuoto."""
    regole = Regole(moduli=["3-5-2", "3-6-1"])                            # la consigliata passa dal 3-5-2 al 3-6-1
    _salva_la_consigliata(mondo_da_fare)
    _cambia(mondo_da_fare, (10, 14))
    _con_anticipo(mondo_da_fare, monkeypatch)
    v = [x for x in vai_da_fare(mondo_da_fare, regole=regole) if x["id"].startswith("consigliata:")]
    assert len(v) == 1 and v[0]["testo"].endswith("Ora schiera g14 al posto di g10.")      # senza anticipi la voce c'è
    _con_anticipo(mondo_da_fare, monkeypatch, fermo)
    v = [x for x in vai_da_fare(mondo_da_fare, regole=regole) if x["id"].startswith("consigliata:")]
    assert v == [], [str(x["testo"]) for x in v]


def test_da_fare_cambio_di_modulo_impossibile_resta_la_voce_dell_infortunato(mondo_da_fare, monkeypatch):
    """#816, revisione: la consigliata ha tolto l'attaccante 10, che gioca l'anticipo già cominciato (entra il centrocampista 14), e
    intanto il centrocampista salvato Bianchi (6) si è infortunato (entra il 12). Il cambio di modulo non si può fare e la sua voce
    sparisce, ma la voce dell'infortunato resta, con un cambio dello stesso ruolo che si può fare: in cima alla Formazione c'è ancora
    una decisione, e nessun cambio tocca il 10."""
    regole = Regole(moduli=["3-5-2", "3-6-1"])
    _salva_la_consigliata(mondo_da_fare)
    _cambia(mondo_da_fare, (10, 14), (6, 12))
    _con_anticipo(mondo_da_fare, monkeypatch, 10)
    voci = vai_da_fare(mondo_da_fare, regole=regole)
    assert not [v for v in voci if v["id"].startswith("consigliata:")]
    bianchi = next((v for v in voci if v["id"] == "dubbio:6"), None)
    assert bianchi is not None and bianchi["priorita"] == 1 and bianchi["testo"].startswith("Bianchi è infortunato. Meglio "), voci
    assert bianchi["alternativa"]["id"] in (12, 14) and bianchi["azione"] == "Sostituisci" and bianchi.get("decisione") == 1
    # nessun cambio impossibile: chi gioca l'anticipo non si sposta, e nessuna voce propone un cambio per chi non è fuori
    assert all(v.get("giocatore", {}).get("id") != 10 and v.get("alternativa", {}).get("id") != 10 for v in voci)
    assert [v["id"] for v in voci if "alternativa" in v] == ["dubbio:6"]
