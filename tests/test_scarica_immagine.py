"""Download di stemma/maglia da un indirizzo web: prove avversarie (SSRF, redirect, DNS rebinding, file enormi, tipo falso).
Nessuna prova tocca la rete vera: `risolvi` e `apri` sono sostituiti da finti."""
import http.client

import pytest

from fanta import immagini, scarica_immagine as si

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64
JPG = b"\xff\xd8\xff\xe0" + b"0" * 64
WEBP = b"RIFF\x10\x00\x00\x00WEBPVP8 " + b"0" * 32


class Risposta:
    def __init__(self, status=200, corpo=b"", intestazioni=None, pezzi_infiniti=False):
        self.status, self.headers, self._corpo, self._inf = status, intestazioni or {}, corpo, pezzi_infiniti
        self.chiusa = False

    def read(self, n):
        if self._inf:
            return b"\x89" * n
        pezzo, self._corpo = self._corpo[:n], self._corpo[n:]
        return pezzo

    def close(self):
        self.chiusa = True


class Rete:
    """DNS e server finti: `dns` = nome -> indirizzi (o lista di liste: una per ogni risoluzione); `siti` = (host, percorso) -> Risposta."""

    def __init__(self, dns, siti):
        self.dns, self.siti, self.risolti, self.aperti = dns, siti, [], []

    def risolvi(self, host, porta):
        self.risolti.append(host)
        v = self.dns.get(host, [])
        if v and isinstance(v[0], list):                 # DNS rebinding: la risposta cambia a ogni domanda
            return v[min(len(self.risolti_di(host)) - 1, len(v) - 1)]
        return v

    def risolti_di(self, host):
        return [h for h in self.risolti if h == host]

    def apri(self, ip, host, porta, percorso, timeout):
        self.aperti.append((ip, host, porta, percorso))
        r = self.siti[(host, percorso)]
        if isinstance(r, Exception):
            raise r
        return r

    def scarica(self, url, **k):
        return si.scarica(url, risolvi=self.risolvi, apri=self.apri, **k)


def rete(siti, dns=None):
    return Rete(dns or {"img.example.com": ["93.184.216.34"], "altro.example.org": ["8.8.4.4"]}, siti)


# ---------------------------------------------------------------- il caso buono
@pytest.mark.parametrize("corpo,ext", [(PNG, ".png"), (JPG, ".jpg"), (WEBP, ".webp")])
def test_scarica_i_tre_formati(corpo, ext):
    r = rete({("img.example.com", "/s.img"): Risposta(200, corpo)})
    assert r.scarica("https://img.example.com/s.img") == (corpo, ext)
    assert r.aperti == [("93.184.216.34", "img.example.com", 443, "/s.img")]      # ci si collega all'indirizzo controllato


def test_indirizzo_con_lettere_accentate_non_rompe_la_richiesta():
    """Un indirizzo incollato con lettere accentate nel percorso (non ancora «%C3%A0») deve partire ASCII: prima http.client
    alzava UnicodeEncodeError con un messaggio in inglese. Le sequenze «%xx» già presenti restano com'erano."""
    host, porta, percorso = si._scomponi("https://img.example.com/stemmi/città%20x.png?n=è&a=b")
    assert (host, porta) == ("img.example.com", 443)
    assert percorso == "/stemmi/citt%C3%A0%20x.png?n=%C3%A8&a=b"
    r = rete({("img.example.com", "/stemmi/citt%C3%A0.png"): Risposta(200, PNG)})
    assert r.scarica("https://img.example.com/stemmi/città.png")[0] == PNG


def test_percorso_con_parametri_e_maiuscole_nel_nome():
    r = rete({("img.example.com", "/a/b.png?x=1&y=2"): Risposta(200, PNG)})
    assert r.scarica("  HTTPS://Img.Example.com/a/b.png?x=1&y=2  ")[0] == PNG


# ---------------------------------------------------------------- indirizzi vietati (SSRF)
@pytest.mark.parametrize("ip", ["127.0.0.1", "127.1.2.3", "10.0.0.5", "192.168.1.10", "172.16.0.1", "169.254.169.254", "169.254.0.1",
                                "0.0.0.0", "100.64.0.1", "224.0.0.1", "255.255.255.255", "::1", "::", "fe80::1", "fc00::1", "fd12:3456::1",
                                "::ffff:127.0.0.1", "::ffff:10.0.0.1", "::ffff:169.254.169.254", "64:ff9b::7f00:1", "2002:7f00:1::1",
                                "fe80::1%eth0", "ff02::1", "192.0.2.1", "198.51.100.7"])
