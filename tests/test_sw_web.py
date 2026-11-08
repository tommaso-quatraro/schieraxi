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
               clients: { claim: () => Promise.resolve() } };
let reteSpenta = false;
class Response { constructor(corpo, init) { this.corpo = corpo; this.status = init.status; this.headers = init.headers; } }
function copiaPer(nome) { if (!cache.has(nome)) cache.set(nome, new Map()); return cache.get(nome); }
const caches = {
  open: nome => Promise.resolve({
    add: url => url === "/app.js" ? Promise.reject(new TypeError("401")) : (copiaPer(nome).set(url, { ok: true, url }), Promise.resolve()),
    put: (req, r) => { copiaPer(nome).set(typeof req === "string" ? req : req.url, r); return Promise.resolve(); },
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
