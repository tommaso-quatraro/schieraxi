"""`giornata`: dice se una giornata è passata senza errori (la misura che chiude #167, spec di prodotto §6). Sola lettura.

La finestra va dalla scadenza della lega a due giorni dopo l'inizio dell'ultima partita. Senza errori vuol dire: nessun allarme
della sentinella, nessuna issue `P1` o `dall-utente` nuova, controlli su `main` verdi, collaudo della prova verde. Conta lo
stato per tutta la finestra: una rottura nata prima e ancora aperta rende la giornata rossa. Mai verde per omissione: una
parte che manca (storia della sentinella, collaudi) è un motivo, non un silenzio.

Codici di uscita: 0 senza errori; 1 non ok (stampa i motivi); 2 date rifiutate; 3 errore di gh o file della sentinella."""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import comune

ETICHETTE = ("P1", "dall-utente")
TITOLI_ROSSI = ("CI: main rosso", "Collaudo della prova", "La prova non si aggiorna")
ESITI_BUONI = {"success", "skipped", "cancelled"}      # «annullato» non è «fallito» (CLAUDE.md)
# Il nome del job che collauda davvero (`name:` del job `collauda` in .github/workflows/collaudo-prova.yml): una corsa
# «success» senza questo job riuscito (segreti mancanti = «spento», versione già collaudata = «salta») non è un collaudo.
JOB_COLLAUDO = "Collaudo delle schermate"
BUCO_MASSIMO = timedelta(hours=2)
LIMITE = 1000                                           # il massimo della ricerca di GitHub: arrivarci = risultati tagliati
CAMPI_CORSE = "databaseId,createdAt,conclusion,url"
CAMPI_ISSUE = "number,title,createdAt,closedAt,labels,url"


@dataclass
class Verdetto:
    ok: bool
    motivi: list[str] = field(default_factory=list)


def _ora(d: datetime, fuso) -> str:
    return d.astimezone(fuso).isoformat(timespec="minutes")


def _dove(voce: dict) -> str:
    return f" ({voce['url']})" if voce.get("url") else ""


def _quando(testo) -> datetime | None:
    """Data con il fuso, oppure None (illeggibile o senza fuso: mai confrontata a caso)."""
    try:
        d = comune.data(str(testo))
    except (TypeError, ValueError):
        return None
    return d if d.utcoffset() is not None else None


def _motivi_issue(dal: datetime, al: datetime, issue: list[dict]) -> list[str]:
    motivi = []
    for i in sorted(issue, key=lambda x: x["number"]):
        creata, chiusa = _quando(i.get("createdAt")), _quando(i.get("closedAt")) if i.get("closedAt") else None
        if creata is None:
            motivi.append(f"issue #{i['number']} con data di apertura illeggibile{_dove(i)}")
            continue
        titolo = i.get("title") or ""
        rossa = next((t for t in TITOLI_ROSSI if titolo.startswith(t)), None)
        if rossa and creata <= al and (chiusa is None or chiusa >= dal):
            stato = "ancora aperta" if chiusa is None else f"chiusa {_ora(chiusa, dal.tzinfo)}"
            motivi.append(f"issue #{i['number']} «{titolo}» aperta durante la finestra ({stato}){_dove(i)}")
            continue
        etichette = [e for e in ETICHETTE if e in (i.get("labels") or [])]
        if etichette and dal <= creata <= al:
            motivi.append(f"issue {'/'.join(etichette)} nuova: #{i['number']} «{titolo}», "
                          f"aperta {_ora(creata, dal.tzinfo)}{_dove(i)}")
    return motivi


def _nella_finestra(dal: datetime, al: datetime, c: dict) -> bool:
    quando = _quando(c.get("createdAt"))
    return quando is not None and dal <= quando <= al


def _riuscita(c: dict) -> bool:
    return (c.get("conclusion") or "").lower() == "success"


def _motivi_corse(dal: datetime, al: datetime, corse: list[dict], nome: str) -> list[str]:
    """Motivi delle corse rosse nella finestra (e di quelle con la data illeggibile)."""
    motivi = []
    for c in sorted(corse, key=lambda x: str(x.get("createdAt"))):
        quando = _quando(c.get("createdAt"))
        if quando is None:
            motivi.append(f"corsa {c.get('databaseId')} di {nome} con data illeggibile{_dove(c)}")
            continue
        if not dal <= quando <= al:
            continue
        esito = (c.get("conclusion") or "").lower()
        if esito not in ESITI_BUONI:
            motivi.append(f"{nome}: corsa {c.get('databaseId')} del {_ora(quando, dal.tzinfo)} "
                          f"con esito «{esito or 'nessuno'}»{_dove(c)}")
    return motivi


