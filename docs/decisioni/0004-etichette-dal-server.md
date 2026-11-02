# 0004. Le etichette dello stato del giocatore le manda il server

Data: 2/11/2026. Stato: accettata.

## Contesto e problema
Lo stato di un giocatore («Ha giocato», «Voto in arrivo», «In dubbio»…) era ricavato da web e iPhone ognuno con le sue regole,
e le due app finivano per dire cose diverse sullo stesso giocatore.

## Fattori della decisione
- Una regola sola per web, iPhone e widget.
- Sul server si lavora con i test prima del codice; sull'iPhone ogni prova costa un Mac di GitHub.

## Opzioni considerate
- Ogni client calcola l'etichetta dai campi grezzi.
- Il server manda l'etichetta pronta.

## Decisione
Scelta: il server manda il campo `etichetta` di ogni giocatore (`fanta/etichette.py`, documentato in `docs/API.md`); i client
la mostrano senza ricalcolarla. Vale anche per le frasi e gli stati nuovi: si decidono sul server.

## Conseguenze
- Bene: stesse parole ovunque; un cambio di testo è una sola pull request sul server, con i suoi test.
- Male: un'etichetta nuova richiede una versione del server prima che i client la mostrino.
- Controlli: revisione delle pull request dei client (niente regole di stato ricalcolate in `ios/` o in `fanta/web/`).
