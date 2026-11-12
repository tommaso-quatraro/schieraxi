"""Le rotte HTTP degli account (/api/account/...) e dell'amministratore (/api/admin/...), più il controllo d'accesso che il
middleware di server.py applica a OGNI richiesta quando FANTA_MULTIUTENTE=1.

Regola di fondo (divieto di default): con l'interruttore acceso, tutto ciò che sta sotto /api/ e non è nell'elenco
PUBBLICI_API risponde 401 senza una sessione valida. Una funzione nuova nasce quindi chiusa, non aperta per dimenticanza.
Con l'interruttore spento non cambia niente: nessun accesso, un solo utente locale implicito.
"""
from __future__ import annotations

import ipaddress
import os
import re
from contextlib import closing

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from . import account, account_email, contesto, fonti_attive, funzioni, percorsi, posta, registro, social
from .account import ErroreAccount, Utente

COOKIE = "fanta_sessione"
# raggiungibili senza sessione: entrare, iscriversi, recuperare la password
PUBBLICI_API = {"/api/account/accedi", "/api/account/registra", "/api/account/recupero", "/api/account/recupero-email",
                "/api/account/recupero-email/conferma", "/api/account/registra/conferma",
                # accesso con Google: il ritorno arriva da un altro sito senza cookie; se manca la configurazione rispondono 404
                "/api/account/social/google/inizia", "/api/account/social/google/ritorno", "/api/account/social/scambio",
                "/api/account/social/completa",
                # controllo esterno: solo «il sito è vivo» e l'ora dell'ultimo aggiornamento, nessun dato personale
                "/api/salute"}
# il minimo statico per mostrare la pagina di accesso (nessun dato di nessuno): pagina, codice dell'app, icone, robots
STATICI = {"/", "/sw.js", "/manifest.webmanifest", "/app.js", "/impostazioni.js", "/dafare.js", "/primoavvio.js", "/anteprima.js", "/stile.css", "/robots.txt", "/icona.svg",
            "/privacy", "/termini", "/crediti", "/elimina-account", "/legale.js", "/testi.js", "/avatar.js"}
STATICI_PREFISSI = ("/icone/", "/.well-known/", "/caratteri/")     # caratteri: la pagina d'accesso li usa prima della sessione
_ICONA = re.compile(r"^/icona-(maskable-)?\d+\.png$")
# immagini del manifest (schermate mostrate all'installazione): le chiede il browser senza sessione
_SCREENSHOT = re.compile(r"^/screenshot-(largo|stretto-\d+)\.png$")
# riservati all'amministratore (oltre a tutto /api/admin/)
SOLO_AMMINISTRATORE = {"/api/aggiorna", "/api/stato-dati"}
# il token del widget (Authorization: Bearer fw_...) apre SOLO queste letture; ogni altra rotta o metodo: 403
PERMESSI_WIDGET = {"/api/oggi", "/api/widget", "/api/live"}
LETTURE_WIDGET_ALL_ORA = (240, account.ORA)          # tetto per utente: un widget si aggiorna ogni 15-30 minuti

router = APIRouter()


# ---------------------------------------------------------------- chi è che chiede
def dietro_proxy() -> bool:
    """FANTA_PROXY=1: il server sta dietro a un proxy fidato (per esempio un proxy inverso) che aggiunge X-Forwarded-For/Proto."""
    return os.environ.get("FANTA_PROXY", "").strip() == "1"


def ip_reale(request: Request) -> str | None:
    """L'indirizzo di chi chiede, solo se si vede davvero. Dietro un proxy si legge X-Forwarded-For (l'ultimo valore, quello che
    aggiunge il proxy: gli altri li può scrivere chiunque), ma solo con FANTA_PROXY=1. Altrimenti, se la connessione arriva da
    questo stesso computer (un proxy locale) l'indirizzo non dice niente e vale None: i limiti per indirizzo non si applicano."""
    if dietro_proxy():
        # più intestazioni X-Forwarded-For valgono come una sola lista: conta l'ultimo valore, quello del proxy
        valori = ",".join(request.headers.getlist("x-forwarded-for")) if hasattr(request.headers, "getlist") else             request.headers.get("x-forwarded-for", "")
        ultimo = _indirizzo(valori.split(",")[-1])
        if ultimo:
            return ultimo
    host = request.client.host if request.client else None
    return None if not host or host.startswith("127.") or host in ("::1", "::ffff:127.0.0.1") else _indirizzo(host) or host[:64]


def _indirizzo(testo: str) -> str | None:
    """Un indirizzo IP valido (senza porta), oppure None: un'intestazione inventata non diventa una chiave dei limiti.
    IPv6: vale il prefisso /64 (`2001:db8:1:2::/64`), perché chi ne ha uno ne ha miliardi e cambiandoli aggirerebbe ogni limite
    per indirizzo. Un IPv4 scritto come IPv6 (`::ffff:1.2.3.4`) torna IPv4."""
    t = testo.strip()[:64]
    if t.startswith("[") and "]" in t:
        t = t[1:t.index("]")]
    elif t.count(":") == 1:
        t = t.split(":")[0]
    try:
        ind = ipaddress.ip_address(t.split("%")[0])
    except ValueError:
        return None
    if isinstance(ind, ipaddress.IPv6Address):
        if ind.ipv4_mapped:
            return str(ind.ipv4_mapped)
        return str(ipaddress.IPv6Network((ind, 64), strict=False))
    return str(ind)


