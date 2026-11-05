r"""Quanto cambia la consigliata con un piccolo aggiornamento dei dati: prima (sempre la migliore) e con il consiglio stabile (#335).

Come la misura della proposta (docs/superpowers/specs/2026-11-05-consiglio-giusto-proposta.md, §1, «piccolo aggiornamento»): per
ogni squadra della lega d'esempio con almeno 20 giocatori con previsione si calcola la consigliata; poi, per ogni prova, ogni
«gioca N%» si sposta a caso di circa 3 punti e ogni fantavoto atteso di circa 0,1, e si ricalcola la consigliata senza e con
`consigli.stabile`. Il guadagno è quanto vale la nuova in più della vecchia, tutte e due con i dati ritoccati.
Legge l'archivio locale (dati/fanta.sqlite) e la lega d'esempio; non scrive niente.

Uso: .venv\Scripts\python.exe prove\misura_stabilita.py [--giornata 9] [--prove 3] [--simulazioni 600] [--seme 1]
"""
import argparse
import statistics
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")

import numpy as np  # noqa: E402

from fanta import archivio, consigli, lega  # noqa: E402
from fanta import formazione as fz  # noqa: E402
from fanta.percorsi import RADICE  # noqa: E402
from fanta.regole import carica  # noqa: E402

ESEMPIO = RADICE / "lega" / "esempio"


def ritocca(prev, rng):
    p = prev.copy()
    p["p_voto"] = (p["p_voto"] + rng.normal(0, 0.03, len(p))).clip(0, 1)
    p["mu"] = p["mu"] + rng.normal(0, 0.1, len(p))
    return p


def valore(prev, s, regole, simulazioni, titolari) -> float:
    """Punti attesi di questi titolari con la panchina del sistema, con i dati `prev`."""
    rosa = consigli._rosa(s, prev)
    per_id = {g.id: g for g in rosa}
    tit = [per_id[i] for i in titolari]
    return fz.Valutatore(rosa, regole, simulazioni).atteso(tit, fz._panchina(rosa, tit, regole))


def main() -> None:
    a = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    a.add_argument("--giornata", type=int, default=9)
    a.add_argument("--prove", type=int, default=3)
    a.add_argument("--simulazioni", type=int, default=600)
    a.add_argument("--seme", type=int, default=1)
    a = a.parse_args()
    regole, rose = carica(ESEMPIO / "regole.json"), lega.carica(ESEMPIO / "rose.json")
    db = archivio.apri()
    prev, giornata, con_probabili = consigli.previsioni(db, regole, a.giornata)
    rng = np.random.default_rng(a.seme)
    esiti = {"sempre la migliore": [], "consiglio stabile": []}          # per prova: (titolari cambiati, guadagno)
    for s in rose.squadre:
        if len(consigli._rosa(s, prev)) < 20:
            continue
        f0 = consigli._calcola_formazione(s, prev, giornata, con_probabili, regole, a.simulazioni)
        prima = {"titolari": [g["id"] for g in f0["titolari"]], "panchina": [g["id"] for g in f0["panchina"]]}
        for _ in range(a.prove):
            pk = ritocca(prev, rng)
            migliore = consigli._calcola_formazione(s, pk, giornata, con_probabili, regole, a.simulazioni)
            stabile = consigli.stabile(migliore, prima, pk, s, regole, a.simulazioni)
            for nome, f in (("sempre la migliore", migliore), ("consiglio stabile", stabile)):
                nuovi = [g["id"] for g in f["titolari"]]
                cambiati = len(set(prima["titolari"]) - set(nuovi))
                guadagno = (valore(pk, s, regole, a.simulazioni, nuovi) - valore(pk, s, regole, a.simulazioni, prima["titolari"])
                            if cambiati else 0.0)
                esiti[nome].append((cambiati, guadagno))
    print(f"Giornata {giornata} ({'con' if con_probabili else 'senza'} probabili), {a.prove} ritocchi per squadra, "
          f"{a.simulazioni} simulazioni, soglia {consigli.SOGLIA_CAMBIO_PUNTI:g} punto")
    for nome, righe in esiti.items():
        n = len(righe)
        uno, tre = sum(c >= 1 for c, _ in righe), sum(c >= 3 for c, _ in righe)
        guadagni = [g for c, g in righe if c]
        testo = (f"mediana {statistics.median(guadagni):+.2f}, da {min(guadagni):+.2f} a {max(guadagni):+.2f}" if guadagni
                 else "nessun cambio")
        sotto = sum(g < consigli.SOGLIA_CAMBIO_PUNTI for g in guadagni)
        print(f"- {nome}: {n} prove; almeno 1 titolare cambiato in {uno} ({uno / n:.0%}), 3 o più in {tre} ({tre / n:.0%}); "
              f"quanto vale la nuova quando cambia: {testo}; cambi sotto la soglia: {sotto}")


if __name__ == "__main__":
    main()
