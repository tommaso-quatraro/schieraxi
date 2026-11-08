"""Contratto fra iPhone e server, controllato su Linux e Windows (senza Mac e senza rete).

L'OpenAPI non descrive le risposte (le rotte restituiscono dizionari), quindi i modelli Swift non si possono generare da lì.
Al loro posto questo controllo: ogni campo dei modelli `Decodable` dell'iPhone, tradotto nel nome JSON, deve comparire come
chiave nel codice del server (`fanta/`). Prende le rinomine e i campi tolti nella stessa pull request. I tipi sbagliati li
prende l'altro controllo, sul Mac (test Swift sulle risposte vere di `ios/fotografie/vero-*.json`).

Usato da `tests/test_contratto_ios.py`:
- `campi_swift(cartelle)`: i campi letti dall'iPhone (`Campo`);
- `chiavi_server(cartella)`: le chiavi che il server scrive nelle risposte;
- `campi_mancanti`, `eccezioni_vecchie`, `messaggio`, `rotte_probabili`.

Il lettore Swift è volutamente semplice (niente compilatore): toglie i commenti e il contenuto delle stringhe, segue le
graffe e legge le dichiarazioni. Le eccezioni (campi riempiti sul telefono, dati non del server) stanno in
`tests/dati/contratto_ios_eccezioni.json`, ognuna con il suo motivo.
"""
from __future__ import annotations

import ast
import bisect
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
CARTELLE_SWIFT = [RADICE / "ios" / "Sources", RADICE / "ios" / "WidgetSources"]
ECCEZIONI = Path(__file__).resolve().parent / "dati" / "contratto_ios_eccezioni.json"


@dataclass(frozen=True)
class Campo:
    struttura: str   # nome completo, con le strutture che la contengono: «StatoDati.Partite»
    nome_swift: str  # la proprietà o il caso di CodingKeys
    nome_json: str   # la chiave che l'iPhone si aspetta dal server (in snake_case)
    file: str        # percorso dalla radice del repository, con «/»
    riga: int
    chiave_swift: str = ""  # il valore tra virgolette del caso di CodingKeys, se c'è (altrimenti vale `nome_swift`)

    @property
    def voce(self) -> str:
        """Come si scrive nel file delle eccezioni: «Struttura.campo»."""
        return f"{self.struttura}.{self.nome_swift}"


# ---------------------------------------------------------------- nomi

def nome_json(nome: str) -> str:
    """Da camelCase al nome JSON: `pVoto` → `p_voto`. Un nome senza maiuscole resta com'è (`promemoria_60`, `id`)."""
    return re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", nome).lower() if any(c.isupper() for c in nome) else nome


def da_snake(chiave: str) -> str:
    """Come `convertFromSnakeCase` di `JSONDecoder` (Foundation): `p_voto` → `pVoto`, `I2_calibrazione` → `i2Calibrazione`.
    Le «_» iniziali e finali restano; una parola sola resta com'è."""
    inizio = len(chiave) - len(chiave.lstrip("_"))
    fine = len(chiave.rstrip("_"))
    if inizio >= fine:
        return chiave
    parti = [p for p in chiave[inizio:fine].split("_") if p]
    if len(parti) == 1:
        corpo = chiave[inizio:fine]
    else:
        corpo = parti[0].lower() + "".join(p[:1].upper() + p[1:].lower() for p in parti[1:])
    return chiave[:inizio] + corpo + chiave[fine:]


# ---------------------------------------------------------------- lettore Swift