def test_indirizzi_non_pubblici_rifiutati(ip):
    assert si.indirizzo_pubblico(ip) is False
    r = rete({}, {"sito.example.com": [ip]})
    with pytest.raises(ValueError, match="rete privata"):
        r.scarica("https://sito.example.com/s.png")
    assert r.aperti == []                                 # non ci si è nemmeno collegati


@pytest.mark.parametrize("ip", ["93.184.216.34", "8.8.8.8", "2606:4700:4700::1111", "2a00:1450:4002::65"])
def test_indirizzi_pubblici_accettati(ip):
    assert si.indirizzo_pubblico(ip) is True


@pytest.mark.parametrize("url", ["https://localhost/s.png", "https://127.0.0.1/s.png", "https://[::1]/s.png", "https://[::ffff:7f00:1]/s.png",
                                 "https://169.254.169.254/latest/meta-data/", "https://2130706433/s.png", "https://0x7f.1/s.png",
                                 "https://127.1/s.png", "https://metadata.google.internal/", "https://10.0.0.1/s.png"])
def test_host_interni_con_la_risoluzione_vera_mai_raggiunti(url, monkeypatch):
    """Con il DNS vero di questa macchina: se un nome interno si risolve in un indirizzo non pubblico, non si apre nessuna connessione."""
    chiamate = []
    monkeypatch.setattr(si, "_apri", lambda *a, **k: chiamate.append(a))
    with pytest.raises(ValueError):
        si.scarica(url)
    assert chiamate == []


def test_un_solo_indirizzo_privato_tra_tanti_basta_a_rifiutare():
    r = rete({}, {"misto.example.com": ["93.184.216.34", "10.0.0.7"]})
    with pytest.raises(ValueError, match="rete privata"):
        r.scarica("https://misto.example.com/s.png")


def test_nessun_indirizzo_trovato():
    r = rete({}, {})
    with pytest.raises(ValueError, match="Non trovo il sito"):
        r.scarica("https://non-esiste.example.com/s.png")


# ---------------------------------------------------------------- forma dell'indirizzo
@pytest.mark.parametrize("url", ["http://img.example.com/s.png", "ftp://img.example.com/s.png", "file:///etc/passwd", "gopher://img.example.com/",
                                 "javascript:alert(1)", "data:image/png;base64,AAAA", "//img.example.com/s.png", "img.example.com/s.png", "",
                                 "   ", "https://", "https:///s.png", "https://utente:pw@img.example.com/s.png", "https://utente@img.example.com/s.png",
                                 "https://img.example.com:8443/s.png", "https://img.example.com:80/s.png", "https://img.example.com/a b.png",
                                 "https://img.example.com/\x00.png", "https://img.example.com/\n.png", "https://img.example.com:abc/s.png",
                                 "https://" + "a" * 2100 + ".com/s.png"])
def test_indirizzi_malformati_o_non_https_rifiutati(url):
    r = rete({})
    with pytest.raises(ValueError):
        r.scarica(url)
    assert r.aperti == [] and r.risolti == []


def test_porta_443_esplicita_va_bene():
    r = rete({("img.example.com", "/s.png"): Risposta(200, PNG)})
    assert r.scarica("https://img.example.com:443/s.png")[0] == PNG


# ---------------------------------------------------------------- redirect
def test_redirect_verso_altro_sito_pubblico():
    r = rete({("img.example.com", "/a"): Risposta(302, intestazioni={"Location": "https://altro.example.org/b.png"}),
              ("altro.example.org", "/b.png"): Risposta(200, PNG)})
    assert r.scarica("https://img.example.com/a")[0] == PNG
    assert r.risolti == ["img.example.com", "altro.example.org"]


def test_redirect_relativo():
    r = rete({("img.example.com", "/a"): Risposta(301, intestazioni={"Location": "/dir/b.png"}),
              ("img.example.com", "/dir/b.png"): Risposta(200, PNG)})
    assert r.scarica("https://img.example.com/a")[0] == PNG


@pytest.mark.parametrize("destinazione", ["https://127.0.0.1/s.png", "https://169.254.169.254/latest/meta-data/", "https://[::1]/x",
                                          "https://interno.example.com/x", "http://altro.example.org/b.png", "file:///etc/passwd",
                                          "https://utente:pw@altro.example.org/b.png", "https://altro.example.org:8080/b.png", "gopher://altro.example.org/"])
