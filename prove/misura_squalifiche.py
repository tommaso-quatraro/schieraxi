r"""Quanto è giusta la regola di fanta/squalifiche.py (#640), misurata sull'archivio locale.

Per ogni giornata già giocata si calcola chi risulta squalificato usando solo le partite di prima, poi si guarda se quel
giocatore è nel tabellino della partita: se c'è, la segnalazione era falsa (se la squadra quella partita non l'ha giocata, il
segnalato si conta a parte). Il tasso dei falsi è un minimo: chi è segnalato a torto ma poi non gioca per un altro motivo
(infortunio, scelta dell'allenatore) conta come giusto. Dove l'archivio ha l'elenco della fonte (tabella
`probabili`, l'ultima lettura della giornata) si confrontano anche squalificati e diffidati con quell'elenco.
La squadra di un giocatore è quella della sua ultima riga dei voti prima della partita. L'ora usata è quella vera, al momento
della misura: sulle giornate passate una partita non giocata è sempre rinviata.

Apre l'archivio in sola lettura e stampa solo numeri: nessun nome di giocatore o di squadra.

Uso: .venv\Scripts\python.exe prove\misura_squalifiche.py [archivio.sqlite]      (senza argomento: dati\fanta.sqlite)
"""
from __future__ import annotations

import sqlite3
import sys
from datetime import datetime
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE))

from fanta import squalifiche  # noqa: E402

_PARTITE = ("stagione", "giornata", "data", "casa", "trasferta", "giocata")
_VOTI = ("stagione", "giornata", "calciatore_id", "squadra", "ammonizioni", "espulsioni")


def _righe(db: sqlite3.Connection, tabella: str, colonne: tuple[str, ...], stagione: str) -> list[dict]:
    sql = f"SELECT {', '.join(colonne)} FROM {tabella} WHERE stagione = ?"          # nomi scritti qui sopra, mai dai dati
    return [dict(zip(colonne, r)) for r in db.execute(sql, (stagione,))]


def _squadre(voti: list[dict], partite: list[dict], giornata: int) -> dict[int, str]:
    """La squadra di ogni giocatore alla `giornata`: quella della sua ultima riga dei voti prima di quella partita."""
    quando = {(p["giornata"], s): (p["data"] or "", p["giornata"]) for p in partite for s in (p["casa"], p["trasferta"])}
    ultima: dict[int, tuple] = {}
    for v in voti:
        meta = quando.get((giornata, v["squadra"]))
        q = quando.get((v["giornata"], v["squadra"]), ("", v["giornata"]))
        if meta is None or not q < meta:
            continue
        if v["calciatore_id"] not in ultima or q > ultima[v["calciatore_id"]][0]:
            ultima[v["calciatore_id"]] = (q, v["squadra"])
    return {cid: squadra for cid, (_, squadra) in ultima.items()}


def misura(db: sqlite3.Connection, stagione: str, adesso: datetime) -> dict[str, int]:
    """Sulle giornate giocate dalla seconda in poi: quanti segnalati come squalificati (per espulsione, per somma di
    ammonizioni) e quanti di loro erano poi nel tabellino della partita (falsi). Chi è segnalato per una partita che la sua
    squadra non ha giocato (rinviata) non è né giusto né falso: si conta a parte, in `non_giocate`."""
    partite = _righe(db, "partite", _PARTITE, stagione)
    voti = _righe(db, "voti", _VOTI, stagione)
    rossi = [v for v in voti if v["espulsioni"]]
    giocata = {(p["giornata"], s): bool(p["giocata"]) for p in partite for s in (p["casa"], p["trasferta"])}
    nel_tabellino: dict[int, set[int]] = {}
    for v in voti:
        nel_tabellino.setdefault(v["giornata"], set()).add(v["calciatore_id"])
    ultima = max((g for (g, _), fatta in giocata.items() if fatta), default=0)
    conti = dict.fromkeys(("giornate", "segnalati", "falsi", "per_espulsione", "falsi_per_espulsione", "per_somma",
                           "falsi_per_somma", "non_giocate"), 0)
    for g in range(2, ultima + 1):
        conti["giornate"] += 1
        squadre = _squadre(voti, partite, g)
        per_rosso = squalifiche.calcola(rossi, partite, stagione, g, squadre, adesso)
        for cid, stato in squalifiche.calcola(voti, partite, stagione, g, squadre, adesso).items():
            if not stato.squalificato:
                continue
            if not giocata.get((g, squadre[cid])):
                conti["non_giocate"] += 1
                continue
            motivo = "per_espulsione" if cid in per_rosso else "per_somma"
            falso = cid in nel_tabellino.get(g, set())
            conti["segnalati"] += 1
            conti[motivo] += 1
            conti["falsi"] += falso
            conti["falsi_" + motivo] += falso
    return conti


