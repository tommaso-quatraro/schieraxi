"""Il modello usa i dati di prima della scadenza della formazione (`avvisi.prima_partita`: dall'inizio del turno), non di prima della
PRIMA partita della giornata. Con una partita anticipata di settimane (Supercoppa, coppe: #659, #695) la previsione si fermava a
quella partita e non vedeva la giornata prima. Le partite della giornata stessa (anticipi compresi) non entrano mai nella sua
previsione: sono quello che si prevede. Valgono le stesse regole per gli avversari della misura (verifica, registro), e la misura
delle previsioni passate non conta chi ha giocato prima della scadenza (sarebbe previsto con dati di dopo la sua partita).
Solo dati inventati: venti squadre finte in un archivio in una cartella temporanea."""
from datetime import datetime, timedelta

import pandas as pd
import pytest

from fanta import archivio, avvisi, diario, modello, registro_giornate as rg, verifica, verifica_pacchetti as vp
from fanta.regole import Regole

ST = "2026-27"
G10 = ["2026-10-31 15:00", "2026-10-31 18:00", "2026-10-31 20:45", "2026-11-01 12:30", "2026-11-01 15:00", "2026-11-01 15:00",
       "2026-11-01 18:00", "2026-11-01 20:45", "2026-11-02 18:30", "2026-11-02 20:45"]
G11 = ["2026-11-06 20:45", "2026-11-07 15:00", "2026-11-07 15:00", "2026-11-07 18:00", "2026-11-07 20:45", "2026-11-08 12:30",
       "2026-11-08 15:00", "2026-11-08 15:00", "2026-11-08 18:00", "2026-11-08 20:45"]
G12 = ["2026-11-21 15:00", "2026-11-21 18:00", "2026-11-21 20:45", "2026-11-22 12:30", "2026-11-22 15:00", "2026-11-22 15:00",
       "2026-11-22 18:00", "2026-11-22 20:45", "2026-11-23 18:30", "2026-11-23 20:45"]
ANTICIPO_LONTANO = "2026-11-02 20:45"      # una partita della 12 giocata tre settimane prima del suo turno
CENTROCAMPISTA_11 = 102                   # gioca la partita delle 15:00 di sabato 7/11 (giornata 11)
DELL_ANTICIPO = 100                       # gioca l'anticipo lontano della 12


def _sposta(date: list[str], giorni: int) -> list[str]:
    return [(datetime.fromisoformat(d) + timedelta(days=giorni)).strftime("%Y-%m-%d %H:%M") for d in date]


def _giocate(date: list[str]) -> list[tuple[str, int]]:
    return [(d, 1) for d in date]


def _da_giocare(date: list[str]) -> list[tuple[str, int]]:
    return [(d, 0) for d in date]


# la 12 con la prima partita giocata il 2/11 e le altre nel suo turno (21-23/11), la 13 una settimana dopo
CON_ANTICIPO_LONTANO = {10: _giocate(G10), 11: _giocate(G11), 12: [(ANTICIPO_LONTANO, 1)] + _da_giocare(G12[1:]),
                        13: _da_giocare(_sposta(G12, 7))}


