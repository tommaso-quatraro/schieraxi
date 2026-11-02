# MAPPA: SchieraXI

Leggi prima `CLAUDE.md` (regole e flusso). Qui: dove sta cosa. Per usare l'app: `README.md`.

## Comandi (Windows, dalla radice del repository)
- Ambiente: `python -m venv .venv`, poi `.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt`.
- Librerie: `requirements*.txt` hanno versioni fisse e hash e non si scrivono a mano. L'elenco sta in `requirements.in`, `requirements-dev.in` e `requirements-vincoli.in`; si rigenera con `.venv\Scripts\python.exe script\blocca_dipendenze.py`. Dependabot (`.github/dependabot.yml`) aggiorna solo le azioni di GitHub: le librerie Python le rigenererebbe con pip-compile.
  Su macOS e Linux: `.venv/bin/python` al posto di `.venv\Scripts\python.exe`.
- Test tutti: `.venv\Scripts\python.exe -m pytest -q`. Un file solo: `... -m pytest -q tests\test_rose_csv.py`.
- Server locale: `.venv\Scripts\python.exe -m fanta server` (ascolta su 127.0.0.1:8000). Elenco comandi: `-m fanta --help`.
- Modello: `-m fanta verifica` prima e dopo ogni modifica al modello.

## Cartelle e file
- `fanta/`: il server e la logica. «fanta» è il nome interno storico del pacchetto Python.
  - Server: `server.py` (FastAPI, tutte le rotte `/api/...`, controllo `X-Fanta`, limiti), `rotte_account.py` (account e
    amministrazione), `versioni.py` (ETag e If-Match), `calcolo.py` (coda dei calcoli pesanti, risposta 202, cache di
    `MAX_RISULTATI` = 256 voci), `contesto.py` (percorsi personali per richiesta), `percorsi.py` (cartelle e scritture sicure),
    `salute.py`, `stato_dati.py`.
  - Modello: `modello.py` (fantavoto atteso `mu` e probabilità di voto `p_voto`), `formazione.py` (11 titolari più panchina;
    livelli di rischio in `LIVELLI_RISCHIO`), `punteggio.py` (fantavoto con le regole della lega), `verifica.py` (backtest),
    `incertezza.py` (fascia «tra X e Y»), `affidabilita.py`, `diario.py` (giornate finite: schierata contro consigliata),
    `consigli.py` (formazione e spiegazioni, usato da app e comandi), `scambi.py`, `scambi_multi.py` (scambi N contro M),
    `asta.py` (solo prezzi consigliati), `stagione.py`, `coppe.py`.
  - Partite rinviate: `rinvii.py` (partita rinviata = non giocata e fuori dal turno di `turno.py`, anticipi esclusi: `turno.della_giornata`; anticipi = da 36 ore a 7 giorni prima del gruppo principale, al massimo 2, non fissano la scadenza: `turno.conta_per_scadenza`; regola della lega
    `partite_rinviate` aspetta/senza_voto/voto_ufficio, `voto_ufficio_rinviate`, eccezioni per giornata `rinvii_giornate`).
    Si applica in `consigli._calcola_previsioni` DOPO il modello e il «perché» (`modello.py` non cambia), in `fasi.andamento`
    (giornata in corso) e nel Diario; campo `rinvio` di `/api/oggi`, rotta `PUT /api/regole/rinvio`. Una partita rinviata non tiene
    aperta la giornata (`fasi.fine_giornata`, `fasi.recuperi_mancanti`, `riepilogo.recuperi`). Test `tests/test_rinvii.py`.
  - Dati della lega: `regole.py` (regole parametriche), `regole_testo.py`, `rose.py` (Excel, CSV, testo), `lega.py`,
    `squadre.py`, `movimenti.py`, `scelte.py`, `formazioni_lega.py`, `osservati.py`, `listone.py`, `nomi.py` (riconoscimento
    dei nomi tra fonti), `immagini.py`, `scarica_immagine.py` (solo indirizzi https pubblici, tetto 4 MB).
  - Fonti: `fonti/` (`fantacalcio.py`, `understat.py`, `footballdata.py`, `sosfanta.py`: funzioni pure, provate su estratti
    inventati in `tests/dati/`), `aggiorna.py` (riempie `dati/fanta.sqlite`), `archivio.py`, `rete.py` (si presenta come
    `SchieraXI/<versione>`), `scheda.py`, `fonti_attive.py` (interruttori delle fonti).
  - Risultati in diretta: `live.py` (un solo raccoglitore, cache in memoria e in `dati/live.json` che sopravvive ai riavvii; il risultato ufficiale vince). Rotta `GET /api/live`, vedi `docs/LIVE.md`. Risultati e voti la sera stessa: `pianificatore.giro_risultati`.
  - Avvisi: `notifiche.py` (titolo e testo sono `Frase`: `invia` li scrive nella lingua `lingua` delle impostazioni degli avvisi; l'inglese sta in `frasi_avvisi.py`, chiavi `n.*`), `push.py` (Web Push), `avvisi.py`, `avvisi_utenti.py`, `pianificatore.py`, `riscaldamento.py`. Copia della consigliata alla scadenza per ogni utente (copia automatica in `scelte` mai sopra una scelta vera + istantanea del Diario, negli ultimi 10 minuti, una volta sola, anche senza aprire l'app; `FANTA_COPIA_SCADENZA=0` la spegne): `copia_scadenza.py`, thread del servizio.
  - Account e posta: `account.py` (database sqlite, sessioni, inviti), `account_email.py`, `posta.py`, `social.py` (accesso
    con Google), `onboarding.py`, `limiti.py`, `importa_sicuro.py`, `gestione.py`.
  - Varie: `backup.py`, `controlli.py` (coerenza dei dati), `sentinella.py` (ogni ora: rifà in sola lettura le risposte di Oggi,
    Formazione, Scelta, Diario, widget e Live per ogni utente e controlla le invarianti di `INVARIANTI`; esito nella tabella
    `controlli`, avviso al proprietario alla prima rottura confermata; `script/server/sentinella.sh`), `registro.py` (file di registro con rotazione), `testi_legali.py`
    (pagine privacy, termini, crediti), `sotto_il_cofano.py`, `widget.py`, `da_fare.py`, `stato_utente.py`, `copertura.py`,
    `avatar.py` (`GET /api/avatar`).
