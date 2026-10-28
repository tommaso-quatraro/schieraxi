# SchieraXI per iOS

App **nativa** (SwiftUI) per iPhone e iPad. Parla con il server di SchieraXI sul server (API JSON, rete privata acceso) e usa le funzioni di iOS.
Il server e la logica (modello, formazioni, scambi) stanno nell'altro repository (`schieraxi`): qui c'è solo l'app.

## Cosa c'è
- **Oggi, Formazione, Mercato, Scambi, Lega:** tutto nativo (stili, moduli, modifica a mano e salvataggio, osservati, ricerca, scheda giocatore, scambi anche 2 contro 2, importazione Excel, asta, regole modificabili, crediti, avvisi del server, stato dei dati).
- **iPad e schermi grandi:** con la larghezza "regular" la barra in basso diventa una barra laterale (`NavigationSplitView`); le schede si dispongono in 1, 2 o 3 colonne secondo la larghezza (`Colonne` in `Componenti.swift`). Orizzontale e verticale, Split View e Slide Over.
  Tastiera: Cmd+1...5 per le sezioni, Cmd+R aggiorna, Cmd+S salva la formazione a mano. Puntatore: effetto "lift" sulle schede toccabili.
- **Cache offline:** l'ultima risposta di ogni schermata è salvata in `Caches/api` (limite 150 file). All'apertura si vede subito quella; se il server non risponde compare "Server non raggiungibile. Dati salvati del ...".
  Le schermate che si modificano e si rimandano (regole, avvisi, crediti) non usano la cache.
- **Aggiornamento in background** (`BGAppRefreshTask`): ogni tanto iOS sveglia l'app, che riscarica `/api/oggi`, riprogramma i promemoria e, se la formazione consigliata cambia (o escono le probabili), manda una notifica locale. Orari decisi da iOS.
- **Promemoria locali** (UserNotifications): un'ora e un quarto d'ora prima della prima partita, anche con l'app chiusa.
- **Siri e Comandi** (App Intents, iOS 16+): "Qual è la mia formazione su SchieraXI", "Quanto manca alla partita su SchieraXI". Risposta parlata più riquadro. Compaiono anche nell'app Comandi.
- **Widget** (secondo target `SchieraxiWidget`): piccolo e medio per la Home, cerchio/rettangolo/riga per la schermata di blocco. Conto alla rovescia, modulo, punti attesi. Scarica da solo `/api/oggi` (nessun App Group: usa l'indirizzo della compilazione, non quello scritto nella schermata Lega).
- **Spotlight:** i giocatori osservati si cercano dalla ricerca di iOS e aprono la loro scheda.
- **Aspetto:** segue chiaro/scuro del sistema, Dynamic Type, etichette VoiceOver su righe, icone e difficoltà del calendario, aree di tocco da 44 pt, aptici, ShareLink per condividere la formazione.

## Come si compila (nessun Mac)
- GitHub Actions su un Mac (**`macos-26`**, Xcode 26: dà il Liquid Glass su iOS 26), senza firma: produce `Schieraxi.ipa` con il widget dentro `PlugIns` (artifact e release `build-N`). Gratis anche nel repository privato.
  Per tornare a `macos-15`: lancio manuale del workflow con `runner = macos-15` (non crea la release), oppure cambiare `runs-on` e la condizione della release in `.github/workflows/ipa.yml`.
- Indirizzo del server: variabili del repository `FANTA_HOST` e `FANTA_PORT`; si può cambiare anche dalla schermata Lega (solo `https://`).
- **Installazione:** SideStore sull'iPhone firma l'IPA con l'Apple ID gratuito e lo rinnova da solo (ogni 7 giorni, in background, con LocalDevVPN attiva).

## Da provare sul telefono (la compilazione verde non prova il comportamento)
1. **iPhone, apertura:** Oggi e Formazione compaiono subito (dopo la prima volta) e si aggiornano; con rete privata spento si vede la striscia "dati salvati".
2. **iPad:** barra laterale, colonne affiancate in orizzontale, rotazione; con tastiera Cmd+1...5, Cmd+R.
3. **Formazione a mano:** modifica, cambia sezione e torna (la modifica deve restare), salva, "Torna alla consigliata".
4. **Notifiche:** accetta il permesso; controlla Lega > Promemoria ("Aggiornamento in background: attivo"). Il risveglio in background è deciso da iOS: va osservato in 1-2 giorni.
5. **Siri / Comandi:** chiedi le due frasi in italiano (Siri in italiano); in Comandi cerca "SchieraXI". Se Siri non le riconosce, apri una volta l'app Comandi e lancia l'azione a mano.
6. **Widget:** aggiungi il widget dalla Home e dalla schermata di blocco (iOS 16+); il widget non vede la cache dell'app, quindi con rete privata spento mostra l'ultimo riassunto che ha scaricato lui.
7. **Spotlight:** apri Mercato > Osservati una volta (indicizza), poi cerca un giocatore dalla ricerca di iOS.
8. **Tema:** prova modalità chiara e scura; testo grande da Impostazioni > Accessibilità; VoiceOver sulle righe giocatore.
9. **Excel:** importa un .xlsx (rifiuta altri file e oltre 5 MB). Regole: scrivi un numero con virgola (1,5).

## Limiti noti (Apple ID gratuito)
- Niente notifiche push (APNs): per gli avvisi del server resta la web app installata dalla Home; l'app nativa usa promemoria locali e l'aggiornamento in background.
- Certificato di 7 giorni, massimo 3 app. **Il widget consuma un App ID in più** (l'app ne usa 2 contro il limite di 10 nuovi identificativi a settimana): se SideStore protesta, togli il target `SchieraxiWidget` da `project.yml` e la riga `dependencies`.
- Niente TestFlight né App Store.
- Mai in git: firme, certificati, profili, password, Apple ID.
