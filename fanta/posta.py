"""Invio delle email (verifica, recupero, avviso di accesso nuovo), dietro un'interfaccia sola: `invia(messaggio)`.

Il modo si sceglie con la variabile d'ambiente FANTA_MAIL (si legge a ogni invio):
- `spento` (predefinito, anche per un valore sconosciuto): NON parte nessuna email e non si scrive niente.
- `log`: NON parte nessuna email. In `posta.log` (cartella dati, con rotazione, righe tenute 30 giorni) resta solo che un
  messaggio sarebbe partito: quando, a chi (indirizzo accorciato) e il tipo. MAI il testo né i codici: il file non serve a
  entrare negli account di nessuno. Serve a provare l'app senza servizio esterno.
- `smtp`: server SMTP con TLS (porta 465 = TLS subito, altre = STARTTLS; mai senza cifratura, certificato sempre controllato).
  Variabili: FANTA_SMTP_HOST, FANTA_SMTP_PORT (587), FANTA_SMTP_UTENTE. La password, in ordine: il file indicato da
  FANTA_SMTP_PASSWORD_FILE (consigliato: una riga, permessi 600, altrimenti non si usa), FANTA_SMTP_PASSWORD, il file
  `dati/smtp-password.txt`. Con un utente e senza password non si prova nemmeno ad accedere.
- `resend`: API HTTPS di Resend (resend.com). La chiave in FANTA_RESEND_KEY oppure nel file `dati/chiave-resend.txt`.
Mittente: FANTA_MAIL_DA (per esempio `SchieraXI <noreply@tuodominio.it>`); senza, l'invio vero non parte.
Tetto: al massimo FANTA_MAIL_MAX_ORA invii veri (smtp e resend) nell'ultima ora (predefinito MAX_ALL_ORA, contati per processo
del server), così un'ondata di richieste non fa bloccare la casella dal fornitore. Oltre il tetto il messaggio non parte e nel
registro di sicurezza resta `posta_tetto_ora`.
Chiavi e password solo da ambiente o da file in `dati/` (mai in git, mai nei log). Un errore di invio non si propaga: l'app va
avanti, nel registro di sicurezza resta il solo tipo di errore. L'invio avviene in un thread a parte, così il tempo di risposta
di chi chiede non dice se l'indirizzo esiste (vedi `account.py`).
"""
from __future__ import annotations

import os
import re
import smtplib
import ssl
import threading
import time
from collections import deque
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formatdate, make_msgid, parseaddr
from pathlib import Path

from . import percorsi, registro

MODI = ("spento", "log", "smtp", "resend")
PREDEFINITO = "spento"
FILE_LOG = "posta.log"
MAX_LOG = 256 * 1024
TIMEOUT = 15
IN_BACKGROUND = True            # i test lo spengono per aspettare l'esito
MAX_ALL_ORA = 50                # invii veri all'ora (FANTA_MAIL_MAX_ORA): molto sotto i limiti delle caselle dei fornitori
MAX_FILE_PASSWORD = 4096        # byte: un file più grande non è una password
_orologio = time.monotonic
_PERMESSI_UNIX = os.name == "posix"     # su Windows i permessi 600 non esistono
_invii: deque[float] = deque()  # quando sono partiti gli invii veri dell'ultima ora
_invii_lock = threading.Lock()
_EMAIL = re.compile(r"[^@\s<>\"',;()\\]{1,64}@[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)+")


@dataclass(frozen=True)
class Messaggio:
    a: str
    oggetto: str
    testo: str


def modo() -> str:
    m = os.environ.get("FANTA_MAIL", PREDEFINITO).strip().lower()
    return m if m in MODI else PREDEFINITO


def attiva() -> bool:
    """False con FANTA_MAIL=spento: nessun codice può arrivare, e le rotte dell'email lo dicono subito (`posta_spenta`) invece di
    far aspettare un messaggio che non parte. `log` conta come attiva: serve a provare i giri dell'email senza spedire."""
    return modo() != "spento"


def segreto(variabile: str, file: str) -> str:
    """Una chiave: prima dall'ambiente, poi da un file in dati/ (una riga). Vuota se non c'è."""
    v = os.environ.get(variabile, "").strip()
    if v:
        return v
    try:
        return (percorsi.cartella_account() / file).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


class PasswordNonSicura(Exception):
    """Il file della password è leggibile da altri utenti del server (permessi diversi da 600) o non è una password."""


