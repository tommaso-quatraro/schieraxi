"""Ingresso di un amico invitato (#580, trovati dal percorso «amico nuovo»): pagina dell'invito e primo avvio.
Le funzioni si leggono da `fanta/web/app.js` e `fanta/web/primoavvio.js` e si provano con node, con il catalogo vero dei testi."""
import json
import re
import shutil
import subprocess

import pytest

import codice_web

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node non installato")

APP = codice_web.app()
TESTI = codice_web.leggi("testi.js")
PRIMO = codice_web.leggi("primoavvio.js")


def _funzione(src: str, nome: str) -> str:
    m = re.search(rf"^(?:async )?function {nome}\(.*?^\}}\n", src, re.S | re.M)
    assert m, f"{nome} non trovata"
    return m.group(0)


def _node(codice: str):
    r = subprocess.run([NODE, "-"], input=codice, capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


# ---- 1. invito già usato o scaduto: la password scritta non si svuota --------------------------------------------------
@pytest.mark.parametrize("scheda, stato, svuota", [
    ("registra", 403, False),              # invito non valido o già usato, registrazioni chiuse
    ("registra", 401, False),
    ("registra", 400, False),
    ("accedi", 401, True),                 # password sbagliata: si riscrive
    ("accedi", 403, True),
    ("accedi", 400, False),
    ("accedi", 429, False),                # attesa: quello che hai scritto resta
    ("recupero", 403, True),               # codice di recupero sbagliato
    ("recupero", 422, False),
])
def test_la_password_si_svuota_solo_se_rifiutata_e_mai_registrandosi(scheda, stato, svuota):
    codice = _funzione(APP, "svuotaPassword") + f"\nconsole.log(JSON.stringify(svuotaPassword({json.dumps(scheda)}, {stato})));"
    assert _node(codice) is svuota


def test_il_modulo_d_accesso_usa_la_regola():
    assert 'if ($("#ac-pw") && svuotaPassword(scheda, e.status)) $("#ac-pw").value = "";' in APP
    assert 'e.status === 401 || e.status === 403)) $("#ac-pw").value' not in APP


# ---- 2. codice d'invito già scritto (arrivato dal link): la pagina non chiede di procurarselo ------------------------------
def _registrati(modo: str, invito: str) -> str:
    """L'HTML dei campi di «Registrati», come lo scrive app.js, con il codice dal link salvato (o no) nella sessione."""
    blocco = re.search(r"^const campoAccesso = .*?(?=^// il testo del pulsante di invio)", APP, re.S | re.M)
    assert blocco, "campoAccesso / campiAccesso non trovati in app.js"
    codice = "\n".join([
        TESTI,
        "const esc = x => String(x);",
        f"const sessionStorage = {{ getItem: k => (k === 'invito' ? {json.dumps(invito)} : null) }};",
        f"const stato = {{ registrazione: {json.dumps(modo)}, emailAttiva: false }};",
        _funzione(APP, "invitoSalvato"),
        "const valoreInvito = () => (invitoSalvato() ? ` value=\"${esc(invitoSalvato())}\"` : '');",
        blocco.group(0),
        "console.log(JSON.stringify(campiAccesso('registra')));",
    ])
    return _node(codice)


def test_con_il_codice_dal_link_dice_che_e_gia_inserito():
    html = _registrati("invito", "ABCDE-FGHIJ")
    assert "Codice d'invito già inserito: scegli un nome utente e una password." in html
    assert "Ti serve un codice d'invito" not in html
    assert 'id="ac-invito"' in html and 'value="ABCDE-FGHIJ"' in html          # il campo resta, si può correggere


def test_senza_codice_chiede_di_procurarselo_come_prima():
    html = _registrati("invito", "")
    assert "Ti serve un codice d'invito: chiedilo a chi ti ha invitato." in html
    assert "già inserito" not in html


def test_con_email_obbligatoria_e_codice_dal_link():
    html = _registrati("email", "ABCDE-FGHIJ")
    assert "Codice d'invito già inserito. Serve anche un indirizzo email: ti mandiamo un codice per confermarlo." in html
    assert "Serve un codice d'invito" not in html
    assert "Serve un codice d'invito e un indirizzo email" in _registrati("email", "")


def test_registrazione_aperta_non_parla_di_inviti():
    assert "invito" not in _registrati("aperta", "ABCDE-FGHIJ").lower()


# ---- 3. il pulsante del file dice cosa accetta ------------------------------------------------------------------------
def test_il_pulsante_del_file_dice_excel_o_csv():
    codice = "\n".join([TESTI, "const esc = x => String(x); const stato = { account: true };", PRIMO,
                        "console.log(JSON.stringify(PA_SCHERMATE.rose().html));"])
    html = _node(codice)
    pulsante = re.search(r'<button class="bottone secondario" id="pa-scegli-file" type="button">([^<]*)</button>', html)
    assert pulsante and pulsante.group(1) == "Scegli il file (Excel o CSV)"
    accetta = re.search(r'<input id="pa-file" type="file" accept="([^"]*)"', html).group(1)
    assert ".xlsx" in accetta and ".csv" in accetta


# ---- 4. riaperta dalla Home con il primo avvio lasciato a metà: riprende dal passo dove era ------------------------------
PASSI = ["rose", "squadra", "tempi"]


def da_riprendere(stato, gia=()):
    codice = _funzione(PRIMO, "paDaRiprendere") + (
        f"\nconsole.log(JSON.stringify(paDaRiprendere({json.dumps(PASSI)}, {json.dumps(stato)}, {json.dumps(list(gia))})));")
    return _node(codice)


@pytest.mark.parametrize("stato, gia, atteso", [
    (None, [], None),                                                                       # mai iniziato: lo apre l'altra regola
    ({"fatti": ["server", "accesso"], "saltati": [], "chiuso": False}, [], "rose"),         # appena registrato
    ({"fatti": ["server", "accesso", "rose"], "saltati": [], "chiuso": False}, [], "squadra"),
    ({"fatti": ["server", "accesso"], "saltati": ["rose"], "chiuso": False}, [], "squadra"),  # un passo saltato resta saltato
    ({"fatti": ["server", "accesso", "rose", "squadra"], "saltati": [], "chiuso": False}, [], "tempi"),
    ({"fatti": ["server", "accesso"], "saltati": [], "chiuso": False}, ["rose", "squadra"], "tempi"),  # rose e squadra già fatte altrove
    ({"fatti": ["server", "accesso", "rose", "squadra"], "saltati": ["tempi"], "chiuso": False}, [], None),  # niente di aperto
    ({"fatti": ["server", "accesso", "rose", "squadra", "tempi"], "saltati": [], "chiuso": False}, [], None),
    ({"fatti": ["server", "accesso"], "saltati": [], "chiuso": True}, [], None),           # chiuso con «Vai a Oggi»: mai più da solo
])
def test_il_passo_da_cui_riprendere(stato, gia, atteso):
    assert da_riprendere(stato, gia) == atteso


def _avvio(primo_avvio, squadre=(), mia=False, chiamate=1, onboarding="nessuno") -> dict:
    """Esegue `primoAvvioSeServe` (una o più volte, come fanno l'avvio e Oggi senza rose) con il server finto: cosa ha aperto e salvato."""
    codice = "\n".join([
        TESTI,
        "const esc = x => String(x); const avviso = () => {};",
        f"const stato = {{ account: {{ nome_utente: 'amico' }}, squadre: {json.dumps(list(squadre))} }};",
        f"const miaSquadra = () => {json.dumps(bool(mia))};",
        "const scritte = [];",
        f"const risposte = {{ '/api/primo-avvio': {{ primo_avvio: {json.dumps(primo_avvio)} }}, '/api/onboarding': {{ stato: {json.dumps(onboarding)} }} }};",
        "async function api(percorso, opz = {}) {",
        "  if (opz.method === 'PUT') { scritte.push(JSON.parse(opz.body)); return { primo_avvio: JSON.parse(opz.body) }; }",
        "  return JSON.parse(JSON.stringify(risposte[percorso]));",
        "}",
        PRIMO,
        "let aperture = 0; apriPrimoAvvio = async () => { aperture += 1; };",
        "(async () => {",
        f"  await Promise.all(Array.from({{ length: {chiamate} }}, () => primoAvvioSeServe()));",
        "  await new Promise(r => setTimeout(r, 20));",
        "  console.log(JSON.stringify({ aperture, scritte }));",
        "})();",
    ])
    return _node(codice)


def test_riaperta_con_il_primo_avvio_a_meta_lo_riprende():
    esito = _avvio({"fatti": ["server", "accesso"], "saltati": [], "chiuso": False})
    assert esito["aperture"] == 1
    assert esito["scritte"] == []                         # lo stato salvato sul server resta com'era: si riprende, non si riparte


def test_riprende_anche_con_le_rose_gia_caricate():
    esito = _avvio({"fatti": ["server", "accesso", "rose"], "saltati": [], "chiuso": False}, squadre=[{"nome": "Real Esempio"}], mia=True)
    assert esito["aperture"] == 1                         # resta il passo «I tempi della lega»


def test_primo_avvio_chiuso_o_finito_non_si_riapre():
    assert _avvio({"fatti": ["server", "accesso"], "saltati": [], "chiuso": True})["aperture"] == 0
    finito = {"fatti": ["server", "accesso", "rose", "squadra"], "saltati": ["tempi"], "chiuso": False}
    assert _avvio(finito, squadre=[{"nome": "Real Esempio"}], mia=True)["aperture"] == 0


def test_chi_ha_gia_le_rose_e_non_l_ha_mai_iniziato_non_lo_vede():
    assert _avvio(None, squadre=[{"nome": "Real Esempio"}], mia=True) == {"aperture": 0, "scritte": []}


def test_account_nuovo_senza_rose_lo_apre_come_prima():
    esito = _avvio(None)
    assert esito["aperture"] == 1 and esito["scritte"] == [{"fatti": ["server", "accesso"]}]


def test_si_riprende_una_volta_sola_per_apertura_dell_app():
    """L'avvio e Oggi senza rose lo chiedono tutti e due: si apre una volta; chiuso con la ✕, non torna a ogni visita di Oggi."""
    assert _avvio({"fatti": ["server", "accesso"], "saltati": [], "chiuso": False}, chiamate=3)["aperture"] == 1
    assert _avvio(None, chiamate=2)["aperture"] == 1