def e_https(request: Request) -> bool:
    if dietro_proxy():
        return request.headers.get("x-forwarded-proto", "").split(",")[-1].strip().lower() == "https"
    return request.url.scheme == "https"


def token_della_richiesta(request: Request) -> str | None:
    """Le app native mandano `Authorization: Bearer <token>`; il web ha il cookie (HttpOnly, quindi invisibile a JavaScript)."""
    auth = request.headers.get("authorization", "")
    if auth[:7].lower() == "bearer ":
        return auth[7:].strip() or None
    return request.cookies.get(COOKIE)


def identifica(request: Request) -> Utente | None:
    token = token_della_richiesta(request)
    if not token:
        return None
    with closing(account.apri()) as db:
        return account.utente_da_token(db, token)


def bearer_widget(request: Request) -> str | None:
    """Il token del widget, se la richiesta ne porta uno (solo nell'intestazione Authorization, mai in un cookie)."""
    auth = request.headers.get("authorization", "")
    if auth[:7].lower() == "bearer " and auth[7:].strip().startswith(account.PREFISSO_TOKEN_WIDGET):
        return auth[7:].strip()
    return None


def _controllo_widget(request: Request, token: str) -> JSONResponse | None:
    """Il token del widget vale solo per leggere (GET) /api/oggi, /api/widget e /api/live. None = tutto bene (e `request.state.utente` è il proprietario);
    il token non è una sessione: non si sostituisce a un accesso e non apre niente altro."""
    with closing(account.apri()) as db:
        utente = account.utente_da_token_widget(db, token)
        if utente is None:
            return None                                   # sconosciuto, scaduto o revocato: si prosegue come senza token (sessione o 401)
        if request.method not in ("GET", "HEAD") or request.url.path not in PERMESSI_WIDGET:
            return JSONResponse(status_code=403, content={"detail": "Questo accesso serve solo al widget"})
        account.limite.consuma(db, account._chiave("widget", utente.id), *LETTURE_WIDGET_ALL_ORA)
    request.state.utente = utente
    request.state.solo_widget = True
    return None


def _pubblico(percorso: str) -> bool:
    return percorso in PUBBLICI_API or percorso in STATICI or percorso.startswith(STATICI_PREFISSI) or bool(_ICONA.match(percorso)) or bool(_SCREENSHOT.match(percorso))


# Senza account (FANTA_MULTIUTENTE spento) chi chiede ha i poteri dell'amministratore: il server risponde SOLO a richieste
# dirette da questo stesso computer, senza proxy in mezzo (un proxy aggiunge X-Forwarded-* o Forwarded e porterebbe dentro
# chiunque lo raggiunga). Per usarlo da altri dispositivi si accendono gli account.
SOLO_LOCALE = "Questo server non ha gli account accesi: risponde solo dal computer su cui gira"
AVVISO_SOLO_LOCALE = ("Account spenti (FANTA_MULTIUTENTE non è 1): il server risponde solo alle richieste dirette da questo computer "
                      "(127.0.0.1 o ::1), aperte con un indirizzo 127.x.x.x, localhost o [::1], e senza proxy; tutte le altre "
                      "ricevono 403. "
                      "Per usarlo da altri dispositivi o dietro un "
                      "proxy imposta FANTA_MULTIUTENTE=1 nelle variabili del servizio.")
_INTESTAZIONI_PROXY = ("forwarded", "via", "x-real-ip", "x-client-ip", "true-client-ip", "cf-connecting-ip")
# L'indirizzo scritto nella richiesta (intestazione Host) deve essere questo computer: una pagina di un altro sito che fa puntare il
# suo nome a 127.0.0.1 («DNS rebinding») arriva da qui, ma con il suo nome nell'Host. Vale tutta la rete 127.0.0.0/8 (foto e
# collaudi avviano il server su 127.0.0.{20+…}): ogni numero da 0 a 255, senza zeri davanti.
_OTTETTO = r"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)"
_HOST_LOCALE = re.compile(rf"(?:127(?:\.{_OTTETTO}){{3}}|localhost|\[::1\])(?::\d{{1,5}})?")


def richiesta_locale(request: Request) -> bool:
    """Vero solo per una connessione diretta da loopback, verso 127.x.x.x, localhost o [::1] (con o senza porta), senza
    intestazioni di proxy. `testclient` è il nome che il client di prova di Starlette dà a sé stesso, e `testserver` quello che dà
    al server: un server vero mette sempre l'indirizzo della connessione (mai un nome)."""
    host = request.client.host if request.client else None
    destinazione = request.headers.get("host", "").strip().lower()
    if not _HOST_LOCALE.fullmatch(destinazione) and not (host == "testclient" and destinazione == "testserver"):
        return False
    if host != "testclient":
        try:
            ind = ipaddress.ip_address((host or "").split("%")[0])
        except ValueError:
            return False
        if isinstance(ind, ipaddress.IPv6Address) and ind.ipv4_mapped:
            ind = ind.ipv4_mapped
        if not ind.is_loopback:
            return False
    nomi = {k.lower() for k in request.headers.keys()}
    return not any(n.startswith("x-forwarded-") or n in _INTESTAZIONI_PROXY for n in nomi)