def _pulisci(testo: str) -> str:
    """Stessa lunghezza e stesse righe: commenti → spazi; dentro le stringhe `{`, `}`, `;`, `,` → spazi (l'interpolazione
    `\\( … )` resta codice). Così graffe e separatori contano solo nel codice; i valori tra virgolette restano leggibili."""
    out = list(testo)
    n = len(testo)
    pila: list[list] = [["codice", 0]]  # codice | interp (con la profondità delle parentesi) | str | str3 | raw
    i = 0
    while i < n:
        modo = pila[-1]
        c = testo[i]
        if modo[0] in ("codice", "interp"):
            if testo.startswith("//", i):
                j = testo.find("\n", i)
                j = n if j < 0 else j
                out[i:j] = " " * (j - i)
                i = j
                continue
            if testo.startswith("/*", i):
                j = testo.find("*/", i + 2)
                j = n if j < 0 else j + 2
                out[i:j] = ["\n" if ch == "\n" else " " for ch in testo[i:j]]
                i = j
                continue
            if testo.startswith('#"', i):
                pila.append(["raw", 0])
                i += 2
            elif testo.startswith('"""', i):
                pila.append(["str3", 0])
                i += 3
            elif c == '"':
                pila.append(["str", 0])
                i += 1
            else:
                if modo[0] == "interp":
                    if c == "(":
                        modo[1] += 1
                    elif c == ")":
                        if modo[1] == 0:
                            pila.pop()
                        else:
                            modo[1] -= 1
                i += 1
            continue
        # dentro una stringa
        if modo[0] == "raw" and testo.startswith('"#', i):
            pila.pop()
            i += 2
            continue
        if modo[0] != "raw" and c == "\\":
            if testo.startswith("\\(", i):
                pila.append(["interp", 0])
            i += 2
            continue
        if modo[0] == "str3" and testo.startswith('"""', i):
            pila.pop()
            i += 3
            continue
        if modo[0] == "str" and c == '"':
            pila.pop()
            i += 1
            continue
        if c in "{};,":
            out[i] = " "
        i += 1
    return "".join(out)


_TIPO = re.compile(
    r"\b(struct|class|enum|extension|actor|protocol)\s+([A-Za-z_][\w.]*)\s*(<[^{]*?>)?\s*(?::\s*([^{]*?))?"
    r"\s*(?:\bwhere\b[^{]*)?$"
)
_INIT_DECODER = re.compile(r"\binit\s*\(\s*from\s+decoder\s*:\s*(?:any\s+)?Decoder\s*\)[^{]*$")
_PROPRIETA = re.compile(
    r"^\s*(?:@[\w.]+(?:\([^)]*\))?\s+)*"
    r"(?P<mod>(?:(?:private|fileprivate|public|internal|open)(?:\(set\))?\s+|static\s+|class\s+|lazy\s+|weak\s+"
    r"|unowned\s+|final\s+|nonisolated\s+|override\s+)*)"
    r"(?P<decl>let|var)\s+(?P<nome>[A-Za-z_]\w*)\s*(?::\s*(?P<tipo>[^={]+?))?\s*(?P<valore>=[^{]*?)?\s*"
    r"(?P<corpo>\{\w*\}.*)?$"
)
_CASO = re.compile(r"^\s*(?:indirect\s+)?case\s+(.+)$")
_DECODABLE = re.compile(r"\b(Codable|Decodable)\b")
_TIPI_CON_CAMPI = ("struct", "class", "actor")
_TIPI = ("struct", "class", "enum", "extension", "actor", "protocol")


@dataclass
class _Ambito:
    tipo: str        # struct | class | enum | extension | actor | protocol | init | blocco | file
    nome: str        # nome completo per i tipi, "" per gli altri
    inizio: int      # posizione della «{»
    eredita: str = ""
    testo: list = field(default_factory=list)      # caratteri al primo livello dell'ambito ({…} ridotti a «{parola}»)
    posizioni: list = field(default_factory=list)  # posizione nel file di ogni carattere di `testo`
    chiavi: list = field(default_factory=list)     # (enum, caso, valore tra virgolette o None, riga) delle enum CodingKey
    inits: list = field(default_factory=list)      # corpi di `init(from decoder:)`


@dataclass
class _Tipo:
    nome: str
    tipo: str
    decodable: bool
    file: str
    proprieta: list   # (nome, tipo dichiarato, è un `let` con il valore già scritto, riga)
    chiavi: list
    inits: list


@dataclass
class _Lettura:
    tipi: list = field(default_factory=list)
    estensioni: dict = field(default_factory=dict)  # nome → {"decodable": bool, "chiavi": [...], "inits": [...]}