def test_redirect_verso_rete_privata_o_schema_vietato(destinazione):
    r = rete({("img.example.com", "/a"): Risposta(302, intestazioni={"Location": destinazione})},
             {"img.example.com": ["93.184.216.34"], "altro.example.org": ["8.8.4.4"], "interno.example.com": ["192.168.0.9"]})
    with pytest.raises(ValueError):
        r.scarica("https://img.example.com/a")
    assert [a[1] for a in r.aperti] == ["img.example.com"]          # al secondo passo non si è aperto nulla


def test_al_massimo_tre_redirect():
    siti = {("img.example.com", f"/{i}"): Risposta(302, intestazioni={"Location": f"/{i + 1}"}) for i in range(10)}
    siti[("img.example.com", "/3")] = Risposta(200, PNG)
    assert rete(siti).scarica("https://img.example.com/0")[0] == PNG        # 3 redirect: ancora ok
    siti[("img.example.com", "/3")] = Risposta(302, intestazioni={"Location": "/4"})
    siti[("img.example.com", "/4")] = Risposta(200, PNG)
    with pytest.raises(ValueError, match="troppe volte"):
        rete(siti).scarica("https://img.example.com/0")                     # il quarto no


def test_redirect_in_cerchio():
    siti = {("img.example.com", "/a"): Risposta(302, intestazioni={"Location": "/a"})}
    with pytest.raises(ValueError, match="troppe volte"):
        rete(siti).scarica("https://img.example.com/a")


def test_redirect_senza_destinazione():
    with pytest.raises(ValueError, match="senza destinazione"):
        rete({("img.example.com", "/a"): Risposta(302)}).scarica("https://img.example.com/a")


def test_risposte_chiuse_anche_in_errore():
    r1 = Risposta(302, intestazioni={"Location": "/b"})
    r2 = Risposta(200, b"non e' un'immagine")
    r = rete({("img.example.com", "/a"): r1, ("img.example.com", "/b"): r2})
    with pytest.raises(ValueError):
        r.scarica("https://img.example.com/a")
    assert r1.chiusa and r2.chiusa


# ---------------------------------------------------------------- DNS rebinding
def test_dns_rebinding_ci_si_collega_all_indirizzo_controllato_e_non_si_risolve_due_volte():
    """Prima risposta pubblica, seconda interna: la connessione deve andare all'indirizzo già controllato (la prima risposta)."""
    r = rete({("sito.example.com", "/s.png"): Risposta(200, PNG)}, {"sito.example.com": [["93.184.216.34"], ["127.0.0.1"]]})
    assert r.scarica("https://sito.example.com/s.png")[0] == PNG
    assert r.risolti == ["sito.example.com"]                 # una sola domanda al DNS
    assert r.aperti[0][0] == "93.184.216.34"


def test_dns_rebinding_su_redirect_la_nuova_risoluzione_e_controllata():
    r = rete({("sito.example.com", "/a"): Risposta(302, intestazioni={"Location": "https://sito.example.com/b"})},
             {"sito.example.com": [["93.184.216.34"], ["127.0.0.1"]]})
    with pytest.raises(ValueError, match="rete privata"):
        r.scarica("https://sito.example.com/a")
    assert len(r.aperti) == 1


def test_connessione_vera_va_all_indirizzo_non_al_nome(monkeypatch):
    """La classe di connessione vera: `create_connection` riceve l'IP, non il nome (così non c'è una seconda risoluzione)."""
    viste = []

    def finta(indirizzo, timeout):
        viste.append(indirizzo)
        raise OSError("stop")

    monkeypatch.setattr(si.socket, "create_connection", finta)
    c = si._Connessione("sito.example.com", "93.184.216.34", 443, 3)
    with pytest.raises(OSError):
        c.connect()
    assert viste == [("93.184.216.34", 443)]
    assert c.host == "sito.example.com"                      # `Host` e verifica del certificato usano il nome


def test_richiesta_senza_cookie_ne_credenziali(monkeypatch):
    """Le intestazioni della richiesta vera: nessun Cookie né Authorization."""
    mandate = {}

    class Finta(si._Connessione):
        def request(self, metodo, percorso, headers=None, **k):
            mandate.update(headers or {})
            raise OSError("stop")

    monkeypatch.setattr(si, "_Connessione", Finta)
    with pytest.raises(OSError):
        si._apri("93.184.216.34", "img.example.com", 443, "/s.png", 3)
    assert not {k.lower() for k in mandate} & {"cookie", "authorization", "proxy-authorization", "referer", "origin"}
    assert mandate["Accept-Encoding"] == "identity"


