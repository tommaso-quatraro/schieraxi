# Aperta agli amici: collaudo da «amico nuovo» e audit di sicurezza: piano

> **Per chi esegue:** per i compiti con codice (A1, A4, S3) OBBLIGATORIA la skill `superpowers:subagent-driven-development`
> (consigliata) o `superpowers:executing-plans`, un compito alla volta. Ogni compito con codice è un ramo e una PR sua, in una
> worktree sua. Passi con `- [ ]`. I confini dei file (§1) non si superano: se un compito ha bisogno di un file che non è suo, si
> ferma e lo scrive nel rapporto. Gli altri compiti (A2, A3, S1, S2, S4, P, C) sono del coordinatore o dell'utente e non toccano file.

**Obiettivo:** il primo lavoro dell'obiettivo #168: provare l'ingresso di un amico nuovo (invito, web sulla Home, rose, regole e
tempi della lega, prima formazione) sull'ambiente di prova, misurare i minuti, fare l'audit di sicurezza della parte che vedono gli
amici e aprire ai primi amici veri solo quando tutte e due le cose sono a posto.

**Architettura:** uno script Playwright ripetibile percorre l'ingresso come farebbe un amico, prima su un server locale e poi sulla
prova; l'utente rifà lo stesso percorso sui telefoni veri con il cronometro; un comando del server misura, a cose fatte, quanti
minuti ha impiegato ogni amico nuovo. In parallelo il coordinatore lancia la skill `security-audit` su un elenco chiuso di file;
il rapporto resta sul PC, fuori dal repository. Gli ostacoli diventano sotto-issue di #168; i problemi di sicurezza restano privati
e arrivano su GitHub solo insieme alla loro correzione; una «porta» con una lista di controlli decide l'apertura.

**Strumenti:** Python 3.12 (libreria standard; `openpyxl` già nei requisiti di sviluppo), Playwright della versione fissata in
`.github/playwright-requisiti.txt` in un ambiente a parte, Chrome di sistema, skill `security-audit`, `gh`.

**Spec:** `docs/superpowers/specs/2026-11-08-prodotto-design.md` (§2, §5, §6, §7 punto 2, §9, §10). Issue #568, obiettivo #168.
Esempio di forma: `docs/superpowers/plans/2026-11-08-ondata-2.md`. Ambiente di prova: decisione 0012 e `script/server/prova/LEGGIMI.md`.

## In breve: ordine e date

G0 è il giorno dopo la chiusura di #167, cioè dopo la misura della 12ª giornata di Serie A (dal 21 al 25/11/2026; la finestra della
misura finisce due giorni dopo l'ultima partita). G0 previsto: **sabato 28/11/2026**. Le date sotto sono previste: se un passo
slitta, slitta il resto, ma la porta (P) non si apre per data, solo con i controlli verdi.

| Quando (previsto) | Squadra | Utente |
|---|---|---|
| G0, sab 28/11 | lancio di A1, A4 e S1 in parallelo | primo invito sulla prova (D11, vale 7 giorni); risposta su D1 |
| G0+1/+2, dom 29/11 - lun 30/11 | A1 unito, prima corsa A2 sulla prova, sotto-issue | lun 30/11: prova sul suo iPhone (A3a, 20 minuti) |
| G0+2/+9, lun 30/11 - lun 7/12 | correzioni degli ostacoli e di sicurezza (S2, S3), Z | risposte su D2-D6, D8 (entro mar 1/12) |
| G0+9/+10, lun 7/12 - mar 8/12 | seconda corsa A2, verifica dell'audit (S4), lista della porta | secondo invito sulla prova (D11); misura finale sui telefoni (A3b, 20 minuti) |
| G0+11, mer 9/12 | | ok all'apertura (D9) e inviti a 1-2 amici prima di una scadenza |
| G0+12/+14, gio 10/12 - sab 12/12 | misura dal server (A4) e commento su #168 | gli amici entrano da soli; poi D10 |

## Vincoli globali

- Misura (spec §6): «un amico entra da solo dalla web e carica la sua lega in meno di 10 minuti».
- Per chi (spec §2): «Gli amici usano la web installata sulla schermata Home (iPhone e Android)». «Restano le regole già in vigore
  per gli account: inviti a tempo e un numero massimo di utenti» (oggi 7 giorni e `MAX_UTENTI`, predefinito 30).
- Fallimenti anche se «funziona» (spec §5): «un amico che ha bisogno del proprietario per entrare o per caricare la sua lega»;
  «la produzione toccata da una prova; dati veri o personali nel repository pubblico».
- Audit (spec §7): «il rapporto resta privato e i problemi gravi o critici bloccano l'apertura».
- Spese (spec §9): «Nessuna spesa (fonte con licenza, account Apple) prima della chiusura di #168».
- Funzioni congelate (spec §4): «resta com'è, si correggono i difetti e resta uguale su web e iPhone, ma niente funzioni, rifiniture
  o schermate nuove». Proporre di nasconderle si può; deciderlo spetta all'utente (D1, sezione 6 di questo piano).
- Repository pubblico: niente indirizzi (`<indirizzo-del-server>`, `app.<dominio>`, `prova.<dominio>`), nomi veri, email, codici
  d'invito, password, dettagli dei problemi di sicurezza; nemmeno in issue, PR, commit e commenti. Prima di ogni commit `git status`,
  `git diff --staged` e la skill `pubblica-repo`.
- Sulla prova solo dati inventati (`lega/esempio/`, `tests/dati/`): mai una lega vera, nemmeno quella del proprietario.
- Foto e registrazioni dello schermo solo nello scratchpad: la prova ha i nomi veri dei calciatori, quindi niente foto negli artifact
  né nel repository (come il collaudo della prova).
- `python` in questo piano = `<cartella principale>\.venv\Scripts\python.exe`. Suite intera: `python -m pytest -q -n 3`.
- Testi nuovi o cambiati per l'utente: nel catalogo `fanta/testi/`, poi `python script/testi.py --scrivi`; ogni schermata cambiata
  vale per web e iPhone (`docs/COERENZA-WEB-IPHONE.md`) o apre «coerenza: …»; skill `ui-schieraxi` e `docs/STILE-SENZA-AI.md`;
  mai testo tagliato con «…».
- PR che tocca `fanta/`, `script/server/` o `requirements.txt`: un solo `fanta/novita.d/<nome>.json`. PR in bozza, salvo l'eccezione
  P1 di S3.

## Attenzione in revisione

