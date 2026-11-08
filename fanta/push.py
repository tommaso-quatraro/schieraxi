"""Notifiche web native (Web Push): arrivano direttamente da questa app, senza l'app ntfy e senza canali pubblici.

- chiavi VAPID (l'identità del server): generate la prima volta e tenute in dati/vapid.json (mai in git);
- iscrizioni: ogni dispositivo che le attiva (iPhone con l'app sulla Home, PC, iPad) lascia la sua in dati/push.json;
- invio: a tutti i dispositivi iscritti, insieme, con un tempo massimo totale (`limiti.MAX_SECONDI_INVIO`): un servizio lento non
  ritarda gli altri dispositivi né il giro degli avvisi; quelle scadute (404/410) si tolgono da sole.
Su iPhone servono iOS 16.4 o più e l'app aggiunta alla schermata Home.
"""
from __future__ import annotations

import base64
import concurrent.futures
import functools
import hashlib
import http.client
import io
import ipaddress
import json
import os
import re
import threading
import time
import uuid
from pathlib import Path

from .percorsi import RADICE, scrittura_permessa

FILE_VAPID = RADICE / "dati" / "vapid.json"
FILE_ISCRIZIONI = RADICE / "dati" / "push.json"
MASSIMO_DISPOSITIVI = 8
CONTATTO = "mailto:schieraxi@users.noreply.github.com"      # richiesto dal protocollo (deve essere un mailto:): un recapito di chi manda le notifiche; qui uno neutro


def _riservato(percorso: Path) -> None:
    """Un file creato da una versione vecchia (leggibile da tutti) diventa leggibile solo dal proprietario. Su Windows non fa danni."""
    try:
        if percorso.exists():
            os.chmod(percorso, 0o600)
    except OSError:
        pass


def scrivi_sicuro(percorso: Path, testo: str) -> None:
    """Come `percorsi.scrivi_sicuro` (file temporaneo e poi rinomina), ma il file nasce già leggibile solo dal proprietario (600):
    dentro ci sono la chiave privata VAPID e gli indirizzi di notifica dei dispositivi.
    Come lì, nella cartella di un account eliminato non scrive: il segno di cancellazione si guarda prima e dopo."""
    if not scrittura_permessa(percorso):
        return
    percorso.parent.mkdir(parents=True, exist_ok=True)
    tmp = percorso.with_name(f"{percorso.name}.{uuid.uuid4().hex[:8]}.tmp")
    descrittore = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descrittore, "w", encoding="utf-8") as f:
        f.write(testo)
    os.replace(tmp, percorso)
    scrittura_permessa(percorso)      # eliminato mentre scrivevamo: si toglie quello che è rinato


def _b64(dati: bytes) -> str:
    return base64.urlsafe_b64encode(dati).rstrip(b"=").decode()


def chiavi(percorso: Path | None = None) -> dict:
    """{"privata", "pubblica"} in base64 URL-safe; si creano la prima volta."""
    percorso = percorso or FILE_VAPID
    try:
        d = json.loads(percorso.read_text(encoding="utf-8"))
        if d.get("privata") and d.get("pubblica"):
            _riservato(percorso)                  # anche il file creato da una versione vecchia
            return d
    except (OSError, ValueError, AttributeError):
        pass
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    chiave = ec.generate_private_key(ec.SECP256R1())
    privata = chiave.private_numbers().private_value.to_bytes(32, "big")
    pubblica = chiave.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    d = {"privata": _b64(privata), "pubblica": _b64(pubblica)}
    scrivi_sicuro(percorso, json.dumps(d))
    try:
        percorso.chmod(0o600)                     # la chiave privata la legge solo chi ha creato il file
    except OSError:
        pass
    return d


def iscrizioni(percorso: Path | None = None) -> list[dict]:
    try:
        d = json.loads((percorso or FILE_ISCRIZIONI).read_text(encoding="utf-8"))
        _riservato(percorso or FILE_ISCRIZIONI)
        return [s for s in d if isinstance(s, dict) and s.get("endpoint")] if isinstance(d, list) else []
    except (OSError, ValueError):
        return []


TEMPO_DNS = 5.0                      # secondi al massimo per risolvere un nome
DURATA_CACHE_DNS = 300               # 5 minuti: l'indirizzo controllato e quello usato per connettersi sono lo stesso
_cache_dns: dict[str, tuple[float, list[str]]] = {}
_blocco_dns = threading.Lock()
_NOME_SITO = re.compile(r"^(?=.{4,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+(xn--[a-z0-9-]{2,59}|[a-z]{2,24})$")