def controllo_accesso(request: Request) -> JSONResponse | None:
    """Chiamato dal middleware: None = si può proseguire (e `request.state.utente` è chi chiede), altrimenti la risposta da dare."""
    request.state.utente = None
    if not account.multiutente():
        if richiesta_locale(request):
            return None
        return JSONResponse(status_code=403, content={"detail": SOLO_LOCALE})
    percorso = request.url.path
    token_widget = bearer_widget(request) if percorso.startswith("/api/") else None
    if token_widget:
        try:
            rifiuto = _controllo_widget(request, token_widget)
        except ErroreAccount as e:
            return errore_account(None, e)
        if rifiuto is not None or getattr(request.state, "solo_widget", False):
            return rifiuto
    if _pubblico(percorso):
        return None
    try:
        utente = identifica(request)
    except ErroreAccount as e:                      # database degli account illeggibile: risposta chiara, niente traccia
        return errore_account(None, e)
    if utente is None:
        return JSONResponse(status_code=401, content={"detail": "Accesso richiesto", "multiutente": True,
                                                                         "registrazione": account_email.modo_registrazione(),
                                                                         "social": social.provider_attivi(),
                                                                         "email_attiva": posta.attiva()})
    request.state.utente = utente
    if (percorso in SOLO_AMMINISTRATORE or percorso.startswith("/api/admin/")) and not utente.amministratore:
        return JSONResponse(status_code=403, content={"detail": "Solo per l'amministratore"})
    return None


# Invito inesistente, scaduto, revocato o già usato (`account.INVITO_NON_VALIDO`, da registrazione, conferma dell'email e Google):
# a chi si iscrive un messaggio solo, che non dice quale dei casi è ma dice cosa fare (#580).
INVITO_DA_CHIEDERE = "Invito non valido, scaduto o già usato: chiedine uno nuovo a chi te l'ha mandato"


def errore_account(_, e: ErroreAccount) -> JSONResponse:
    messaggio = INVITO_DA_CHIEDERE if e.messaggio == account.INVITO_NON_VALIDO else e.messaggio
    corpo = ({"detail": messaggio} | ({"riprova_tra": e.riprova_tra} if e.riprova_tra else {})
             | ({"codice": e.codice} if getattr(e, "codice", None) else {}))      # secondi: anche nel corpo, non solo in Retry-After
    return JSONResponse(status_code=e.stato, content=corpo,
                        headers={"Retry-After": str(e.riprova_tra)} if e.riprova_tra else None)


POSTA_SPENTA = ("Su questo server l'invio delle email è spento: il codice non può arrivare. "
                "Per la password usa il codice di recupero.")


def _posta_accesa() -> None:
    """Con FANTA_MAIL=spento nessun codice parte: si dice subito (503, `posta_spenta`) invece di far aspettare un'email che non
    arriva. Non dice niente su chi ha un account: vale uguale per ogni indirizzo."""
    if not posta.attiva():
        raise ErroreAccount(POSTA_SPENTA, 503, codice="posta_spenta")


def _attivo() -> None:
    if not account.multiutente():
        raise HTTPException(404, "Gli account non sono attivi")


def utente_corrente(request: Request) -> Utente:
    """Dipendenza: chi sta chiedendo. A interruttore spento è l'utente locale implicito; acceso, serve una sessione (401 altrimenti)."""
    if not account.multiutente():
        return account.UTENTE_LOCALE
    utente = getattr(request.state, "utente", None) or identifica(request)
    if utente is None:
        raise HTTPException(401, "Accesso richiesto")
    return utente


def solo_amministratore(utente: Utente = Depends(utente_corrente)) -> Utente:
    if not utente.amministratore:
        raise HTTPException(403, "Solo per l'amministratore")
    return utente


# ---------------------------------------------------------------- cookie
def _metti_cookie(risposta: Response, request: Request, token: str) -> None:
    risposta.set_cookie(COOKIE, token, max_age=int(account.DURATA_SESSIONE.total_seconds()), path="/", httponly=True,
                        samesite="strict", secure=e_https(request))


def _togli_cookie(risposta: Response, request: Request) -> None:
    risposta.delete_cookie(COOKIE, path="/", httponly=True, samesite="strict", secure=e_https(request))


def _dispositivo(request: Request) -> str:
    return request.headers.get("user-agent", "")[:120]


# ---------------------------------------------------------------- rotte
class Credenziali(BaseModel):
    nome_utente: str = Field(max_length=100)
    password: str = Field(max_length=500)
    nativo: bool = False             # app native: il token torna nella risposta (da mandare come Bearer) invece che nel cookie


