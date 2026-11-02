"""Scarica un'immagine da un indirizzo web scelto dall'utente (stemma o maglia), senza farsi usare per entrare nella rete di casa (SSRF).

Regole, tutte controllate qui e non altrove:
- solo https, solo porta 443, niente nome utente/password nell'indirizzo;
- il nome si risolve UNA volta; tutti gli indirizzi trovati devono essere pubblici (niente loopback, reti private, link-local,
  metadata del cloud 169.254.x, CGNAT, multicast, IPv6 mappati/6to4/NAT64) e la connessione va proprio a quell'indirizzo
  (il nome non viene risolto una seconda volta: contro il «DNS rebinding»);
- al massimo 3 reindirizzamenti, e ognuno ripassa da tutti i controlli;
- tempo massimo totale, tetto di 4 MB letto a pezzi, tipo riconosciuto dai byte (PNG/JPEG/WebP) come in `immagini.py`;
- nessun cookie né credenziale inviati; solo https quindi niente invii in chiaro.
Le funzioni di rete (`risolvi`, `apri`) si possono sostituire: i test non toccano la rete vera.
"""
from __future__ import annotations

import http.client
import ipaddress
import socket
import ssl
import threading
import time
from urllib.parse import quote, urljoin, urlsplit

from . import immagini

MAX_REDIRECT = 3
TEMPO_TOTALE = 15.0                 # secondi per tutto il lavoro
TEMPO_CONNESSIONE = 8.0             # secondi per ogni connessione/lettura
MAX_URL = 2000
PEZZO = 64 * 1024
_REDIRECT = (301, 302, 303, 307, 308)
_RETI_VIETATE = [ipaddress.ip_network(r) for r in ("64:ff9b::/96", "64:ff9b:1::/48", "2002::/16", "100.64.0.0/10")]


def indirizzo_pubblico(testo: str) -> bool:
    """Vero solo per un indirizzo IP che sta su internet (non rete locale, né della macchina, né interno)."""
    try:
        ip = ipaddress.ip_address(testo.split("%")[0])
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    if any(ip.version == r.version and ip in r for r in _RETI_VIETATE):
        return False
    return ip.is_global and not ip.is_multicast


def _scomponi(url: str) -> tuple[str, int, str]:
    url = (url or "").strip()
    if not url or len(url) > MAX_URL or any(ord(c) < 33 or ord(c) == 127 for c in url):
        raise ValueError("Indirizzo non valido: incolla un indirizzo web completo che inizia con https://")
    try:
        parti = urlsplit(url)
        porta = parti.port
    except ValueError:
        raise ValueError("Indirizzo non valido: incolla un indirizzo web completo che inizia con https://") from None
    if parti.scheme.lower() != "https":
        raise ValueError("Per sicurezza accetto solo indirizzi che iniziano con https://")
    if parti.username is not None or parti.password is not None:
        raise ValueError("L'indirizzo non può contenere nome utente o password")
    if not parti.hostname:
        raise ValueError("Indirizzo non valido: manca il nome del sito")
    if porta not in (None, 443):
        raise ValueError("Accetto solo indirizzi sulla porta normale di https")
    try:
        host = parti.hostname.encode("idna").decode("ascii")
    except UnicodeError:
        raise ValueError("Indirizzo non valido: nome del sito non riconosciuto") from None
    percorso = (parti.path or "/") + (f"?{parti.query}" if parti.query else "")
    # lettere accentate incollate così come sono (non ancora «%C3%A0»): la richiesta HTTP vuole solo ASCII; le «%xx» già presenti restano
    return host, 443, quote(percorso, safe="/%:@!$&'()*+,;=?-._~")


def _risolvi(host: str, porta: int) -> list[str]:
    try:
        trovati = socket.getaddrinfo(host, porta, type=socket.SOCK_STREAM)
    except (OSError, UnicodeError):
        raise ValueError("Non trovo il sito di quell'indirizzo: controlla di averlo scritto bene") from None
    visti: list[str] = []
    for *_, indirizzo in trovati:
        if indirizzo[0] not in visti:
            visti.append(indirizzo[0])
    return visti


class _Connessione(http.client.HTTPSConnection):
    """Si collega all'indirizzo IP già controllato, ma verifica il certificato e manda `Host` con il nome del sito."""

    def __init__(self, host: str, ip: str, porta: int, timeout: float):
        super().__init__(host, porta, timeout=timeout, context=ssl.create_default_context())
        self._ip = ip

    def connect(self):
        sock = socket.create_connection((self._ip, self.port), self.timeout)
        try:
            self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
        except Exception:
            sock.close()
            raise