def _risolvi_host(host: str) -> list[str]:
    """Gli indirizzi di un nome, con un tempo massimo (la risoluzione di sistema da sola non ne ha)."""
    from . import scarica_immagine
    esecutore = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        return esecutore.submit(scarica_immagine._risolvi, host, 443).result(timeout=TEMPO_DNS)
    except concurrent.futures.TimeoutError:
        raise ValueError("Nome non risolto in tempo") from None
    finally:
        esecutore.shutdown(wait=False)


def _forma_endpoint(ep: str) -> str:
    """Controlli senza rete: solo https, porta 443, niente credenziali; il sito e' un nome normale (lettere, punti, ultima parte alfabetica:
    niente 0x7f.1, 127.1, localhost., nomi interni) oppure un indirizzo IP pubblico scritto in forma canonica. Restituisce il sito."""
    from urllib.parse import urlsplit
    from .scarica_immagine import indirizzo_pubblico
    try:
        parti = urlsplit(ep)
        porta = parti.port
    except ValueError:
        raise ValueError("Iscrizione non valida") from None
    host = (parti.hostname or "").lower()
    if (parti.scheme.lower() != "https" or not host or parti.username is not None or parti.password is not None or porta not in (None, 443)
            or any(ord(c) < 33 or ord(c) == 127 for c in ep) or host.endswith(".")):
        raise ValueError("Iscrizione non valida")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    if ip is not None:
        if str(ip) != host or not indirizzo_pubblico(host):          # solo la forma canonica e solo indirizzi pubblici
            raise ValueError("Iscrizione non valida")
    elif not _NOME_SITO.match(host) or host.endswith((".local", ".internal", ".lan", ".localhost", ".home.arpa", ".localdomain", ".intranet")):
        raise ValueError("Iscrizione non valida")
    return host


def indirizzi_verificati(host: str) -> list[str]:
    """Gli indirizzi IP del sito, tutti pubblici (altrimenti ValueError). Il risultato resta 5 minuti: la connessione di invio usa
    proprio questi, senza risolvere una seconda volta (contro il «DNS rebinding»)."""
    from .scarica_immagine import indirizzo_pubblico
    if indirizzo_pubblico(host):
        return [host]
    ora = time.monotonic()
    with _blocco_dns:
        voce = _cache_dns.get(host)
        if voce and ora - voce[0] < DURATA_CACHE_DNS:
            return list(voce[1])
    try:
        trovati = _risolvi_host(host)
    except OSError:
        raise ValueError("Nome non risolto") from None
    if not trovati or not all(indirizzo_pubblico(i) for i in trovati):
        raise ValueError("Indirizzo non pubblico")
    with _blocco_dns:
        if len(_cache_dns) > 200:
            _cache_dns.clear()
        _cache_dns[host] = (ora, list(trovati))
    return list(trovati)


def indirizzo_consentito(ep: str) -> bool:
    """Vero se l'indirizzo di consegna e' pubblico (anche dopo la risoluzione del nome): il server non deve poter essere usato per raggiungere la rete di casa."""
    try:
        indirizzi_verificati(_forma_endpoint(ep))
    except ValueError:
        return False
    return True


class _Risposta:
    def __init__(self, stato: int, motivo: str, testo: str, intestazioni):
        self.status_code, self.reason, self.text, self.headers = stato, motivo, testo, intestazioni     # `reason`: pywebpush lo
        self.ok = 200 <= stato < 400                                                                   # legge negli errori (404/410)


def _orologio() -> float:
    return time.monotonic()


class _LetturaEntro(io.RawIOBase):
    """Le letture della risposta di un servizio di notifica con una scadenza totale (`fine`, sull'orologio `_orologio`): prima di
    ognuna il tempo che resta diventa il tempo massimo del socket, e a tempo finito si ferma. Serve con un servizio che risponde
    un byte alla volta: lì il tempo massimo di ogni singola lettura, da solo, non finisce mai."""

    def __init__(self, file, sock, fine: float):
        super().__init__()
        self._file, self._sock, self._fine = file, sock, fine

    def readable(self) -> bool:
        return True

    def readinto(self, b) -> int:
        resta = self._fine - _orologio()
        if resta <= 0:
            raise TimeoutError("Tempo dell'invio finito")
        self._sock.settimeout(resta)
        return self._file.readinto1(b)          # una lettura sola: il tempo si ricontrolla prima della successiva

    def close(self) -> None:
        if not self.closed:
            self._file.close()
        super().close()


class _RispostaEntro(http.client.HTTPResponse):
    """La risposta del servizio di notifica, letta tutta (riga di stato, intestazioni e corpo) entro la scadenza `fine`."""

    def __init__(self, sock, *args, fine: float, **kwargs):
        super().__init__(sock, *args, **kwargs)
        self.fp = io.BufferedReader(_LetturaEntro(self.fp, sock, fine))


