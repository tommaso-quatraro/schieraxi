# 0003. La web è il riferimento per l'iPhone

Data: 2/11/2026. Stato: accettata.

## Contesto e problema
In un confronto sul telefono la stessa giornata compariva con numeri diversi sulla web e sull'iPhone. Chi usa le due app non
deve mai chiedersi quale numero è giusto.

## Fattori della decisione
- Una sola fonte di verità per testi, numeri e stati.
- La web cambia più in fretta e si prova in locale; l'iPhone si compila solo su Mac di GitHub.

## Opzioni considerate
- Ogni app con i suoi testi.
- L'iPhone come riferimento.
- La web come riferimento, con l'iPhone che la segue.

## Decisione
Scelta: la web è il riferimento (`docs/COERENZA-WEB-IPHONE.md`, testi in `fanta/web/testi.js`). Si prende la forma dell'iPhone
solo dove è chiaramente migliore, e allora si cambia anche la web. Ogni modifica a una schermata vale per tutte e due:
nella stessa pull request, oppure con un'issue «coerenza: …».

## Conseguenze
- Bene: stesso vocabolario su web, iPhone e widget.
- Male: una modifica di schermata costa due lati, o un'issue in più.
- Controlli: casella nel modello di pull request; le foto iOS su `main` si confrontano con la web (0006).
