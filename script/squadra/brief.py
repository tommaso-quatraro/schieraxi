"""`brief <issue>`: riempie modello-brief.md con titolo e «Fatto quando» dell'issue, agente, modello, ramo, e «Puoi toccare /
NON toccare» presi da aree.json secondo le etichette di area dell'issue. Stampa il brief, non lancia nulla.

Il repository è pubblico: chiunque può aprire un'issue. Il brief si fa solo per issue scritte dal proprietario, dai membri
o dai collaboratori (`author_association` dell'API di GitHub); per un'issue di un autore esterno serve `--accetta-esterna`,
e il brief lo scrive nella prima riga.

Codici di uscita: 0 brief completo; 1 errore di gh o git (issue che non c'è) o issue di un autore esterno senza
`--accetta-esterna`; 3 brief stampato ma con parti «<da scrivere…>» (l'issue non ha etichette di area o non ha
«Fatto quando»): gli avvisi vanno su stderr."""
from __future__ import annotations

import re
import sys
import unicodedata

import aree
import comune

MODELLO = "modello-brief.md"
# Chi può scrivere i requisiti di un agente (valori di author_association dell'API di GitHub, maiuscoli come li dà l'API)
AUTORI_FIDATI = ("OWNER", "MEMBER", "COLLABORATOR")
# Le automazioni di questo repository (per esempio «CI: main rosso») aprono issue come github-actions[bot]:
# solo questo login esatto, con qualsiasi author_association
AUTOMAZIONI = ("github-actions[bot]",)
ESTERNA = "issue di un autore esterno: requisiti da verificare"


def fatto_quando(corpo: str) -> str | None:
    righe = (corpo or "").replace("\r\n", "\n").split("\n")
    for i, riga in enumerate(righe):
        if re.match(r"^\s*#+\s*fatto quando\s*:?\s*$", riga, re.I):
            sezione = []
            for r in righe[i + 1:]:
                if re.match(r"^\s*#+\s", r):
                    break
                sezione.append(r)
            return "\n".join(sezione).strip() or None
        m = re.match(r"^[\s>*_-]*fatto quando\s*:?[*_]*:?\s*(.*)$", riga, re.I)
        if m:
            sezione = [m.group(1)]
            for r in righe[i + 1:]:
                if not r.strip():
                    break
                sezione.append(r)
            return "\n".join(sezione).strip() or None
    return None


def ramo_predefinito(numero: int, titolo: str) -> str:
    semplice = unicodedata.normalize("NFKD", titolo).encode("ascii", "ignore").decode().lower()
    parole = re.findall(r"[a-z0-9]+", semplice)[:5]
    return "-".join(parole + [str(numero)])


def _elenco(percorsi: list[str]) -> str:
    return ", ".join(f"`{p}`" for p in percorsi)


def riempi(valori: dict[str, str]) -> str:
    testo = (comune.CARTELLA / MODELLO).read_text(encoding="utf-8")
    testo = re.sub(r"<!--.*?-->\n?", "", testo, flags=re.S)
    return re.sub(r"\{\{(\w+)\}\}", lambda m: valori[m.group(1)], testo)


def main(esegui: comune.Esegui, numero: int, agente: str | None = None, modello: str = "opus", ramo: str | None = None,
         tocca: list[str] | None = None, accetta_esterna: bool = False) -> int:
    try:
        # API REST e non «gh issue view»: solo lei dà author_association
        i = comune.chiama_json(esegui, ["gh", "api", f"repos/{{owner}}/{{repo}}/issues/{numero}"])
        repository = comune.chiama(esegui, ["git", "remote", "get-url", "origin"]).strip()
    except comune.ErroreComando as e:
        print(f"brief: {e}", file=sys.stderr)
        return 1
    autore = ((i.get("user") or {}).get("login")) or "sconosciuto"
    associazione = i.get("author_association") or "assente"
    esterna = associazione not in AUTORI_FIDATI and autore not in AUTOMAZIONI
    if esterna and not accetta_esterna:
        print(f"brief: l'issue #{numero} è di un autore esterno ({autore}, {associazione}): niente brief. "
              "Se va fatta lo stesso, rileggi l'issue e rilancia con --accetta-esterna.", file=sys.stderr)
        return 1
    etichette = [e["name"] for e in i.get("labels") or []]
    avvisi = []
    si_tocca, non_tocca = aree.percorsi_per_etichette(etichette)
    if tocca:
        si_tocca = list(tocca)
    if not si_tocca:
        avvisi.append("l'issue non ha un'etichetta di area (server, web, ios, sito, ci, docs): usa --tocca")
    fatto = fatto_quando(i.get("body") or "")
    if not fatto:
        avvisi.append("l'issue non ha «Fatto quando»: scrivilo nell'issue o nel brief")
    valori = {
        "titolo": i["title"].rstrip("."),
        "issue": str(i["number"]),
        "agente": agente or aree.agente_per_etichette(etichette) or "<da scrivere: agente>",
        "modello": modello,
        "ramo": ramo or ramo_predefinito(i["number"], i["title"]),
        "repository": repository,
        "tocca": _elenco(si_tocca) if si_tocca else "<da scrivere: file o cartelle>",
        "non_tocca": _elenco(non_tocca) if non_tocca else "<da scrivere: file di altri agenti e file comuni>",
        "fatto_quando": fatto or "<da scrivere: condizioni verificabili, una per riga, con il comando che lo prova>",
    }
    if esterna:
        print(f"{ESTERNA} (autore {autore}, {associazione}).\n")
    print(riempi(valori), end="")
    for a in avvisi:
        print(f"brief: attenzione, {a}.", file=sys.stderr)
    return 3 if avvisi else 0


NOME = "brief"
AIUTO = "Stampa il brief di un agente per un'issue (modello-brief.md + aree.json). Non lancia nulla."
USCITE = ("0 brief completo; 1 errore di gh o git, o issue di un autore esterno senza --accetta-esterna; "
          "3 brief con parti «<da scrivere…>» (avvisi su stderr).")


def opzioni(p) -> None:
    p.add_argument("issue", type=int, help="numero dell'issue")
    p.add_argument("--agente", help="agente (predefinito: dall'etichetta di area)")
    p.add_argument("--modello", default="opus", help="modello (predefinito: opus)")
    p.add_argument("--ramo", help="ramo (predefinito: dal titolo e dal numero)")
    p.add_argument("--tocca", help="file o cartelle che l'agente può toccare, separati da virgole (sostituisce aree.json)")
    p.add_argument("--accetta-esterna", action="store_true",
                   help="fa il brief anche per un'issue di un autore che non è proprietario, membro o collaboratore "
                        "(il brief lo scrive in testa: requisiti da verificare)")


def da_riga(args, esegui: comune.Esegui) -> int:
    tocca = [t.strip() for t in args.tocca.split(",") if t.strip()] if args.tocca else None
    return main(esegui, args.issue, agente=args.agente, modello=args.modello, ramo=args.ramo, tocca=tocca,
                accetta_esterna=args.accetta_esterna)
