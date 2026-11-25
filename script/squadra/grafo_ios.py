"""Grafo dei tipi Swift dell'app (#505): da un file cambiato alle viste «radice» delle schermate che lo mostrano.

Il codice si divide in pezzi di primo livello (una dichiarazione che comincia a inizio riga: struct, class, enum, protocol,
actor, typealias, extension, func, let, var). Un pezzo «usa» un altro se nel suo testo compare il nome dell'altro.
Dal file cambiato si risale a chi lo usa finché si arriva a una vista radice (lì ci si ferma, salvo le radici «annidate»
dentro un'altra) o a una «barriera» (gli oggetti che tengono tutto, come AppModel: da lì in su ogni schermata sarebbe
raggiunta).

Nomi di un pezzo: il tipo che dichiara; per un'estensione di un tipo dell'app il tipo esteso; per un'estensione di un tipo
esterno (View, String...) i nomi dei suoi membri (chi chiama `.bordino()` usa l'estensione che lo dichiara). Un pezzo
`private`/`fileprivate` vale solo nel suo file. Commenti e testo delle stringhe non contano; il codice delle interpolazioni
(`"\\(Formato.euro(x))"`) sì. È una lettura a occhio del testo, non un compilatore: sbaglia per eccesso (nomi uguali in file
diversi) e per difetto (usi che il testo non mostra), e per questo le regole a mano strette vincono e un file che arriva a
troppe radici usa le regole larghe di foto.json. Solo libreria standard."""
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
    """Toglie commenti e testo delle stringhe; restano gli a capo (gli inizi di riga servono a trovare i pezzi) e il codice
    delle interpolazioni (`"\\(Formato.euro(x))"` usa Formato)."""
    return _codice(testo, 0, False)[0]


def _codice(testo: str, i: int, dentro_interpolazione: bool) -> tuple[str, int]:
    """Codice da `i` alla fine (o alla «)» che chiude un'interpolazione): (testo pulito, posizione dopo)."""
    fuori, n, aperte = [], len(testo), 0
    while i < n:
        c = testo[i]
        if testo.startswith("//", i):
            j = testo.find("\n", i)
            i = n if j < 0 else j
        elif testo.startswith("/*", i):
            j = testo.find("*/", i + 2)
            j = n if j < 0 else j + 2
            fuori.append("\n" * testo.count("\n", i, j))
            i = j
        elif c == '"':
            pulita, i = _stringa(testo, i)
            fuori.append(pulita)
        elif dentro_interpolazione and c == ")" and aperte == 0:
            return "".join(fuori), i + 1
        else:
            aperte += (c == "(") - (c == ")")
            fuori.append(c)
            i += 1
    return "".join(fuori), i


def _stringa(testo: str, i: int) -> tuple[str, int]:
    """Una stringa che comincia in `i` (semplice o fra «\"\"\"»): ne tiene solo gli a capo e il codice delle interpolazioni."""
    lunga = testo.startswith('"""', i)
    chiusura = '"""' if lunga else '"'
    fuori, n = ['"'], len(testo)
    i += len(chiusura)
    while i < n:
        if testo.startswith(chiusura, i):
            return "".join(fuori) + '"', i + len(chiusura)
        if testo[i] == "\n":
            if not lunga:
                break
            fuori.append("\n")
        elif testo.startswith("\\(", i):
            interno, i = _codice(testo, i + 2, True)
            fuori.append(" " + interno + " ")
            continue
        elif testo[i] == "\\":
            i += 1
        i += 1
    return "".join(fuori) + '"', i


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

    def radici_dichiarate(self, file: str, radici: set[str]) -> list[str]:
        """Le viste radice dichiarate nel file stesso (un tipo o un'estensione non privati: per `radici()` l'estensione di
        una vista è la vista stessa), in ordine di nome."""
        return sorted({p["nome"] for p in self.pezzi if p["file"] == file and not p["privato"] and p["nome"] in radici
                       and (p["tipo"] in _TIPI or p["tipo"] == "extension")})

    def radici(self, file: str, radici: set[str], barriere: set[str],
               annidate: set[str] = frozenset()) -> dict[str, list[str]]:
        """Viste radice raggiunte risalendo da `file`, ciascuna con la strada (nomi dei pezzi, dalla radice al file).
        A una radice ci si ferma, tranne a quelle `annidate` (mostrate dentro un'altra radice, come AspettoSezione dentro
        ImpostazioniView): da lì si continua a risalire e si prendono anche le radici di fuori."""
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
                if p["nome"] not in annidate:
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