def confronto_con_la_fonte(db: sqlite3.Connection, stagione: str, adesso: datetime) -> list[dict[str, int]]:
    """Per ogni giornata con le probabili in archivio: squalificati e diffidati della fonte, nostri e in comune."""
    partite = _righe(db, "partite", _PARTITE, stagione)
    voti = _righe(db, "voti", _VOTI, stagione)
    righe = []
    giornate = [g for (g,) in db.execute("SELECT DISTINCT giornata FROM probabili WHERE stagione = ? AND fonte = 'fantacalcio' "
                                         "ORDER BY giornata", (stagione,))]
    for g in giornate:
        fonte = db.execute("SELECT calciatore_id, stato, diffidato FROM probabili WHERE stagione = ? AND giornata = ? "
                           "AND fonte = 'fantacalcio'", (stagione, g)).fetchall()
        fuori_fonte = {cid for cid, stato, _ in fonte if stato == "squalificato"}
        diffidati_fonte = {cid for cid, _, diffidato in fonte if diffidato}
        nostri = squalifiche.calcola(voti, partite, stagione, g, _squadre(voti, partite, g), adesso)
        fuori_nostri = {cid for cid, stato in nostri.items() if stato.squalificato}
        diffidati_nostri = {cid for cid, stato in nostri.items() if stato.diffidato}
        righe.append({
            "giornata": g,
            "squalificati_fonte": len(fuori_fonte), "squalificati_nostri": len(fuori_nostri),
            "squalificati_comuni": len(fuori_fonte & fuori_nostri),
            "diffidati_fonte": len(diffidati_fonte), "diffidati_nostri": len(diffidati_nostri),
            "diffidati_comuni": len(diffidati_fonte & diffidati_nostri)})
    return righe


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    percorso = Path(sys.argv[1]) if len(sys.argv) > 1 else RADICE / "dati" / "fanta.sqlite"
    db = sqlite3.connect(f"{percorso.resolve().as_uri()}?mode=ro", uri=True)
    adesso = datetime.now()
    stagioni = [s for (s,) in db.execute("SELECT DISTINCT stagione FROM voti ORDER BY stagione")]
    totale = {}
    for stagione in stagioni:
        conti = misura(db, stagione, adesso)
        totale = {k: totale.get(k, 0) + v for k, v in conti.items()}
        print(f"{stagione}: {conti}")
    if totale.get("segnalati"):
        print(f"in tutto: {totale}; falsi {100 * totale['falsi'] / totale['segnalati']:.2f}% dei segnalati")
    for stagione in stagioni:
        for riga in confronto_con_la_fonte(db, stagione, adesso):
            print(f"fonte {stagione}: {riga}")
    righe, insieme = db.execute("SELECT COUNT(*), SUM(ammonizioni > 0 AND espulsioni > 0) FROM voti").fetchone()
    print(f"righe dei voti: {righe}; con giallo e rosso insieme: {insieme or 0}")


if __name__ == "__main__":
    main()