def password_da_file(percorso: str) -> str:
    """La prima riga del file (senza il ritorno a capo finale). Rifiuta file leggibili da altri o troppo grandi.
    Un percorso relativo parte dalla cartella dell'app."""
    p = Path(percorso).expanduser()
    if not p.is_absolute():
        p = percorsi.RADICE / p
    st = p.stat()
    if _PERMESSI_UNIX and st.st_mode & 0o077:
        raise PasswordNonSicura("permessi")
    if st.st_size > MAX_FILE_PASSWORD:
        raise PasswordNonSicura("dimensione")
    righe = p.read_text(encoding="utf-8").splitlines()
    return righe[0] if righe else ""


def password_smtp() -> str:
    file = os.environ.get("FANTA_SMTP_PASSWORD_FILE", "").strip()
    return password_da_file(file) if file else segreto("FANTA_SMTP_PASSWORD", "smtp-password.txt")


def tetto_ora() -> int:
    try:
        return max(0, int(os.environ.get("FANTA_MAIL_MAX_ORA", "").strip() or MAX_ALL_ORA))
    except ValueError:
        return MAX_ALL_ORA


def _prenota_invio() -> bool:
    """Conta un invio vero se nell'ultima ora non si è già arrivati al tetto."""
    adesso = _orologio()
    with _invii_lock:
        while _invii and adesso - _invii[0] >= 3600:
            _invii.popleft()
        if len(_invii) >= tetto_ora():
            return False
        _invii.append(adesso)
        return True


def mittente() -> str:
    return os.environ.get("FANTA_MAIL_DA", "").strip()


def indirizzo_valido(testo: str) -> bool:
    return isinstance(testo, str) and len(testo) <= 254 and bool(_EMAIL.fullmatch(testo))


def _evento(tipo: str, **campi) -> None:
    from . import account
    account.evento(tipo, **campi)


# ---------------------------------------------------------------- modelli di email
def _firma() -> str:
    return "\n\nSchieraXI\nSe non sei stato tu, ignora questo messaggio: non succede niente."


def modello_verifica(a: str, codice: str, minuti: int, nome_utente: str | None = None) -> Messaggio:
    """Con `nome_utente` (iscrizione) il messaggio dice per quale account è il codice: chi lo riceve riconosce una richiesta non sua."""
    cosa = (f"per creare l'account «{nome_utente}» in SchieraXI con questo indirizzo email scrivi il codice" if nome_utente
            else "per confermare questo indirizzo email in SchieraXI scrivi il codice")
    return Messaggio(a, "SchieraXI: conferma la tua email",
                     f"Ciao,\n{cosa}:\n\n    {codice}\n\n"
                     f"Vale {minuti} minuti e si può usare una volta sola. Non darlo a nessuno." + _firma())


def modello_recupero(a: str, codice: str, minuti: int) -> Messaggio:
    return Messaggio(a, "SchieraXI: recupero della password",
                     f"Ciao,\nhai chiesto di scegliere una nuova password. Il codice è:\n\n    {codice}\n\n"
                     f"Vale {minuti} minuti e si può usare una volta sola. Non darlo a nessuno." + _firma())


def modello_accesso_nuovo(a: str, dispositivo: str, quando: str) -> Messaggio:
    d = re.sub(r"[^\w .,;:/()+-]", "", dispositivo or "")[:80] or "un dispositivo sconosciuto"
    return Messaggio(a, "SchieraXI: accesso da un dispositivo nuovo",
                     f"Ciao,\nil tuo account è stato aperto da un dispositivo nuovo.\n\n    Quando: {quando}\n    Dispositivo: {d}\n\n"
                     "Se sei stato tu, va bene così. Se non riconosci questo accesso, cambia subito la password da Lega > Account "
                     "e usa «Esci da tutti i dispositivi».")


def modello_google_collegato(a: str, quando: str) -> Messaggio:
    return Messaggio(a, "SchieraXI: Google collegato al tuo account",
                     f"Ciao,\nè stato collegato un account Google al tuo account SchieraXI.\n\n    Quando: {quando}\n\n"
                     "Se sei stato tu, va bene così. Se non riconosci questa operazione, cambia subito la password e usa "
                     "«Esci da tutti i dispositivi»: così Google viene scollegato.")


# ---------------------------------------------------------------- invio
def _indirizzo_accorciato(a: str) -> str:
    """`marco.rossi@example.com` -> `m...@example.com`: si capisce a quale dominio, non a chi."""
    locale, _, dominio = a.partition("@")
    return f"{locale[:1]}...@{dominio}"


