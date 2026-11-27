# SchieraXI: guida per chi gestisce l'app

Questa guida è per chi gestisce il server e fa entrare gli amici. Quello che vede chi usa l'app sta in
[GUIDA-UTENTE.md](GUIDA-UTENTE.md); qui ci sono solo le cose che vede o fa chi gestisce. Per il server stesso: gli script e
l'aggiornamento automatico in `script/server/LEGGIMI.md`, il ripristino in [RIPRISTINO-SERVER.md](RIPRISTINO-SERVER.md).
Nei comandi qui sotto l'indirizzo del server si scrive `<indirizzo-del-server>`.

Tutto quello che segue sta in **Impostazioni › Gestione**, che compare solo a chi gestisce l'app (nell'elenco degli utenti ha
accanto «amministratore»). Sull'iPhone la Gestione ha solo i dati, **Collegamento** e **Certificato**: inviti, password, utenti,
errori e commenti si gestiscono solo dalla web.

## 1. Iscrizioni e inviti

### Solo con invito, oppure aperte

Di norma si entra **solo con un invito** (qui sotto, «Con gli inviti»): è così anche dopo l'aggiornamento del 26/11/2026, finché la
variabile `FANTA_REGISTRAZIONE` non c'è. Le iscrizioni aperte non si accendono da sole: si aprono a mano, quando hai deciso di
aprirle e sai come togliere un account che non vuoi.

**Aprire le iscrizioni**, sul server:

1. `sudoedit /etc/schieraxi/fantacalcio.env` e scrivi la riga `FANTA_REGISTRAZIONE=aperta` (se c'è già una riga
   `FANTA_REGISTRAZIONE=...`, cambia quella);
2. `sudo systemctl restart fantacalcio`;
3. controllo: `curl -s -H "X-Fanta: 1" http://127.0.0.1:8000/api/regole` risponde con `"registrazione":"aperta"`.

**Richiudere**: togli la riga (oppure scrivi `FANTA_REGISTRAZIONE=invito`) e `sudo systemctl restart fantacalcio`; il controllo
risponde con `"registrazione":"invito"`. Chi ha già un account non perde niente. Un valore scritto male (per esempio `chiusa`) vale
come `invito`: le iscrizioni non si aprono mai per sbaglio.

C'è anche `FANTA_REGISTRAZIONE=email`: serve l'invito **e** un'email, e l'account nasce solo dopo il codice a 6 cifre arrivato a
quell'indirizzo. Funziona solo con l'invio delle email acceso (sezione 2, in fondo); se è spento, chi si registra legge «Su questo
server l'iscrizione con l'email non è disponibile» e l'account non nasce.

### Iscrizioni aperte

Con `FANTA_REGISTRAZIONE=aperta` chi vuole apre l'app, tocca **Registrati**, sceglie nome utente e password (l'email è facoltativa) ed
entra subito, senza invito: dopo il codice di recupero parte il primo avvio (rose, squadra, tempi). In **Impostazioni › Gestione**
c'è **Iscrizioni** con la frase «Le iscrizioni sono aperte: chi vuole si registra da solo dalla schermata d'accesso, finché ci sono
posti.»; **Nuovo invito** e **Inviti aperti** non ci sono, perché non servono. Quando gli utenti arrivano al numero massimo, sotto la
frase c'è l'avviso **Posti pieni** e chi prova a registrarsi legge «Iscrizioni chiuse: siamo al completo».

Due tetti tengono lontano chi trova il sito e prova a riempirlo, tutti e due nelle variabili del servizio:

- `MAX_UTENTI`: quanti account al massimo (15 se manca; vale anche con gli inviti);
- `FANTA_ISCRIZIONI_GIORNO`: quanti account nuovi senza invito in 24 ore (5 se manca). Oltre, chi si registra legge «Per oggi le
  iscrizioni sono chiuse: riprova domani». Il giorno in cui mandi il link dell'app a tutti gli amici alzalo (per esempio a 12) e poi
  rimettilo com'era.

In più la web ha un campo nascosto che una persona non vede: se un programma lo compila, l'account non nasce (nel registro di
**Errori recenti** compare «Registrazione fermata: modulo compilato da un programma»). E da uno stesso indirizzo internet si fanno
pochi tentativi non riusciti all'ora.

Per cambiare una variabile, sul server: `sudoedit /etc/schieraxi/fantacalcio.env`, scrivi la riga (per esempio `MAX_UTENTI=12`),
poi `sudo systemctl restart fantacalcio`.

