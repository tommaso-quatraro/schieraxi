"""Squalificati e diffidati calcolati dai cartellini dei voti (fanta/squalifiche.py, #640): soglie delle ammonizioni,
espulsione, conto incerto dopo un rosso, rinvii e recuperi, cambio di squadra, inizio stagione; e lo strumento che lo misura
sull'archivio (prove/misura_squalifiche.py). Solo dati inventati."""
import importlib.util
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from fanta import archivio
from fanta import squalifiche as sq

RADICE = Path(__file__).resolve().parent.parent
ST = "2026-27"
PRIMA = datetime(2026, 8, 22, 15, 0)          # sabato della prima giornata; poi una giornata a settimana
ADESSO = datetime(2027, 6, 1, 12, 0)          # a stagione finita: dove conta l'ora (partite non giocate) il test la fissa


def ora(giornata, giorni=0, ore=0):
    return PRIMA + timedelta(days=7 * (giornata - 1) + giorni, hours=ore)


def quando(giornata, giorni=0, ore=0):
    return ora(giornata, giorni, ore).strftime("%Y-%m-%d %H:%M")


def partita(giornata, casa="alfa", trasferta="beta", data=None, giocata=True, stagione=ST):
    return {"stagione": stagione, "giornata": giornata, "data": data, "casa": casa, "trasferta": trasferta,
            "giocata": int(giocata)}


def calendario(giocate, casa="alfa", trasferta="beta", stagione=ST, giorni=0, salta=()):
    """38 partite casa-trasferta, una a settimana; giocate le prime `giocate`. `salta`: giornate da non mettere."""
    return [partita(g, casa, trasferta, quando(g, giorni), g <= giocate, stagione) for g in range(1, 39) if g not in salta]


def cartellino(cid, giornata, squadra="alfa", giallo=0, rosso=0, stagione=ST):
    return {"stagione": stagione, "giornata": giornata, "calciatore_id": cid, "squadra": squadra,
            "ammonizioni": giallo, "espulsioni": rosso}


def gialli(cid, giornate, squadra="alfa", stagione=ST):
    return [cartellino(cid, g, squadra, giallo=1, stagione=stagione) for g in giornate]


# Gli esiti sono (squalificato, diffidato); chi non è né l'uno né l'altro non c'è.
def test_quinta_ammonizione_squalificato_alla_prossima_quarta_diffidato():
    carte = gialli(1, [1, 2, 3, 4, 5]) + gialli(2, [1, 2, 3, 4]) + gialli(3, [1, 2, 3])
    esito = sq.calcola(carte, calendario(5), ST, 6, {1: "alfa", 2: "alfa", 3: "alfa"}, ADESSO)
    assert esito == {1: (True, False), 2: (False, True)}


@pytest.mark.parametrize("n, atteso", [
    (4, (False, True)), (5, (True, False)), (6, None), (8, None), (9, (False, True)), (10, (True, False)), (11, None),
    (13, (False, True)), (14, (True, False)), (15, None), (16, (False, True)), (17, (True, False)), (18, (False, True)),
    (19, (True, True)), (20, (True, True)), (21, (True, True))])
def test_soglie_delle_ammonizioni(n, atteso):
    """Codice di giustizia sportiva, art. 9 comma 5: squalifica alla quinta ammonizione, poi dopo altre cinque (10), quattro
    (14), tre (17), due (19) e a ogni ammonizione in più. Dalla diciannovesima è squalificato e resta diffidato."""
    esito = sq.calcola(gialli(1, range(1, n + 1)), calendario(n), ST, n + 1, {1: "alfa"}, ADESSO)
    assert esito.get(1) == atteso


def test_espulsione_squalificato_alla_prossima_e_poi_basta():
    carte = [cartellino(1, 5, rosso=1)]
    assert sq.calcola(carte, calendario(5), ST, 6, {1: "alfa"}, ADESSO) == {1: (True, False)}
    assert sq.calcola(carte, calendario(6), ST, 7, {1: "alfa"}, ADESSO) == {}          # una giornata: le più lunghe non si indovinano


