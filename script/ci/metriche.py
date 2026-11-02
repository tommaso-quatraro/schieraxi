"""Metriche della squadra, settimana per settimana (lunedì-domenica, ora italiana).

Misura, dai dati di GitHub letti con `gh` (solo lettura):
- versioni uscite (release `vX.Y` create dal job `rilascia`);
- PR unite e tempo dall'apertura all'unione (mediana e 90° percentile, ore);
- guasti dopo l'unione: issue con l'etichetta `regressione` aperte nella settimana, e quante per PR unita;
- tempo per rimediare: dall'apertura alla chiusura delle issue `regressione` (mediana, ore) e quante ancora aperte;
- difetti trovati dall'utente: issue `dall-utente` sul totale dei difetti (`bug`, `regressione`, `dall-utente`);
- PR fuori piano: PR unite con l'etichetta `fuori-piano`;
- attesa dei lavori iOS: dall'apertura all'unione delle PR che toccano `ios/` (o di un repository `*-ios`).

Uso: python script/ci/metriche.py [--repo PROPRIETARIO/NOME ...] [--da AAAA-MM-GG] [--settimane N] [--json]
Senza --repo usa il repository della cartella corrente. Solo libreria standard più il comando `gh` già autenticato.
"""
import argparse
import json
import math
import re
import subprocess
import sys
import time
from datetime import date, datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
    _ROMA = ZoneInfo("Europe/Rome")
except Exception:                                   # Windows senza dati dei fusi: ora solare italiana
    _ROMA = timezone(timedelta(hours=1))

DIFETTI = {"bug", "regressione", "dall-utente"}
VERSIONE = re.compile(r"^v\d+(\.\d+)+$")


def lunedi(quando: datetime) -> date:
    """Il lunedì (ora italiana) della settimana di `quando`."""
    giorno = quando.astimezone(_ROMA).date()
    return giorno - timedelta(days=giorno.weekday())


def mediana(valori):
    v = sorted(valori)
    if not v:
        return None
    m = len(v) // 2
    return v[m] if len(v) % 2 else (v[m - 1] + v[m]) / 2


def percentile(valori, p):
    """Percentile col metodo del rango più vicino."""
    v = sorted(valori)
    if not v:
        return None
    return v[max(0, math.ceil(p / 100 * len(v)) - 1)]


def e_ios(repo: str, file: list) -> bool:
    return repo.endswith("-ios") or any(f.startswith("ios/") for f in file)


def _ore(da: datetime, a: datetime) -> float:
    return (a - da).total_seconds() / 3600


def riepilogo(settimana: date, pr: list, issue: list, versioni: list) -> dict:
    """Numeri di una settimana. pr: dict con creata, unita, etichette, ios; issue: dict con creata, chiusa, etichette."""
    def dentro(t):
        return t is not None and lunedi(t) == settimana

    unite = [p for p in pr if dentro(p["unita"])]
    ore_pr = [_ore(p["creata"], p["unita"]) for p in unite]
    ios = [_ore(p["creata"], p["unita"]) for p in unite if p["ios"]]
    regressioni = [i for i in issue if "regressione" in i["etichette"] and dentro(i["creata"])]
    rimedi = [_ore(i["creata"], i["chiusa"]) for i in regressioni if i["chiusa"]]
    difetti = [i for i in issue if DIFETTI & set(i["etichette"]) and dentro(i["creata"])]
    dall_utente = [i for i in difetti if "dall-utente" in i["etichette"]]
    return {
        "settimana": settimana.isoformat(),
        "versioni": sum(1 for v in versioni if dentro(v)),
        "pr_unite": len(unite),
        "ore_pr_mediana": mediana(ore_pr),
        "ore_pr_p90": percentile(ore_pr, 90),
        "regressioni": len(regressioni),
        "guasti_su_unioni": (len(regressioni) / len(unite)) if unite else None,
        "ore_rimedio_mediana": mediana(rimedi),
        "regressioni_aperte": sum(1 for i in regressioni if not i["chiusa"]),
        "difetti": len(difetti),
        "dall_utente": len(dall_utente),
        "quota_dall_utente": (len(dall_utente) / len(difetti)) if difetti else None,
        "fuori_piano": sum(1 for p in unite if "fuori-piano" in p["etichette"]),
        "pr_ios": len(ios),
        "ore_ios_mediana": mediana(ios),
    }


# --- lettura da GitHub (gh) ---

def _gh(*args):
    for tentativo in range(3):                     # GitHub risponde a volte 502 sulle richieste pesanti: si riprova
        r = subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8")
        if r.returncode == 0:
            return json.loads(r.stdout or "[]")
        if "502" not in r.stderr and "504" not in r.stderr:
            break
        time.sleep(5 * (tentativo + 1))
    raise SystemExit(f"gh {' '.join(args[:3])}...: {r.stderr.strip()}")


