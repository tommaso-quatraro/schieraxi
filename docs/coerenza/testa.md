# Web e iPhone uguali

Scritto il 2/11/2026 dopo un confronto su telefono: la stessa giornata era «Giornata 10» in testa alla web, «Giornata 7» in
Oggi e «Giornata 7 di lega (Serie A 10)» sull'iPhone. Chi usa le due app non deve mai chiedersi quale numero è giusto.

## La regola
1. **La web app è il riferimento.** Testi, numeri, forme e stati dell'iPhone sono quelli della web (`fanta/web/testi.js`).
2. Si prende la forma dell'iPhone solo dove è chiaramente migliore. In quel caso si cambia anche la web, e la scelta si scrive
   qui nel vocabolario.
3. **Ogni modifica a una schermata vale per tutte e due.** Una PR che cambia un testo, un numero o uno stato su un lato
   aggiorna anche l'altro. Se non può, perché l'altro lato è di un altro agente o di un'altra PR, apre un'issue «coerenza:
   …» con il testo esatto e la cita nella PR.
4. I numeri arrivano dal server e non si ricalcolano sul client: fantavoto atteso, «gioca N%», punti attesi e fascia.
5. Il widget dell'iPhone e Android seguono lo stesso vocabolario.
