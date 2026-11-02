"""Regole che devono valere SEMPRE, provate con Hypothesis su rose, regole e calendari inventati ma validi.

Accanto ai test a esempi (test_formazione.py, test_turno.py): qui Hypothesis genera molti casi a caso e, se una regola salta,
riduce il caso al più piccolo che la fa saltare. Pochi esempi per test (la suite non deve rallentare); `deadline=None`
perché il primo calcolo con numpy è lento e non è un errore.
"""
import math
import sqlite3
from collections import Counter
from datetime import datetime, timedelta
from itertools import combinations

from hypothesis import HealthCheck, example, given, settings
from hypothesis import strategies as st

from fanta import avvisi, turno
from fanta import formazione as fz
from fanta.punteggio import modificatore_difesa, modulo_valido
from fanta.regole import RUOLI, Regole, modulo_in_numeri

PROVE = settings(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.too_slow])

# tutti i moduli possibili con almeno un giocatore per reparto (d + c + a = 10)
MODULI = [f"{d}-{c}-{a}" for d in range(1, 9) for c in range(1, 9) for a in range(1, 9) if d + c + a == 10]


# ---------------------------------------------------------------- generatori
@st.composite
def regole(draw) -> Regole:
    """Regole valide (Regole.problemi() vuoto): moduli, panchina e modificatore della difesa a caso."""
    r = Regole()
    r.moduli = draw(st.lists(st.sampled_from(MODULI), min_size=1, max_size=8, unique=True))
    servono = [modulo_in_numeri(m) for m in r.moduli]
    r.rosa = {"P": draw(st.integers(1, 3)),
              **{ruolo: max(n[i] for n in servono) + draw(st.integers(0, 3)) for i, ruolo in enumerate("DCA")}}
    p = r.panchina
    p.tipo = draw(st.sampled_from(["libera", "per_ruolo"]))
    p.cambio_modulo = draw(st.booleans())
    p.max_sostituzioni = draw(st.integers(0, 5))
    if draw(st.booleans()):
        p.posti = {ruolo: draw(st.integers(0, 3)) for ruolo in RUOLI}
        p.numero = sum(p.posti.values())
    else:
        p.posti, p.numero = None, draw(st.integers(0, 12))
    m = r.modificatore_difesa
    m.attivo = draw(st.booleans())
    m.min_difensori = draw(st.integers(1, 5))
    m.soglie = draw(st.lists(st.tuples(st.floats(4, 9), st.floats(-3, 8)).map(list), max_size=4))
    r.voto_senza_sostituto = draw(st.none() | st.floats(0, 6))
    assert r.problemi() == [], r.problemi()
    return r


def giocatore(id_: int, ruolo: str):
    return st.builds(fz.Giocatore, st.just(id_), st.just(f"g{id_}"), st.just(ruolo),
                     st.floats(0, 1), st.floats(-5, 25), st.floats(3, 10))


@st.composite
def rosa_e_regole(draw):
    """Regole e una rosa che le rispetta (tanti giocatori per ruolo quanti ne chiede la lega)."""
    r = draw(regole())
    rosa, id_ = [], 1
    for ruolo in RUOLI:
        for _ in range(r.rosa[ruolo]):
            rosa.append(draw(giocatore(id_, ruolo)))
            id_ += 1
    return rosa, r


@st.composite
def formazione_schierata(draw):
    """Regole, 11 titolari con un modulo ammesso, una panchina e chi prende voto."""
    rosa, r = draw(rosa_e_regole())
    d, c, a = modulo_in_numeri(draw(st.sampled_from(r.moduli)))
    per_ruolo = {ruolo: [g for g in rosa if g.ruolo == ruolo] for ruolo in RUOLI}
    titolari = [g for ruolo, n in zip(RUOLI, (1, d, c, a)) for g in draw(st.permutations(per_ruolo[ruolo]))[:n]]
    ids = {g.id for g in titolari}
    resto = [g for g in rosa if g.id not in ids]
    panchina = draw(st.permutations(resto))[:draw(st.integers(0, len(resto)))]
    gioca = {g.id: draw(st.booleans()) for g in rosa}
    return titolari, panchina, gioca, r


def _conta(giocatori) -> Counter:
    return Counter(g.ruolo for g in giocatori)