class Iscrizione(Credenziali):
    invito: str = Field(default="", max_length=100)               # facoltativo: con FANTA_REGISTRAZIONE=aperta si entra senza
    email: str | None = Field(default=None, max_length=300)       # facoltativa: i client vecchi non la mandano
    accetto_termini: bool | None = None                           # facoltativo: assente = client vecchio (si iscrive, senza traccia); false = errore


# `endpoint_push` (facoltativo, sulle rotte che chiudono tutto: cambio password e recupero): l'indirizzo delle notifiche web di
# QUESTO dispositivo. Resta iscritto; tutte le altre iscrizioni dell'utente si tolgono. Non aggiunge mai un'iscrizione che non c'era.
class Recupero(BaseModel):
    nome_utente: str = Field(max_length=100)
    codice: str = Field(max_length=100)
    nuova: str = Field(max_length=500)
    endpoint_push: str | None = Field(default=None, max_length=600)


class NuovaEmail(BaseModel):
    email: str = Field(max_length=300)
    password: str = Field(max_length=500)


class ConfermaIscrizione(BaseModel):
    email: str = Field(max_length=300)
    codice: str = Field(max_length=40)
    iscrizione: str = Field(default="", max_length=100)       # il segreto restituito da /registra: lega il codice a chi l'ha chiesto
    nativo: bool = False


class CodiceEmail(BaseModel):
    codice: str = Field(max_length=40)


class RichiestaRecuperoEmail(BaseModel):
    email: str = Field(max_length=300)


class RecuperoEmail(BaseModel):
    email: str = Field(max_length=300)
    codice: str = Field(max_length=40)
    nuova: str = Field(max_length=500)
    endpoint_push: str | None = Field(default=None, max_length=600)


class CambioPassword(BaseModel):
    attuale: str = Field(max_length=500)
    nuova: str = Field(max_length=500)
    endpoint_push: str | None = Field(default=None, max_length=600)


class EsciDaTutti(BaseModel):
    """Corpo facoltativo di «Esci da tutti» (i client di prima non lo mandano). Con la password (per chi è solo Google: vuota, vale
    la riconferma recente) la risposta ha il nuovo codice di recupero."""
    password: str | None = Field(default=None, max_length=500)


class SoloPassword(BaseModel):
    password: str = Field(max_length=500)


COOKIE_DISPOSITIVO = "fanta_dispositivo"
INTESTAZIONE_DISPOSITIVO = "x-fanta-dispositivo"


def dispositivo_fidato(request: Request) -> str | None:
    """Il segreto del dispositivo fidato, se la richiesta lo porta: cookie per il web, intestazione `X-Fanta-Dispositivo` per le app."""
    valore = request.headers.get(INTESTAZIONE_DISPOSITIVO) or request.cookies.get(COOKIE_DISPOSITIVO)
    return valore if account.formato_dispositivo(valore) else None


def _dai_dispositivo(risposta: Response, request: Request, segreto: str, nativo: bool, corpo: dict) -> dict:
    """Dopo un accesso riuscito il dispositivo diventa «fidato» per 60 giorni: da lì il titolare entra anche se qualcuno sta
    provando password sul suo nome da altri indirizzi. Web: cookie HttpOnly valido solo per /api/account/. App native: campo
    `dispositivo` nella risposta (facoltativo: da rimandare nell'intestazione X-Fanta-Dispositivo), nessun cookie."""
    if nativo:
        corpo["dispositivo"] = segreto
    else:
        risposta.set_cookie(COOKIE_DISPOSITIVO, segreto, max_age=account.NOTO_PER, path="/api/account/", httponly=True,
                            samesite="strict", secure=e_https(request))
    return corpo


def _con_sessione(risposta: Response, request: Request, utente: Utente, token: str, nativo: bool, extra: dict | None = None) -> dict:
    corpo = {"multiutente": True, "utente": utente.come_dict()} | (extra or {})
    if nativo:
        corpo["token"] = token
    else:
        _metti_cookie(risposta, request, token)
    return corpo


@router.get("/api/account/me")
def me(request: Request, utente: Utente = Depends(utente_corrente)):
    """Chi sono. A interruttore spento: l'utente locale implicito (l'app non chiede nessun accesso)."""
    corpo = {"multiutente": account.multiutente(), "utente": utente.come_dict()}
    if account.multiutente():
        with closing(account.apri()) as db:
            corpo |= social.profilo_email(db, utente.id, account_email.email_di(db, utente.id))
            corpo["social"] = social.provider_attivi()
            corpo["email_attiva"] = posta.attiva()       # False: le rotte che mandano un codice per email rispondono 503 `posta_spenta`
            if social.google_attivo():
                corpo["accessi"] = social.accessi(db, utente.id)
    return corpo