class SessioneFissata:
    """Al posto di `requests.Session` per pywebpush: invia il POST all'indirizzo IP GIA' controllato (verificando il certificato del nome),
    senza seguire reindirizzamenti, senza proxy dell'ambiente e senza una seconda risoluzione del nome.
    Con `fine` (sull'orologio `_orologio`) l'invio sta entro quel momento: collegamento e stretta di mano TLS (il tempo massimo del
    socket vale per tutta la stretta di mano), richiesta e risposta, anche goccia a goccia. `chiudi()` interrompe le connessioni
    ancora aperte: chi manda l'avviso non le aspetta oltre."""

    def __init__(self, fine: float | None = None):
        self.fine = fine
        self._aperte: set = set()
        self._blocco = threading.Lock()
        self._chiusa = False

    def _tempo(self, timeout: float) -> float:
        """Il tempo massimo del prossimo collegamento: `timeout`, ma mai oltre la scadenza (passata: TimeoutError)."""
        if self.fine is None:
            return timeout
        resta = self.fine - _orologio()
        if resta <= 0:
            raise TimeoutError("Tempo dell'invio finito")
        return min(timeout, resta)

    def chiudi(self) -> None:
        from .scarica_immagine import _tronca
        with self._blocco:
            self._chiusa = True
            aperte = list(self._aperte)
        for conn in aperte:
            _tronca(conn)

    def post(self, url: str, data=None, headers=None, timeout: float = 15, **_ignorati) -> _Risposta:
        from urllib.parse import urlsplit
        from .scarica_immagine import _Connessione
        host = _forma_endpoint(url)
        parti = urlsplit(url)
        percorso = (parti.path or "/") + (f"?{parti.query}" if parti.query else "")
        ultimo: Exception | None = None
        for ip in indirizzi_verificati(host)[:3]:
            conn = _Connessione(host, ip, 443, self._tempo(timeout))
            if self.fine is not None:
                conn.response_class = functools.partial(_RispostaEntro, fine=self.fine)
            with self._blocco:
                if self._chiusa:
                    raise TimeoutError("Tempo dell'invio finito")
                self._aperte.add(conn)
            try:
                conn.request("POST", percorso, body=data, headers={**(headers or {}), "Connection": "close"})
                r = conn.getresponse()
                return _Risposta(r.status, getattr(r, "reason", ""), r.read(65536).decode("utf-8", "replace"), r.headers)
            except (OSError, http.client.HTTPException) as e:
                ultimo = e
            finally:
                with self._blocco:
                    self._aperte.discard(conn)
                conn.close()
        if self.fine is not None and _orologio() >= self.fine:
            raise TimeoutError("Tempo dell'invio finito") from ultimo
        raise ConnectionError("Servizio di notifica non raggiungibile") from ultimo


def _valida(sub: dict) -> dict:
    ep, k = sub.get("endpoint"), sub.get("keys") or {}
    if not isinstance(ep, str) or len(ep) > 600:
        raise ValueError("Iscrizione non valida")
    try:
        indirizzi_verificati(_forma_endpoint(ep))          # anche il nome deve portare a un indirizzo pubblico, subito
    except ValueError:
        raise ValueError("Iscrizione non valida") from None
    if not isinstance(k.get("p256dh"), str) or not isinstance(k.get("auth"), str) or len(k["p256dh"]) > 200 or len(k["auth"]) > 100:
        raise ValueError("Iscrizione non valida")
    return {"endpoint": ep, "keys": {"p256dh": k["p256dh"], "auth": k["auth"]}}


_blocco_iscrizioni = threading.Lock()          # leggere-modificare-scrivere una alla volta: due iscrizioni insieme non si perdono


def iscrivi(sub: dict, percorso: Path | None = None) -> list[dict]:
    nuova = _valida(sub)                       # (rete) fuori dal blocco
    with _blocco_iscrizioni:
        lista = [s for s in iscrizioni(percorso) if s["endpoint"] != nuova["endpoint"]] + [nuova]
        lista = lista[-MASSIMO_DISPOSITIVI:]
        scrivi_sicuro(percorso or FILE_ISCRIZIONI, json.dumps(lista))
    return lista


def togli(endpoint: str, percorso: Path | None = None) -> list[dict]:
    with _blocco_iscrizioni:
        lista = [s for s in iscrizioni(percorso) if s["endpoint"] != endpoint]
        scrivi_sicuro(percorso or FILE_ISCRIZIONI, json.dumps(lista))
    return lista