def _istruzioni(amb: _Ambito) -> list[tuple[str, int]]:
    """Le istruzioni al primo livello dell'ambito (divise su a capo e «;»), con la posizione del primo carattere."""
    testo = "".join(amb.testo)
    fuori, inizio = [], 0
    for k, ch in enumerate(testo + "\n"):
        if ch in "\n;":
            pezzo = testo[inizio:k]
            if pezzo.strip():
                fuori.append((pezzo, amb.posizioni[inizio + len(pezzo) - len(pezzo.lstrip())]))
            inizio = k + 1
    return fuori


def _leggi_file(percorso: Path, relativo: str, lettura: _Lettura) -> None:
    pulito = _pulisci(percorso.read_text(encoding="utf-8"))
    a_capo = [i for i, c in enumerate(pulito) if c == "\n"]

    def riga(pos: int) -> int:
        return bisect.bisect_left(a_capo, pos) + 1

    pila = [_Ambito("file", "", -1)]
    confine = 0  # dopo l'ultima «{», «}» o «;»: da qui comincia l'intestazione di un blocco

    def tipo_vicino() -> _Ambito | None:
        return next((a for a in reversed(pila) if a.tipo in _TIPI), None)

    def chiudi(amb: _Ambito, fine: int) -> None:
        if amb.tipo == "init":
            dove = tipo_vicino()
            if dove is not None:
                dove.inits.append(pulito[amb.inizio:fine])
            return
        if amb.tipo not in _TIPI:
            return
        istruzioni = _istruzioni(amb)
        if amb.tipo == "enum" and re.search(r"\bCodingKey\b", amb.eredita):
            dove = tipo_vicino()  # l'enum è già tolta dalla pila: questo è il tipo che la contiene
            if dove is not None:
                nome_enum = amb.nome.rsplit(".", 1)[-1]
                for frase, p in istruzioni:
                    m = _CASO.match(frase)
                    for pezzo in (m.group(1).split(",") if m else []):
                        mm = re.match(r'\s*([A-Za-z_]\w*)\s*(?:=\s*"([^"]*)")?\s*$', pezzo)
                        if mm:
                            dove.chiavi.append((nome_enum, mm.group(1), mm.group(2), riga(p)))
        if amb.tipo == "extension":
            info = lettura.estensioni.setdefault(amb.nome, {"decodable": False, "chiavi": [], "inits": []})
            info["decodable"] |= bool(_DECODABLE.search(amb.eredita))
            info["chiavi"] += amb.chiavi
            info["inits"] += amb.inits
            return
        proprieta = []
        for frase, p in istruzioni:
            m = _PROPRIETA.match(frase)
            if not m or re.search(r"\b(static|class|lazy)\b", m.group("mod")):
                continue
            corpo = m.group("corpo") or ""
            if corpo and not m.group("valore") and not re.match(r"\{(willSet|didSet)\b", corpo):
                continue  # proprietà calcolata
            let_con_valore = m.group("decl") == "let" and bool(m.group("valore"))
            proprieta.append((m.group("nome"), (m.group("tipo") or "").strip(), let_con_valore, riga(p)))
        lettura.tipi.append(_Tipo(amb.nome, amb.tipo, bool(_DECODABLE.search(amb.eredita)), relativo, proprieta,
                                  amb.chiavi, amb.inits))

    for pos, c in enumerate(pulito):
        corrente = pila[-1]
        if c == "{":
            intestazione = pulito[confine:pos]
            m = _TIPO.search(intestazione)
            if m:
                tipo, nome = m.group(1), m.group(2)
                padre = next((a.nome for a in reversed(pila) if a.nome), "")
                completo = nome if tipo == "extension" or not padre else f"{padre}.{nome}"
                nuovo = _Ambito(tipo, completo, pos, eredita=re.sub(r"\s+", " ", m.group(4) or ""))
            elif _INIT_DECODER.search(intestazione):
                nuovo = _Ambito("init", "", pos)
            else:
                nuovo = _Ambito("blocco", "", pos)
            parola = re.match(r"\s*(\w*)", pulito[pos + 1:pos + 40]).group(1)
            corrente.testo.extend("{" + parola)
            corrente.posizioni.extend([pos] * (1 + len(parola)))
            pila.append(nuovo)
            confine = pos + 1
        elif c == "}":
            if len(pila) > 1:
                chiuso = pila.pop()
                chiudi(chiuso, pos)
                pila[-1].testo.append("}")
                pila[-1].posizioni.append(pos)
            confine = pos + 1
        else:
            if c == ";":
                confine = pos + 1
            corrente.testo.append(c)
            corrente.posizioni.append(pos)