@router.post("/api/account/registra", dependencies=[Depends(_attivo)])
def registra(dati: Iscrizione, request: Request, risposta: Response):
    """Crea l'account con un invito. Il codice di recupero compare solo qui: l'app deve farlo salvare."""
    modo = account_email.modo_registrazione()
    if not account_email.invito_classico(modo, dati.invito):
        with closing(account.apri()) as db, account.uno_alla_volta(ip_reale(request)):    # l'account nasce alla conferma del codice
            return account_email.iscrivi(db, dati.nome_utente, dati.password, dati.email, dati.invito, ip_reale(request),
                                         accetto_termini=dati.accetto_termini)
    email = account_email.normalizza_email(dati.email) if dati.email else None       # indirizzo sbagliato: errore PRIMA di creare l'account
    with closing(account.apri()) as db:
        utente, token, recupero = account.registra(db, dati.nome_utente, dati.password, dati.invito, ip_reale(request), _dispositivo(request),
                                                  accetto_termini=dati.accetto_termini)
        email_non_salvata = bool(email) and not posta.attiva()      # posta spenta: il codice non può arrivare, l'email non resta «in attesa»
        if email and not email_non_salvata:          # la verifica parte a parte: se non si riesce, l'account c'è lo stesso
            try:
                account_email.chiedi_verifica(db, utente.id, email, None, ip_reale(request), senza_password=True)
            except ErroreAccount:
                pass
        segreto = account.ricorda_dispositivo(db, utente.id, dispositivo_fidato(request))
    corpo = _con_sessione(risposta, request, utente, token, dati.nativo,
                          {"codice_recupero": recupero} | ({"email_non_salvata": True} if email_non_salvata else {}))
    return _dai_dispositivo(risposta, request, segreto, dati.nativo, corpo)


@router.post("/api/account/registra/conferma", dependencies=[Depends(_attivo)])
def conferma_iscrizione(dati: ConfermaIscrizione, request: Request, risposta: Response):
    """Seconda metà dell'iscrizione con email: il codice arrivato per posta crea l'account e apre la sessione."""
    with closing(account.apri()) as db:
        utente, token, recupero = account_email.conferma_iscrizione(db, dati.email, dati.codice, ip_reale(request), _dispositivo(request),
                                                                   segreto=dati.iscrizione)
    return _con_sessione(risposta, request, utente, token, dati.nativo, {"codice_recupero": recupero})


@router.post("/api/account/accedi", dependencies=[Depends(_attivo)])
def accedi(dati: Credenziali, request: Request, risposta: Response):
    with closing(account.apri()) as db:
        utente, token, segreto = account.accedi_ricordando(db, dati.nome_utente, dati.password, ip_reale(request),
                                                           _dispositivo(request), fidato=dispositivo_fidato(request))
        account.esci(db, token_della_richiesta(request))     # una sessione già presente su questo dispositivo si chiude: niente fissazione
    return _dai_dispositivo(risposta, request, segreto, dati.nativo, _con_sessione(risposta, request, utente, token, dati.nativo))


class NuovoNome(BaseModel):
    nome_utente: str = Field(max_length=100)


@router.put("/api/account/nome", dependencies=[Depends(_attivo)])
def cambia_nome(dati: NuovoNome, utente: Utente = Depends(utente_corrente)):
    """Cambia solo le maiuscole del proprio nome (le lettere restano le stesse: l'accesso non cambia)."""
    with closing(account.apri()) as db:
        nuovo = account.cambia_maiuscole(db, utente.id, dati.nome_utente)
    return {"utente": nuovo.come_dict()}


@router.post("/api/account/esci", dependencies=[Depends(_attivo)])
def esci(request: Request, risposta: Response):
    with closing(account.apri()) as db:
        account.esci(db, token_della_richiesta(request))
    _togli_cookie(risposta, request)
    return {"ok": True}


@router.post("/api/account/token-widget", dependencies=[Depends(_attivo)])
def crea_token_widget(utente: Utente = Depends(utente_corrente)):
    """Il token per il widget iOS: uno solo per utente (uno nuovo revoca il precedente), vale 90 giorni e serve solo a leggere (GET)
    /api/oggi, /api/widget e /api/live. Si vede una volta sola: sul server resta l'hash. (Con il token del widget questa rotta è già chiusa dal controllo d'accesso.)"""
    with closing(account.apri()) as db:
        account.limite.consuma(db, account._chiave("crea-token-widget", utente.id), 10, account.ORA)
        token, scade = account.crea_token_widget(db, utente.id)
    return {"token": token, "scade": scade, "etichetta": "widget"}


@router.get("/api/account/token-widget", dependencies=[Depends(_attivo)])
def stato_token_widget(utente: Utente = Depends(utente_corrente)):
    with closing(account.apri()) as db:
        return account.stato_token_widget(db, utente.id)


@router.delete("/api/account/token-widget", dependencies=[Depends(_attivo)])
def revoca_token_widget(utente: Utente = Depends(utente_corrente)):
    with closing(account.apri()) as db:
        account.limite.consuma(db, account._chiave("crea-token-widget", utente.id), 10, account.ORA)
        return {"revocato": account.revoca_token_widget(db, utente.id)}


