"""Dopo l'unione di una PR, su main: dà il numero di versione alle novità in attesa in `fanta/novita.d/`.

Ogni PR scrive le sue novità in un file proprio, `fanta/novita.d/<nome-breve>.json`, SENZA numero:
    {"titolo": "Cosa cambia in una riga", "voci": ["una frase per l'utente", "..."], "tecnico": ["dettagli per chi sviluppa"]}
Le `voci` le legge l'utente nell'app (Lega > Novità): italiano semplice, 2-3 voci da 1-2 righe, senza sigle, indirizzi
/api, metodi HTTP, codici (202, 403) o nomi di file. I dettagli tecnici vanno in `tecnico` (facoltativo: l'app non lo
mostra, finisce nelle note della release) o nella descrizione della PR.
Facoltativi: `titolo_en` e `voci_en` (tante voci quante le italiane), la traduzione inglese che l'app mostra con la lingua inglese.
così due PR in parallelo non toccano la stessa riga e non vanno in conflitto.
Questo script (lo lancia il job `rilascia` dei controlli, uno alla volta) per ogni file in attesa, nell'ordine in cui
sono entrati in main:
- aggiunge in cima a `fanta/novita.json` una voce con la versione dopo la più alta (1.10 dopo 1.9) e data e ora
  dell'unione (ora italiana, AAAA-MM-GGTOO:MM:SS);
- toglie il file da `fanta/novita.d/`;
- se quella PR ha toccato `fanta/web/` senza alzare `VERSIONE` in `fanta/web/sw.js`, la alza di 1 (una volta sola per giro).
Con --commit fa anche il commit (il push lo fa il job). Stampa le versioni nuove, una per riga (niente = nulla da fare).
Con --urgente il commit ha anche la riga «Rilascio: urgente»: il server installa subito, senza aspettare l'intervallo fra due
installazioni (script/server/aggiorna-app.sh, #635). Il job la chiede quando una delle PR delle novità in attesa, o una issue che
quella PR chiude, ha l'etichetta P1 o urgente. Le stampa --pr-e-issue-in-attesa, senza cambiare niente: «pr N» dal titolo
«... (#N)» del commit di unione, «issue M» dalle righe di chiusura che il job unisci mette nel suo corpo («Closes #M»).
Solo libreria standard: gira nei controlli di GitHub e sul server (Python 3.11).
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import re
import subprocess
import sys
from pathlib import Path

NOVITA = "fanta/novita.json"
CARTELLA = "fanta/novita.d"
SW = "fanta/web/sw.js"
WEB = "fanta/web/"
NOME_FILE = re.compile(r"[a-z0-9][a-z0-9-]{0,60}\.json")
RIGA_VERSIONE = re.compile(r'^(const VERSIONE = "fanta-)(\d+)(";)', re.M)
DATA = re.compile(r"\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2})?")
RIGA_URGENTE = "Rilascio: urgente"          # la cerca, come riga intera, script/server/aggiorna-app.sh
PR_NEL_TITOLO = re.compile(r"\(#(\d+)\)\s*$")     # il job unisci scrive il titolo del commit come «Titolo della PR (#N)»
# ... e nel corpo una riga «Closes #N» per ogni issue chiusa (solo quelle che GitHub collega alla PR): riga intera, un numero
RIGA_CHIUSURA = re.compile(r"^(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?) #(\d+)\s*$", re.I | re.M)
# parole da tecnici nelle voci per l'utente: solo un avviso, non blocca
TECNICO = [(re.compile(r"/api/"), "indirizzo /api/"), (re.compile(r"\b(GET|POST|PUT|DELETE|PATCH|HTTP)\b"), "metodo o sigla HTTP"),
           (re.compile(r"(?<![\d,.])[1-5]\d\d(?![\d,]|\.\d)"), "numero di tre cifre (codice di risposta?)"),
           (re.compile(r"\b[\w-]+\.(py|js|json|sh|md|css|html|sqlite)\b"), "nome di file")]


def numero(versione: str) -> tuple[int, ...]:
    if not re.fullmatch(r"\d+(\.\d+)+", str(versione)):
        raise ValueError(f"versione non valida: {versione!r} (serve un formato come 1.10)")
    return tuple(int(p) for p in str(versione).split("."))


# --- Parte pura (testata in tests/test_assegna_versione.py) ---

def errori_file(nome: str, dati) -> list[str]:
    """Cosa non va in un file di novità in attesa (lista vuota = va bene)."""
    errori = []
    if not NOME_FILE.fullmatch(nome):
        errori.append(f"{nome}: il nome deve essere breve, con lettere minuscole, cifre e trattini, e finire in .json")
    if not isinstance(dati, dict):
        return errori + [f"{nome}: deve contenere un oggetto JSON con titolo e voci"]
    if "versione" in dati:
        errori.append(f"{nome}: niente numero di versione, lo assegna il bot quando la PR si unisce")
    if not isinstance(dati.get("titolo"), str) or not dati["titolo"].strip():
        errori.append(f"{nome}: serve un titolo (testo)")
    voci = dati.get("voci")
    if not isinstance(voci, list) or not voci or not all(isinstance(v, str) and v.strip() for v in voci):
        errori.append(f"{nome}: serve almeno una voce di novità (lista di frasi)")
    if "data" in dati and not DATA.fullmatch(str(dati["data"])):
        errori.append(f"{nome}: la data, se c'è, va scritta AAAA-MM-GGTOO:MM:SS (tanto la mette il bot all'unione)")
    tecnico = dati.get("tecnico", [])
    if not isinstance(tecnico, list) or not all(isinstance(v, str) and v.strip() for v in tecnico):
        errori.append(f"{nome}: «tecnico», se c'è, è una lista di frasi")
    if "titolo_en" in dati and (not isinstance(dati["titolo_en"], str) or not dati["titolo_en"].strip()):
        errori.append(f"{nome}: «titolo_en», se c'è, è un testo")
    voci_en = dati.get("voci_en")
    if "voci_en" in dati and (not isinstance(voci_en, list) or not all(isinstance(v, str) and v.strip() for v in voci_en)
                              or (isinstance(voci, list) and len(voci_en) != len(voci))):
        errori.append(f"{nome}: «voci_en», se c'è, è una lista di frasi, tante quante le voci")
    altre = set(dati) - {"titolo", "voci", "data", "tecnico", "titolo_en", "voci_en"}
    if altre:
        errori.append(f"{nome}: chiavi non previste: {', '.join(sorted(altre))}")
    return errori


def avvisi_voci(voci) -> list[str]:
    """Voci che sembrano scritte per tecnici (l'utente finale le legge nell'app): avvisi, non errori."""
    avvisi = []
    for voce in voci if isinstance(voci, list) else []:
        trovati = [descrizione for schema, descrizione in TECNICO if schema.search(str(voce))]
        if trovati:
            avvisi.append(f"voce poco adatta all'utente ({', '.join(trovati)}): «{str(voce)[:70]}…» -> sposta i dettagli in «tecnico»")
        if len(str(voce)) > 240:
            avvisi.append(f"voce lunga ({len(str(voce))} caratteri, meglio 1-2 righe): «{str(voce)[:50]}…»")
    if isinstance(voci, list) and len(voci) > 3:
        avvisi.append(f"{len(voci)} voci: meglio 2-3")
    return avvisi


def con_versioni(elenco: list[dict], in_attesa: list[tuple[dict, str]]) -> tuple[list[dict], list[str]]:
    """Elenco nuovo e versioni assegnate. `in_attesa` = (novità, data dell'unione), dalla più vecchia alla più nuova."""
    alta = max((numero(v["versione"]) for v in elenco), default=(1, 0))
    nuove, versioni = [], []
    for i, (dati, data) in enumerate(in_attesa, start=1):
        versione = ".".join(str(p) for p in alta[:-1] + (alta[-1] + i,))
        voce = {"versione": versione, "data": data, "titolo": dati["titolo"].strip(), "voci": list(dati["voci"])}
        if dati.get("tecnico"):
            voce["tecnico"] = list(dati["tecnico"])
        if dati.get("titolo_en") and dati.get("voci_en"):          # facoltativi: la traduzione inglese che l'app mostra con la lingua inglese
            voce["titolo_en"] = dati["titolo_en"].strip()
            voce["voci_en"] = list(dati["voci_en"])
        nuove.insert(0, voce)
        versioni.append(versione)
    return nuove + elenco, versioni


def alza_sw(testo: str) -> str:
    trovate = RIGA_VERSIONE.findall(testo)
    if len(trovate) != 1:
        raise ValueError("in fanta/web/sw.js deve esserci una sola riga VERSIONE")
    return RIGA_VERSIONE.sub(lambda m: f"{m.group(1)}{int(m.group(2)) + 1}{m.group(3)}", testo)


def ora_italiana(iso: str) -> str:
    """'2026-10-30T15:08:24Z' o con fuso -> '2026-10-30T16:08:24' (Europe/Rome)."""
    quando = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    try:
        from zoneinfo import ZoneInfo
        quando = quando.astimezone(ZoneInfo("Europe/Rome"))
    except Exception:       # senza database dei fusi: si tiene l'ora così com'è
        pass
    return quando.strftime("%Y-%m-%dT%H:%M:%S")


# --- Parte con git e con i file ---

def git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True).stdout.decode("utf-8")


