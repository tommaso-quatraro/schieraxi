"""Grafo dei tipi Swift dell'app (#505): da un file cambiato alle viste «radice» delle schermate che lo mostrano.

Il codice si divide in pezzi di primo livello (una dichiarazione che comincia a inizio riga: struct, class, enum, protocol,
actor, typealias, extension, func, let, var). Un pezzo «usa» un altro se nel suo testo compare il nome dell'altro.
Dal file cambiato si risale a chi lo usa finché si arriva a una vista radice (lì ci si ferma) o a una «barriera» (gli oggetti
che tengono tutto, come AppModel: da lì in su ogni schermata sarebbe raggiunta).

Nomi di un pezzo: il tipo che dichiara; per un'estensione di un tipo dell'app il tipo esteso; per un'estensione di un tipo
esterno (View, String...) i nomi dei suoi membri (chi chiama `.bordino()` usa l'estensione che lo dichiara). Un pezzo
`private`/`fileprivate` vale solo nel suo file. Commenti e stringhe non contano. È una lettura a occhio del testo, non un
compilatore: sbaglia per eccesso (nomi uguali in file diversi), e per questo un file che arriva a troppe radici usa le regole
larghe di foto.json. Solo libreria standard."""
from __future__ import annotations

import re
from collections import defaultdict, deque
from pathlib import Path

_MODIFICATORI = (r"(?:@\w+(?:\([^)\n]*\))?\s+)*"
                 r"(?:(?:public|internal|private|fileprivate|final|open|indirect|nonisolated|static)\s+)*")
_INIZIO = re.compile(r"^" + _MODIFICATORI + r"(struct|class|enum|protocol|actor|typealias|extension|func|let|var)\s+"
                     r"([A-Za-z_]\w*)", re.M)
_TIPI = {"struct", "class", "enum", "protocol", "actor", "typealias"}
_MEMBRO = re.compile(r"\b(?:func|var|let|case|struct|enum|class|actor|protocol|typealias)\s+([A-Za-z_]\w*)")
_NOME = re.compile(r"\b[A-Za-z_]\w*\b")


def pulisci(testo: str) -> str:
    """Toglie commenti e contenuto delle stringhe; gli a capo restano (gli inizi di riga servono a trovare i pezzi)."""
    fuori, i, n = [], 0, len(testo)
    while i < n:
        if testo.startswith("//", i):
            j = testo.find("\n", i)
            i = n if j < 0 else j
        elif testo.startswith("/*", i):
            j = testo.find("*/", i + 2)
            j = n if j < 0 else j + 2
            fuori.append("\n" * testo.count("\n", i, j))
            i = j
        elif testo.startswith('"""', i):
            j = testo.find('"""', i + 3)
            j = n if j < 0 else j + 3
            fuori.append('""' + "\n" * testo.count("\n", i, j))
            i = j
        elif testo[i] == '"':
            j = i + 1
            while j < n and testo[j] not in '"\n':
                j += 2 if testo[j] == "\\" else 1
            fuori.append('""')
            i = j + 1
        else:
            fuori.append(testo[i])
            i += 1
    return "".join(fuori)


def _membri(corpo: str) -> set[str]:
    """Nomi dichiarati dentro la prima coppia di graffe (i membri di un'estensione)."""
    nomi, profondita, da = set(), 0, 0
    for m in re.finditer(r"[{}]", corpo):
        if profondita == 1:
            nomi |= set(_MEMBRO.findall(corpo[da:m.start()]))
        profondita += 1 if m.group() == "{" else -1
        da = m.end()
    return nomi


def pezzi(file: str, testo: str) -> list[dict]:
    t = pulisci(testo)
    inizi = list(_INIZIO.finditer(t))
    risultato = []
    for k, m in enumerate(inizi):
        fine = inizi[k + 1].start() if k + 1 < len(inizi) else len(t)
        corpo = t[m.end():fine]
        risultato.append({"file": file, "tipo": m.group(1), "nome": m.group(2), "corpo": corpo,
                          "privato": bool(re.search(r"\b(?:private|fileprivate)\b", t[m.start():m.start(2)]))})
    return risultato


def tipi_dichiarati(testo: str) -> set[str]:
    return {p["nome"] for p in pezzi("", testo) if p["tipo"] in _TIPI}


class Grafo:
    def __init__(self, testi: dict[str, str]):
        self.pezzi: list[dict] = []
        for f in sorted(testi):
            self.pezzi += pezzi(f, testi[f])
        self.dichiarati = {p["nome"] for p in self.pezzi if p["tipo"] in _TIPI}
        pubblici, privati = defaultdict(list), defaultdict(list)
        for i, p in enumerate(self.pezzi):
            if p["tipo"] == "extension" and p["nome"] not in self.dichiarati:
                nomi = _membri(p["corpo"])
            else:
                nomi = {p["nome"]}
            for nome in nomi:
                (privati[(p["file"], nome)] if p["privato"] else pubblici[nome]).append(i)
        self.usato_da: dict[int, set[int]] = defaultdict(set)
        for j, p in enumerate(self.pezzi):
            for nome in set(_NOME.findall(p["corpo"])):
                for i in pubblici.get(nome, []) + privati.get((p["file"], nome), []):
                    if i != j:
                        self.usato_da[i].add(j)

    def radici(self, file: str, radici: set[str], barriere: set[str]) -> dict[str, list[str]]:
        """Viste radice raggiunte risalendo da `file`, ciascuna con la strada (nomi dei pezzi, dalla radice al file)."""
        partenza = [i for i, p in enumerate(self.pezzi) if p["file"] == file]
        visti, coda, da, trovate = set(partenza), deque(partenza), {}, {}
        while coda:
            i = coda.popleft()
            p = self.pezzi[i]
            if p["nome"] in radici and not p["privato"]:
                if p["nome"] not in trovate:
                    strada, k = [p["nome"]], i
                    while k in da:
                        k = da[k]
                        strada.append(self.pezzi[k]["nome"])
                    trovate[p["nome"]] = strada
                continue
            if p["nome"] in barriere and i not in partenza:
                continue
            for j in sorted(self.usato_da[i]):
                if j not in visti:
                    visti.add(j)
                    da[j] = i
                    coda.append(j)
        return trovate


def leggi(radice: Path) -> dict[str, str]:
    """I file Swift dell'app (ios/Sources) letti dal disco."""
    return {p.relative_to(radice).as_posix(): p.read_text(encoding="utf-8")
            for p in sorted((radice / "ios" / "Sources").rglob("*.swift"))}
