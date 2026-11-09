# Decisioni di architettura

Qui stanno le decisioni importanti e il loro perché, una per file, così chi arriva dopo non le rifà da capo.
Formato: [MADR](https://github.com/adr/madr) riscritto in italiano, versione breve (`modello.md`).

- Un file per decisione: `NNNN-titolo-breve.md`, numeri in fila, mai riusati.
- Una decisione accettata non si riscrive: se si cambia idea se ne scrive una nuova che la «sostituisce» e nella vecchia si
  cambia solo lo stato («sostituita da NNNN»).
- Repository pubblico: niente indirizzi, email, nomi di persone o dettagli del server (`pubblica-repo`).

| N. | Decisione | Stato |
|---|---|---|
| [0001](0001-repository-unico-pubblico-agpl.md) | Repository unico pubblico con licenza AGPL-3.0 | accettata |
| [0002](0002-metodo-superpowers-e-bozze.md) | Metodo Superpowers e pull request in bozza con revisione | accettata |
| [0003](0003-la-web-e-il-riferimento.md) | La web è il riferimento per l'iPhone | accettata |
| [0004](0004-etichette-dal-server.md) | Le etichette dello stato del giocatore le manda il server | accettata |
| [0005](0005-niente-quote-ne-scommesse.md) | Niente quote né scommesse nel modello | accettata |
| [0006](0006-foto-ios-su-main.md) | Le foto iOS si fanno su `main` dopo l'unione | accettata |
| [0007](0007-revisione-ia-in-ci.md) | Revisione IA di ogni pull request in CI | accettata |
| [0008](0008-controlli-su-main-dopo-l-unione.md) | Dopo ogni unione i controlli girano anche su `main` | accettata |
| [0009](0009-gioca-probabili-si-ritara-sul-server.md) | «Gioca N%» con le probabili si ritara da solo sul server | proposta |
| [0010](0010-una-sola-fonte-per-i-testi.md) | I testi di web e iPhone nascono da un catalogo solo | accettata |
| [0011](0011-regressione-visiva-web-contro-main.md) | L'aspetto della web si confronta con `main` nella stessa corsa, per ora solo come avviso | accettata |
| [0012](0012-ambiente-di-prova-con-collaudo-automatico.md) | Ogni versione passa prima da un ambiente di prova collaudato in automatico | accettata |
| [0013](0013-giornata-senza-errori.md) | #167 si chiude con una «giornata senza errori», mai verde per omissione | accettata |
| [0014](0014-contratto-iphone-controllato-non-generato.md) | Il contratto fra iPhone e server si controlla, non si genera | accettata |
