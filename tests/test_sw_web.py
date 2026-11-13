"""Service worker (fanta/web/sw.js): la scocca salvata deve esistere e restare pubblica anche con gli account accesi,
e il service worker deve installarsi anche se una copia manca. Il test di comportamento gira con node, se c'è."""
import json
import re
import shutil
import subprocess

import pytest

from fanta import rotte_account, server
import codice_web

SW = codice_web.leggi("sw.js")


def _scocca():
    """L'elenco FILE di sw.js (è un array JSON valido)."""
    m = re.search(r"const FILE = (\[.*?\]);", SW)
    assert m, "elenco FILE non trovato in sw.js"
    return json.loads(m.group(1))


def test_ogni_file_della_scocca_esiste_ed_e_pubblico_con_gli_account():
    for percorso in _scocca():
        if percorso == "/":
            continue
        assert (server.WEB / percorso.lstrip("/")).is_file(), f"manca {percorso}"
        assert rotte_account._pubblico(percorso), f"{percorso} risponderebbe 401 con FANTA_MULTIUTENTE=1 e farebbe fallire il service worker"


def test_la_pagina_carica_solo_file_che_stanno_nella_scocca():
    html = (server.WEB / "index.html").read_text(encoding="utf-8")
    caricati = re.findall(r'<script src="([^"]+)"', html) + re.findall(r'<link rel="stylesheet" href="([^"]+)"', html)
    scocca = {p.lstrip("/") for p in _scocca()}
    for f in caricati:
        assert f in scocca, f"{f} non è nella scocca: senza rete la pagina resterebbe senza questo file"


@pytest.mark.skipif(shutil.which("node") is None, reason="serve node per provare il service worker")
def test_comportamento_del_service_worker_con_node():
    prova = r"""
const fs = require("fs");
const testo = fs.readFileSync(process.argv[1], "utf8");
const cache = new Map();                    // nome cache -> mappa url -> risposta
const eventi = {};
const self = { addEventListener: (t, f) => { eventi[t] = f; }, skipWaiting: () => { self.saltata = true; return Promise.resolve(); },
               clients: { claim: () => Promise.resolve() }, location: { origin: "http://x" } };
let reteSpenta = false;
class Response { constructor(corpo, init) { this.corpo = corpo; this.status = init.status; this.headers = init.headers; } }
function copiaPer(nome) { if (!cache.has(nome)) cache.set(nome, new Map()); return cache.get(nome); }
const caches = {
  open: nome => Promise.resolve({
    add: url => url === "/app.js" ? Promise.reject(new TypeError("401")) : (copiaPer(nome).set(url, { ok: true, url }), Promise.resolve()),
    put: (req, r) => { copiaPer(nome).set(typeof req === "string" ? req : req.url, r); return Promise.resolve(); },
    match: req => Promise.resolve(copiaPer(nome).get(typeof req === "string" ? req : req.url)),
  }),
  match: req => { const u = typeof req === "string" ? req : req.url;
                  for (const c of cache.values()) if (c.has(u)) return Promise.resolve(c.get(u));
                  return Promise.resolve(undefined); },
  keys: () => Promise.resolve([...cache.keys()]),
  delete: n => Promise.resolve(cache.delete(n)),
};
global.fetch = () => reteSpenta ? Promise.reject(new TypeError("Failed to fetch"))
                                : Promise.resolve({ ok: true, status: 200, clone() { return this; } });
global.self = self; global.caches = caches; global.Response = Response;
new Function(testo)();
const risultati = {};
(async () => {
  // 1) installazione con una copia che manca: deve finire lo stesso e attivare il worker
  let install; eventi.install({ waitUntil: p => { install = p; } });
  await install;
  risultati.installazioneSaltata = !!self.saltata;
  risultati.copieSalvate = cache.size ? [...cache.values()][0].size : 0;
  // 2) navigazione offline con la scocca salvata: si riceve la scocca
  copiaPer(/const VERSIONE = "([^"]+)"/.exec(testo)[1]).set("/", { ok: true, scocca: true });   // nome della cache = VERSIONE di sw.js (la alza il bot)
  reteSpenta = true;
  const attesa = (req) => new Promise((ok, ko) => { const e = { request: req, respondWith: p => p.then(ok, ko) }; eventi.fetch(e); });
  risultati.offlineConScocca = await attesa({ method: "GET", url: "http://x/?vista=formazione", mode: "navigate" }).then(r => r.scocca ? "scocca" : "altro", () => "errore");
  // 3) navigazione offline senza nessuna copia: pagina «Nessuna connessione» con stato 503
  cache.clear();
  const r3 = await attesa({ method: "GET", url: "http://x/nuova", mode: "navigate" }).then(r => r, () => null);
  risultati.offlineSenzaCopia = r3 ? { stato: r3.status, testo: /Nessuna connessione/.test(r3.corpo) } : "errore";
  // 4) una risorsa (non una pagina) senza copia e senza rete: errore, niente pagina finta
  const r4 = await attesa({ method: "GET", url: "http://x/app.js", mode: "no-cors" }).then(() => "risposta", () => "errore");
  risultati.risorsaOffline = r4;
  // 5) le richieste /api/ non passano dal service worker
  let preso = false; eventi.fetch({ request: { method: "GET", url: "http://x/api/oggi", mode: "cors" }, respondWith() { preso = true; } });
  risultati.apiNonPreso = !preso;
  console.log(JSON.stringify(risultati));
})();
"""
    esito = subprocess.run(["node", "-e", prova, str(server.WEB / "sw.js")], capture_output=True, text=True, timeout=60)
    assert esito.returncode == 0, esito.stderr
    r = json.loads(esito.stdout.strip().splitlines()[-1])
    assert r["installazioneSaltata"] is True, "con una copia mancante il service worker deve comunque installarsi"
    assert r["copieSalvate"] >= 1
    assert r["offlineConScocca"] == "scocca", "una pagina senza rete deve dare la scocca salvata"
    assert r["offlineSenzaCopia"] == {"stato": 503, "testo": True}, r["offlineSenzaCopia"]
    assert r["risorsaOffline"] == "errore"
    assert r["apiNonPreso"] is True, "/api/ deve restare fuori dal service worker"


