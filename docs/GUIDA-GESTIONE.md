# SchieraXI: guida per chi gestisce l'app

Questa guida è per chi gestisce il server e fa entrare gli amici. Quello che vede chi usa l'app sta in
[GUIDA-UTENTE.md](GUIDA-UTENTE.md); qui ci sono solo le cose che vede o fa chi gestisce. Per il server stesso: gli script e
l'aggiornamento automatico in `script/server/LEGGIMI.md`, il ripristino in [RIPRISTINO-SERVER.md](RIPRISTINO-SERVER.md).
Nei comandi qui sotto l'indirizzo del server si scrive `<indirizzo-del-server>`.

Tutto quello che segue sta in **Impostazioni › Gestione**, che compare solo a chi gestisce l'app (nell'elenco degli utenti ha
accanto «amministratore»).

## 1. Iscrizioni e inviti

### Iscrizioni aperte (di norma)

Chi vuole apre l'app, tocca **Registrati**, sceglie nome utente e password (l'email è facoltativa) ed entra subito, senza invito:
dopo il codice di recupero parte il primo avvio (rose, squadra, tempi). In **Impostazioni › Gestione** c'è **Iscrizioni** con la
frase «Le iscrizioni sono aperte: chi vuole si registra da solo dalla schermata d'accesso, finché ci sono posti.»; **Nuovo invito** e
**Inviti aperti** non ci sono, perché non servono. Quando gli utenti arrivano al numero massimo, sotto la frase c'è l'avviso **Posti
pieni** e chi prova a registrarsi legge «Iscrizioni chiuse: siamo al completo».

Due tetti tengono lontano chi trova il sito e prova a riempirlo, tutti e due nelle variabili del servizio:

- `MAX_UTENTI`: quanti account al massimo (15 se manca);
- `FANTA_ISCRIZIONI_GIORNO`: quanti account nuovi senza invito in 24 ore (5 se manca). Oltre, chi si registra legge «Per oggi le
  iscrizioni sono chiuse: riprova domani». Il giorno in cui mandi il link dell'app a tutti gli amici alzalo (per esempio a 12) e poi
  rimettilo com'era.

In più la web ha un campo nascosto che una persona non vede: se un programma lo compila, l'account non nasce (nel registro di
**Errori recenti** compare «Registrazione fermata: modulo compilato da un programma»). E da uno stesso indirizzo internet si fanno
pochi tentativi non riusciti all'ora.

Per cambiare una variabile, sul server: `sudoedit /etc/schieraxi/fantacalcio.env`, scrivi la riga (per esempio `MAX_UTENTI=12`),
poi `sudo systemctl restart fantacalcio`.

### Aperte o solo con invito

Si sceglie con la riga `FANTA_REGISTRAZIONE` dello stesso file, poi `sudo systemctl restart fantacalcio`:

- nessuna riga, oppure `FANTA_REGISTRAZIONE=aperta`: iscrizioni aperte, come sopra;
- `FANTA_REGISTRAZIONE=invito`: si entra solo con un invito, come prima del 26/11/2026; in **Registrati** torna il campo **Codice
  d'invito** e in **Gestione** tornano **Nuovo invito** e **Inviti aperti** (qui sotto). Chi ha già un account non perde niente.

Un valore scritto male (per esempio `chiusa`) vale come `invito`: le iscrizioni non si aprono mai per sbaglio. Per far entrare una
chat di amici con un solo link anche con `invito`, crea un **invito di gruppo** sul server:
`.venv/bin/python -m fanta invito --etichetta "Lega" --usi 12` (fino a 30 persone, vale 7 giorni; il codice si vede una volta sola) e
manda nella chat `https://<indirizzo-del-server>/?invito=<codice>`.

Con le iscrizioni aperte il modulo non chiede codici: un amico che deve gestire l'app con te si registra come tutti e poi, sul server,
`.venv/bin/python -m fanta utente-ruolo --utente <nome> --ruolo admin`.

### Con gli inviti

**Impostazioni › Gestione › Nuovo invito** crea il link da mandare (**Condividi l'invito** o **Copia il messaggio**): apre la
registrazione con il codice già scritto e vale 7 giorni. Sotto c'è anche il codice, per chi usa l'app per iPhone. L'etichetta
serve a ricordare per chi era; con la casella **Il nuovo account sarà amministratore** chi entra gestisce l'app anche lui.

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
  24 ore, una volta sola. Si dà di persona: con quel codice l'amico sceglie una nuova password.
- **Utenti**: chi ha un account; chi gestisce ha accanto «amministratore».
- **Errori recenti**: le richieste dall'ultimo riavvio con le rifiutate e gli errori del server, tempo medio e massimo, gli
  eventi di sicurezza con il loro nome in parole, le richieste più lente con accanto al percorso tecnico il nome della parte
  (per esempio «Formazione (/api/oggi)»). Ore nell'ora italiana. Le richieste senza nessun accesso verso le parti dell'app (di
  solito dalla pagina prima dell'ingresso) sono dette a parte; un accesso con un codice o una sessione che non vale, o una
  richiesta a una parte riservata, resta fra le rifiutate. Nessuna password e nessun dato delle richieste.

Sul PC, da 1100 px, la pagina ha due colonne: gli strumenti a sinistra, **Errori recenti** a destra.

Le email (codice per la password dimenticata, avvisi di sicurezza, cambio dell'email) partono solo se il server ha l'invio
acceso (`fanta/posta.py`, variabili `FANTA_MAIL` e `FANTA_SMTP_*`). Se è spento, l'app lo dice: il recupero passa solo dal codice
di recupero e in **Il tuo account** non si può collegare un'email.

## 3. Dati e fonti

- **Aggiorna i dati** scarica subito dalle fonti; di solito il server lo fa da solo. Se all'apertura dell'app il server è già
  occupato con un aggiornamento (dei dati o di una versione nuova), il pulsante è spento con una frase che lo dice e si riaccende
  da sé quando ha finito; se l'aggiornamento parte con l'app già aperta, il pulsante premuto risponde «Aggiornamento già in
  corso». Con tutte le fonti spente lo dice e non parte.
- **Stato dei dati** (**Apri lo stato dei dati**): da dove arrivano i dati, se qualche fonte ha dato errore e quanto è affidabile
  il modello. Le fonti si accendono e si spengono da qui: sotto ogni fonte spenta c'è cosa non arriva, e una volta sola sotto
  l'elenco cosa fa l'app senza e le condizioni d'uso.
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
  da un indirizzo `https://` e, sulla web, dal menu Condividi del telefono; sull'iPhone il menu Condividi funziona anche senza). Si accendono con il file `dati/funzioni.json` o con la variabile
  `FANTA_FUNZIONE_<NOME>` (`1` acceso, `0` spento); l'elenco con i nomi è in `fanta/funzioni.py`.
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
  Formazione, la decisione «L'app sul telefono scade tra N giorni: rinnovala.» con **Rinnova**. Tutti gli utenti dell'app per
  iPhone ricevono invece, se gli avvisi sono permessi, il promemoria «SchieraXI · Da rinnovare» 24 ore e 6 ore prima della
  scadenza.
- **Registrazione.** Con le iscrizioni aperte l'app per iPhone ha lo stesso modulo della web (nome utente, password, email
  facoltativa). Con gli inviti chi usa l'app per iPhone si registra con il codice scritto sotto il link dell'invito (sezione 1).