Casi che la spec implica e che è facile lasciar scappare; ognuno ha la sua prova nel compito indicato.
1. **Ordine fra registrazione e installazione sull'iPhone.** La web installata sulla Home ha un archivio suo, separato da Safari;
   da iOS 17.2 i cookie dovrebbero essere copiati al momento dell'installazione [da verificare, §9]. Il link d'invito si toglie
   dall'indirizzo appena letto, quindi installare dalla pagina dell'invito può perdere il codice. Atteso: in tutti e due gli ordini
   l'amico arriva dentro senza chiedere aiuto, o la guida e il primo avvio gli dicono l'ordine giusto. Prova: A3, «due ordini».
2. **Invito già usato o scaduto.** Atteso: una frase che dice cosa fare (chiedere un invito nuovo), non un errore generico. Prova:
   passo `invito_usato` di A1 (solo sul server locale).
3. **File che non è delle rose** (calendario, classifica, file di un'altra stagione con molti non trovati). Atteso: il messaggio
   spiega cosa riesportare e si può andare avanti (saltare o squadre di esempio). Prova: passo `file_sbagliato` di A1 (server locale).
4. **Password dimenticata senza posta** (sulla prova la posta è spenta, in produzione [da verificare]). Atteso: con il codice di
   recupero salvato l'amico rientra da solo. Prova: passo `rientro` di A1.
5. **Giornata già iniziata quando l'amico entra.** Atteso: Oggi dice «Questa giornata è già iniziata» e la Formazione è quella della
   prossima. Prova: una delle corse di A2 a giornata in corso.
Due in più, per A4: un primo avvio con passi saltati non conta come «dentro» (`test_saltato_non_conta_come_dentro`); le squadre di
esempio non contano come lega caricata, anche se il primo avvio segna `rose` fatto (`test_squadre_di_esempio_non_contano`).

---

## 1. Compiti, chi li fa e confini dei file

| Compito | Cosa | Agente e modello | Tetto | Può toccare | Non tocca |
|---|---|---|---|---|---|
| **A1** (#573) | percorso automatico «amico nuovo» | `collaudatore`, Opus high (con `isolation: "worktree"`) | server-web | `prove/amico_nuovo/**` (nuovo), `tests/test_amico_nuovo.py` (nuovo) | `fanta/**`, `prove/foto_web/**` (solo import), `MAPPA.md` |
| **A2** | corse sulla prova e sotto-issue | coordinatore (Opus) | nessuno | nessun file | il repository |
| **A3** | telefoni veri con il cronometro | utente; coordinatore annota | nessuno | nessun file | il repository |
| **A4** (#574) | misura dei minuti dal server | `sviluppatore-web`, Opus xhigh | server-web | `fanta/misura_ingresso.py` (nuovo), `fanta/__main__.py` (solo il comando `ingresso`), `tests/test_misura_ingresso.py` (nuovo), `fanta/novita.d/misura-ingresso.json` | `fanta/stato_utente.py`, `fanta/account.py`, `fanta/lega.py`, `fanta/onboarding.py` (solo import), `fanta/web/**`, `MAPPA.md` |
| **S1** | audit di sicurezza | coordinatore, sessione principale (Opus), skill `security-audit` | nessuno | nessun file del repository; rapporto fuori | il repository, prova e produzione |
| **S2** | smistamento, solo in privato | coordinatore | nessuno | `stato-coordinatore.md` (memoria privata) | GitHub, il repository |
| **S3** | correzioni (issue neutra aperta insieme alla PR) | `sviluppatore-web`, Opus xhigh, uno per gruppo di voci | server-web (P1 fuori bozza) | i file scritti nel brief | file di un'altra correzione in corso |
| **S4** | verifica dell'audit | coordinatore, skill `security-audit` | nessuno | nessun file | il repository |
| **P** | porta: lista dei controlli | coordinatore; ok dell'utente | nessuno | commento su #168 | |
| **C** | primi amici veri | utente; coordinatore misura con A4 | nessuno | commento su #168 | |
| **Z** | documenti | `documentatore`, Sonnet medium | soli documenti | `MAPPA.md` (righe di `prove/amico_nuovo/` e `fanta/misura_ingresso.py`), `docs/METODO.md` (sezione nuova) | codice |

Le correzioni degli ostacoli trovati da A2 e A3 sono sotto-issue nuove (§4): ognuna ha agente, file e «fatto quando» suoi, scritti
dal coordinatore con `python script/squadra/squadra.py brief <issue>`.

## 2. Ordine e cosa va in parallelo

Dipendenze (→ = «deve essere finito o unito prima»):
- A1 → A2 → (sotto-issue degli ostacoli) → seconda corsa A2 → P.
- A1 e l'invito sulla prova → A3a (il file inventato lo fa `file_rose` di A1); le correzioni P1 degli ostacoli → A3b → P.
- S1 → S2 → S3 → S4 → P.
- A4 → C (serve per misurare gli amici). A1 e A4 → Z.
- P e D9 → C.

Ondate:
- **G0:** A1, A4 (due agenti, nessun file in comune) e S1 (coordinatore). S1 legge il codice di `main` al commit di G0: le PR che
  si uniscono dopo le guarda S4.
- **Dopo A1:** A2 e A3a.
- **Dopo S2 e A2:** correzioni in parallelo, al massimo 4 PR server-web aperte (le correzioni di sicurezza contano dal momento della
  PR, S3.3), mai due agenti sugli stessi file. Prima le P1 (di
  sicurezza e degli ostacoli), poi le P2. Z quando A1 e A4 sono uniti.
- **Fine:** seconda corsa A2, A3b, S4, P; poi C.

## 3. Compiti

**Chi prova cosa nell'ingresso:**
- **Squadra, in automatico (A1, A2):** tutto il percorso dentro il browser, su un server locale e sulla prova: invito, registrazione,
  codice di recupero, requisiti per l'installazione, rose in tre formati, squadra, tempi, regole, formazione, rientro, cancellazione;
  errori della console, accessibilità con axe, larghezze 360 e 390.
- **Collaudo automatico che c'è già** (`collaudo-prova.yml`): ogni versione sulla prova con l'account di collaudo, ma solo schermate
  già dentro; non prova l'ingresso. Serve alla porta (P, punto 5).
- **Telefono vero (A3, utente):** Safari e Chrome veri, «Aggiungi alla schermata Home», archivio dell'app installata, testo grande,
  esportazione delle rose da Leghe, il cronometro.
- **Amico vero (C):** se entra davvero da solo, con la sua lega, in produzione; avvisi e posta veri.

### A1. Percorso automatico «amico nuovo»

**Interfacce prodotte** (`prove/amico_nuovo/percorso.py`, usate da A2, dalle sotto-issue e dalla porta):
- `PASSI = ("invito", "registrazione", "recupero_salvato", "installabile", "rose", "squadra", "tempi", "regole", "formazione",
  "rientro", "elimina")`; solo con `--locale` in più `PASSI_LOCALI = ("invito_usato", "file_sbagliato")`.
- `file_rose(rose_json: Path, formato: str, cartella: Path) -> Path` con `formato` fra `"testo"` (colonne `ruolo;nome;club;prezzo`),
  `"rosters"` (CSV di Leghe, una riga per giocatore: squadra, codice, costo) ed `"excel"` (`openpyxl`, come `tests/test_rose.py`).
  Costruisce il file da `lega/esempio/rose.json` al momento, sempre fuori dal repository. Gira con il Python di `.venv` (che ha
  `openpyxl`), lanciato come sottoprocesso come fa `prove/foto_web/foto.py` con il server.
- `riga(passo: str, secondi: float, tocchi: int, errori_console: int, gravi: int, esito: str) -> str` →
  `"<passo> secondi=<s> tocchi=<n> errori-console=<n> gravi=<n> esito=<ok|bloccato|errore:<tipo>>"`;
  `esito_complessivo(righe: list[str]) -> tuple[bool, list[str]]` (vero solo se ogni passo è `ok` con 0 errori e 0 gravi).
- Riga di comando: `percorso.py <cartella fuori dal repository> (--locale | --remoto) [--telefono iphone|android]
  [--larghezza 360|390] [--formato testo|rosters|excel] [--a-secco]`. Con `--remoto` indirizzo e invito arrivano SOLO da
  `SCHIERAXI_INDIRIZZO` e `SCHIERAXI_INVITO`; con `--locale` il server parte come in `foto.py` (`prepara_copia`, `ambiente_server`
  più `FANTA_MULTIUTENTE=1`) e l'invito si crea nella copia con `python -m fanta invito --etichetta amico-nuovo`. Nome utente
  `amico-<6 cifre a caso>`, password da `secrets.token_urlsafe(18)`: indirizzo, invito, password e codice di recupero mai stampati
  né scritti nei file. `--a-secco`: prepara i file e stampa i passi, senza browser. Uscita 0 tutto ok, 1 almeno un passo non ok,
  2 argomenti sbagliati.
- Riuso, senza copiare: `fuori_dal_repository`, `ServerDiProva`, `prepara_copia`, `ambiente_server`, `gravi` di `foto.py`; axe da
  `tests/strumenti/axe/`. Playwright si importa solo dentro la funzione che apre il browser (i test girano senza).
- Telefoni: Chrome di sistema con l'emulazione di Playwright (`iPhone 13` o `Pixel 7`, tocco, larghezza scelta), profilo temporaneo.
- Cosa vuol dire «ok» per ogni passo: `invito` = la registrazione si apre con il codice già scritto e il codice non è più
  nell'indirizzo; `registrazione` = compare il codice di recupero; `recupero_salvato` = si apre il primo avvio; `installabile` = il
  manifesto ha nome, icone 192 e 512, `display` a schermo intero e `start_url`, il service worker controlla la pagina dopo una
  ricarica, ci sono `apple-touch-icon` e i meta di Apple, e su Chrome `Page.getInstallabilityErrors` torna vuoto [da verificare, §9];
  `rose` = l'anteprima mostra le squadre; `squadra` = «Qual è la tua squadra?» → `Real Esempio`, i «da controllare» risolti con la
  prima proposta, «Conferma e salva»; `tempi` = scadenza 10 minuti e prima giornata proposta, poi «Tutto pronto»; `regole` = Altro >
  Regole, incolla il testo `ESEMPIO` di `tests/test_regole_testo.py`, «Applica ai campi», «Salva le regole»; `formazione` = 11
  titolari e un modulo, salvata; `rientro` = esci, «Password dimenticata», codice di recupero, password nuova, dentro; `elimina` =
  Impostazioni > Il tuo account > Elimina l'account (si fa sempre, anche se un passo prima fallisce). `invito_usato` = lo stesso
  invito monouso una seconda volta dà una frase che nomina l'invito; `file_sbagliato` = un CSV senza rose dà il messaggio del
  catalogo per «nessuna rosa» e si può andare avanti.

- [ ] **A1.1 Test rossi** in `tests/test_amico_nuovo.py` (nessun test usa il browser né `dati/fanta.sqlite`):
  `test_file_rose_hanno_tutte_le_squadre_d_esempio` (parametrico sui tre formati: le griglie lette da `fanta.rose.leggi_griglie`
  contengono i 10 nomi di squadra di `lega/esempio/rose.json`; per `testo` e `rosters` una riga per giocatore);
  `test_riga_del_riepilogo` (secondi con una cifra decimale:
  `riga("rose", 4.3, 3, 0, 0, "ok") == "rose secondi=4.3 tocchi=3 errori-console=0 gravi=0 esito=ok"`); `test_esito_rosso_se_un_passo_non_e_ok`
  (`esito_complessivo([...riga ok..., riga("rose", 1, 1, 0, 0, "bloccato")]) == (False, ["rose: bloccato"])`);
  `test_errori_console_rendono_rosso`; `test_segreti_mai_nell_uscita` (`--remoto --a-secco` con `SCHIERAXI_INVITO` e
  `SCHIERAXI_INDIRIZZO` di prova: né lo stdout né i file della cartella li contengono); `test_cartella_nel_repository_rifiutata`.
  Comando: `python -m pytest -q tests/test_amico_nuovo.py` → rossi.
- [ ] **A1.2 Codice** → `python -m pytest -q tests/test_amico_nuovo.py` verde; `ruff check prove tests` pulito.
- [ ] **A1.3 Prova vera sul server locale:** ambiente di Playwright nello scratchpad
  (`pip install --require-hashes --only-binary=:all: -r .github/playwright-requisiti.txt`), poi tre corse:
  `--locale --telefono iphone --larghezza 390 --formato excel`, `--locale --telefono android --larghezza 360 --formato testo`,
  `--locale --telefono iphone --larghezza 390 --formato rosters`. Atteso: uscita 0 e 13 passi `ok` in ognuna. Il collaudatore guarda
  2-3 schermate per corsa (nello scratchpad) e scrive nel rapporto i passi che un amico non capirebbe.
- [ ] **A1.4** `prove/amico_nuovo/LEGGIMI.md` (come si lancia, variabili, cosa non si salva mai). Suite intera una volta. PR in bozza:
  `Aree: prove/amico_nuovo, tests`, `Aspetto: nessuno`, nessuna novità (non tocca `fanta/`), `Closes #573`.

**Fatto quando:** test verdi; tre corse locali con uscita 0; PR unita.

### A2. Corse sulla prova e sotto-issue

- [ ] **A2.1 Prima di correre** (sessione `casa`, sola lettura): la prova ha l'ultima versione (ultima corsa verde di «Collaudo della
  prova» su quella versione); gli interruttori delle
  funzioni della prova (`FANTA_PROFILO_FUNZIONI=completo` nel suo servizio) e quelli della produzione sono uguali, oppure la
  differenza si annota e si legge il collaudo con quella [da verificare]; un invito sulla prova per più usi (D11):
  `sudo -u schieraxi-prova -H bash -c 'cd ~/app && .venv/bin/python -m fanta invito --etichetta amico-nuovo --usi 10'`. Il codice
  va solo in `SCHIERAXI_INVITO` sul PC, mai in chat pubbliche, issue o file. Un invito vale 7 giorni (`account.DURATA_INVITO`):
  basta per A2.2 e A3a, non per A2.5 e A3b.
- [ ] **A2.2 Quattro corse** con `--remoto`: `iphone 390 excel` e `android 360 testo`, una volta in settimana e una a giornata in corso
  (attenzione 5). Ogni corsa usa un posto dell'invito e toglie il suo account alla fine.
- [ ] **A2.3** Il coordinatore guarda riepiloghi e schermate. Ogni passo non `ok`, ogni errore della console, ogni violazione grave e
  ogni frase che un amico non capirebbe diventa una sotto-issue (§4).
- [ ] **A2.4** Commento su #168 che inizia con `## Esito A2`: passi ok e non ok per corsa, numeri delle sotto-issue. Niente indirizzi.
- [ ] **A2.5 Seconda tornata** dopo le correzioni P1: le stesse quattro corse (o due, se la giornata non cade nella finestra), con un
  **secondo invito** creato come in A2.1 (il primo è scaduto o ha finito i posti); lo stesso invito serve anche ad A3b.

**Fatto quando:** quattro corse fatte; ogni passo non ok ha la sua sotto-issue; commento su #168. Per la porta: seconda tornata con
tutte le corse a uscita 0.

### A3. Telefoni veri con il cronometro (utente)

Quello che l'emulazione non vede: Safari vero, «Aggiungi alla schermata Home», l'archivio separato dell'app installata, il testo
grande del telefono, l'esportazione delle rose da Leghe dal telefono.
- [ ] **A3.1 Preparazione** (coordinatore): un file Excel inventato fatto da `file_rose` (`--a-secco`), da mettere sul telefono (per
  esempio in File di iCloud Drive o mandato per posta a sé stessi); un posto dell'invito della prova.
- [ ] **A3.2 A3a, lun 30/11, 20 minuti, iPhone con Safari sulla prova.** Cronometro dal tocco sul link d'invito alla Formazione
  visibile, passando da registrazione, rose (il file inventato), regole (il testo d'esempio), tempi e installazione sulla Home.
  Poi: **due ordini** (registrarsi in Safari e poi installare; installare e poi registrarsi), l'app installata si apre a schermo
  intero e resta dentro, «Attiva» degli avvisi compare solo nell'app installata (la prova non manda avvisi: basta la richiesta del
  permesso), testo più grande al massimo (Impostazioni > Accessibilità > Schermo e dimensioni testo > Testo più grande) senza
  frasi tagliate. In più, senza caricare niente sulla prova: quanto ci vuole a esportare le rose da Leghe dal telefono (conta nei
  10 minuti dell'amico).
- [ ] **A3.3** Android con Chrome, stessa lista (installazione da «Installa app»), se c'è un telefono (D4).
- [ ] **A3.4** Il coordinatore scrive su #168 un commento `## Esito A3`: minuti per passo, ordine che funziona, ostacoli; poi le
  sotto-issue (§4).
- [ ] **A3.5 A3b, lun 7/12 o mar 8/12, 20 minuti:** stessa prova dopo le correzioni, con un posto del secondo invito (A2.5), e con
  una versione nuova arrivata sulla prova dopo l'installazione (l'app installata la mostra alla riapertura, senza pagina bianca né
  versione vecchia). Si cronometra di nuovo anche l'esportazione delle rose da Leghe.

**Fatto quando (per la porta):** in A3b la **somma** dei due tempi, esportazione delle rose da Leghe più il percorso dal link
d'invito alla Formazione, resta sotto i 10 minuti sull'iPhone, senza aiuto; lo stesso su Android se c'è il telefono, altrimenti la
parte Android si chiude con il primo amico Android in C (D4).

### A4. Misura dei minuti dal server

Serve a misurare gli amici veri senza stargli accanto. Usa solo dati che ci sono già, nella cartella dell'utente
(`<cartella_utenti>/<id>/`, la stessa di `contesto.cartella_utente`):
- `utenti.creato` (UTC con fuso) in `account.sqlite`: l'inizio;
- le rose, `rose.json` letto con `lega.carica`: contano solo se ci sono e **non** sono le squadre di esempio
  (`onboarding.e_demo(rose)` falso). Il primo avvio segna `rose` fatto anche con «Usa le squadre di esempio»
  (`fanta/web/primoavvio.js`, bottone `#pa-esempi`), quindi `fatti` da solo non basta; l'ora è `rose.aggiornato`;
- il `primo_avvio` (`fatti`, `saltati`, `chiuso`, `aggiornato`), letto con `stato_utente.leggi_primo_avvio` da
  `avvisi-impostazioni.json`: serve `tempi` fra i `fatti`, con l'ora `aggiornato`.
**Trappola:** `rose.aggiornato` (`lega.py`, `datetime.now()`) e `primo_avvio.aggiornato` (`stato_utente._ora()`) sono senza fuso,
cioè nell'ora del server; `utenti.creato` invece è UTC con fuso.

**Interfacce prodotte** (`fanta/misura_ingresso.py`):
- `minuti_di_ingresso(creato: str, rose: Rose | None, primo_avvio: dict | None, fuso_server: tzinfo) -> tuple[str, float | None]`:
  - `"dentro"` con i minuti da `creato` al più tardi fra `rose.aggiornato` e `primo_avvio["aggiornato"]` (letti nel `fuso_server`),
    se ci sono rose che non sono d'esempio e `tempi` è fra i `fatti`;
  - `"solo_esempio"` (minuti `None`) se le rose sono quelle d'esempio;
  - `"non_finito"` se mancano rose vere o `tempi`; `"non_iniziato"` se non ci sono né rose né primo avvio.
- `misura(db: sqlite3.Connection, cartella_utenti: Path, dal: datetime, al: datetime, fuso_server: tzinfo) -> list[dict]`
  (`{"utente": id, "esito": …, "minuti": …}`, solo gli account creati fra `dal` e `al`).
- Comando `python -m fanta ingresso --dal <ISO con fuso> [--al <ISO con fuso>]`: apre `account.sqlite` in sola lettura
  (`mode=ro`), stampa una riga per account (`utente <id>: dentro in <m> minuti`, `solo squadre di esempio`, `non finito` o
  `non iniziato`, mai nomi utente) e l'ultima riga `dentro in meno di 10 minuti: <n> su <m>`. Uscita 0 se tutti gli account del
  periodo sono dentro entro 10 minuti, 1 altrimenti, 2 se nel periodo non c'è nessun account. Si lancia sul server come
  `sentinella --giri`.

- [ ] **A4.1 Test rossi** in `tests/test_misura_ingresso.py` (orologio mai vero: tutte le ore nei dati):
  `test_dentro_quando_rose_e_tempi_fatti` (`creato="2026-12-10T09:00:00+00:00"`, rose non d'esempio con
  `aggiornato="2026-12-10T10:06:00"`, primo avvio con `rose` e `tempi` fatti e `aggiornato="2026-12-10T10:08:00"`, fuso
  Europa/Roma in inverno → `("dentro", 8.0)`); `test_squadre_di_esempio_non_contano` (rose con i nomi di `onboarding.SQUADRE_DEMO`,
  `rose` e `tempi` fatti → `("solo_esempio", None)`); `test_saltato_non_conta_come_dentro`; `test_non_iniziato`;
  `test_solo_account_del_periodo`; `test_archivio_in_sola_lettura` (dopo `misura` il file ha lo stesso contenuto e una scrittura
  sulla connessione fallisce); `test_niente_nomi_utente_nell_uscita`; `test_codici_di_uscita` (tutti entro 10 → 0, uno a 12 → 1,
  nessuno → 2).
- [ ] **A4.2 Codice** → verdi; suite intera una volta; `docs/API.md` non cambia (nessuna rotta).
- [ ] **A4.3** `fanta/novita.d/misura-ingresso.json` con voci «nessun cambio visibile» come nelle PR di sola manutenzione, `tecnico`
  con il comando. PR in bozza, `Aree: fanta, tests`, `Closes #574`.

**Fatto quando:** test verdi, compreso `test_squadre_di_esempio_non_contano`; PR unita; sul server locale con due account finti
(uno con rose importate, uno con le squadre di esempio) il comando stampa le due righe giuste.

### S1. Audit di sicurezza (coordinatore)

La richiesta di audit completo viene dalla spec (§7, decisa dal proprietario): la skill `security-audit` gira in «full audit mode».
- [ ] **S1.1 Preparazione.** Profilo `standard`, corsa limitata al perimetro qui sotto (la skill la dichiara copertura parziale),
  tetto di 50 invocazioni di agenti, commit di `main` di G0 scritto in `run-metadata.json`. Cartella del rapporto: quella predefinita
  della skill, `~/security-audit-skill/schieraxi/run-<N>/` (sul PC, fuori dal repository). La cartella `.claude/` del repository
  (dove stanno le worktree degli altri agenti) è fuori dal perimetro. Nessuna prova contro la prova o la produzione: la skill lo
  vieta e da noi è un fallimento (spec §5).
- [ ] **S1.2 Perimetro** (la parte che vedono gli amici, spec §7):
  - accesso, sessioni, inviti, recupero: `fanta/account.py`, `fanta/rotte_account.py`, `fanta/account_email.py`, `fanta/posta.py`,
    `fanta/social.py`, `fanta/limiti.py`;
  - isolamento fra utenti e poteri dell'amministratore: `fanta/contesto.py`, `fanta/percorsi.py`, `fanta/server.py` (rotte
    personali, `X-Fanta`, intestazioni, limiti), `fanta/gestione.py`, `fanta/funzioni.py`;
  - file caricati e indirizzi: `fanta/rose.py`, `fanta/importa_sicuro.py`, `fanta/_excel_figlio.py`, `fanta/regole_testo.py`,
    `fanta/immagini.py`, `fanta/scarica_immagine.py`, `fanta/avatar.py`, `fanta/backup.py`;
  - avvisi: `fanta/push.py`, `fanta/avvisi_utenti.py`, `fanta/notifiche.py`, `fanta/avvisi.py`;
  - token del widget e accesso dell'app con `Authorization`: `fanta/widget.py` e le parti di `account.py` e `server.py` che li leggono;
  - web app: `fanta/web/*.js`, `fanta/web/index.html`, `fanta/web/sw.js` (nomi importati mostrati nelle pagine, dati personali nella
    cache del service worker);
  - primo avvio e dati dell'utente: `fanta/onboarding.py`, `fanta/stato_utente.py`, cancellazione dell'account e «Scarica i tuoi dati»;
  - configurazione d'esempio del server (`script/server/`, `script/server/prova/`): solo come fatti da far controllare all'utente.
- [ ] **S1.3** Se il recinto che la skill chiede per eseguire codice non c'è sul PC [da verificare], la corsa resta sul codice e i
  punti da provare diventano `needs_validation` (si provano poi nei test delle correzioni).
- [ ] **S1.4** In `stato-coordinatore.md` (memoria privata) solo i conteggi per gravità e la cartella della corsa. Nient'altro esce dal PC.

**Fatto quando:** corsa finita con i due controlli della skill superati, oppure `incomplete` con il motivo scritto; conteggi annotati.

### S2. Smistamento, solo in privato

Regola (gravità della skill: `critical`, `high`, `medium`, `low`, `informational`):
- `critical` e `high` confermati: **bloccano la porta**. Priorità `P1`.
- `needs_validation` su accesso, inviti, isolamento fra utenti, token o file caricati: bloccano come un `high` finché non si chiariscono
  (fatto controllato dall'utente in sola lettura nella sessione `casa`, oppure un test locale in S3).
- `medium`: priorità `P2`, non blocca la prima ondata di amici; si chiude prima di invitarne altri.
- `low` e `informational`: `P3` o niente, una scelta per voce.

**Nessuna issue pubblica prima della correzione.** Un'issue aperta su un difetto ancora nel codice pubblico, con la produzione accesa,
dice a chiunque dove cercare (e va contro `SECURITY.md`, che chiede di non rendere pubblico un problema prima che sia sistemato).
Finché la correzione non è pronta, le voci stanno SOLO in privato: il rapporto sul PC e `stato-coordinatore.md` del coordinatore
(numero della voce, priorità, gruppo di file, stato; mai su GitHub). Le voci sugli stessi file si correggono insieme, così due
correzioni non toccano gli stessi file. I dettagli arrivano all'agente di S3 solo nel brief (chiamata dell'agente, non GitHub), con
il percorso della voce in `FINDINGS-DETAIL.md` sul PC. Un problema `critical` sfruttabile senza account sulla produzione: prima si
chiude la porta sul server (D7), poi la correzione.

- [ ] **S2.1** In `stato-coordinatore.md` una riga per voce o gruppo: `F-<n>`, priorità, file da toccare, agente, stato.
- [ ] **S2.2** Lista dei `needs_validation` per l'utente, in privato (chat o memoria), con il comando di sola lettura per ognuno.

**Fatto quando:** ogni voce confermata o bloccante ha la sua riga privata con priorità e gruppo di file, o una scelta scritta in
privato per le `low`; su GitHub ancora niente.

### S3. Correzioni di sicurezza

- [ ] **S3.1** Un `sviluppatore-web` per gruppo di voci, file disgiunti. Il brief lo scrive il coordinatore dal modello
  (`script/squadra/modello-brief.md`), senza issue, con il puntatore privato alla voce; l'agente lavora nella sua worktree e NON fa
  push né PR.
- [ ] **S3.2** Test di regressione prima del codice, visto rosso; nome che dice il comportamento atteso
  (`test_<area>_<comportamento>`), con l'ingresso minimo che serve, senza parole come «attacco».
- [ ] **S3.3** La revisione si fa sul ramo locale PRIMA del push (coordinatore: `revisore`, `/code-review`, `/security-review`).
  Poi, nello stesso giro, il coordinatore apre l'issue neutra, fa il push e apre la PR con `Closes #<issue>`:
  - issue: titolo «Sicurezza: voce F-<n>» (senza area); corpo **Cosa** «correzione di una voce dell'audit di sicurezza del <data>»,
    **Perché** «i dettagli restano nel rapporto privato (repository pubblico)», **Fatto quando** «PR di correzione unita con il suo
    test di regressione; la voce risulta chiusa alla verifica S4»; etichetta di priorità e `server`; «Parte di #168»; agganciata a
    #168 e messa sulla bacheca (`gh api -X POST "repos/{owner}/{repo}/issues/168/sub_issues" -F sub_issue_id=$(gh api
    "repos/{owner}/{repo}/issues/<N>" --jq .id)` e `gh project item-add 1 --owner "@me" --url <link>`, dalla cartella del repository);
  - PR: descrizione e commit neutri; voci `P1` di poche righe subito pronte (eccezione P1 di REGOLE §1), le altre in bozza con la
    revisione già registrata, tolta dalla bozza appena partono i controlli;
  - mai, né nell'issue né nella PR: rotte, parametri, file e righe, condizioni, esempi d'attacco, parole sulla gravità oltre
    all'etichetta.
  Così il difetto diventa pubblico solo insieme alla sua correzione, per il tempo dei controlli.
- [ ] **S3.4** Novità con voci neutre (per esempio «Accesso e dati più protetti») se la PR tocca `fanta/`.

**Fatto quando** (per gruppo): issue e PR aperte insieme, PR unita, test di regressione verde, voce F-<n> segnata «corretta» nel
rapporto privato e in `stato-coordinatore.md`.

### S4. Verifica dell'audit

- [ ] **S4.1** Nuova corsa della skill sullo stesso perimetro e nella stessa cartella radice (`run-<N+1>`): la skill rilegge le corse
  precedenti e riverifica le parti cambiate. Commit: `main` dopo l'ultima correzione.
- [ ] **S4.2** Commento pubblico su #168, solo questa frase: «Audit di sicurezza: nessun problema grave o critico aperto (verifica
  del <data>)».

**Fatto quando:** zero `critical` e `high` confermati aperti, zero `needs_validation` bloccanti.

### P. Porta dell'apertura

Il coordinatore apre la porta solo con tutti i punti veri, e li scrive in un commento `## Porta` su #168 (senza dettagli):
1. S4 fatto.
2. Seconda tornata di A2: tutte le corse con uscita 0.
3. A3b: sull'iPhone esportazione delle rose da Leghe più percorso dal link alla Formazione sotto i 10 minuti, senza aiuto (Android
   come in D4).