- `fanta/web/`: la web app, HTML, CSS e JavaScript senza librerie né compilazione. File principali: `index.html`, `app.js`,
  `impostazioni.js`, `dafare.js`, `primoavvio.js`, `live.js`, `avatar.js`, `testi.js`, `stile.css`, `sw.js`, icone.
  Dopo una modifica il job `rilascia` alza `VERSIONE` in `fanta/web/sw.js`.
- `fanta/web/testi.js`: tutti i testi dell'interfaccia, in italiano e in inglese, con le stesse chiavi (`tests/test_testi.py`
  lo controlla). Nel codice si usa solo `t("chiave")`. I messaggi del server restano in italiano (iOS e Android li leggono): gli errori il web li traduce con le chiavi `err.*` (il testo italiano della chiave È il messaggio del server; `tests/test_testi.py` lo controlla parola per parola e fa fallire un messaggio nuovo senza traduzione). Le frasi che cambiano con i dati (Da fare, motivi, «perché», probabili, avvisi delle rose...) sono `Frase` di `fanta/frasi.py`: testo italiano + `frase` con chiave e parametri accanto (`X_frase`, `X_frasi`; contratto in `docs/API.md`, «Frasi con chiave»); il web le traduce con `traduciFrase`/`testoDi`/`testiDi` da `frase.<chiave>`. Frase nuova = una voce in `CATALOGO` (italiano) e due righe in `testi.js` (`frase.<chiave>`, italiano identico e inglese); `tests/test_frasi.py` controlla che combacino.
- `fanta/contenuti/sotto-il-cofano.json`: testi di «Sotto il cofano», fonte unica per web e iPhone. Ogni affermazione ha il
  suo punto di codice in `fonte_codice`.
- `fanta/novita.json`: storia delle versioni (numero, data, titolo, voci). `fanta/novita.d/`: voci in attesa, un file per pull request.
- `sito/`: il sito di presentazione. Statico: `index.html` (italiano), `en/index.html` (inglese), `stile.css`, `js/`, `sw.js`
  con `VERSIONE`. Niente script né stili dentro l'HTML (la Content-Security-Policy non ammette `unsafe-inline`).
  Il nome «SchieraXI» è in tracciati SVG (nessun font da scaricare): simboli `#wm` (grande) e `#wm-c` (compatto) in cima a ogni pagina,
  nome animato della prima schermata con classi `wm-*`. Si rigenera con `assets/marchio/wordmark/genera.py` (font Archivo, SIL OFL 1.1).
  Test: `tests/test_sito.py`, `tests/test_sito_html.py`.
