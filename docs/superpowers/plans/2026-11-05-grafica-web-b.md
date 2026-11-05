# Piano: grafica B della web app

> **Per chi esegue:** skill obbligatoria `superpowers:subagent-driven-development` (consigliata) oppure
> `superpowers:executing-plans`, un compito alla volta. I passi usano le caselle (`- [ ]`) per segnare l'avanzamento.

**Obiettivo:** portare tutte le schermate della web app nella direzione B «Distinta», comoda sul PC e semplice al telefono,
senza cambiare testi, numeri, rotte né funzioni.

**Architettura:** HTML, CSS e JavaScript senza librerie in `fanta/web/` (come oggi). Un solo foglio di stile `stile.css`,
quindi le PR che lo toccano vanno una alla volta. Si cambia prima ciò che è comune (colori, carattere, testata, sezioni, riga
del giocatore), poi le schermate. Ogni PR unita va in produzione da sola e lascia l'app coerente.

**Strumenti:** pytest (test statici che leggono CSS, HTML e JS; alcuni girano pezzi di `app.js` con node), Playwright per
Python senza finestra per le foto, axe-core 4.14.0 (`tests/strumenti/axe/axe.min.js`), fontTools per il carattere.

**Spec:** `docs/superpowers/specs/2026-11-05-grafica-web-b-design.md` (chi esegue legge spec e piano insieme). Issue #354.

## Vincoli globali
- Nessuna funzione nuova; nessun testo cambiato in `fanta/web/testi.js` (si aggiungono solo le chiavi che il piano nomina, in
  italiano e in inglese); vocabolario di `docs/COERENZA-WEB-IPHONE.md` («gioca 85%» sempre intero, «vs PAR» / «@ UDI», «−0,4»).
- Colori (spec §7.1): chiaro `--sfondo #ffffff`, `--superficie #f4f5f2`, `--filo #dde1dc`, `--testo #10201a`, `--solido #ffffff`;
  scuro `--sfondo #121513`, `--superficie #1a1e1c`, `--filo #2e3430`, `--testo #e9edea`, `--solido #1a1e1c`. `--testo-2`, `--azione`, `--azione-testo`,
  `--verde`, `--rosso`, `--arancio`, `--blu`, `--capitano`, `--bordo-campo`, `--campo` restano i valori di oggi (legati all'iPhone
  dai test), salvo la scelta 1 dell'utente.
- Scala (spec §7.3): `--t-eroe` 56 px (72 px da 900 px), `--t-titolo` 32, `--t-card` 17, `--t-valore` 20, `--t-corpo` 15,
  `--t-sec` 13, `--t-eti` 12. Mai sotto 12 px. Raggi: `--r-in` 8 px, `--r-card` 12 px, `--r-pill` 999 px.
- Carattere dei numeri e dei titoli: `--font-numeri: "Archivo", <carattere di sistema>`, file `fanta/web/caratteri/archivo.woff2`,
  `font-display: swap`, cifre tabellari. Testo nel carattere di sistema.
- Soglie: barra in basso sotto i 900 px, schede in alto da 900 px; due colonne in Oggi e Formazione da 768 px (5:7 da 900 px);
  Squadra e Altro a due colonne da 1100 px; pannello affiancato da 1200 px; contenuto al massimo 1240 px.
- Aree di tocco 44 px; focus visibile (`:focus-visible` 2 px `--testo`, stacco 2 px) e mai coperto; nessuna `transition: all`;
  nessun `backdrop-filter` alla fine del piano; «Animazioni ridotte» e `prefers-reduced-motion` rispettati.
- axe: zero violazioni `critical` e `serious` a 390, 768, 1024 e 1440 px, in chiaro e in scuro, sulle schermate toccate.
- Firme: `pagina(html, opz)`, `vai(vista, gruppo, opz)`, `apriFoglio(html, opz)`, `voceGiocatore(x, posizione, conConfronto,
  sostituisci)`, `pedina(x, k)`: i parametri nuovi solo in fondo e facoltativi (molti test girano queste funzioni con node).
- Si tengono classi e id di oggi dove la struttura non cambia (spec §4.7). Una regola CSS che non serve più si toglie nella PR
  che la rende inutile.
- Repository pubblico: niente dati veri; foto fuori dal repository (le pagine mostrano nomi di calciatori veri); nelle PR solo
  misure ed esito di axe, oppure foto con nomi inventati.
- Ogni PR che tocca `fanta/` aggiunge un file `fanta/novita.d/<nome>.json` (voci senza «PC», senza nomi di file).

## Attenzione in revisione
Casi che la spec non nomina e che un utente incontrerà; ognuno ha il suo controllo nel compito indicato.
1. **Nomi lunghi e inglese** a 320-390 px (righe, linguette, pulsanti, «Altro ▾»): niente «…», si va a capo
   (compiti 6.1, 4.1: foto a 390 px in inglese oltre che in italiano).
2. **Testo «Molto grande» o zoom al 200%** (pagina sotto i 320 px): le regole della «Pagina strettissima» valgono per i
   componenti nuovi (`tests/test_riflusso_web.py`, aggiornato in 4.1, 6.1, 8.1).
3. **Giornata chiusa, in corso, finita, partita rinviata**: righe con «–», fantavoto preso, «Rinviata» al posto di
   «gioca N%»; le colonne restano allineate (compiti 6.1 e 8.1: scena «giornata in corso» nelle foto se i dati la danno,
   altrimenti test con node su `voceGiocatore` con `stato_partita`).
4. **Finestra ristretta sotto i 1200 px con il pannello aperto** e poi riallargata: il pannello passa a foglio modale e torna
   affiancato, il focus non si perde (compito 9.1).