def _scrivi_log(m: Messaggio) -> bool:
    """Solo che il messaggio sarebbe partito (quando, a chi in forma accorciata, l'oggetto): mai il testo, quindi mai i codici."""
    riga = f"{registro.adesso()} non_inviata a={registro.pulito(_indirizzo_accorciato(m.a))} oggetto={m.oggetto!r}"
    registro.scrivi(percorsi.cartella_account() / FILE_LOG, riga, MAX_LOG)
    return True


def _spento(m: Messaggio) -> bool:
    return False


def _costruisci(m: Messaggio, da: str) -> EmailMessage:
    e = EmailMessage()
    e["From"], e["To"], e["Subject"] = da, m.a, m.oggetto          # con a capo nei campi EmailMessage alza ValueError
    e["Date"] = formatdate(localtime=True)
    dominio = (parseaddr(da)[1] or da).rpartition("@")[2]
    e["Message-ID"] = make_msgid(domain=dominio or None)           # col dominio del mittente: non rivela il nome del server
    e.set_content(m.testo)
    return e


def _invia_smtp(m: Messaggio) -> bool:
    host, da = os.environ.get("FANTA_SMTP_HOST", "").strip(), mittente()
    if not host or not da:
        return False
    try:
        porta = int(os.environ.get("FANTA_SMTP_PORT", "587"))
    except ValueError:
        return False
    utente, password = os.environ.get("FANTA_SMTP_UTENTE", "").strip(), password_smtp()
    if utente and not password:
        return False
    contesto = ssl.create_default_context()
    e = _costruisci(m, da)
    if porta == 465:
        s = smtplib.SMTP_SSL(host, porta, timeout=TIMEOUT, context=contesto)
    else:
        s = smtplib.SMTP(host, porta, timeout=TIMEOUT)
    with s:
        if porta != 465:
            s.starttls(context=contesto)             # se il server non lo offre, alza un errore: mai in chiaro
        if utente:
            s.login(utente, password)
        s.send_message(e)
    return True


def _invia_resend(m: Messaggio) -> bool:
    import requests
    chiave, da = segreto("FANTA_RESEND_KEY", "chiave-resend.txt"), mittente()
    if not chiave or not da:
        return False
    _costruisci(m, parseaddr(da)[1] or da)           # stessi controlli sui campi (a capo ecc.)
    r = requests.post("https://api.resend.com/emails", timeout=TIMEOUT, headers={"Authorization": f"Bearer {chiave}"},
                      json={"from": da, "to": [m.a], "subject": m.oggetto, "text": m.testo})
    return r.status_code // 100 == 2


def _invia_ora(m: Messaggio) -> bool:
    """Invia nel modo scelto. Non alza mai: restituisce se è andata."""
    try:
        if not indirizzo_valido(m.a) or "\n" in m.oggetto or "\r" in m.oggetto:
            return False
        scelto = modo()
        if scelto in ("smtp", "resend") and not _prenota_invio():
            _evento("posta_tetto_ora", modo=scelto)
            return False
        ok = {"spento": _spento, "log": _scrivi_log, "smtp": _invia_smtp, "resend": _invia_resend}[scelto](m)
        if not ok and scelto != "spento":
            _evento("posta_non_inviata", modo=scelto)
        return ok
    except Exception as e:           # noqa: BLE001 - la posta non deve mai rompere una richiesta
        _evento("posta_errore", modo=modo(), errore=type(e).__name__)
        return False


def invia(m: Messaggio) -> bool:
    """Manda il messaggio. In background (risposta immediata, True = preso in carico) salvo IN_BACKGROUND spento (test)."""
    if not IN_BACKGROUND:
        return _invia_ora(m)
    threading.Thread(target=_invia_ora, args=(m,), daemon=True).start()
    return True


def modello_gia_registrato(a: str) -> Messaggio:
    return Messaggio(a, "SchieraXI: questo indirizzo ha già un account",
                     "Ciao,\nqualcuno (forse tu) ha usato questo indirizzo email in SchieraXI, ma ha già un account.\n\n"
                     "Se sei tu e non ricordi la password, nella schermata di accesso scegli «Password dimenticata» e "
                     "scrivi questo indirizzo." + _firma())


def modello_email_cambiata(a: str) -> Messaggio:
    return Messaggio(a, "SchieraXI: l'email del tuo account è cambiata",
                     "Ciao,\nl'indirizzo email del tuo account SchieraXI è stato sostituito con un altro: da ora i messaggi "
                     "non arriveranno più qui.\n\nSe non sei stato tu, cambia subito la password e usa «Esci da tutti i "
                     "dispositivi» (Lega > Account).")