def _collaudata(dal: datetime, al: datetime, corse: list[dict]) -> bool:
    """Almeno una corsa nella finestra, riuscita, con il job del collaudo riuscito (campo `collaudo`, messo da `raccogli`)."""
    return any(_nella_finestra(dal, al, c) and _riuscita(c) and c.get("collaudo") == "success" for c in corse)


def _motivi_giri(dal: datetime, al: datetime, giri: list[dict] | None) -> list[str]:
    if giri is None:
        return ["manca la storia della sentinella: `python -m fanta sentinella --giri --dal … --al …` sul server, "
                "poi `--sentinella <file.json>`"]
    motivi, ore = [], []
    for g in giri:
        quando = _quando(g.get("quando") if isinstance(g, dict) else None)
        if quando is None:
            motivi.append(f"giro della sentinella con ora illeggibile: {str(g)[:80]}")
            continue
        if not dal <= quando <= al:
            continue
        ore.append(quando)
        rotte = g.get("rotte") or []
        if rotte:
            nomi = ", ".join(str(r) for r in rotte) if isinstance(rotte, list) else str(rotte)
            motivi.append(f"allarme della sentinella alle {_ora(quando, dal.tzinfo)}: {nomi}")
    punti = [dal] + sorted(ore) + [al]
    for prima, dopo in zip(punti, punti[1:]):
        if dopo - prima > BUCO_MASSIMO:
            motivi.append(f"la sentinella non ha girato da {_ora(prima, dal.tzinfo)} a {_ora(dopo, dal.tzinfo)}")
    return motivi


def verdetto(dal: datetime, al: datetime, issue: list[dict], corse_main: list[dict], corse_collaudo: list[dict],
             giri: list[dict] | None) -> Verdetto:
    """Funzione pura: tutte le date con il fuso. `issue` con `labels` come nomi; `giri` = voci della sentinella (H1) o None."""
    if dal.utcoffset() is None or al.utcoffset() is None:
        raise ValueError("dal e al vogliono il fuso")
    motivi = _motivi_issue(dal, al, issue)
    motivi += _motivi_corse(dal, al, corse_main, "Controlli su main")
    motivi += _motivi_corse(dal, al, corse_collaudo, "Collaudo della prova")
    if not _collaudata(dal, al, corse_collaudo):
        motivi.append(f"la prova non è stata collaudata davvero nella finestra (collaudo saltato o spento): nessuna corsa "
                      f"di «Collaudo della prova» con il job «{JOB_COLLAUDO}» riuscito; se nella finestra non esce una "
                      "versione nuova, il collaudo si lancia a mano su main")
    motivi += _motivi_giri(dal, al, giri)
    return Verdetto(ok=not motivi, motivi=motivi)


# --- raccolta con gh ---

def _z(d: datetime) -> str:
    return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _lista(esegui: comune.Esegui, argomenti: list[str]) -> list[dict]:
    risposta = comune.chiama_json(esegui, argomenti)
    if risposta is None:                                # «nessuna risposta» non è «nessun dato»: mai verde per omissione
        raise comune.ErroreComando(f"«{' '.join(argomenti[:4])}» ha dato una risposta vuota")
    if not isinstance(risposta, list):
        raise comune.ErroreComando(f"«{' '.join(argomenti[:4])}» non ha risposto con una lista")
    if len(risposta) >= LIMITE:
        raise comune.ErroreComando(f"«{' '.join(argomenti[:4])}» ha dato {len(risposta)} risultati, il massimo ({LIMITE}): "
                                   "risultati tagliati, finestra troppo larga")
    return risposta


def _segna_collaudi(esegui: comune.Esegui, dal: datetime, al: datetime, corse: list[dict]) -> None:
    """Dalla corsa riuscita più recente nella finestra legge i job e mette in `collaudo` l'esito del job del collaudo; si
    ferma alla prima con il collaudo riuscito (basta un collaudo vero)."""
    riuscite = [c for c in corse if _nella_finestra(dal, al, c) and _riuscita(c)]
    for c in sorted(riuscite, key=lambda x: _quando(x["createdAt"]), reverse=True):
        argomenti = ["gh", "run", "view", str(c["databaseId"]), "--json", "jobs"]
        risposta = comune.chiama_json(esegui, argomenti)
        if not isinstance(risposta, dict) or not isinstance(risposta.get("jobs"), list):
            raise comune.ErroreComando(f"«{' '.join(argomenti[:4])}» non ha dato l'elenco dei job")
        job = next((j for j in risposta["jobs"] if j.get("name") == JOB_COLLAUDO), None)
        c["collaudo"] = (job.get("conclusion") or "").lower() if job else "manca"
        if c["collaudo"] == "success":
            return


