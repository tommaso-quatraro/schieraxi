"""Aiuto per i test sul codice web: rimette al loro posto i testi italiani.

Nel codice i testi sono t("chiave"); molti test controllano che certe parole (i nomi di docs/ETICHETTE.md, per esempio) ci siano.
`espandi(codice)` sostituisce ogni t("chiave") semplice con il testo italiano della chiave: dentro un modello HTML (${t("k")}) in chiaro,
altrove tra virgolette. Così i controlli sui testi restano scritti in italiano e leggibili.
"""
import json
import re

import codice_web

_TESTI = codice_web.leggi("testi.js")


def _italiano() -> dict:
    blocco = _TESTI[_TESTI.index("  it: {"):_TESTI.index("\n  },", _TESTI.index("  it: {"))]
    return {k: json.loads(v) for k, v in re.findall(r'^\s*"([\w.]+)":\s*("(?:[^"\\]|\\.)*"),?\s*$', blocco, flags=re.M)}


ITALIANO = _italiano()


def espandi(codice: str) -> str:
    codice = re.sub(r'\$\{t\("([\w.]+)"\)\}', lambda m: ITALIANO.get(m.group(1), m.group(0)), codice)
    return re.sub(r'(?<![\w.])t\("([\w.]+)"\)', lambda m: json.dumps(ITALIANO[m.group(1)], ensure_ascii=False) if m.group(1) in ITALIANO else m.group(0), codice)
