r"""Percorso automatico «amico nuovo»: l'ingresso di un amico invitato, fatto nel browser come lo farebbe lui.

Uso (dalla radice del repository; il Python è quello di un venv con Playwright, vedi LEGGIMI.md):
    <venv-playwright>\Scripts\python.exe prove\amico_nuovo\percorso.py <cartella fuori dal repository> (--locale | --remoto)
        [--telefono iphone|android] [--larghezza 360|390] [--formato testo|rosters|excel] [--a-secco]

`--locale`: avvia da solo un server di prova con gli account accesi (copia di `fanta/`, lega d'esempio, copia dell'archivio dei
dati di calcio), crea l'invito nella copia e lo ferma alla fine. `--remoto`: usa il server di `SCHIERAXI_INDIRIZZO` con l'invito di
`SCHIERAXI_INVITO` (solo dalle variabili d'ambiente). Indirizzo, invito, password e codici di recupero non si stampano e non si
scrivono mai nei file; nelle foto i campi che li mostrano sono coperti.

Passi: invito, registrazione, codice di recupero, requisiti per installare la web sulla Home, rose (nel formato scelto, costruite
al momento da `lega/esempio/rose.json`), squadra, tempi della lega, regole incollate, prima formazione, rientro con il codice di
recupero, cancellazione dell'account (sempre, anche se un passo prima non riesce). Solo con `--locale` anche l'invito già usato e
un file che non è delle rose. Ogni passo scrive una riga in `riepilogo.txt`:
    <passo> secondi=<s> tocchi=<n> errori-console=<n> gravi=<n> esito=<ok|bloccato|errore:<tipo>>
Esce con 0 se ogni passo è `ok` senza errori, 1 se almeno un passo non lo è, 2 con argomenti sbagliati.
"""
from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import os
import re
import secrets
import subprocess
import sys
import tempfile
import time
from contextlib import ExitStack
from pathlib import Path
from urllib.parse import quote, urlsplit

RADICE = Path(__file__).resolve().parent.parent.parent
ROSE_ESEMPIO = RADICE / "lega" / "esempio" / "rose.json"
REGOLE_TESTO = RADICE / "tests" / "test_regole_testo.py"        # il testo ESEMPIO delle regole, quello dei test


