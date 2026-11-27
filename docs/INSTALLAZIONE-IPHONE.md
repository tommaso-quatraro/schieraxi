# SchieraXI su iPhone: installazione con SideStore

Questa guida installa l'app per iPhone (cartella `ios/` del repository) con **SideStore**, senza un account Apple a pagamento.
Per cosa fa l'app, vedi [GUIDA-UTENTE.md](GUIDA-UTENTE.md). Per i limiti dell'Apple ID gratuito, vedi la sezione «Limiti noti» di `ios/README.md`.

Tre cose da sapere subito:

- L'app **scade ogni 7 giorni** e va rinnovata. Il rinnovo è automatico, con un Comando di Apple alle 3:00 (sezione 5).
- L'indirizzo di SchieraXI è **https://app.schieraxi.it**. Per usare l'app **non serve nessuna VPN**.
- L'unica app di rete che serve è **LocalDevVPN**, e solo per il rinnovo di SideStore: è un passo di SideStore, non di SchieraXI.
- Se non vuoi installare nulla, puoi aggiungere SchieraXI alla Home da Safari come web app: vedi [GUIDA-UTENTE.md](GUIDA-UTENTE.md), sezione 6, «Installare SchieraXI dal browser».

## 0. Cosa serve

- Un iPhone con **iOS 18 o più recente** (il progetto richiede almeno iOS 18).
- Un **Apple ID** normale (gratuito). Non serve il Developer Program a pagamento.
- Il **Wi-Fi** per il rinnovo: con la sola rete mobile il rinnovo non parte.
- L'app **LocalDevVPN** (dall'App Store): serve a SideStore per rinnovare l'app.
- Un account SchieraXI (vedi [GUIDA-UTENTE.md](GUIDA-UTENTE.md), sezione 2).

## 1. Installare SideStore