def _archivio(percorso, calendario: dict, speciali: dict | None = None):
    """L'archivio con il calendario {giornata: [(data, giocata)]}: venti squadre finte (la partita k è s{2k} contro s{2k+1}), un
    centrocampista per squadra (id 100 + numero della squadra) con un 6 in ogni partita giocata. `speciali` = {(giornata, id): campi
    del voto da cambiare}."""
    db = archivio.apri(percorso)
    for k in range(20):
        db.execute("INSERT INTO calciatori (id, nome, ruolo, squadra, squadra_slug, quotazione) VALUES (?, ?, 'C', ?, ?, 10)",
                   (100 + k, f"finto{k}", f"S{k}", f"s{k}"))
    for g, partite in calendario.items():
        for k, (data, giocata) in enumerate(partite):
            gol = 1 if giocata else None
            db.execute("INSERT INTO partite (id, stagione, giornata, data, casa, trasferta, gol_casa, gol_trasferta, giocata) "
                       "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (g * 100 + k, ST, g, data, f"s{2 * k}", f"s{2 * k + 1}", gol, gol, giocata))
            if not giocata:
                continue
            for sq in (2 * k, 2 * k + 1):
                campi = {"stagione": ST, "giornata": g, "calciatore_id": 100 + sq, "nome": f"finto{sq}", "squadra": f"s{sq}",
                         "ruolo": "C", "voto_red": 6.0, "voto_stat": 6.0, "voto_ita": 6.0, "gol": 0, "gol_subiti": 0, "autogol": 0,
                         "rig_segnati": 0, "rig_sbagliati": 0, "rig_parati": 0, "assist": 0, "mvp": 0, "ammonizioni": 0,
                         "espulsioni": 0, "subentrato": 0, "sostituito": 0} | (speciali or {}).get((g, 100 + sq), {})
                db.execute(f"INSERT INTO voti ({', '.join(campi)}) VALUES ({', '.join('?' * len(campi))})", tuple(campi.values()))
    db.commit()
    return db


def _dati(tmp_path, nome: str, calendario: dict, speciali: dict | None = None) -> modello.Dati:
    db = _archivio(tmp_path / f"{nome}.sqlite", calendario, speciali)
    try:
        return modello.carica(db)
    finally:
        db.close()


def _mu(d: modello.Dati, giornata: int) -> dict[int, float]:
    return modello.previsioni(d, ST, giornata, Regole()).set_index("id")["mu"].to_dict()


GRANDE = {"voto_red": 9.0, "voto_stat": 9.0, "voto_ita": 9.0, "gol": 2, "assist": 1}


def test_con_una_partita_anticipata_di_settimane_il_modello_si_ferma_alla_scadenza(tmp_path):
    """Lo scenario di #695: la 12 si gioca dal 21/11 e una sua partita è stata giocata il 2/11. Il modello si fermava al 2/11 20:45;
    ora si ferma dove si chiude la formazione, come la scadenza."""
    db = _archivio(tmp_path / "a.sqlite", CON_ANTICIPO_LONTANO)
    d = modello.carica(db)
    assert avvisi.prima_partita(db, ST, 12) == datetime(2026, 11, 21, 18, 0)
    assert d.inizio(ST, 12) == "2026-11-21 18:00"


def test_con_una_partita_anticipata_di_settimane_la_giornata_prima_entra_nella_previsione(tmp_path):
    """Prima la previsione della 12 non vedeva nessuna delle 10 partite della 11: un 9 con due gol il 7/11 non cambiava niente."""
    normale = _mu(_dati(tmp_path, "normale", CON_ANTICIPO_LONTANO), 12)
    grande = _mu(_dati(tmp_path, "grande", CON_ANTICIPO_LONTANO, {(11, CENTROCAMPISTA_11): GRANDE}), 12)
    assert grande[CENTROCAMPISTA_11] > normale[CENTROCAMPISTA_11] + 0.05


def test_la_partita_anticipata_della_giornata_non_entra_nella_sua_previsione(tmp_path):
    """La partita della 12 giocata il 2/11 è prima della scadenza, ma è della 12: è quello che si prevede, non un dato."""
    normale = _mu(_dati(tmp_path, "normale", CON_ANTICIPO_LONTANO), 12)
    grande = _mu(_dati(tmp_path, "grande", CON_ANTICIPO_LONTANO, {(12, DELL_ANTICIPO): GRANDE}), 12)
    assert grande == normale


def test_l_anticipo_del_venerdi_gia_giocato_non_entra_nella_previsione_della_sua_giornata(tmp_path):
    """Giornata in corso: la partita del venerdì è giocata, le altre no. La previsione della giornata resta quella di prima del
    venerdì (la scadenza)."""
    calendario = {10: _giocate(G10), 11: [(G11[0], 1)] + _da_giocare(G11[1:]), 12: _da_giocare(G12)}
    d = _dati(tmp_path, "normale", calendario)
    assert d.inizio(ST, 11) == G11[0]
    grande = _dati(tmp_path, "grande", calendario, {(11, 100): GRANDE, (11, 101): GRANDE})
    assert _mu(grande, 11) == _mu(d, 11)


def _rinviate(n: int) -> list[tuple[str, int]]:
    """La 10 con le prime 10 - n partite giocate nel fine settimana e le altre n rinviate a dicembre."""
    recuperi = ["2026-12-02 18:30", "2026-12-02 20:45", "2026-12-02 20:45", "2026-12-03 18:30", "2026-12-03 20:45", "2026-12-03 20:45"]
    return _giocate(G10[:10 - n]) + _da_giocare(recuperi[:n])


CALENDARI = {
    "anticipo lontano": CON_ANTICIPO_LONTANO,
    "tre anticipi lontani": {10: _giocate(G10), 11: _giocate(G11),
                             12: _giocate(["2026-11-02 20:45", "2026-11-03 20:45", "2026-11-04 20:45"]) + _da_giocare(G12[3:]),
                             13: _da_giocare(_sposta(G12, 7))},
    "4 giocate e 6 rinviate": {10: _rinviate(6), 11: _giocate(G11), 12: _da_giocare(G12)},
    "anticipo di mercoledì": {10: _giocate(G10), 11: [("2026-11-04 20:45", 1)] + _da_giocare(G11[1:]), 12: _da_giocare(G12)},
    "rinviata con la data vecchia": {10: _giocate(G10), 11: [("2026-10-20 20:45", 0)] + _da_giocare(G11[1:]), 12: _da_giocare(G12)},
    "giornate normali": {10: _giocate(G10), 11: _giocate(G11), 12: _da_giocare(G12)},
}


@pytest.mark.parametrize("calendario", CALENDARI.values(), ids=CALENDARI.keys())
def test_il_modello_si_ferma_dove_si_chiude_la_formazione(tmp_path, calendario):
    """Una regola sola: il modello vede i dati di prima della scadenza della formazione, calcolata come `avvisi.prima_partita`."""
    db = _archivio(tmp_path / "a.sqlite", calendario)
    d = modello.carica(db)
    for g in calendario:
        assert d.inizio(ST, g) == avvisi.prima_partita(db, ST, g).strftime("%Y-%m-%d %H:%M"), g


def test_gli_avversari_della_misura_vedono_gli_stessi_dati_del_modello(tmp_path):
    """La fantamedia tirata (verifica e registro delle giornate) e gli squalificati dai cartellini della verifica usano gli stessi
    dati del modello: la giornata prima sì, la partita anticipata della giornata no."""
    speciali = {(11, CENTROCAMPISTA_11): GRANDE | {"espulsioni": 1}, (12, DELL_ANTICIPO): GRANDE}
    db = _archivio(tmp_path / "a.sqlite", CON_ANTICIPO_LONTANO, speciali)
    d = modello.carica(db)
    tirate, _ = verifica.avversari(d, ST, 12, Regole())
    assert tirate[CENTROCAMPISTA_11] > tirate[CENTROCAMPISTA_11 + 1]            # il 9 con due gol del 7/11 conta
    assert tirate[DELL_ANTICIPO] == pytest.approx(tirate[DELL_ANTICIPO + 1])    # l'anticipo della 12 no
    registro, _ = rg.fantamedie_tirate(db, ST, 12, Regole())
    assert registro[CENTROCAMPISTA_11] > registro[CENTROCAMPISTA_11 + 1]
    assert registro[DELL_ANTICIPO] == pytest.approx(registro[DELL_ANTICIPO + 1])
    assert CENTROCAMPISTA_11 in vp.squalificati(d, ST, 12)                     # espulso nella 11: squalificato nella 12


# la 12 finita: la partita del 2/11 e le altre nel suo turno, tutte giocate
TUTTA_GIOCATA = {10: _giocate(G10), 11: _giocate(G11), 12: [(ANTICIPO_LONTANO, 1)] + _giocate(G12[1:]),
                 13: _da_giocare(_sposta(G12, 7))}
GIOCANO_IL_2_11 = {DELL_ANTICIPO, DELL_ANTICIPO + 1}


def test_la_misura_non_conta_chi_ha_giocato_prima_della_scadenza(tmp_path):
    """Revisione della #966: il modello prevede la 12 con i dati fino alla scadenza (21/11). Per chi ha giocato il 2/11 sono dati dal
    futuro: il giocatore 100 prende 9 nella 11 il 6/11 e il suo atteso per il 2/11 saliva da 6,0 a 6,82. La verifica (e con lei
    l'Affidabilità) lo misurava: ora chi ha giocato una partita della giornata prima della scadenza non si misura, come il registro
    delle giornate non salva chi ha la partita già cominciata."""
    d = _dati(tmp_path, "a", TUTTA_GIOCATA, {(11, DELL_ANTICIPO): GRANDE})
    esito = verifica.verifica_giornata(d, ST, 12, Regole(), modello.Parametri())
    assert esito.n == 18                                                    # i 20 della 12 meno i due del 2/11
    prev, _, fv_vero = diario._previsti_e_veri(d, ST, 12, Regole(), modello.Parametri())     # Diario e «Quanto ci abbiamo preso»
    assert not GIOCANO_IL_2_11 & set(prev.index) and not GIOCANO_IL_2_11 & set(fv_vero) and len(fv_vero) == 18
    raccolte: list = []                                                     # gol attesi contro veri della verifica dei pacchetti
    vp._con_registro(vp._previsioni, raccolte)(d, ST, 12, Regole(), modello.Parametri())
    assert not GIOCANO_IL_2_11 & set(raccolte[0]["id"]) and len(raccolte[0]) == 18


def test_con_date_non_leggibili_vale_la_prima_come_e_scritta():
    """Una giornata le cui date non si leggono come date tiene la regola di prima (la prima data come è scritta): non «9999», che
    darebbe al modello tutti i dati, anche quelli di dopo, e toglierebbe tutta la giornata dalla misura."""
    partite = pd.DataFrame([{"id": 1, "stagione": ST, "giornata": 5, "data": "2026-10-35 15:00", "giocata": 1},
                            {"id": 2, "stagione": ST, "giornata": 5, "data": "2026-10-36 15:00", "giocata": 1}])
    assert modello.inizio_giornata(partite, ST, 5) == "2026-10-35 15:00"
    assert modello.giocate_prima(partite, ST, 5) == set()
    assert modello.inizio_giornata(partite.assign(data=None), ST, 5) == "9999"
