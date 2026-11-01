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

## Collegamento (Apple ID gratuito + SideStore)

Non è sicuro che SideStore registri l'App Group con l'Apple ID gratuito (mai provato su un telefono vero): il widget NON deve dipenderne.
- Widget non collegato (manca il server, o il server risponde 401): dice **«Tocca per collegare»** e il tocco apre `schieraxi://widget/collega`.
- L'app (foglio «Collega il widget», `Presentation/Lega/CollegaWidgetView.swift`, anche dal passo Widget della configurazione guidata) chiede il token `fw_` se manca, crea il codice di collegamento (`CodiceWidget`, prefisso `schieraxi1.`) e lo mette negli appunti di questo telefono per 5 minuti (niente Appunti universali).
- L'utente tiene premuto il widget > «Modifica widget» > incolla in «Codice di collegamento» (primo campo). Fatto una volta.
- Il server tiene UN token per utente: quando l'app lo rinnova (a 7 giorni dalla scadenza dei 90) o si esce dall'account, il codice incollato smette di valere. Il widget mostra la copia vecchia con **«Tocca per ricollegare»** e lo stesso tocco.
- Ordine per indirizzo e token (`CodiceWidget.destinazione`, provato nei test): App Group con token > codice incollato > App Group senza token > indirizzo scritto nel widget.

Tocchi (indirizzi `schieraxi://`): widget da collegare -> `widget/collega`, scadenza -> `oggi`, modulo e punti -> `formazione`, volti e righe dei giocatori -> `giocatore/<id>`, scambio -> `scambi`, svincolo e crediti -> `mercato`, grafico attesi e fatti -> `lega`.

Anteprime: il target `AnteprimaWidget` (solo CI, non entra nell IPA) mostra i widget con dati finti in tutte le misure; il workflow `Screenshot` (`screenshot.yml`, insieme alle foto dell app) li fotografa su iPhone e iPad (chiaro, scuro, dati parziali o assenti) e carica l artifact `screenshot-widget`.