@router.post("/api/account/esci-da-tutti", dependencies=[Depends(_attivo)])
def esci_da_tutti(request: Request, risposta: Response, dati: EsciDaTutti | None = None, utente: Utente = Depends(utente_corrente)):
    """Chiude tutto (anche questa sessione) e cambia il codice di recupero; il codice nuovo torna solo con la password."""
    with closing(account.apri()) as db:
        chiuse, codice = account.esci_da_tutti_i_dispositivi(db, utente.id, dati.password if dati else None, token_della_richiesta(request))
    _togli_cookie(risposta, request)
    return {"sessioni_chiuse": chiuse} | ({"codice_recupero": codice} if codice else {})


@router.post("/api/account/cambia-password", dependencies=[Depends(_attivo)])
def cambia_password(dati: CambioPassword, request: Request, risposta: Response, utente: Utente = Depends(utente_corrente)):
    """Tutte le sessioni si chiudono e questa riparte con un token nuovo (cookie per il web, nella risposta per le app native).
    La risposta ha anche il nuovo codice di recupero (il vecchio non vale più), da mostrare una volta sola."""
    with closing(account.apri()) as db:
        token, codice = account.cambia_password(db, utente.id, dati.attuale, dati.nuova, dispositivo=_dispositivo(request),
                                                tieni_push=dati.endpoint_push)
    nativo = request.headers.get("authorization", "")[:7].lower() == "bearer "
    return _con_sessione(risposta, request, utente, token, nativo, {"ok": True, "codice_recupero": codice})


@router.post("/api/account/codice-recupero", dependencies=[Depends(_attivo)])
def nuovo_codice_recupero(dati: SoloPassword, request: Request, utente: Utente = Depends(utente_corrente)):
    """Un nuovo codice di recupero al posto del vecchio (serve la password). Si mostra una volta sola."""
    with closing(account.apri()) as db:
        return {"codice_recupero": account.rigenera_codice_recupero(db, utente.id, dati.password, token_della_richiesta(request))}


@router.post("/api/account/elimina", dependencies=[Depends(_attivo)])
def elimina_account(dati: SoloPassword, request: Request, risposta: Response, utente: Utente = Depends(utente_corrente)):
    """Cancella l'account e TUTTI i suoi dati (rose, regole, scelte, immagini, avvisi). Serve la password; non si può annullare.
    Per portarti via i dati prima, usa il backup (Lega > Backup)."""
    with closing(account.apri()) as db:
        account.conferma_password(db, utente.id, dati.password, token_della_richiesta(request))
        account.elimina(db, utente.id)
    contesto.elimina_cartella(utente.id)
    _togli_cookie(risposta, request)
    return {"ok": True}


@router.post("/api/account/recupero", dependencies=[Depends(_attivo)])
def recupero(dati: Recupero, request: Request):
    """Nuova password con il codice di recupero (o con un codice di reset dell'amministratore). Le sessioni aperte si chiudono."""
    with closing(account.apri()) as db:
        nuovo = account.recupera(db, dati.nome_utente, dati.codice, dati.nuova, ip_reale(request), fidato=dispositivo_fidato(request),
                                 tieni_push=dati.endpoint_push)
    return {"ok": True, "codice_recupero": nuovo}


@router.post("/api/account/email", dependencies=[Depends(_attivo)])
def imposta_email(dati: NuovaEmail, request: Request, utente: Utente = Depends(utente_corrente)):
    """Aggiunge o cambia l'email: manda un codice a 6 cifre al nuovo indirizzo (serve la password). Stessa risposta in ogni caso."""
    _posta_accesa()
    with closing(account.apri()) as db:
        return account_email.chiedi_verifica(db, utente.id, dati.email, dati.password, ip_reale(request), sessione=token_della_richiesta(request))


@router.post("/api/account/email/conferma", dependencies=[Depends(_attivo)])
def conferma_email(dati: CodiceEmail, request: Request, utente: Utente = Depends(utente_corrente)):
    with closing(account.apri()) as db:
        return account_email.conferma_email(db, utente.id, dati.codice, ip_reale(request))


@router.post("/api/account/email/togli", dependencies=[Depends(_attivo)])
def togli_email(dati: SoloPassword, request: Request, utente: Utente = Depends(utente_corrente)):
    with closing(account.apri()) as db:
        return account_email.togli_email(db, utente.id, dati.password, token_della_richiesta(request))


@router.post("/api/account/recupero-email", dependencies=[Depends(_attivo)])
def recupero_email_richiesta(dati: RichiestaRecuperoEmail, request: Request):
    """Password dimenticata: manda un codice all'email dell'account. Risposta identica se l'indirizzo esiste o no."""
    _posta_accesa()
    with closing(account.apri()) as db:
        return account_email.chiedi_recupero(db, dati.email, ip_reale(request))


@router.post("/api/account/recupero-email/conferma", dependencies=[Depends(_attivo)])
def recupero_email_conferma(dati: RecuperoEmail, request: Request):
    with closing(account.apri()) as db:
        nuovo = account_email.recupera_con_email(db, dati.email, dati.codice, dati.nuova, ip_reale(request), tieni_push=dati.endpoint_push)
    return {"ok": True, "codice_recupero": nuovo}


