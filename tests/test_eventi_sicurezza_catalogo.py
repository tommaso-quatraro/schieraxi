"""Ogni evento del registro di sicurezza ha il suo nome in parole nel catalogo (#779).

Impostazioni › Gestione › «Errori recenti» mostra gli eventi di `GET /api/admin/registro` con la chiave `errori.evento_<tipo>`
(fanta/testi/errori.json; nel tipo il trattino conta come il trattino basso, `fonte-cambiata` → `errori.evento_fonte_cambiata`):
senza, l'amministratore leggerebbe il nome interno. I tipi si leggono dal codice del server con `ast`:
- le chiamate a `evento(...)` (anche `account.evento` e `_evento` della posta) con un testo fisso, e quelle composte
  `evento(prefisso + "_bloccato")` dei tentativi di accesso, recupero e iscrizione (i prefissi sono quelli passati a
  `_prenota_tentativo` e `_fallimento`);
- le righe scritte direttamente nel registro di sicurezza, `registro.scrivi(… FILE_SICUREZZA, f"{registro.adesso()} <tipo> …")`
  (l'interruttore di una fonte o di una funzione, in rotte_account.py).
Una forma nuova che il controllo non sa leggere lo fa fallire: va insegnata qui."""
import ast
import json
import re
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


def _nel_registro_di_sicurezza(n: ast.Call) -> bool:
    return _nome(n.func) == "scrivi" and bool(n.args) and any(
        isinstance(x, ast.Attribute) and x.attr == "FILE_SICUREZZA" for x in ast.walk(n.args[0]))


def _tipo_della_riga(riga: ast.expr) -> str | None:
    """Il tipo di una riga scritta a mano: la prima parola dopo l'ora (`f"{registro.adesso()} fonte-cambiata …"`)."""
    if not isinstance(riga, ast.JoinedStr):
        return None
    testo = "".join(v.value if isinstance(v, ast.Constant) else "\0" for v in riga.values)
    m = re.match(r"\0 ([a-z][a-z_-]*)\s", testo)
    return m.group(1) if m else None


def tipi_di_evento(cartella: Path = RADICE / "fanta") -> tuple[set[str], list[str]]:
    """(tipi trovati, scritte che il controllo non sa leggere con file e riga)."""
    fissi, finali, prefissi, ignote = set(), set(), set(), []
    for f in sorted(cartella.rglob("*.py")):
        albero = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
        dove = f.relative_to(RADICE).as_posix()
        # dentro `evento` e `_evento` il tipo arriva da chi chiama: lì non si legge
        inoltri = {id(c) for d in ast.walk(albero) if isinstance(d, ast.FunctionDef) and d.name in NOMI_EVENTO
                   for c in ast.walk(d) if isinstance(c, ast.Call)}
        for n in ast.walk(albero):
            if not isinstance(n, ast.Call) or not n.args or id(n) in inoltri:
                continue
            nome, primo = _nome(n.func), n.args[0]
            if nome == "_prenota_tentativo" and len(n.args) > 1 and isinstance(n.args[1], ast.Constant):
                prefissi.add(n.args[1].value)
            elif nome == "_fallimento" and isinstance(primo, ast.Constant):
                prefissi.add(primo.value)
            elif nome in NOMI_EVENTO:
                if isinstance(primo, ast.Constant) and isinstance(primo.value, str):
                    fissi.add(primo.value)
                elif (isinstance(primo, ast.BinOp) and isinstance(primo.op, ast.Add) and isinstance(primo.left, ast.Name)
                      and primo.left.id == "prefisso" and isinstance(primo.right, ast.Constant)):
                    finali.add(primo.right.value)
                else:
                    ignote.append(f"{dove}:{n.lineno}: {ast.unparse(n)[:80]}")
            elif _nel_registro_di_sicurezza(n):
                tipo = _tipo_della_riga(n.args[1]) if len(n.args) > 1 else None
                if tipo:
                    fissi.add(tipo)
                else:
                    ignote.append(f"{dove}:{n.lineno}: {ast.unparse(n)[:80]}")
    return {t.replace("-", "_") for t in fissi | {p + s for p in prefissi for s in finali}}, ignote


def test_ogni_evento_di_sicurezza_ha_il_nome_nel_catalogo():
    tipi, ignote = tipi_di_evento()
    assert not ignote, "scritte nel registro di sicurezza che il controllo non sa leggere:\n" + "\n".join(ignote)
    assert {"ruolo_cambiato", "accesso_fallito", "recupero_bloccato", "iscrizione_rallentamento_pieno",
            "fonte_cambiata", "funzione_cambiata"} <= tipi, sorted(tipi)
    catalogo = json.loads(CATALOGO.read_text(encoding="utf-8"))
    mancano = sorted(t for t in tipi if f"{PREFISSO}{t}" not in catalogo)
    assert not mancano, f"aggiungi in fanta/testi/errori.json le chiavi {PREFISSO}<tipo> (italiano e inglese): {mancano}"
    in_piu = sorted(k for k in catalogo if k.startswith(PREFISSO) and k.removeprefix(PREFISSO) not in tipi)
    assert not in_piu, f"eventi che il server non scrive più: togli le chiavi {in_piu}"


def test_il_controllo_legge_le_righe_scritte_a_mano():
    riga = ast.parse('scrivi(p / registro.FILE_SICUREZZA, f"{registro.adesso()} fonte-cambiata utente={u}")').body[0].value
    assert _nel_registro_di_sicurezza(riga) and _tipo_della_riga(riga.args[1]) == "fonte-cambiata"
    altro = ast.parse('scrivi(p / registro.FILE_ERRORI, f"{registro.adesso()} errore x")').body[0].value
    assert not _nel_registro_di_sicurezza(altro)


def test_gli_eventi_importanti_sono_tipi_che_il_server_scrive():
    """`account.EVENTI_IMPORTANTI` (copiati nel registro a parte che Gestione mostra anche dopo tanti accessi sbagliati) ha solo
    tipi che il server scrive davvero: un nome scritto male non verrebbe mai copiato, senza che nessuno se ne accorga. E nessun
    tentativo sbagliato o rifiutato, che chiunque può ripetere quante volte vuole."""
    from fanta import account
    tipi, _ = tipi_di_evento()
    assert account.EVENTI_IMPORTANTI <= tipi, sorted(account.EVENTI_IMPORTANTI - tipi)
    ripetibili = {p + s for p in ("accesso", "recupero", "iscrizione") for s in ("_fallito", "_bloccato", "_rallentamento_pieno")}
    ripetibili |= {"accesso_negato_bloccato", "registrazione_invito_sbagliato", "registrazione_trappola", "email_codice_sbagliato",
                   "social_rifiutato", "social_inizio", "iscrizione_richiesta", "recupero_email_richiesto", "email_verifica_richiesta"}
    assert ripetibili <= tipi, sorted(ripetibili - tipi)
    assert not account.EVENTI_IMPORTANTI & ripetibili, sorted(account.EVENTI_IMPORTANTI & ripetibili)