4. Nessuna sotto-issue `P1` di #168 aperta.
5. Ultimo collaudo automatico della prova verde (`collaudo-prova.yml`) e sentinella senza allarmi negli ultimi 2 giorni.
6. Produzione controllata in sola lettura (sessione `casa`): `FANTA_MULTIUTENTE=1`, `FANTA_REGISTRAZIONE=invito`, `MAX_UTENTI`,
   stato della posta, pagine Privacy e Termini compilate (variabili `FANTA_TITOLARE` e `FANTA_CONTATTO`), interruttori delle
   funzioni come deciso in D1 [da verificare: tutti e sei].
7. Ok dell'utente (D9).

### C. Primi amici veri

- [ ] **C.1** L'utente crea un invito monouso per amico in produzione (Impostazioni > Avanzate > Nuovo invito, «Copia il messaggio») e
  lo manda 1-2 giorni prima di una scadenza [date di Serie A da verificare]. Non li aiuta: se un amico chiede, lo annota (è un ostacolo).
- [ ] **C.2** Il giorno dopo: `python -m fanta ingresso --dal <ora degli inviti>` sul server (sessione `casa`, sola lettura, con l'ok
  dell'utente); domanda all'amico «hai chiesto aiuto a qualcuno?».
- [ ] **C.3** Commento `## Esito C` su #168: numero di amici, minuti, aiuti chiesti, ostacoli (sotto-issue). Niente nomi.

**Fatto quando:** almeno un amico «dentro» in meno di 10 minuti secondo A4 e senza aiuto; poi il coordinatore propone D10.

### Z. Documenti

- [ ] Dopo l'unione di A1 e A4: in `MAPPA.md` una riga per `prove/amico_nuovo/` e una per `fanta/misura_ingresso.py` (comando
  `ingresso`); in `docs/METODO.md` una sezione «Ingresso degli amici (la misura di #168)» accanto a «Giornata senza errori»: cosa
  misurano lo script e il comando, dove resta il rapporto dell'audit, regola delle issue neutre aperte insieme alla correzione. PR
  di soli documenti, `pubblica-repo`.

**Fatto quando:** PR unita; `MAPPA.md` nomina `prove/amico_nuovo/` e `fanta/misura_ingresso.py` (con il comando `ingresso`);
`docs/METODO.md` ha la sezione con i due comandi, la soglia dei 10 minuti e la regola delle voci di sicurezza solo in privato fino
alla PR di correzione; la ricerca di `pubblica-repo` sul diff non trova niente.

## 4. Ostacoli: modello della sotto-issue

Ostacolo = un passo che non va avanti senza il proprietario, un errore, una violazione grave di accessibilità, una frase che un
amico non capisce, o un passo che da solo si mangia buona parte dei 10 minuti.
- Titolo: «Ingresso: <cosa succede, con le parole dell'amico>» (per esempio «Ingresso: dopo l'installazione chiede di nuovo la password»).
- **Cosa**: passo del percorso, telefono, cosa succede e cosa ci si aspetta. **Perché**: spec §5 e il compito del piano (A2 o A3).
  **Fatto quando**: il passo `<nome>` di `percorso.py` torna `ok` (o, per un ostacolo visto solo sul telefono, la stessa prova di
  A3 passa); per i testi anche catalogo e coerenza web-iPhone. **Aree**: le cartelle toccate.