@pytest.mark.skipif(shutil.which("node") is None, reason="serve node per provare il service worker")
def test_sw_non_salva_le_pagine_con_codici_nell_indirizzo():
    """Le pagine aperte da un link con un codice (invito, ritorno da Google) passano dalla rete e non finiscono nella cache;
    una pagina normale sì, come scocca dell'app («/», la stessa pagina per ogni indirizzo): prova che il finto funziona."""
    prova = r"""
const fs = require("fs");
const testo = fs.readFileSync(process.argv[1], "utf8");
const salvate = [];
const eventi = {};
const self = { addEventListener: (t, f) => { eventi[t] = f; }, skipWaiting: () => Promise.resolve(), clients: { claim: () => Promise.resolve() },
               location: { origin: "http://x" } };
const caches = { open: () => Promise.resolve({ put: (req) => { salvate.push(typeof req === "string" ? req : req.url); return Promise.resolve(); },
                                               add: () => Promise.resolve(), match: () => Promise.resolve(undefined) }),
                 match: () => Promise.resolve(undefined), keys: () => Promise.resolve([]), delete: () => Promise.resolve(true) };
global.fetch = () => Promise.resolve({ ok: true, status: 200, clone() { return this; } });
global.self = self; global.caches = caches; global.Response = class {};
new Function(testo)();
(async () => {
  const prese = {};
  for (const url of ["http://x/?invito=CODICEPROVA", "http://x/?vista=oggi&invito=CODICEPROVA", "http://x/?social=CODICEPROVA", "http://x/?vista=oggi"]) {
    await new Promise(fatto => {
      let preso = false;
      eventi.fetch({ request: { method: "GET", url, mode: "navigate" }, respondWith: p => { preso = true; p.then(fatto, fatto); } });
      if (!preso) fatto();
      prese[url] = preso;
    });
  }
  await new Promise(r => setTimeout(r, 50));
  console.log(JSON.stringify({ salvate, prese }));
})();
"""
    esito = subprocess.run(["node", "-e", prova, str(server.WEB / "sw.js")], capture_output=True, text=True, timeout=60)
    assert esito.returncode == 0, esito.stderr
    r = json.loads(esito.stdout.strip().splitlines()[-1])
    assert not [u for u in r["salvate"] if "CODICEPROVA" in u], r["salvate"]
    assert not any(preso for u, preso in r["prese"].items() if "CODICEPROVA" in u), r["prese"]
    assert r["salvate"] == ["/"], r["salvate"]


