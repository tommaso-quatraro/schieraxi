# SchieraXI senza aspetto da AI

Scritto il 2/11/2026 dopo un giro di foto su web (390 e 1440 px, chiaro e scuro), sito e iPhone.
Obiettivo: chi apre l'app deve pensare «l'ha disegnata uno che guarda il calcio», non «l'ha generata un programma».
Vale per web, sito e iPhone. Le regole di base restano in `DESIGN.md` (scala, colori, componenti) e `COERENZA-WEB-IPHONE.md`
(parole e numeri): qui c'è solo cosa evitare e perché.

## Cosa resta (è SchieraXI, non è da AI)
- Il nome e il marchio a 11 punti con il capitano lime (`MARCHIO.md`).
- Il verde del campo e il lime del capitano come colori di marca. Il lime si usa solo per la selezione e per il capitano.
- Il campo con le pedine, i volti illustrati e le sigle a tre lettere nei colori sociali: sono le cose che ha solo questa app.
- Le parole del vocabolario comune: «gioca 92%», «vs PAR» / «@ UDI», «Giornata 7».

## Principi
1. **Una cosa audace per schermata.** Oggi: il conto alla rovescia o i punti. Formazione: il campo. Scheda: il fantavoto atteso.
   Mercato: il guadagno in punti. Tutto il resto è quieto.
2. **I dati sono i protagonisti**, come su un tabellone o nella pagina dei voti del lunedì: numeri grandi, cifre tabellari,
   colonne allineate a destra, nomi in grassetto, il resto in grigio.
3. **Meno contenitori, più tipografia.** Una carta solo se raggruppa davvero qualcosa. Dentro una carta: righe e spazio, mai
   un'altra carta. I gruppi si separano con un titolo e con lo spazio, non con una scatola in più.
4. **Testi brevi e attivi.** Una frase dice cosa succede o cosa fare. La spiegazione lunga sta dietro «Come si legge».
5. **Il colore ha un significato.** Verde = bene/guadagno, rosso = male/rischio, arancio = dubbio, lime = scelto. Mai colore
   per decorare, mai un colore diverso per ogni riga.

## Segni vietati
| Segno | Perché sa di AI | Al suo posto |
|---|---|---|
| Sfondo con macchie sfumate che si muovono (verde, blu, giallo) | È lo sfondo «aurora» di mille modelli | Fondo piatto `--sfondo` |
| Vetro con riflessi ovunque: gradiente lucido, bordo luminoso in alto, ombra grande sotto ogni carta | Kit generico; tutte le carte uguali | Superficie piena, un gradino di tono sopra il fondo, bordo sottile, niente ombra |
| Pulsanti lucidi con alone colorato | «Get started» luminoso | Pulsante piatto, un colore pieno |
| Aloni e pallini luminosi (`box-shadow: 0 0 8px`) | Decorazione senza informazione | Pallino pieno, o niente |
| Etichette MAIUSCOLE spaziate sopra ogni blocco («MODULO», «PORTIERI (3)», «PUNTI IN STAGIONE») | L'«eyebrow» è il segno più riconoscibile | Minuscolo con l'iniziale maiuscola, 13 px, grigio `--testo-2`, senza spaziatura |
| Una parola del titolo colorata o a gradiente («giornata dopo giornata» verde) | Trucco da pagina generata | Titolo di un solo colore |
| Emoji come icone («✨ Novità») | Infantile e generico | Parole |
| Freccia «→» o «←» incollata a pulsanti e link («← Squadra», «Apri la web app →») | Tic da template | Il pulsante dice l'azione; per tornare indietro la freccia è un'icona, non testo |
| Tre colonne uguali con numero in un cerchio (1, 2, 3) per cose che non sono passi | Sezione «features» da template | Una frase per cosa, o un elenco vero |
| Entrata a dissolvenza dal basso di ogni blocco, una dopo l'altra | Movimento di riempitivo | Nessuna entrata per le sezioni; il movimento solo dove racconta il calcio (pedine, modulo) |
| Comparsa allo scorrimento di ogni sezione del sito | Se non scatta resta una fascia vuota | Contenuto visibile subito |
| Pillole e chip ovunque, due segni di stato per riga | Rumore | Un solo segno di stato per riga |
| Arcobaleno di colori per una sola misura (5 pallini di forma in 3 colori, 5 caselle del calendario in 5 colori) | Colore come decorazione | Un colore solo con l'intensità, oppure il numero e basta |
| Titoli che sono domande («Rende sopra o sotto le occasioni?») | Tono da marketing | Un nome: «Gol e assist rispetto alle occasioni» |
| Frasi lunghe ripetute sopra ogni elenco | Il modello spiega tutto | Una riga; il resto in «Come si legge» |
| Stringhe di dati unite da « · » su tre righe | Muro di testo | Una riga secondaria con al massimo 3 dati, il resto nella scheda |