- Priorità: `P1` se l'amico non può andare avanti da solo; `P2` se lo rallenta o lo confonde; `P3` il resto.
- Una schermata cambiata: compito web e compito iOS nello stesso ramo, uno dopo l'altro, oppure issue «coerenza: …».
- Se la correzione vorrebbe aggiungere, togliere o nascondere una funzione: si scrive la proposta nell'issue e decide l'utente.
- Agganciata a #168 e messa sulla bacheca con i comandi di S3.3.

## 5. Cosa serve dall'utente, tutto insieme

| Quando (previsto) | Cosa | Tempo |
|---|---|---|
| sab 28/11 | primo invito sulla prova (D11) e risposta su cosa vedono gli amici (D1) | 5 minuti |
| lun 30/11 | A3a sul suo iPhone, con il file inventato e il cronometro | 20 minuti |
| entro mar 1/12 | risposte su D2-D6 e D8 | 10 minuti |
| se serve | ok a una chiusura temporanea sul server per un problema critico (D7) | al momento |
| lun 7/12 | secondo invito sulla prova (D11), per A2.5 e A3b | 5 minuti |
| lun 7/12 o mar 8/12 | A3b su iPhone (e Android, se c'è) | 20 minuti |
| mer 9/12 | ok all'apertura (D9); inviti a 1-2 amici in produzione | 10 minuti |
| gio 10/12 - sab 12/12 | non aiutare gli amici; ok al comando di misura sul server; poi D10 | 5 minuti |

## 6. Decisioni dell'utente (con la mia proposta)

- **D1. Cosa vedono gli amici.** Gli interruttori delle funzioni valgono per tutto il server; ognuno può accendere per sé «Mostra tutte
  le funzioni» (solo menu e schermate). Proposta: per gli amici il nucleo della spec (§3), con le funzioni congelate nascoste, e per il
  proprietario «Mostra tutte le funzioni». [da verificare: profilo e scelte di oggi in produzione, e quali rotte restano spente anche
  con «Mostra tutte».] È un «togliere funzioni» per gli amici: decide l'utente.
- **D2. Dove entra il primo amico vero.** Proposta: in produzione, con la sua lega, dopo la porta. La prova resta per i dati inventati
  (niente avvisi, posta, internet e dati freschi lì).
- **D3. Quanti amici, con che telefono, quando.** Proposta: due, uno con iPhone e uno con Android, inviti monouso, mandati mer 9/12
  prima di una scadenza. I nomi restano fuori da GitHub.
- **D4. Android per A3.** Proposta: se nessun telefono Android è pronto, A3 vale con la sola emulazione e la prova vera la fa il primo
  amico Android in C. Alternativa: l'emulatore di Android Studio sul PC (gratuito, installazione grande [da verificare]), con il tuo ok.
- **D5. Password dimenticata per gli amici.** Se in produzione la posta è spenta [da verificare], restano il codice di recupero e il
  ripristino da parte del proprietario (che però è «aiuto»). Proposta: tenere così per i primi amici e decidere sulla posta (servizio e
  casella: account) solo se A3 o C mostrano che il codice si perde.
- **D6. Pagine legali.** Proposta: prima degli inviti controllare che Privacy e Termini abbiano titolare e contatto (punto 6 della
  porta). Ogni altro passo legale lo decide l'utente; la squadra non scrive testi legali nuovi senza di lui.
- **D7. Problema critico sulla produzione.** Proposta: ok di massima a spegnere per poco, sul server, la sola funzione colpita prima
  della PR pubblica; i comandi si mostrano al momento.
- **D8. Avvisi di sicurezza pubblici su GitHub** dopo le correzioni. Proposta: no per i problemi trovati da noi prima dell'apertura
  (nessun utente esterno coinvolto); il fork privato temporaneo di GitHub non serve (§9).
- **D9. Ok all'apertura** quando la porta è verde.
- **D10. Chiusura di #168** dopo C. Chiuderla sblocca le spese (spec §2, §9), che restano decisioni a parte. Proposta: chiudere quando
  almeno un amico è dentro in meno di 10 minuti da solo.
- **D11. Inviti sulla prova per A2 e A3** (due: uno sab 28/11, uno lun 7/12, perché un invito vale 7 giorni). Proposta: li crea il
  coordinatore nella sessione `casa` con il comando di A2.1, con il tuo ok.

## 7. Scelte mie

- Scelta mia: A1 è uno script ripetibile e non un collaudo a mano una volta, perché ogni sotto-issue lo usa come «fatto quando».
  Costo se sbagliata: una PR in più.
- Scelta mia: A1 gira dal PC e non in un workflow nuovo, perché sulla prova ogni corsa consuma un invito e lascia un account da togliere,
  e un workflow con un segreto in più va rivisto. Costo se sbagliata: non si ripete da solo a ogni versione; si aggiunge dopo al
  collaudo della prova con un'issue `P3`.
- Scelta mia: Chrome di sistema con l'emulazione di iPhone e Android, senza scaricare WebKit. Costo se sbagliata: una differenza di
  Safari passa; la prende A3.
- Scelta mia: file delle rose costruiti al momento da `lega/esempio/rose.json` in tre formati, mai salvati. Costo: nessuno.
- Scelta mia: la misura dei minuti usa solo dati che il server ha già (A4), senza un dato nuovo sugli utenti, e scarta le squadre di
  esempio. Costo se sbagliata: se l'amico riapre il primo avvio o reimporta le rose lo stesso giorno, la misura viene più lunga del
  vero, cioè sbaglia a sfavore.
- Scelta mia: due corse A2 per telefono, in settimana e a giornata in corso. Costo: un posto dell'invito in più.
- Scelta mia: audit con profilo `standard`, perimetro chiuso, commit fisso, tetto di 50 invocazioni. Costo se sbagliata: parti fuori
  perimetro non coperte (elencate in §8); la skill permette una corsa in più sul resto.
- Scelta mia: i `needs_validation` su accesso, inviti, isolamento, token e file caricati bloccano come un `high`, perché la porta non
  deve diventare verde per omissione (decisione 0013). Costo: qualche giorno.
- Scelta mia: `medium` non blocca la prima ondata di amici ma la seconda. Costo se sbagliata: un rischio limitato per 1-2 amici.
- Scelta mia: per le correzioni di sicurezza la revisione si fa sul ramo locale prima del push, e le `P1` di poche righe escono
  subito pronte. Costo: niente bozza; resta la revisione IA dei controlli come secondo sguardo.
- Scelta del coordinatore (revisione della PR #572): le voci dell'audit restano SOLO in privato (rapporto sul PC e
  `stato-coordinatore.md`) fino alla correzione; l'issue neutra «Sicurezza: voce F-<n>», senza area, si apre insieme alla PR della
  correzione, perché un'issue su un difetto ancora aperto nel codice pubblico, con la produzione accesa, dice dove cercare (e va
  contro `SECURITY.md`). Costo: fino alla PR il lavoro di sicurezza non si vede su GitHub né sulla bacheca, e si segue solo dalla
  memoria del coordinatore.
