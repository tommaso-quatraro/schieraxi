"""Ogni evento del registro di sicurezza ha il suo nome in parole nel catalogo (#779).

Impostazioni › Gestione › «Errori recenti» mostra gli eventi di `GET /api/admin/registro` con la chiave `errori.evento_<tipo>`
(fanta/testi/errori.json): senza, l'amministratore leggerebbe il nome interno con gli spazi al posto dei trattini bassi. I tipi si
leggono dal codice del server con `ast`: le chiamate a `evento(...)` (anche `account.evento` e `_evento` della posta) con un testo
fisso, e quelle composte `evento(prefisso + "_bloccato")` dei tentativi di accesso, recupero e iscrizione (i prefissi sono quelli
passati a `_prenota_tentativo` e `_fallimento`). Una forma nuova che il controllo non sa leggere lo fa fallire: va insegnata qui."""
import ast
import json
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
CATALOGO = RADICE / "fanta" / "testi" / "errori.json"
PREFISSO = "errori.evento_"
NOMI_EVENTO = {"evento", "_evento"}


def _nome(funzione: ast.expr) -> str | None:
    if isinstance(funzione, ast.Name):
        return funzione.id
    if isinstance(funzione, ast.Attribute):
        return funzione.attr
    return None


def tipi_di_evento(cartella: Path = RADICE / "fanta") -> tuple[set[str], list[str]]:
    """(tipi trovati, chiamate che il controllo non sa leggere con file e riga)."""
    fissi, finali, prefissi, ignote = set(), set(), set(), []
    for f in sorted(cartella.rglob("*.py")):
        albero = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
        dove = f.relative_to(RADICE).as_posix()
        inoltri = {id(c) for d in ast.walk(albero) if isinstance(d, ast.FunctionDef) and d.name in NOMI_EVENTO
                   for c in ast.walk(d) if isinstance(c, ast.Call)}          # `_evento(tipo)` passa il suo tipo a `account.evento`
        for n in ast.walk(albero):
            if not isinstance(n, ast.Call) or not n.args:
                continue
            nome, primo = _nome(n.func), n.args[0]
            if nome == "_prenota_tentativo" and len(n.args) > 1 and isinstance(n.args[1], ast.Constant):
                prefissi.add(n.args[1].value)
            elif nome == "_fallimento" and isinstance(primo, ast.Constant):
                prefissi.add(primo.value)
            elif nome in NOMI_EVENTO and id(n) not in inoltri:
                if isinstance(primo, ast.Constant) and isinstance(primo.value, str):
                    fissi.add(primo.value)
                elif (isinstance(primo, ast.BinOp) and isinstance(primo.op, ast.Add) and isinstance(primo.left, ast.Name)
                      and primo.left.id == "prefisso" and isinstance(primo.right, ast.Constant)):
                    finali.add(primo.right.value)
                else:
                    ignote.append(f"{dove}:{n.lineno}: {ast.unparse(n)[:80]}")
    return fissi | {p + s for p in prefissi for s in finali}, ignote


def test_ogni_evento_di_sicurezza_ha_il_nome_nel_catalogo():
    tipi, ignote = tipi_di_evento()
    assert not ignote, "chiamate a evento() che il controllo non sa leggere:\n" + "\n".join(ignote)
    assert {"ruolo_cambiato", "accesso_fallito", "recupero_bloccato", "iscrizione_rallentamento_pieno"} <= tipi, sorted(tipi)
    catalogo = json.loads(CATALOGO.read_text(encoding="utf-8"))
    mancano = sorted(t for t in tipi if f"{PREFISSO}{t}" not in catalogo)
    assert not mancano, f"aggiungi in fanta/testi/errori.json le chiavi {PREFISSO}<tipo> (italiano e inglese): {mancano}"
    in_piu = sorted(k for k in catalogo if k.startswith(PREFISSO) and k.removeprefix(PREFISSO) not in tipi)
    assert not in_piu, f"eventi che il server non scrive più: togli le chiavi {in_piu}"