# ---------------------------------------------------------------- amministratore
class NuovoInvito(BaseModel):
    etichetta: str = Field(max_length=100)
    amministratore: bool = False
    usi: int = Field(1, ge=1, le=account.MAX_USI_INVITO)       # quanti amici possono entrare con lo stesso codice (1 = come sempre)


class DaResettare(BaseModel):
    nome_utente: str = Field(max_length=100)


@router.post("/api/admin/inviti", dependencies=[Depends(_attivo), Depends(solo_amministratore)])
def crea_invito(dati: NuovoInvito):
    with closing(account.apri()) as db:
        codice = account.crea_invito(db, dati.etichetta, dati.amministratore, usi_max=dati.usi)
    return {"codice": codice, "etichetta": dati.etichetta.strip(), "valido_giorni": account.DURATA_INVITO.days, "usi_max": dati.usi}


@router.get("/api/admin/inviti", dependencies=[Depends(_attivo), Depends(solo_amministratore)])
def elenco_inviti():
    """Gli inviti con posti usati e stato (attivo, finito, scaduto, revocato). I codici non si rileggono."""
    with closing(account.apri()) as db:
        return {"inviti": account.elenco_inviti(db)}


@router.delete("/api/admin/inviti/{invito_id}", dependencies=[Depends(_attivo), Depends(solo_amministratore)])
def revoca_invito(invito_id: int):
    with closing(account.apri()) as db:
        account.revoca_invito(db, invito_id)
    return {"ok": True}


@router.get("/api/admin/utenti", dependencies=[Depends(_attivo), Depends(solo_amministratore)])
def elenco_utenti():
    with closing(account.apri()) as db:
        return {"utenti": account.elenco(db), "massimo": account.max_utenti()}


@router.get("/api/admin/registro", dependencies=[Depends(solo_amministratore)])
def registro_server():
    """Per l'amministratore: contatori dall'ultimo riavvio, ultimi errori del server e ultimi eventi di sicurezza (indirizzi nascosti a metà)."""
    return {"contatori": registro.contatori.riepilogo(), "errori": registro.ultimi(registro.FILE_ERRORI, 30),
            "sicurezza": registro.ultimi(registro.FILE_SICUREZZA, 30, nascondi_indirizzi=True)}


class SceltaFonte(BaseModel):
    fonte: str = Field(max_length=30)
    acceso: bool | None = None        # None = torna alla scelta di default (ambiente o predefinito)


@router.get("/api/admin/fonti", dependencies=[Depends(solo_amministratore)])
def fonti_dati():
    """Le fonti di dati esterne con l'interruttore di ognuna (acceso, da dove viene la scelta, messaggio se spenta)."""
    return {"fonti": fonti_attive.stato()}


@router.put("/api/admin/fonti", dependencies=[Depends(solo_amministratore)])
def scegli_fonte(dati: SceltaFonte, utente: Utente = Depends(solo_amministratore)):
    """Accende o spegne una fonte. Accendere una fonte significa assumersi il rispetto delle condizioni d'uso del sito.
    Le richieste già in corso finiscono; i risultati in diretta (ESPN) si riavviano al prossimo avvio del servizio."""
    if dati.fonte not in fonti_attive.FONTI:
        raise HTTPException(400, "Fonte sconosciuta")
    fonti_attive.imposta(dati.fonte, dati.acceso)
    valore = "standard" if dati.acceso is None else ("acceso" if dati.acceso else "spento")
    registro.scrivi(percorsi.cartella_account() / registro.FILE_SICUREZZA,
                    f"{registro.adesso()} fonte-cambiata utente={registro.pulito(utente.nome_utente)} "
                    f"fonte={registro.pulito(dati.fonte)} valore={valore}")
    return {"fonti": fonti_attive.stato()}


class SceltaFunzione(BaseModel):
    funzione: str = Field(max_length=30)
    acceso: bool | None = None        # None = torna alla scelta di default (ambiente o predefinito)


@router.get("/api/admin/funzioni", dependencies=[Depends(solo_amministratore)])
def funzioni_app():
    """Le funzioni dell'app con l'interruttore di ognuna (acceso, da dove viene la scelta)."""
    return {"funzioni": funzioni.stato()}


@router.put("/api/admin/funzioni", dependencies=[Depends(solo_amministratore)])
def scegli_funzione(dati: SceltaFunzione, utente: Utente = Depends(solo_amministratore)):
    """Accende o spegne una funzione per tutti (chi ha «Mostra tutte le funzioni» la vede comunque)."""
    if dati.funzione not in funzioni.FUNZIONI:
        raise HTTPException(400, "Funzione sconosciuta")
    funzioni.imposta(dati.funzione, dati.acceso)
    valore = "standard" if dati.acceso is None else ("acceso" if dati.acceso else "spento")
    registro.scrivi(percorsi.cartella_account() / registro.FILE_SICUREZZA,
                    f"{registro.adesso()} funzione-cambiata utente={registro.pulito(utente.nome_utente)} "
                    f"funzione={registro.pulito(dati.funzione)} valore={valore}")
    return {"funzioni": funzioni.stato()}