def _t(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


def leggi(repo: str, da: date, fino: date):
    """PR unite, issue aperte e release dal lunedì `da` alla domenica prima di `fino`. Le PR si chiedono una settimana
    alla volta (con i file, per riconoscere quelle iOS): una richiesta sola per tutto il periodo è troppo pesante per GitHub."""
    giorno = da.isoformat()
    grezze = []
    s = da
    while s < fino:
        intervallo = f"merged:{s.isoformat()}..{(s + timedelta(days=6)).isoformat()}"
        grezze += _gh("pr", "list", "-R", repo, "--state", "merged", "--limit", "500", "--search", intervallo,
                      "--json", "number,createdAt,mergedAt,labels,files")
        s += timedelta(weeks=1)
    pr = []
    for p in grezze:
        pr.append({"repo": repo, "numero": p["number"], "creata": _t(p["createdAt"]), "unita": _t(p["mergedAt"]),
                   "etichette": [e["name"] for e in p["labels"]],
                   "ios": e_ios(repo, [f["path"] for f in p.get("files") or []])})
    issue = []
    for i in _gh("issue", "list", "-R", repo, "--state", "all", "--limit", "1000", "--search", f"created:>={giorno}",
                 "--json", "number,createdAt,closedAt,labels"):
        issue.append({"repo": repo, "numero": i["number"], "creata": _t(i["createdAt"]), "chiusa": _t(i["closedAt"]),
                      "etichette": [e["name"] for e in i["labels"]]})
    versioni = [_t(r["publishedAt"]) for r in _gh("release", "list", "-R", repo, "--limit", "1000",
                                                  "--json", "tagName,publishedAt")
                if VERSIONE.match(r["tagName"]) and r.get("publishedAt")]
    return pr, issue, versioni


def coda_ios(repos: list, adesso: datetime) -> dict:
    """PR iOS ancora aperte adesso e da quante ore aspettano (la coda vera: le PR unite da sole non la mostrano)."""
    ore, bozze = [], 0
    for repo in repos:
        for p in _gh("pr", "list", "-R", repo, "--state", "open", "--limit", "200", "--json", "createdAt,isDraft,files"):
            if e_ios(repo, [f["path"] for f in p.get("files") or []]):
                ore.append(_ore(_t(p["createdAt"]), adesso))
                bozze += bool(p["isDraft"])
    return {"aperte": len(ore), "bozze": bozze, "ore_mediana": mediana(ore), "ore_massima": max(ore) if ore else None}


def _fmt(v, cifre=1):
    if v is None:
        return "–"
    if isinstance(v, float):
        return f"{v:.{cifre}f}"
    return str(v)


def tabella(righe: list) -> str:
    colonne = [
        ("Settimana (lun)", "settimana"), ("Versioni", "versioni"), ("PR unite", "pr_unite"),
        ("Ore PR→unione (mediana)", "ore_pr_mediana"), ("(90°)", "ore_pr_p90"), ("Regressioni", "regressioni"),
        ("Regressioni per PR", "guasti_su_unioni"), ("Ore per rimediare", "ore_rimedio_mediana"),
        ("Regr. aperte", "regressioni_aperte"), ("Difetti", "difetti"), ("Dall'utente", "quota_dall_utente"),
        ("PR fuori piano", "fuori_piano"), ("PR iOS", "pr_ios"), ("Ore iOS (mediana)", "ore_ios_mediana"),
    ]
    out = ["| " + " | ".join(t for t, _ in colonne) + " |", "|" + "---|" * len(colonne)]
    for r in righe:
        celle = []
        for _, k in colonne:
            v = r[k]
            if k == "quota_dall_utente":
                celle.append("–" if v is None else f"{v:.0%} ({r['dall_utente']}/{r['difetti']})")
            elif k == "guasti_su_unioni":
                celle.append(_fmt(v, 2))
            else:
                celle.append(_fmt(v))
        out.append("| " + " | ".join(celle) + " |")
    return "\n".join(out)


def main(argv=None):
    a = argparse.ArgumentParser(description="Metriche settimanali della squadra (dati di GitHub, solo lettura).")
    a.add_argument("--repo", action="append", help="PROPRIETARIO/NOME; si può ripetere. Predefinito: quello della cartella.")
    a.add_argument("--da", help="primo giorno (AAAA-MM-GG); predefinito: il lunedì di N settimane fa")
    a.add_argument("--settimane", type=int, default=4, help="quante settimane (predefinito 4)")
    a.add_argument("--json", action="store_true", help="stampa JSON invece della tabella")
    o = a.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")       # console di Windows in cp1252
    oggi = datetime.now(timezone.utc)
    if o.da:
        primo = lunedi(datetime.fromisoformat(o.da).replace(hour=12, tzinfo=_ROMA))
    else:
        primo = lunedi(oggi) - timedelta(weeks=o.settimane - 1)
    repos = o.repo or [_gh("repo", "view", "--json", "nameWithOwner")["nameWithOwner"]]
    pr, issue, versioni = [], [], []
    fine = min(primo + timedelta(weeks=o.settimane), lunedi(oggi) + timedelta(weeks=1))
    for r in repos:
        p, i, v = leggi(r, primo, fine)
        pr += p
        issue += i
        versioni += v
    settimane = []
    s = primo
    while s <= lunedi(oggi) and len(settimane) < o.settimane:
        settimane.append(riepilogo(s, pr, issue, versioni))
        s += timedelta(weeks=1)
    coda = coda_ios(repos, oggi)
    if o.json:
        print(json.dumps({"repository": repos, "settimane": settimane, "coda_ios": coda}, ensure_ascii=False, indent=1))
    else:
        print(f"Metriche della squadra: {', '.join(repos)} (ore = ore di calendario; «–» = nessun dato)\n")
        print(tabella(settimane))
        print(f"\nCoda iOS adesso: {coda['aperte']} PR aperte ({coda['bozze']} in bozza), attesa mediana "
              f"{_fmt(coda['ore_mediana'])} ore, la più vecchia {_fmt(coda['ore_massima'])} ore.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
