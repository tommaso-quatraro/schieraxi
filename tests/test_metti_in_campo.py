"""«Metti in campo» dalla scheda di un giocatore che non è fra gli 11 (#643): chi può lasciargli il posto lo calcola il server.

Lo stesso ruolo, oppure un altro ruolo se il modulo che ne esce è ammesso dalla lega (la regola unica della scelta,
`scelte.motivo_non_valida`). Per ognuno il modulo dopo il cambio e la differenza dei punti attesi della FORMAZIONE intera (dopo
il cambio meno adesso, con la valutazione di POST /api/formazione/valuta), non il confronto fra i due giocatori; in cima il cambio
che rende di più. Gli stessi giocatori che «Sostituisci» propone: nessuno per chi è già titolare o gioca un anticipo già
cominciato; infortunati e squalificati sì, come fra i sostituti (la scheda dice il loro stato). Rosa e regole inventate."""
# ruff: noqa: F811  (le fixture importate arrivano come parametri con lo stesso nome: è il modo di pytest)
from datetime import datetime, timedelta

from fanta import scelte, server
from fanta.regole import Regole
from test_anticipi_scelta import CONSIGLIATA, GIORNATA, ROSA as ROSA_ANTICIPI
from test_anticipi_scelta import mondo  # noqa: F401  (fixture: rosa, calendario e anticipo inventati, #373)
from test_server import client  # noqa: F401  (fixture del server)

# id: (ruolo, punti attesi, stato delle probabili)
ROSA = {1: ("P", 4.0, None), 20: ("P", 3.0, None),
        2: ("D", 4.0, None), 3: ("D", 6.5, None), 4: ("D", 5.2, None), 5: ("D", 5.5, None), 21: ("D", 5.0, None),
        25: ("D", 6.0, "squalificato"),
        6: ("C", 6.0, None), 7: ("C", 5.0, None), 8: ("C", 5.5, None), 22: ("C", 5.8, None), 23: ("C", 7.0, "infortunato"),
        9: ("A", 7.0, None), 10: ("A", 5.0, None), 11: ("A", 6.0, None), 24: ("A", 6.2, None)}
TITOLARI = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]                   # 4-3-3


def _schede(rosa=ROSA) -> dict:
    """Come il campo `schede` di GET /api/formazione: chiavi testo."""
    return {str(i): {"id": i, "nome": f"Gioc{i}", "ruolo": r, "punti_attesi": p, "stato": s, "titolarita": "titolare"}
            for i, (r, p, s) in rosa.items()}


def _somma(ids) -> float:
    """Una valutazione finta della formazione: la somma dei punti attesi degli 11 (quella vera è POST /api/formazione/valuta)."""
    return sum(ROSA[i][1] for i in ids)


def _uscite(entra, regole=None, fermi=(), titolari=TITOLARI, punti=_somma) -> list[dict]:
    return scelte.chi_lascia_il_posto(entra, titolari, _schede(), regole or Regole(), fermi, punti)


def _escono(entra, **altro) -> dict[int, dict]:
    return {u["esce"]: u for u in _uscite(entra, **altro)}


def _con(ids, esce, entra) -> frozenset:
    return frozenset(entra if i == esce else i for i in ids)


def test_lo_stesso_ruolo_lascia_il_posto_senza_cambiare_modulo():
    escono = _escono(21)
    for i in (2, 3, 4, 5):
        assert escono[i]["modulo"] == "4-3-3" and escono[i]["cambia_modulo"] is False, escono[i]


def test_un_cambio_di_modulo_ammesso_dalla_lega_c_e_con_il_modulo_nuovo():
    """Un difensore entra al posto di un attaccante: 5-3-2, che la lega ammette."""
    escono = _escono(21)
    for i in (9, 10, 11):
        assert escono[i]["modulo"] == "5-3-2" and escono[i]["cambia_modulo"] is True, escono[i]


def test_un_cambio_di_modulo_non_ammesso_non_c_e():
    """Un difensore al posto di un centrocampista darebbe il 5-2-3, che la lega non ammette; nemmeno il portiere esce per lui."""
    escono = _escono(21)
    assert not {6, 7, 8, 1} & set(escono), escono
    assert set(escono) == {2, 3, 4, 5, 9, 10, 11}


def test_i_moduli_sono_quelli_delle_regole_della_lega():
    """Lo stesso cambio compare o sparisce con i moduli della lega: la regola è nella configurazione, non nel codice."""
    assert not {9, 10, 11} & set(_escono(21, regole=Regole(moduli=["4-3-3", "4-4-2"])))
    assert {6, 7, 8} <= set(_escono(21, regole=Regole(moduli=["4-3-3", "5-2-3"])))


