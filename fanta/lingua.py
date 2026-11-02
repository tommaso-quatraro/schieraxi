"""Lingua dei testi scritti dal server (italiano predefinito, inglese a richiesta).

Chi non dice nulla (app iOS e Android vecchie, widget) riceve l'italiano, come sempre. Si chiede l'inglese con
`?lingua=en` oppure con l'intestazione `Accept-Language: en` (vale la lingua con la preferenza più alta).
Il parametro `lingua` vince sull'intestazione. Altre lingue o valori strani: italiano.
"""
from __future__ import annotations

IT, EN = "it", "en"
LINGUE = (IT, EN)


def da_intestazione(valore: str | None) -> str:
    """`Accept-Language` -> «it» o «en»: la lingua con la q più alta (a parità, la prima); le altre lingue contano come italiano."""
    migliore, q_migliore = IT, 0.0
    for parte in (valore or "")[:200].split(","):
        tag, _, resto = parte.strip().partition(";")
        tag = tag.strip().lower()
        if not tag or tag == "*":
            continue
        q = 1.0
        resto = resto.strip().lower()
        if resto.startswith("q="):
            try:
                q = float(resto[2:])
            except ValueError:
                q = 0.0
        if q > q_migliore:
            migliore, q_migliore = (EN if tag == "en" or tag.startswith("en-") else IT), q
    return migliore


def valida(valore: str | None) -> str | None:
    v = (valore or "").strip().lower()
    return v if v in LINGUE else None


def della_richiesta(request) -> str:
    """La lingua chiesta da una richiesta FastAPI: `?lingua=` poi `Accept-Language`, altrimenti italiano."""
    return valida(request.query_params.get("lingua")) or da_intestazione(request.headers.get("accept-language"))