1. Segui la guida ufficiale di SideStore (sito `sidestore.io`). I passi cambiano spesso: quella ufficiale è più aggiornata di questa. [da verificare sul sito: l'indirizzo e i nomi dei menu]
2. Usa la versione **Nightly**. A ottobre 2026 la versione stabile dava un errore di accesso (`-80045`), la Nightly no.
3. Quando SideStore chiede l'Apple ID, usa quello normale. Le password restano sull'iPhone: non vanno mai scritte in un file o in una chat.
4. Verifica che SideStore parta e che LocalDevVPN si possa attivare.

## 2. Aggiungere la fonte di SchieraXI

1. In SideStore apri la scheda **Sorgenti** (in inglese *Sources*). Tocca **+**.
2. Incolla questo indirizzo, che punta all'ultima versione pubblicata:

   ```
   https://github.com/tommaso-quatraro/schieraxi/releases/latest/download/sorgente.json
   ```

3. Apri la fonte e scegli **SchieraXI**.
4. Tocca **Installa** (o **Get**).

### La scelta da fare: «Register App ID for Each Extension»

L'app ha un widget, che è una «estensione» separata. Quando SideStore lo chiede, scegli **Register App ID for Each Extension**. Così il widget ottiene il suo identificativo e funziona.

Con un Apple ID gratuito ci sono limiti: circa 3 app installate insieme e un identificativo per ogni app o estensione. Se SideStore protesta per il widget, lascia l'app senza widget (vedi `ios/README.md`, sezione «Limiti noti»).

## 3. Primo avvio

1. Apri **SchieraXI** dalla Home.
2. L'app non chiede nessun indirizzo: usa da sola **https://app.schieraxi.it**. La prima schermata ha **Accedi** e **Registrati**.
3. Entra o registrati (vedi [GUIDA-UTENTE.md](GUIDA-UTENTE.md), sezione 2). Se non hai ancora le rose, parte la configurazione guidata.

Chi gestisce un server proprio può cambiare l'indirizzo in **Impostazioni › Gestione**, nel riquadro **Collegamento** (solo `https://`), oppure, prima di entrare, tenendo premuto il marchio nella prima schermata.

**Se avevi una versione di prima**: l'app ha un nuovo identificativo, quindi per SideStore è un'app nuova. Installala dalla fonte, rifai l'accesso e riaggiungi i widget. La vecchia resta sul telefono finché non la rimuovi (sezione 8).

## 4. Rete e VPN

- SchieraXI parla con il server solo con l'indirizzo `https`. Non serve nessuna VPN né altre app di rete per usarla.
- **LocalDevVPN** serve solo quando SideStore rinnova l'app (sezione 5). Puoi lasciarla accesa sempre: non disturba l'uso di SchieraXI.

## 5. Rinnovo ogni 7 giorni

Un Apple ID gratuito firma l'app per 7 giorni. Dopo, SideStore la rinnova.

### Il Comando automatico (da impostare una volta)

Chi gestisce l'app trova gli stessi passi anche dentro l'app, in **Impostazioni › Gestione › Rinnovo automatico (SideStore)**. Riassunto:

1. Nell'app **Comandi** crea un comando con l'azione di SideStore **Refresh All Apps** (in italiano può comparire come «Aggiorna tutte le app»).
2. Vai su **Automazione**, tocca **+**, scegli **Ora del giorno**, imposta **3:00** e ripeti ogni giorno.
3. Come azione scegli quel comando. Poi tocca **Esegui subito** e spegni **Notifica quando viene eseguito**.
4. **LocalDevVPN** deve essere attiva durante il rinnovo: puoi lasciarla sempre accesa.
5. Tocca **Fine**.

Il rinnovo richiede il Wi-Fi: con la sola rete mobile dà l'errore «No wifi interface satisfied». I nomi dei passaggi possono cambiare con la versione di iOS: se un'azione non si trova, cercala per nome.

### Promemoria dentro l'app

Se gli avvisi dell'app sono permessi, 24 ore e 6 ore prima della scadenza arriva il promemoria «SchieraXI · Da rinnovare». Chi gestisce l'app vede anche quanti giorni mancano in **Impostazioni › Gestione › Certificato dell'app** («Scade tra N giorni») e, in cima alla Formazione, la decisione «L'app sul telefono scade tra N giorni: rinnovala.» con **Rinnova**.

Se il rinnovo non è partito e la scadenza si avvicina:

1. Apri SideStore e tocca **Refresh All Apps** a mano (con LocalDevVPN accesa e Wi-Fi attivo).
2. Se non basta, reinstalla dalla fonte (sezione 2): i dati locali dell'app restano, ma verifica sempre dopo.

## 6. Aggiornamento dell'app

Quando esce una nuova versione:

1. Apri SideStore e aggiorna SchieraXI dalla sua fonte (sezione 2). Se non compare un tasto di aggiornamento, reinstalla dalla fonte.
2. Apri l'app e controlla la scheda **Novità** (in **Impostazioni › Informazioni**).

L'icona sulla Home può non cambiare subito: se non cambia, riaggiungi l'app alla Home.

## 7. Widget

Il widget mostra i dati letti dal server, senza far partire calcoli. Si collega **da solo**, senza nessun codice:

1. Entra nell'app SchieraXI.
2. Tieni premuto sulla Home (o sulla schermata di blocco) e tocca **+** oppure **Modifica widget**.
3. Scegli **SchieraXI** e il tipo di widget.

Se il widget dice «Tocca per collegare» (sotto: «Si apre SchieraXI per collegarlo»), toccalo: si apre l'app su **Collega il widget**; tocca **Collega**. La stessa schermata si apre dalla riga **Widget: tocca per collegare** in **Impostazioni** dell'app. Se proprio non si collega, l'app copia un codice: tieni premuto il widget, tocca **Modifica widget**, attiva **Collegamento manuale** e incolla il codice.

Il widget legge solo la formazione, i dati del widget e i risultati in diretta, e il suo permesso scade dopo 90 giorni (si rinnova aprendo l'app).

Ogni iPhone e iPad ha il suo permesso: con lo stesso account, entrare o uscire su uno non scollega il widget dell'altro. I dispositivi collegati possono essere al massimo 10; con l'undicesimo si scollega quello usato meno di recente.

## 8. Rimuovere l'app

1. In SideStore, nella scheda **My Apps**, tocca l'app e scegli **Rimuovi** (o **Remove**).
2. I dati dell'app sul telefono vanno via con l'app. I dati sul server restano: per cancellarli si elimina l'account (vedi [GUIDA-UTENTE.md](GUIDA-UTENTE.md), sezione 6). Se vuoi una copia, usa prima **Scarica i tuoi dati** (guida, sezione 6).

## 9. Limiti noti

- Niente notifiche push vere (servono a un account a pagamento). L'app manda da sola solo i promemoria della scadenza (un'ora e un quarto d'ora prima) quelli del rinnovo e l'avviso di una versione nuova; l'avviso quando cambia la formazione da schierare arriva dalla web app, oppure con ntfy se la scelta è attiva (interruttore «Avvisi anche per l'app nativa»). Dettagli in `ios/README.md`.
- Il certificato dura 7 giorni: se il rinnovo fallisce più giorni di fila, l'app smette di aprirsi.
- Il repository è pubblico: così le Actions di GitHub su macOS sono gratuite. Lì dentro non ci sono firme, certificati o password.
- Problemi che non si risolvono: scrivi da **Impostazioni › Scrivici** dell'app, oppure al recapito indicato nella pagina [Privacy](https://app.schieraxi.it/privacy).

## 10. Notifiche dopo un cambio di chiave

Le notifiche della web app (sezione 4 della guida, «Avvisi sul telefono») usano una chiave del server. Se chi gestisce il server la cambia, le notifiche attivate prima smettono di arrivare, e l'app non lo segnala. Per riattivarle:

1. Apri SchieraXI dalla schermata Home: la web app aggiunta da Safari, non quella installata con SideStore.
2. Vai in **Impostazioni › Avvisi**.
3. Spegni e riaccendi **Avvisi su questo dispositivo**. Concedi il permesso quando il telefono lo chiede.
4. Quando lo riaccendi l'app ti manda un avviso di prova; se non parte, te lo dice.

Se il permesso è stato negato, riattivalo dalle impostazioni del telefono per l'app, poi ripeti i passi.

Per la parte tecnica (come si compila, la lista dei controlli sul telefono) vedi `ios/README.md`.
