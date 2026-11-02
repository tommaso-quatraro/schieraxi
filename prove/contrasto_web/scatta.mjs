// Contrasto reale del testo nella web app: apre le schermate in Chrome senza finestra, per ogni passo di scorrimento
// salva (1) l'elenco dei testi con colore, opacita e riquadro, (2) uno screenshot SENZA testo (solo il fondo vero).
// Uso: node scatta.mjs <porta-app> <cartella-uscita> [scene,separate,da,virgola] [larghezze]
import { spawn } from "node:child_process";
import { writeFileSync, mkdirSync } from "node:fs";

const [porta, uscita, scenePar, largPar] = process.argv.slice(2);
mkdirSync(uscita, { recursive: true });
const CHROME = process.env.CHROME || "C:/Program Files/Google/Chrome/Application/chrome.exe";
const DBG = 9361 + Math.floor(Math.random() * 40);
const chrome = spawn(CHROME, ["--headless=new", `--remote-debugging-port=${DBG}`, `--user-data-dir=${uscita}/profilo`, "--no-first-run", "--hide-scrollbars", "--force-color-profile=srgb", "about:blank"], { stdio: "ignore" });
const attendi = ms => new Promise(r => setTimeout(r, ms));
let lista;
for (let i = 0; i < 40; i++) { try { lista = await (await fetch(`http://127.0.0.1:${DBG}/json/list`)).json(); if (lista.length) break; } catch { } await attendi(250); }
const pagina = lista.find(x => x.type === "page");
const ws = new WebSocket(pagina.webSocketDebuggerUrl);
await new Promise(r => ws.addEventListener("open", r));
let id = 0; const attese = new Map();
ws.addEventListener("message", e => { const m = JSON.parse(e.data); if (m.id && attese.has(m.id)) { attese.get(m.id)(m); attese.delete(m.id); } });
const cdp = (method, params = {}) => new Promise(r => { const n = ++id; attese.set(n, r); ws.send(JSON.stringify({ id: n, method, params })); });
const valuta = async expr => { const r = await cdp("Runtime.evaluate", { expression: expr, awaitPromise: true, returnByValue: true }); if (r.result?.exceptionDetails) console.error("ERR", expr.slice(0, 60), JSON.stringify(r.result.exceptionDetails).slice(0, 200)); return r.result?.result?.value; };

const SCENE = {
  oggi: "vai('oggi')",
  formazione: "vai('formazione')",
  rosa: "vistaRosa()",
  diario: "apriDiario()",
  impostazioni: "vai('impostazioni')",
};
const scene = (scenePar || Object.keys(SCENE).join(",")).split(",");
const larghezze = (largPar || "390,1440").split(",").map(Number);

// Raccoglie i testi visibili nel riquadro corrente.
const RACCOGLI = `(() => {
  const H = innerHeight, W = innerWidth;
  const rad = getComputedStyle(document.documentElement);
  const sec = rad.getPropertyValue('--testo-2').trim();
  const nav = document.querySelector('.schede'); const nr = nav && getComputedStyle(nav).display !== 'none' ? nav.getBoundingClientRect() : null;
  const out = [];
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let n;
  while ((n = w.nextNode())) {
    if (!n.nodeValue.trim()) continue;
    const el = n.parentElement; if (!el) continue;
    if (el.closest('script,style,noscript,[hidden],.sr-only')) continue;
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.display === 'none') continue;
    let op = 1; for (let e = el; e; e = e.parentElement) op *= parseFloat(getComputedStyle(e).opacity);
    if (op < 0.05) continue;
    const r = document.createRange(); r.selectNodeContents(n);
    const b = r.getBoundingClientRect(); if (b.width < 2 || b.height < 2) continue;
    if (b.top < 0 || b.bottom > H || b.left < 0 || b.right > W) continue;      // solo testi interi nel riquadro
    if (nr && !(b.bottom <= nr.top || b.top >= nr.bottom || b.right <= nr.left || b.left >= nr.right)) continue;   // sotto la barra: non si legge comunque
    const foglioAperto = document.querySelector('#foglio:not([hidden])');
    if (foglioAperto && !el.closest('.foglio-corpo')) continue;                // con il foglio aperto conta solo il foglio
    const sopra = document.elementFromPoint(b.left + Math.min(b.width / 2, 6), b.top + b.height / 2);      // coperto da altro (barra, foglio, avviso)?
    if (sopra && !(el.contains(sopra) || sopra.contains(el))) continue;
    const svg = el.closest('svg') && el.namespaceURI.includes('svg');
    const col = svg ? cs.fill : cs.color;
    out.push({ ay: b.top + scrollY + (document.querySelector('.foglio-corpo') && foglioAperto ? document.querySelector('.foglio-corpo').scrollTop : 0), t: n.nodeValue.trim().slice(0, 28), c: col, op, x: b.left, y: b.top, w: b.width, h: b.height, fs: parseFloat(cs.fontSize), fw: parseInt(cs.fontWeight) || 400,
      sec: false, cls: (el.className && el.className.baseVal === undefined ? String(el.className) : '').slice(0, 40), tag: el.tagName.toLowerCase() });
  }
  return JSON.stringify({ sec, out });
})()`;