# ---------------------------------------------------------------- dimensioni, tempo, tipo
def test_file_troppo_grande_dichiarato():
    r = rete({("img.example.com", "/g"): Risposta(200, PNG, {"Content-Length": str(immagini.MAX_BYTE + 1)})})
    with pytest.raises(ValueError, match="troppo grande"):
        r.scarica("https://img.example.com/g")


def test_file_troppo_grande_senza_dichiararlo():
    r = rete({("img.example.com", "/g"): Risposta(200, PNG + b"0" * (immagini.MAX_BYTE + 10))})
    with pytest.raises(ValueError, match="troppo grande"):
        r.scarica("https://img.example.com/g")


def test_file_infinito_si_ferma_al_tetto():
    letti = []
    risposta = Risposta(200, pezzi_infiniti=True)
    originale = risposta.read
    risposta.read = lambda n: (letti.append(n), originale(n))[1]
    with pytest.raises(ValueError, match="troppo grande"):
        rete({("img.example.com", "/g"): risposta}).scarica("https://img.example.com/g")
    assert sum(letti) <= immagini.MAX_BYTE + si.PEZZO       # mai letto molto oltre il tetto


def test_esattamente_quattro_mega_va_bene():
    corpo = PNG + b"0" * (immagini.MAX_BYTE - len(PNG))
    assert len(rete({("img.example.com", "/g"): Risposta(200, corpo)}).scarica("https://img.example.com/g")[0]) == immagini.MAX_BYTE


@pytest.mark.parametrize("corpo", [b"<html><body>Accedi</body></html>", b"GIF89a" + b"0" * 30, b"%PDF-1.4", b"<svg xmlns='http://www.w3.org/2000/svg'/>", b"", b"MZ\x90\x00",
                                   b"RIFF\x00\x00\x00\x00WAVEfmt "])
def test_tipo_falso_rifiutato_dai_byte(corpo):
    """Anche se il sito dice «image/png», contano solo i byte."""
    r = rete({("img.example.com", "/f"): Risposta(200, corpo, {"Content-Type": "image/png"})})
    with pytest.raises(ValueError, match="PNG, JPEG o WebP"):
        r.scarica("https://img.example.com/f")


@pytest.mark.parametrize("stato", [401, 403, 404, 500, 204, 206])
def test_risposte_non_200(stato):
    with pytest.raises(ValueError, match=str(stato)):
        rete({("img.example.com", "/f"): Risposta(stato, PNG)}).scarica("https://img.example.com/f")


def test_sito_troppo_lento():
    t = [0.0]

    class Lenta(Risposta):
        def read(self, n):
            t[0] += 10                                   # ogni lettura «costa» 10 secondi
            return super().read(n)

    r = rete({("img.example.com", "/l"): Lenta(200, PNG + b"0" * 200_000)})
    with pytest.raises(ValueError, match="troppo lento"):
        r.scarica("https://img.example.com/l", orologio=lambda: t[0])


def test_connessione_fallita_o_certificato_sbagliato():
    for errore in (OSError("rifiutata"), http.client.HTTPException("rotto"), TimeoutError()):
        with pytest.raises(ValueError, match="Non riesco a collegarmi"):
            rete({("img.example.com", "/f"): errore}).scarica("https://img.example.com/f")


def test_lettura_interrotta():
    class Rotta(Risposta):
        def read(self, n):
            raise http.client.IncompleteRead(b"")

    with pytest.raises(ValueError, match="interrotto"):
        rete({("img.example.com", "/f"): Rotta(200)}).scarica("https://img.example.com/f")


def test_secondo_indirizzo_se_il_primo_non_risponde():
    class R(Rete):
        def apri(self, ip, host, porta, percorso, timeout):
            self.aperti.append(ip)
            if ip == "93.184.216.34":
                raise OSError("giu'")
            return Risposta(200, PNG)

    r = R({"x.example.com": ["93.184.216.34", "8.8.8.8"]}, {})
    assert r.scarica("https://x.example.com/s.png")[0] == PNG and r.aperti == ["93.184.216.34", "8.8.8.8"]
