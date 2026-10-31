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

Tocchi (indirizzi `schieraxi://`): scadenza -> `oggi`, modulo e punti -> `formazione`, volti e righe dei giocatori -> `giocatore/<id>`, scambio -> `scambi`, svincolo e crediti -> `mercato`, grafico attesi e fatti -> `lega`.

Anteprime: il target `AnteprimaWidget` (solo CI, non entra nell IPA) mostra i widget con dati finti in tutte le misure; il workflow `Screenshot` (`screenshot.yml`, insieme alle foto dell app) li fotografa su iPhone e iPad (chiaro, scuro, dati parziali o assenti) e carica l artifact `screenshot-widget`.
