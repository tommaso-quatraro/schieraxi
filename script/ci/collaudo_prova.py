"""Collaudo dell'ambiente di prova dopo ogni rilascio (workflow .github/workflows/collaudo-prova.yml, issue #511 e #549).

Tre comandi, usati dal workflow:
    python script/ci/collaudo_prova.py decidi [--forza | --quotidiano]
        Guarda l'ultima release del server `v<N>`, la versione che ha la prova e quando `v<N>` è stata collaudata l'ultima
        volta (artifact `collaudo-v<N>`): una versione già collaudata si collauda di nuovo dopo RIPETI_ORE. Scrive in
        $GITHUB_OUTPUT `esito` (spento, aspetta, collauda, salta, in-ritardo), `versione`, `prova` e `minuti`.
        `--forza` (corsa lanciata a mano): collauda subito, anche una versione già collaudata. `--quotidiano` (corsa fissa
        del mattino): collauda la versione in vigore sulla prova anche se collaudata da poco, così ogni giorno c'è un collaudo
        anche senza versione nuova (#549).
    python script/ci/collaudo_prova.py esito <cartella>
        Legge `<cartella>/riepilogo.txt` di prove/foto_web/foto.py e scrive in $GITHUB_OUTPUT `ok` (true/false) e `dettaglio`,
        e in `<cartella>/esito.txt` lo stesso per l'artifact.
    python script/ci/collaudo_prova.py segnala
        Dalle variabili DECISIONE, VERSIONE, PROVA, MINUTI, OK, DETTAGLIO e CORSA (le uscite dei job): apre, commenta o chiude
        le issue «Collaudo della prova: v<N> non passa» (una sola per versione) e «La prova non si aggiorna».

Indirizzo, utente e password della prova arrivano SOLO dalle variabili d'ambiente PROVA_URL, PROVA_UTENTE e PROVA_PASSWORD (i
segreti del repository): mai stampati. Senza segreti l'esito è «spento» e non succede niente. Il repository è pubblico: i testi
che finiscono nelle issue non contengono indirizzi. Solo libreria standard (più la `gh` del computer di GitHub).
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

RITARDO_MINUTI = 40          # oltre questo tempo dalla release, una prova senza la versione nuova è «in ritardo»
RIPETI_ORE = 20              # oltre questo tempo dall'ultimo collaudo, la versione in vigore si collauda di nuovo (#549)
ESITI = ("spento", "aspetta", "collauda", "salta", "in-ritardo")
MISURE = ("gravi", "scorrimento-di-lato", "errori-console")      # le chiavi di ogni riga di riepilogo.txt (foto.riga_riepilogo)
# I testi che passano fra i job (uscite `dettaglio` ed `esito`) non contengono mai la parola «collaudo»: è il nome
# dell'account di prova (segreto PROVA_UTENTE) e GitHub scarta le uscite che contengono un segreto.
_VERSIONE = re.compile(r"v?(\d+(?:\.\d+)*)")
_INDIRIZZO = re.compile(r"https?://\S+")


# =========================== parti senza rete ===========================
def versione_valida(testo) -> str | None:
    """La versione senza «v» se è fatta solo di numeri e punti («1.442»), altrimenti None (finisce in titoli e nomi)."""
    m = _VERSIONE.fullmatch(testo.strip()) if isinstance(testo, str) else None
    return m.group(1) if m else None


def _numeri(versione: str) -> tuple[int, ...]:
    return tuple(int(p) for p in versione.split("."))


def decidi(ultima_release: str, versione_prova: str | None, minuti_dalla_release: int, gia_collaudate: set[str],
           ore_dal_collaudo: float | None = None) -> str:
    """aspetta | collauda | salta | in-ritardo. La prova ha l'ultima release: si collauda se non è già stata collaudata, o se
    l'ultimo collaudo ha più di RIPETI_ORE (`ore_dal_collaudo`; None = età non nota, vale come recente).
    Non ce l'ha (o non risponde): si aspetta, fino a RITARDO_MINUTI dalla release. Una prova più avanti della release (la
    release arriva un attimo dopo il commit) aspetta."""
    ultima = versione_valida(ultima_release)
    prova = versione_valida(versione_prova)
    collaudate = {versione_valida(v) for v in gia_collaudate}
    if ultima is None:
        return "aspetta"
    if prova == ultima:
        recente = ore_dal_collaudo is None or ore_dal_collaudo <= RIPETI_ORE
        return "salta" if ultima in collaudate and recente else "collauda"
    if prova is not None and _numeri(prova) > _numeri(ultima):
        return "aspetta"
    return "in-ritardo" if minuti_dalla_release > RITARDO_MINUTI else "aspetta"


def _numero(valore: str) -> int:
    """Un conteggio del riepilogo; un valore illeggibile conta come un problema (meglio un'issue in più che un difetto taciuto)."""
    return int(valore) if valore.isdigit() else 1


def _quanti(n: int, uno: str, tanti: str) -> str:
    return f"{n} {uno if n == 1 else tanti}"


def esito(riepilogo: str) -> tuple[bool, list[str]]:
    """(tutto a posto, problemi) dalle righe di riepilogo.txt di foto.py: violazioni gravi di accessibilità, errori della
    console (comprese le risposte 4xx e 5xx, che Chrome scrive nella console), scorrimento di lato, scene che non si aprono.
    Gli indirizzi nei messaggi diventano «<indirizzo>»: i problemi finiscono in un'issue pubblica."""
    problemi = []
    righe = [r.strip() for r in riepilogo.splitlines() if r.strip()]
    for riga in righe:
        chi = " ".join(riga.split()[:3])
        if "errore=" in riga:
            problemi.append(f"{chi}: la schermata non si apre ({riga.split('errore=', 1)[1].strip()})")
            continue
        valori = dict(p.split("=", 1) for p in riga.split()[3:] if "=" in p)
        mancanti = [k for k in MISURE if k not in valori]
        difetti = [f"misura assente nel riepilogo ({', '.join(mancanti)})"] if mancanti else []
        n_gravi, n_console = (_numero(valori.get(k, "0")) for k in ("gravi", "errori-console"))
        if n_gravi:
            difetti.append(_quanti(n_gravi, "violazione grave di accessibilità", "violazioni gravi di accessibilità"))
        if n_console:
            difetti.append(_quanti(n_console, "errore della console", "errori della console"))
        if valori.get("scorrimento-di-lato", "no") != "no":
            difetti.append("la pagina scorre di lato")
        if difetti:
            problemi.append(f"{chi}: {', '.join(difetti)}")
    if not righe:
        problemi.append("riepilogo vuoto: nessuna schermata provata")
    return not problemi, [_INDIRIZZO.sub("<indirizzo>", p) for p in problemi]


def maschera(testo: str, url: str | None) -> str:
    """Toglie dal testo l'indirizzo della prova (anche il solo nome del server) e ogni altro indirizzo web."""
    testo = _INDIRIZZO.sub("<indirizzo>", testo)
    parti = urlsplit(url or "")
    for pezzo in {parti.netloc, parti.hostname or ""} - {""}:
        testo = testo.replace(pezzo, "<indirizzo-della-prova>")
    return testo


def indirizzo_valido(url: str) -> bool:
    """https verso un nome qualsiasi, oppure http solo verso un indirizzo di loopback 127.x (prove in locale)."""
    if not url or any(c.isspace() for c in url):
        return False
    try:
        parti = urlsplit(url)
        host = parti.hostname
        porta = parti.port                               # una porta sbagliata («:x», «:99999») solleva ValueError
    except ValueError:
        return False
    if not host or porta == 0:
        return False
    if parti.scheme == "https":
        return True
    if parti.scheme != "http":
        return False
    try:
        return ipaddress.ip_address(host) in ipaddress.ip_network("127.0.0.0/8")
    except ValueError:
        return False


def _quando(testo: str) -> datetime:
    return datetime.fromisoformat(testo.replace("Z", "+00:00"))


def ultima_release(release: list[dict], adesso: datetime) -> tuple[str, int] | None:
    """(versione, minuti da quando è uscita) della release del server `v<N>` più alta, senza bozze; None se non ce n'è."""
    valide = [(versione_valida(r.get("tagName")), r) for r in release
              if not r.get("isDraft") and str(r.get("tagName", "")).startswith("v")]
    valide = [(v, r) for v, r in valide if v]
    if not valide:
        return None
    versione, r = max(valide, key=lambda x: _numeri(x[0]))
    return versione, max(0, int((adesso - _quando(r["createdAt"])).total_seconds() // 60))


# =========================== rete e GitHub ===========================
class _SenzaReindirizzamenti(urllib.request.HTTPRedirectHandler):
    """Un reindirizzamento non si segue: password e token restano solo per l'indirizzo della prova."""
    def redirect_request(self, *a, **k):
        return None


_APRI = urllib.request.build_opener(_SenzaReindirizzamenti)


def _chiedi(url: str, metodo: str, corpo: dict | None = None, token: str | None = None) -> dict:
    # X-Fanta: il server rifiuta (403) le richieste che cambiano qualcosa senza questa intestazione, come fa l'app
    intestazioni = {"Accept": "application/json", "User-Agent": "schieraxi-collaudo-prova", "X-Fanta": "1"}
    dati = None
    if corpo is not None:
        dati = json.dumps(corpo).encode()
        intestazioni["Content-Type"] = "application/json"
    if token:
        intestazioni["Authorization"] = f"Bearer {token}"
    with _APRI.open(urllib.request.Request(url, data=dati, headers=intestazioni, method=metodo), timeout=30) as r:
        return json.loads(r.read() or b"{}")


def versione_della_prova(url: str, utente: str, password: str) -> str | None:
    """La versione che ha la prova («1.442»), da `/api/stato` dopo l'accesso con l'account di collaudo (token delle app native,
    poi la sessione si chiude). None se la prova non risponde o non fa entrare: il perché va nel registro, senza indirizzo."""
    base = url.rstrip("/")
    try:
        token = _chiedi(base + "/api/account/accedi", "POST", {"nome_utente": utente, "password": password, "nativo": True}).get("token")
        if not token:
            print("Prova: l'accesso non ha dato un token", file=sys.stderr)
            return None
        try:
            return versione_valida(_chiedi(base + "/api/stato", "GET", token=token).get("versione"))
        finally:
            try:
                _chiedi(base + "/api/account/esci", "POST", {}, token=token)
            except (urllib.error.URLError, OSError, ValueError):
                pass
    except urllib.error.HTTPError as e:
        print(f"Prova: risposta {e.code}", file=sys.stderr)
    except (urllib.error.URLError, OSError, ValueError) as e:
        print(f"Prova: nessuna risposta valida ({type(e).__name__})", file=sys.stderr)
    return None


def _gh(*argomenti: str) -> str:
    try:
        return subprocess.run(["gh", *argomenti], capture_output=True, text=True, encoding="utf-8", check=True,
                              timeout=120).stdout
    except subprocess.CalledProcessError as e:
        # l'uscita è catturata: senza questa riga il perché (permessi, etichetta mancante, limite) sparisce dal registro.
        # Si stampano solo il comando (i primi due argomenti) e il messaggio di gh: i segreti della prova non passano da gh.
        print(f"gh {' '.join(argomenti[:2])} non riuscito: {(e.stderr or '').strip()}", file=sys.stderr)
        raise


def _adesso() -> datetime:
    return datetime.now(timezone.utc)


def ore_dall_ultimo_collaudo(versione: str, adesso: datetime) -> float | None:
    """Ore dall'artifact `collaudo-v<N>` non scaduto (30 giorni) più recente; None se la versione non è mai stata collaudata."""
    dati = json.loads(_gh("api", f"repos/{{owner}}/{{repo}}/actions/artifacts?name=collaudo-v{versione}&per_page=100"))
    quando = [_quando(a["created_at"]) for a in dati.get("artifacts", []) if not a.get("expired") and a.get("created_at")]
    return max(0.0, (adesso - max(quando)).total_seconds() / 3600) if quando else None


def _scrivi_uscite(valori: dict[str, str]) -> None:
    righe = "".join(f"{k}={str(v).replace(chr(13), ' ').replace(chr(10), ' ')}\n" for k, v in valori.items())
    destinazione = os.environ.get("GITHUB_OUTPUT")
    if destinazione:
        with open(destinazione, "a", encoding="utf-8") as f:
            f.write(righe)
    print(righe, end="")


# =========================== comandi ===========================
def comando_decidi(forza: bool, quotidiano: bool = False) -> int:
    url, utente, password = (os.environ.get(n, "").strip() for n in ("PROVA_URL", "PROVA_UTENTE", "PROVA_PASSWORD"))
    if not (url and utente and password):
        print("Segreti della prova non impostati (PROVA_URL, PROVA_UTENTE, PROVA_PASSWORD): niente da collaudare.")
        _scrivi_uscite({"esito": "spento", "versione": "", "prova": "", "minuti": ""})
        return 0
    if not indirizzo_valido(url):
        print("PROVA_URL non valido: serve un indirizzo https:// (o http://127.x per le prove in locale).", file=sys.stderr)
        return 1
    adesso = _adesso()
    trovata = ultima_release(json.loads(_gh("release", "list", "--limit", "30", "--exclude-drafts", "--json",
                                            "tagName,createdAt,isDraft")), adesso)
    prova = versione_della_prova(url, utente, password)
    if trovata is None:
        print("Nessuna release del server v<N>: niente da collaudare.")
        _scrivi_uscite({"esito": "aspetta", "versione": "", "prova": prova or "nessuna", "minuti": ""})
        return 0
    ultima, minuti = trovata
    if forza:
        decisione, versione = "collauda", prova or ultima
    else:
        # corsa quotidiana: la versione in vigore si collauda comunque, senza guardare l'età dell'ultimo collaudo
        ore = ore_dall_ultimo_collaudo(ultima, adesso) if prova == ultima and not quotidiano else None
        gia = {ultima} if ore is not None else set()
        decisione, versione = decidi(ultima, prova, minuti, gia, ore), ultima
    assert decisione in ESITI
    _scrivi_uscite({"esito": decisione, "versione": versione, "prova": prova or "nessuna", "minuti": str(minuti)})
    return 0


def comando_esito(cartella: Path) -> int:
    riepilogo = cartella / "riepilogo.txt"
    fatto = riepilogo.is_file()          # senza riepilogo le misure non sono partite: niente artifact, la corsa dopo riprova
    if fatto:
        ok, problemi = esito(riepilogo.read_text(encoding="utf-8", errors="replace"))
    else:
        ok, problemi = False, ["nessun riepilogo: le misure non sono partite (prova irraggiungibile, accesso rifiutato o "
                               "Playwright non installato; il perché è nel registro della corsa)"]
    problemi = [maschera(p, os.environ.get("PROVA_URL")) for p in problemi]
    cartella.mkdir(parents=True, exist_ok=True)
    (cartella / "esito.txt").write_text(("ok\n" if ok else "non passa\n") + "".join(f"- {p}\n" for p in problemi), encoding="utf-8")
    dettaglio = "; ".join(problemi)
    if len(dettaglio) > 1500:
        dettaglio = dettaglio[:1500] + f" (e altro: {len(problemi)} problemi in tutto)"
    _scrivi_uscite({"ok": "true" if ok else "false", "fatto": "true" if fatto else "false", "dettaglio": dettaglio})
    return 0


RITARDO = "La prova non si aggiorna"
PREFISSO = "Collaudo della prova: v"
_TITOLO_COLLAUDO = re.compile(re.escape(PREFISSO) + r"\d+(?:\.\d+)* non passa")


def comando_segnala() -> int:
    """Le issue del collaudo e del ritardo, come le chiede l'esito della corsa. Una sola issue per versione: un collaudo
    ripetuto (quello quotidiano) che non passa commenta l'issue già aperta di quella versione. Testi senza indirizzi."""
    env = {n: os.environ.get(n, "").strip() for n in ("DECISIONE", "VERSIONE", "PROVA", "MINUTI", "OK", "DETTAGLIO", "CORSA")}
    decisione, ok, corsa = env["DECISIONE"], env["OK"], env["CORSA"]
    versione = versione_valida(env["VERSIONE"])
    if versione is None:
        print("Versione non valida: nessuna issue toccata.", file=sys.stderr)
        return 1
    aperte = json.loads(_gh("issue", "list", "--state", "open", "--limit", "1000", "--json", "number,title"))

    def numeri(scelta) -> list[str]:
        return [str(i["number"]) for i in aperte if scelta(str(i.get("title", "")))]

    def chiudi(numero: str, testo: str) -> None:
        _gh("issue", "comment", numero, "--body", testo)
        _gh("issue", "close", numero, "--reason", "completed")

    in_ritardo = numeri(lambda t: t.startswith(RITARDO))
    if decisione == "in-ritardo":
        if in_ritardo:
            print(f"Issue «{RITARDO}» già aperta: nessun commento nuovo.")
        else:
            _gh("issue", "create", "--title", RITARDO, "--label", "P2", "--label", "ci", "--body",
                f"La prova ha la versione {env['PROVA']}, ma l'ultima release del server è v{versione}, uscita "
                f"{env['MINUTI']} minuti fa (soglia {RITARDO_MINUTI} minuti).\n"
                "Da guardare: l'aggiornamento della prova sul server (aggiorna-app.sh con SCHIERAXI_ISTANZA=prova) o "
                f"l'account di collaudo.\nCorsa: {corsa}\nL'issue si chiude da sola quando la prova ha la versione nuova.")
    else:
        for numero in in_ritardo:
            chiudi(numero, f"La prova ha di nuovo la versione nuova (v{versione}). Corsa: {corsa}")

    if decisione != "collauda":
        return 0
    if ok == "false":
        titolo = f"{PREFISSO}{versione} non passa"
        problemi = "\n".join(f"- {p}" for p in env["DETTAGLIO"].split("; ") if p) or "- (nessun dettaglio)"
        stessa = numeri(lambda t: t == titolo)
        if stessa:
            _gh("issue", "comment", stessa[0], "--body", f"Ancora non passa:\n{problemi}\nCorsa: {corsa}")
        else:
            _gh("issue", "create", "--title", titolo, "--label", "P1", "--label", "ci", "--body",
                f"Il collaudo automatico della prova (workflow «Collaudo della prova») ha trovato:\n{problemi}\n"
                f"Corsa: {corsa}\nSi chiude da sola al primo collaudo che passa. Per riprovare subito: Actions > "
                "Collaudo della prova > Run workflow.")
    elif ok == "true":
        for numero in numeri(lambda t: _TITOLO_COLLAUDO.fullmatch(t) is not None):
            chiudi(numero, f"Il collaudo della prova passa con v{versione}. Corsa: {corsa}")
    else:
        print("Il collaudo non si è concluso (job «collauda» rotto): nessuna issue, la corsa è già rossa.")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="collaudo_prova.py", description="Collaudo dell'ambiente di prova dopo ogni rilascio.")
    sotto = p.add_subparsers(dest="comando", required=True)
    d = sotto.add_parser("decidi", help="aspetta, collauda, salta o in-ritardo (in $GITHUB_OUTPUT)")
    d.add_argument("--forza", action="store_true", help="corsa a mano: collauda subito, anche una versione già collaudata")
    d.add_argument("--quotidiano", action="store_true",
                   help="corsa fissa del mattino: collauda la versione in vigore sulla prova anche se collaudata da poco")
    e = sotto.add_parser("esito", help="ok e problemi dal riepilogo di foto.py (in $GITHUB_OUTPUT e in esito.txt)")
    e.add_argument("cartella", type=Path)
    sotto.add_parser("segnala", help="apre, commenta o chiude le issue del collaudo e del ritardo (dalle variabili d'ambiente)")
    a = p.parse_args(argv)
    if a.comando == "decidi":
        return comando_decidi(a.forza, a.quotidiano)
    if a.comando == "segnala":
        return comando_segnala()
    return comando_esito(a.cartella)


if __name__ == "__main__":
    for flusso in (sys.stdout, sys.stderr):
        flusso.reconfigure(encoding="utf-8")
    sys.exit(main())