def _leggi_tutto(cartelle: list[Path], radice: Path | None) -> _Lettura:
    radice = Path(radice or RADICE).resolve()
    lettura = _Lettura()
    for cartella in cartelle:
        for percorso in sorted(Path(cartella).rglob("*.swift")):
            _leggi_file(percorso, percorso.resolve().relative_to(radice).as_posix(), lettura)
    return lettura


def campi_swift(cartelle: list[Path], radice: Path | None = None) -> list[Campo]:
    """I campi che l'iPhone legge con `Decodable` (struct e class; le enum hanno valori, non campi):

    - con un `init(from:)` scritto a mano: i casi delle enum `CodingKey` del tipo; se non ce ne sono e l'init usa `forKey`,
      le CodingKeys implicite (cioè le proprietà memorizzate); senza `forKey` (contenitori come `Tollerante<T>`) nessun campo;
    - senza init a mano: i casi di `CodingKeys` se c'è, altrimenti le proprietà memorizzate (non `static`, non `lazy`, non
      calcolate, non `let` con il valore già scritto, che `Decodable` non legge).
    """
    lettura = _leggi_tutto(cartelle, radice)
    campi: list[Campo] = []
    for t in sorted(lettura.tipi, key=lambda t: (t.nome, t.file)):
        info = lettura.estensioni.get(t.nome, {"decodable": False, "chiavi": [], "inits": []})
        if t.tipo not in _TIPI_CON_CAMPI or not (t.decodable or info["decodable"]):
            continue
        chiavi, inits = t.chiavi + info["chiavi"], t.inits + info["inits"]
        if inits:
            if chiavi:
                scelte = chiavi
            elif any("forKey" in corpo for corpo in inits):
                scelte = None
            else:
                continue
        else:
            scelte = [c for c in chiavi if c[0] == "CodingKeys"] or None
        if scelte is None:
            campi += [Campo(t.nome, p, nome_json(p), t.file, r) for p, _tipo, con_valore, r in t.proprieta if not con_valore]
            continue
        visti = set()
        for _enum, caso, valore, r in scelte:
            if caso not in visti:
                visti.add(caso)
                campi.append(Campo(t.nome, caso, nome_json(valore if valore is not None else caso), t.file, r, valore or ""))
    return campi


# ---------------------------------------------------------------- rotte (solo per il messaggio)

_NOME_TIPO = re.compile(r"\b[A-Z]\w*\b")
_ROTTA = re.compile(r'"(/api/[^"?\\]*)')


