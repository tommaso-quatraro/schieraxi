"""Prepara la richiesta per far creare a GitHub (API GraphQL createCommitOnBranch) lo stesso commit che c'è in locale.

Perché: un commit creato da GitHub via API è FIRMATO con la chiave di GitHub, e il server installa solo commit firmati
(script/server/verifica-firme.sh). Un `git push` del job invece porterebbe un commit senza firma, che il server rifiuterebbe.

Uso (nel job rilascia, dopo `assegna_versione.py --commit`):
    python3 -I -s script/ci/commit_firmato.py origin/main HEAD > corpo.json
    gh api graphql --input corpo.json --jq .data.createCommitOnBranch.commit.oid
Il commit nuovo nasce sopra BASE solo se main punta ancora a BASE (expectedHeadOid): se main è cambiato GitHub rifiuta e il job riprova.
Solo librerie standard. Ramo di destinazione: main (o --ramo). Repository: variabile GITHUB_REPOSITORY (o --repo).
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys

MUTAZIONE = """mutation ($input: CreateCommitOnBranchInput!) {
  createCommitOnBranch(input: $input) { commit { oid url } }
}"""


def git(*args: str) -> bytes:
    return subprocess.run(["git", *args], check=True, capture_output=True).stdout


def corpo(base: str, testa: str, repo: str, ramo: str = "main") -> dict:
    base = git("rev-parse", "--verify", f"{base}^{{commit}}").decode().strip()
    testa = git("rev-parse", "--verify", f"{testa}^{{commit}}").decode().strip()
    genitori = git("rev-list", "--parents", "-n", "1", testa).decode().split()[1:]
    if genitori != [base]:
        raise SystemExit(f"il commit da ricreare deve essere UNO solo sopra {base[:7]} (genitori: {[g[:7] for g in genitori]})")
    aggiunte, tolte = [], []
    # -z: nomi esatti anche con spazi o accenti; --no-renames: un rinomino diventa «tolto» + «aggiunto»
    campi = git("diff-tree", "-r", "-z", "--no-renames", "--no-commit-id", base, testa).split(b"\0")
    for i in range(0, len(campi) - 1, 2):
        _, modo_nuovo, _, _, stato = campi[i].decode().lstrip(":").split(" ")
        percorso = campi[i + 1].decode("utf-8")
        if stato == "D":
            tolte.append({"path": percorso})
            continue
        if modo_nuovo not in ("100644",):
            raise SystemExit(f"{percorso}: modo {modo_nuovo} (eseguibile o link) non si può creare con l'API: solo file normali")
        aggiunte.append({"path": percorso, "contents": base64.b64encode(git("show", f"{testa}:{percorso}")).decode()})
    if not aggiunte and not tolte:
        raise SystemExit("nessuna differenza fra base e commit: niente da creare")
    messaggio = git("log", "-1", "--format=%B", testa).decode("utf-8").strip()
    titolo, _, resto = messaggio.partition("\n")
    msg = {"headline": titolo.strip()}
    if resto.strip():
        msg["body"] = resto.strip()
    return {"query": MUTAZIONE, "variables": {"input": {
        "branch": {"repositoryNameWithOwner": repo, "branchName": ramo},
        "expectedHeadOid": base,
        "message": msg,
        "fileChanges": {"additions": aggiunte, "deletions": tolte},
    }}}


def main(argv: list[str] | None = None) -> int:
    a = argparse.ArgumentParser(description="Corpo della richiesta createCommitOnBranch per ricreare su GitHub un commit locale")
    a.add_argument("base", help="dove deve puntare il ramo su GitHub adesso (es. origin/main)")
    a.add_argument("testa", help="il commit locale da ricreare (es. HEAD)")
    a.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    a.add_argument("--ramo", default="main")
    arg = a.parse_args(argv)
    if not arg.repo:
        raise SystemExit("manca il repository (--repo o GITHUB_REPOSITORY)")
    # Solo ASCII (accenti come à): il runner del server ha l'uscita in latin-1 e GitHub vuole UTF-8,
    # con «più» nel messaggio rispondeva «Problems parsing JSON (HTTP 400)». In ASCII va bene con ogni codifica.
    sys.stdout.write(json.dumps(corpo(arg.base, arg.testa, arg.repo, arg.ramo), ensure_ascii=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