## Il pavimento (regole che valgono sempre)
Adattate dal «Floor» di Hallmark. Si controllano a mano prima di ogni PR che tocca lo stile.
1. **Token in `:root`.** Ogni colore e ogni carattere passa da una variabile di `:root` (o dal blocco del tema). Eccezioni ammesse:
   il campo (bianco sulle pedine) e i colori sociali delle squadre, che sono dati.
2. **`:focus-visible`** su tutto ciò che si tocca, subito, senza animazione.
3. **`prefers-reduced-motion`** (e Aspetto > Animazioni > Ridotte): ogni animazione ha la versione calma (`MARCHIO.md`, «Movimento»).
4. **Cifre tabellari** (`font-variant-numeric: tabular-nums`) su ogni numero che sta in colonna o cambia: punti, voti, crediti, ore.
5. **Mai `transition: all`.** Si animano solo `transform`, `opacity`, colori e ombre; mai `width`, `height`, `top`, `left`.
6. **Titoli al massimo su 2 righe** a 390 px. Se non ci stanno si accorciano, non si rimpiccioliscono.
7. **Niente carta dentro una carta**, niente emoji come icone, niente gradiente viola-blu.
8. **Etichette in minuscolo** (iniziale maiuscola), mai maiuscole spaziate. Unica eccezione: le sigle delle squadre (sono nomi).
9. **Niente numeri inventati** nel sito: solo dati veri o esempi detti esempi.
10. **Circa 80 parole per schermata** di testo che non sia un dato (nomi e numeri non contano).

## Prima e dopo
| Dove | Prima | Dopo |
|---|---|---|
| Fondo | macchie verdi, blu e gialle sfocate che si muovono | fondo piatto, il verde sta nel campo e nei dati |
| Carte | vetro lucido, riflesso che segue il dito, ombra grande | superficie piena, bordo sottile |
| Formazione, etichette | «MODULO», «STILE» | «Modulo», «Stile» |
| Formazione, nota | «Hai modificato la formazione a mano: tocca un modulo o uno stile per tornare alla scelta automatica.» | «Modificata a mano. Tocca un modulo o uno stile per tornare alla consigliata.» |
| Oggi, novità | «✨ Novità nell'app (versione 1.353): tocca per vedere» | «Novità della versione 1.353» |
| Rosa, indietro | «← Squadra» | «Squadra» con l'icona della freccia |
| Mercato | «PUNTI IN STAGIONE» | «punti in stagione» |
| Diario | 9 righe di spiegazione in cima | una riga; il resto in «Come si legge» |
| Sito, titolo | «La formazione giusta, *giornata dopo giornata*» con la seconda metà a gradiente | stesso titolo, un colore |
| Sito, pulsante | «Apri la web app →» | «Apri la web app» |

## Come si controlla
- Foto a 390 e 1440 px, chiaro e scuro, delle schermate toccate (prima e dopo, stessi dati).
- Cerca nel CSS: `text-transform: uppercase`, `letter-spacing: .0[6-9]em|.1`, `box-shadow: 0 0`, `backdrop-filter`,
  `transition: all`, `linear-gradient(` sulle superfici. Ognuno deve avere un motivo scritto accanto.
- Cerca nei testi: `✨`, `→`, `←`, frasi oltre le 2 righe a 390 px.