Con le iscrizioni aperte il modulo non chiede codici: un amico che deve gestire l'app con te si registra come tutti e poi, sul server,
`.venv/bin/python -m fanta utente-ruolo --utente <nome> --ruolo admin`.

Se un altro amministratore ha perso password, codice di recupero ed email, dalla web non puoi creargli il codice: sul server
riportalo a utente normale (`utente-ruolo --utente <nome> --ruolo normale`), crea il codice da Gestione, e dopo che è rientrato
ridagli il ruolo di amministratore.

### Con gli inviti

**Impostazioni › Gestione › Nuovo invito** crea il link da mandare (**Condividi l'invito** o **Copia il messaggio**): apre la
registrazione con il codice già scritto e vale 7 giorni. Sotto c'è anche il codice, per chi usa l'app per iPhone. L'etichetta
serve a ricordare per chi era; con la casella **Il nuovo account sarà amministratore** chi entra gestisce l'app anche lui (solo con
**Quante persone** a 1). Con la casella accesa **Crea l'invito** chiede prima conferma, e dopo ogni invito la casella si spegne da
sola: l'invito dopo è di nuovo per un utente normale. Mentre l'invito si crea il pulsante resta spento (un doppio tocco non crea due
inviti).

Per far entrare tutta una chat di amici con un solo link crea un **invito di gruppo**: in **Quante persone** scrivi quanti
sono (con **+** e **−**, da 1 a 30), poi **Crea l'invito**. L'esito dice per quante persone vale (per esempio «Invito per «Lega»,
valido 7 giorni, per 12 persone.») e il link si manda nella chat. Ognuno si registra con lo stesso link finché ci sono posti; in
**Inviti aperti** l'invito dice quanti posti restano. Dal server si fa lo stesso con
`.venv/bin/python -m fanta invito --etichetta "Lega" --usi 12` (il codice si vede una volta sola), da mandare come
`https://<indirizzo-del-server>/?invito=<codice>`.

Se tutti i posti sono presi (per esempio «4 utenti su 4»), sopra **Crea l'invito** c'è l'avviso **Posti pieni**: l'invito si
può creare lo stesso, ma chi lo riceve trova le registrazioni chiuse finché il numero massimo di utenti non sale. Se i posti
liberi sono già tutti negli inviti ancora aperti (per esempio 3 utenti su 4 e un invito non ancora usato), l'avviso è
**Posti quasi pieni**: chi riceve un invito in più può trovare le registrazioni chiuse.

Il numero massimo è la variabile `MAX_UTENTI` del servizio (15 se manca), da cambiare come sopra. Dopo il riavvio, ricaricata la
pagina, l'avviso non c'è più e lo stesso link funziona (vale 7 giorni dalla creazione).

Sotto **Crea l'invito** c'è **Inviti aperti**: gli inviti non ancora usati e non scaduti, ognuno con l'etichetta, quando è stato
creato e quando scade (per esempio «Creato mer 25 nov, scade mer 2 dic.») e, per un invito per più amici, i posti ancora liberi.
**Annulla** toglie valore al link: prima l'app chiede conferma, poi l'invito sparisce dall'elenco e il suo posto torna libero.
Chi è già entrato con quell'invito tiene il suo account. Gli inviti usati, scaduti o annullati non compaiono.

## 2. Password dimenticata, utenti, errori

- **Password dimenticata**: se qualcuno ha perso password e codice di recupero, **Genera il codice** crea un codice che vale
  24 ore, una volta sola. Si dà di persona: con quel codice l'amico sceglie una nuova password. Vale per gli utenti e per il proprio
  account, non per un altro amministratore: l'app lo dice («Per un altro amministratore il codice non si crea dalla web: la password
  si cambia con il suo codice di recupero.»). Nel registro di sicurezza del server la riga dice anche chi ha creato il codice.