def test_squalifica_per_ammonizioni_scontata_non_resta_una_seconda_giornata():
    assert sq.calcola(gialli(1, [1, 2, 3, 4, 5]), calendario(6), ST, 7, {1: "alfa"}, ADESSO) == {}


def test_dopo_un_rosso_il_conto_delle_ammonizioni_non_e_certo():
    """Nei voti un giallo seguito dal rosso nella stessa partita arriva come solo rosso: dopo un'espulsione le ammonizioni
    possono essere quelle contate o una in più. Niente squalifica per somma e niente diffida."""
    con_rosso = gialli(1, [1, 2, 3, 4]) + [cartellino(1, 5, rosso=1)]
    assert sq.calcola(con_rosso, calendario(5), ST, 6, {1: "alfa"}, ADESSO) == {1: (True, False)}      # il rosso è certo, la diffida no
    dopo = con_rosso + gialli(1, [7])                                                          # rosso scontato alla 6
    assert sq.calcola(dopo, calendario(7), ST, 8, {1: "alfa"}, ADESSO) == {}
    assert sq.calcola(gialli(2, [1, 2, 3, 4, 7]), calendario(7), ST, 8, {2: "alfa"}, ADESSO) == {2: (True, False)}     # senza rosso sì


def test_partita_rinviata_la_squalifica_vale_ancora_alla_giornata_dopo():
    """Quinta ammonizione alla 5; la partita della 6 è rinviata ed è rimasta con la data vecchia (le altre squadre l'hanno
    giocata). Per numero di giornata la squalifica sarebbe scontata alla 6: invece vale alla 7, la prima che la squadra gioca."""
    partite = calendario(5) + calendario(6, "gamma", "delta", giorni=1)
    assert sq.calcola(gialli(1, [1, 2, 3, 4, 5]), partite, ST, 7, {1: "alfa"}, ADESSO) == {1: (True, False)}


@pytest.mark.parametrize("dopo_ore, atteso", [
    (-24, {}),                   # in programma: la squalifica si sconterà lì
    (1, {}),                     # in corso: si sta scontando
    (11, {}),                    # finita da poco, non ancora segnata come giocata
    (13, {1: (True, False)}),    # passata da più di mezza giornata e non giocata: rinviata
    (72, {1: (True, False)})])
def test_partita_non_giocata_in_programma_in_corso_o_rinviata(dopo_ore, atteso):
    """Quinta ammonizione alla 5; la partita della 6 è l'ultima in calendario della 6 (le altre si sono giocate prima) e
    nell'archivio non è giocata. Prima, durante e fino a mezza giornata dopo l'inizio sconta la squalifica; poi è rinviata:
    non la sconta, e alla 7 resta squalificato. Nessuna partita giocata dopo di lei lo dice: lo dice solo l'ora."""
    partite = calendario(5) + calendario(6, "gamma", "delta", giorni=-1)
    assert sq.calcola(gialli(1, [1, 2, 3, 4, 5]), partite, ST, 7, {1: "alfa"}, ora(6, ore=dopo_ore)) == atteso


def test_recupero_giocato_prima_della_giornata_dopo_sconta_la_squalifica():
    """Quinta ammonizione alla 6; il mercoledì la squadra recupera la partita della giornata 3: la squalifica si sconta lì."""
    partite = calendario(6, salta=(3,)) + [partita(3, data=quando(6, giorni=4))]
    assert sq.calcola(gialli(1, [1, 2, 4, 5, 6]), partite, ST, 7, {1: "alfa"}, ADESSO) == {}


def test_ammonizione_presa_nel_recupero_conta_per_data():
    """La quinta ammonizione arriva nel recupero della giornata 3, giocato dopo la 6: squalificato alla 7. Per numero di
    giornata l'ultimo cartellino sarebbe quello della 5 e la squalifica risulterebbe scontata alla 6."""
    partite = calendario(6, salta=(3,)) + [partita(3, data=quando(6, giorni=4))]
    assert sq.calcola(gialli(1, [1, 2, 4, 5, 3]), partite, ST, 7, {1: "alfa"}, ADESSO) == {1: (True, False)}


