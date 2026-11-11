"""Prove da «attaccante» sul percorso di accesso (server). Ogni test dice quale attacco prova e cosa deve succedere.
Tutto su cartelle temporanee e dati finti (fixture `multiutente` e `dati_isolati`): nessun file vero viene toccato."""
import base64
import contextlib
import hashlib
import re
import sqlite3
import threading
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from fanta import account, percorsi, rotte_account, server
from fanta.account import ErroreAccount

from test_account_http import PASSWORD, cliente

ADESSO = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def db(multiutente):
    with contextlib.closing(account.apri()) as d:
        yield d


@pytest.fixture
def web(multiutente, dati_isolati):
    return cliente()


def nuovo(db, nome="marco", password=PASSWORD, admin=False, ip=None):
    inv = account.crea_invito(db, "prova", admin, ADESSO)
    return account.registra(db, nome, password, inv, ip=ip, adesso=ADESSO)


def errore(funzione, *args, **kw) -> ErroreAccount:
    with pytest.raises(ErroreAccount) as e:
        funzione(*args, **kw)
    return e.value


def da(ip: str, **extra) -> TestClient:
    """Un dispositivo che arriva da questo indirizzo (FANTA_PROXY=1 nei test: lo dice il proxy con X-Forwarded-For)."""
    return cliente(**{"X-Forwarded-For": ip} | extra)


def invito_http(amministratore=False) -> str:
    with contextlib.closing(account.apri()) as d:
        return account.crea_invito(d, "prova", amministratore)


# ================================================================ (a) enumerazione degli utenti
def test_enumerazione_stessa_risposta_per_nome_inesistente_password_sbagliata_e_blocco(web):
    """Attacco: capire quali nomi esistono guardando codice, messaggio o intestazioni. Deve essere tutto identico."""
    da("1.1.1.1").post("/api/account/registra", json={"nome_utente": "marco", "password": PASSWORD, "invito": invito_http()})
    a, b = da("2.2.2.2"), da("3.3.3.3")
    esiste = a.post("/api/account/accedi", json={"nome_utente": "marco", "password": "sbagliata-sbagliata"})
    non_esiste = b.post("/api/account/accedi", json={"nome_utente": "nessuno", "password": "sbagliata-sbagliata"})
    assert (esiste.status_code, esiste.json()) == (non_esiste.status_code, non_esiste.json()) == (401, {"detail": account.ACCESSO_SBAGLIATO})
    assert sorted(k for k in esiste.headers if k != "content-length") == sorted(k for k in non_esiste.headers if k != "content-length")
    for _ in range(5):                                         # anche il blocco arriva identico per chi c'è e per chi non c'è
        a.post("/api/account/accedi", json={"nome_utente": "marco", "password": "sbagliata-sbagliata"})
        b.post("/api/account/accedi", json={"nome_utente": "nessuno", "password": "sbagliata-sbagliata"})
    x = a.post("/api/account/accedi", json={"nome_utente": "marco", "password": "sbagliata-sbagliata"})
    y = b.post("/api/account/accedi", json={"nome_utente": "nessuno", "password": "sbagliata-sbagliata"})
    assert x.status_code == y.status_code == 429 and x.json() == y.json()


def lavoro(monkeypatch):
    """Quanto scrypt si fa (somma di n*r*p): misura il «tempo» senza cronometro, quindi senza test ballerini."""
    fatto = []
    vero = account.hashlib.scrypt
    monkeypatch.setattr(account.hashlib, "scrypt", lambda d, salt, n, r, p, maxmem, dklen: fatto.append(n * r * p) or vero(
        d, salt=salt, n=n, r=r, p=p, maxmem=maxmem, dklen=dklen))
    return fatto


def test_enumerazione_dal_tempo_stesso_lavoro(db, monkeypatch):
    """Attacco: misurare il tempo di risposta. Nome inesistente e password sbagliata devono costare lo stesso scrypt."""
    nuovo(db)
    account._hash_fittizio()                                    # il fittizio si prepara una volta sola (all'avvio)
    fatto = lavoro(monkeypatch)
    errore(account.accedi, db, "marco", "sbagliata-sbagliata", adesso=ADESSO)
    esistente = sum(fatto)
    fatto.clear()
    errore(account.accedi, db, "nessuno", "sbagliata-sbagliata", adesso=ADESSO)
    assert sum(fatto) == esistente > 0


def test_enumerazione_dal_tempo_anche_con_un_hash_di_parametri_vecchi(db, monkeypatch):
    """Il vero account di oggi ha l'hash con il costo vecchio (2^15): il lavoro a vuoto lo pareggia con il fittizio (2^16)."""
    monkeypatch.setattr(account, "COSTO", {"n": 2 ** 4, "r": 8, "p": 1})
    nuovo(db)                                                   # salvato «leggero»
    monkeypatch.setattr(account, "COSTO", {"n": 2 ** 5, "r": 8, "p": 1})    # poi il costo raddoppia
    account._hash_fittizio()
    fatto = lavoro(monkeypatch)
    errore(account.accedi, db, "marco", "sbagliata-sbagliata", adesso=ADESSO)
    vecchio = sum(fatto)
    fatto.clear()
    errore(account.accedi, db, "nessuno", "sbagliata-sbagliata", adesso=ADESSO)
    assert vecchio == sum(fatto)