const SENZA_TESTO = `(() => { let s = document.getElementById('__nt'); if (!s) { s = document.createElement('style'); s.id='__nt'; document.head.appendChild(s); }
  s.textContent = '*,*::before,*::after{-webkit-text-fill-color:transparent!important;text-shadow:none!important;caret-color:transparent!important} svg text{fill:transparent!important} svg *{stroke-opacity:1}'; 1 })()`;
const CON_TESTO = `(() => { const s = document.getElementById('__nt'); if (s) s.textContent=''; 1 })()`;
const FERMA = `(() => { const s = document.createElement('style'); s.textContent='*,*::before,*::after{animation-play-state:paused!important;transition:none!important}'; document.head.appendChild(s); 1 })()`;

const indice = [];
for (const tema of ["light", "dark"]) {
  for (const larghezza of larghezze) {
    const altezza = larghezza < 600 ? 844 : 900;
    await cdp("Emulation.setDeviceMetricsOverride", { width: larghezza, height: altezza, deviceScaleFactor: 1, mobile: larghezza < 600 });
    await cdp("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: tema }] });
    for (const scena of scene) {
      await cdp("Page.navigate", { url: `http://127.0.0.1:${porta}/` });
      await attendi(3500);
      await valuta("localStorage.setItem('lingua','it'); 1");
      await valuta(SCENE[scena] + "; 1");
      await attendi(3500);
      await valuta(FERMA);
      const sc = scena === "diario" ? "document.querySelector('.foglio-corpo')" : "document.scrollingElement";
      const totale = await valuta(`${sc}.scrollHeight`);
      const alto = await valuta(`${sc}.clientHeight`);
      const passi = Math.min(8, Math.max(1, Math.ceil((totale - 100) / (alto - 150))));
      for (let p = 0; p < passi; p++) {
        const y = Math.min(p * (alto - 150), Math.max(0, totale - alto));
        await valuta(`${sc}.scrollTop = ${y}; 1`);
        await attendi(500);
        const dati = JSON.parse(await valuta(RACCOGLI));
        await valuta(SENZA_TESTO);
        await attendi(250);
        const shot = await cdp("Page.captureScreenshot", { format: "png" });
        await valuta(CON_TESTO);
        const base = `${scena}-${tema}-${larghezza}-${p}`;
        writeFileSync(`${uscita}/${base}.png`, Buffer.from(shot.result.data, "base64"));
        writeFileSync(`${uscita}/${base}.json`, JSON.stringify({ scena, tema, larghezza, passo: p, y, testo2: dati.sec, testi: dati.out }));
        indice.push(base);
      }
    }
  }
}
writeFileSync(`${uscita}/indice.json`, JSON.stringify(indice));
ws.close(); chrome.kill();
process.exit(0);