def test_ultimo_cartellino_per_data_anche_nell_ordine_dell_archivio():
    """I cartellini escono dall'archivio in ordine di giornata. La partita della 3 è recuperata il mercoledì dopo la 5 e la
    quinta ammonizione arriva lì: l'ultimo cartellino è quello della 3, non quello della 5 in fondo alla lista. Squalificato
    alla 6; contando dalla 5, la squalifica risulterebbe scontata nel recupero."""
    partite = calendario(5, salta=(3,)) + [partita(3, data=quando(5, giorni=4))]
    assert sq.calcola(gialli(1, [1, 2, 3, 4, 5]), partite, ST, 6, {1: "alfa"}, ADESSO) == {1: (True, False)}


def test_recupero_in_programma_prima_della_giornata_la_squalifica_si_sconta_li():
    """Quinta ammonizione alla 6, l'ultima giocata; è il lunedì dopo. Prima della 7 la squadra ha in programma il recupero
    della giornata 3 (mercoledì): la squalifica si sconterà lì, quindi alla 7 gioca."""
    partite = calendario(6, salta=(3,)) + [partita(3, data=quando(6, giorni=4), giocata=False)]
    assert sq.calcola(gialli(1, [1, 2, 4, 5, 6]), partite, ST, 7, {1: "alfa"}, ora(6, giorni=2)) == {}


def test_cambio_squadra_il_conto_e_la_squalifica_seguono_il_giocatore():
    partite = calendario(5) + calendario(5, "gamma", "delta", giorni=1)
    tre_e_due = gialli(1, [1, 2, 3], "alfa") + gialli(1, [4, 5], "gamma")
    assert sq.calcola(tre_e_due, partite, ST, 6, {1: "gamma"}, ADESSO) == {1: (True, False)}
    # la quinta con la squadra vecchia nella sua ultima partita: la sconta con la nuova
    assert sq.calcola(gialli(2, [1, 2, 3, 4, 5], "alfa"), partite, ST, 6, {2: "gamma"}, ADESSO) == {2: (True, False)}


def test_inizio_stagione_il_conto_riparte_da_zero():
    """Art. 19 comma 9: le ammonizioni che non hanno portato a una squalifica decadono a fine stagione. Quattro nelle prime
    giornate della stagione prima e una alla 5 di questa: alla 6 né squalificato né diffidato. (Gialli della stagione prima
    alle stesse giornate di quelli di questa: se si contassero, cadrebbero prima della partita chiesta.)"""
    partite = calendario(38, stagione="2025-26", giorni=-364) + calendario(5)
    carte = gialli(1, [1, 2, 3, 4], stagione="2025-26") + gialli(1, [5])
    assert sq.calcola(carte, partite, ST, 6, {1: "alfa"}, ADESSO) == {}


def test_le_partite_di_un_altra_stagione_non_scontano_la_squalifica():
    """Quinta ammonizione alla 5 e partita della 6 rinviata: squalificato alla 7. Una partita giocata della stagione prima,
    senza data (si confronta per numero di giornata: cade fra la 5 e la 7), non la sconta."""
    partite = [partita(6, stagione="2025-26")] + calendario(5) + calendario(6, "gamma", "delta", giorni=1)
    assert sq.calcola(gialli(1, [1, 2, 3, 4, 5]), partite, ST, 7, {1: "alfa"}, ADESSO) == {1: (True, False)}


def test_contano_solo_cartellini_e_partite_di_prima_della_partita():
    """Sul passato (misure): per la giornata 5 non conta il giallo della 5; per la 6 la squalifica vale anche se oggi la
    squadra ha già giocato la 6 e le giornate dopo."""
    carte = gialli(1, [1, 2, 3, 4, 5])
    assert sq.calcola(carte, calendario(10), ST, 5, {1: "alfa"}, ADESSO) == {1: (False, True)}
    assert sq.calcola(carte, calendario(10), ST, 6, {1: "alfa"}, ADESSO) == {1: (True, False)}