def test_registrazione_nome_preso_solo_con_invito_valido_e_stesso_lavoro(db, monkeypatch):
    """Il «nome già preso» si dice (serve a chi si iscrive), ma solo a chi ha un invito valido; invito sbagliato, scaduto o
    usato danno lo stesso messaggio. In tutti i casi lo scrypt della password si fa (stesso tempo)."""
    nuovo(db, "marco")
    fatto = lavoro(monkeypatch)
    e1 = errore(account.registra, db, "marco", PASSWORD, "AAAAA-BBBBB-CCCCC-DDDDD", adesso=ADESSO)
    sbagliato = sum(fatto)
    fatto.clear()
    inv = account.crea_invito(db, "x", adesso=ADESSO)
    e2 = errore(account.registra, db, "marco", PASSWORD, inv, adesso=ADESSO)
    assert (e1.stato, e1.messaggio) == (403, account.INVITO_NON_VALIDO) and "già preso" in e2.messaggio
    assert sum(fatto) == sbagliato > 0
    scaduto = account.crea_invito(db, "x", adesso=ADESSO - timedelta(days=8))
    assert errore(account.registra, db, "luca", PASSWORD, scaduto, adesso=ADESSO).messaggio == account.INVITO_NON_VALIDO


def test_con_un_invito_valido_non_si_provano_i_nomi_in_massa(db):
    inv = account.crea_invito(db, "x", adesso=ADESSO)
    for i in range(30):
        nuovo(db, f"utente{i:02d}") if i < 3 else None
    for i in range(account.PROVE_PER_INVITO[0]):
        errore(account.registra, db, f"utente{i % 3:02d}", PASSWORD, inv, adesso=ADESSO)
    assert errore(account.registra, db, "libero123", PASSWORD, inv, adesso=ADESSO).stato == 429


def test_recupero_stessa_risposta_per_nome_inesistente_e_codice_sbagliato(db):
    nuovo(db)
    a = errore(account.recupera, db, "marco", "AAAAA-AAAAA-AAAAA-AAAAA", "nuova-password-lunga")
    b = errore(account.recupera, db, "nessuno", "AAAAA-AAAAA-AAAAA-AAAAA", "nuova-password-lunga")
    assert (a.stato, a.messaggio) == (b.stato, b.messaggio) == (403, "Nome utente o codice non validi")


# ================================================================ (b) forza bruta
def test_forza_bruta_un_attaccante_blocca_se_stesso_non_il_vero_utente(db, multiutente):
    """Attacco: da un indirizzo si provano password per «marco». Si blocca la coppia nome+indirizzo dell'attaccante; il vero
    utente da casa sua (altro indirizzo) entra lo stesso."""
    nuovo(db)
    for _ in range(5):
        errore(account.accedi, db, "marco", "sbagliata-sbagliata", ip="6.6.6.6", adesso=ADESSO)
    assert errore(account.accedi, db, "marco", PASSWORD, ip="6.6.6.6", adesso=ADESSO).stato == 429
    account.accedi(db, "marco", PASSWORD, ip="10.0.0.1", adesso=ADESSO)


def test_forza_bruta_da_tanti_indirizzi_passa_solo_l_indirizzo_noto(db, multiutente, monkeypatch):
    """Attacco distribuito (tanti indirizzi, pochi tentativi ciascuno): oltre il tetto per nome entrano solo gli indirizzi da
    cui il vero utente era già entrato. Un indirizzo nuovo aspetta che la finestra passi (un'ora), mai per sempre."""
    monkeypatch.setattr(account, "FALLIMENTI_PER_NOME", (10, 3600))
    nuovo(db)
    account.accedi(db, "marco", PASSWORD, ip="10.0.0.1", adesso=ADESSO)            # casa: indirizzo noto
    for i in range(10):
        errore(account.accedi, db, "marco", "sbagliata-sbagliata", ip=f"6.6.{i}.1", adesso=ADESSO)
    assert errore(account.accedi, db, "marco", PASSWORD, ip="7.7.7.7", adesso=ADESSO).stato == 429     # indirizzo nuovo
    account.accedi(db, "marco", PASSWORD, ip="10.0.0.1", adesso=ADESSO)            # da casa sì
    multiutente.t += 3601
    account.accedi(db, "marco", PASSWORD, ip="7.7.7.7", adesso=ADESSO)             # e passata l'ora anche dal nuovo


def test_mai_un_blocco_per_sempre_anche_se_l_attaccante_insiste(db, multiutente):
    """Attacco: tenere bloccato un utente riprovando di continuo. L'attesa ha un tetto di 15 minuti dall'ultimo errore, e
    l'attaccante da un altro indirizzo non tocca la coppia del vero utente."""
    nuovo(db)
    for _ in range(40):                     # l'attaccante riprova appena può, per ore
        try:
            account.accedi(db, "marco", "sbagliata-sbagliata", ip="6.6.6.6", adesso=ADESSO)
        except ErroreAccount as e:
            assert e.riprova_tra is None or e.riprova_tra <= 900
            multiutente.t += (e.riprova_tra or 0) + 1
    account.accedi(db, "marco", PASSWORD, ip="10.0.0.1", adesso=ADESSO)


def test_i_contatori_sopravvivono_al_riavvio(multiutente):
    """Attacco: far ripartire il servizio (o aspettare un aggiornamento) per azzerare i limiti. Sono nel database: restano."""
    with contextlib.closing(account.apri()) as d:
        nuovo(d)
        for _ in range(5):
            errore(account.accedi, d, "marco", "sbagliata-sbagliata", adesso=ADESSO)
    with contextlib.closing(account.apri()) as d:                      # «riavvio»: connessione nuova, nessuna memoria
        assert errore(account.accedi, d, "marco", PASSWORD, adesso=ADESSO).stato == 429
        chiavi = " ".join(r[0] for r in d.execute("SELECT chiave FROM tentativi"))
        assert "marco" not in chiavi                                   # nel file solo hash, niente nomi né indirizzi


