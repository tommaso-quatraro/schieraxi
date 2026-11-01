# Linee guida dell'interfaccia di SchieraXI (iOS, riusabili su web e Android)

Scritte il 30/10/2026 dopo la revisione di Mercato > Consigliati. Valgono per ogni schermata.

1. **Una cosa principale per riga.** Il dato che decide (guadagno in punti, fantavoto atteso, conto alla rovescia) è grande, in grassetto e a destra o in alto. Il resto è piccolo (`caption`) e in grigio secondario, leggibile ma mai dominante.
2. **Il secondario in una riga sola.** Rimborso, costo, crediti, giornate considerate: una riga unica separata da «·», massimo due righe a capo. Mai un blocco per ognuno.
3. **Niente muri di testo.** Una spiegazione lunga diventa una riga di riepilogo («12 svincolati analizzati · crediti 40») più un pulsante «i» che apre il dettaglio. Il dettaglio non è visibile di default.
4. **Avatar nelle card.** Ogni giocatore ha il suo volto illustrato (stesso id, stesso volto su ogni piattaforma). L'entrante o il protagonista è grande (44 pt); il secondario è piccolo (18 pt) accanto al nome.
5. **Non ripetere.** Se il titolo della schermata dice «Mercato», la card non lo ripete. Se un numero è nella riga sopra, non è anche nel testo sotto.
6. **Barre di scelta (tab, segmenti).** Le etichette stanno su una riga e hanno la loro larghezza vera (mai troncate né sovrapposte). Se non ci stanno tutte, la barra scorre di lato e tiene visibile quella scelta. Mai testo che si sovrappone.
7. **Una sola barra in basso.** Niente elementi fissi sotto la barra delle schede (il conto alla rovescia sta nell'intestazione di Oggi e nel widget). L'ultima card non finisce mai sotto la barra: margine in basso su ogni lista.
8. **Densità compatta di default.** Margini piccoli, più contenuto per schermo; le aree di tocco restano da 44 pt. Non si sceglie (Aspetto ha solo tema e animazioni).
9. **Tablet: più colonne.** Dove l'iPhone ha una colonna, l'iPad ne ha due o tre (le card compatte stanno bene in griglia), con barra laterale al posto delle schede.
10. **Colore con significato.** Verde = bene/azione, arancio = attenzione, rosso = male, lime = selezione. Mai il solo colore: sempre anche testo o simbolo.
11. **Testo grande e VoiceOver.** Tutto deve reggere Dynamic Type grande (a capo o scroll, mai troncato); ogni card ha una frase completa per VoiceOver («Entra X, esce Y, +2,4 punti attesi. Rimborso…»).
12. **Movimento sobrio.** Dissolvenze e molle leggere; con «Riduci movimento» niente spostamenti, solo dissolvenze e il marchio che respira (opacità).

Prima/dopo di Mercato > Consigliati: la card di prova era alta circa 150 pt con tre blocchi di testo e il nome dell'uscente a sinistra e quello dell'entrante a destra su altezze diverse; ora è alta circa 80 pt, con avatar, nome, uscente in piccolo, guadagno a destra e una riga di dettagli.