5. **Carattere non arrivato** (prima visita senza rete, account accesi prima dell'accesso): la pagina d'accesso non fa errori
   401 e le colonne restano allineate con il carattere di sistema (compiti 2.1 e 4.1).

## Scelte per l'utente (dalla spec, §18)
1. **Colore delle azioni nel tema chiaro**: (a) oliva `#526600` di oggi [consigliata, vale finché non risponde];
   (b) verde bosco `#0B6B3A` solo sulla web; (c) verde bosco su web e iPhone. Se (b) o (c): compito 3.2 (e PR iOS-1 per la c).
2. **Volti sul campo**: come la prova B (numero nel disco, niente volto) [vale finché non risponde] o volto da 40 px con il
   numero sotto. Si decide prima della PR 8.
3. **Sito di presentazione** nello stesso stile: issue a parte, fuori da questo piano.

## Ordine delle PR e lavoro in parallelo
| PR | Titolo | Area e file principali | Dipende da | In parallelo con |
|---|---|---|---|---|
| 1 | Foto e axe senza finestra | `prove/foto_web/`, `tests/` | – | PR 2 |
| 2 | Carattere Archivo servito dal server | `fanta/web/caratteri/`, `fanta/rotte_account.py`, `fanta/server.py`, `fanta/web/sw.js`, `fanta/testi_legali.py`, `script/`, `THIRD-PARTY-NOTICES.md` | – | PR 1, PR 3 |
| 3 | Colori e fondo neutri | `stile.css` (solo i temi), `index.html` (colore della barra), `manifest.webmanifest` | PR 1 | PR 2 |
| 4 | Testata, schede, titolo della pagina, Indietro | `index.html`, `stile.css`, `app.js`, `sw.js` | PR 2, PR 3 | – |
| 5 | Sezioni, pulsanti, etichette, avvisi | `stile.css` | PR 4 | – |
| 6 | Riga del giocatore e colonne di numeri | `app.js`, `stile.css`, `docs/COERENZA-WEB-IPHONE.md` | PR 5 | – |
| 7 | Oggi | `app.js`, `dafare.js`, `live.js`, `stile.css` | PR 6 | – |
| 8 | Formazione (campo, colonne, Ctrl+S) | `app.js`, `stile.css`, documenti | PR 7 | – |
| 9 | Pannello affiancato, scheda, ricerca | `app.js`, `stile.css`, `index.html` | PR 8 | – |
| 10 | Squadra | `app.js`, `anteprima.js`, `stile.css` | PR 9 | – |
| 11 | Altro | `app.js`, `stile.css` | PR 10 | – |
| 12 | Impostazioni, accesso, primo avvio, pulizia e documenti | `impostazioni.js`, `primoavvio.js`, `app.js`, `stile.css`, `docs/` | PR 11 | – |
| iOS-1 | Solo se scelta 1c: colore delle azioni su web e iPhone (compito 3.2 + iOS, una PR mista) | `stile.css`, `ios/Sources/Support/Aspetto.swift`, `ios/Sources/Support/Design/Tema.swift` | PR 3 e risposta dell'utente | – (prima della PR 4) |

Da PR 4 a PR 12 tutte toccano `stile.css` e `app.js`: una alla volta, nell'ordine. Le PR 1, 2 e 3 toccano file diversi tra loro
(PR 3 parte quando PR 1 è unita, perché le sue foto «prima» usano lo strumento). Tetto: al massimo 4 PR aperte per server e
web (`REGOLE.md` §1); questo piano ne tiene aperte al massimo 2 insieme.

## Procedura comune a ogni PR
1. `git fetch origin && git switch -c <ramo> origin/main` nella propria worktree; leggi spec e piano.
2. **Foto «prima»**, prima di toccare qualsiasi file: server di prova come in `collaudo-web` (dalla worktree,
   `<cartella principale del repository>\.venv\Scripts\python.exe -m fanta server --porta 80NN` con la lega d'esempio, PID
   annotato), poi `<venv-playwright>\Scripts\python.exe prove\foto_web\foto.py http://127.0.0.NN:80NN <scratchpad>\foto-prNN\prima --scene <scene della PR>`.
   Nessuna finestra: lo strumento usa sempre Chrome senza finestra.
3. Per ogni compito: test che fallisce → visto fallire → codice → test che passa → commit (`git status` e `git diff --staged`
   prima). Un test che fissa una regola che la PR toglie si riscrive per lo stesso scopo e si vede fallire prima del cambio
   (spec §15.1). Trova i test toccati con `grep -ln "<selettore o funzione>" tests/*.py`.
4. **Foto «dopo»** con lo stesso comando in `...\dopo`; guarda davvero almeno 390 e 1440 px, chiaro e scuro, delle scene della
   PR; `riepilogo.txt` con `gravi=0` e `scorrimento-di-lato=no` ovunque. Ferma il server per PID.
5. Suite intera una volta: `<cartella principale del repository>\.venv\Scripts\python.exe -m pytest -q` verde.
6. PR **in bozza** verso `main`, descrizione dal modello (`Aree: …`), «Parte di #354», cosa hai guardato e a che larghezza, esito
   di axe, misure chieste dal «fatto quando». Niente `gh pr ready`, niente unione.
7. Compito iPhone della PR: indicato in ogni PR. Se trovi una differenza di testi o numeri con l'iPhone: issue «coerenza: …».

---

## PR 1: Foto e axe senza finestra
Area: `prove/foto_web/`, `tests/`, `MAPPA.md`. Niente file di novità (non tocca `fanta/`).

### Compito 1.1: strumento `prove/foto_web/foto.py`
**File:**
- Crea: `prove/foto_web/foto.py`, `prove/foto_web/LEGGIMI.md`
- Crea: `tests/test_foto_web.py`
- Modifica: `MAPPA.md` (una riga in «`prove/`»)

**Interfacce:**
- Produce: `python prove/foto_web/foto.py <indirizzo> <cartella> [--scene a,b] [--larghezze 390,768,1024,1440] [--temi chiaro,scuro] [--lingua it|en]`.
  Per ogni scena, larghezza e tema scrive `<scena>-<larghezza>-<tema>.png` (pagina intera) e `axe-<scena>-<larghezza>-<tema>.json`
  (violazioni di axe con regole `wcag2a`, `wcag2aa`, `wcag21aa`, `wcag22aa`), e una riga in `riepilogo.txt`:
  `<scena> <larghezza> <tema> gravi=<n> scorrimento-di-lato=<sì|no> errori-console=<n>`. Esce con 1 se `gravi` > 0.
- Scene (espressioni JavaScript lanciate nella pagina dopo il caricamento, come `SCENE` di `prove/contrasto_web/scatta.mjs`):
  `oggi`, `formazione`, `squadra`, `elenco` (Squadra > Elenco dei giocatori), `rosa`, `scheda` (scheda del primo titolare),
  `altro`, `diario`, `regole`, `scambi`, `impostazioni`. Prima della foto aspetta che `#contenuto` non contenga `.caricamento`.

- [ ] **Passo 1: test che fallisce** in `tests/test_foto_web.py`

```python
"""Lo strumento delle foto della web (prove/foto_web/foto.py): mai una finestra, axe del repository, foto fuori dal repository."""
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
FOTO = (RADICE / "prove" / "foto_web" / "foto.py").read_text(encoding="utf-8")


def test_foto_senza_finestra_con_chrome_di_sistema():
    assert "headless=True" in FOTO and "headless=False" not in FOTO
    assert 'channel="chrome"' in FOTO


def test_axe_del_repository_e_tutte_le_larghezze_e_i_temi():
    assert "tests/strumenti/axe/axe.min.js" in FOTO.replace("\\", "/")
    for larghezza in ("390", "768", "1024", "1440"):
        assert larghezza in FOTO
    assert 'color_scheme="light"' in FOTO and 'color_scheme="dark"' in FOTO


def test_le_foto_non_finiscono_nel_repository():
    assert "def fuori_dal_repository(" in FOTO           # rifiuta una cartella di uscita dentro il repository
```

- [ ] **Passo 2:** `<cartella principale del repository>\.venv\Scripts\python.exe -m pytest -q tests\test_foto_web.py` → FAIL
  (`FileNotFoundError`).
- [ ] **Passo 3:** scrivi `foto.py` sullo scheletro di `collaudo-web` (Playwright per Python 1.64.1 in un venv nello
  scratchpad, `launch_persistent_context(profilo, channel="chrome", headless=True, viewport=…)`, tema con
  `pagina.emulate_media(color_scheme="light"|"dark")`, axe con `pagina.add_script_tag(path=…)` e `axe.run`). `fuori_dal_repository(cartella)`
  esce con un messaggio se la cartella sta dentro la radice del repository. `LEGGIMI.md`: come si installa il venv, il comando,
  cosa vuol dire il riepilogo, perché le foto non vanno nel repository.
- [ ] **Passo 4:** test → PASS. Prova vera: server di prova e `foto.py … --scene oggi --larghezze 390 --temi chiaro`;
  il file PNG esiste e `riepilogo.txt` ha una riga. Nessuna finestra comparsa.
- [ ] **Passo 5: commit** `git commit -m "Strumento per foto e axe della web senza finestra"`.

**Fatto quando:** il comando fa le foto di tutte le scene a 4 larghezze e 2 temi senza aprire finestre e scrive il riepilogo;
le foto restano nello scratchpad. Compito iPhone: nessuno.

---

## PR 2: Carattere Archivo servito dal server
Area: `fanta`, `script`, `tests`, `THIRD-PARTY-NOTICES.md`, `MAPPA.md`. Nessuna schermata cambia ancora (il CSS lo usa dalla PR 4):
niente foto, axe non serve.

### Compito 2.1: file del carattere e server
**File:**
- Crea: `script/carattere_web.py`, `fanta/web/caratteri/archivo.woff2`, `fanta/web/caratteri/OFL.txt` (copia di
  `assets/marchio/wordmark/OFL.txt`)
- Modifica: `fanta/rotte_account.py:34` (`STATICI_PREFISSI` con `"/caratteri/"`), `fanta/server.py` (prima di `app.mount`:
  `mimetypes.add_type("font/woff2", ".woff2")`), `fanta/web/sw.js:4` (`FILE` con `"/caratteri/archivo.woff2"`)
- Crea: `tests/test_carattere_web.py`

**Interfacce:**
- Produce: `/caratteri/archivo.woff2` (pubblico anche con gli account accesi, tipo `font/woff2`), usato dalla PR 4.
- `script/carattere_web.py <Archivo[wdth,wght].ttf>`: istanza `wdth=87.5 wght=400:700` (`fontTools.varLib.instancer`),
  sottoinsieme con le lettere di spec §16, `--flavor=woff2 --layout-features+=tnum,lnum --name-IDs='*'`; stampa
  `byte=<n> tnum=<sì|no> licenza=<sì|no>` ed esce con 1 se manca `tnum` nel GSUB o il nome 13 (licenza). Si lancia in un venv
  a parte (`pip install fonttools brotli`), come `assets/marchio/wordmark/genera.py`: non entra in `requirements*.txt`.

- [ ] **Passo 1: test che fallisce** in `tests/test_carattere_web.py`

```python
"""Il carattere dei numeri (Archivo, SIL OFL 1.1) servito dal nostro server: piccolo, con la licenza, pubblico, offline."""
import json
import re

import pytest
from fastapi.testclient import TestClient

from fanta import rotte_account, server

WEB = server.WEB


@pytest.fixture
def client():
    return TestClient(server.app, headers={"X-Fanta": "1"})


def test_woff2_piccolo_con_la_licenza_accanto():
    f = WEB / "caratteri" / "archivo.woff2"
    assert f.read_bytes()[:4] == b"wOF2" and f.stat().st_size <= 80_000
    ofl = (WEB / "caratteri" / "OFL.txt").read_text(encoding="utf-8")
    assert "SIL OPEN FONT LICENSE Version 1.1" in ofl and "The Archivo Project Authors" in ofl


def test_il_server_lo_da_con_il_tipo_giusto_anche_prima_dell_accesso(client):
    r = client.get("/caratteri/archivo.woff2")
    assert r.status_code == 200 and r.headers["content-type"].startswith("font/woff2")
    assert rotte_account._pubblico("/caratteri/archivo.woff2") and rotte_account._pubblico("/caratteri/OFL.txt")


def test_il_carattere_sta_nella_scocca_offline():
    sw = (WEB / "sw.js").read_text(encoding="utf-8")
    assert "/caratteri/archivo.woff2" in json.loads(re.search(r"const FILE = (\[.*?\]);", sw).group(1))
```

- [ ] **Passo 2:** `… -m pytest -q tests\test_carattere_web.py` → FAIL (file mancante).
- [ ] **Passo 3:** scarica `ofl/archivo/Archivo[wdth,wght].ttf` da `google/fonts` (annota nel commit e nella PR il commit di
  google/fonts e lo SHA-256 del file, `Get-FileHash -Algorithm SHA256`) in una cartella nuova dello scratchpad; lancia
  `script/carattere_web.py`; deve stampare `tnum=sì licenza=sì`. Se `tnum` manca in Archivo: fermati e scrivi BLOCCATO
  (la spec chiede cifre tabellari). Poi le tre modifiche al server.
- [ ] **Passo 4:** test → PASS; anche `tests\test_sw_web.py` e `tests\test_sicurezza_accesso.py` → PASS.
- [ ] **Passo 5: commit** `git commit -m "Carattere Archivo per i numeri, servito dal server"` (scrivi i byte del file nel messaggio).

### Compito 2.2: licenza visibile
**File:** `script/avvisi_terze_parti.py` (testo su Archivo: ora la web serve un sottoinsieme del carattere, in
`fanta/web/caratteri/`, con la licenza accanto) e `THIRD-PARTY-NOTICES.md` rigenerato con lo script; `fanta/testi_legali.py`
(una voce in «Programmi aperti» di `crediti`, italiano e inglese: «Il carattere Archivo per numeri e titoli: licenza SIL Open
Font License 1.1.» / «The Archivo typeface for numbers and titles: SIL Open Font License 1.1.»); `MAPPA.md` (riga
`fanta/web/caratteri/`); `fanta/novita.d/carattere-archivo.json`; test in `tests/test_carattere_web.py`.

- [ ] **Passo 1: test che fallisce**

```python
def test_crediti_e_avvisi_citano_archivo(client):
    for lingua in ("it", "en"):
        assert "Archivo" in client.get(f"/crediti?lingua={lingua}").text
    avvisi = (server.WEB.parent.parent / "THIRD-PARTY-NOTICES.md").read_text(encoding="utf-8")
    assert "fanta/web/caratteri/" in avvisi
```
  (Prima di scriverlo controlla in `fanta/server.py` come la pagina `/crediti` sceglie la lingua e usa lo stesso parametro.)
- [ ] **Passo 2:** FAIL. **Passo 3:** testi e rigenerazione. **Passo 4:** PASS, più `tests\test_avvisi_terze_parti.py` e
  `tests\test_legale.py`. **Passo 5: commit** `"Crediti e avvisi: il carattere Archivo della web"`.

Novità: `{"titolo": "Un carattere per i numeri", "voci": ["Prepara il nuovo carattere dei numeri dell'app web: per ora non cambia niente sullo schermo."], "tecnico": ["Archivo (SIL OFL 1.1) in fanta/web/caratteri, pubblico anche con gli account, tipo font/woff2, nella cache offline."]}`

**Fatto quando:** `/caratteri/archivo.woff2` risponde 200 `font/woff2` anche senza accesso, il file pesa al più 80 KB (obiettivo
60 KB, misura nella PR), licenza nel file e accanto, crediti e avvisi aggiornati. Compito iPhone: nessuno.

---

## PR 3: Colori e fondo neutri
Area: `fanta/web`, `tests`. Scene delle foto: `oggi`, `formazione`, `scheda`, `impostazioni`.

### Compito 3.1: temi
**File:** `fanta/web/stile.css:9-110` (i tre blocchi dei temi; `.vetro`, `.carta` solo nei colori), `fanta/web/index.html:8`,
`fanta/web/manifest.webmanifest:12-13`, `tests/test_design_web.py`, `tests/test_stile_senza_ai_web.py`,
`fanta/novita.d/colori-neutri.json`.

**Interfacce:** produce `--superficie` e `--filo` nei tre blocchi (scuro, chiaro di sistema, chiaro a mano, con gli stessi
valori nei due chiari); `--vetro` e `--vetro-carta` diventano `var(--sfondo)`; nessun `backdrop-filter`.

- [ ] **Passo 1: test che fallisce** (in `tests/test_design_web.py`, che ha già `_temi()` e `_variabili()`)

```python
def test_fondo_neutro_superficie_e_filo_della_grafica_b():
    t = _temi()
    assert (t["chiaro"]["--sfondo"], t["scuro"]["--sfondo"]) == ("#ffffff", "#121513")
    assert (t["chiaro"]["--superficie"], t["scuro"]["--superficie"]) == ("#f4f5f2", "#1a1e1c")
    assert (t["chiaro"]["--filo"], t["scuro"]["--filo"]) == ("#dde1dc", "#2e3430")
    assert t["scuro"]["--testo"] == "#e9edea" and "#eaf3ee" not in CSS        # niente fondo menta
    assert t["scuro"]["--solido"] == "#1a1e1c"
    sistema = _variabili(CSS.split("@media (prefers-color-scheme: light) {")[1].split("}")[0])
    for nome in ("--sfondo", "--superficie", "--filo"):
        assert sistema[nome] == t["chiaro"][nome], nome


def test_colore_della_barra_del_browser_segue_il_tema():
    html = (server.WEB / "index.html").read_text(encoding="utf-8")
    assert '<meta name="theme-color" media="(prefers-color-scheme: light)" content="#ffffff">' in html
    assert '<meta name="theme-color" media="(prefers-color-scheme: dark)" content="#121513">' in html
    man = json.loads((server.WEB / "manifest.webmanifest").read_text(encoding="utf-8"))
    assert man["background_color"] == man["theme_color"] == "#121513"
```
  e in `tests/test_stile_senza_ai_web.py`:
```python
def test_superfici_piene_senza_sfocatura():
    assert "backdrop-filter" not in CSS
```
- [ ] **Passo 2:** FAIL. **Passo 3:** valori di spec §7.1; via `backdrop-filter` (anche `.foglio-sfondo`). In
  `test_tema_chiaro_azioni_in_oliva_con_contrasto_sufficiente_su_ogni_superficie` i fondi scritti a mano (`#eaf3ee`) diventano
  quelli nuovi (`#ffffff`, `#f4f5f2`). I test esistenti sul
  contrasto (`test_pillole_dei_giocatori_almeno_4_5_su_ogni_fondo_in_chiaro_e_scuro`, `test_bordo_dei_campi_almeno_3_a_1…`,
  `tests/test_accessibilita.py`) devono passare senza cambiarli: misurano i fondi nuovi.
- [ ] **Passo 4:** PASS e suite intera. Foto «dopo» e axe.
- [ ] **Passo 5: commit** `"Web: fondo bianco e grigio scuro neutri, niente sfocatura"`.

### Compito 3.2 (solo con la scelta 1b o 1c dell'utente)
`--azione` chiaro `#0b6b3a` e `--azione-2` più scuro; `test_colori_semantici_come_su_ios` e
`test_tema_chiaro_azioni_in_oliva…` riscritti sul valore nuovo (contrasti 6,6:1 sul bianco, bianco sopra 6,6:1). Con la
scelta 1b: in una PR web dopo la PR 3, e `test_pulsanti_pieni_almeno_4_5_e_uguali_su_web_e_ios` smette di confrontare il
chiaro con `Aspetto.swift` (lo scuro resta legato). Con la 1c: dentro la PR iOS-1 (in fondo al piano).

**Fatto quando:** nessun fondo menta né verde scuro; nessuna sfocatura; axe a zero gravi su `oggi`, `formazione`, `scheda`,
`impostazioni`; foto guardate a 390 e 1440 in chiaro e scuro. Compito iPhone: nessuno (i colori legati non cambiano).

---

## PR 4: Testata, schede, titolo della pagina, Indietro
Area: `fanta/web`, `tests`, `docs/GUIDA-UTENTE.md`. Scene: tutte. Larghezze 390, 768, 1024, 1440; anche `--lingua en` a 390.

### Compito 4.1: testata unica e schede come collegamenti
**File:** `fanta/web/index.html:20-80`, `fanta/web/stile.css` (sezioni «testata» e «barra in basso», «Schermi larghi»),
`fanta/web/app.js` (gestori delle schede: righe ~517 e ~1907; `vai()`), `fanta/web/sw.js` (colori della pagina
«Nessuna connessione»: fondo `#121513`, testo `#e9edea`, pulsante `#3ddc97` con scritta `#04301c`),
`tests/test_grafica_b_web.py` (nuovo), test esistenti da riscrivere: `tests/test_design_web.py`
(`test_barra_in_basso…`, `test_pulsanti_link_e_azioni…` sulla scheda attiva, `test_composizione_a_colonne…`),
`tests/test_focus_bersagli_web.py`, `tests/test_riflusso_web.py` (testata e barra sotto i 320 px).

**Interfacce:**
- Produce: in `index.html` `<header class="testata">` con dentro, in ordine, `<a class="marchio" href="/?vista=oggi">` (SVG
  `#wm-c` copiato da `sito/index.html`), `<nav class="schede">` con `<a class="scheda" data-vista="…" href="/?vista=…">`,
  `<input type="search" id="campo-cerca">` con `aria-label` da `shell.cerca` e `<kbd aria-hidden="true">/</kbd>`, i pulsanti
  `#bottone-cerca` (solo sotto i 900 px), `#bottone-impostazioni`, `#bottone-aggiorna`.
- Produce: `--alto-ferma` (0 sotto i 900 px; da 900 px l'altezza vera della testata, come `--alto-testata`), usato da 8.1 e 10.1.
- `vai(vista, gruppo, opz = {})`: scrive `history.pushState({ vista, gruppo }, "", <indirizzo>)` tranne con `opz.daCronologia`;
  `window.addEventListener("popstate", ev => vai(ev.state?.vista || "oggi", ev.state?.gruppo, { daCronologia: true }))`.
  Se `lasciaFormazione()` dice di restare, `history.pushState` rimette l'indirizzo della Formazione.
- Clic su una `.scheda` senza Ctrl, ⌘, Maiusc né clic centrale: `preventDefault()` e `vai()`; con quei tasti decide il browser.
- `apriRicerca(testo = "")` (oggi senza parametri, ~2546): apre la ricerca di oggi con il testo già scritto. Il campo
  `#campo-cerca` della testata, al primo tasto scritto o con Invio, chiama `apriRicerca(campo.value)` e si svuota: così la ricerca
  funziona già da questa PR (la PR 9 sposta i risultati nel pannello affiancato).
- `main`: una colonna, al massimo 1240 px, margini 32 px da 900 px. Via la griglia a 2-4 colonne di `main` (regole a 1100, 1700,
  3200 px) e il margine `--lato`; restano `.colonne` (Oggi, Formazione), le griglie interne di Mercato e Scambi e i gradini di `--z`.

- [ ] **Passo 1: test che falliscono** in `tests/test_grafica_b_web.py`

```python
"""Grafica B della web (spec docs/superpowers/specs/2026-11-05-grafica-web-b-design.md): controlli sul codice."""
import re
from pathlib import Path

from fanta import server

WEB = server.WEB
RADICE = WEB.parent.parent
HTML = (WEB / "index.html").read_text(encoding="utf-8")
CSS = (WEB / "stile.css").read_text(encoding="utf-8")
APP = (WEB / "app.js").read_text(encoding="utf-8")


def _funzione(testo, nome):
    """Il corpo di una funzione di primo livello («function nome(» o «async function nome(») fino alla graffa che la chiude."""
    i = re.search(rf"\n(?:async )?function {nome}\(", testo).start()
    return testo[i:testo.index("\n}\n", i)]


def test_una_sola_nav_nella_testata_con_le_schede_come_collegamenti():
    assert HTML.count("<nav") == 1 and HTML.index("<nav") < HTML.index("</header>")
    for v in ("oggi", "formazione", "squadra", "altro"):
        assert f'<a class="scheda" data-vista="{v}" href="/?vista={v}"' in HTML


def test_testata_senza_h1_e_nome_disegnato_uguale_al_sito():
    testata = HTML[HTML.index("<header"):HTML.index("</header>")]
    assert "<h1" not in testata
    simbolo = lambda t: re.search(r'<symbol id="wm-c".*?</symbol>', t, re.S).group(0)
    assert simbolo(HTML) == simbolo((RADICE / "sito" / "index.html").read_text(encoding="utf-8"))


def test_ricerca_sempre_aperta_sul_pc_e_che_funziona_subito():
    assert re.search(r'<input type="search" id="campo-cerca"[^>]*data-t-aria="shell.cerca"', HTML)
    assert re.search(r"@media \(min-width: 900px\) \{[^@]*#bottone-cerca \{ display: none; \}", CSS)
    assert re.search(r'function apriRicerca\(testo = ""\)', APP)
    assert re.search(r'\$\("#campo-cerca"\)\.addEventListener\("(?:input|keydown)"', APP)


def test_pagina_larga_al_massimo_1240_px_senza_griglia_di_carte():
    assert re.search(r"\nmain \{[^}]*max-width: 1240px", CSS)
    assert not re.search(r"main \{[^}]*grid-template-columns: repeat\(", CSS)


def test_indietro_del_browser_torna_alla_schermata_di_prima():
    corpo = _funzione(APP, "vai")
    assert "history.pushState" in corpo and "daCronologia" in corpo
    assert 'addEventListener("popstate"' in APP


def test_niente_pillola_verticale_ne_lente_sul_pc():
    assert "translateY(-50%)" not in CSS and ".lente" not in CSS and "--lato" not in CSS
```
- [ ] **Passo 2:** FAIL. **Passo 3:** HTML, CSS (spec §6 e §8.1: barra piena in basso con filo e linea di 3 px sulla voce
  attiva; testata da 56 px ferma da 900 px; al telefono testata in posizione assoluta in alto a destra, non ferma), JS.
  `test_focus_bersagli_web.py` e `test_riflusso_web.py`: riscrivi le asserzioni sulla testata per le regole nuove con lo stesso
  scopo (focus mai sotto testata e barra; sotto i 320 px barra con le sole icone e niente scorrimento di lato).
- [ ] **Passo 4:** PASS, suite intera. Prova con Playwright senza finestra: da Oggi a Formazione e `pagina.go_back()` →
  di nuovo Oggi; Ctrl+clic su «Formazione» apre una seconda pagina del browser.
- [ ] **Passo 5: commit** `"Web: testata con le schede in alto sul PC, barra piena al telefono, Indietro del browser"`.

### Compito 4.2: titolo della schermata e riga di stato
**File:** `fanta/web/app.js` (`pagina()` riga ~253, `caricaInfo()` riga ~595), `fanta/web/impostazioni.js` (passa
`{ titolo: t("shell.impostazioni") }`), `fanta/web/stile.css`, `tests/test_grafica_b_web.py`.

**Interfacce:** `pagina(html, opz = {})` con `opz.titolo?: string` (senza: `t("nav." + SCHEDA_DI(stato.vista))`) e
`opz.stato?: false` (niente riga di stato). Scrive prima del contenuto
`<header class="capo-pagina"><h1 id="titolo-pagina">…</h1><p class="stato-pagina">…</p></header>`. La riga di stato è
`[stemma 20 px] Giornata N · <nome della squadra> · <dati del …>` con le chiavi di oggi (`testata.giornata`, `testata.dati_del`,
`testata.mai`, `testata.offline`); i dati li prepara `caricaInfo()` in `stato.rigaStato`.

- [ ] **Passo 1: test che fallisce**

```python
def test_ogni_schermata_ha_il_suo_titolo_h1_e_la_riga_di_stato():
    corpo = _funzione(APP, "pagina")
    assert 'class="capo-pagina"' in corpo and '<h1 id="titolo-pagina"' in corpo and 'class="stato-pagina"' in corpo
    assert 't("nav." + ' in corpo and "opz.titolo" in corpo
    assert 'testata.giornata", { n: ' in APP and "_lega" in APP[APP.index('testata.giornata", { n: '):][:120]
    for nome in ("vistaNovita", "vistaRosa"):                  # pagine dentro Altro e Squadra: il loro titolo, non quello della scheda
        assert "titolo:" in _funzione(APP, nome), nome
```
- [ ] **Passo 2:** FAIL. **Passo 3:** codice; le pagine dentro Squadra e Altro disegnate con `pagina()` passano il loro titolo
  (`opz.titolo`); quelle che si aprono nel foglio (Diario) hanno già il loro `h2`.
  `tests/test_coerenza_web.py::test_giornata_della_lega_dappertutto` deve restare verde senza cambiarlo.
- [ ] **Passo 4:** PASS. **Passo 5: commit** `"Web: titolo della schermata e riga di stato in cima alla pagina"`.

### Compito 4.3: carattere dei numeri e dei titoli, scala nuova
**File:** `fanta/web/stile.css` (`@font-face`, `--font-numeri`, valori `--t-*` di spec §7.3, `.grande`, `.enorme`,
`#titolo-pagina`, numeri in `.valore`, `.partita .pt`), `fanta/web/index.html` (`<link rel="preload" href="caratteri/archivo.woff2" as="font" type="font/woff2" crossorigin>`),
`docs/GUIDA-UTENTE.md` (riga «Da tastiera», aggiungi: «Indietro del browser torna alla schermata di prima»),
`fanta/novita.d/testata-schede.json`.

- [ ] **Passo 1: test che fallisce**

```python
def test_numeri_e_titoli_in_archivo_dal_nostro_server_con_ripiego():
    assert re.search(r'@font-face \{[^}]*font-family: "Archivo";[^}]*src: url\("caratteri/archivo\.woff2"\) format\("woff2"\);[^}]*font-display: swap;', CSS)
    assert re.search(r'--font-numeri: "Archivo", [^;]*system-ui', CSS)
    assert '<link rel="preload" href="caratteri/archivo.woff2" as="font" type="font/woff2" crossorigin>' in HTML
    assert re.search(r"#titolo-pagina \{[^}]*font-family: var\(--font-numeri\)", CSS)


def test_scala_della_grafica_b():
    for valore in ("--t-eroe: 56px", "--t-titolo: 32px", "--t-card: 17px", "--t-valore: 20px", "--t-corpo: 15px",
                   "--t-sec: 13px", "--t-eti: 12px"):
        assert valore in CSS, valore
    assert re.search(r"@media \(min-width: 900px\) \{[^@]*--t-eroe: 72px", CSS)
```
  `tests/test_design_web.py::test_scala_tipografica_a_sette_livelli…` resta verde senza cambiarlo (7 nomi, mai sotto 12 px).
- [ ] **Passo 2-4:** FAIL, codice, PASS. Foto «dopo» di tutte le scene; in console nessun 404 né 401 per il carattere.
- [ ] **Passo 5: commit** `"Web: numeri e titoli nel carattere Archivo"`.

Novità: `{"titolo": "Nuova testata", "voci": ["Su schermi larghi le sezioni stanno in alto, con la ricerca sempre aperta.", "Il tasto Indietro del browser torna alla schermata di prima.", "Ogni schermata ha il suo titolo in cima."], "tecnico": ["Una sola nav con collegamenti ?vista=, history.pushState/popstate, pagina() scrive h1 e riga di stato, @font-face Archivo."]}`

**Fatto quando:** a 1440 px le schede stanno in alto con la linea sotto quella attiva e la ricerca aperta; a 390 px barra piena
in basso e titolo della schermata in cima; Indietro torna alla scheda di prima; nessun `h1` in testata; axe a zero gravi su
tutte le scene; nessuno scorrimento di lato a 320 px. Compito iPhone: nessuno (la web prende il titolo della schermata come
l'iPhone, `docs/DESIGN.md` incoerenza 15: segnala «fatto» in quel documento nella PR 12).

---

## PR 5: Sezioni, pulsanti, etichette, avvisi
Area: `fanta/web`, `tests`. Scene: tutte. Tutte le schermate perdono le carte nello stesso momento (spec §15.3).

### Compito 5.1: la carta diventa una sezione
**File:** `fanta/web/stile.css` (`.carta`, `.carta h2`, `.carta h3`, `.carta.hero`, densità compatta), `tests/test_grafica_b_web.py`,
`tests/test_design_web.py` (`test_accesso_e_primo_avvio_centrati` resta: la pagina d'accesso è un modulo centrato).

- [ ] **Passo 1: test che fallisce**

```python
def test_la_carta_e_una_sezione_senza_scatola():
    regola = re.search(r"\n\.carta \{([^}]*)\}", CSS).group(1)
    assert "background: none" in regola and "border: 0" in regola and "border-radius" not in regola
    assert re.search(r"\.carta h2 \{[^}]*border-bottom: 2px solid var\(--testo\)", CSS)
    assert "--r-card: 12px" in CSS and ".col > * { animation: entra" not in CSS   # raggio del campo; niente entrata delle colonne
```
- [ ] **Passo 2-4:** FAIL, CSS, PASS. Nelle foto la proposta di uno scambio resta un blocco riconoscibile (filo intorno o
  spazio), l'unico posto dove un riquadro raggruppa davvero (spec §8.3).
- [ ] **Passo 5: commit** `"Web: sezioni con titolo e filo al posto delle carte"`.

### Compito 5.2: pulsanti, controlli di scelta, focus e passaggio del mouse
**File:** `fanta/web/stile.css` (`.bottone`, `.bottone.secondario`, nuova `.azione-testo`, `.chip`, `.chip.attiva`, `.segmenti`,
`button:active`, `.voce:active`, `.voce:hover`, `:focus-visible`), test in `tests/test_grafica_b_web.py` e `tests/test_design_web.py`
(`test_la_scelta_attiva_e_lime_con_testo_scuro` resta e si aggiunge il bordo).

**Interfacce:** produce la classe `.azione-testo` (pulsante di solo testo nel colore delle azioni, almeno 44×44 px), usata da
7.1, 8.1, 10.1.

- [ ] **Passo 1: test che fallisce**

```python
def test_pulsanti_piatti_scelta_con_bordo_e_niente_pressione():
    assert re.search(r"\.bottone \{[^}]*border-radius: var\(--r-in\)", CSS) and "--r-in: 8px" in CSS
    assert re.search(r"\.azione-testo \{[^}]*min-height: 44px;[^}]*min-width: 44px;[^}]*color: var\(--azione\)", CSS)
    assert re.search(r"\.chip\.attiva \{[^}]*border: 2px solid var\(--testo\)", CSS)    # il lime chiaro da solo è 2,8:1
    assert "scale(.95)" not in CSS and "scale(.985)" not in CSS


def test_focus_nel_colore_del_testo_e_riga_sotto_il_mouse():
    assert re.search(r"\n:focus-visible \{ outline: 2px solid var\(--testo\); outline-offset: 2px; \}", CSS)
    assert re.search(r"\.campo :focus-visible \{[^}]*outline-color: #fff", CSS)            # sul campo verde il focus è bianco
    assert re.search(r"\.voce:hover \{[^}]*background: var\(--superficie\)", CSS)
```
- [ ] **Passo 2-5:** FAIL, CSS, PASS, commit `"Web: pulsanti piatti e scelta segnata anche dal bordo"`.

### Compito 5.3: etichette come testo colorato
**File:** `fanta/web/stile.css` (`.etichetta*`, `.etichette`, `.tono*`), `tests/test_design_web.py` (riscrivi
`_pillole()`, `_fondi_delle_pillole()` e `test_pillole_dei_giocatori_almeno_4_5…`: le etichette non hanno più tinta; la scritta
deve fare 4,5:1 su `--sfondo`, `--superficie` e il fondo del foglio nei due temi; `_fondi_delle_pillole()` non legge più
`--vetro` e `--vetro-carta`, che la PR 12 toglie, e resta usata da `test_bordo_dei_campi_almeno_3_a_1…`),
`tests/test_etichette_intere_web.py` (le regole di `.pezzo` per andare a capo restano).

- [ ] **Passo 1: test che fallisce** (nuovo, accanto a quelli riscritti)

```python
def test_etichette_senza_fondo_ne_bordo_tranne_le_due_pillole():
    regola = re.search(r"\n\.etichetta \{([^}]*)\}", CSS).group(1)
    assert "background: none" in regola and "border: 0" in regola and "font-size: var(--t-sec)" in regola
    assert re.search(r"\.pedina \.gioca\.basso[^{]*\{[^}]*border-radius", CSS)        # «⚠ gioca 45%» resta una pillola
```
- [ ] **Passo 2-5:** FAIL, CSS, PASS, commit `"Web: etichette dei giocatori come testo nel colore del tono"`.

### Compito 5.4: avvisi, errori, stati vuoti, messaggio che passa
**File:** `fanta/web/stile.css` (`.errore`, `.attenzione`, `.vuoto`, `.avviso`, `.banner-novita`), `fanta/novita.d/sezioni-pulsanti.json`.

- [ ] **Passo 1: test che fallisce**

```python
def test_avvisi_con_filo_a_sinistra_nel_colore_del_significato():
    assert re.search(r"\n\.errore \{[^}]*border-left: 3px solid var\(--rosso\)", CSS)
    assert re.search(r"\n\.attenzione \{[^}]*border-left: 3px solid var\(--arancio\)", CSS)
```
- [ ] **Passo 2-5:** FAIL, CSS, PASS, commit `"Web: avvisi ed errori con il filo del loro colore"`.

Novità: `{"titolo": "Meno riquadri", "voci": ["Le schermate dell'app web non sono più fatte di riquadri: sezioni con un titolo e righe.", "Le etichette dei giocatori sono testo colorato, senza fondo."]}`

**Fatto quando:** nessun riquadro bordato tranne la proposta di scambio e il modulo d'accesso; un solo pulsante pieno per
schermata nelle foto di Oggi e Formazione; axe a zero gravi su tutte le scene. Compito iPhone: nessuno; scrivi nella PR che le
etichette restano le stesse parole.

---

## PR 6: Riga del giocatore e colonne di numeri
Area: `fanta/web`, `tests`, `docs/COERENZA-WEB-IPHONE.md`. Scene: `oggi`, `formazione`, `elenco`, `rosa`; anche `--lingua en`.

### Compito 6.1: una riga sola, con le colonne
**File:** `fanta/web/app.js` (`voceGiocatore` ~482, `valoreRosa` ~506, `rigaGiocatoreCompatta` ~1510, `avatarIndice` ~332,
`partitaBreve` ~479), `fanta/web/stile.css` (`.voce`, `.valore`, `.ruolo`, `.barra-p`, `.diff` nelle righe,
`.badge-indice`, `.avatar-anello`), `tests/test_grafica_b_web.py`; da riscrivere con lo stesso scopo:
`tests/test_riflusso_web.py::test_righe_dei_giocatori_impilate…`, `tests/test_etichette_intere_web.py::test_riga_stretta_della_formazione…`,
`tests/test_oggi_migliori_dafare_web.py::test_una_sola_percentuale…`, `tests/test_rosa_righe_web.py`, `tests/test_mercato_web.py`.

**Interfacce:**
- Produce: `lineetta(slug) -> string` (`<i class="lineetta" style="--c:<primo colore sociale>" aria-hidden="true"></i>`, colori
  da `COLORI_SQUADRA`, grigio se manca); `intestazioneColonne(opz = { partita: true }) -> string` (riga con «Partita» e
  `t("mercato.fantavoto_atteso")`, `aria-hidden="true"`, classe `intestazione-colonne`; con `opz.ferma` anche la classe
  `ferma`). Variabili CSS `--col-gioca` e `--col-fv` (in `ch`) usate da tutte le righe.
- `voceGiocatore(x, posizione, conConfronto = false, sostituisci = false)`: stessa firma. Dentro: volto 36 px con l'indice come
  numero neutro (niente anello colorato), lettera del ruolo in `<span class="ruolo-l">`, nome, riga secondaria
  `lineetta(x.squadra) + partitaBreve(x)`, etichette (testo, terza riga al telefono, colonna sul PC), `«gioca N%»` intero,
  fantavoto atteso (o l'esito di `esitoPartita`), azione ⇄/✎ come oggi.

- [ ] **Passo 1: test che fallisce**

```python
def test_riga_del_giocatore_con_pochi_segni_e_gioca_intero():
    corpo = _funzione(APP, "voceGiocatore")
    assert "badgeRuolo(" not in corpo and "barra-p" not in corpo and 'class="diff' not in corpo
    assert 'class="ruolo-l"' in corpo and "lineetta(x.squadra)" in corpo and 't("giocatore.gioca"' in corpo


def test_intestazione_delle_colonne_nascosta_ai_lettori_e_colonne_pari():
    assert 'aria-hidden="true"' in _funzione(APP, "intestazioneColonne")
    assert re.search(r"--col-gioca: \d+(?:\.\d+)?ch", CSS) and re.search(r"--col-fv: \d+(?:\.\d+)?ch", CSS)
    assert ".avatar-anello.alto" not in CSS                    # niente anello colorato per l'indice
```
  più un test con node (stesso schema degli altri test che girano `app.js`) su `voceGiocatore` con
  `stato_partita: "fatto"` e `fv_preso: 7` → la riga contiene «7,0» e non contiene «gioca».
- [ ] **Passo 2:** FAIL. **Passo 3:** codice e CSS (spec §8.4-8.5): telefono 2-3 righe a sinistra e numeri a destra;
  da 900 px una riga con la colonna «Partita»; sotto i 320 px le regole di oggi (volto e numeri sopra, nome sotto).
- [ ] **Passo 4:** PASS, suite intera. Misura nelle foto: altezza di una riga dei titolari a 390 px (obiettivo 56-68 px, oggi
  100-150) e a 1440 px (obiettivo 48 px).
- [ ] **Passo 5: commit** `"Web: una riga del giocatore con pochi segni e i numeri in colonna"`.

### Compito 6.2: coerenza scritta
**File:** `docs/COERENZA-WEB-IPHONE.md` («Differenze ammesse»: due righe, spec §13: lineetta del colore sociale sulla web e
sigla nei colori sociali sull'iPhone; etichette come testo colorato sulla web e pillole sull'iPhone, stesse parole e toni),
`fanta/novita.d/riga-giocatore.json`. Commit `"Coerenza: lineetta del club e etichette come testo sulla web"`.

**Fatto quando:** in Formazione, Oggi, Rosa ed Elenco le colonne «gioca N%» e fantavoto atteso sono allineate tra tutte le
sezioni (misura: stessa `x` del bordo destro nelle foto a 1440); righe più basse come sopra; axe a zero gravi. Compito
iPhone: nessun cambio; controlla che `RigaGiocatore` mostri le stesse parole (nome, partita, etichette, «gioca N%», numero).

---

## PR 7: Oggi
Area: `fanta/web`, `tests`, `docs/GUIDA-UTENTE.md`. Scene: `oggi` (prima della scadenza; se i dati lo permettono anche a
giornata in corso e finita).

### Compito 7.1: Oggi come distinta
**File:** `fanta/web/app.js` (`mostraOggi` ~792, `marchioOggi` ~734 tolta, `cardRinvio`, `cardInCorso`, `cardRiepilogo`),
`fanta/web/dafare.js` (`dfRiga`, `cardDaFare`), `fanta/web/live.js` se le sue righe hanno classi tolte, `fanta/web/stile.css`
(sezione «Oggi», `.colonne-oggi`, `.maglia-hero`, `.con-maglia`, `.df-*`, `.marchio-oggi`, `.slogan-oggi`), test da riscrivere:
`tests/test_formazione_ritocchi_web.py::test_nome_e_slogan_in_oggi`, `tests/test_oggi_maglia_web.py`,
`tests/test_oggi_migliori_dafare_web.py::test_da_fare_pulsante_sotto_il_testo…`, `tests/test_riflusso_web.py` (maglia e conto),
`tests/test_da_fare_web.py`.

**Interfacce:** consuma `.azione-testo` (5.2), `intestazioneColonne` (6.1), `pagina(html, opz)` (4.2).

- [ ] **Passo 1: test che fallisce**

```python
DAFARE = (WEB / "dafare.js").read_text(encoding="utf-8")


def test_oggi_senza_nome_e_slogan_e_con_due_colonne_5_7():
    assert "marchioOggi(" not in APP and ".slogan-oggi" not in CSS
    assert re.search(r"@media \(min-width: 900px\) \{[^@]*\.colonne-oggi[^{]*\{ grid-template-columns: minmax\(0, 5fr\) minmax\(0, 7fr\)", CSS)


def test_da_fare_con_l_azione_scritta_nella_riga():
    corpo = _funzione(DAFARE, "dfRiga")
    assert 'class="azione-testo df-azione"' in corpo and "bottone secondario" not in corpo


def test_maglia_piccola_dritta_senza_ombra():
    regola = re.search(r"\.maglia-hero \{([^}]*)\}", CSS).group(1)
    assert "height: 72px" in regola and "rotate" not in regola and "drop-shadow" not in regola
```
- [ ] **Passo 2:** FAIL. **Passo 3:** spec §9 «Oggi»: conto alla rovescia in `--t-eroe` senza riquadro, cifre (modulo e punti)
  separate da un filo, un solo pulsante pieno «Apri la formazione», poi Da fare, I tuoi migliori, Da controllare,
  Indisponibili (chiuso), Diffidati, Partite del turno (griglia di oggi, test `test_partite_del_turno_in_una_griglia_sola`
  invariato). Il contatore di «Da fare» è un numero grigio accanto al titolo (non più il pallino lime).
- [ ] **Passo 4:** PASS, suite intera. Misure: a 390 px il conto alla rovescia e «Apri la formazione» stanno nel primo
  schermo (844 px di altezza); a 1440 px le due colonne finiscono senza un buco più alto di 200 px tra loro.
- [ ] **Passo 5: commit** `"Oggi: distinta con il conto alla rovescia, Da fare con l'azione nella riga"`.

Novità: `{"titolo": "Oggi più ordinata", "voci": ["Oggi mostra prima il conto alla rovescia e la formazione consigliata, poi le cose da fare con l'azione sulla stessa riga."]}`
GUIDA-UTENTE: aggiorna la descrizione di Oggi se parla del nome, dello slogan o della maglia grande.

**Fatto quando:** foto di Oggi a 390, 768, 1024, 1440 in chiaro e scuro guardate; nessun «Sostituisci» a contorno in fila; axe
a zero gravi. Compito iPhone: nessun cambio (l'iPhone non ha lo slogan); controlla che «Da fare», «Da controllare» e le partite
del turno abbiano le stesse parole.

---

## PR 8: Formazione
Area: `fanta/web`, `tests`, `docs/GUIDA-UTENTE.md`, `docs/COERENZA-WEB-IPHONE.md`, `docs/STILE-SENZA-AI.md`.
Prima di iniziare: risposta alla scelta 2 dell'utente (volti sul campo); senza risposta vale la prova B.
Scene: `formazione` (consigliata, modificata a mano non salvata, salvata, chiusa se i dati lo permettono).

### Compito 8.1: campo ed elenco affiancati, pedina con il disco
**File:** `fanta/web/app.js` (`pedina` ~439, `legendaCampo` ~453, `mostraFormazione` ~1110, `rigaStatoScelta` ~1084,
`distintivo` ~401 se non serve più), `fanta/web/stile.css` (sezione «campo», `.colonne-campo`, `.stato-scelta`), test da
riscrivere: `tests/test_testo_intero_web.py` (pedine e legenda), `tests/test_accessibilita_formazione_web.py` (sigla sul campo
ed entrata delle pedine), `tests/test_formazione_ritocchi_web.py::test_pedina_per_i_lettori_di_schermo` (deve restare verde
senza cambiarlo), `tests/test_design_web.py::test_formazione_controlli_compatti…` (resta: due `chips scorri`, `#modifica`,
«Altro» con Copia e Condividi), `tests/test_riflusso_web.py::test_formazione_chip_e_campo…`.

**Interfacce:** consuma `lineetta()` (6.1), `--alto-ferma` (4.1). `pedina(x, k)` stessa firma; dentro
`<span class="disco" aria-hidden="true">6,8</span>` al posto di `avatar(x)` (scelta 2 dell'utente), avversario con
`lineetta(x.avversario)` e la sigla; la frase per i lettori (`vocePedina`) non cambia.

- [ ] **Passo 1: test che fallisce**

```python
def test_pedina_con_il_numero_nel_disco_e_la_lineetta_del_club():
    corpo = _funzione(APP, "pedina")
    assert 'class="disco"' in corpo and "lineetta(x.avversario)" in corpo and "distintivo(" not in corpo
    assert 'class="solo-lettori"' in corpo and "vocePedina(x, esito)" in corpo


def test_la_legenda_non_copre_il_campo():
    corpo = _funzione(APP, "mostraFormazione")
    assert "${legendaCampo()}" in corpo and '<div class="campo">${legendaCampo()}' not in corpo   # oggi sta dentro il campo
    assert not re.search(r"\.legenda-campo \{[^}]*order: 1", CSS)
    assert "distintivo(" not in _funzione(APP, "legendaCampo")             # anche la spiegazione usa la lineetta


def test_campo_ed_elenco_affiancati_e_salva_sempre_in_vista():
    assert re.search(r"@media \(min-width: 900px\) \{[^@]*\.colonne-campo[^{]*\{ grid-template-columns: minmax\(0, 5fr\) minmax\(0, 7fr\)", CSS)
    assert re.search(r"\.stato-scelta\.modificata, \.stato-scelta\.mano \{[^}]*position: sticky; top: var\(--alto-ferma\)", CSS)
    assert re.search(r"html:has\(\.stato-scelta\.modificata\)", CSS)       # il focus non finisce sotto la riga ferma


def test_testo_sul_campo_leggibile():
    for campo in ("#187a41", "#146b3a"):
        assert _contrasto("#ffffff", campo) >= 4.5                         # nomi, «gioca N%», «vs LAG»
```
  (`_contrasto`: copia la funzione di `tests/test_design_web.py`.) Questo test prende il posto di
  `test_sigla_della_squadra_leggibile_su_ogni_colore_sociale_come_su_iphone` se `distintivo` sparisce: la lineetta è
  decorativa e la sigla è scritta in bianco sul campo.
- [ ] **Passo 2:** FAIL. **Passo 3:** spec §8.10 e §9 «Formazione». Il campo resta fermo con `controllaFerme` (regola di oggi);
  l'entrata delle pedine resta con la sua versione calma (`test_movimento_calmo_mantiene_la_dissolvenza_delle_pedine`).
- [ ] **Passo 4:** PASS. Misure: a 390 px il campo comincia entro 1,5 schermi (oggi dopo uno schermo intero di controlli); a
  1440 px campo e Titolari si vedono insieme senza scorrere.
- [ ] **Passo 5: commit** `"Formazione: campo ed elenco affiancati, pedina con il numero nel disco"`.

### Compito 8.2: Ctrl+S / ⌘+S salva
**File:** `fanta/web/app.js` (gestore `keydown` ~1907: il controllo va PRIMA di `if (ev.metaKey || ev.ctrlKey || ev.altKey) return;`),
`docs/GUIDA-UTENTE.md` (riga «Da tastiera»: «**Ctrl+S** (⌘+S sul Mac) salva la formazione quando c'è qualcosa da salvare»),
`fanta/web/testi.js` solo se serve il suggerimento nel `title` del pulsante (`formazione.salva_tasto`, it/en).

- [ ] **Passo 1: test che fallisce**

```python
def test_ctrl_s_salva_nella_formazione_solo_se_c_e_da_salvare():
    i = APP.index('document.addEventListener("keydown"')
    tasti = APP[i:APP.index("\n});\n", i)]
    assert '(ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === "s"' in tasti
    assert 'stato.vista === "formazione"' in tasti and "#salva-scelta" in tasti and "#salva-questa" in tasti
    assert tasti.index('ev.key.toLowerCase() === "s"') < tasti.index("if (ev.metaKey || ev.ctrlKey || ev.altKey) return;")
```
- [ ] **Passo 2-4:** FAIL, codice (`preventDefault()` solo se il pulsante esiste e non è disabilitato; poi `click()`), PASS.
  Prova con Playwright senza finestra: modifica a mano, `Control+s` → lo stato passa a «salvata».
- [ ] **Passo 5: commit** `"Formazione: Ctrl+S salva"`.

### Compito 8.3: documenti della pedina
`docs/COERENZA-WEB-IPHONE.md` («Differenze ammesse»: pedina della web con il numero nel disco e senza volto, quella dell'iPhone
con il volto; contenuto uguale), `docs/STILE-SENZA-AI.md` («Cosa resta»: sulla web i volti stanno negli elenchi e nella scheda,
sul campo il numero), `fanta/novita.d/formazione-b.json`. Commit `"Documenti: pedina della web con il numero nel disco"`.

Novità: `{"titolo": "Formazione più comoda", "voci": ["Su schermi larghi il campo resta accanto all'elenco dei titolari.", "La spiegazione dei segni sta sotto il campo e non lo copre più.", "Ctrl+S salva la formazione."]}`

**Fatto quando:** misure sopra; Ctrl+S provato; legenda sotto il campo; axe a zero gravi su tutti gli stati fotografati.
Compito iPhone: nessun cambio d'aspetto; controlla che la riga dello stato della scelta, i pulsanti («Salva questa», «Modifica a
mano», «Torna alla consigliata») e la pedina abbiano le stesse parole e gli stessi numeri.

---

## PR 9: Pannello affiancato, scheda del giocatore, ricerca
Area: `fanta/web`, `tests`, `docs/GUIDA-UTENTE.md`. Scene: `scheda` a 1024 (foglio modale) e 1440 (pannello), `formazione` con
la sostituzione aperta, ricerca con un testo.

### Compito 9.1: `apriFoglio(html, { affianco: true })`
**File:** `fanta/web/app.js` (`apriFoglio` ~1836, `chiudiFoglio`, `bloccaSfondo`/`sbloccaSfondo` ~1825, `apriGiocatore` ~1639,
`apriScelta` ~1750, `apriConfronto`, `apriSostituzione` (dentro `mostraFormazione`), foglio del «Perché questo numero»),
`fanta/web/index.html` (il foglio resta lo stesso elemento), `fanta/web/stile.css` (sezione «pannello» e «PC e schermi larghi»),
test da riscrivere: `tests/test_design_web.py::test_composizione_a_colonne…` (`sale-lato` resta), `tests/test_riflusso_web.py::test_scheda_e_confronto…`,
`tests/test_diario_stagione_web.py` e `tests/test_immagine_condivisa_web.py` se leggono `aria-modal` o `inert` (restano veri per
i fogli modali).

**Interfacce:**
- `apriFoglio(html, opz = {})`; `const affiancato = () => opz.affianco && matchMedia("(min-width: 1200px)").matches`.
  Affiancato: niente `bloccaSfondo()`, niente `aria-modal`, `body.classList.add("con-pannello")`, `--pannello:
  clamp(400px, 32vw, 520px)`, focus al primo titolo del contenuto (`tabindex="-1"`), elemento che l'ha aperto ricordato in
  `focusPrima`. `chiudiFoglio()` toglie `con-pannello` e riporta il focus.
- Un ascoltatore su `matchMedia("(min-width: 1200px)")`: con il pannello aperto, sotto i 1200 px passa a foglio modale
  (`bloccaSfondo()`), sopra torna affiancato.

- [ ] **Passo 1: test che fallisce**

```python
def test_pannello_affiancato_solo_per_i_dettagli_dei_giocatori():
    for nome in ("apriGiocatore", "apriScelta", "apriConfronto"):
        assert "affianco: true" in _funzione(APP, nome), nome
    assert "affianco: true" in _funzione(APP, "mostraFormazione")          # la sostituzione di un titolare
    apri = _funzione(APP, "apriFoglio")
    assert 'matchMedia("(min-width: 1200px)")' in APP and "bloccaSfondo()" in apri and "con-pannello" in apri
    assert re.search(r"@media \(min-width: 1200px\) \{[^@]*body\.con-pannello main \{[^}]*margin-right: var\(--pannello\)", CSS)
```
  più un test con node (schema di `tests/test_focus_bersagli_web.py`): con `matchMedia` finto a `true`, `apriFoglio("<h2>x</h2>",
  { affianco: true })` non mette `inert` su `main`; a `false` sì.
- [ ] **Passo 2:** FAIL. **Passo 3:** codice e CSS (spec §5 C5, §8.11, §14).
- [ ] **Passo 4:** PASS. Prova con Playwright senza finestra a 1440: clic su un titolare → pannello, `main` più stretto e non
  inerte; clic su un altro titolare → il pannello cambia; `Escape` → pannello chiuso e focus sul pulsante della riga. A 1024:
  foglio modale come oggi. Finestra da 1440 a 1000 con il pannello aperto → foglio modale, poi di nuovo 1440 → affiancato.
- [ ] **Passo 5: commit** `"Web: dettagli dei giocatori in un pannello accanto alla pagina sugli schermi larghi"`.

### Compito 9.2: scheda del giocatore e ricerca dalla testata
**File:** `fanta/web/app.js` (contenuto di `apriGiocatore`: numero eroe e «gioca N%» come cifre, statistiche in griglia senza
riquadri, spec §9; ricerca della testata (4.1): da 1200 px i risultati si scrivono nel pannello affiancato mentre si scrive, con
un'attesa di 150 ms, e il campo resta dove si scrive; tra 900 e 1199 px resta il foglio della ricerca come nella PR 4; Invio apre
il primo risultato), `fanta/web/stile.css` (`.intestazione-scheda`, `.statistiche`, `.stat-fila`, `.perche-*`),
`tests/test_numeri_web.py` (resta verde), `docs/GUIDA-UTENTE.md` (scheda accanto alla pagina e ricerca in testata sugli schermi
larghi), `fanta/novita.d/pannello-affiancato.json`.

- [ ] **Passo 1: test che fallisce**

```python
def test_la_ricerca_della_testata_scrive_nel_pannello_e_scheda_senza_riquadri():
    corpo = _funzione(APP, "apriRicerca")
    assert "affianco: true" in corpo
    assert not re.search(r"\.statistiche div \{[^}]*background", CSS)       # numeri senza riquadri
    assert not re.search(r"\.stat-fila > div \{[^}]*background", CSS)
```
- [ ] **Passo 2-5:** FAIL, codice, PASS, commit `"Scheda del giocatore come distinta; ricerca dalla testata"`.

Novità: `{"titolo": "Dettagli accanto alla pagina", "voci": ["Su schermi larghi la scheda di un giocatore si apre accanto alla pagina, senza coprirla: un clic su un altro giocatore la cambia.", "La ricerca in alto mostra i risultati mentre scrivi."]}`

**Fatto quando:** le prove di 9.1 passano; axe a zero gravi con il pannello aperto (1440) e con il foglio (390, 1024).
Compito iPhone: nessuno (sull'iPhone la scheda è un foglio di sistema).

---

## PR 10: Squadra
Area: `fanta/web`, `tests`. Scene: `squadra`, `elenco`, `rosa`, Cambi consigliati, Seguiti, Calendario, Aggiorna le rose.

### Compito 10.1: menu e pagina affiancati, Elenco con l'intestazione ferma
**File:** `fanta/web/app.js` (`vistaLega` ~3110 per l'ambito `squadra`, `vistaMercato` ~1332, `rigaGiocatoreCompatta`,
`vistaRosa` ~2356, Calendario), `fanta/web/anteprima.js` (stile delle righe dell'anteprima), `fanta/web/stile.css` (sezioni
«Mercato», «Lega», «calendario», «anteprima delle rose»), test da riscrivere con lo stesso scopo: `tests/test_mercato_web.py`,
`tests/test_lega_web.py`, `tests/test_squadra_testi_web.py`, `tests/test_squadra_dati_aggiornati_web.py`,
`tests/test_anteprima_rose_web.py`, `tests/test_design_web.py` (quattro voci di Mercato, proposta con il guadagno, nomi da 44 px),
`tests/test_riflusso_web.py::test_squadra_rose_e_calendario…`.

**Interfacce:** produce `.lega-colonne` (menu a sinistra, 280 px, e pagina a destra da 1100 px; voce aperta con
`aria-current="page"`), riusata da 11.1. Consuma `intestazioneColonne({ partita: true, ferma: true })` e `--alto-ferma`.

- [ ] **Passo 1: test che fallisce**

```python
def test_squadra_e_altro_a_due_colonne_sul_pc():
    assert re.search(r"@media \(min-width: 1100px\) \{[^@]*\.lega-colonne \{[^}]*grid-template-columns: 280px minmax\(0, 1fr\)", CSS)
    corpo = _funzione(APP, "vistaLega")
    assert 'class="lega-colonne"' in corpo and 'aria-current' in corpo


def test_intestazione_dell_elenco_ferma_sotto_la_testata():
    assert re.search(r"\.intestazione-colonne\.ferma \{[^}]*position: sticky; top: var\(--alto-ferma\)", CSS)
    assert "intestazioneColonne({ partita: true, ferma: true })" in APP       # Elenco dei giocatori e rosa di una squadra
```
- [ ] **Passo 2:** FAIL. **Passo 3:** codice e CSS (spec §5 C7, C10; §9 «Squadra e Altro»). Sotto i 1100 px una cosa alla volta
  con «‹ Squadra» come oggi. Il Calendario resta una tabella con le celle colorate.
- [ ] **Passo 4:** PASS. Misure a 1440: da Seguiti a Calendario con un clic, il menu resta in vista; nell'Elenco l'intestazione
  resta sotto la testata scorrendo; Tab sull'ultima riga visibile non finisce sotto l'intestazione ferma.
- [ ] **Passo 5: commit** `"Squadra: menu e pagina affiancati sugli schermi larghi, elenco con l'intestazione ferma"`.

Novità: `{"titolo": "Squadra più veloce", "voci": ["Su schermi larghi il menu di Squadra resta a sinistra e la pagina scelta si apre a destra.", "Nell'elenco dei giocatori i nomi delle colonne restano in vista mentre scorri."]}`

**Fatto quando:** misure sopra; axe a zero gravi sulle 7 scene di Squadra. Compito iPhone: nessun cambio; controlla nomi e ordine
delle voci (`VOCI_LEGA`, già legato da un test con l'iPhone, #304).

---

## PR 11: Altro
Area: `fanta/web`, `tests`. Scene: `altro`, `scambi` (tre modi), `diario`, `regole`, Movimenti, Crediti, Nuova stagione, Novità.

### Compito 11.1: pagine di Altro come distinta
**File:** `fanta/web/app.js` (`vistaLega` per l'ambito `altro`, `vistaScambi` ~2052, `apriDiario`, `vistaRegole` ~3374,
`vistaNovita` ~3320, movimenti, crediti, nuova stagione), `fanta/web/stile.css` (sezioni «Scambi», «analizzatore», «regole»,
«Diario», «novità», «confronto: duello»), test da riscrivere con lo stesso scopo: `tests/test_scambi_web.py`,
`tests/test_diario_confronto_web.py`, `tests/test_diario_correggi_web.py`, `tests/test_diario_stagione_web.py`,
`tests/test_novita_web.py`, `tests/test_touch_44.py` (i «−/+» restano da 44 px), `tests/test_riflusso_web.py::test_le_righe_delle_regole…`.

- [ ] **Passo 1: test che fallisce**

```python
def test_numeri_di_altro_nel_carattere_dei_numeri_e_regole_da_44_px():
    for selettore in (r"\.qp-num", r"\.guadagno", r"\.fv-fatto"):         # Diario, Scambi, Oggi in corso
        assert re.search(selettore + r" \{[^}]*font-family: var\(--font-numeri\)", CSS), selettore
    assert re.search(r"\.stepper button \{ width: 44px", CSS)              # i «−/+» delle regole restano da 44 px
    assert not re.search(r"\.riga-regola\.evidenzia \{[^}]*color-mix\(in srgb, var\(--verde\)", CSS)   # evidenziata con --superficie, non tinta
```
- [ ] **Passo 2-5:** FAIL, codice, PASS, commit `"Altro: Scambi, Diario, Regole e le altre pagine come distinta"`.

Novità: `{"titolo": "Altro in ordine", "voci": ["Scambi, Diario, Regole e le altre pagine di Altro hanno lo stesso aspetto ordinato delle altre schermate."]}`

**Fatto quando:** axe a zero gravi sulle 8 scene; foto guardate a 390 e 1440 in chiaro e scuro. Compito iPhone: nessun cambio;
controlla i testi di Scambi (riga 25 delle differenze aperte: resta un lavoro iOS già noto, non di questo piano).

---

## PR 12: Impostazioni, accesso, primo avvio, pulizia e documenti
Area: `fanta/web`, `tests`, `docs`, `MAPPA.md`. Scene: `impostazioni` (ogni gruppo), accesso (server con
`FANTA_MULTIUTENTE=1` senza sessione), primo avvio, anteprima delle rose.

### Compito 12.1: ultime schermate
**File:** `fanta/web/impostazioni.js`, `fanta/web/primoavvio.js`, `fanta/web/app.js` (accesso, `controllaAccesso`),
`fanta/web/stile.css` (sezioni «Impostazioni», «accesso», «primo avvio»), test: `tests/test_impostazioni_web.py`,
`tests/test_impostazioni_collaudo5_web.py`, `tests/test_primoavvio_web.py`, `tests/test_accesso_email_web.py`,
`tests/test_web_google.py` (il pulsante Google resta come vuole Google), `tests/test_design_web.py::test_accesso_e_primo_avvio_centrati`.

- [ ] **Passo 1-5:** test che fallisce (`.imp` con sezioni e righe; accesso largo al massimo 420 px senza riquadro:
  `re.search(r"\.accesso-corpo \{[^}]*max-width: 420px", CSS)`), FAIL, codice, PASS, commit
  `"Impostazioni, accesso e primo avvio come distinta"`.

### Compito 12.2: pulizia del CSS
**File:** `fanta/web/stile.css` (via `--vetro`, `--vetro-carta`, `--luce`, `--luce-2`, `.sfondo i`, `.suggerimento-tasti`,
`@keyframes allunga`, `allunga-v`, `respira`, regole delle colonne a 1400 e 1700 px rese inutili), `fanta/web/index.html`
(`<div class="sfondo">` se non serve), `tests/test_stile_senza_ai_web.py`, `tests/test_design_web.py`.

- [ ] **Passo 1: test che fallisce**

```python
def test_niente_resti_della_grafica_di_prima():
    for resto in ("--vetro", "--luce", ".lente", "backdrop-filter", "@keyframes respira", ".marchio-oggi"):
        assert resto not in CSS, resto
```
- [ ] **Passo 2-5:** FAIL, pulizia, PASS (suite intera), commit `"Web: tolte le regole della grafica di prima"`.

### Compito 12.3: documenti
**File:** `docs/DESIGN.md` (la sezione «Web: grafica B» passa da «in arrivo» a «in vigore»; scala, spaziature, componenti,
«Tablet e PC» per la web; incoerenza 15 segnata come fatta), `docs/STILE-SENZA-AI.md` («Prima e dopo» con le righe della B),
`MAPPA.md` (`fanta/web/`: testata con le schede, pannello affiancato, `fanta/web/caratteri/`), `docs/GUIDA-UTENTE.md` (aspetto
generale se descritto), `fanta/novita.d/grafica-b-finita.json`. Commit `"Documenti: grafica B della web in vigore"`.

**Fatto quando:** suite intera verde; `riepilogo.txt` di tutte le scene a 4 larghezze e 2 temi con `gravi=0` e
`scorrimento-di-lato=no`; documenti aggiornati. Compito iPhone: nessuno.

**Collaudo finale (coordinatore, dopo l'unione della PR 12):** «fatto quando» dell'issue #354: collaudo con Claude in Chrome a
390, 768 e 1440 px in chiaro e scuro su tutte le schermate, con dati verosimili; poi chiusura di #354.

---

## PR iOS-1 (solo con la scelta 1c): colore delle azioni su web e iPhone
**File:** `fanta/web/stile.css` (compito 3.2), `ios/Sources/Support/Aspetto.swift` (`case .verde` del tema chiaro: `0x0b6b3a`),
`ios/Sources/Support/Design/Tema.swift` se ha lo stesso valore, test Swift esistenti del colore, `fanta/novita.d/colore-azioni.json`.
Una PR sola, mista web + iPhone (conta nel tetto iOS): `tests/test_design_web.py::test_pulsanti_pieni_almeno_4_5_e_uguali_su_web_e_ios`
confronta i due lati, quindi due PR separate romperebbero i controlli della prima. Va dopo la PR 3 e prima della PR 4 (tocca
`stile.css`). Nella PR «Foto da fare: oggi, formazione» (giro normale del fotografo su `main`).
