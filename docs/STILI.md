# Stili della formazione (preset)

Uno stile è un preset completo: sceglie insieme (a) il profilo di rischio dei giocatori (`peso`: quanto contano la brutta giornata e la giornata eccezionale rispetto ai punti attesi), (b) la preferenza di MODULO (`inclinazione` = punti in più per ogni difensore / ogni attaccante oltre il 4-x-3; sposta solo la scelta del modulo, non quella dei giocatori), (c) un testo di una riga. La panchina non dipende dallo stile: vedi «Panchina» più sotto.

Definizione: `LIVELLI_RISCHIO` in `fanta/formazione.py` (`id, nome, peso, inclinazione, descrizione`).

| id | Stile | peso (giù, su) | inclinazione (D, A) |
|---|---|---|---|
| -2 | Molto sicura | 1,5 / 0 | 0,5 / 0 |
| -1 | Sicura | 0,6 / 0 | 0,5 / 0 |
| 0 | Equilibrata | 0 / 0 | 0 / 0 (la consigliata: solo punti attesi) |
| 1 | Rischiosa | 0 / 0,25 | 0 / 0,5 |
| 2 | Molto rischiosa | 0 / 0,5 | 0 / 0,5 |

**Nota (12/11/2026, #612).** «Equilibrata» è la consigliata e sceglie la formazione con più punti attesi: il suo peso è zero (`PESO_BASE`). Prima toglieva 0,15 × (punti attesi − brutta giornata): una prudenza che costava qualche decimo e non comprava niente di misurabile (misura più sotto). Gli altri stili restano come sono: scelgono con il proprio punteggio (punti attesi meno una penale per la brutta giornata, o più un premio per quella eccezionale) e con la propria inclinazione del modulo, quindi possono mostrare meno punti attesi dell'«Equilibrata». Il numero mostrato è sempre quello della formazione scelta da quello stile.

Due eccezioni al «massimo dei punti attesi», tutte e due volute:
- un titolare che quasi certamente non gioca (meno del 20%) lascia il posto a un compagno di ruolo che gioca almeno il 20%, se costa meno di 0,5 punti attesi (#329, `_senza_improbabili`; fino alla revisione di #612 serviva un compagno al 50% e il tetto era 0,3: con chi è improbabile in fondo alla panchina non bastava più, vedi sotto);
- la ricerca prova, al posto di ogni titolare, i due migliori esclusi del ruolo per «gioca N% × fantavoto atteso». Provare anche i due con il fantavoto atteso più alto trova in media 0,04-0,08 punti attesi in più con la panchina lunga per ruolo, ma i punti veri non lo confermano e i titolari che giocano meno del 50% salgono da 0,3 a 0,7 per formazione: non si fa (misura in `formazione._candidati`).

## Punti attesi esatti (12/11/2026, #612)
I punti attesi di una formazione si contano, non si stimano: dalla probabilità di voto di ognuno si calcola la probabilità che ogni riserva entri (`Valutatore._media_esatta`). Senza cambio di modulo il conto va reparto per reparto, con ogni panchina; con il cambio di modulo si contano tutti i casi fino a `MAX_CASI` (32.768: bastano per 8 riserve di movimento con 3 cambi, 7 con 5 cambi), oltre restano le simulazioni per tutti i moduli della lega insieme. Le simulazioni (600, seme 7) servono ancora per il modificatore difesa, per l'oscillazione e per la brutta giornata e la giornata eccezionale degli stili.

Effetto: la scelta non dipende più dal seme. Dove la lega usa il modificatore difesa resta un rumore piccolo, tra difensori o portieri quasi pari (fantavoto atteso diverso di 0,02 in mediana).

## Panchina (12/11/2026, #612)
Chi va in panchina resta scelto per «gioca N% × fantavoto atteso». L'ordine è per fantavoto atteso: una riserva entra solo se ha preso voto, e a quel punto conta quanto vale quando gioca. Per ruolo: i ruoli nell'ordine della lega, dentro il ruolo chi vale di più. Libera: chi vale di più, di ogni ruolo. Chi quasi certamente non gioca (meno del 20%) sta dopo gli altri: per i punti attesi non cambia quasi niente, ma un infortunato per primo in panchina sembra un errore (con le probabili della giornata 12 succedeva in 9 squadre su 10).

## Misura prima e dopo (12/11/2026, #612)
Giornate già giocate dall'archivio (2025-26 dalla 5ª, 2026-27 dalla 2ª all'11ª), solo i dati di prima di ogni giornata, senza probabili. 440 rose estratte a sorte (10 per giornata, 44 giornate) e 97 casi squadra-giornata delle rose di una lega; punti veri con sostituzioni e modificatore. Tra parentesi quadre l'intervallo al 95% ricampionando le giornate intere. «Punti attesi» = lo stesso metro per prima e dopo (sostituzioni esatte, modificatore con 40.000 simulazioni).

| Regole | Rose | Punti veri, dopo meno prima | Punti attesi, dopo meno prima | Un altro seme cambia un titolare: prima → dopo |
|---|---|---|---|---|
| per ruolo, 11 in panchina, 5 cambi, modificatore | a sorte (440) | +0,33 [+0,04; +0,61] | +0,19 [+0,17; +0,20] | 51% → 17% |
| per ruolo, 11 in panchina, 5 cambi, modificatore | della lega (97) | −0,01 [−0,45; +0,49] | +0,13 [+0,11; +0,15] | 51% → 20% |
| libera, 7 in panchina, 3 cambi, cambio modulo | a sorte (440) | +0,23 [−0,04; +0,49] | +0,21 [+0,19; +0,22] | 86% → 0% |
| libera, 7 in panchina, 3 cambi, cambio modulo | della lega (97) | +0,42 [+0,01; +0,83] | +0,23 [+0,20; +0,27] | 82% → 0% |

Letture oneste: (1) i punti attesi salgono di 0,13-0,23 in tutti i casi, quelli veri non scendono in nessuno e salgono di 0,2-0,4 dove il campione basta a vederlo; sulle 97 rose della lega con le sue regole la differenza non si distingue da zero; (2) quanto pesa ogni pezzo, in punti attesi: l'ordine della panchina 0,11-0,18, il peso zero 0,02-0,04, il conto esatto 0,00-0,03; (3) il tempo di una scelta scende da 30-43 a 23-28 millisecondi (le simulazioni si fanno solo quando servono); con tutti e cinque gli stili, come li calcola l'app, resta quello di prima (da -3% a +10%).

Con le probabili (giornata 12, 10 squadre): i titolari che giocano meno del 50% passano da 7 a 10 su 110, e uno gioca meno del 20% (un portiere al 19% che quando gioca vale 1,6 punti più del titolare sicuro: toglierlo costerebbe 0,32 punti attesi, appena sopra la soglia di 0,3 della regola #329; con la media simulata di prima il conto dava 0,30 scarso e la regola lo toglieva).

## Misura degli stili (backtest, 30/10/2026)
Fatta quando l'«Equilibrata» aveva ancora il peso 0,15. Rose della lega (10 squadre) sulle giornate già giocate dall'archivio (76 casi squadra-giornata con rosa sufficiente), 100 simulazioni, punti veri a giornata con le regole della lega. Differenza dalla Equilibrata (69,29 punti), errore standard in parentesi; con un campione così piccolo sotto circa ±0,3 è rumore.

| Prova | punti | differenza |
|---|---|---|
| Equilibrata | 69,29 | 0 |
| Sicura (solo peso) | 69,38 | +0,09 (0,09) |
| Sicura + D 0,5 | 69,47 | +0,18 (0,16) |
| Sicura + D 1,0 | 69,53 | +0,24 (0,22) |
| Molto sicura (solo peso) | 68,33 | -0,96 (0,44) |
| Molto sicura + D 0,5 | 68,25 | -1,04 (0,46) |
| Rischiosa (solo peso) | 69,61 | +0,32 (0,31) |
| Rischiosa + A 0,5 | 69,38 | +0,09 (0,33) |
| Molto rischiosa (solo peso) | 69,55 | +0,26 (0,32) |
| Molto rischiosa + A 0,5 | 69,24 | -0,05 (0,36) |

Letture oneste: (1) spostare il modulo non costa punti oltre il rumore; (2) il vantaggio dei preset è nel profilo, non nei punti medi: i punti non salgono in modo dimostrabile, cambia solo il carattere della scelta; (3) «Molto sicura» costa circa 1 punto a giornata (già così prima, il modulo non cambia il conto); (4) con la qualità attuale dei dati il 4-3-3 resta il modulo più scelto da tutti gli stili, perché l'inclinazione verso gli attaccanti agisce poco: l'effetto visibile è soprattutto nelle difese folte (5-3-2 in 16 casi su 76 per Sicura). Da rimisurare quando ci saranno più giornate nell'archivio. Script di prova: stesso schema di `verifica` (nessun file del progetto toccato).

## API
`GET /api/formazione` (e per squadra): ogni voce di `livelli` ora ha `stile` (uguale a `rischio`, id numerico -2..2), `nome`, `descrizione` (una riga in italiano), `modulo` (consigliato dallo stile), `punteggio_atteso`, `dev`, `dev_simulata`, `intervallo`, `moduli[]` (per modulo: `modulo, punteggio_atteso, dev, dev_simulata, intervallo, titolari[], panchina[]`). `intervallo` = `{basso, alto, confidenza: 0.8, indicativo}` e `dev` sono calibrati sui punti veri (vedi `docs/INCERTEZZA.md`); `dev_simulata` è la vecchia deviazione della simulazione, utile solo per confrontare due formazioni. `stile_consigliato` = 0. Campi vecchi invariati (compatibile con i client esistenti). Il modulo scelto a mano resta fisso lato client finché si tocca uno stile; `GET /api/confronto?livello=<id>&modulo=<m>` invariato.