- **Utenti**: chi ha un account, con quando si è iscritto e l'ultimo accesso (per esempio «Iscrizione gio 1 ott, ultimo accesso
  mar 24 nov.»); chi gestisce ha accanto «amministratore», e sulla propria riga c'è «Sei tu». Sugli account degli utenti (non
  degli altri amministratori, che si gestiscono solo sul server) due pulsanti, ognuno dopo una conferma che dice il nome (solo
  sulla web: la Gestione dell'iPhone non ha gli strumenti degli account):
  - **Blocca**: l'account non entra più, né con la password né con Google, e le sue sessioni (web, iPhone, widget) e le sue
    notifiche si chiudono subito. I suoi dati restano. Sulla riga compare «Bloccato mer 25 nov: non può entrare.» e al posto di
    **Blocca** c'è **Sblocca**, che lo fa rientrare con la sua password. Chi è bloccato, se prova a entrare con la password
    giusta, legge «Questo account è bloccato: chiedi a chi gestisce SchieraXI.»; lo stesso se prova a cambiare la password
    con il codice di recupero o con l'email. Non riceve avvisi. Sbloccato, rientra con la sua password (le sessioni di prima
    restano chiuse).
  - **Elimina**: l'account e tutti i suoi dati spariscono, come quando lo elimina lui da **Il tuo account**. Non si può
    annullare.

  Il proprio account non si blocca e da qui non si elimina (si elimina da **Il tuo account**, con la password); un altro
  amministratore si blocca o si elimina solo con i comandi qui sotto. L'ultimo amministratore che non è bloccato non si blocca,
  non si elimina e non si declassa. Ogni blocco, sblocco ed eliminazione lascia una riga negli eventi di sicurezza di
  **Errori recenti** («Account bloccato · luca»); nel registro di sicurezza del server la riga dice anche chi l'ha fatto.
  Dopo ogni blocco, sblocco ed eliminazione la pagina rilegge da sola utenti, **Commenti degli utenti** (i commenti di un account
  eliminato vanno via con lui) ed **Errori recenti**.
  Sul server, via ssh, dalla cartella dell'app, gli stessi passi con la conferma del nome (anche per gli amministratori):
  `.venv/bin/python -m fanta utente-blocca <nome>`, `utente-sblocca <nome>` e `utente-elimina <nome>`.
- **Errori recenti**: le richieste dall'ultimo riavvio con le rifiutate e gli errori del server, tempo medio e massimo, gli
  eventi di sicurezza con il loro nome in parole e, quando c'è, di chi sono (per esempio «Uscita da tutti i dispositivi · luca»),
  con in più gli ultimi eventi importanti (registrazioni, recuperi, eliminazioni, cambi di ruolo, blocchi, inviti) anche dopo
  tanti accessi sbagliati, le richieste più lente con accanto al percorso tecnico il nome della parte
  (per esempio «Formazione (/api/oggi)»). Ore nell'ora italiana. Le richieste senza nessun accesso verso le parti dell'app (di
  solito dalla pagina prima dell'ingresso) sono dette a parte; un accesso con un codice o una sessione che non vale, o una
  richiesta a una parte riservata, resta fra le rifiutate. Nessuna password e nessun dato delle richieste. Si rilegge da solo
  dopo ogni invito creato o annullato, dopo un codice per la password e dopo blocca, sblocca ed elimina. Se un file del registro
  sul server c'è ma non si legge (per esempio per i permessi), al posto dell'elenco c'è un errore con il nome del file («Non riesco
  a leggere il registro del server (sicurezza.log): controlla i permessi del file sul server.») e la causa è nel log del servizio
  (`journalctl -u fantacalcio`).

