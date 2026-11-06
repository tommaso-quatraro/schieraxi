# 0009. «Gioca N%» con le probabili si ritara da solo sul server

Data: 6/11/2026. Stato: proposta.

## Contesto e problema
Le costanti che trasformano le probabili formazioni in «gioca N%» (`modello._p_da_probabili`) sono scelte a mano. Per tararle
servono le giornate giocate con le probabili salvate prima della scadenza, e quelle stanno solo nell'archivio del server. Il 6/11
l'utente ha deciso: niente tabelle di calcio copiate sul PC, la taratura gira dove ci sono tutte le giornate (issue #379, L2 di #165).
Resta da decidere dove gira, come il risultato arriva all'app e chi decide di usarlo.

## Fattori della decisione
- I dati restano sul server; il repository è pubblico (niente dati veri).
- Nessun cambio di numeri non misurato: prova su giornate che la taratura non ha visto, con le soglie di I2 (D1 del 5/11).
- Nessun passo a mano a ogni giornata; un modo semplice per tornare indietro.
- Poco peso sul server (VPS piccolo) e nessun rischio per il servizio web.
- Niente cambi di numeri a ridosso della scadenza della formazione.

## Opzioni considerate
- **A.** Comando `python -m fanta taratura-probabili` in fondo a `script/server/aggiorna.sh`; coefficienti in una tabella
  dell'archivio; si accende e si spegne da solo secondo la prova, con avviso al proprietario.
- **B.** Stesso calcolo nel thread del registro delle giornate, dentro il servizio web, subito dopo la misura della giornata.
- **C.** Il server calcola e mostra i numeri; i coefficienti entrano in `modello.py` con una PR a ogni nuova taratura.
- **D.** Una riga nuova nel crontab del server, di notte.
- **E.** Calcolo sul PC o in CI con una copia dei dati (esclusa dall'utente il 6/11).

## Decisione
Scelta: «A». Lo script si aggiorna da solo con l'app, ha già il blocco degli aggiornamenti e la priorità bassa, e un errore non
tocca il servizio web (contro B). Non serve un passo a mano a ogni giornata e nessuno dovrebbe copiare in una PR numeri che sul PC
non si possono rifare (contro C). Non serve cambiare la configurazione del server (contro D).
Il risultato arriva all'app dalla tabella `taratura_probabili` dell'archivio: il modello usa la riga `attiva`, e ogni cambio scrive
una riga in `aggiornamenti`, così le previsioni si ricalcolano come dopo un aggiornamento dei dati.
Piano: `docs/superpowers/plans/2026-11-06-gioca-probabili-server.md`.

## Conseguenze
- Bene: «gioca N%» migliora da solo man mano che arrivano giornate; ogni versione resta nella tabella con coefficienti, giornate
  e misura, ed è nella copia notturna.
- Male: i numeri mostrati possono cambiare senza una PR; la taratura non si rifà sul PC.
- Freni: prova sulla metà più recente delle giornate (Brier almeno lo 0,5% più basso, calibrazione ≤ 5 punti, Brier ≤ 0,15);
  ritorno ai numeri di partenza se peggiora; niente cambi nelle 24 ore prima della prima partita; avviso al proprietario a ogni
  cambio; `python -m fanta taratura-probabili --spegni` vale subito.
- Controlli: test in `tests/test_taratura_probabili.py`; `python -m fanta verifica` identica in ogni PR (non usa le probabili);
  il registro delle giornate continua a misurare I2 sui numeri mostrati e avvisa se esce dalle soglie.
