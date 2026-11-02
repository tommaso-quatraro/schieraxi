r"""Dove va il tempo quando si chiede la formazione? Uso: .venv\Scripts\python.exe prove\misura_tempi.py [--profilo]"""
import cProfile, pstats, sys, time
sys.stdout.reconfigure(encoding="utf-8"); sys.path.insert(0, ".")
from fanta import archivio, consigli, lega, formazione as fz
from fanta.percorsi import CARTELLA_LEGA
from fanta.regole import carica

R = carica(CARTELLA_LEGA / "regole.json"); rose = lega.carica(CARTELLA_LEGA / "rose.json")
db = archivio.apri()


def t(nome, f):
    a = time.perf_counter(); r = f(); print(f"{nome:42s} {time.perf_counter() - a:6.2f} s"); return r


t("carica dati (consigli.dati)", lambda: consigli.dati(db))
prev, g, _ = t("previsioni (modello, tutti i giocatori)", lambda: consigli.previsioni(db, R))
s = rose.squadra(rose.mia_squadra)
rosa = [fz.Giocatore(int(i), prev.at[i, "nome"], prev.at[i, "ruolo"], float(prev.at[i, "p_voto"]), float(prev.at[i, "mu"]),
                     float(prev.at[i, "mu_voto"])) for i in (x.id for x in s.giocatori) if i in prev.index]
t("scelta formazione (600 simulazioni)", lambda: fz.migliore(rosa, R, 600))
t("formazione completa (API)", lambda: consigli.formazione(db, R, rose))
t("valori scambi (5 giornate)", lambda: consigli.valori_scambi(db, R))
if "--profilo" in sys.argv:
    consigli._cache.clear()
    p = cProfile.Profile(); p.enable(); consigli.previsioni(db, R); p.disable()
    pstats.Stats(p).sort_stats("cumulative").print_stats(14)
    p = cProfile.Profile(); p.enable(); fz.migliore(rosa, R, 600); p.disable()
    pstats.Stats(p).sort_stats("cumulative").print_stats(12)