@router.post("/api/admin/reset-password", dependencies=[Depends(_attivo), Depends(solo_amministratore)])
def reset_password(dati: DaResettare):
    with closing(account.apri()) as db:
        codice = account.crea_reset(db, dati.nome_utente)
    return {"codice": codice, "valido_ore": int(account.DURATA_RESET.total_seconds() // 3600)}


# ---------------------------------------------------------------- accesso con Google
def _google() -> None:
    """Senza FANTA_GOOGLE_CLIENT_ID e FANTA_GOOGLE_CLIENT_SECRET è come se queste rotte non ci fossero."""
    if not account.multiutente() or not social.google_attivo():
        raise HTTPException(404, "Non trovato")


class AvvioSocial(BaseModel):
    scopo: str = Field(default="accedi", max_length=20)
    sfida: str = Field(max_length=100)
    piattaforma: str = Field(default="web", max_length=10)
    password: str = Field(default="", max_length=500)      # per «collega»: la password dell'account (o, senza password, la riconferma con Google)


class ScambioSocial(BaseModel):
    codice: str = Field(max_length=200)
    verificatore: str = Field(max_length=200)
    nativo: bool = False


class CompletaSocial(BaseModel):
    iscrizione: str = Field(max_length=200)
    nome_utente: str = Field(max_length=100)
    invito: str = Field(default="", max_length=100)
    accetto_termini: bool = False
    nativo: bool = False


@router.post("/api/account/social/google/inizia", dependencies=[Depends(_google)])
def social_inizia(dati: AvvioSocial, request: Request):
    """Dà l'indirizzo di Google da aprire. Per «collega» e «riconferma» serve la sessione."""
    utente = identifica(request) if dati.scopo in ("collega", "riconferma") else None
    with closing(account.apri()) as db:
        return social.inizia(db, "google", dati.scopo, dati.sfida, dati.piattaforma, utente.id if utente else None, ip_reale(request),
                             social.indirizzo_ritorno(), sessione=token_della_richiesta(request) if utente else None, password=dati.password)


@router.get("/api/account/social/google/ritorno", dependencies=[Depends(_google)])
def social_ritorno(request: Request, code: str | None = None, state: str | None = None, error: str | None = None):
    """Dove torna Google. Non usa mai il cookie. Risponde con un redirect che porta solo un codice monouso (o il motivo dell'errore)."""
    with closing(account.apri()) as db:
        try:
            piattaforma, esito = social.ritorno(db, code, state, error, ip_reale(request), social.indirizzo_ritorno())
            errore = esito in ("annullato", "scaduto", "non_valido")
        except ErroreAccount as e:
            if e.stato == 404:
                raise
            piattaforma, esito, errore = "web", "non_valido", True
    chiave = "social_errore" if errore else "social"
    dove = f"schieraxi://social?{'errore' if errore else 'codice'}={esito}" if piattaforma == "ios" else f"/?{chiave}={esito}"
    return Response(status_code=302, headers={"Location": dove, "Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})


@router.post("/api/account/social/scambio", dependencies=[Depends(_google)])
def social_scambio(dati: ScambioSocial, request: Request, risposta: Response):
    with closing(account.apri()) as db:
        esito = social.scambio(db, dati.codice, dati.verificatore, identifica(request), ip_reale(request), _dispositivo(request),
                               sessione=token_della_richiesta(request))
        if esito["stato"] == "ok":
            account.esci(db, token_della_richiesta(request))        # una sessione già presente su questo dispositivo si chiude
            return _con_sessione(risposta, request, esito["utente"], esito["token"], dati.nativo, {"stato": "ok"})
    return esito


@router.post("/api/account/social/completa", dependencies=[Depends(_google)])
def social_completa(dati: CompletaSocial, request: Request, risposta: Response):
    with closing(account.apri()) as db:
        utente, token = social.completa(db, dati.iscrizione, dati.nome_utente, dati.invito, dati.accetto_termini, ip_reale(request),
                                        _dispositivo(request))
    return _con_sessione(risposta, request, utente, token, dati.nativo, {"stato": "ok"})


@router.get("/api/account/social/accessi", dependencies=[Depends(_google)])
def social_accessi(utente: Utente = Depends(utente_corrente)):
    with closing(account.apri()) as db:
        return social.accessi(db, utente.id)


@router.delete("/api/account/social/{provider}", dependencies=[Depends(_google)])
def social_scollega(provider: str, utente: Utente = Depends(utente_corrente)):
    with closing(account.apri()) as db:
        return social.scollega(db, utente.id, provider)


class NuovaPassword(BaseModel):
    password: str = Field(max_length=500)


@router.post("/api/account/imposta-password", dependencies=[Depends(_attivo)])
def imposta_password(dati: NuovaPassword, request: Request, utente: Utente = Depends(utente_corrente)):
    """Per chi è entrato solo con Google: aggiunge una password (dopo aver riconfermato con Google)."""
    with closing(account.apri()) as db:
        return {"ok": True, "codice_recupero": social.imposta_password(db, utente.id, dati.password, token_della_richiesta(request))}