- Scelta mia: `MAPPA.md` e `docs/METODO.md` in Z alla fine, perché A1 e A4 vanno insieme e `MAPPA.md` è un file comune. Costo: per
  qualche giorno la mappa non nomina i file nuovi.

## 8. Rischi e cosa resta fuori

Rischi:
- **#167 si chiude tardi** (misura rossa): G0 slitta. Il piano ha un ordine, non date fisse.
- **L'audit trova molto:** l'apertura slitta. Va bene così: gravi e critici bloccano.
- **Recinto dell'audit assente sul PC** [da verificare]: solo lettura del codice; le prove passano ai test delle correzioni.
- **La prova non prova tutto:** avvisi (il servizio non esce su internet), posta (spenta), accesso con Google, dati freschi (copia
  notturna). Si vedono solo in C, in produzione.
- **iPhone, archivi separati** fra Safari e app installata: l'amico deve rientrare; A3 prova i due ordini (attenzione 1).
- **Esportare le rose da Leghe dal telefono** può da solo superare i 10 minuti, e non dipende da noi: A3 lo misura; se è così, la
  guida e il primo avvio devono dirlo in modo chiaro (sotto-issue).
- **Finestra pubblica delle correzioni:** il codice della correzione è visibile mentre girano i controlli; S3.3 la tiene corta.
- **Stesso server per prova e produzione:** A2 fa poche corse, una alla volta, con un account che si toglie da solo.
- **Amici non disponibili nelle date:** C slitta; nessun ripiego con amici finti.
- **Tetti delle PR:** al massimo 4 PR server-web; le correzioni P1 passano davanti.