def test_un_centrocampista_puo_entrare_per_un_difensore_o_per_un_attaccante():
    escono = _escono(22)
    assert {i: escono[i]["modulo"] for i in escono} == {2: "3-4-3", 3: "3-4-3", 4: "3-4-3", 5: "3-4-3", 6: "4-3-3",
                                                         7: "4-3-3", 8: "4-3-3", 9: "4-4-2", 10: "4-4-2", 11: "4-4-2"}


def test_il_portiere_entra_solo_al_posto_del_portiere():
    assert set(_escono(20)) == {1}


def test_il_numero_e_quello_della_formazione_intera_non_dei_due_giocatori():
    """Il caso visto con il server vero: fra i due giocatori +1,2 (6,2 contro 5,0), ma la formazione dopo il cambio vale 63,5
    invece di 65,1 (la panchina copre in modo diverso): la riga dice −1,6. In cima il cambio che rende di più alla formazione,
    anche se fra i due giocatori la differenza è più piccola."""
    valori = {frozenset(TITOLARI): 65.1, _con(TITOLARI, 10, 24): 63.5, _con(TITOLARI, 11, 24): 65.4, _con(TITOLARI, 9, 24): 64.0}
    uscite = _uscite(24, punti=lambda ids: valori[frozenset(ids)])
    assert round(ROSA[24][1] - ROSA[10][1], 1) == 1.2                    # fra i due giocatori: +1,2
    assert [(u["esce"], u["differenza"], u["punteggio_atteso"]) for u in uscite] == [(11, 0.3, 65.4), (9, -1.1, 64.0), (10, -1.6, 63.5)]


def test_la_differenza_e_quella_dei_due_numeri_scritti():
    """Come `differenza` di POST /api/formazione/valuta: i due punteggi arrotondati a una cifra, poi la differenza (65,14 e 63,56
    si scrivono 65,1 e 63,6: −1,5, non −1,58 arrotondato a −1,6)."""
    valori = {frozenset(TITOLARI): 65.14, _con(TITOLARI, 10, 24): 63.56, _con(TITOLARI, 11, 24): 65.0, _con(TITOLARI, 9, 24): 64.0}
    differenze = {u["esce"]: u["differenza"] for u in _uscite(24, punti=lambda ids: valori[frozenset(ids)])}
    assert differenze[10] == -1.5 and differenze[11] == -0.1


def test_chi_gioca_un_anticipo_gia_cominciato_non_esce_e_non_entra():
    assert 3 not in _escono(21, fermi=[3])
    assert _escono(21, fermi=[21]) == {}


def test_infortunati_e_squalificati_si_mettono_in_campo_come_fra_i_sostituti():
    """«Sostituisci» li propone (con il loro stato scritto nella riga): qui lo stesso."""
    assert set(_escono(23)) == {6, 7, 8, 2, 3, 4, 5, 9, 10, 11}
    assert set(_escono(25)) == {2, 3, 4, 5, 9, 10, 11}


def test_un_titolare_ripetuto_conta_una_volta_come_in_valuta():
    """Revisione della #783: 12 voci con il difensore 2 ripetuto davano due righe «esce 2» e moduli sbagliati («5-3-3»). Come la
    regola unica della scelta (e quindi `valuta`), un titolare ripetuto conta una volta."""
    uscite = _uscite(21, titolari=TITOLARI + [2])
    assert sorted(u["esce"] for u in uscite) == [2, 3, 4, 5, 9, 10, 11]
    assert {u["esce"]: u["modulo"] for u in uscite} == {2: "4-3-3", 3: "4-3-3", 4: "4-3-3", 5: "4-3-3", 9: "5-3-2", 10: "5-3-2", 11: "5-3-2"}


def test_un_titolare_o_uno_che_non_e_della_rosa_non_ha_nessuno_da_far_uscire():
    assert _escono(2) == {}
    assert _escono(999) == {}


# ---------------------------------------------------------------- la rotta: POST /api/formazione/metti-in-campo
# Il mondo dei test sugli anticipi (#373): giornata 10, consigliata 4-4-2, il 5 (titolare) e il 16 (riserva) giocano un anticipo
# già cominciato, il gruppo principale fra tre giorni.
def _chiedi(mondo, entra, titolari=CONSIGLIATA, giornata=GIORNATA, **altro):
    return mondo["client"].post("/api/formazione/metti-in-campo", json={"entra": entra, "titolari": titolari, "giornata": giornata}, **altro)


