# SchieraXI per iOS

App **nativa** (SwiftUI) per iPhone e iPad. Parla con il server di SchieraXI sul server (API JSON, rete privata acceso) e usa le funzioni di iOS.
Il server e la logica (modello, formazioni, scambi) stanno nell'altro repository (`schieraxi`): qui c'è solo l'app.

## Cosa c'è
- **Oggi, Formazione, Mercato, Scambi, Lega:** tutto nativo (stili, moduli, modifica a mano e salvataggio, osservati, ricerca, scheda giocatore, scambi anche 2 contro 2, importazione Excel, asta, regole modificabili, crediti, avvisi del server, stato dei dati).
- **iPad e schermi grandi:** barra laterale (`NavigationSplitView`) con larghezza "regular"; schede in 1, 2 o 3 colonne secondo la larghezza (`Colonne`). Tastiera: Cmd+1...5 sezioni, Cmd+R aggiorna, Cmd+S salva la formazione a mano. Puntatore: effetto "lift".
- **Cache offline:** l'ultima risposta di ogni schermata sta in `Caches/api` (massimo 150 file, separata per server). Se il server non risponde: "Server non raggiungibile. Dati salvati del ...".
- **Aggiornamento in background** (`BGAppRefreshTask`) e **promemoria locali** prima della prima partita; notifica locale se cambia la formazione consigliata.
- **Siri e Comandi** (App Intents): "Qual è la mia formazione su SchieraXI", "Quanto manca alla partita su SchieraXI".
- **Widget** (target `SchieraxiWidget`): Home (piccolo, medio) e schermata di blocco (cerchio, rettangolo, riga).
- **Spotlight** sui giocatori osservati.
- **Collegamenti `schieraxi://`** (per aprire l'app da una notifica di ntfy con l'intestazione `Click`):
  `schieraxi://oggi`, `formazione`, `mercato`, `scambi`, `lega`, `schieraxi://giocatore/<id>`.
  Esempio: `Click: schieraxi://formazione` (c'è anche in Lega, "Come aprire l'app da una notifica ntfy").
- **Scadenza del certificato:** in Lega "Scade tra N giorni" (arancio sotto 2 giorni, rosso se scaduto), letta da `embedded.mobileprovision`; se non si legge: "scadenza non leggibile". Promemoria locali 24 e 6 ore prima ("Rinnova l'app con SideStore"), riprogrammati a ogni apertura e a ogni aggiornamento in background.
- **Rinnovo automatico SideStore:** in Lega una scheda con i passi (Comandi > Automazione > 3:00 > "Refresh All Apps", LocalDevVPN attiva, una sola VPN alla volta).
- **Aspetto:** segue chiaro/scuro del sistema, Dynamic Type, VoiceOver, aree di tocco da 44 pt.

## Architettura (cartelle in `Sources/`)
- `Domain/` modelli puri del server (`Modelli*.swift`), `Quando` (date del server, ora italiana), `Formato` (numeri sempre in italiano, conversioni sicure). Condivisi anche con il widget.
- `Data/` tutto ciò che tocca la rete e il disco: protocollo `ServerClient` (+ `ServerHTTP` via URLSession e `FinteServer` per anteprime/test), `Cache`, `Stato<T>` (idle/loading/loaded/failed con ultimi dati) e `Caricatore<T>`, `OggiRepository`.
- `Presentation/<Sezione>/` una `View` dichiarativa e il suo `ViewModel` (`@MainActor`, `ObservableObject`, derivato da `ViewModelBase`) per Oggi, Formazione, Mercato (+ scheda giocatore), Scambi (+ analisi), Lega (+ squadre, regole, avvisi, crediti, importazione Excel). Ogni vista ha un `#Preview` con dati finti (`Support/DatiAnteprima.swift`).
- `Support/` componenti grafici (`Componenti`), `Notifiche`, `Aggiornamento` (background), `Spotlight`, `Comandi` (Siri), `Certificato`, `Collegamenti`, `Haptics`.
- `App/` punto d'ingresso, `AppModel` (crea una volta i ViewModel: cambiando sezione non si perde nulla), `Radice` (schede o barra laterale).
- Iniezione del server: i ViewModel ricevono un `ServerClient` nel costruttore (`AppModel(server:)`; nelle anteprime `FinteServer.esempio`). Fuori da SwiftUI (aggiornamento in background, Siri) si usa `ServerCorrente.condiviso`.

## Come si compila (nessun Mac)
- GitHub Actions su un Mac (**`macos-26`**, Xcode 26), senza firma: produce `Schieraxi.ipa` con il widget in `PlugIns` (artifact e release `build-N`). Per tornare a `macos-15`: lancio manuale del workflow con `runner = macos-15` (non crea la release) o modifica di `runs-on` in `.github/workflows/ipa.yml`.
- Indirizzo del server: variabili del repository `FANTA_HOST` e `FANTA_PORT`; modificabile da Lega (solo `https://`).
- **Installazione:** SideStore sull'iPhone firma l'IPA con l'Apple ID gratuito e lo rinnova (ogni 7 giorni, con LocalDevVPN attiva).

## Vedere l'app senza telefono (modalità demo e foto nel simulatore)
- **Modalità demo:** se l'app parte con l'argomento di lancio `-DEMO` usa `FinteServer.demo` (`Sources/Support/DatiDemo.swift`): una lega finta ma verosimile (formazione con titolari e panchina, avvisi, mercato, scambi, regole, stato dei dati), senza rete, senza permessi e senza lavori in background. Nel comportamento normale non cambia niente.
  Altri argomenti, solo in demo: `-DEMO_SCHERMATA <nome>` (apre una schermata o una sotto-pagina, vedi `Sources/Support/Demo.swift`), `-DEMO_FONDO 1` (parte scorsa in fondo), `-DEMO_ORIENTAMENTO orizzontale`.
- **Workflow `screenshot.yml`** (a mano da Actions, e a ogni push su `main` che cambia `Sources/`): compila per il simulatore, avvia un iPhone e un iPad, lancia l'app con `-DEMO` e fotografa ogni schermata (chiaro e scuro, testo normale e grande, verticale e orizzontale). Le foto sono nell'artifact `screenshot-app` (14 giorni); non crea release.
  Scaricarle: `gh run download <id> --name screenshot-app --dir .screenshot` (la cartella `.screenshot/` è ignorata da git).

## Da provare sul telefono (la compilazione verde non prova il comportamento)
1. Tutte le schermate come prima (Oggi, Formazione con modifica a mano, Mercato, Scambi, Lega): l'architettura è cambiata sotto, il comportamento no.
2. Cambia sezione e torna: Formazione deve tenere la modifica a mano; Mercato la sezione scelta.
3. Server spento: compare "dati salvati".
4. `schieraxi://formazione`: scrivilo in Safari o mandalo da ntfy con l'intestazione `Click`; deve aprire l'app sulla Formazione. Prova anche `schieraxi://giocatore/<id>`.
5. Lega: riga "Certificato dell'app" con i giorni rimasti (se dice "scadenza non leggibile" è normale con certi rifirmi di SideStore); permesso notifiche acceso per i promemoria di scadenza.
6. Rinnovo notturno con Comandi: segui la scheda in Lega; ricorda che rete privata e LocalDevVPN non possono essere attive insieme.
7. Siri, widget, Spotlight, iPad con tastiera: come nelle versioni precedenti.

## Limiti noti (Apple ID gratuito)
- Niente notifiche push (APNs): per gli avvisi del server resta la web app o ntfy; l'app nativa usa promemoria locali e l'aggiornamento in background.
- Certificato di 7 giorni, massimo 3 app. Il widget consuma un App ID in più: se SideStore protesta, togli il target `SchieraxiWidget` da `project.yml` e la riga `dependencies`.
- Se SideStore rinnova l'app senza che l'app venga aperta, un promemoria di scadenza già programmato può arrivare lo stesso: si corregge alla prima apertura.
- Mai in git: firme, certificati, profili, password, Apple ID.