- **Commenti degli utenti** (solo sulla web): quello che gli amici scrivono da **Impostazioni › Scrivici** (web e iPhone), gli
  ultimi 100, il più recente in alto: chi, quando (ora italiana), da dove (web, iPhone, Android) con la versione dell'app, e il
  testo intero. **Segna come letto** toglie il commento da quelli da leggere (il numero sta sotto il titolo e conta i commenti
  mostrati). A ogni commento nuovo arriva un avviso sul canale ntfy del server (lo stesso della sentinella e degli script,
  `~/.config/schieraxi/canale`): «SchieraXI · un commento nuovo», senza il testo e senza il nome, che restano sul server. Al
  massimo 6 avvisi all'ora per tutto il server: oltre, i commenti si salvano senza avviso. Senza quel file l'avviso non parte,
  il commento si salva lo stesso. Ognuno ne manda al massimo 5 al giorno (sul server si cambia con `FANTA_MAX_COMMENTI_AL_GIORNO`), tranne chi gestisce l'app, che non ha limite; con l'account
  eliminato se ne vanno anche i suoi commenti. Sul server, via ssh, gli ultimi 20 con il testo intero:
  `.venv/bin/python -m fanta feedback --ultimi 20` (dalla cartella dell'app, sola lettura).

Sul PC, da 1100 px, la pagina ha due colonne: gli strumenti a sinistra, **Commenti degli utenti** ed **Errori recenti** a destra.

Le email (codice per la password dimenticata, avvisi di sicurezza, cambio dell'email) partono solo se il server ha l'invio
acceso (`fanta/posta.py`, variabili `FANTA_MAIL` e `FANTA_SMTP_*`). Se è spento, l'app lo dice: il recupero passa solo dal codice
di recupero e in **Il tuo account** non si può collegare un'email.

## 3. Dati e fonti

- **Aggiorna i dati** scarica subito dalle fonti; di solito il server lo fa da solo. Se all'apertura dell'app il server è già
  occupato con un aggiornamento (dei dati o di una versione nuova), il pulsante è spento con una frase che lo dice e si riaccende
  da sé quando ha finito; se l'aggiornamento parte con l'app già aperta, il pulsante premuto risponde «Aggiornamento già in
  corso.». Con tutte le fonti spente lo dice e non parte. Fra un giro e il successivo passano almeno 10 minuti, per non chiedere
  troppo alle fonti: premuto prima, dice fra quanto riprovare («Hai appena provato: riprova fra 9 minuti.») e non parte. Finito
  con dei problemi, l'avviso dice «Aggiornato, ma con problemi:» e sotto una frase per riga, per esempio «Fantacalcio.it non
  risponde: riprova più tardi.»; il dettaglio tecnico sta nel registro del server e in **Stato dei dati**. Un giro in cui non
  arriva nessuna pagina non cambia l'ora dei dati («dati del …»): l'avviso «I dati delle partite non si aggiornano da …» resta
  finché i dati non arrivano, e l'avviso di **Aggiorna i dati** dice «Nessun dato nuovo:» con sotto le stesse frasi (o, se non
  c'era niente da scaricare, «Nessun dato nuovo: non c'era niente di più recente da scaricare.»).
- **Stato dei dati** (**Apri lo stato dei dati**): da dove arrivano i dati, se qualche fonte ha dato errore e quanto è affidabile
  il modello. Le fonti si accendono e si spengono da qui: sotto ogni fonte spenta c'è cosa non arriva, e una volta sola sotto
  l'elenco cosa fa l'app senza e le condizioni d'uso. La scelta vale subito, anche per i risultati in diretta (ESPN e la
  funzione «Risultati in diretta»): non serve riavviare il server. **Quanto si usa l'app** conta le richieste delle ultime 4
  settimane per funzione e, sotto **Le schermate più usate**, per parte dell'app (per esempio «Formazione», «La mia lega»).
- Quando i dati non si aggiornano da giorni, chi gestisce vede in cima alla Formazione la decisione «I dati delle partite non
  si aggiornano da N giorni.» con **Controlla**, che apre **Impostazioni › Gestione**: lì **Apri lo stato dei dati** dice quale
  fonte si è fermata. Gli altri utenti non la vedono.

Le misure dello **Stato dei dati**:

- **Registro delle giornate**: prima di ogni giornata l'app salva i numeri che mostra per tutta la Serie A e, a giornata finita,
  li confronta con com'è andata. Per tre misure (errore del fantavoto atteso contro la fantamedia avvicinata alla media del
  ruolo, «gioca N%» contro chi ha giocato davvero, punti veri dentro la fascia «8 volte su 10») c'è la media delle ultime
  giornate misurate, la soglia e se **regge** o **non regge**; finché le giornate misurate sono meno di 8 c'è scritto quante ne
  servono ancora. Sotto, le **Giornate perse**: quelle non salvate prima della prima partita, con il motivo in parole semplici;
  il dettaglio tecnico resta nel log del server. Da questo registro viene anche la riga «su tutta la Serie A» che gli utenti
  vedono in **Giornate › Dettagli**.
- **Gol attesi nostri (senza Understat)**: prima di ogni giornata l'app salva anche i numeri calcolati solo con i voti di
  Fantacalcio.it e, a giornata finita, li confronta con quelli mostrati. Per tre misure (errore del fantavoto atteso, punti veri
  della formazione migliore, gol attesi contro gol veri per fasce) c'è la media delle ultime giornate misurate con la versione
  di oggi del calcolo, la soglia e se **regge** o **non regge**; in cima, se reggono tutte e tre insieme. Se reggono per 8
  giornate si può fare a meno di Understat. **Giornata per giornata** mostra ogni giornata: da misurare, misurata con i suoi
  numeri, o persa con il motivo.
- **Consiglio di formazione**: dopo ogni giornata l'app misura la formazione consigliata che mostrava prima della scadenza,
  sommando i Diari di tutti. Quattro misure: punti in più della consigliata rispetto alla scelta semplice (chi ha preso voto la
  giornata prima, con la fantamedia più alta) e rispetto alla formazione schierata, quando è diversa; cambi della consigliata
  nelle 24 ore prima della scadenza; titolari che rischiano di non giocare mentre un compagno di ruolo gioca; scelte strane senza
  un motivo detto. Per ognuna la media delle ultime giornate, la soglia e se **regge** o **non regge**.