def maschera(ep: str) -> str:
    """L'indirizzo di consegna e' un segreto (chi lo conosce puo' mandare notifiche): nei log restano solo il sito e una sigla breve."""
    from urllib.parse import urlsplit
    try:
        host = urlsplit(ep).hostname or "?"
    except ValueError:
        host = "?"
    return f"{host}#{hashlib.sha256(ep.encode()).hexdigest()[:6]}"


def _annota(testo: str) -> None:
    """Gli errori dell'invio restano in dati/push.log: senza, una notifica che non parte sembrerebbe solo "arrivata da ntfy"."""
    try:
        from datetime import datetime
        f = FILE_ISCRIZIONI.with_name("push.log")
        righe = (f.read_text(encoding="utf-8").splitlines() if f.exists() else [])[-49:] + [f"{datetime.now():%F %T} {testo}"]
        scrivi_sicuro(f, chr(10).join(righe) + chr(10))
    except OSError:
        pass


def invia(titolo: str, testo: str, priorita: int = 3, tag: str = "soccer", percorso: Path | None = None, file_chiavi: Path | None = None) -> int:
    """Manda la notifica a tutti i dispositivi iscritti, tutti insieme, e restituisce quanti l'hanno ricevuta.
    Tempo massimo in tutto: `limiti.MAX_SECONDI_INVIO` (variabile FANTA_MAX_SECONDI_INVIO). Un dispositivo con un servizio lento non
    fa aspettare gli altri; chi non ha risposto a tempo finito si lascia (una riga in push.log) e il giro degli avvisi va avanti."""
    lista = iscrizioni(percorso)
    if not lista:
        return 0
    from pywebpush import WebPushException, webpush
    from . import limiti
    from .notifiche import SEZIONE_PER_TAG
    privata = chiavi(file_chiavi)["privata"]
    # `sezione` e `priorita` li usa l'app Android (ricevuta con UnifiedPush): il tocco apre la schermata giusta. Il web usa `url`:
    # gli avvisi sulla formazione (cambi, «cambia la formazione», promemoria) aprono la Formazione, gli altri l'app com'è.
    sezione = SEZIONE_PER_TAG.get(tag, "lega")
    payload = json.dumps({"title": titolo, "body": testo, "tag": tag, "url": "/?vista=formazione" if sezione == "formazione" else "/",
                          "sezione": sezione, "priorita": priorita})
    sessione = SessioneFissata(fine=_orologio() + limiti.valore("MAX_SECONDI_INVIO"))

    def a_uno(s: dict) -> tuple[str, str]:
        """Un dispositivo: ("consegnata" | "scaduta" | "rifiutata" | "ignorata" | "errore", tipo dell'errore). Mai eccezioni."""
        try:
            if not indirizzo_consentito(s["endpoint"]):
                return "ignorata", ""
            webpush(subscription_info=s, data=payload, vapid_private_key=privata, vapid_claims={"sub": CONTATTO},
                    ttl=3600, headers={"Urgency": "high" if priorita >= 4 else "normal"}, timeout=15, requests_session=sessione)
            return "consegnata", ""
        except WebPushException as e:
            return ("scaduta" if getattr(e.response, "status_code", None) in (404, 410) else "rifiutata"), ""
        except Exception as e:  # noqa: BLE001 - un dispositivo che non risponde non deve fermare gli altri
            return "errore", type(e).__name__          # mai il testo dell'errore: puo' contenere il percorso segreto

    esecutore = concurrent.futures.ThreadPoolExecutor(max_workers=min(len(lista), MASSIMO_DISPOSITIVI), thread_name_prefix="avviso")
    try:
        futuri = [esecutore.submit(a_uno, s) for s in lista]
        concurrent.futures.wait(futuri, timeout=max(0.0, sessione.fine - _orologio()))
    finally:
        sessione.chiudi()                              # a tempo finito chi e' ancora collegato si ferma: non lo aspetta nessuno
        esecutore.shutdown(wait=False, cancel_futures=True)
    consegnate, scadute = 0, []
    for s, futuro in zip(lista, futuri):              # registro e iscrizioni si scrivono da qui, uno alla volta
        esito, errore = futuro.result() if futuro.done() and not futuro.cancelled() else ("errore", "TimeoutError")
        if esito == "consegnata":
            consegnate += 1
        elif esito == "scaduta":
            scadute.append(s["endpoint"])
        elif esito == "ignorata":
            _annota(f"Iscrizione ignorata (indirizzo non pubblico o non valido): {maschera(s['endpoint'])}")
        elif esito == "errore":
            _annota(f"{errore} ({maschera(s['endpoint'])})")
    for ep in scadute:
        togli(ep, percorso)
    return consegnate
