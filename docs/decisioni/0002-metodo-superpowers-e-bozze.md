# 0002. Metodo Superpowers e pull request in bozza con revisione

Data: 2/11/2026. Stato: accettata.

## Contesto e problema
Le pull request del proprietario si uniscono da sole (job `unisci`) appena i controlli sono verdi, e da `main` il codice va
in produzione. Più agenti lavorano insieme: senza un metodo comune nascono lavori fuori piano, test scritti dopo il codice e
pull request unite prima di una revisione.

## Fattori della decisione
- Un metodo già scritto e provato, invece di regole nostre da mantenere.
- Nessuna pull request unita senza revisione, senza rallentare l'unione automatica.

## Opzioni considerate
- Regole scritte da noi per ogni fase.
- Le skill di [Superpowers](https://github.com/obra/superpowers) così come sono, più poche regole nostre.
- Togliere l'unione automatica.

## Decisione
Scelta: Superpowers per il «come» (idea, piano, test prima del codice, ricerca della causa, revisione, verifica); in questo
repository solo ciò che è nostro (`docs/METODO.md`). Chi sviluppa apre la pull request **in bozza**; chi coordina fa la
revisione e poi la toglie dalla bozza; a quel punto la unisce il job `unisci`. Le bozze non si uniscono mai.

## Conseguenze
- Bene: la revisione arriva sempre prima dell'unione; l'unione resta automatica.
- Male: un passo a mano (togliere la bozza) per ogni pull request.
- Controlli: `unisci` richiede `!github.event.pull_request.draft`; i controlli ripartono quando la bozza diventa pronta.