def versione_sw(commit: str) -> str | None:
    try:
        trovata = RIGA_VERSIONE.search(git("show", f"{commit}:{SW}"))
    except subprocess.CalledProcessError:
        return None
    return trovata.group(2) if trovata else None


def in_attesa() -> list[tuple[str, dict, str, bool]]:
    """(percorso, novità, data dell'unione, serve alzare sw.js), nell'ordine in cui sono entrati in main."""
    trovati = []
    for f in sorted(Path(CARTELLA).glob("*.json")) if Path(CARTELLA).is_dir() else []:
        percorso = f.as_posix()
        dati = json.loads(f.read_bytes().decode("utf-8"))
        errori = errori_file(f.name, dati)
        if errori:
            raise ValueError("; ".join(errori))
        riga = git("log", "-1", "--diff-filter=A", "--format=%H %cI", "--", percorso).split()
        if not riga:
            raise ValueError(f"{percorso} non è in git")
        commit, quando = riga
        ordine = int(git("rev-list", "--count", commit).strip())
        toccati = git("diff-tree", "--no-commit-id", "--name-only", "-r", "--root", commit).splitlines()
        # anche una PR che tocca solo sw.js: se non ha alzato VERSIONE lo fa il bot (nessun ciclo: il commit del bot non aggiunge file in novita.d)
        web = any(t.startswith(WEB) for t in toccati)
        sw_alzato = SW in toccati and versione_sw(f"{commit}^") != versione_sw(commit)
        trovati.append((ordine, percorso, dati, ora_italiana(quando), web and not sw_alzato))
    trovati.sort(key=lambda t: (t[0], t[1]))
    return [t[1:] for t in trovati]