def test_codici_di_invito_e_recupero_spazio_di_ricerca():
    """20 caratteri da 32 simboli = 100 bit: indovinarli a tentativi è impossibile (e i tentativi sono limitati)."""
    assert len(account.ALFABETO) == 32 and len(set(account.ALFABETO)) == 32
    codici = {account.nuovo_codice(20) for _ in range(200)}
    assert len(codici) == 200 and all(len(c.replace("-", "")) == 20 for c in codici)


def test_forza_bruta_sugli_inviti_da_un_indirizzo(db):
    for _ in range(account.INVITI_SBAGLIATI_PER_IP[0]):
        assert errore(account.registra, db, "luca", PASSWORD, account.nuovo_codice(20), ip="6.6.6.6", adesso=ADESSO).stato == 403
    assert errore(account.registra, db, "luca", PASSWORD, account.nuovo_codice(20), ip="6.6.6.6", adesso=ADESSO).stato == 429


def test_forza_bruta_sugli_inviti_globale(db, monkeypatch):
    monkeypatch.setattr(account, "INVITI_SBAGLIATI_GLOBALI", (6, 3600))
    for i in range(6):
        errore(account.registra, db, "luca", PASSWORD, account.nuovo_codice(20), ip=f"6.6.6.{i}", adesso=ADESSO)
    assert errore(account.registra, db, "luca", PASSWORD, account.nuovo_codice(20), ip="7.7.7.7", adesso=ADESSO).stato == 429


def test_forza_bruta_sul_recupero_e_sul_reset(db):
    nuovo(db)
    for _ in range(5):
        errore(account.recupera, db, "marco", account.nuovo_codice(20), "nuova-password-lunga", ip="6.6.6.6")
    assert errore(account.recupera, db, "marco", account.nuovo_codice(20), "nuova-password-lunga", ip="6.6.6.6").stato == 429
    for _ in range(30):
        account.crea_reset(db, "marco", ADESSO)
    assert errore(account.crea_reset, db, "marco", ADESSO).stato == 429         # anche l'amministratore ha un tetto


def test_forza_bruta_sulla_password_attuale(db):
    utente, token, _ = nuovo(db)
    for _ in range(10):
        errore(account.conferma_password, db, utente.id, "sbagliata-sbagliata")
    assert errore(account.cambia_password, db, utente.id, PASSWORD, "nuova-password-lunga").stato == 429


# ================================================================ (c) X-Forwarded-For inventato
class _Finta:
    def __init__(self, host, *xff):
        self.client = type("C", (), {"host": host})() if host else None
        self.headers = _Intestazioni([("x-forwarded-for", v) for v in xff])


class _Intestazioni:
    def __init__(self, coppie):
        self.coppie = coppie

    def get(self, k, d=None):
        return next((v for c, v in self.coppie if c == k), d)

    def getlist(self, k):
        return [v for c, v in self.coppie if c == k]


def test_xff_vale_solo_l_ultimo_valore_e_solo_se_e_un_indirizzo(monkeypatch):
    """Attacco: scrivere la propria X-Forwarded-For per cambiare indirizzo a ogni tentativo. Il proxy aggiunge il vero in fondo."""
    monkeypatch.setenv("FANTA_PROXY", "1")
    assert rotte_account.ip_reale(_Finta("127.0.0.1", "1.2.3.4, 9.9.9.9")) == "9.9.9.9"
    assert rotte_account.ip_reale(_Finta("127.0.0.1", "1.2.3.4", "9.9.9.9")) == "9.9.9.9"          # due intestazioni
    assert rotte_account.ip_reale(_Finta("127.0.0.1", "1.2.3.4, ciao")) is None                     # spazzatura: non è una chiave
    assert rotte_account.ip_reale(_Finta("203.0.113.9", "1.2.3.4, ciao")) == "203.0.113.9"          # si torna al vero mittente
    assert rotte_account.ip_reale(_Finta("127.0.0.1", "[2001:db8::1]:443")) == "2001:db8::/64"   # IPv6: conta il prefisso /64
    assert rotte_account.ip_reale(_Finta("127.0.0.1", "9.9.9.9:5555")) == "9.9.9.9"
    assert rotte_account.ip_reale(_Finta("127.0.0.1", "x" * 10000)) is None


def test_xff_inventato_non_aggira_il_limite_per_indirizzo(web):
    for i in range(5):
        r = da(f"10.0.0.{i}, 9.9.9.9").post("/api/account/registra", json={"nome_utente": "xyz", "password": PASSWORD, "invito": "no"})
        assert r.status_code == 403
    assert da("1.1.1.1, 9.9.9.9").post("/api/account/registra", json={"nome_utente": "xyz", "password": PASSWORD, "invito": "no"}).status_code == 429


# ================================================================ (d) password e nomi
def test_password_normalizzata_nfkc(db):
    """La «é» composta (iPhone) e scomposta (Mac) sono la stessa password; lo stesso per le lettere a larghezza piena."""
    composta = "caffè-della-mattina"
    nuovo(db, password=composta)
    account.accedi(db, "marco", unicodedata.normalize("NFD", composta), adesso=ADESSO)
    larga = "ｐａｓｓｅｇｇｉａｔａ-lunga"
    nuovo(db, "luca", password=larga)
    account.accedi(db, "luca", unicodedata.normalize("NFKC", larga), adesso=ADESSO)


