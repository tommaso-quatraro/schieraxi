"""«Sostituisci» dalla scheda di un titolare: chi può prendere il suo posto e quanto cambiano i punti attesi della FORMAZIONE.

Il collaudo del 26/11: toccando un difensore al 35% e poi «Sostituisci», la web scriveva «+2,7» e «+2,6» accanto ai due compagni
che giocano di più (la differenza fra i due giocatori), ma fatto il cambio i punti attesi della formazione cambiavano di −0,1 e
0,0: se il titolare non gioca entra già uno dalla panchina. Il numero giusto è quello di «Metti in campo» (#643): la valutazione
di POST /api/formazione/valuta della formazione dopo il cambio, meno quella di adesso, calcolata dal server. Gli stessi
giocatori di prima: lo stesso ruolo, non già titolari, nessuno che gioca un anticipo già cominciato; infortunati e squalificati
compresi (la riga dice il loro stato). Rosa e regole inventate."""
# ruff: noqa: F811  (le fixture importate arrivano come parametri con lo stesso nome: è il modo di pytest)
from datetime import datetime, timedelta

from fanta import scelte, server
from test_anticipi_scelta import CONSIGLIATA, GIORNATA, MESSAGGIO, ROSA as ROSA_ANTICIPI
from test_anticipi_scelta import mondo  # noqa: F401  (fixture: rosa, calendario e anticipo inventati, #373)
from test_metti_in_campo import ROSA, TITOLARI, _con, _schede, _somma
from test_server import client  # noqa: F401  (fixture del server)


def _entrate(esce, fermi=(), titolari=TITOLARI, punti=_somma) -> list[dict]:
    return scelte.chi_prende_il_posto(esce, titolari, _schede(), fermi, punti)


def _entrano(esce, **altro) -> dict[int, dict]:
    return {e["entra"]: e for e in _entrate(esce, **altro)}


def test_entrano_i_compagni_dello_stesso_ruolo_che_non_sono_titolari():
    """Per un difensore: gli altri difensori della rosa fuori dagli 11, anche lo squalificato (la riga dice il suo stato)."""
    assert set(_entrano(3)) == {21, 25}
    assert set(_entrano(6)) == {22, 23}                     # un centrocampista: anche l'infortunato
    assert set(_entrano(1)) == {20}                         # il portiere: solo l'altro portiere


def test_il_numero_e_quello_della_formazione_intera_non_dei_due_giocatori():
    """Il caso del collaudo: fra i due giocatori +2,7, ma la formazione dopo il cambio vale 65,2 invece di 65,3 (la panchina copre
    già il titolare che rischia di non giocare): la riga dice −0,1. In cima il cambio che rende di più alla FORMAZIONE."""
    valori = {frozenset(TITOLARI): 65.3, _con(TITOLARI, 3, 21): 65.2, _con(TITOLARI, 3, 25): 65.4}
    entrate = _entrate(3, punti=lambda ids: valori[frozenset(ids)])
    assert [(e["entra"], e["differenza"], e["punteggio_atteso"]) for e in entrate] == [(25, 0.1, 65.4), (21, -0.1, 65.2)]


def test_la_differenza_e_quella_dei_due_numeri_scritti():
    """Come `differenza` di POST /api/formazione/valuta: i due punteggi arrotondati a una cifra, poi la differenza."""
    valori = {frozenset(TITOLARI): 65.14, _con(TITOLARI, 3, 21): 63.56, _con(TITOLARI, 3, 25): 65.0}
    differenze = {e["entra"]: e["differenza"] for e in _entrate(3, punti=lambda ids: valori[frozenset(ids)])}
    assert differenze == {21: -1.5, 25: -0.1}


def test_a_parita_di_formazione_prima_chi_vale_di_piu_da_solo():
    """Spesso la panchina copre tutti allo stesso modo (0,0 per tutti): allora l'ordine di prima, dal giocatore con più punti
    attesi. Il 25 (6,0) prima del 21 (5,0)."""
    assert [e["entra"] for e in _entrate(3, punti=lambda ids: 60.0)] == [25, 21]


def test_chi_gioca_un_anticipo_gia_cominciato_non_esce_e_non_entra():
    assert _entrate(3, fermi=[3]) == []
    assert set(_entrano(3, fermi=[21])) == {25}


def test_chi_non_e_titolare_non_ha_sostituti():
    assert _entrate(21) == [] and _entrate(999) == []


def test_un_titolare_ripetuto_conta_una_volta():
    assert set(_entrano(3, titolari=TITOLARI + [2])) == {21, 25}


def test_niente_conti_se_non_c_e_nessuno_da_far_entrare():
    """Nessun candidato: nessuna formazione da valutare (ognuna costa una decina di millisecondi)."""
    chiamate = []
    rosa_senza = {i: v for i, v in ROSA.items() if i != 20}
    assert scelte.chi_prende_il_posto(1, TITOLARI, _schede(rosa_senza), (), lambda ids: chiamate.append(ids) or 0.0) == []
    assert chiamate == []