- **Quanto ci azzecca il modello › Taratura con le probabili**: a che punto è la taratura di «gioca N%» con le probabili
  formazioni. **In attesa**: quante giornate con le probabili salvate prima della prima partita ci sono, su quante ne servono per
  la prima prova. **Attiva**: da quando e, sulle ultime giornate di prova, di quanti punti in media hanno sbagliato le percentuali
  «gioca N%», contro quanti senza questa taratura. **Non attiva**: perché (per esempio «non sbaglia meno dei numeri di partenza»).
  **Spenta a mano**. Negli **Ultimi aggiornamenti** la riga **Taratura di «gioca N%»** ha l'ora dell'ultimo cambio.

## 4. Scelte che si fanno sul server

- **Aste e finestre di scambio.** La decisione **Aggiorna le rose** compare dopo le aste e nelle finestre di scambio. Senza
  date vale l'asta di partenza dal 1° al 21 settembre e dal 1° al 21 febbraio, e per gli scambi le soste del campionato. Le date
  vere della lega si scrivono in `regole.json`: `asta_estiva` e `asta_invernale` (un periodo
  `{"dal": "AAAA-MM-GG", "al": "AAAA-MM-GG"}`) e `finestre_scambio` (un elenco di periodi).
- **Funzioni dietro un interruttore.** Alcune parti sono spente di norma, per esempio **Squadre della lega** (le rose delle
  altre squadre: senza, in **La mia lega** la voce **Le altre squadre** non c'è) e **Immagini da indirizzo web** (stemma e maglia
  da un indirizzo `https://` e, sulla web, dal menu Condividi del telefono; sull'iPhone il menu Condividi funziona anche senza) e **Widget aggiuntivi** (`widget_extra`: il widget **Da controllare**;
  spento, dice «Widget spento»). Si accendono con il file `dati/funzioni.json`, per esempio
  `{"squadre_altrui": true, "widget_extra": false}` (`true` acceso, `false` spento; valgono anche `1` e `0`), o con la
  variabile `FANTA_FUNZIONE_<NOME>` (`1` acceso, `0` spento); l'elenco con i nomi è in `fanta/funzioni.py`. Se il file è
  scritto male (per esempio una virgola di troppo) nessuna delle sue scelte vale: il registro del servizio lo dice con il nome
  del file, e dall'app gli interruttori non si cambiano finché non lo correggi o lo togli. Lo stesso vale per `dati/fonti.json`,
  il file delle fonti.
- **Server senza account.** In **Gestione** c'è anche **Avvisi anche per l'app nativa**: gli avvisi arrivano anche con ntfy,
  e il tocco sulla notifica apre l'app per iPhone.

## 5. App per iPhone

- **Indirizzo del server.** L'app usa da sola il server pubblico (https://app.schieraxi.it) e a chi la usa non chiede nessun
  indirizzo. Chi gestisce un server proprio lo cambia in **Impostazioni › Gestione**, nel riquadro **Collegamento** (solo
  `https://<indirizzo-del-server>`), oppure, prima di entrare, tenendo premuto il marchio nella prima schermata. Se il server non
  risponde, anche gli altri utenti trovano in **Impostazioni** il riquadro **Collegamento** con **Cambia server** ed **Esci**:
  lasciando vuoto l'indirizzo si torna al server di SchieraXI.
- **Certificato.** L'app installata con SideStore scade dopo 7 giorni. In **Impostazioni › Gestione** c'è **Certificato
  dell'app** (**Validità** e **Scade il**) e **Rinnovo automatico (SideStore)**, con i passi per far rinnovare l'app ogni notte
  (gli stessi di [INSTALLAZIONE-IPHONE.md](INSTALLAZIONE-IPHONE.md), sezione 5). Chi gestisce vede anche, in cima alla
  Formazione, la decisione «L'app sul telefono scade fra N giorni: rinnovala.» con **Rinnova**. Tutti gli utenti dell'app per
  iPhone ricevono invece, se gli avvisi sono permessi, il promemoria «SchieraXI · Da rinnovare» 24 ore e 6 ore prima della
  scadenza, mai nelle ore tranquille: se ci cadono, arrivano un minuto prima che comincino.
- **Registrazione.** Con le iscrizioni aperte l'app per iPhone ha lo stesso modulo della web (nome utente, password, email
  facoltativa). Con gli inviti chi usa l'app per iPhone si registra con il codice scritto sotto il link dell'invito (sezione 1).