def test_password_del_formato_vecchio_funziona_e_si_ricalcola(db):
    """Retrocompatibilità: una password salvata senza normalizzazione e con i parametri vecchi entra, e al primo accesso
    riuscito si salva di nuovo con quelli di adesso. Nessuna password già salvata smette di valere."""
    utente, _, _ = nuovo(db)
    vecchia = unicodedata.normalize("NFD", "caffè-amaro-forte")           # scritta così da un Mac, prima della normalizzazione
    sale = b"s" * 16
    h = hashlib.scrypt(vecchia.encode(), salt=sale, n=2 ** 3, r=8, p=1, maxmem=account._memoria(2 ** 3, 8, 1), dklen=32)
    db.execute("UPDATE utenti SET password_hash = ? WHERE id = ?",
               (f"scrypt${2 ** 3}$8$1${base64.b64encode(sale).decode()}${base64.b64encode(h).decode()}", utente.id))
    db.commit()
    account.accedi(db, "marco", vecchia, adesso=ADESSO)
    salvato = db.execute("SELECT password_hash FROM utenti WHERE id = ?", (utente.id,)).fetchone()[0]
    assert salvato.split("$")[1] == str(account.COSTO["n"])                # ricalcolato con i parametri di adesso
    account.accedi(db, "marco", vecchia, adesso=ADESSO)                    # e si entra ancora
    account.accedi(db, "marco", unicodedata.normalize("NFC", vecchia), adesso=ADESSO)


def test_hash_con_parametri_assurdi_non_manda_giu_il_server(db):
    utente, _, _ = nuovo(db)
    db.execute("UPDATE utenti SET password_hash = ? WHERE id = ?", (f"scrypt${2 ** 30}$8$1$AAAA$AAAA", utente.id))
    db.commit()
    assert errore(account.accedi, db, "marco", PASSWORD, adesso=ADESSO).stato == 401


@pytest.mark.parametrize("password", ["Password2026!", "fantacalcio_1", "!!juventus!!", "1234567890", "marco12345", "ocram12345",
                                      "x" * 201, "spazio​invisibile-lunga", "con\x00nul-lunghissima", "aaaaaaaaaaaaaa",
                                      "ciao‮oaic-lunga"])
def test_password_rifiutate(password):
    with pytest.raises(ErroreAccount):
        account.valida_password(password, "marco")


def test_password_massima_200_e_la_richiesta_oltre_500_e_422_senza_ripeterla(web):
    r = web.post("/api/account/registra", json={"nome_utente": "marco", "password": "A1b2" * 51, "invito": invito_http()})
    assert r.status_code == 400 and "200" in r.json()["detail"]
    segreta = "segreta-" + "y" * 600
    r = web.post("/api/account/accedi", json={"nome_utente": "marco", "password": segreta})
    assert r.status_code == 422 and "segreta" not in r.text and isinstance(r.json()["detail"], str)


@pytest.mark.parametrize("nome", ["ｍａｒｃｏ", "MARCO", " marco ", "Marco", "ＭＡＲＣＯ"])
def test_nomi_uguali_a_occhio_sono_lo_stesso_nome(db, nome):
    """Attacco: registrarsi come «ｍａｒｃｏ» (larghezza piena) o «MARCO» per farsi passare per marco. È lo stesso nome: già preso."""
    nuovo(db, "marco")
    assert "già preso" in errore(nuovo, db, nome).messaggio


@pytest.mark.parametrize("nome", ["mar​co", "marco‮", "mаrco", "mar\nco", "mar co", "ma", "a" * 33, "../admin",
                                  "marco'--", "marco\x00", "<script>", "-marco", "ḿarco"])
def test_nomi_con_caratteri_invisibili_omoglifi_o_strani_rifiutati(nome):
    """Spazi invisibili, inversione di testo (RTL), la «а» cirillica, a capo, accenti combinati: rifiutati, niente sosia."""
    with pytest.raises(ErroreAccount):
        account.valida_nome(nome)


def test_il_vincolo_unique_del_database_tiene_anche_se_il_codice_sbagliasse(db):
    nuovo(db, "marco")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO utenti (nome_utente, password_hash, recupero_hash, creato) VALUES ('marco', 'x', 'y', 'z')")
    db.rollback()


# ================================================================ (e) sessioni
def test_sessione_token_lungo_e_salvato_come_hash(db):
    _, token, _ = nuovo(db)
    assert len(base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))) >= 32               # almeno 256 bit
    salvati = [r[0] for r in db.execute("SELECT token_hash FROM sessioni")]
    assert token not in salvati and hashlib.sha256(token.encode()).hexdigest() in salvati


def test_sessione_ruota_all_accesso_niente_fissazione(web):
    """Attacco (fissazione): far usare alla vittima un cookie scelto dall'attaccante. Il server non accetta token inventati e
    all'accesso chiude la sessione che il dispositivo aveva già."""
    da("1.1.1.1").post("/api/account/registra", json={"nome_utente": "marco", "password": PASSWORD, "invito": invito_http()})
    c = da("2.2.2.2")
    scelto = {"Cookie": f"{rotte_account.COOKIE}=token-scelto-dall-attaccante"}
    assert c.get("/api/account/me", headers=scelto).status_code == 401
    primo = c.post("/api/account/accedi", json={"nome_utente": "marco", "password": PASSWORD}, headers=scelto)
    vecchio = primo.cookies.get(rotte_account.COOKIE)
    assert vecchio and vecchio != "token-scelto-dall-attaccante"
    c.cookies.clear()
    secondo = c.post("/api/account/accedi", json={"nome_utente": "marco", "password": PASSWORD},
                     headers={"Cookie": f"{rotte_account.COOKIE}={vecchio}"})
    assert secondo.cookies.get(rotte_account.COOKIE) != vecchio
    assert cliente(Authorization=f"Bearer {vecchio}").get("/api/account/me").status_code == 401        # il primo è chiuso