Fuori da questo piano: il pubblico (stagione 2027-28), fonte dati con licenza, store, account Apple, ogni spesa (spec §9); l'app
iPhone per gli amici (resta del proprietario, spec §2) e quindi widget per gli amici; Android nativo; funzioni nuove o allargate;
nell'audit l'app `ios/`, il sito `sito/`, i workflow `.github/workflows/` (li controllano già zizmor e `agentic-actions-auditor`),
`prove/`, `tests/`, il modello e le fonti, salvo dove leggono dati scritti dall'utente.

## 9. Fonti e cose da verificare

- Fork privato temporaneo degli avvisi di sicurezza di GitHub: i controlli di CI non girano, le regole di protezione del ramo non
  valgono, l'unione la fa a mano un amministratore dell'avviso. Per questo il piano non lo usa (D8). [verificato]
  [guida di GitHub](https://docs.github.com/en/code-security/security-advisories/working-with-repository-security-advisories/collaborating-in-a-temporary-private-fork-to-resolve-a-repository-security-vulnerability)
- Segnalazione privata delle falle accesa nel repository (citata in `SECURITY.md`): [da verificare] nelle impostazioni del repository.
- iPhone: da iOS 17.2 i cookie del sito si copiano nell'app installata sulla Home, poi gli archivi restano separati. [da verificare]
  [iGeneration, 12/2023](https://www.igen.fr/ios/2023/12/ios-172-et-macos-142-ameliorent-leur-gestion-des-web-apps-141013);
  difetto aperto sui cookie di sessione nelle app sulla Home: [WebKit 272325](https://bugs.webkit.org/show_bug.cgi?id=272325) [da verificare].
- Avvisi web sull'iPhone solo con l'app aggiunta alla Home, da iOS 16.4 (lo dice già `docs/GUIDA-UTENTE.md`). [da verificare]
  [WebKit](https://webkit.org/blog/13878/web-push-for-web-apps-on-ios-and-ipados/)
- Chrome: `Page.getInstallabilityErrors` del protocollo di DevTools dice perché una pagina non è installabile. [da verificare]
  [protocollo di DevTools](https://chromedevtools.github.io/devtools-protocol/tot/Page/#method-getInstallabilityErrors)
- Skill `security-audit`: rapporto predefinito in `~/security-audit-skill/<repo>/run-<N>`, gravità `critical`/`high`/`medium`/`low`/
  `informational`, niente prove contro servizi in rete. [verificato] sul file della skill sul PC.
- Date delle giornate di Serie A dopo la 12ª. [da verificare]
- Produzione: stato della posta, profilo e scelte delle funzioni, pagine legali compilate. [da verificare] (punto 6 della porta).
