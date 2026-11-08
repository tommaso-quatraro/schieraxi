# Ondata 2 del piano di crescita: spec

Data: 8/11/2026. Piano: `docs/superpowers/plans/2026-11-08-ondata-2.md`. Ondata 1 (comandi del coordinatore, controlli delle PR,
coerenza come dati): `docs/superpowers/plans/2026-11-06-squadra-come-codice.md`.

## 1. Perché

L'ondata 1 ha trasformato in comandi e controlli i passi che il coordinatore faceva a mano. Restano quattro punti da cui nascono
ancora errori e lavoro ripetuto:

- **Testi copiati a mano.** La web ha tutti i testi in `fanta/web/testi.js` (italiano e inglese); l'iPhone li riscrive nel suo codice
  e una trentina di test iOS li confrontano con `testi.js` leggendolo riga per riga sul Mac. Una parola cambiata su un lato si scopre
  solo dopo una corsa iOS da 20 minuti, e le differenze aperte stanno in `docs/coerenza/`.
- **Un file solo per tutta la web.** `fanta/web/app.js` ha 4.923 righe: ogni PR della web lo tocca, i conflitti sono frequenti e
  gli agenti non riescono a leggerlo intero.
- **Nessun posto per provare dal vero.** Una versione nuova si vede per la prima volta in produzione. Le foto della web si fanno
  a mano (`prove/foto_web/foto.py`); le foto iOS a volte coprono più schermate del necessario (#476, punto 3).
- **Il client iPhone può staccarsi dall'API senza che nessuno se ne accorga.** I modelli Swift sono quasi tutti facoltativi
  («un campo mancante non deve rompere la schermata»): se il server rinomina un campo, l'iPhone mostra un vuoto e nessun test fallisce.

In più, prima di aprire l'app agli altri (#168), servono limiti per utente che impediscano a una persona sola di rallentare il
servizio per tutti (#483).

## 2. Obiettivi, non obiettivi, fallimenti

Obiettivi (decisi dall'utente il 6/11; la lettera è quella del piano):
- **(a)** una sola fonte per i testi di web, iPhone e inglese, con i risultati generati e controllati dai test;
- **(b)** `app.js` diviso in moduli ES, senza librerie né compilazione, con un comportamento identico;
- **(c)** ambiente di prova online sullo stesso server della produzione: seconda copia dell'app con la lega d'esempio, accesso
  separato, aggiornata a ogni rilascio e collaudata da sola dopo il rilascio. Qui si consegnano solo la **proposta** e gli script nel
  repository: le modifiche al server le vede e le approva l'utente prima;
- **(d)** regressione visiva della web in CI: foto confrontate con un riferimento, con una soglia e un modo chiaro per aggiornarle;
- **(e)** foto iOS mirate: solo le schermate toccate dalla PR, con una mappa da file a schermata più precisa;
- **(f)** il client iPhone non si stacca dall'API: modelli generati da `docs/openapi.json` o un controllo che li confronti;
- **(g)** limiti di risorse per utente (#483), scritti come requisiti di qualità del servizio.

Non obiettivi: funzioni nuove per chi usa l'app; l'iPhone in inglese; Android; un nuovo aspetto della web; un archivio di calcio
inventato (vedi §6); spese.

Sarebbe un fallimento, anche con tutti i test verdi:
- una schermata della web che cambia aspetto o comportamento per la divisione in moduli;
- la produzione toccata dall'ambiente di prova (dati, servizio, aggiornamenti, avvisi agli utenti veri);
- una foto con nomi veri di calciatori pubblicata negli artifact del repository pubblico;
- un utente normale che vede «Troppe richieste» usando l'app in modo normale;
- un controllo che blocca le PR per falsi allarmi (foto instabili, campi Swift calcolati sul telefono scambiati per campi del server).

## 3. Vincoli

- Repository pubblico: niente indirizzi, nomi, chiavi; nei documenti `<dominio>`, `<utente>`, `<indirizzo-del-server>`.
- Python della sola libreria standard per gli script nuovi (Pillow c'è già fra le librerie dei test; Playwright solo in ambienti
  a parte, come `prove/foto_web/`, con versione e hash fissati).
- Web senza librerie né compilazione (`MAPPA.md`). Content-Security-Policy `script-src 'self'`: niente script dentro l'HTML.
- iOS senza Mac in locale: ogni prova iOS costa una corsa sui Mac di GitHub (5 in tutto).
- Tetti: 4 PR aperte per server + web (sito e CI compresi), 3 per iOS; le PR di soli documenti o soli test non contano
  [verificato: `script/squadra/aree.py`, `gruppo_di` restituisce nessun gruppo per le sole aree neutre].
- Mai due agenti sugli stessi file. Ogni ramo finisce in una PR; l'unione la fa il job `unisci`.

## 4. Fatti che cambiano il disegno

- `docs/openapi.json` descrive i corpi delle richieste (46 modelli) ma **nessuna risposta**: 0 operazioni su 128 hanno lo schema
  della risposta, le rotte restituiscono dizionari [verificato]. Quindi oggi non si possono generare i modelli Swift delle risposte
  dall'OpenAPI.
- `ios/fotografie/vero-*.json` sono risposte vere del server con nomi inventati, per 80 indirizzi e un momento fisso (`adesso`).
  Coprono le letture principali della web (oggi, formazione, scelta, giocatori, confronto, mercato, classifica, diario, scambi,
  regole, rose, squadre, stato, live, widget) [verificato]. Mancano novità, avatar, onboarding e le rotte di amministrazione.
- `lega/esempio/` ha squadre inventate ma calciatori veri (nomi e id del listone) [verificato]: senza l'archivio di calcio
  `dati/fanta.sqlite` le schermate sono vuote, e in CI quell'archivio non c'è.
- 86 file di test Python nominano `app.js` e molti ne estraggono pezzi di codice per farli girare con node; 5 file di test iOS
  leggono `fanta/web/app.js` dal disco (`OggiComeLaWebTests`, `NovitaComeLaWebTests`, `PartiteRisultatoUfficialeTests`,
  `VociLegaWeb`, `ModificaAManoModuliTests`) [verificato]. Spostare il codice di `app.js` li rompe, se prima non leggono da un posto solo.
- Con gli account accesi i file statici serviti senza sessione sono un elenco fisso (`STATICI` e `STATICI_PREFISSI` in
  `fanta/rotte_account.py`) [verificato]: un file JavaScript nuovo non entra nella pagina d'accesso se non sta lì.
- `testi.js`: circa 1.800 chiavi per lingua con una cinquantina di prefissi (`frase.`, `err.`, `mercato.`, `lega.`, …) [verificato].
  Il formato «una chiave per riga» lo leggono `tests/test_testi.py`, `tests/test_frasi.py` e l'aiuto `TestiWeb` dei test iOS.
- L'interfaccia dell'iPhone è solo in italiano (`ios/Sources/Domain/LinguaServer.swift`) [verificato].
- PR aperte che toccano gli stessi file: #487 (`testi.js`, `server.py`, `rotte_account.py`, `consigli.py`, `backup.py`,
  `tests/test_server.py`), #490 (`script/squadra/foto.json`, `pr_pronta.py`, `pulisci.py`, `LEGGIMI.md`), #488 (`CLAUDE.md`,
  `docs/METODO.md`) [verificato l'8/11]. L'ondata 2 parte su quei file solo dopo la loro unione.

## 5. Il disegno, lavoro per lavoro

### (a) Catalogo unico dei testi
- **Fonte:** `fanta/testi/<prefisso>.json`, un file per prefisso della chiave (`oggi.json` contiene solo chiavi `oggi.*`). Ogni voce
  ha `it` e `en` e, se serve, `nota`. I plurali restano coppie `.one` / `.other`, i segnaposto `{nome}`.
- **Web:** `script/testi.py --scrivi` genera la parte dei dati di `fanta/web/testi.js` (l'oggetto `TESTI`, fra due righe-segno),
  una chiave per riga come oggi. Le funzioni di `testi.js` (`t`, `tp`, `traduciErrore`, …) restano scritte a mano. `--controlla`
  esce con 1 se `testi.js` non è quello generato.
- **iPhone:** l'iPhone dichiara quali chiavi usa in `ios/testi/<prefisso>.txt`. Il generatore scrive
  `ios/Sources/Support/Catalogo/<Prefisso>.swift` (costanti e funzioni Swift, solo italiano). Una PR della web che cambia il testo
  di una chiave usata dall'iPhone rigenera anche il file Swift: il cambio arriva ai due lati nella stessa PR, per costruzione.
- **Inglese:** resta solo sulla web; il controllo «ogni chiave italiana ha la sua inglese» resta in `tests/test_testi.py`.
- Le frasi del server (`fanta/frasi.py`) e i messaggi d'errore restano dove sono; le loro traduzioni (`frase.*`, `err.*`) entrano
  nel catalogo come gli altri testi e i test di oggi continuano a confrontarle con il server.
- Il passaggio nel catalogo non cambia nessun testo: i dizionari prima e dopo sono uguali (cambia solo l'ordine delle righe di `testi.js`).
- Decisione: `docs/decisioni/0010-una-sola-fonte-per-i-testi.md`.

### (b) Web a moduli
- `fanta/web/app.js` diventa il modulo d'ingresso (`<script type="module">`), che importa i moduli di `fanta/web/moduli/`, uno per
  sezione di oggi (base, copia, pezzi, navigazione, Oggi, formazione, mercato, scheda, foglio, scambi, lega, stemma, novità, regole,
  account, Google) e alla fine contiene solo l'avvio.
- Gli altri script (`testi.js`, `avatar.js`, `live.js`, `dafare.js`, `anteprima.js`, `primoavvio.js`, `impostazioni.js`) restano
  script classici in questa ondata; `impostazioni.js` prende `defer`, così l'ordine di esecuzione resta quello di oggi.
- I nomi che gli script classici, `index.html` e gli strumenti di prova (`prove/foto_web/foto.py`) usano restano raggiungibili da
  `window`, e un test lo controlla.
- I moduli non fanno niente quando si caricano: registrare gestori o far partire timer avviene in funzioni `monta…()` chiamate da
  `app.js` nell'ordine di oggi. Un nome importato non si riassegna mai (in un modulo ES darebbe errore solo al primo uso).
- Prima di spostare codice, tutti i test leggono il codice della web da un aiuto solo (`tests/codice_web.py` per Python,
  `CodiceWeb.swift` per iOS), che unisce `app.js` e i moduli.
- `ios/Tests/file-esterni.txt` accetta anche cartelle (`fanta/web/moduli/`), così spostare codice fra moduli non tocca `ios/`.
- Ogni PR della divisione dimostra «comportamento identico» con zero scene diverse nella regressione visiva (d).

### (c) Ambiente di prova (proposta per l'utente)
- Seconda copia dell'app sullo stesso server: cartella `~/schieraxi-prova`, servizio `schieraxi-prova`, `127.0.0.1:8001`,
  indirizzo `https://prova.<dominio>` dietro nginx con certificato proprio e `X-Robots-Tag: noindex`.
- Accesso separato: database degli account suo, registrazione solo con invito, un account di collaudo con password nei segreti di
  GitHub; nessun utente della produzione esiste lì.
- Dati: la lega d'esempio per l'account di collaudo; l'archivio dei dati di calcio è una copia di quello della produzione (solo dati di
  calcio pubblici, svuotata degli esiti della sentinella), rifatta ogni notte e a ogni installazione.
- Spento tutto ciò che parla con l'esterno o con gli utenti: pianificatore, registro delle giornate, copia alla scadenza,
  riscaldamento, posta, avvisi, fonti. Nessuna riga di crontab per dati, avvisi o copie.
- Isolamento: lo stesso utente del server, ma il servizio non vede la cartella dei dati della produzione (`InaccessiblePaths`),
  scrive solo nella sua cartella `dati`, ha memoria e CPU limitate (`MemoryMax`, `CPUWeight`, `Nice=19`).
- Aggiornamento: lo stesso `aggiorna-app.sh` con `SCHIERAXI_ISTANZA=prova` (cartelle, servizio, porta e stato suoi), senza
  aspettare la fine delle partite: la prova riceve ogni versione **prima** della produzione.
- Collaudo dopo il rilascio: un workflow su GitHub, ogni 20 minuti, vede se la prova ha l'ultima versione `v<N>` non ancora
  collaudata, entra con l'account di collaudo, apre le schermate principali e controlla errori della console, risposte 5xx,
  scorrimento di lato e accessibilità; se qualcosa non va apre un'issue `P1`. Nessuna foto negli artifact (calciatori veri).
- Le modifiche al server sono un elenco esatto di comandi nel piano (§4), con il ritorno indietro; la PR degli script resta in bozza
  fino all'ok dell'utente, perché `aggiorna-app.sh` si installa da solo sul server.

### (d) Regressione visiva della web
- Un server finto (libreria standard) serve `fanta/web/` di una cartella e risponde alle `/api/...` con `ios/fotografie/vero-prima.json`:
  stessi dati, nomi inventati, orologio fermo sul momento della registrazione. Le stesse risposte delle foto dell'iPhone.
- **Riferimento = le foto di `main`** (la base della PR) scattate nella stessa corsa, con lo stesso Chrome. Niente immagini nel
  repository; il riferimento si aggiorna da solo quando la PR si unisce.
- 11 scene × 2 larghezze (390 e 1440 px) × 2 temi. Una scena è «diversa» se più dello 0,1% dei pixel cambia di oltre 16/255 su un
  canale, o se cambia la misura della pagina.
- La PR dichiara cosa cambia con una riga `Aspetto: <scene>` (o `Aspetto: nessuno`). Fallisce solo se cambia una scena non dichiarata.
  Le immagini delle scene diverse (base, PR, differenza) vanno negli artifact: hanno solo nomi inventati.
- Prima solo avviso, in un workflow suo; dopo una decina di corse senza falsi allarmi diventa un job bloccante di `test.yml`.

### (e) Foto iOS mirate
- Un grafo dei tipi Swift (chi nomina chi) ricavato dai sorgenti di `ios/`; per ogni schermata di `ios/scripts/screenshot.sh` una o
  più viste radice in `script/squadra/foto.json` (sezione nuova `radici`). Un file cambiato → le schermate le cui radici lo
  raggiungono. Un file che raggiunge più di 12 schermate vale «principali».
- Le regole a mano di oggi in `foto.json` restano e vincono sul grafo (servono per risorse, `project.yml` e casi speciali).
- Raccordo con #476 punto 3 (PR #490, altro agente): quella PR corregge a mano la regola del file dei crediti; (e) parte dopo la sua
  unione, non riscrive le sue regole e aggiunge un test che quel caso esca uguale anche dal grafo.

### (f) Contratto fra iPhone e server
- Generare i modelli Swift dall'OpenAPI oggi non si può (§4). Al loro posto due controlli:
  1. **su Linux, in ogni PR** (secondi): ogni campo dei modelli `Decodable` dell'iPhone, tradotto nel nome JSON (`pVoto` →
     `p_voto`, o il valore di `CodingKeys`), deve comparire come chiave nel codice del server (`fanta/`). Le eccezioni stanno in un
     file con il motivo. Prende le rinomine e i campi tolti nella PR stessa;
  2. **sul Mac** (test Swift): tutte le risposte di `ios/fotografie/vero-*.json` si decodificano con i modelli dell'app. Prende i tipi
     sbagliati, con i dati veri dell'ultima registrazione.
- Il comando `giro` avvisa quando `docs/openapi.json` è cambiato dopo l'ultima registrazione delle fotografie dal vero.
- I corpi delle richieste generati dall'OpenAPI (che li descrive) restano un'idea `P3`.

### (g) Limiti per utente (#483)
Requisiti, scritti come qualità del servizio (il dettaglio è presso chi cura il progetto):
- **R1** un utente non può avere più di 4 calcoli pesanti in coda o in corso insieme, né occupare più di un quarto della memoria
  condivisa dei risultati; oltre, risponde 429 con `Retry-After` solo a lui;
- **R2** nessuna azione di un utente svuota i risultati già calcolati per gli altri; le azioni ripetibili che costano calcoli hanno
  un tetto per ora per utente;
- **R3** l'importazione delle rose ha lo stesso tetto di lavoro per ogni formato (celle, memoria, tempo) e non blocca le scritture
  degli altri utenti mentre lavora;
- **R4** ogni invio di un avviso verso l'esterno ha un tempo massimo totale; la prova degli avvisi ha un tetto per utente; un giro
  di avvisi non si ferma per un destinatario lento;
- **R5** la memoria della «consigliata già mostrata» (#335) ha una quota per utente: le voci di uno non fanno dimenticare quelle degli altri;
- **R6** la cancellazione dell'account è definitiva anche con lavori in corso: niente dati ricreati dopo, errori non muti, un
  controllo che trova le cartelle senza account.
Messaggi d'errore: quelli dei limiti di oggi, già tradotti; un messaggio nuovo va nel catalogo, dopo (a).

## 6. Scelte mie (le può cambiare l'utente)

- Scelta mia: catalogo in JSON dentro `fanta/testi/` e `testi.js` generato, invece di tenere `testi.js` come fonte, perché un file
  per prefisso riduce i conflitti, i programmi leggono JSON senza indovinare il JavaScript, e il server potrà usarlo per gli avvisi in
  inglese. Costo se sbagliata: medio (si torna a scrivere `testi.js` a mano togliendo il generatore).
- Scelta mia: l'iPhone dichiara le chiavi che usa (`ios/testi/*.txt`) invece di ricevere tutto il catalogo, perché altrimenti ogni PR
  della web toccherebbe `ios/` e farebbe partire i Mac. Costo se sbagliata: basso.
- Scelta mia: niente generazione dei modelli Swift delle risposte; due controlli al loro posto, perché l'OpenAPI non descrive le
  risposte e riscrivere 1.350 righe di modelli con la loro logica senza Mac è un rischio grande. Costo se sbagliata: medio
  (descrivere le risposte sul server e generare dopo).
- Scelta mia: riferimento della regressione visiva = `main` nella stessa corsa, invece di immagini salvate nel repository, perché
  niente file pesanti in git, nessun passo per aggiornarle e nessun falso allarme quando cambia il Chrome di GitHub. Costo se
  sbagliata: basso (le foto di riferimento salvate si aggiungono dopo).
- Scelta mia: server finto con le risposte registrate per la regressione visiva, invece di un archivio di calcio inventato, perché
  l'archivio inventato è un progetto a sé (il modello ha bisogno di stagioni intere coerenti) e le risposte registrate ci sono già.
  Costo se sbagliata: medio (scene non coperte finché le registrazioni non si allargano).
- Scelta mia: ambiente di prova con lo stesso utente del server e il servizio chiuso dentro la sua cartella, invece di un utente
  nuovo, perché costa metà comandi e la copia dell'archivio resta semplice. Costo se sbagliata: un pomeriggio per passare a un utente nuovo.
- Scelta mia: la prova si aggiorna prima della produzione e senza aspettare le partite. Il «cancello» (la produzione installa solo
  le versioni collaudate) è una scelta dell'utente, dopo (piano §8).
- Scelta mia: numeri di (g) come costanti in `fanta/limiti.py` con variabile d'ambiente per cambiarli, come `FANTA_MAX_SCAMBI`.
  Costo se sbagliati: basso, si cambiano senza codice.
- Scelta mia: `MAPPA.md`, `docs/METODO.md` e le decisioni nuove si aggiornano in una PR di documenti alla fine dell'ondata (compito Z);
  solo il catalogo (a) cambia subito `MAPPA.md` e `CLAUDE.md`, perché da quel momento i testi nuovi si scrivono altrove.

## 7. Cosa resta a chi costruisce

Nomi interni, struttura delle funzioni, messaggi dei test, l'ordine delle chiavi nel catalogo dentro un file, quali scene esatte
entrano nella regressione visiva (purché coprano le quattro schede, scheda, confronto, diario, regole, scambi e impostazioni), il
dettaglio del grafo dei tipi, i numeri di (g) se una misura mostra che sono sbagliati (scrivendolo nella PR).

## 8. Controllo del costruttore (fatto da me, senza sotto-agente)

Domande che un costruttore avrebbe fatto, e dove sta la risposta:
- «Il catalogo cambia i testi?» No, solo l'ordine delle righe (§5 a; piano A1).
- «Chi tocca per primo i test iOS che leggono `app.js`?» La PR B1; i lavori iOS del catalogo su quelle schermate vengono dopo (piano §2).
- «Con quali dati gira la regressione visiva in CI?» Con le risposte registrate di `ios/fotografie/` (§5 d).
- «Il collaudo della prova pubblica le foto?» No (§5 c).
- «Che cosa si fa se `.js` arriva come `text/plain` sul server locale di Windows?» È [da verificare]; se succede, B1 registra il tipo
  accanto all'elenco dei file pubblici (piano B1).
- Restano all'utente: l'ok alla proposta del server, il record DNS, il cancello (piano §8).