def test_cambio_password_ruota_la_sessione_e_chiude_le_altre(web):
    r = da("1.1.1.1").post("/api/account/registra", json={"nome_utente": "marco", "password": PASSWORD, "invito": invito_http(), "nativo": True})
    vecchio = r.json()["token"]
    ladro = cliente(Authorization=f"Bearer {vecchio}")
    cambio = ladro.post("/api/account/cambia-password", json={"attuale": PASSWORD, "nuova": "nuova-password-lunga"})
    assert cambio.status_code == 200 and cambio.json()["token"] != vecchio
    assert ladro.get("/api/account/me").status_code == 401
    assert cliente(Authorization=f"Bearer {cambio.json()['token']}").get("/api/account/me").status_code == 200


def test_scadenza_per_inattivita_e_assoluta(db):
    _, token, _ = nuovo(db)
    assert account.utente_da_token(db, token, ADESSO + timedelta(days=31)) is None
    _, t2 = account.accedi(db, "marco", PASSWORD, adesso=ADESSO)
    for giorni in range(20, 180, 20):
        assert account.utente_da_token(db, t2, ADESSO + timedelta(days=giorni)) is not None
    assert account.utente_da_token(db, t2, ADESSO + timedelta(days=181)) is None


def test_le_sessioni_di_oggi_continuano_a_valere(db):
    """Retrocompatibilità: una sessione creata dalla versione di prima (scadenza a 90 giorni) resta valida."""
    utente, _, _ = nuovo(db)
    token = "token-della-versione-di-prima-abbastanza-lungo"
    db.execute("INSERT INTO sessioni (utente_id, token_hash, creata, scade, ultimo_uso) VALUES (?, ?, ?, ?, ?)",
               (utente.id, hashlib.sha256(token.encode()).hexdigest(), account._testo(ADESSO), account._testo(ADESSO + timedelta(days=90)),
                account._testo(ADESSO)))
    db.commit()
    assert account.utente_da_token(db, token, ADESSO + timedelta(days=2)).id == utente.id


def test_cookie_httponly_strict_path_e_secure_su_https(web):
    r = da("1.1.1.1", **{"X-Forwarded-Proto": "https"}).post(
        "/api/account/registra", json={"nome_utente": "marco", "password": PASSWORD, "invito": invito_http()})
    c = r.headers["set-cookie"].lower()
    assert all(x in c for x in ("httponly", "samesite=strict", "path=/", "secure"))
    assert "strict-transport-security" in r.headers


def test_il_token_nell_indirizzo_non_vale(web):
    r = da("1.1.1.1").post("/api/account/registra", json={"nome_utente": "marco", "password": PASSWORD, "invito": invito_http(), "nativo": True})
    token = r.json()["token"]
    assert cliente().get(f"/api/account/me?token={token}").status_code == 401
    assert cliente().get(f"/api/account/me?{rotte_account.COOKIE}={token}").status_code == 401


def test_recupero_chiude_tutte_le_sessioni(db):
    utente, token, codice = nuovo(db)
    _, t2 = account.accedi(db, "marco", PASSWORD, adesso=ADESSO)
    account.recupera(db, "marco", codice, "nuova-password-lunga")
    assert account.utente_da_token(db, token, ADESSO) is None and account.utente_da_token(db, t2, ADESSO) is None


# ================================================================ CSRF: richieste da un altro sito
@pytest.mark.parametrize("intestazioni,stato", [
    ({"Sec-Fetch-Site": "cross-site"}, 403), ({"Sec-Fetch-Site": "same-site"}, 403), ({"Origin": "https://cattivo.example"}, 403),
    ({"Origin": "null"}, 403), ({"Sec-Fetch-Site": "same-origin"}, 401), ({"Origin": "http://testserver"}, 401), ({}, 401)])
def test_csrf_da_un_altro_sito_rifiutato(web, intestazioni, stato):
    """Un altro sito aperto sullo stesso telefono non può far partire azioni con il cookie dell'utente."""
    r = cliente(**intestazioni).post("/api/account/accedi", json={"nome_utente": "marco", "password": "sbagliata-sbagliata"})
    assert r.status_code == stato


def test_csrf_senza_x_fanta_rifiutato(web):
    assert TestClient(server.app).post("/api/account/esci").status_code == 403


# ================================================================ (f) intestazioni di sicurezza
@pytest.mark.parametrize("percorso", ["/", "/app.js", "/api/account/me", "/api/regole", "/api/non-esiste", "/robots.txt"])
def test_intestazioni_di_sicurezza_ovunque(web, percorso):
    h = web.get(percorso).headers
    assert "default-src 'self'" in h["content-security-policy"] and "frame-ancestors 'none'" in h["content-security-policy"]
    assert "script-src 'self'" in h["content-security-policy"] and "unsafe-eval" not in h["content-security-policy"]
    assert h["x-content-type-options"] == "nosniff" and h["x-frame-options"] == "DENY" and h["referrer-policy"] == "no-referrer"
    assert "camera=()" in h["permissions-policy"]
    if percorso.startswith("/api/"):
        assert "no-store" in h["cache-control"]


