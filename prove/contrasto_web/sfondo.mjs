// Fondo sfumato vero (solo .sfondo, senza contenuto) in 4 momenti dell'animazione. Uso: node sfondo.mjs <porta-app> <cartella>
import { spawn } from "node:child_process";
import { writeFileSync, mkdirSync } from "node:fs";
const [porta, uscita] = process.argv.slice(2);
mkdirSync(uscita, { recursive: true });
const DBG = 9411 + Math.floor(Math.random() * 40);
const chrome = spawn(process.env.CHROME || "C:/Program Files/Google/Chrome/Application/chrome.exe", ["--headless=new", `--remote-debugging-port=${DBG}`, `--user-data-dir=${uscita}/profilo`, "--no-first-run", "--hide-scrollbars", "--force-color-profile=srgb", "about:blank"], { stdio: "ignore" });
const attendi = ms => new Promise(r => setTimeout(r, ms));
let lista;
for (let i = 0; i < 40; i++) { try { lista = await (await fetch(`http://127.0.0.1:${DBG}/json/list`)).json(); if (lista.length) break; } catch { } await attendi(250); }
const ws = new WebSocket(lista.find(x => x.type === "page").webSocketDebuggerUrl);
await new Promise(r => ws.addEventListener("open", r));
let id = 0; const attese = new Map();
ws.addEventListener("message", e => { const m = JSON.parse(e.data); if (m.id && attese.has(m.id)) { attese.get(m.id)(m); attese.delete(m.id); } });
const cdp = (method, params = {}) => new Promise(r => { const n = ++id; attese.set(n, r); ws.send(JSON.stringify({ id: n, method, params })); });
const valuta = async expr => (await cdp("Runtime.evaluate", { expression: expr, awaitPromise: true, returnByValue: true })).result?.result?.value;
for (const tema of ["light", "dark"]) for (const [l, a] of [[390, 844], [1440, 900]]) {
  await cdp("Emulation.setDeviceMetricsOverride", { width: l, height: a, deviceScaleFactor: 1, mobile: l < 600 });
  await cdp("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: tema }] });
  await cdp("Page.navigate", { url: `http://127.0.0.1:${porta}/` });
  await attendi(3000);
  await valuta(`(() => { const s = document.createElement('style'); s.textContent = 'body > *:not(.sfondo){display:none!important}'; document.head.appendChild(s); 1 })()`);
  for (const t of [0, 12, 24, 36, 48]) {
    await valuta(`(() => { document.querySelectorAll('.sfondo i').forEach(i => { i.style.animationPlayState='paused'; i.style.animationDelay='-${t}s'; }); 1 })()`);
    await attendi(400);
    const shot = await cdp("Page.captureScreenshot", { format: "png" });
    writeFileSync(`${uscita}/sfondo-${tema}-${l}-${t}.png`, Buffer.from(shot.result.data, "base64"));
  }
}
ws.close(); chrome.kill(); process.exit(0);