def _valutata(mondo, titolari) -> float:
    r = mondo["client"].post("/api/formazione/valuta", json={"titolari": titolari, "giornata": GIORNATA})
    assert r.status_code == 200, r.text
    return r.json()["punteggio_atteso"]


def test_la_rotta_dice_chi_puo_uscire_con_il_modulo(mondo):
    r = _chiedi(mondo, 12)                                              # un difensore della panchina
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["giornata"] == GIORNATA and corpo["entra"] == 12
    moduli = {u["esce"]: (u["modulo"], u["cambia_modulo"]) for u in corpo["uscite"]}
    assert moduli == {2: ("4-4-2", False), 3: ("4-4-2", False), 4: ("4-4-2", False),           # il 5 gioca l'anticipo: resta
                      6: ("5-3-2", True), 7: ("5-3-2", True), 8: ("5-3-2", True), 9: ("5-3-2", True),
                      10: ("5-4-1", True), 11: ("5-4-1", True)}


def test_i_punti_sono_quelli_di_valuta_per_la_formazione_dopo_il_cambio(mondo):
    """La stessa valutazione di POST /api/formazione/valuta (simulazioni vere, niente finti): adesso e dopo ogni cambio, e la
    differenza dei due numeri scritti; in ordine dal cambio che rende di più."""
    corpo = _chiedi(mondo, 12).json()
    adesso = _valutata(mondo, CONSIGLIATA)
    assert corpo["punteggio_atteso"] == adesso
    for u in corpo["uscite"]:
        dopo = _valutata(mondo, [12 if i == u["esce"] else i for i in CONSIGLIATA])
        assert u["punteggio_atteso"] == dopo and u["differenza"] == round(dopo - adesso, 1), u
    differenze = [u["differenza"] for u in corpo["uscite"]]
    assert differenze == sorted(differenze, reverse=True)


def test_la_rotta_da_il_numero_della_formazione_anche_quando_i_due_giocatori_dicono_il_contrario(mondo, monkeypatch):
    """Il caso visto con il server vero: +1,2 fra i due giocatori, −1,6 per la formazione. La rotta dice −1,6."""
    schede = {str(i): {"id": i, "nome": n, "ruolo": r, "squadra": s, "punti_attesi": 6.0, "p_voto": 0.9} for i, (n, r, s) in ROSA_ANTICIPI.items()}
    schede["12"]["punti_attesi"], schede["4"]["punti_attesi"] = 6.2, 5.0                  # il 12 entra al posto del 4: +1,2
    monkeypatch.setattr(server.consigli, "formazione", lambda *a, **k: {"giornata": GIORNATA, "schede": schede})
    con_il_12 = [12 if i == 4 else i for i in CONSIGLIATA]

    def valuta(db, regole, rose, titolari, squadra=None, giornata=None, *a, **k):
        return {"modulo": "4-4-2", "giornata": GIORNATA, "punteggio_atteso": 65.1 if sorted(titolari) == sorted(CONSIGLIATA)
                else 63.5 if sorted(titolari) == sorted(con_il_12) else 60.0}
    monkeypatch.setattr(server.consigli, "valuta", valuta)
    uscite = {u["esce"]: u for u in _chiedi(mondo, 12).json()["uscite"]}
    assert uscite[4]["differenza"] == -1.6 and uscite[4]["punteggio_atteso"] == 63.5


def test_la_rotta_non_scrive_niente_e_non_chiede_if_match(mondo):
    """Non scrive: un If-Match vecchio non la ferma (niente 412) e la scelta resta com'è. Il 412 lo dà il salvataggio dopo,
    POST /api/formazione/valuta con `salva` (provato nel browser)."""
    assert _chiedi(mondo, 12, headers={"If-Match": '"vecchio"'}).status_code == 200
    assert mondo["client"].get("/api/scelta", params={"giornata": GIORNATA}).json() is None


def test_chi_gioca_un_anticipo_gia_cominciato_non_si_mette_in_campo(mondo):
    r = _chiedi(mondo, 16)
    assert r.status_code == 200 and r.json()["uscite"] == []


def test_con_11_che_non_si_possono_schierare_risponde_400(mondo):
    r = _chiedi(mondo, 12, titolari=CONSIGLIATA[:10])
    assert r.status_code == 400 and r.json()["codice"] == "formazione_non_valida"


def test_dopo_la_scadenza_risponde_409_formazione_chiusa(mondo):
    mondo["anticipo"] = datetime.now() - timedelta(hours=2)
    mondo["principale"] = datetime.now() - timedelta(hours=1)
    r = _chiedi(mondo, 12)
    assert r.status_code == 409 and r.json()["codice"] == "formazione_chiusa", r.text