# ---------------------------------------------------------------- formazione migliore
@PROVE
@given(rosa_e_regole(), st.booleans())
def test_la_formazione_migliore_usa_un_modulo_ammesso_e_rispetta_i_ruoli(caso, ricerca):
    rosa, r = caso
    f = fz.migliore(rosa, r, simulazioni=40, ricerca=ricerca)
    d, c, a = modulo_in_numeri(f.modulo)
    assert f.modulo in r.moduli and modulo_valido(d, c, a, r)
    assert _conta(f.titolari) == Counter({"P": 1, "D": d, "C": c, "A": a}) - Counter()
    ids_rosa = {g.id for g in rosa}
    tit, pan = [g.id for g in f.titolari], [g.id for g in f.panchina]
    assert len(tit) == 11 and len(set(tit + pan)) == len(tit) + len(pan)      # nessuno due volte
    assert set(tit + pan) <= ids_rosa
    assert len(pan) <= r.panchina.numero
    if r.panchina.posti is not None:
        assert all(n <= r.panchina.posti[ruolo] for ruolo, n in _conta(f.panchina).items())
    assert math.isfinite(f.atteso) and math.isfinite(f.dev)
    assert all(x.modulo in r.moduli for x in f.tutte)


# ---------------------------------------------------------------- sostituzioni
@PROVE
@given(formazione_schierata())
def test_le_sostituzioni_non_superano_11_e_non_fanno_entrare_ruoli_non_ammessi(caso):
    titolari, panchina, gioca, r = caso
    va, scoperti = fz.chi_va_a_punteggio(titolari, panchina, gioca, r)
    ids = [g.id for g in va]
    assert len(va) <= 11 and len(set(ids)) == len(ids)
    assert all(gioca[i] for i in ids)                                       # a punteggio solo chi prende voto
    ids_tit = {t.id for t in titolari}
    entrati = [g for g in va if g.id not in ids_tit]
    assert {g.id for g in entrati} <= {b.id for b in panchina}
    assert [t.id for t in titolari if gioca[t.id]] == ids[:len(ids) - len(entrati)]   # i titolari con voto restano
    mancanti = [t for t in titolari if not gioca[t.id]]
    assert len(entrati) <= r.panchina.max_sostituzioni and len(entrati) + scoperti == len(mancanti)
    assert _conta(va)["P"] <= 1                                              # in porta solo un portiere
    if not r.panchina.cambio_modulo:                                         # senza cambio modulo: stesso ruolo di chi esce
        assert all(_conta(entrati)[ruolo] <= _conta(mancanti)[ruolo] for ruolo in RUOLI)
    # il modulo che ne esce (contando al loro posto i titolari rimasti senza sostituto) è sempre uno di quelli ammessi
    assert any(_modulo_ammesso(_conta(va) + _conta(scoperti_), r)
               for scoperti_ in combinations(mancanti, scoperti))


def _modulo_ammesso(conta: Counter, r: Regole) -> bool:
    return conta["P"] == 1 and modulo_valido(conta["D"], conta["C"], conta["A"], r)


# ---------------------------------------------------------------- punteggio e modificatore della difesa
@PROVE
@given(formazione_schierata(), st.data())
def test_il_punteggio_con_il_modificatore_non_va_in_errore_e_non_da_nan(caso, data):
    titolari, panchina, gioca, r = caso
    r.modificatore_difesa.attivo = True
    numeri = st.floats(-10, 30, allow_nan=False, allow_infinity=False)
    fv = {g.id: data.draw(numeri) for g in titolari + panchina}
    voto = {g.id: data.draw(st.floats(0, 10)) for g in titolari + panchina}
    punti = fz.punteggio(titolari, panchina, gioca, fv, voto, r)
    assert math.isfinite(punti)


@PROVE
@given(regole(), st.none() | st.floats(0, 10), st.lists(st.floats(0, 10), max_size=8))
def test_il_modificatore_della_difesa_e_sempre_uno_dei_bonus_previsti(r, portiere, difensori):
    r.modificatore_difesa.attivo = True
    bonus = modificatore_difesa(portiere, difensori, r)
    assert math.isfinite(bonus)
    assert bonus == 0.0 or bonus in [valore for _, valore in r.modificatore_difesa.soglie]


@settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(rosa_e_regole())
def test_il_calcolo_veloce_da_gli_stessi_punti_di_quello_semplice(caso):
    """Il Valutatore (sostituzioni e modificatore per tutte le simulazioni insieme) contro `punteggio`, simulazione per simulazione."""
    rosa, r = caso
    val = fz.Valutatore(rosa, r, simulazioni=30)
    f = fz.migliore(rosa, r, simulazioni=30, ricerca=False, valutatore=val)
    veloci = val._punti(f.titolari, f.panchina)
    fv = {g.id: g.mu for g in rosa}
    for s in range(30):
        gioca = {g.id: bool(val.gioca[s, val.indice[g.id]]) for g in rosa}
        voto = {g.id: float(val.voti[s, val.indice[g.id]]) for g in rosa}
        assert math.isclose(veloci[s], fz.punteggio(f.titolari, f.panchina, gioca, fv, voto, r), abs_tol=1e-9)


# ---------------------------------------------------------------- turno e scadenza
# Date vicine fra loro (tre settimane, orari tipici della Serie A): così capitano gruppi, anticipi e recuperi.
INIZIO_STAGIONE = datetime(2026, 8, 21, 0, 0)
ORARI = [timedelta(hours=h, minutes=m) for h, m in ((12, 30), (15, 0), (18, 0), (20, 45))]
quando = st.builds(lambda giorno, ora: INIZIO_STAGIONE + timedelta(days=giorno) + ora, st.integers(0, 20), st.sampled_from(ORARI))
# una giornata vera ha le partite a gruppi (lo stesso giorno e orario): fino a 10 partite in pochi gruppi, qualcuna senza data
giornata = st.lists(st.tuples(st.none() | quando, st.integers(1, 5)), min_size=1, max_size=4).map(
    lambda gruppi: [d for d, n in gruppi for _ in range(n)][:10])


# calendario con chi ha già giocato: (data, giocata) per le partite con la data
calendario = st.lists(st.tuples(quando, st.integers(1, 5), st.booleans()), min_size=1, max_size=4).map(
    lambda gruppi: [(d, g) for d, n, g in gruppi for _ in range(n)][:10])
VENERDI, MERCOLEDI = datetime(2026, 8, 21, 12, 30), datetime(2026, 8, 26, 12, 30)


@PROVE
@given(giornata)
def test_inizio_del_turno_coerente(date):
    vere = [x for x in date if x is not None]
    i = turno.inizio(date)
    if not vere:
        assert i is None
        return
    assert i in vere and turno.nel_turno(i, i)
    assert turno.inizio(list(reversed(date))) == i                          # l'ordine delle partite non conta


@PROVE
@given(giornata)
@example([VENERDI] * 3 + [MERCOLEDI] * 4)        # il controesempio trovato da Hypothesis (difetto #139, corretto)
def test_mai_piu_di_max_anticipi(date):
    """Più di MAX_ANTICIPI partite «anticipate» non sono anticipi ma un turno diviso (fanta/turno.py)."""
    i = turno.inizio(date)
    assert sum(turno.anticipo(x, i) for x in date if x is not None) <= turno.MAX_ANTICIPI


@PROVE
@given(calendario, st.integers(0, 720))
@example([(VENERDI, True), (VENERDI + timedelta(days=7), False), (VENERDI + timedelta(days=7), False)], 0)   # giocata 7 giorni prima
def test_la_scadenza_viene_prima_del_turno_e_non_la_fissa_un_anticipo(partite, minuti):
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE partite (stagione TEXT, giornata INT, data TEXT, giocata INT)")
    db.executemany("INSERT INTO partite VALUES ('2026-27', 9, ?, ?)",
                   [(d.strftime("%Y-%m-%d %H:%M"), int(g)) for d, g in partite])
    prima = avvisi.prima_partita(db, "2026-27", 9)
    inizio_turno = turno.inizio(d for d, _ in partite)
    assert prima is not None and prima <= inizio_turno and not turno.anticipo(prima, inizio_turno)
    # la scadenza la fissa la prima partita che conta: tutte quelle del turno e quelle già giocate prima (che non siano anticipi)
    assert all(prima <= d for d, giocata in partite if turno.nel_turno(d, inizio_turno)
               or (giocata and d < inizio_turno and not turno.anticipo(d, inizio_turno)))
    r = Regole()
    r.scadenza_minuti = minuti
    scadenza = avvisi.scadenza(prima, r)
    assert scadenza == prima - timedelta(minutes=minuti) and scadenza <= inizio_turno