def _carica_foto():
    """`prove/foto_web/foto.py` come modulo: server di prova, copia dei dati, axe (si riusa, non si copia)."""
    spec = importlib.util.spec_from_file_location("foto_web", RADICE / "prove" / "foto_web" / "foto.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


foto = _carica_foto()

PASSI = ("invito", "registrazione", "recupero_salvato", "installabile", "rose", "squadra", "tempi", "regole", "formazione",
         "rientro", "elimina")
PASSI_LOCALI = ("invito_usato", "file_sbagliato")
FORMATI = ("testo", "rosters", "excel")
TELEFONI = {"iphone": "iPhone 13", "android": "Pixel 7"}
LARGHEZZE = (360, 390)
MIA_SQUADRA = "Real Esempio"
SCADENZA_MINUTI = 10
# Le risposte d'errore che un passo si aspetta (non sono errori): la pagina d'accesso chiede «chi sei?» e riceve 401, l'invito
# già usato dà 403, il file che non è delle rose dà 400. Tutte le altre risposte 4xx e 5xx contano come errori della console.
ATTESE = {
    "invito": {("/api/account/me", 401)},
    "rientro": {("/api/account/me", 401)},
    "invito_usato": {("/api/account/me", 401), ("/api/account/registra", 403)},
    "file_sbagliato": {("/api/rose/anteprima/file", 400), ("/api/rose/anteprima/file", 422)},
    "elimina": {("/api/account/me", 401)},
}
# Un passo si prova solo se sono riusciti quelli da cui dipende (altrimenti «bloccato» senza provarlo). `elimina` si fa sempre.
PRIMA = {
    "recupero_salvato": ("registrazione",), "file_sbagliato": ("recupero_salvato",), "rose": ("recupero_salvato",),
    "squadra": ("rose",), "tempi": ("squadra",), "regole": ("registrazione",), "formazione": ("squadra",),
    "rientro": ("registrazione",), "invito_usato": ("registrazione",),
}
NASCOSTO = "«nascosto»"


# =========================== parti senza browser ===========================
def ordine(locale: bool) -> tuple[str, ...]:
    """L'ordine in cui si fanno i passi: il file sbagliato subito prima delle rose (come capita a chi sbaglia file), l'invito
    già usato con un secondo browser dopo il rientro, la cancellazione sempre per ultima."""
    passi = ["invito", "registrazione", "recupero_salvato", "installabile", "file_sbagliato", "rose", "squadra", "tempi",
             "regole", "formazione", "rientro", "invito_usato", "elimina"]
    return tuple(p for p in passi if locale or p in PASSI)


def riga(passo: str, secondi: float, tocchi: int, errori_console: int, gravi: int, esito: str) -> str:
    return (f"{passo} secondi={secondi:.1f} tocchi={tocchi} errori-console={errori_console} gravi={gravi} esito={esito}")


_RIGA = re.compile(r"^(\S+) secondi=\S+ tocchi=\d+ errori-console=(\d+) gravi=(\d+) esito=(\S+)$")


def esito_complessivo(righe: list[str]) -> tuple[bool, list[str]]:
    """(vero solo se ogni passo è `ok` con 0 errori della console e 0 violazioni gravi, i problemi «<passo>: ...»)."""
    problemi = []
    for r in righe:
        m = _RIGA.match(r.strip())
        if not m:
            problemi.append(f"riga illeggibile: {r.strip()[:80]}")
            continue
        passo, errori, n_gravi, esito = m.group(1), int(m.group(2)), int(m.group(3)), m.group(4)
        parti = ([] if esito == "ok" else [esito]) + ([f"errori-console={errori}"] if errori else []) \
            + ([f"gravi={n_gravi}"] if n_gravi else [])
        if parti:
            problemi.append(f"{passo}: {', '.join(parti)}")
    return (bool(righe) and not problemi, problemi)


def risposta_attesa(passo: str, percorso: str, stato: int) -> bool:
    return (percorso, stato) in ATTESE.get(passo, set())


def oscura(testo: str, segreti) -> str:
    """Il testo senza nessuno dei segreti (prima i più lunghi: un indirizzo contiene il suo nome di host)."""
    for s in sorted({s for s in segreti if s and len(s) >= 4}, key=len, reverse=True):
        testo = testo.replace(s, NASCOSTO)
    return testo


def controlla_manifesto(m) -> list[str]:
    """I problemi del manifesto per l'installazione sulla Home: nome, icone 192 e 512, schermo intero, indirizzo di partenza."""
    if not isinstance(m, dict):
        return ["manifesto assente o illeggibile"]
    problemi = []
    if not (m.get("name") or m.get("short_name")):
        problemi.append("manca il nome")
    misure = {x for i in m.get("icons") or [] if isinstance(i, dict) for x in str(i.get("sizes", "")).split()}
    problemi += [f"manca l'icona {d}" for d in ("192x192", "512x512") if d not in misure]
    if m.get("display") not in ("standalone", "fullscreen"):
        problemi.append(f"display non a schermo intero: {m.get('display')!r}")
    if not m.get("start_url"):
        problemi.append("manca start_url")
    return problemi


def file_rose(rose_json: Path, formato: str, cartella: Path) -> Path:
    """Il file delle rose nel formato scelto, costruito al momento dalle rose d'esempio, nella cartella data (fuori dal
    repository). `testo`: colonne `ruolo;nome;club;prezzo`, una riga col solo nome per ogni fantasquadra; `rosters`: il CSV di
    Leghe, una riga «squadra,codice,costo» per giocatore e «$,$,$» tra una squadra e l'altra; `excel`: per ogni squadra il nome,
    l'intestazione e una riga per giocatore (serve `openpyxl`, che c'è nel .venv del repository)."""
    if formato not in FORMATI:
        raise ValueError(f"formato sconosciuto: {formato} (validi: {', '.join(FORMATI)})")
    squadre = json.loads(Path(rose_json).read_text(encoding="utf-8"))["squadre"]
    cartella = Path(cartella)
    cartella.mkdir(parents=True, exist_ok=True)
    if formato == "testo":
        righe = ["ruolo;nome;club;prezzo"]
        for s in squadre:
            righe.append(s["nome"])
            righe += [f"{g['ruolo']};{g['nome']};{g['squadra']};{g['costo']}" for g in s["giocatori"]]
        f = cartella / "rose.txt"
        f.write_text("\n".join(righe) + "\n", encoding="utf-8")
        return f
    if formato == "rosters":
        righe = []
        for i, s in enumerate(squadre):
            if i:
                righe.append("$,$,$")
            righe += [f"{s['nome']},{g['id']},{g['costo']}" for g in s["giocatori"]]
        f = cartella / "rosters.csv"
        f.write_text("\n".join(righe) + "\n", encoding="utf-8")
        return f
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Rose"
    for s in squadre:
        ws.append([s["nome"]])
        ws.append(["Ruolo", "Calciatore", "Squadra", "Costo"])
        for g in s["giocatori"]:
            ws.append([g["ruolo"], g["nome"], g["squadra"], g["costo"]])
        ws.append([])
    f = cartella / "rose.xlsx"
    wb.save(f)
    return f


def file_non_rose(cartella: Path) -> Path:
    """Un CSV che non è delle rose (un calendario inventato): l'app deve dire cosa riesportare."""
    f = Path(cartella) / "calendario.csv"
    f.write_text("Giornata,Casa,Ospite,Data\n1,Real Esempio,Atletico Prova,23/08\n1,Dinamo Finta,FC Segnaposto,23/08\n"
                 "2,Atletico Prova,Dinamo Finta,30/08\n2,FC Segnaposto,Real Esempio,30/08\n", encoding="utf-8")
    return f


def prepara_rose(formato: str, cartella: Path) -> Path:
    """`file_rose` qui se c'è `openpyxl`; altrimenti (venv di Playwright) con il Python del .venv, in un sottoprocesso."""
    if formato != "excel" or importlib.util.find_spec("openpyxl"):
        return file_rose(ROSE_ESEMPIO, formato, cartella)
    r = subprocess.run([foto.python_server(None), str(Path(__file__).resolve()), "--solo-file-rose", formato, str(cartella)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    if r.returncode != 0:
        sys.exit(f"File delle rose non creato (uscita {r.returncode}): {r.stderr.strip()[-300:]}")
    return Path(r.stdout.strip().splitlines()[-1])


def testo_regole_esempio() -> str:
    """Il testo ESEMPIO di tests/test_regole_testo.py (letto, non importato: i test non si eseguono)."""
    albero = ast.parse(REGOLE_TESTO.read_text(encoding="utf-8"))
    for nodo in albero.body:
        if isinstance(nodo, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "ESEMPIO" for t in nodo.targets):
            return ast.literal_eval(nodo.value).strip()
    raise RuntimeError("ESEMPIO non trovato in tests/test_regole_testo.py")


def leggi_argomenti(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="percorso.py", description="L'ingresso di un amico nuovo, nel browser senza finestra. Scrive riepilogo.txt e le foto.",
        epilog="riepilogo.txt: una riga per passo, «<passo> secondi=<s> tocchi=<n> errori-console=<n> gravi=<n> esito=<...>». "
               "Esce con 0 se tutto è ok, 1 se un passo non lo è, 2 con argomenti sbagliati.")
    p.add_argument("cartella", help="cartella dei risultati, FUORI dal repository")
    dove = p.add_mutually_exclusive_group(required=True)
    dove.add_argument("--locale", action="store_true", help="server di prova avviato e fermato da solo, con i passi in più")
    dove.add_argument("--remoto", action="store_true", help="server di SCHIERAXI_INDIRIZZO con l'invito di SCHIERAXI_INVITO")
    p.add_argument("--telefono", choices=list(TELEFONI), default="iphone")
    p.add_argument("--larghezza", type=int, choices=list(LARGHEZZE), default=390)
    p.add_argument("--formato", choices=list(FORMATI), default="excel")
    p.add_argument("--a-secco", action="store_true", help="prepara i file e stampa i passi, senza browser né server")
    return p.parse_args(argv)


def da_ambiente(ambiente=None) -> tuple[str, str] | None:
    """Indirizzo e invito per `--remoto`, solo dalle variabili d'ambiente (mai i valori nei messaggi)."""
    ambiente = os.environ if ambiente is None else ambiente
    indirizzo, invito = ambiente.get("SCHIERAXI_INDIRIZZO", "").strip().rstrip("/"), ambiente.get("SCHIERAXI_INVITO", "").strip()
    return (indirizzo, invito) if indirizzo and invito else None


def indirizzo_di_prova(indirizzo: str) -> bool:
    """Freno contro la produzione: `--remoto` gira solo su un server il cui nome comincia con «prova.» (l'ambiente di
    prova). Non c'è un'opzione per scavalcarlo: lo script crea e cancella account, e lì ci sono gli amici veri."""
    try:
        nome = (urlsplit(indirizzo).hostname or "").lower()
    except ValueError:
        return False
    return nome.startswith("prova.") and len(nome) > len("prova.")


def crea_invito(python: str, copia: Path, env: dict) -> str:
    """Un invito monouso nella copia del server (`python -m fanta invito`); il codice si legge dall'uscita e non si stampa."""
    r = subprocess.run([python, "-m", "fanta", "invito", "--etichetta", "amico-nuovo"], cwd=copia, env=env,
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    codici = re.findall(r"^\s{2}(\S{4,40})\s*$", r.stdout, flags=re.M)
    if r.returncode != 0 or not codici:
        sys.exit(f"Invito non creato nella copia (uscita {r.returncode}).")
    return codici[0]


# =========================== il giro nel browser ===========================
class Bloccato(Exception):
    """Il passo non va avanti: un amico resterebbe fermo qui (o il risultato non è quello atteso)."""


class Giro:
    """Il browser di un amico: tocchi, errori e risposte del passo in corso, foto e axe alla fine di ogni passo."""

    def __init__(self, ctx, base: str, uscita: Path, segreti: list[str], base_api: str | None = None):
        self.ctx, self.base, self.uscita, self.segreti = ctx, base, uscita, segreti
        self.base_api = base_api or base             # per le richieste fatte da qui (non dal browser): l'indirizzo vero
        self.pagina = ctx.pages[0] if ctx.pages else ctx.new_page()
        self.attiva = self.pagina                    # la pagina su cui si misurano axe e foto (cambia per l'invito già usato)
        self.passo, self.tocchi, self.errori, self.risposte = "", 0, [], []
        self.dettagli: list[str] = []
        self.nome = f"amico-{secrets.randbelow(10 ** 6):06d}"
        self.password = secrets.token_urlsafe(18)
        self.password_usate = [self.password]        # tutte, per la pulizia (prima e dopo il rientro)
        self.recupero = ""
        self.creato = False                          # l'account esiste: va cancellato alla fine
        self.da_chiudere: list = []                  # browser in più di un passo: si chiudono dopo foto e axe
        self.ascolta(self.pagina)

    # --- ascolto della pagina
    def ascolta(self, pagina) -> None:
        def console(m):
            if m.type == "error" and "the server responded with a status of" not in m.text:   # le risposte si contano a parte
                self.errori.append(m.text)
        pagina.on("console", console)
        pagina.on("pageerror", lambda e: self.errori.append(str(e)))
        pagina.on("response", lambda r: r.status >= 400 and self.risposte.append((urlsplit(r.url).path, r.status)))
        pagina.on("dialog", self._dialogo)
        pagina.set_default_timeout(20000)

    def _dialogo(self, d) -> None:
        self.tocchi += 1                             # «OK» nella finestra di conferma
        d.accept()

    def segreto(self, *valori: str) -> None:
        self.segreti.extend(v for v in valori if v)

    # --- gesti di chi usa il telefono
    def tocca(self, loc) -> None:
        loc.first.tap()
        self.tocchi += 1

    def scrivi(self, loc, testo: str) -> None:
        loc.first.tap()
        loc.first.fill(testo)
        self.tocchi += 1

    def scegli(self, loc, valore: str) -> None:
        loc.first.select_option(valore)              # tendina: tocco per aprirla, tocco sulla scelta
        self.tocchi += 2

    def nota(self, testo: str) -> None:
        self.dettagli.append(f"{self.passo}: {oscura(' '.join(str(testo).split()), self.segreti)[:400]}")

    # --- un passo
    def fai(self, numero: int, passo: str, funzione) -> str:
        self.passo, self.tocchi = passo, 0
        self.errori.clear()
        self.risposte.clear()
        self.attiva = self.pagina
        inizio = time.monotonic()
        try:
            funzione(self)
            esito = "ok"
        except Bloccato as e:
            esito = "bloccato"
            self.nota(e)
        except Exception as e:                       # noqa: BLE001 - un passo rotto non ferma gli altri
            esito = "bloccato" if type(e).__name__ == "TimeoutError" else f"errore:{type(e).__name__}"
            self.nota(f"{type(e).__name__}: {str(e).splitlines()[0] if str(e) else ''}")
        secondi = time.monotonic() - inizio
        n_gravi, esito = self._misura(numero, passo, esito)
        while self.da_chiudere:
            self.da_chiudere.pop().close()
        self.attiva = self.pagina
        inattese = [f"{s} {p}" for p, s in self.risposte if not risposta_attesa(passo, p, s)]
        for e in self.errori + inattese:
            self.nota(f"errore: {e}")
        return riga(passo, secondi, self.tocchi, len(self.errori) + len(inattese), n_gravi, esito)

    def _misura(self, numero: int, passo: str, esito: str) -> tuple[int, str]:
        """axe sulla schermata di fine passo (violazioni in un file), poi la foto con i segreti coperti."""
        p, nome = self.attiva, f"{numero:02d}-{passo}"
        n_gravi = 0
        try:
            if self.in_app(p):                       # la schermata finita di caricare, non la rotella
                try:
                    foto._aspetta_pronta(p, 30000)
                except Exception:                    # noqa: BLE001 - si misura quello che c'è
                    self.nota("schermata ancora in caricamento dopo 30 s")
            p.wait_for_timeout(300)
            p.evaluate(foto.FINISCI_ANIMAZIONI)
            p.evaluate(foto.AXE.read_text(encoding="utf-8"))
            violazioni = p.evaluate(foto.LANCIA_AXE, foto.REGOLE_AXE)
            n_gravi = foto.gravi(violazioni)
            (self.uscita / f"axe-{nome}.json").write_text(
                oscura(json.dumps(violazioni, ensure_ascii=False, indent=1), self.segreti), encoding="utf-8")
        except Exception as e:                       # noqa: BLE001 - misura non riuscita: il passo non è «ok»
            self.nota(f"axe non riuscito: {type(e).__name__}")
            if esito == "ok":
                esito = "errore:axe"
        self.foto(p, nome)
        return n_gravi, esito

    def foto(self, p, nome: str) -> None:
        coperti = [p.locator(s) for s in ("#codice-una-volta", "#ac-invito", "#ac-codice", "#adm-link-invito")]
        try:
            p.screenshot(path=str(self.uscita / f"{nome}.png"), mask=coperti, animations="disabled")
        except Exception as e:                       # noqa: BLE001 - la foto è un di più
            self.nota(f"foto non riuscita: {type(e).__name__}")

    # --- stato dell'app
    def in_app(self, p=None) -> bool:
        p = p or self.pagina
        return bool(p.evaluate("() => typeof stato === 'object' && !!stato.account && !document.querySelector('#accesso')"))

    def aspetta_app(self, p=None, limite_ms: int = 30000) -> None:
        p = p or self.pagina
        p.wait_for_function("() => typeof stato === 'object' && !!stato.account && !document.querySelector('#accesso') "
                            "&& document.querySelector('#contenuto').children.length > 0", timeout=limite_ms)

    def api(self, percorso: str):
        """Una lettura come la fa l'app (funzione `api` di app.js), per controllare cosa è stato salvato."""
        return self.pagina.evaluate("(p) => api(p)", percorso)

    def chiudi_fogli(self) -> None:
        """Torna all'app senza fogli aperti (dopo un passo andato storto)."""
        p = self.pagina
        if p.locator("#foglio:not([hidden])").count():
            p.goto(self.base + "/", wait_until="load")
            self.aspetta_app()

    def avviso(self, testo: str, limite_ms: int = 30000) -> None:
        self.pagina.locator("#avviso").filter(has_text=testo).wait_for(state="visible", timeout=limite_ms)

    def apri_account(self) -> None:
        """Impostazioni nella barra > «Il tuo account» (#618: prima era l'ingranaggio in testata)."""
        p = self.pagina
        self.tocca(p.locator("a.scheda[data-vista='impostazioni']"))
        self.tocca(p.get_by_role("button", name=re.compile(r"^\s*Il tuo account")).or_(
            p.get_by_role("link", name=re.compile(r"^\s*Il tuo account"))))
        p.locator("#scheda-account").wait_for(state="visible")

    def accedi_dal_modulo(self) -> None:
        p = self.pagina
        p.locator("#accesso-form").wait_for(state="visible")
        if p.locator("#accesso-schede button[data-s='accedi'][aria-pressed='true']").count() == 0:
            self.tocca(p.locator("#accesso-schede button[data-s='accedi']"))
        self.scrivi(p.locator("#ac-nome"), self.nome)
        self.scrivi(p.locator("#ac-pw"), self.password)
        self.tocca(p.locator("#accesso-invia"))
        self.aspetta_app()


# --- i passi (ognuno alza Bloccato con il motivo, in parole)
def passo_invito(g: Giro, invito: str) -> None:
    p = g.pagina
    p.goto(g.base + "/?invito=" + quote(invito), wait_until="load")
    p.locator("#accesso-form").wait_for(state="visible")
    if p.locator("#accesso-schede button[data-s='registra'][aria-pressed='true']").count() == 0:
        raise Bloccato("la pagina non apre la registrazione")
    atteso = re.sub(r"[^A-Z0-9-]", "", invito.upper())
    if p.locator("#ac-invito").input_value() != atteso:
        raise Bloccato("il codice d'invito non è già scritto nel campo")
    if "invito" in urlsplit(p.url).query:
        raise Bloccato("il codice d'invito resta nell'indirizzo")


def passo_registrazione(g: Giro) -> None:
    p = g.pagina
    g.scrivi(p.locator("#ac-nome"), g.nome)
    g.scrivi(p.locator("#ac-pw"), g.password)
    g.tocca(p.locator("#ac-letto"))
    g.creato = True                                  # da qui l'account può esistere sul server: alla fine va cancellato
    g.tocca(p.locator("#accesso-invia"))
    p.locator("#codice-una-volta, #accesso-msg .errore").first.wait_for(state="visible", timeout=30000)
    if not p.locator("#codice-una-volta").is_visible():
        g.creato = False                             # il server l'ha rifiutata: nessun account
        raise Bloccato("registrazione rifiutata: " + p.locator("#accesso-msg").inner_text())
    g.recupero = p.locator("#codice-una-volta").inner_text().strip()
    g.segreto(g.recupero)
    if not g.recupero:
        raise Bloccato("il codice di recupero è vuoto")


def passo_recupero_salvato(g: Giro) -> None:
    p = g.pagina
    g.tocca(p.locator("#copia-codice"))
    g.tocca(p.locator("#codice-salvato"))
    g.tocca(p.locator("#codice-continua"))
    p.locator("#foglio:not([hidden]) .pa-capo").wait_for(state="visible", timeout=30000)


FOGLIO_PRIMO_AVVIO = "#foglio:not([hidden]) .pa-capo"
ATTESA_PRIMO_AVVIO_MS = 10000


def primo_avvio_aperto(p, limite_ms: int = ATTESA_PRIMO_AVVIO_MS) -> bool:
    """Vero se il foglio del primo avvio si vede entro `limite_ms`. Si apre dopo l'app (prima risponde il server sullo stato
    della guida): guardarlo appena l'app è pronta dava «NON aperto» anche quando poi si apriva (#598)."""
    try:
        p.locator(FOGLIO_PRIMO_AVVIO).first.wait_for(state="visible", timeout=limite_ms)
        return True
    except Exception as e:                           # noqa: BLE001 - Playwright si importa solo con il browser
        if type(e).__name__ != "TimeoutError":
            raise
        return False


def passo_installabile(g: Giro) -> None:
    p = g.pagina
    problemi = controlla_manifesto(p.evaluate(
        "async () => { const l = document.querySelector('link[rel=manifest]'); if (!l) return null;"
        " try { const r = await fetch(l.href); return r.ok ? await r.json() : null; } catch (e) { return null; } }"))
    apple = p.evaluate(
        "async () => { const l = document.querySelector('link[rel=apple-touch-icon]'); let icona = 0;"
        " if (l) { try { icona = (await fetch(l.href)).status; } catch (e) {} }"
        " const meta = n => (document.querySelector(`meta[name=\"${n}\"]`) || {}).content || '';"
        " return { icona, capace: meta('apple-mobile-web-app-capable'), titolo: meta('apple-mobile-web-app-title') }; }")
    if apple["icona"] != 200:
        problemi.append("manca apple-touch-icon")
    if apple["capace"] != "yes" or not apple["titolo"]:
        problemi.append("mancano i meta di Apple")
    # La web aperta dall'icona della Home è un caricamento nuovo: una seconda scheda, con il service worker già installato.
    nuova = g.ctx.new_page()
    g.da_chiudere.append(nuova)
    g.ascolta(nuova)
    g.attiva = nuova
    nuova.goto(g.base + "/?da=app", wait_until="load")
    try:
        nuova.wait_for_function("() => !!(navigator.serviceWorker && navigator.serviceWorker.controller)", timeout=20000)
    except Exception:                                # noqa: BLE001
        problemi.append("il service worker non controlla la pagina dopo una ricarica")
    cdp = g.ctx.new_cdp_session(nuova)
    errori = [e.get("errorId", "?") for e in cdp.send("Page.getInstallabilityErrors").get("installabilityErrors", [])]
    if errori:
        problemi.append("Chrome non la installa: " + ", ".join(errori))
    try:
        g.aspetta_app(nuova)
        g.nota("aperta dalla Home: primo avvio " + ("aperto" if primo_avvio_aperto(nuova) else "NON aperto")
               + ", si vede «" + nuova.locator("#contenuto").inner_text()[:160] + "»")
    except Exception as e:                           # noqa: BLE001 - è solo un'osservazione
        g.nota(f"aperta dalla Home: app non pronta ({type(e).__name__})")
    if problemi:
        raise Bloccato("; ".join(problemi))


def _aspetta_anteprima(p) -> None:
    p.locator("#ar-titolo, #pa-anteprima [role=alert]").first.wait_for(state="visible", timeout=90000)


def _scegli_file(g: Giro, file: Path) -> None:
    p = g.pagina
    with p.expect_file_chooser() as scelta:
        g.tocca(p.locator("#pa-scegli-file"))
    scelta.value.set_files(str(file))


def _primo_avvio_su(g: Giro, nome_passo: str) -> None:
    titolo = g.pagina.locator("#foglio:not([hidden]) h3.pa-titolo")
    if not titolo.count() or titolo.first.inner_text().strip() != nome_passo:
        raise Bloccato(f"il primo avvio non è sul passo «{nome_passo}»")


def dice_nessuna_rosa(messaggio: str) -> bool:
    """Il messaggio dice che nel file non ci sono rose: la frase di adesso del server («Non ho trovato rose nel file», #577)
    o quella di prima («nessuna rosa»), per un server remoto non ancora aggiornato."""
    return bool(re.search(r"nessuna rosa|non ho trovato rose", messaggio, re.I))


def passo_file_sbagliato(g: Giro, sbagliato: Path) -> None:
    p = g.pagina
    _primo_avvio_su(g, "Le rose")
    _scegli_file(g, sbagliato)
    _aspetta_anteprima(p)
    if p.locator("#ar-titolo").is_visible():
        raise Bloccato("un calendario è stato preso per le rose")
    messaggio = p.locator("#pa-anteprima [role=alert]").inner_text()
    g.nota("messaggio: " + messaggio)
    if not dice_nessuna_rosa(messaggio):
        raise Bloccato("il messaggio non dice che nel file non ci sono rose")
    g.tocca(p.locator("#ar-indietro"))
    if not (p.locator("#pa-testo").is_visible() and p.locator("#pa-salta").is_visible()):
        raise Bloccato("dopo «Torna indietro» non si può riprovare né saltare")
    if p.evaluate("() => { const f = document.querySelector('#pa-file'); return !!(f && f.files && f.files.length); }"):
        raise Bloccato("dopo «Torna indietro» il file sbagliato resta scelto (#578)")


def passo_rose(g: Giro, formato: str, file: Path) -> None:
    p = g.pagina
    _primo_avvio_su(g, "Le rose")
    if formato == "testo":
        g.scrivi(p.locator("#pa-testo"), file.read_text(encoding="utf-8"))
        g.tocca(p.locator("#pa-avanti"))
    else:
        _scegli_file(g, file)
    _aspetta_anteprima(p)
    if not p.locator("#ar-titolo").is_visible():
        raise Bloccato("anteprima non riuscita: " + p.locator("#pa-anteprima [role=alert]").inner_text())
    g.nota("riassunto: " + p.locator(".ar-riassunto").inner_text())
    lette = {re.sub(r"\s+(Nuova|nuova)$", "", t.strip()) for t in p.locator(".ar-squadra h4").all_inner_texts()}
    attese = {s["nome"] for s in json.loads(ROSE_ESEMPIO.read_text(encoding="utf-8"))["squadre"]}
    if not attese <= lette:
        raise Bloccato("l'anteprima non mostra tutte le squadre: mancano " + ", ".join(sorted(attese - lette)))


def passo_squadra(g: Giro) -> None:
    p = g.pagina
    p.locator(".ar-mia legend").filter(has_text="Qual è la tua squadra?").wait_for(state="visible")
    g.tocca(p.locator(".ar-mia label").filter(has_text=MIA_SQUADRA))
    # i «da controllare» restano sulla prima proposta dell'app
    g.tocca(p.locator("#ar-salva"))
    p.locator("#foglio:not([hidden]) h3.pa-titolo").filter(has_text="I tempi della lega").or_(
        p.locator("#ar-msg .errore")).first.wait_for(state="visible", timeout=90000)
    if p.locator("#ar-msg .errore").count():
        raise Bloccato("salvataggio delle rose non riuscito: " + p.locator("#ar-msg").inner_text())
    mia = p.evaluate("() => ((stato.squadre || []).find(s => s.mia) || {}).nome || ''")
    if mia != MIA_SQUADRA:
        raise Bloccato(f"la squadra scelta non risulta la tua ({mia or 'nessuna'})")


def passo_tempi(g: Giro) -> None:
    p = g.pagina
    _primo_avvio_su(g, "I tempi della lega")
    try:
        p.wait_for_load_state("networkidle", timeout=5000)      # i valori di adesso arrivano dal server
    except Exception:                                # noqa: BLE001
        pass
    g.scegli(p.locator("#pa-scadenza"), str(SCADENZA_MINUTI))
    g.nota("prima giornata proposta: " + p.locator("#pa-prima option:checked").inner_text())
    g.tocca(p.locator("#pa-avanti"))
    p.locator("#foglio:not([hidden]) .pa-capo").filter(has_text="Tutto pronto").wait_for(state="visible", timeout=30000)
    g.tocca(p.locator("#pa-chiudi"))
    p.locator("#foglio").wait_for(state="hidden")
    regole = g.api("/api/regole")
    if regole.get("scadenza_minuti") != SCADENZA_MINUTI:
        raise Bloccato(f"scadenza salvata: {regole.get('scadenza_minuti')} minuti, non {SCADENZA_MINUTI}")


def passo_regole(g: Giro) -> None:
    """Impostazioni > Regole e scadenza (#618): il regolamento incollato si salva con un tocco dopo il riconoscimento (prima: Altro >
    Regole, «Applica ai campi», poi «Salva le regole»)."""
    p = g.pagina
    g.chiudi_fogli()
    g.tocca(p.locator("a.scheda[data-vista='impostazioni']"))
    g.tocca(p.locator("#contenuto").get_by_role("button", name=re.compile(r"^\s*Regole e scadenza\b")))
    g.scrivi(p.locator("#testo-regole"), testo_regole_esempio())
    g.tocca(p.locator("#riconosci-regole"))
    g.tocca(p.locator("#salva-riconosciute"))
    g.avviso("Regole salvate")
    r = g.api("/api/regole")
    if r.get("crediti_iniziali") != 500 or not (r.get("modificatore_difesa") or {}).get("attivo"):
        raise Bloccato("le regole salvate non sono quelle del testo incollato")


def passo_formazione(g: Giro) -> None:
    """La Formazione si apre con gli 11 consigliati e si salva da sola (#616): non c'è un pulsante da toccare. Chi ha messo la
    formazione nell'app della lega lo dice con la spunta «L'ho messa»: da lì quegli 11 sono la sua scelta sul server."""
    p = g.pagina
    g.chiudi_fogli()
    g.tocca(p.locator("a.scheda[data-vista='formazione']"))
    # la spunta accesa: all'apertura c'è la copia tenuta sul telefono, di sola lettura finché non arrivano i dati nuovi
    p.locator("#messa:enabled, .fz.chiusa").first.wait_for(state="visible", timeout=90000)
    if not p.locator("label.spunta").count():
        raise Bloccato("la formazione è già chiusa: non si può più dire «L'ho messa»")
    sul_campo = p.locator("#campo-formazione .pedina").count()
    if sul_campo != 11:
        raise Bloccato(f"sul campo ci sono {sul_campo} titolari, non 11")
    g.tocca(p.locator("label.spunta"))
    p.wait_for_function("() => !!(stato.scelta && stato.scelta.salvata && stato.scelta.salvata.messa)", timeout=30000)
    giornata = p.evaluate("() => stato.formaz.f.giornata")
    s = g.api(f"/api/scelta?giornata={int(giornata)}") or {}
    if len(s.get("titolari") or []) != 11 or s.get("messa") is not True or not re.fullmatch(r"\d-\d-\d(-\d)?", s.get("modulo") or ""):
        raise Bloccato(f"scelta salvata con {len(s.get('titolari') or [])} titolari, modulo «{s.get('modulo')}», messa {s.get('messa')}")


def passo_rientro(g: Giro) -> None:
    p = g.pagina
    g.chiudi_fogli()
    g.apri_account()
    g.tocca(p.locator("#acc-esci"))
    p.locator("#accesso-form").wait_for(state="visible", timeout=30000)
    g.tocca(p.locator("#accesso-dimenticata"))
    nuova = secrets.token_urlsafe(18)
    g.segreto(nuova)
    g.scrivi(p.locator("#ac-nome"), g.nome)
    g.scrivi(p.locator("#ac-codice"), g.recupero)
    g.scrivi(p.locator("#ac-pw"), nuova)
    g.tocca(p.locator("#accesso-invia"))
    p.locator("#codice-una-volta, #accesso-msg .errore").first.wait_for(state="visible", timeout=30000)
    if not p.locator("#codice-una-volta").is_visible():
        raise Bloccato("recupero rifiutato: " + p.locator("#accesso-msg").inner_text())
    g.password = nuova
    g.password_usate.append(nuova)
    g.recupero = p.locator("#codice-una-volta").inner_text().strip()
    g.segreto(g.recupero)
    g.tocca(p.locator("#codice-salvato"))
    g.tocca(p.locator("#codice-continua"))
    g.accedi_dal_modulo()


def passo_invito_usato(g: Giro, invito: str, apri_browser) -> None:
    """Un secondo browser, senza sessione, apre lo stesso link d'invito monouso e prova a registrarsi."""
    ctx = apri_browser()
    g.da_chiudere.append(ctx)                        # si chiude dopo foto e axe della sua pagina
    p = ctx.pages[0] if ctx.pages else ctx.new_page()
    g.ascolta(p)
    g.attiva = p
    p.goto(g.base + "/?invito=" + quote(invito), wait_until="load")
    p.locator("#accesso-form").wait_for(state="visible")
    altro = secrets.token_urlsafe(18)
    g.segreto(altro)
    g.scrivi(p.locator("#ac-nome"), g.nome + "-bis")
    g.scrivi(p.locator("#ac-pw"), altro)
    g.tocca(p.locator("#ac-letto"))
    g.tocca(p.locator("#accesso-invia"))
    p.locator("#accesso-msg .errore, #codice-una-volta").first.wait_for(state="visible", timeout=30000)
    if p.locator("#codice-una-volta").is_visible():
        raise Bloccato("l'invito monouso ha creato un secondo account")
    messaggio = p.locator("#accesso-msg").inner_text()
    g.nota("messaggio: " + messaggio)
    if "invito" not in messaggio.lower():
        raise Bloccato("il messaggio non nomina l'invito")


def passo_elimina(g: Giro, richieste) -> None:
    p = g.pagina
    if not g.in_app():
        p.goto(g.base + "/", wait_until="load")
        if p.locator("#accesso-form").count():
            g.accedi_dal_modulo()
    g.chiudi_fogli()
    g.apri_account()
    g.tocca(p.locator("#scheda-account summary").filter(has_text="Elimina l'account"))
    g.scrivi(p.locator("#acc-pw-elimina"), g.password)
    g.tocca(p.locator("#acc-elimina"))               # più il tocco su «OK» nella conferma
    p.locator("#accesso-form").wait_for(state="visible", timeout=30000)
    r = richieste.post(g.base_api + "/api/account/accedi", data={"nome_utente": g.nome, "password": g.password},
                       headers={"X-Fanta": "1"})
    if r.status != 401:
        raise Bloccato(f"dopo l'eliminazione l'accesso risponde {r.status}, non 401")
    g.creato = False


def pulisci(g, richieste) -> bool:
    """Ultima rete: l'account di prova si cancella con l'API (eliminazione dall'app non riuscita o mai arrivata). Si prova
    ogni password usata nel giro, l'ultima per prima; vero solo se la cancellazione risponde 200. Un accesso rifiutato con
    tutte non vuol dire «già cancellato» (password cambiata a metà, tetto di tentativi): è falso."""
    for password in reversed(list(dict.fromkeys(g.password_usate))):
        try:
            r = richieste.post(g.base_api + "/api/account/accedi", data={"nome_utente": g.nome, "password": password},
                               headers={"X-Fanta": "1"})
            if r.status != 200:
                continue
            r = richieste.post(g.base_api + "/api/account/elimina", data={"password": password}, headers={"X-Fanta": "1"})
            return r.status == 200
        except Exception:                            # noqa: BLE001 - si prova la password seguente
            continue
    return False


def chiudi_account(g, richieste) -> None:
    """Se l'account di prova può esistere ancora lo si cancella; se non si riesce, un avviso con il nome (mai la password)."""
    if g.creato and not pulisci(g, richieste):
        print(f"ATTENZIONE: l'account di prova «{g.nome}» potrebbe esistere ancora: controlla ed eliminalo a mano.",
              file=sys.stderr, flush=True)
    else:
        g.creato = False


def scrivi_dettagli(g, uscita: Path) -> None:
    """Le note del giro, ripassate dal filtro dei segreti (anche quelli scoperti dopo la nota)."""
    (Path(uscita) / "dettagli.txt").write_text("".join(oscura(d, g.segreti) + "\n" for d in g.dettagli), encoding="utf-8")


def copia_registro(log: Path, uscita: Path, segreti) -> None:
    """Il registro del server di prova, senza i segreti (contiene gli indirizzi chiesti, anche quello dell'invito)."""
    if Path(log).is_file():
        (Path(uscita) / "server.log").write_text(oscura(Path(log).read_text(encoding="utf-8", errors="replace"), segreti),
                                                 encoding="utf-8")


def percorri(base: str, uscita: Path, telefono: str, larghezza: int, formato: str, file: Path, invito: str,
             locale: bool, sbagliato: Path | None, host: str | None, segreti: list[str], base_api: str | None = None) -> list[str]:
    from playwright.sync_api import sync_playwright          # solo qui: i test dello strumento girano senza Playwright

    righe: list[str] = []
    with ExitStack() as pila:
        p = pila.enter_context(sync_playwright())
        dispositivo = {k: v for k, v in p.devices[TELEFONI[telefono]].items() if k != "default_browser_type"}
        dispositivo["viewport"] = {"width": larghezza, "height": dispositivo["viewport"]["height"]}
        # In locale il server ascolta su 127.0.0.NN; il browser lo apre come «localhost» (è lì che l'app registra il service
        # worker, come farebbe su https).
        argomenti = [f"--host-resolver-rules=MAP localhost {host}"] if host else []

        def apri_browser():
            profilo = pila.enter_context(tempfile.TemporaryDirectory(prefix="amico-nuovo-profilo-", ignore_cleanup_errors=True))
            ctx = p.chromium.launch_persistent_context(profilo, channel="chrome", headless=True, args=argomenti,
                                                       locale="it-IT", **dispositivo)
            ctx.grant_permissions(["clipboard-read", "clipboard-write"], origin=base)
            return ctx

        ctx = apri_browser()
        g = None
        try:
            g = Giro(ctx, base, uscita, segreti, base_api)
            g.segreto(g.password)
            fatti: dict[str, str] = {}
            azioni = {
                "invito": lambda g: passo_invito(g, invito), "registrazione": passo_registrazione,
                "recupero_salvato": passo_recupero_salvato, "installabile": passo_installabile,
                "file_sbagliato": lambda g: passo_file_sbagliato(g, sbagliato), "rose": lambda g: passo_rose(g, formato, file),
                "squadra": passo_squadra, "tempi": passo_tempi, "regole": passo_regole, "formazione": passo_formazione,
                "rientro": passo_rientro, "invito_usato": lambda g: passo_invito_usato(g, invito, apri_browser),
                "elimina": lambda g: passo_elimina(g, ctx.request),
            }
            for numero, passo in enumerate(ordine(locale), start=1):
                mancano = [x for x in PRIMA.get(passo, ()) if fatti.get(x) != "ok"]
                if passo == "elimina" and not g.creato:
                    mancano = ["registrazione"]
                if mancano:
                    g.passo = passo
                    g.nota("non provato: prima serve " + ", ".join(mancano))
                    r = riga(passo, 0, 0, 0, 0, "bloccato")
                else:
                    r = g.fai(numero, passo, azioni[passo])
                fatti[passo] = r.rsplit("esito=", 1)[1]
                print(r, flush=True)
                righe.append(r)
        finally:
            try:
                if g is not None:
                    chiudi_account(g, ctx.request)
                    scrivi_dettagli(g, uscita)
            finally:
                ctx.close()
    return righe


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["--solo-file-rose"] and len(argv) == 3:     # interno: il file Excel con il Python del .venv
        print(file_rose(ROSE_ESEMPIO, argv[1], Path(argv[2])))
        return 0
    try:
        a = leggi_argomenti(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    try:
        uscita = foto.fuori_dal_repository(a.cartella)
    except SystemExit as e:
        print(e.code, file=sys.stderr)
        return 2
    remoto = da_ambiente() if a.remoto else None
    if a.remoto and not remoto:
        print("--remoto: servono le variabili d'ambiente SCHIERAXI_INDIRIZZO e SCHIERAXI_INVITO", file=sys.stderr)
        return 2
    if remoto and not indirizzo_di_prova(remoto[0]):
        print("--remoto: SCHIERAXI_INDIRIZZO deve essere l'ambiente di prova (nome che comincia con «prova.»): "
              "lo script crea e cancella account e non gira altrove", file=sys.stderr)
        return 2
    uscita.mkdir(parents=True, exist_ok=True)
    file = prepara_rose(a.formato, uscita)
    sbagliato = file_non_rose(uscita) if a.locale else None
    passi = ordine(a.locale)
    print(f"Amico nuovo: {TELEFONI[a.telefono]} a {a.larghezza} px, rose in formato «{a.formato}» ({file.name}), "
          f"{len(passi)} passi: {', '.join(passi)}", flush=True)
    if a.a_secco:
        print("A secco: niente browser né server" + (" (indirizzo e invito letti dalle variabili d'ambiente)." if a.remoto else "."))
        return 0
    segreti: list[str] = []
    with ExitStack() as pila:
        if a.remoto:
            base, invito = remoto
            segreti += [base, urlsplit(base).hostname or "", invito, invito.upper()]
            host, base_api = None, base
        else:
            lavoro = Path(pila.enter_context(tempfile.TemporaryDirectory(prefix="amico-nuovo-server-", ignore_cleanup_errors=True)))
            dati = foto.cartella_dati(None)
            if not dati or not (dati / "fanta.sqlite").is_file():
                print("Serve l'archivio dei dati di calcio (dati/fanta.sqlite) per la formazione.", file=sys.stderr)
                return 2
            copia = foto.prepara_copia(lavoro / "app", dati)
            python = foto.python_server(None)
            env = foto.ambiente_server(copia) | {"FANTA_MULTIUTENTE": "1"}
            invito = crea_invito(python, copia, env)
            segreti += [invito, invito.upper()]
            porta = foto.porta_libera("127.0.0.1")
            host = foto.host_per(porta)
            porta = foto.porta_libera(host)
            log = lavoro / "server.log"
            server = pila.enter_context(foto.ServerDiProva(
                [python, "-m", "fanta", "server", "--host", host, "--porta", str(porta)], f"http://{host}:{porta}",
                cwd=copia, env=env, log=log, attesa=60))
            print(f"Server di prova su http://{host}:{porta} (PID {server.processo.pid}), aperto come localhost", flush=True)
            base, base_api = f"http://localhost:{porta}", server.base

            def copia_log():                         # il registro del server, senza i segreti, nella cartella dei risultati
                server.ferma()
                copia_registro(log, uscita, segreti)
            pila.callback(copia_log)
        righe = percorri(base, uscita, a.telefono, a.larghezza, a.formato, file, invito, a.locale, sbagliato, host, segreti,
                         base_api)
    (uscita / "riepilogo.txt").write_text("\n".join(righe) + "\n", encoding="utf-8")
    va, problemi = esito_complessivo(righe)
    print(f"{'Tutto ok' if va else 'Non tutto ok'}: {len(righe)} passi, risultati in {uscita}" +
          ("" if va else "\n  " + "\n  ".join(problemi)))
    return 0 if va else 1


if __name__ == "__main__":
    for flusso in (sys.stdout, sys.stderr):
        flusso.reconfigure(encoding="utf-8")          # «» e lettere accentate anche nella console di Windows
    sys.exit(main())