# ---------------------------------------------------------------- la rotta: POST /api/formazione/sostituisci
# Il mondo dei test sugli anticipi (#373): giornata 10, consigliata 4-4-2, il 5 (titolare) e il 16 (riserva) giocano un anticipo
# già cominciato, il gruppo principale fra tre giorni.
def _chiedi(mondo, esce, titolari=CONSIGLIATA, giornata=GIORNATA, **altro):
    return mondo["client"].post("/api/formazione/sostituisci", json={"esce": esce, "titolari": titolari, "giornata": giornata}, **altro)


def _valutata(mondo, titolari) -> float:
    r = mondo["client"].post("/api/formazione/valuta", json={"titolari": titolari, "giornata": GIORNATA})
    assert r.status_code == 200, r.text
    return r.json()["punteggio_atteso"]


def test_la_rotta_dice_chi_puo_entrare(mondo):
    r = _chiedi(mondo, 4)                                               # un difensore titolare
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["giornata"] == GIORNATA and corpo["esce"] == 4
    assert {e["entra"] for e in corpo["entrate"]} == {12}               # il 16 è dell'anticipo: non entra


def test_i_punti_sono_quelli_di_valuta_per_la_formazione_dopo_il_cambio(mondo):
    """La stessa valutazione di POST /api/formazione/valuta (simulazioni vere, niente finti): adesso e dopo il cambio, e la
    differenza dei due numeri scritti. Fatto il cambio, i punti attesi accanto al modulo cambiano proprio di tanto."""
    corpo = _chiedi(mondo, 10).json()                                   # un attaccante: entra il 14
    adesso = _valutata(mondo, CONSIGLIATA)
    assert corpo["punteggio_atteso"] == adesso
    assert [e["entra"] for e in corpo["entrate"]] == [14]
    for e in corpo["entrate"]:
        dopo = _valutata(mondo, [e["entra"] if i == 10 else i for i in CONSIGLIATA])
        assert e["punteggio_atteso"] == dopo and e["differenza"] == round(dopo - adesso, 1), e


def test_la_rotta_da_il_numero_della_formazione_anche_quando_i_due_giocatori_dicono_il_contrario(mondo, monkeypatch):
    """Il caso del collaudo: +2,7 fra i due giocatori, −0,1 per la formazione. La rotta dice −0,1."""
    schede = {str(i): {"id": i, "nome": n, "ruolo": r, "squadra": s, "punti_attesi": 6.0, "p_voto": 0.9} for i, (n, r, s) in ROSA_ANTICIPI.items()}
    schede["12"]["punti_attesi"], schede["4"]["punti_attesi"] = 4.8, 2.1                  # il 12 al posto del 4: +2,7
    monkeypatch.setattr(server.consigli, "formazione", lambda *a, **k: {"giornata": GIORNATA, "schede": schede})
    con_il_12 = [12 if i == 4 else i for i in CONSIGLIATA]

    def valuta(db, regole, rose, titolari, squadra=None, giornata=None, *a, **k):
        return {"modulo": "4-4-2", "giornata": GIORNATA, "punteggio_atteso": 65.3 if sorted(titolari) == sorted(CONSIGLIATA)
                else 65.2 if sorted(titolari) == sorted(con_il_12) else 60.0}
    monkeypatch.setattr(server.consigli, "valuta", valuta)
    entrate = {e["entra"]: e for e in _chiedi(mondo, 4).json()["entrate"]}
    assert entrate[12]["differenza"] == -0.1 and entrate[12]["punteggio_atteso"] == 65.2


def test_la_rotta_non_scrive_niente_e_non_chiede_if_match(mondo):
    assert _chiedi(mondo, 4, headers={"If-Match": '"vecchio"'}).status_code == 200
    assert mondo["client"].get("/api/scelta", params={"giornata": GIORNATA}).json() is None


def test_chi_gioca_un_anticipo_gia_cominciato_non_si_sostituisce_e_la_rotta_dice_perche(mondo):
    """Il 5 gioca un anticipo già cominciato (il server lo legge al momento della richiesta, anche se la pagina non lo sapeva
    ancora): la stessa risposta del salvataggio, 400 `giocatore_bloccato` con la sua frase."""
    r = _chiedi(mondo, 5)
    assert r.status_code == 400, r.text
    assert r.json() == {"detail": MESSAGGIO.format("Dif5"), "codice": "giocatore_bloccato"}


def test_con_11_che_non_si_possono_schierare_risponde_400(mondo):
    r = _chiedi(mondo, 4, titolari=CONSIGLIATA[:10])
    assert r.status_code == 400 and r.json()["codice"] == "formazione_non_valida"


def test_dopo_la_scadenza_risponde_409_formazione_chiusa(mondo):
    mondo["anticipo"] = datetime.now() - timedelta(hours=2)
    mondo["principale"] = datetime.now() - timedelta(hours=1)
    r = _chiedi(mondo, 4)
    assert r.status_code == 409 and r.json()["codice"] == "formazione_chiusa", r.text