def test_la_pagina_non_ha_script_in_linea():
    """La CSP vieta gli script in linea: la pagina non deve averne (altrimenti l'app non partirebbe)."""
    html = (Path(server.WEB) / "index.html").read_text(encoding="utf-8")
    assert not re.search(r"<script(?![^>]*\bsrc=)[^>]*>", html) and not re.search(r"\son[a-z]+=", html)


def test_hsts_solo_su_https(web):
    assert "strict-transport-security" not in web.get("/").headers


# ================================================================ (h) input ostili
@pytest.mark.parametrize("corpo", [
    {"nome_utente": 123, "password": "x"}, {"nome_utente": ["marco"], "password": PASSWORD}, {"nome_utente": None, "password": None},
    {"nome_utente": {"$ne": ""}, "password": PASSWORD}, {}, [], "stringa", 42, None])
def test_tipi_sbagliati_422_pulito(web, corpo):
    r = web.post("/api/account/accedi", json=corpo)
    assert r.status_code == 422 and isinstance(r.json()["detail"], str)


@pytest.mark.parametrize("nome", ["marco' OR '1'='1", "marco\"; DROP TABLE utenti; --", "\x00", "🙂" * 30, "\U0010ffff" * 10,
                                  "ﷺ" * 20, "‮‭" * 10])
def test_sql_injection_e_unicode_estremo_mai_500(web, nome):
    da("1.1.1.1").post("/api/account/registra", json={"nome_utente": "marco", "password": PASSWORD, "invito": invito_http()})
    r = da("2.2.2.2").post("/api/account/accedi", json={"nome_utente": nome, "password": nome * 2 or "x"})
    assert r.status_code in (401, 422), r.text
    r = da("3.3.3.3").post("/api/account/registra", json={"nome_utente": nome, "password": PASSWORD, "invito": nome})
    assert 400 <= r.status_code < 500
    with contextlib.closing(account.apri()) as d:
        assert [u["nome_utente"] for u in account.elenco(d)] == ["marco"]           # la tabella c'è ancora, intatta


def test_nel_codice_solo_query_con_parametri():
    """Nessuna query costruita incollando testo: in account.py le f-string nelle execute ci sono solo per PRAGMA con numeri."""
    for nome in ("account.py", "limiti.py", "rotte_account.py"):
        sorgente = (Path(account.__file__).parent / nome).read_text(encoding="utf-8")
        for riga in re.findall(r"execute(?:many|script)?\((f?\"[^\n]*)", sorgente):
            assert not riga.startswith("f") or "PRAGMA" in riga, riga


def test_surrogati_spaiati_nel_json(web):
    """JSON valido con un «\\ud800» da solo (non è un carattere vero): niente 500."""
    for campo in ("nome_utente", "password"):
        altro = "password" if campo == "nome_utente" else "nome_utente"
        corpo = b'{"' + altro.encode() + b'": "una-password", "' + campo.encode() + b'": "a\\ud800b"}'
        r = web.post("/api/account/accedi", content=corpo, headers={"Content-Type": "application/json"})
        assert r.status_code in (401, 422), r.text


def test_json_enorme_e_corpi_strani(web):
    assert web.post("/api/account/accedi", content=b"{" * 9000, headers={"Content-Type": "application/json"}).status_code == 413
    assert web.post("/api/account/accedi", content=b'{"nome_utente": "a"' + b" " * 5000 + b"}", headers={"Content-Type": "application/json"}).status_code == 422
    assert web.post("/api/account/accedi", headers={"Content-Length": "-1"}).status_code in (400, 413)
    assert web.post("/api/account/accedi", headers={"Content-Length": "abc"}).status_code in (400, 413)
    assert web.post("/api/account/accedi", content=b"nome_utente=marco&password=x", headers={"Content-Type": "application/x-www-form-urlencoded"}).status_code == 422
    assert web.post("/api/account/accedi", content=b"\xff\xfe\x00", headers={"Content-Type": "application/json"}).status_code in (400, 422)


def test_corpo_a_pezzi_senza_lunghezza_rifiutato(web):
    def pezzi():
        yield b'{"nome_utente": "marco", '
        yield b'"password": "x"}'
    assert web.post("/api/account/accedi", content=pezzi(), headers={"Content-Type": "application/json"}).status_code == 411


def test_metodi_sbagliati(web):
    assert web.get("/api/account/accedi").status_code in (404, 405)
    assert web.put("/api/account/accedi", json={}).status_code in (401, 405)
    assert web.delete("/api/account/registra").status_code in (401, 405)


def test_intestazioni_enormi_o_strane(web):
    assert web.get("/api/account/me", headers={"Authorization": "Bearer " + "x" * 20000}).status_code == 401
    assert web.get("/api/account/me", headers={"Cookie": f"{rotte_account.COOKIE}=" + "y" * 20000}).status_code == 401
    assert web.get("/api/account/me", headers={"Authorization": "Basic " + "z" * 100}).status_code == 401
    assert da("1" * 5000).post("/api/account/accedi", json={"nome_utente": "a", "password": "b"}).status_code == 401


def test_un_errore_imprevisto_e_un_500_pulito(web, monkeypatch):
    monkeypatch.setattr(account, "accedi_ricordando", lambda *a, **k: 1 / 0)
    r = TestClient(server.app, headers={"X-Fanta": "1"}, raise_server_exceptions=False)
    risposta = r.post("/api/account/accedi", json={"nome_utente": "marco", "password": "x"})
    assert risposta.status_code == 500 and "Traceback" not in risposta.text and "ZeroDivision" not in risposta.text
    assert "Errore interno" in risposta.json()["detail"]