@pytest.mark.skipif(shutil.which("node") is None, reason="serve node per provare il service worker")
def test_sw_scocca_dalla_copia_e_pagine_quando_il_server_non_c_e():
    """#654. La scocca viene dalla copia di questa versione anche con la rete buona (mai metà vecchia e metà nuova). Le altre
    pagine (Privacy...) chiedono alla rete: se il proxy risponde 502, 503 o 504 danno la copia salvata, se c'è (senza, la
    risposta com'è); senza rete e senza copia «Nessuna connessione», mai la scocca dell'app."""
    prova = r"""
const fs = require("fs");
const testo = fs.readFileSync(process.argv[1], "utf8");
const VERSIONE = /const VERSIONE = "([^"]+)"/.exec(testo)[1];
const copie = new Map();                                     // percorso -> risposta, nella cache di VERSIONE
const eventi = {};
const self = { addEventListener: (t, f) => { eventi[t] = f; }, skipWaiting: () => Promise.resolve(), clients: { claim: () => Promise.resolve() },
               location: { origin: "http://x" } };
const chiave = req => { const u = typeof req === "string" ? req : req.url; return u.startsWith("http") ? new URL(u).pathname : u; };
const caches = { open: nome => Promise.resolve({ put: () => Promise.resolve(), add: () => Promise.resolve(),
                                                 match: req => Promise.resolve(nome === VERSIONE ? copie.get(chiave(req)) : undefined) }),
                 match: () => Promise.resolve(undefined), keys: () => Promise.resolve([]), delete: () => Promise.resolve(true) };
let rete = null;                                             // la risposta della rete; null = niente rete
global.fetch = () => rete === null ? Promise.reject(new TypeError("Failed to fetch"))
                                   : Promise.resolve({ ...rete, ok: rete.status < 300, clone() { return this; } });
class Response { constructor(corpo, init) { this.corpo = corpo; this.status = init.status; } }
global.self = self; global.caches = caches; global.Response = Response;
new Function(testo)();
const chiedi = (url, mode) => new Promise((ok, ko) => eventi.fetch({ request: { method: "GET", url, mode }, respondWith: p => p.then(ok, ko) }))
  .then(r => r.da || (r.corpo && /Nessuna connessione/.test(r.corpo) ? "nessuna connessione" : String(r.status)), () => "errore");
(async () => {
  const esiti = {};
  copie.set("/", { status: 200, da: "scocca salvata" });
  copie.set("/app.js", { status: 200, da: "app.js salvato" });
  copie.set("/privacy", { status: 200, da: "privacy salvata" });
  rete = { status: 200, da: "rete" };
  esiti.appConRete = await chiedi("http://x/?vista=formazione", "navigate");
  esiti.scriptConRete = await chiedi("http://x/app.js", "no-cors");
  esiti.privacyConRete = await chiedi("http://x/privacy", "navigate");
  for (const stato of [502, 503, 504, 500]) {
    rete = { status: stato };
    esiti["privacy" + stato] = await chiedi("http://x/privacy", "navigate");
    esiti["termini" + stato] = await chiedi("http://x/termini", "navigate");
  }
  rete = null;
  esiti.terminiSenzaRete = await chiedi("http://x/termini", "navigate");
  esiti.appSenzaRete = await chiedi("http://x/?vista=formazione", "navigate");
  console.log(JSON.stringify(esiti));
})();
"""
    esito = subprocess.run(["node", "-e", prova, str(server.WEB / "sw.js")], capture_output=True, text=True, timeout=60)
    assert esito.returncode == 0, esito.stderr
    r = json.loads(esito.stdout.strip().splitlines()[-1])
    assert (r["appConRete"], r["scriptConRete"]) == ("scocca salvata", "app.js salvato"), r
    assert r["privacyConRete"] == "rete", r
    assert [r[f"privacy{s}"] for s in (502, 503, 504)] == ["privacy salvata"] * 3, r
    assert [r[f"termini{s}"] for s in (502, 503, 504)] == ["502", "503", "504"], r
    assert (r["privacy500"], r["termini500"]) == ("500", "500"), r          # un errore vero del server non si nasconde
    assert r["terminiSenzaRete"] == "nessuna connessione", r
    assert r["appSenzaRete"] == "scocca salvata", r