- `ios/`: l'app per iPhone e iPad (SwiftUI). Ha i suoi test e il suo `README.md`.
  Mac di GitHub solo se servono: il job `ios` di `test.yml` parte se la pull request tocca `ios/` e non è in bozza (riparte quando la bozza diventa pronta); un push nuovo annulla le corse vecchie della stessa pull request, mai quelle su `main` (`tests/test_workflow_ios.py`).
  Screenshot: workflow `screenshot.yml` (a mano o etichetta `screenshot` sulla pull request non in bozza). «Fotografie dal vero»: `gh workflow run screenshot.yml -f scatti=vero` (o etichetta `screenshot-vero`), tre Mac in parallelo (iPhone piccolo, iPhone grande, iPad) con gli scenari `ios/fotografie/vero-*.json`: risposte vere del server con rose e nomi INVENTATI, prima della scadenza, a giornata in corso e a giornata finita. Si rifanno con `prove/fotografie_dal_vero.py` (copia dei dati, orologio fermo, niente rete, controllo dei nomi veri con le parole vietate private).
- `lega/esempio/`: la lega inventata (10 squadre finte, regole d'esempio). La lega vera sta fuori dal repository e si indica
  con la variabile `FANTA_LEGA=<cartella>`.
- `dati/`: database, cache e chiavi locali. Non va in git.
- `script/server/`: script del server (aggiornamento automatico, copie dei dati, promemoria, controllo di salute, sentinella).
- `script/ci/`: numero di versione e note di rilascio (`controlla_versione.py`, `assegna_versione.py`, `note_rilascio.py`);
  `metriche.py`: metriche della squadra per settimana (versioni, tempo PR→unione, etichette `regressione`, `dall-utente`,
  `fuori-piano`, coda iOS), solo lettura con `gh`: `python script/ci/metriche.py --settimane 4`.
- `tests/`: test pytest, un file per modulo. `conftest.py` e dati inventati in `tests/dati/`.
  `tests/strumenti/axe/`: axe-core (Deque, MPL-2.0) a versione fissa con hash, per i collaudi di accessibilità nel browser; mai dentro `fanta/web/` (`tests/test_strumenti_axe.py`).
- `prove/`: prove e strumenti di servizio (crea icone e marchio, misure di tempi, carico, `fotografie_dal_vero.py` per gli screenshot dell'app). `calibra_p_voto.py`: calibrazione di «gioca N%» senza probabili (misura prima/dopo, ristima i pesi di `modello.CALIBRAZIONE_SENZA_PROBABILI` con `--stima <stagioni passate>`).
- `docs/`: guide e contratti. Per chi usa l'app: `GUIDA-UTENTE.md`, `INSTALLAZIONE-IPHONE.md`. Per chi sviluppa: `API.md`,
  `API-SOTTO-IL-COFANO.md`, `ARCHITETTURA-INFORMAZIONI.md`, `AVATAR.md`, `COERENZA-WEB-IPHONE.md` (web e iPhone uguali), `DESIGN.md`, `STILE-SENZA-AI.md` (cosa evitare perché non sembri generata), `INCERTEZZA.md`, `LIVE.md`, `METODO.md` (come si lavora), `decisioni/` (decisioni di architettura, una per file, modello MADR in italiano),
  `SOTTO-IL-COFANO.md`, `STEMMA-DIVISA.md`, `STILI.md`.
- `.claude/settings.json`: divieti fissi per Claude Code (`gh pr merge`, push su `main`, push forzato, `--no-verify`); spiegati in `CLAUDE.md`.
- Radice: `README.md`, `CLAUDE.md`, `MAPPA.md`, `LICENSE` (AGPL-3.0), `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`,
  `TRADEMARKS.md`, `THIRD-PARTY-NOTICES.md`, `requirements.txt`, `requirements-dev.txt`, `.env.example`.

## Convenzioni
- Testi in italiano semplice. Le regole della lega non stanno mai nel codice.
- Quando cambi una schermata o una rotta: aggiorna `docs/GUIDA-UTENTE.md` o `docs/API.md` nella stessa pull request.
- Scritture sicure: `percorsi.scrivi_sicuro` (file temporaneo e poi rinomina). Le risorse personali usano ETag.
- Database degli account (`MIGRAZIONI` in `fanta/account.py`): una migrazione già rilasciata non si modifica mai. Ogni
  cambio di struttura è una voce nuova in fondo. `tests/test_migrazioni.py` controlla lo schema.
- Chiavi e segreti: solo in `.env` o in `dati/`, mai in git. `.env.example` mostra i nomi delle variabili, senza valori.

## Versioni e rilascio
- Pull request che tocca `fanta/`, `script/server/` o `requirements.txt`: serve `fanta/novita.d/<nome-breve>.json` senza numero.
  Il job `versione` blocca la pull request se manca. Regole in `CLAUDE.md`.
- Unione: il job `unisci` fa lo «squash» e cancella il ramo, solo per le pull request del proprietario non in bozza e con i
  controlli verdi. Una pull request in bozza non si unisce.
- Controllo del codice con ruff (solo controllo, niente riformattazione; regole in `ruff.toml`: `E9` sintassi, `F` errori sicuri): passo del job `test`, quindi blocca l'unione. ruff da PyPI con hash in `.github/ruff-requisiti.txt`. In locale: `ruff check fanta tests script prove`.
- Job `ambito` (`script/ci/controlla_ambito.py`, preso da `main`): i file della pull request devono stare nelle aree della riga «Aree: …» della descrizione (modello in `.github/PULL_REQUEST_TEMPLATE.md`; issue con il modulo «Lavoro», `.github/ISSUE_TEMPLATE/lavoro.yml`). Esenti i bot e le pull request di soli documenti. Per ora solo avvisi, fuori dai `needs` di `unisci`.
- Job `zizmor` (sicurezza dei workflow; zizmor da PyPI con hash in `.github/zizmor-requisiti.txt`): per ora solo avvisi, fuori dai `needs` di `unisci` (bloccante dopo #108). Azioni solo di GitHub e sempre per hash: le altre fanno fallire l'avvio dei controlli (`tests/test_workflow_controlli.py`).
- Controllo esterno della salute: `.github/workflows/salute.yml` (ogni 30 minuti sui server di GitHub, a mano con «Run workflow»): chiede la salute dell'app e la pagina del sito, 3 tentativi a qualche minuto di distanza, poi apre l'issue `P1` «Server non raggiungibile» (o la commenta) e la chiude quando tutto risponde. Serve perché `script/server/controllo-salute.sh` gira sul server stesso e, se il server si spegne, tace.
  Non usa segreti né azioni esterne; `issues: write` solo nel job che segnala.
- Job `rilascia` (in fila, un alla volta, dopo `unisci`): dà il numero di versione dopo il più alto, data e ora dell'unione,
  scrive la voce in `fanta/novita.json`, toglie il file da `fanta/novita.d/`, alza `VERSIONE` in `fanta/web/sw.js` se la
  pull request ha toccato `fanta/web/`, fa un commit su `main` e crea la release.
- Il server installa da `main` solo le cartelle che servono al server (`fanta`, `script/server`, `tests`, `requirements*.txt`).
- E solo commit firmati da GitHub (unioni squash e commit di versione creato via API) e librerie con l'hash atteso: `script/server/verifica-firme.sh`, `script/server/LEGGIMI.md`. Regole del repository (protezione di `main`, controlli obbligatori): impostazioni di GitHub del proprietario.

### Contratti delle release
- `v<numero>` (server): release creata dal job `rilascia`, con le voci della versione come note. Sempre con `--latest=false`.
- `build-<N>` (app per iPhone): file IPA non firmato per SideStore, creato dal workflow `ipa.yml`. È l'unica release marcata
  «Latest». Il numero `N` cresce sempre e non torna indietro.
- Sorgente per SideStore: `https://github.com/tommaso-quatraro/schieraxi/releases/latest/download/sorgente.json`. Punta alla
  release «Latest», cioè all'ultima `build-<N>`. Non rinominare `ipa.yml`: il contatore è per file.
- L'unione fatta con il token di GitHub non avvia i workflow `on: push`. Per questo il job `rilascia` lancia `ipa.yml`
  da solo quando la pull request ha toccato `ios/`.

## Contratti delle API
Client: la web app, l'app per iPhone e il widget. Dettagli in `docs/API.md`. Non rompere i campi esistenti: aggiungerne si può.
- Istantanea di tutte le rotte: `docs/openapi.json`, controllata da `tests/test_contratto_api.py`; si rifà con
  `python script/ci/aggiorna_openapi.py` quando l'API cambia apposta (poi si controllano web e iPhone, `docs/METODO.md`).
- Ogni richiesta diversa da GET e HEAD deve avere l'intestazione `X-Fanta: 1`, altrimenti 403. Corpo troppo grande: 413.
- Errori: JSON `{"detail": "testo in italiano"}`.
- 202 = «sto calcolando» (coda, solo in modo multiutente): il client riprova. 429 con `Retry-After` = limiti per utente.
- Scelta della giornata: `GET /api/scelta` dà anche `salvata` (data e ora) e `tipo`; web e iPhone mostrano in Formazione lo stato della scelta confrontando gli 11 mostrati con quelli salvati. Formazione non valida in `POST /api/formazione/valuta`: `400` con `codice: "formazione_non_valida"` (`consigli.FormazioneNonValida`); i client non cancellano la scelta da soli.
- Formazione chiusa (dal 2/11/2026): dopo la scadenza della lega `POST /api/formazione/valuta` con `salva` e `DELETE /api/scelta` rispondono 409 con `codice: "formazione_chiusa"`, per tutti (`server._formazione_chiusa`, regola `fasi.iniziata`). La copia automatica (`copia_scadenza.py`) scrive prima della scadenza e non passa dalle rotte.
- Titolari incerti con una riserva quasi sicura: lista `incerti` in ogni modulo di `/api/formazione` (`consigli.incerti`, soglie 50% e 80%).
- A giornata iniziata ogni scheda ha anche `fv_preso` (fantavoto preso, `fasi.schede_a_giornata_iniziata`): il web mostra quello al posto di «gioca N%» (`esitoPartita` in `app.js`).
- ETag e If-Match su scelta, osservati, rose, regole e avvisi. Con un If-Match vecchio: 412. Senza If-Match si scrive come sempre.
- Partite rinviate: `PUT /api/regole/rinvio` (eccezione per una giornata, stesso ETag delle regole), campo `rinvio` in
  `/api/oggi` e nelle schede dei giocatori; contratto in `docs/API.md`, «Partite rinviate».
- Account: rotte `/api/account/*`. Con `nativo: true` il token torna nel corpo (l'app per iPhone lo manda come
  `Authorization: Bearer`). La web app usa il cookie `fanta_sessione`, HttpOnly.
- Token del widget iPhone: `fw_...`, vale 90 giorni, creato con `POST /api/account/token-widget`. Apre solo `GET /api/oggi`,
  `GET /api/widget` e `GET /api/live`. Ogni altra rotta risponde 403. Cambio password e «esci da tutti» lo revocano.
- Giocatori: all'utente una sola percentuale sul giocare, «gioca N%» (`p_voto`); `percentuale` delle probabili non si mostra e
  `titolarita` va a parole. Dopo la scadenza `GET /api/formazione` ha `iniziata: true`, `titolarita: null` e `stato_partita`
  (`fanta/fasi.py`, `formazione_a_giornata_iniziata`). Dettagli in `docs/API.md`, «Giocatori».
- Scambi: `GET /api/scambi/proposte`, `GET /api/scambi/analizza`, `POST /api/scambi/da-testo`, `GET /api/scambi/limite`. `analizza` e `da-testo` passano dallo stesso `limiti.analisi_scambio`.
- Ogni parametro `giornata` delle rotte ha `ge=1, le=MAX_GIORNATA` (422, mai 500): `tests/test_giornata_limiti.py` trova da solo le rotte nuove.
- Rose dalle schermate di Leghe (OCR dell'app iPhone): testo `ruolo;nome;club;prezzo` (intestazione nella prima riga, una riga con una
  cella sola = fantasquadra, `crediti;N`) a `POST /api/rose/anteprima` e `/api/rose/testo`; `rose._estrai_schermate`. Contratto in `docs/API.md`.

## Modo multiutente (`FANTA_MULTIUTENTE=1`, obbligatorio su un server raggiungibile da altri)
- Spento: nessun accesso, file in `lega/` e `dati/`; chi chiede ha i poteri dell'amministratore, quindi il server risponde
  solo a richieste dirette da 127.0.0.1/::1 senza intestazioni di proxy (le altre: 403, avviso nel log all'avvio).
- Acceso: senza sessione `/api/*` risponde 401 (tranne accesso, registrazione e recupero). Una cartella per utente in
  `dati/utenti/<id>/`, database `dati/account.sqlite`.
- L'id utente viene solo dalla sessione, mai da un parametro. Ogni rotta personale usa `contesto.py` e va coperta da
  `tests/test_isolamento.py`.
- Tetti per utente in `fanta/limiti.py`: importazioni di rose, ricerche di scambi (`FANTA_MAX_SCAMBI`), immagini da indirizzo web.
- Registrazione: `FANTA_REGISTRAZIONE=invito|email|aperta` (predefinito `invito`).
- Posta: `FANTA_MAIL=spento|log|smtp|resend` (predefinito `spento`: nessun invio; `log` scrive in `dati/posta.log` solo che un
  messaggio sarebbe partito, mai il codice). Con registrazione `aperta` o `email` servono `smtp` o `resend`.
  SMTP (`fanta/posta.py`): `FANTA_SMTP_HOST`, `FANTA_SMTP_PORT` (465 = TLS subito, 587 = STARTTLS; mai in chiaro), `FANTA_SMTP_UTENTE`,
  `FANTA_MAIL_DA` (stessa casella dell'utente, così SPF e DKIM tornano), password in un file a parte indicato da
  `FANTA_SMTP_PASSWORD_FILE` (una riga, permessi 600: altrimenti non si usa; mai in `ambiente.env`). Tetto `FANTA_MAIL_MAX_ORA`
  (predefinito 50 invii veri all'ora; oltre, `posta_tetto_ora` nel registro di sicurezza). Chi spedisce, nella Privacy: `FANTA_POSTA_FORNITORE`.
- Registri: righe tenute 30 giorni, indirizzi accorciati (IPv4 senza l'ultimo numero, IPv6 solo /64).
- Accesso con Google: spento (404) senza `FANTA_GOOGLE_CLIENT_ID` e `FANTA_GOOGLE_CLIENT_SECRET`.
- Pagine legali (`testi_legali.py`): `FANTA_TITOLARE`, `FANTA_CONTATTO`, `FANTA_SORGENTE`, `FANTA_HOSTING`, `FANTA_BACKUP_GIORNI`,
  `FANTA_REGISTRO_WEB_GIORNI` (senza: frasi generiche). `tests/test_legale.py` lega i testi al codice: se cambi cookie, durate, Google o widget, cambia la pagina,
  la data «aggiornato» e `account.VERSIONE_TERMINI`.

## Fonti dati
- Ogni fonte ha un suo interruttore: `FANTA_FONTE_<NOME>=1`, oppure l'amministratore la accende da `dati/fonti.json`
  (rotte `/api/admin/fonti`). Il predefinito sta in `fanta/fonti_attive.py`.
- Le fonti in ombra si raccolgono e si conservano, ma il modello non le usa finché una misura non le promuove.
- Le richieste sono poche, una alla volta e con pausa, e si salvano in cache.
- Le foto dei calciatori non sono nel repository: i volti sono illustrazioni generate dal codice (`docs/AVATAR.md`).

## Punti delicati
- Nomi dei giocatori tra fonti diverse: `nomi.py`. Gli abbinamenti incerti non si devono prendere per buoni.
  Un nome abbreviato è sicuro solo con ruolo E squadra uguali al listone; con uno dei due diverso mai. Misura: `tests/corpus_nomi.py`
  (anche le varianti OCR, `genera_ocr`) e `prove/misura_nomi.py --vero` sul listone salvato in locale.
- `dati/` non va mai in git né nei log. Il backup (`backup.py`) non contiene chiavi né iscrizioni alle notifiche.
- Il ripristino del backup salva prima lo stato di prima in `dati/backup-prima-del-ripristino.json` e non cambia le scelte delle giornate già chiuse (`backup.unisci_scelte`, regola di `fasi.iniziata`).
- Rifare tutto il servizio da una copia notturna (`backup-dati.sh`): `docs/RIPRISTINO-SERVER.md` (provato il 2/11/2026; cosa non c'è nella copia e cosa succede).
- Ore tranquille (`silenzio`, `silenzio_da`, `silenzio_a`): bloccano l'invio degli avvisi. La prova le ignora.
- Il tempo della lega (`scadenza_minuti`, `prima_giornata_lega`) sta nelle regole della lega, non nel codice.
- Il modello non legge le quote dei bookmaker: non reintrodurle senza prima e dopo con `verifica`.
- `fanta/avatar_tratti.json` non è nel repository: senza di lui tutti i volti hanno la carnagione neutra.
