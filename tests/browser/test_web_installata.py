"""La web installata sul telefono (#654). Il service worker tiene la «scocca» dell'app (pagina, script, stile, icone) per aprirla
subito, anche senza rete. Qui il service worker è acceso (fixture `installata`), davanti al server finto c'è un proxy che fa la
parte di nginx (rete debole, 502 mentre il servizio riparte, rete assente) e la web è una copia, da cambiare per un rilascio finto:
- dopo un rilascio, con la rete debole sui file grossi, la pagina non mescola file di due versioni (un testo nuovo non compare
  come chiave) e la versione nuova arriva con «Ricarica»;
- mentre il server riparte (502 dal proxy) si apre l'app salvata, non la pagina d'errore del proxy;
- senza rete Privacy (mai aperta prima) dice «Nessuna connessione» invece di aprire un'altra copia dell'app.
Ogni test gira una volta (niente fasi della giornata): conta il service worker, non la schermata.
"""
import re
from urllib.parse import urlsplit

SCRIPT = ["testi.js", "avatar.js", "dafare.js", "anteprima.js", "primoavvio.js", "app.js", "impostazioni.js"]
# Di che versione è ogni file della pagina: gli script lo scrivono in window.__versioni, la pagina in un <meta>, lo stile in una
# variabile CSS (vedi `rilascio`).
VERSIONI = """() => {
  const v = Object.assign({}, window.__versioni || {});
  const meta = document.querySelector('meta[name=versione-di-prova]');
  v['index.html'] = meta ? meta.content : null;
  v['stile.css'] = getComputedStyle(document.documentElement).getPropertyValue('--versione-di-prova').trim().replace(/"/g, '') || null;
  return v; }"""
TESTO_NUOVO = "() => { const e = document.getElementById('prova-nuova'); return e ? e.textContent : null; }"
SEZIONI = "Sezioni"            # la barra delle schede dell'app (nav.sezioni): c'è solo se si è aperta l'app
# /api/account/me del server con gli account (com'è in produzione), per un utente normale inventato
UTENTE = {"multiutente": True, "utente": {"id": 7, "nome_utente": "amico", "nome_visualizzato": "Amico di prova", "ruolo": "utente",
                                           "creato": "2026-10-01T10:00:00"}}


def rilascio(web, originali: dict[str, str], versione: str, testo_nuovo: bool = False) -> None:
    """Una versione della web: ogni file della scocca dice la sua `versione`. Con `testo_nuovo` il catalogo (testi.js) ha una
    frase nuova che un file piccolo (impostazioni.js) mostra, come quando una funzione nuova porta il suo testo."""
    for nome in SCRIPT:
        aggiunta = f'\n;(window.__versioni = window.__versioni || {{}})["{nome}"] = "{versione}";\n'
        if testo_nuovo and nome == "testi.js":
            aggiunta += 'TESTI.it["prova.nuova"] = "Testo nuovo"; TESTI.en["prova.nuova"] = "New text";\n'
        if testo_nuovo and nome == "impostazioni.js":
            aggiunta += ('{ const p = document.createElement("p"); p.id = "prova-nuova"; p.textContent = t("prova.nuova"); '
                         'document.body.append(p); }\n')
        (web / nome).write_text(originali[nome] + aggiunta, encoding="utf-8")
    (web / "index.html").write_text(originali["index.html"].replace(
        "<head>", f'<head>\n  <meta name="versione-di-prova" content="{versione}">', 1), encoding="utf-8")
    (web / "stile.css").write_text(originali["stile.css"] + f'\n:root {{ --versione-di-prova: "{versione}"; }}\n', encoding="utf-8")


def alza_versione(web) -> None:
    """Come il job `rilascia`: VERSIONE di sw.js più uno (il browser vede un service worker nuovo)."""
    sw = web / "sw.js"
    testo, quanti = re.subn(r'(const VERSIONE = "fanta-)(\d+)(")', lambda m: f"{m[1]}{int(m[2]) + 1}{m[3]}",
                            sw.read_text(encoding="utf-8"))
    assert quanti == 1, "riga VERSIONE non trovata in sw.js"
    sw.write_text(testo, encoding="utf-8")