def rotte_probabili(cartelle: list[Path], radice: Path | None = None) -> dict[str, list[str]]:
    """Struttura → rotte che probabilmente la riempiono: le righe Swift con `"/api/..."` e il nome del tipo, poi i tipi dei
    campi a cascata. Serve solo a rendere più utile il messaggio: può mancare o abbondare."""
    lettura = _leggi_tutto(cartelle, radice)
    per_semplice: dict[str, set[str]] = {}
    for t in lettura.tipi:
        per_semplice.setdefault(t.nome.rsplit(".", 1)[-1], set()).add(t.nome)

    def risolvi(semplice: str, dentro: str) -> set[str]:
        """Il tipo annidato più vicino con quel nome; se non c'è, tutti quelli con quel nome."""
        candidati = per_semplice.get(semplice, set())
        parti = dentro.split(".")
        for k in range(len(parti), -1, -1):
            pieno = ".".join(parti[:k] + [semplice])
            if pieno in candidati:
                return {pieno}
        return set(candidati)

    rotte: dict[str, set[str]] = {}
    for cartella in cartelle:
        for percorso in sorted(Path(cartella).rglob("*.swift")):
            for linea in percorso.read_text(encoding="utf-8").splitlines():
                trovate = _ROTTA.findall(linea)
                if not trovate or linea.lstrip().startswith("//"):
                    continue
                for semplice in set(_NOME_TIPO.findall(linea)):
                    for pieno in per_semplice.get(semplice, ()):
                        rotte.setdefault(pieno, set()).update(trovate)
    figli: dict[str, set[str]] = {}
    for t in lettura.tipi:
        for _p, tipo, _l, _r in t.proprieta:
            for semplice in _NOME_TIPO.findall(tipo):
                figli.setdefault(t.nome, set()).update(risolvi(semplice, t.nome))
    cambiato = True
    while cambiato:
        cambiato = False
        for padre, sotto in figli.items():
            for figlio in sotto:
                nuove = rotte.get(padre, set()) - rotte.get(figlio, set())
                if nuove:
                    rotte.setdefault(figlio, set()).update(nuove)
                    cambiato = True
    return {nome: sorted(r) for nome, r in rotte.items()}


# ---------------------------------------------------------------- chiavi del server