# ================================================================ (i) registrazione: corse tra richieste
def _in_parallelo(n, funzione):
    esiti, barriera = [], threading.Barrier(n)

    def corri(i):
        barriera.wait()
        with contextlib.closing(account.apri()) as d:
            try:
                esiti.append(("ok", funzione(d, i)))
            except ErroreAccount as e:
                esiti.append(("no", e.stato))
    fili = [threading.Thread(target=corri, args=(i,)) for i in range(n)]
    for f in fili:
        f.start()
    for f in fili:
        f.join(60)
    return esiti


def test_stesso_invito_in_parallelo_un_solo_account(db):
    inv = account.crea_invito(db, "x", adesso=ADESSO)
    esiti = _in_parallelo(8, lambda d, i: account.registra(d, f"nome{i}", PASSWORD, inv, adesso=ADESSO))
    assert [e for e, _ in esiti].count("ok") == 1 and len(esiti) == 8
    assert db.execute("SELECT COUNT(*) FROM utenti").fetchone()[0] == 1


def test_stesso_nome_in_parallelo_un_solo_account(db):
    inviti = [account.crea_invito(db, "x", adesso=ADESSO) for _ in range(6)]
    esiti = _in_parallelo(6, lambda d, i: account.registra(d, "marco", PASSWORD, inviti[i], adesso=ADESSO))
    assert [e for e, _ in esiti].count("ok") == 1
    assert db.execute("SELECT COUNT(*) FROM utenti").fetchone()[0] == 1


def test_tetto_utenti_in_parallelo(db, monkeypatch):
    monkeypatch.setenv("MAX_UTENTI", "3")
    inviti = [account.crea_invito(db, "x", adesso=ADESSO) for _ in range(8)]
    _in_parallelo(8, lambda d, i: account.registra(d, f"nome{i}", PASSWORD, inviti[i], adesso=ADESSO))
    assert db.execute("SELECT COUNT(*) FROM utenti").fetchone()[0] == 3


def test_stesso_codice_di_recupero_in_parallelo_vale_una_volta(db):
    _, _, codice = nuovo(db)
    esiti = _in_parallelo(6, lambda d, i: account.recupera(d, "marco", codice, f"nuova-password-{i}-lunga"))
    assert [e for e, _ in esiti].count("ok") == 1


# ================================================================ (j) registro degli eventi
def test_registro_eventi_senza_segreti(web):
    r = da("1.1.1.1").post("/api/account/registra", json={"nome_utente": "marco", "password": PASSWORD, "invito": invito_http()})
    codice = r.json()["codice_recupero"]
    da("6.6.6.6").post("/api/account/accedi", json={"nome_utente": "marco", "password": "sbagliata-segreta-1"})
    da("6.6.6.6").post("/api/account/accedi", json={"nome_utente": "una-password-nel-nome!", "password": "x"})
    da("1.1.1.1").post("/api/account/recupero", json={"nome_utente": "marco", "codice": codice, "nuova": "nuova-password-lunga"})
    registro = (percorsi.cartella_account() / "sicurezza.log").read_text(encoding="utf-8")
    assert "registrazione" in registro and "accesso_fallito" in registro and "recupero" in registro and "ip=6.6.6.x" in registro
    assert "6.6.6.6" not in registro and "1.1.1.1" not in registro          # l'indirizzo intero non si conserva: solo la rete
    for segreto in (PASSWORD, "sbagliata-segreta-1", "una-password-nel-nome", codice, codice.replace("-", ""), "nuova-password-lunga"):
        assert segreto not in registro
    assert all(re.fullmatch(r"\S+ \S+( \w+=\S+)*", r) for r in registro.splitlines())          # niente righe inventate


def test_registro_con_rotazione(multiutente, monkeypatch):
    monkeypatch.setattr(account, "MAX_REGISTRO", 2000)
    for i in range(300):
        account.evento("prova", n=i)
    cartella = percorsi.cartella_account()
    assert (cartella / "sicurezza.log.1").exists() and not (cartella / "sicurezza.log.4").exists()
    assert (cartella / "sicurezza.log").stat().st_size <= 2200


# ================================================================ (k) stabilità
def test_tanti_accessi_insieme_nessun_blocco_del_database(web):
    """Venti dispositivi entrano ed escono nello stesso momento: nessun «database is locked», nessun 500."""
    da("1.1.1.1").post("/api/account/registra", json={"nome_utente": "marco", "password": PASSWORD, "invito": invito_http()})
    esiti, barriera = [], threading.Barrier(20)

    def dispositivo(i):
        c = da(f"10.0.{i}.1")
        barriera.wait()
        giusta = i % 2 == 0
        r = c.post("/api/account/accedi", json={"nome_utente": "marco", "password": PASSWORD if giusta else "sbagliata-sbagliata"})
        esiti.append((giusta, r.status_code))
        if giusta:
            esiti.append((None, c.get("/api/account/me").status_code))
    fili = [threading.Thread(target=dispositivo, args=(i,)) for i in range(20)]
    for f in fili:
        f.start()
    for f in fili:
        f.join(120)
    assert len(esiti) == 30, esiti                     # con l'elenco dei codici: se fallisce si vede quale risposta era sbagliata
    assert all(s == 200 for g, s in esiti if g) and all(s == 401 for g, s in esiti if g is False), esiti
    assert all(s == 200 for g, s in esiti if g is None), esiti


