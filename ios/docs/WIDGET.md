# Widget di SchieraXI: quali, in che misure, con quali dati

Tutti leggono UNA chiamata compatta, `GET /api/widget` (token `fw_` a scopo limitato, sempre `If-None-Match`; 304 = dati uguali, 202 = il server sta calcolando e il widget tiene quelli di prima). La lega non usa il capitano e non ha una classifica della lega nei dati: niente widget per quelle due cose.

| Widget | piccolo | medio | grande | extra large (iPad) | cerchio | rettangolo | riga | Motivo |
|---|---|---|---|---|---|---|---|---|
| Prossima giornata | si | si | no | no | si | si | si | conto alla rovescia vivo; grande ed extra large non aggiungerebbero dati |
| Formazione consigliata | si | si (campo mini) | si (campo con cognomi) | si (campo + lista) | si | si | si | i volti sul campo sono il dato |
| Da controllare | no | si | si | no | no | si | no | servono almeno 2-3 nomi per avere senso |
| Chi gioca (orari) | no | si | si | si (2 colonne) | no | si | si | serve un nome, un orario e un avversario |
| Crediti e svincolo | si | si | no | no | si | si | si | un numero e un suggerimento: grande sarebbe vuoto |
| Stato dei dati | si | no | no | no | si | si | si | un'informazione sola (per la diagnosi) |
| Cruscotto | no | no | si | si (2 colonne) | si | si | si | tutto prima di una giornata: scadenza viva, formazione, dubbi, scambio, svincolo, attesi e fatti, crediti; ogni blocco apre la sua schermata |
| Punti attesi e fatti | si | si (grafico) | si (grafico e tabella) | no | si | si | si | dal diario: quanto hai fatto contro il previsto; serve a fidarsi delle previsioni |
| Partite live | no | si | si | no | no | si | si | punteggio e minuto delle partite in corso con i tuoi titolari (volto e cognome); senza partite in gioco mostra le prossime. Aggiornamento ogni 2 minuti nelle finestre di gioco (iOS puo rimandare); dal campo `live` di /api/widget |
| Giocatore osservato (scelta nelle impostazioni del widget) | si | si | no | no | si | si | si | un giocatore a tua scelta tra osservati, rosa e titolari |
| Miglior scambio | si | si | si | no | no | si | si | solo se il server lo ha gia' in cache (apri Scambi nell'app); altrimenti dice di aprire l'app |

Da fare: niente di fisso. Stile e modulo: il server non li mette in `/api/widget`.

## Collegamento automatico (Apple ID gratuito + SideStore)

L'utente non compila niente: l'app passa al widget l'indirizzo e il token `fw_` da sola. Come firma SideStore (sorgenti, ramo `develop`, novembre 2026):
- [verificato nel codice] registra il gruppo `group.it.schieraxi.app` come `group.it.schieraxi.app.<SQUADRA>`, uguale per app e widget (`FetchProvisioningProfilesOperation.adjustedGroupIdentifier`), e aggiunge la squadra al bundle id (`it.schieraxi.app.<SQUADRA>`).
- [verificato nel codice] dal commit 7866508 (15/9/2026) NON scrive più `ALTAppGroups` in Info.plist (prima sì; AltStore sì). Il nome vero si legge dal profilo `embedded.mobileprovision` di ogni pacchetto (`ProfiloFirma`), poi si prova con `containerURL(forSecurityApplicationGroupIdentifier:)`. Era il motivo per cui il widget restava da collegare.
- [verificato nel codice] firma con i permessi del profilo, solo quelli che l'app dichiara (ldid in `ipa.yml`); per `keychain-access-groups` tiene i gruppi dell'app e cambia il prefisso (prima del primo punto) con la squadra (`ALTSigner.swift` di AltSign). Da qui il ripiego: Keychain condiviso `<SQUADRA>.it.schieraxi.app.condiviso` (`PortachiaviCondiviso`). Il token della sessione resta nel gruppo privato dell'app.
- [da verificare sul telefono] che il profilo gratuito contenga davvero gruppo e `keychain-access-groups` e che widget e app vedano gli stessi dati. La riga Impostazioni > App lo dice: «Widget collegato automaticamente» o «Widget: tocca per collegare»; i dettagli in Avanzate > Diagnostica widget («gruppo sì/no · portachiavi sì/no»).

Ordine per indirizzo e token (`CodiceWidget.destinazione`, provato nei test): App Group con token > Keychain condiviso con token > codice incollato > indirizzo dell'app senza token > server pubblico (`ServerPubblico.indirizzo`). Il widget non chiede più l'indirizzo.

Ultimo ripiego (se né gruppo né Keychain funzionano):
- Widget non collegato (il server risponde 401 o non c'è niente): dice **«Tocca per collegare»** e il tocco apre `schieraxi://widget/collega`.
- L'app (foglio «Collega il widget», `Presentation/Lega/CollegaWidgetView.swift`, anche dal passo Widget della guida e dalla riga delle Impostazioni) chiede il token `fw_` se manca e riprova l'automatico; solo se non va crea il codice (`CodiceWidget`, prefisso `schieraxi1.`) e lo mette negli appunti di questo telefono per 5 minuti (niente Appunti universali).
- L'utente tiene premuto il widget > «Modifica widget» > attiva «Collegamento manuale» > incolla in «Codice di collegamento» (il campo compare solo con l'interruttore acceso, `parameterSummary` con `When`).
- Il server tiene UN token per utente: quando l'app lo rinnova (a 7 giorni dalla scadenza dei 90) o si esce dall'account, il codice incollato smette di valere (con il collegamento automatico invece il token nuovo arriva da solo). Il widget mostra la copia vecchia con **«Tocca per ricollegare»** e lo stesso tocco.

Tocchi (indirizzi `schieraxi://`): widget da collegare -> `widget/collega`, scadenza -> `oggi`, modulo e punti -> `formazione`, volti e righe dei giocatori -> `giocatore/<id>`, scambio -> `scambi`, svincolo e crediti -> `mercato`, grafico attesi e fatti -> `lega`.

Anteprime: il target `AnteprimaWidget` (solo CI, non entra nell IPA) mostra i widget con dati finti in tutte le misure; il workflow `Screenshot` (`screenshot.yml`, insieme alle foto dell app) li fotografa su iPhone e iPad (chiaro, scuro, dati parziali o assenti) e carica l artifact `screenshot-widget`.