def chiavi_server(cartella: Path) -> set[str]:
    """Le chiavi che il codice Python del server può scrivere in una risposta (`cartella/**/*.py`): chiavi di testo dei
    dizionari `{...}`, argomenti `nome=` di `dict(...)` e `.update(...)`, campi annotati nelle classi (dataclass,
    `TypedDict`, modelli Pydantic), `x["nome"] = ...`, `x.setdefault("nome", ...)` e le chiavi delle comprensioni su testi
    fissi (`{k: … for k in ("gol", "assist")}`, anche con una tupla del modulo)."""
    chiavi: set[str] = set()

    def testo(nodo) -> str | None:
        return nodo.value if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str) else None

    def testi_fissi(nodo, costanti: dict[str, list[str]]) -> list[str]:
        """I testi di una tupla, lista o insieme scritti nel codice, anche attraverso un nome del modulo (`TIPI`)."""
        if isinstance(nodo, ast.Name):
            return costanti.get(nodo.id, [])
        if isinstance(nodo, (ast.Tuple, ast.List, ast.Set)):
            valori = [testo(e) for e in nodo.elts]
            return [v for v in valori if v is not None] if all(v is not None for v in valori) else []
        return []

    for percorso in sorted(Path(cartella).rglob("*.py")):
        albero = ast.parse(percorso.read_text(encoding="utf-8"), filename=str(percorso))
        costanti = {}
        for s in albero.body:
            if isinstance(s, ast.Assign) and len(s.targets) == 1 and isinstance(s.targets[0], ast.Name):
                costanti[s.targets[0].id] = testi_fissi(s.value, {})
        for nodo in ast.walk(albero):
            if isinstance(nodo, ast.DictComp) and isinstance(nodo.key, ast.Name):
                # {k: … for k in ("gol", "assist")} oppure {t: … for t in TIPI}
                for gen in nodo.generators:
                    if isinstance(gen.target, ast.Name) and gen.target.id == nodo.key.id:
                        chiavi.update(testi_fissi(gen.iter, costanti))
            elif isinstance(nodo, ast.Dict):
                chiavi.update(k for k in map(testo, filter(None, nodo.keys)) if k is not None)
            elif isinstance(nodo, ast.Call):
                f = nodo.func
                nome = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ""
                if nome in ("dict", "update"):
                    chiavi.update(k.arg for k in nodo.keywords if k.arg)
                elif nome == "setdefault" and nodo.args and testo(nodo.args[0]) is not None:
                    chiavi.add(testo(nodo.args[0]))
            elif isinstance(nodo, ast.ClassDef):
                chiavi.update(s.target.id for s in nodo.body if isinstance(s, ast.AnnAssign) and isinstance(s.target, ast.Name))
            elif isinstance(nodo, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
                for b in (nodo.targets if isinstance(nodo, ast.Assign) else [nodo.target]):
                    if isinstance(b, ast.Subscript) and testo(b.slice) is not None:
                        chiavi.add(testo(b.slice))
    return chiavi


def indice_chiavi(chiavi: set[str]) -> set[str]:
    """Le chiavi come le può vedere l'iPhone: così come sono (decodificatore senza conversione) e convertite da snake_case
    (`convertFromSnakeCase`, il decodificatore di base dell'app)."""
    return set(chiavi) | {da_snake(k) for k in chiavi}


def trovato(campo: Campo, indice: set[str]) -> bool:
    """La chiave Swift (valore del caso di CodingKeys o nome) corrisponde a una chiave del server, con o senza conversione."""
    return (campo.chiave_swift or campo.nome_swift) in indice


# ---------------------------------------------------------------- eccezioni e messaggio

def carica_eccezioni(percorso: Path = ECCEZIONI) -> dict[str, str]:
    return json.loads(percorso.read_text(encoding="utf-8"))


def _coperto(campo: Campo, eccezioni: dict[str, str]) -> bool:
    return campo.voce in eccezioni or campo.struttura in eccezioni


def campi_mancanti(campi: list[Campo], indice: set[str], eccezioni: dict[str, str]) -> list[Campo]:
    return [c for c in campi if not trovato(c, indice) and not _coperto(c, eccezioni)]


def eccezioni_vecchie(campi: list[Campo], indice: set[str], eccezioni: dict[str, str]) -> list[str]:
    """Eccezioni senza motivo, per strutture o campi che non ci sono più, doppie, o per campi che il server ormai manda."""
    problemi = []
    per_voce: dict[str, list[Campo]] = {}
    per_struttura: dict[str, list[Campo]] = {}
    for c in campi:
        per_voce.setdefault(c.voce, []).append(c)
        per_struttura.setdefault(c.struttura, []).append(c)
    for voce, motivo in eccezioni.items():
        if not isinstance(motivo, str) or len(motivo.strip()) < 15:
            problemi.append(f"«{voce}»: manca il motivo (una frase che dica perché il server non manda il campo)")
        if voce in per_voce:
            if all(trovato(c, indice) for c in per_voce[voce]):
                problemi.append(f"«{voce}»: il server ora manda «{per_voce[voce][0].nome_json}», togli l'eccezione")
            elif per_voce[voce][0].struttura in eccezioni:
                problemi.append(f"«{voce}»: c'è già l'eccezione per tutta «{per_voce[voce][0].struttura}», togli questa")
        elif voce in per_struttura:
            if all(trovato(c, indice) for c in per_struttura[voce]):
                problemi.append(f"«{voce}»: tutti i suoi campi ora ci sono nel server, togli l'eccezione")
        else:
            problemi.append(f"«{voce}»: non c'è più tra i modelli Decodable dell'iPhone, togli l'eccezione")
    return problemi


def messaggio(mancanti: list[Campo], rotte: dict[str, list[str]]) -> str:
    righe = [f"{len(mancanti)} campi letti dall'iPhone non compaiono come chiave nel codice del server (fanta/):"]
    for c in sorted(mancanti, key=lambda c: (c.file, c.riga)):
        dove = rotte.get(c.struttura) or []
        rotta = ", ".join(dove[:4]) + (f" e altre {len(dove) - 4}" if len(dove) > 4 else "") if dove \
            else "nessuna trovata nel codice Swift"
        righe.append(f"- {c.file}:{c.riga}  {c.voce} → chiave «{c.nome_json}» (rotte probabili: {rotta})")
    righe += [
        "Come rimediare:",
        "- il server ha tolto o rinominato la chiave: rimettila nel server o aggiorna il modello dell'iPhone nella stessa PR;",
        "- il campo è nuovo sull'iPhone: prima va aggiunto alla risposta del server;",
        "- il campo non arriva dal server di proposito (riempito sul telefono, dati salvati in locale, campo facoltativo per un",
        "  server più nuovo): aggiungi in tests/dati/contratto_ios_eccezioni.json \"Struttura.campo\" (o \"Struttura\")",
        "  con il motivo.",
    ]
    return "\n".join(righe)