def _disco_lento(monkeypatch, ritardo: float):
    """Simula una scheda SD lenta: ogni scrittura confermata (commit) dura `ritardo` secondi, tenendo il blocco. Restituisce il contatore."""
    import time
    conta = [0]

    class Lenta(sqlite3.Connection):
        def commit(self):
            if self.in_transaction:
                conta[0] += 1
                time.sleep(ritardo)
            super().commit()
    vero = sqlite3.connect
    monkeypatch.setattr(account.sqlite3, "connect", lambda *a, **k: vero(*a, factory=Lenta, **k))
    return conta


def test_database_account_pragma_giusti_su_ogni_connessione(multiutente, dati_isolati):
    """Ogni connessione: attesa di 15 s, WAL, conferme senza attendere il disco (synchronous NORMAL = 1)."""
    from fanta import archivio
    with contextlib.closing(account.apri()) as d:
        assert d.execute("PRAGMA busy_timeout").fetchone()[0] == 15000
        assert d.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert d.execute("PRAGMA synchronous").fetchone()[0] == 1
    with contextlib.closing(archivio.apri(percorsi.cartella_account() / "fanta-prova.sqlite")) as d:
        assert d.execute("PRAGMA busy_timeout").fetchone()[0] == 30000
        assert d.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert d.execute("PRAGMA synchronous").fetchone()[0] == 1


def test_accesso_poche_conferme_sul_database(web, monkeypatch):
    """Ogni conferma (commit) tiene il blocco di scrittura per il tempo del disco: un accesso riuscito ne fa al massimo 2, uno sbagliato 1."""
    conta = _disco_lento(monkeypatch, 0)
    web.post("/api/account/registra", json={"nome_utente": "marco", "password": PASSWORD, "invito": invito_http()})
    conta[0] = 0
    assert da("5.5.5.5").post("/api/account/accedi", json={"nome_utente": "marco", "password": PASSWORD}).status_code == 200
    assert conta[0] <= 2, conta
    conta[0] = 0
    assert da("5.5.5.6").post("/api/account/accedi", json={"nome_utente": "marco", "password": "sbagliata-sbagliata"}).status_code == 401
    assert conta[0] <= 1, conta


def test_database_occupato_risponde_503_con_retry_after_non_500(web, monkeypatch):
    def occupato(*a, **k):
        raise sqlite3.OperationalError("database is locked")
    monkeypatch.setattr(account, "accedi_ricordando", occupato)
    r = web.post("/api/account/accedi", json={"nome_utente": "marco", "password": PASSWORD})
    assert r.status_code == 503 and r.headers["Retry-After"] == "3" and "Traceback" not in r.text

    def altro(*a, **k):
        raise sqlite3.OperationalError("no such table: x")
    monkeypatch.setattr(account, "accedi_ricordando", altro)
    assert web.post("/api/account/accedi", json={"nome_utente": "marco", "password": PASSWORD}).status_code == 500


def test_accessi_insieme_con_disco_lento_nessun_500(web, monkeypatch):
    """Scheda SD lenta simulata (ogni conferma tiene il blocco 0,3 s): venti accessi insieme, nessun «database is locked»."""
    _disco_lento(monkeypatch, 0.3)
    da("1.1.1.1").post("/api/account/registra", json={"nome_utente": "marco", "password": PASSWORD, "invito": invito_http()})
    esiti, barriera = [], threading.Barrier(20)

    def d(i):
        c = da(f"10.0.{i}.1")
        barriera.wait()
        r = c.post("/api/account/accedi", json={"nome_utente": "marco", "password": PASSWORD if i % 2 == 0 else "sbagliata-sbagliata"})
        esiti.append(r.status_code)
    fili = [threading.Thread(target=d, args=(i,)) for i in range(20)]
    for f in fili:
        f.start()
    for f in fili:
        f.join(120)
    assert sorted(set(esiti)) == [200, 401]


def test_database_rovinato_messaggio_chiaro_e_niente_cancellato(web):
    file = percorsi.cartella_account() / "account.sqlite"
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_bytes(b"questo non e' un database sqlite" * 100)
    prima = file.read_bytes()
    r = web.post("/api/account/accedi", json={"nome_utente": "marco", "password": PASSWORD})
    assert r.status_code == 503 and "rovinato" in r.json()["detail"] and "Traceback" not in r.text
    assert web.get("/api/regole", headers={"Authorization": "Bearer qualcosa"}).status_code == 503
    assert file.read_bytes() == prima                                     # niente cancellato né sovrascritto


def test_tanti_scrypt_insieme_al_massimo_due_alla_volta(multiutente, monkeypatch):
    insieme, massimo, blocco = [0], [0], threading.Lock()
    vero = account.hashlib.scrypt

    def conta(*a, **k):
        with blocco:
            insieme[0] += 1
            massimo[0] = max(massimo[0], insieme[0])
        try:
            import time
            time.sleep(0.02)
            return vero(*a, **k)
        finally:
            with blocco:
                insieme[0] -= 1
    monkeypatch.setattr(account.hashlib, "scrypt", conta)
    esiti = []

    def calcola():
        try:
            account.hash_password(PASSWORD)
            esiti.append("fatto")
        except account.ErroreAccount as e:              # oltre le attese ammesse (ATTESE_MASSIME): «riprova» subito
            esiti.append(e.stato)
    fili = [threading.Thread(target=calcola) for _ in range(10)]
    for f in fili:
        f.start()
    for f in fili:
        f.join(30)
    assert massimo[0] <= account.CALCOLI_INSIEME
    assert len(esiti) == 10 and set(esiti) <= {"fatto", 429} and esiti.count("fatto") >= account.CALCOLI_INSIEME