def raccogli(esegui: comune.Esegui, dal: datetime, al: datetime) -> dict:
    finestra = f"{_z(dal)}..{_z(al)}"
    corse = {}
    for chiave, workflow in (("corse_main", "test.yml"), ("corse_collaudo", "collaudo-prova.yml")):
        corse[chiave] = _lista(esegui, ["gh", "run", "list", "--workflow", workflow, "--branch", "main",
                                        "--created", finestra, "--limit", str(LIMITE), "--json", CAMPI_CORSE])
    _segna_collaudi(esegui, dal, al, corse["corse_collaudo"])
    ricerche = [f"created:{finestra}"] + [f'"{t}" in:title created:<={_z(al)}' for t in TITOLI_ROSSI]
    issue: dict[int, dict] = {}
    for ricerca in ricerche:
        for i in _lista(esegui, ["gh", "issue", "list", "--state", "all", "--search", ricerca,
                                 "--limit", str(LIMITE), "--json", CAMPI_ISSUE]):
            issue[i["number"]] = dict(i, labels=[e["name"] if isinstance(e, dict) else e for e in i.get("labels") or []])
    return {"issue": [issue[n] for n in sorted(issue)], **corse}


def leggi_giri(percorso: str) -> list[dict]:
    """Il file portato dal server: l'uscita di `sentinella --giri` (una lista) o il file di stato intero (con `giri`)."""
    try:
        dati = json.loads(Path(percorso).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise ValueError(f"file della sentinella illeggibile ({type(e).__name__})") from None
    giri = dati.get("giri") if isinstance(dati, dict) else dati
    if not isinstance(giri, list):
        raise ValueError("file della sentinella senza la lista dei giri")
    return giri


def _data_con_fuso(nome: str, testo: str) -> datetime:
    try:
        d = datetime.fromisoformat(testo.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError(f"{nome}: «{testo}» non è una data ISO (esempio con il fuso: 2026-11-15T13:50:00+01:00)") from None
    if d.utcoffset() is None:
        raise ValueError(f"{nome}: «{testo}» non ha il fuso (esempio: 2026-11-15T13:50:00+01:00 o 2026-11-15T12:50:00Z)")
    return d


def testo(dal: datetime, al: datetime, v: Verdetto) -> str:
    finestra = f"Giornata dal {_ora(dal, dal.tzinfo)} al {_ora(al, dal.tzinfo)}"
    if v.ok:
        return f"{finestra}: senza errori."
    return "\n".join([f"{finestra}: NON ok ({len(v.motivi)} motivi)"] + [f"- {m}" for m in v.motivi])


def main(esegui: comune.Esegui, dal: str, al: str, sentinella: str | None = None, json_: bool = False,
         adesso: datetime | None = None) -> int:
    try:
        inizio, fine = _data_con_fuso("--dal", dal), _data_con_fuso("--al", al)
        if inizio >= fine:
            raise ValueError("--dal deve venire prima di --al (date con il fuso)")
        if fine > (adesso or comune.ora()):
            raise ValueError("--al è nel futuro: il comando si lancia a finestra finita")
    except ValueError as e:
        print(f"giornata: {e}", file=sys.stderr)
        return 2
    try:
        giri = leggi_giri(sentinella) if sentinella else None
        dati = raccogli(esegui, inizio, fine)
    except (ValueError, comune.ErroreComando) as e:
        print(f"giornata: {e}", file=sys.stderr)
        return 3
    v = verdetto(inizio, fine, dati["issue"], dati["corse_main"], dati["corse_collaudo"], giri)
    if json_:
        print(json.dumps({"dal": inizio.isoformat(), "al": fine.isoformat(), "ok": v.ok, "motivi": v.motivi},
                         ensure_ascii=False, indent=2))
    else:
        print(testo(inizio, fine, v))
    return 0 if v.ok else 1


NOME = "giornata"
AIUTO = "Dice se una giornata è passata senza errori: sentinella, issue P1 o dall-utente, controlli su main, collaudo (sola lettura)."
USCITE = "0 senza errori; 1 non ok (stampa i motivi); 2 date rifiutate (senza fuso, rovesciate o --al nel futuro); " \
         "3 errore di gh o file della sentinella illeggibile."


def opzioni(p) -> None:
    p.add_argument("--dal", required=True, help="inizio della finestra, ISO con il fuso: la scadenza della lega")
    p.add_argument("--al", required=True, help="fine della finestra, ISO con il fuso: due giorni dopo l'ultima partita")
    p.add_argument("--sentinella", metavar="FILE", help="giri della sentinella portati dal server (uscita di "
                   "«python -m fanta sentinella --giri --dal … --al …»); senza, la giornata non è mai verde")
    p.add_argument("--json", action="store_true", help="uscita in JSON per altri script")


def da_riga(args, esegui: comune.Esegui, adesso: datetime | None = None) -> int:
    return main(esegui, args.dal, args.al, args.sentinella, json_=args.json, adesso=adesso)
