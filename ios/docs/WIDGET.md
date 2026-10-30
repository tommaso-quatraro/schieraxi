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

Da fare (serve altro lavoro): Miglior scambio, Punti attesi e fatti (dal diario), Giocatore osservato (con scelta), Cruscotto (grande ed extra large). Stile e modulo: il server non lo mette in `/api/widget`.
