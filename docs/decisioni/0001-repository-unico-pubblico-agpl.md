# 0001. Repository unico pubblico con licenza AGPL-3.0

Data: 1/11/2026. Stato: accettata.

## Contesto e problema
Server, web, sito e app per iPhone stavano in repository separati e privati. L'app iPhone si compila e si fotografa su Mac di
GitHub, che sui repository privati costano minuti a pagamento; SideStore installa l'app leggendo le release del repository.

## Fattori della decisione
- Costo zero per i controlli e per i Mac di GitHub.
- Una sola storia e una sola pull request per una modifica che tocca web e iPhone.
- Codice libero, ma chi offre una versione modificata come servizio deve condividerne il codice.

## Opzioni considerate
- Repository privati separati (com'era).
- Un repository unico privato.
- Un repository unico pubblico con licenza AGPL-3.0.

## Decisione
Scelta: repository unico pubblico `schieraxi`, licenza AGPL-3.0 (file `LICENSE`), con l'app iPhone in `ios/`. Actions gratuite,
release `build-N` lette da SideStore, una modifica = una pull request anche quando tocca due lati.

## Conseguenze
- Bene: controlli e Mac gratuiti; web e iPhone cambiano insieme.
- Male: tutto è pubblico, anche issue, pull request, log e foto. Niente segreti, indirizzi, email o dati personali da nessuna
  parte; i dati veri restano in `dati/` sul server, fuori da git.
- Controlli: `script/controlli/anti_residui.py` nel job `test`, zizmor sui workflow, skill `pubblica-repo` prima di ogni push,
  workflow con permessi minimi e niente segreti per le PR da fork.