def test_dopo_un_rilascio_con_la_rete_debole_la_pagina_ha_una_versione_sola(installata):
    web = installata.web
    originali = {n: (web / n).read_text(encoding="utf-8") for n in SCRIPT + ["index.html", "stile.css"]}
    rilascio(web, originali, "v1")
    installata.installa()
    rilascio(web, originali, "v2", testo_nuovo=True)
    alza_versione(web)
    installata.proxy.lenti = {"/app.js": 4, "/testi.js": 4}          # i due file grossi oltre i 2,5 secondi
    pagina = installata.scheda("/?da=app")                          # l'app riaperta dalla schermata Home
    versioni = pagina.evaluate(VERSIONI)
    assert set(versioni.values()) == {"v1"}, f"la pagina non è tutta della versione salvata, mescola file di due versioni: {versioni}"
    assert pagina.evaluate(TESTO_NUOVO) != "prova.nuova", "un testo nuovo compare come chiave: codice nuovo con il catalogo vecchio"
    # la versione nuova arriva con il service worker nuovo: la barra «Ricarica» la apre, tutta intera
    pagina.evaluate("() => navigator.serviceWorker.getRegistration().then(r => r && r.update()).catch(() => null)")
    ricarica = pagina.get_by_role("button", name="Ricarica")
    ricarica.wait_for(timeout=30000)
    with pagina.expect_navigation(wait_until="load"):
        ricarica.click()
    versioni = pagina.evaluate(VERSIONI)
    assert set(versioni.values()) == {"v2"}, f"dopo «Ricarica» non c'è tutta la versione nuova: {versioni}"
    assert pagina.evaluate(TESTO_NUOVO) == "Testo nuovo"
    assert not installata.errori, installata.errori


def test_mentre_il_server_riparte_si_apre_l_app_salvata(installata):
    installata.installa()
    installata.proxy.modo = "502"                                   # nginx davanti, il servizio dietro sta ripartendo
    pagina = installata.scheda("/?da=app")
    assert "502" not in pagina.title(), f"si vede la pagina d'errore del proxy: {pagina.title()!r}"
    assert pagina.get_by_role("navigation", name=SEZIONI).is_visible(), "non si è aperta l'app salvata"


def test_con_gli_account_mentre_il_server_riparte_restano_l_account_e_i_suoi_dati(installata):
    """In produzione ci sono gli account: durante il riavvio anche «chi sono» riceve 502. L'app riprende l'account salvato, come
    senza rete: mostra la copia dei dati di quell'account e, tornato il server, non diventa un altro utente (niente «Gestione»)."""
    installata.proxy.risposte["/api/account/me"] = UTENTE
    installata.installa()
    pagina = installata.scheda("/?vista=formazione")
    installata.aspetta(pagina)                                      # la Formazione letta resta nel browser, sotto l'account
    assert "punti attesi" in pagina.locator("main").inner_text()
    pagina.close()
    installata.proxy.modo = "502"
    pagina = installata.scheda("/?vista=formazione")
    installata.aspetta(pagina)
    testo = pagina.locator("main").inner_text()
    assert "punti attesi" in testo, f"durante il riavvio la Formazione salvata dell'account non si vede: {testo[:300]!r}"
    installata.proxy.modo = "ok"
    pagina.locator("main").get_by_role("button", name="Riprova").first.click()
    installata.aspetta(pagina)
    pagina.get_by_role("navigation", name=SEZIONI).get_by_role("link", name="Impostazioni").click()
    installata.aspetta(pagina)
    principale = pagina.locator("main")
    assert principale.get_by_role("button", name=re.compile(r"^\s*Il tuo account")).is_visible(), principale.inner_text()[:400]
    assert principale.get_by_role("button", name=re.compile(r"^\s*Gestione")).count() == 0, "un utente normale vede «Gestione»"
    assert not installata.errori, installata.errori


def test_senza_rete_privacy_dice_nessuna_connessione_e_l_app_si_apre(installata):
    installata.installa()
    installata.proxy.modo = "spento"
    pagina = installata.scheda("/privacy")                          # mai aperta prima: nessuna copia
    assert urlsplit(pagina.url).path == "/privacy", pagina.url
    assert pagina.get_by_role("navigation", name=SEZIONI).count() == 0, "senza rete Privacy ha aperto un'altra copia dell'app"
    assert pagina.get_by_role("heading", name="Nessuna connessione").is_visible()
    pagina.goto(installata.proxy.indirizzo + "/?vista=impostazioni", wait_until="load")     # l'app invece c'è, dalla copia salvata
    assert pagina.get_by_role("navigation", name=SEZIONI).is_visible(), "senza rete l'app salvata non si apre"
