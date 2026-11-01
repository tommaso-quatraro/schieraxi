# Storia dello sviluppo

Le tappe principali dell'app iOS di SchieraXI, in ordine, con il mese e l'anno. Non è un registro completo: per il dettaglio ci sono i commit e le pull request di questo repository.

## Ottobre 2026

- **App nativa e test.** Prima versione in SwiftUI con le schermate di base (Oggi, Formazione, Mercato, Lega) e i primi test automatici.
- **Compilazione in cloud.** Build, test e screenshot sui Mac di GitHub Actions; poi alleggeriti (concorrenza, test su PR e `main`, screenshot solo a richiesta).
- **Accesso multiutente.** Login, registrazione, account nella lega, codice di recupero. Poi revisione «da attaccante»: token nel Keychain, limiti di richieste con conto alla rovescia, test avversari.
- **Importazione delle rose** da file CSV e di testo, con abbinamento a mano dei giocatori non riconosciuti.
- **Grafica in stile Apple.** Liquid Glass, scheletri di caricamento animati, layout per iPad, colori semantici condivisi con la web app.
- **Identità e marchio.** Nome, icona e marchio animato; più avanti la rinomina totale in SchieraXI.
- **Avatar.** Prima foto, poi volti illustrati e vettoriali generati dal codice del giocatore, in tre versioni, uguali su web e app.
- **Widget.** Formazione, punti attesi, chi gioca, scambi, cruscotto; modalità colorata e StandBy; collegamento con un codice e un token a scopo limitato; testo grande di sistema.
- **Formazione e diario.** Stili di rischio, fascia dei punti attesi, ballottaggi, modifica a mano, confronto fra consigliata e schierata.
- **Partite in diretta** nella schermata Oggi, con gol e rossi in due colonne.
- **Scambi** in più modi (anche N contro M con conguaglio) e contatore delle ricerche.
- **Accessibilità.** Contrasti 4,5:1, bersagli di tocco da 44 pt, annunci per VoiceOver, rispetto di «Riduci movimento», testo grande senza tagli.
- **Semplificazione.** Meno funzioni in vista (menu a poche voci), impostazioni a gruppi, configurazione guidata al primo avvio.
- **Distribuzione.** Installazione con SideStore e sorgente per gli aggiornamenti, avviso di nuova versione nell'app.
- **Repository pubblico.** Licenza AGPL-3.0, nota su marchi e fonti di terzi, privacy manifest, pagine di informazioni legali, dati di prova inventati, nell'app distribuita solo l'indirizzo pubblico predefinito, nessun indirizzo privato.

## Novembre 2026

- Accesso con Google, richieste in lingua italiana, widget che leggono le funzioni accese.
- Server salvato non più valido: l'app passa a quello predefinito, e «Esci» e «Cambia server» sono sempre disponibili.
- Testi più semplici per errori e copie di sicurezza, rinomina totale in SchieraXI.