def test_calendario_senza_date_vale_il_numero_di_giornata():
    def senza_date(giocate):
        return [partita(g, giocata=g <= giocate) for g in range(1, 39)]
    carte = gialli(1, [1, 2, 3, 4, 5])
    assert sq.calcola(carte, senza_date(5), ST, 6, {1: "alfa"}, ADESSO) == {1: (True, False)}
    assert sq.calcola(carte, senza_date(6), ST, 7, {1: "alfa"}, ADESSO) == {}


def test_senza_squadra_o_senza_partita_nella_giornata_nessun_esito():
    carte = gialli(1, [1, 2, 3, 4, 5]) + gialli(2, [1, 2, 3, 4, 5])
    assert sq.calcola(carte, calendario(5), ST, 6, {1: "zeta"}, ADESSO) == {}        # 1: la sua squadra non gioca; 2: non è in elenco


# ---------------------------------------------------------------- la misura sull'archivio (prove/misura_squalifiche.py)
def _strumento():
    spec = importlib.util.spec_from_file_location("misura_squalifiche", RADICE / "prove" / "misura_squalifiche.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _archivio_di_prova(tmp_path):
    """Sei giornate giocate di alfa-beta; gamma-delta ha giocato anche la 7, alfa-beta no (rinviata). Presenze e cartellini:
    1: giallo dalla 1 alla 5, alla 6 non c'è (squalificato vero);    2: rosso alla 5, alla 6 è in campo (falso);
    3: giallo dalla 1 alla 4, sempre in campo (diffidato);            4: giallo dalla 2 alla 6 (squalificato alla 7, non giocata)."""
    db = archivio.apri(tmp_path / "prova.sqlite")
    archivio.inserisci(db, "partite", [{"id": g, **partita(g, data=quando(g), giocata=g <= 6)} for g in range(1, 39)]
                       + [{"id": 100 + g, **partita(g, "gamma", "delta", quando(g), g <= 7)} for g in range(1, 39)])
    presenze = {1: range(1, 6), 2: range(1, 7), 3: range(1, 7), 4: range(1, 7)}
    gialli_di = {1: {1, 2, 3, 4, 5}, 2: set(), 3: {1, 2, 3, 4}, 4: {2, 3, 4, 5, 6}}
    archivio.inserisci(db, "voti", [
        {"stagione": ST, "giornata": g, "calciatore_id": cid, "squadra": "alfa", "voto_red": 6.0,
         "ammonizioni": int(g in gialli_di[cid]), "espulsioni": int(cid == 2 and g == 5)}
        for cid, giornate in presenze.items() for g in giornate])
    db.commit()
    return db


def test_misura_conta_segnalati_e_falsi_dal_tabellino(tmp_path):
    """Il 4, squalificato per la 7 che alfa non ha giocato, non è né giusto né falso: si conta a parte."""
    db = _archivio_di_prova(tmp_path)
    assert _strumento().misura(db, ST, ADESSO) == {
        "giornate": 6, "segnalati": 2, "falsi": 1,
        "per_espulsione": 1, "falsi_per_espulsione": 1, "per_somma": 1, "falsi_per_somma": 0, "non_giocate": 1}


def test_misura_confronta_con_l_elenco_della_fonte(tmp_path):
    """La fonte per la giornata 7: squalificati 4 e 5 (il 5 noi non lo vediamo), diffidati 3 e 6 (il 6 noi non lo vediamo)."""
    db = _archivio_di_prova(tmp_path)
    archivio.inserisci(db, "probabili", [
        {"stagione": ST, "giornata": 7, "fonte": "fantacalcio", "calciatore_id": cid, "squadra": "alfa", "stato": stato,
         "diffidato": diffidato}
        for cid, stato, diffidato in ((4, "squalificato", 0), (5, "squalificato", 0), (3, "titolare", 1), (6, "panchina", 1),
                                      (1, "titolare", 0))])
    db.commit()
    assert _strumento().confronto_con_la_fonte(db, ST, ADESSO) == [{
        "giornata": 7,
        "squalificati_fonte": 2, "squalificati_nostri": 1, "squalificati_comuni": 1,
        "diffidati_fonte": 2, "diffidati_nostri": 1, "diffidati_comuni": 1}]