class _Risposta:
    def __init__(self, conn: _Connessione, risposta: http.client.HTTPResponse):
        self._conn, self._r = conn, risposta
        self.status = risposta.status
        self.headers = risposta.headers

    def read(self, n: int) -> bytes:
        return self._r.read(n)

    def leggi_entro(self, n: int, secondi: float) -> bytes:
        """Una sola lettura (al massimo `n` byte, senza aspettare di riempire il pezzo) che non attende oltre `secondi`."""
        if self._conn.sock is not None:
            self._conn.sock.settimeout(max(0.5, secondi))
        return self._r.read1(n)

    def close(self) -> None:
        self._conn.close()


def _tronca(conn: http.client.HTTPConnection) -> None:
    """Interrompe subito una connessione ferma in lettura (un semplice close() da un altro filo non la sveglia)."""
    sock = conn.sock
    if sock is not None:
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
    conn.close()


def _apri(ip: str, host: str, porta: int, percorso: str, timeout: float) -> _Risposta:
    conn = _Connessione(host, ip, porta, timeout)
    guardia = threading.Timer(timeout, _tronca, (conn,))       # connessione + intestazioni lente (goccia a goccia) non superano il tempo dato
    guardia.daemon = True
    guardia.start()
    try:
        conn.request("GET", percorso, headers={"User-Agent": "SchieraXI/1 (immagine squadra)", "Accept": "image/png,image/jpeg,image/webp,*/*;q=0.5",
                                               "Accept-Encoding": "identity", "Connection": "close"})
        return _Risposta(conn, conn.getresponse())
    except Exception:
        conn.close()
        raise
    finally:
        guardia.cancel()


def scarica(url: str, *, risolvi=_risolvi, apri=_apri, orologio=time.monotonic) -> tuple[bytes, str]:
    """Scarica l'immagine e restituisce (byte, estensione). Alza ValueError con un messaggio in italiano per ogni problema."""
    fine = orologio() + TEMPO_TOTALE
    for giro in range(MAX_REDIRECT + 1):
        if orologio() > fine:
            raise ValueError("Il sito è troppo lento: riprova più tardi")
        host, porta, percorso = _scomponi(url)
        indirizzi = risolvi(host, porta)
        if not indirizzi:
            raise ValueError("Non trovo il sito di quell'indirizzo: controlla di averlo scritto bene")
        if not all(indirizzo_pubblico(i) for i in indirizzi):
            raise ValueError("Quell'indirizzo porta a una rete privata o interna: non lo scarico")
        risposta, ultimo_errore = None, None
        for ip in indirizzi[:3]:
            if orologio() > fine:
                break
            try:
                risposta = apri(ip, host, porta, percorso, min(TEMPO_CONNESSIONE, max(1.0, fine - orologio())))
                break
            except (OSError, http.client.HTTPException, ssl.SSLError) as e:
                ultimo_errore = e
        if risposta is None:
            raise ValueError("Non riesco a collegarmi al sito (o il suo certificato non è valido): riprova più tardi") from ultimo_errore
        try:
            if risposta.status in _REDIRECT:
                destinazione = risposta.headers.get("Location")
                if not destinazione:
                    raise ValueError("Il sito ha mandato un reindirizzamento senza destinazione")
                if giro >= MAX_REDIRECT:
                    raise ValueError("L'indirizzo rimanda ad altri indirizzi troppe volte")
                url = urljoin(f"https://{host}{percorso}", destinazione.strip())
                continue
            if risposta.status != 200:
                raise ValueError(f"Il sito ha risposto con un errore ({risposta.status}): controlla che l'immagine sia pubblica")
            try:
                dichiarata = int(risposta.headers.get("Content-Length") or 0)
            except ValueError:
                dichiarata = 0
            if dichiarata > immagini.MAX_BYTE:
                raise ValueError("Immagine troppo grande (massimo 4 MB)")
            pezzi, totale = [], 0
            while True:
                if orologio() > fine:
                    raise ValueError("Il sito è troppo lento: riprova più tardi")
                try:
                    if hasattr(risposta, "leggi_entro"):
                        pezzo = risposta.leggi_entro(PEZZO, fine - orologio())
                    else:
                        pezzo = risposta.read(PEZZO)
                except (OSError, http.client.HTTPException):
                    raise ValueError("Il sito ha interrotto il trasferimento: riprova più tardi") from None
                if not pezzo:
                    break
                totale += len(pezzo)
                if totale > immagini.MAX_BYTE:
                    raise ValueError("Immagine troppo grande (massimo 4 MB)")
                pezzi.append(pezzo)
            dati = b"".join(pezzi)
            estensione = immagini.estensione_da_contenuto(dati)
            if estensione is None:
                raise ValueError("Quell'indirizzo non porta a un'immagine PNG, JPEG o WebP (forse è una pagina web: apri l'immagine da sola e copia quell'indirizzo)")
            return dati, estensione
        finally:
            risposta.close()
    raise ValueError("L'indirizzo rimanda ad altri indirizzi troppe volte")