def pr_e_issue_in_attesa() -> list[tuple[str, int]]:
    """(«pr», N) e («issue», M) delle novità in attesa, dal commit che ha aggiunto ogni file: la PR dal titolo («... (#N)»), le
    issue dalle righe di chiusura del corpo. Ognuna una volta sola; un commit senza numero di PR non conta."""
    trovate: list[tuple[str, int]] = []
    for percorso, *_ in in_attesa():
        titolo, _, corpo = git("log", "-1", "--diff-filter=A", "--format=%B", "--", percorso).strip().partition("\n")
        m = PR_NEL_TITOLO.search(titolo.strip())
        if not m:
            continue
        for voce in [("pr", int(m.group(1)))] + [("issue", int(n)) for n in RIGA_CHIUSURA.findall(corpo.replace("\r", ""))]:
            if voce not in trovate:
                trovate.append(voce)
    return trovate


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", newline="\n")     # righe lette da bash: niente \r, anche su Windows
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--commit", action="store_true", help="fa anche il commit (senza push)")
    parser.add_argument("--urgente", action="store_true", help=f"con --commit: aggiunge la riga «{RIGA_URGENTE}» al messaggio")
    parser.add_argument("--pr-e-issue-in-attesa", action="store_true",
                        help="stampa solo le PR delle novità in attesa e le issue che chiudono («pr N», «issue M»)")
    args = parser.parse_args()
    try:
        if args.pr_e_issue_in_attesa:
            print("\n".join(f"{tipo} {n}" for tipo, n in pr_e_issue_in_attesa()))
            return 0
        attesa = in_attesa()
        if not attesa:
            print("Nessuna novità in attesa in fanta/novita.d.", file=sys.stderr)
            return 0
        testo = Path(NOVITA).read_bytes().decode("utf-8")
        elenco, versioni = con_versioni(json.loads(testo), [(d, data) for _, d, data, _ in attesa])
        a_capo = "\r\n" if "\r\n" in testo else "\n"
        Path(NOVITA).write_bytes((json.dumps(elenco, indent=2, ensure_ascii=False) + "\n").replace("\n", a_capo).encode("utf-8"))
        da_aggiungere = [NOVITA]
        if any(sw for *_, sw in attesa):
            Path(SW).write_bytes(alza_sw(Path(SW).read_bytes().decode("utf-8")).encode("utf-8"))
            da_aggiungere.append(SW)
        if args.commit:
            git("rm", "-q", *[p for p, *_ in attesa])
            git("add", *da_aggiungere)
            titoli = "; ".join(d["titolo"] for _, d, _, _ in attesa)
            messaggio = f"Versione {', '.join(versioni)}: {titoli}"[:200]
            if args.urgente:
                messaggio += f"\n\n{RIGA_URGENTE}"
            git("commit", "-q", "-m", messaggio)
        else:
            for p, *_ in attesa:
                Path(p).unlink()
    except (ValueError, KeyError, json.JSONDecodeError, subprocess.CalledProcessError) as e:
        dettaglio = e.stderr.decode("utf-8", "replace") if isinstance(e, subprocess.CalledProcessError) and e.stderr else ""
        print(f"Errore: {e} {dettaglio}".strip(), file=sys.stderr)
        return 2
    print("\n".join(versioni))
    return 0


if __name__ == "__main__":
    sys.exit(main())
