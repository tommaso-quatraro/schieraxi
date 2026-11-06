<!-- Modello del brief per un agente. Lo riempie `python script/squadra/squadra.py brief <issue>`: le parti tra doppie
graffe si riempiono da sole, quelle tra < > le scrive il coordinatore. Copia pubblica: niente percorsi personali,
indirizzi, nomi o token. Questo commento non finisce nel brief. -->
Compito: {{titolo}}. Issue #{{issue}}. Dove si inserisce: <una riga sul piano o sul ciclo>.
Agente: {{agente}}, modello {{modello}}.

Leggi prima: CLAUDE.md, MAPPA.md e docs/METODO.md del repository, poi l'issue #{{issue}} (è il requisito, con i valori da
usare tali e quali). Skill da caricare con lo strumento Skill: superpowers:test-driven-development,
superpowers:verification-before-completion, <altre skill del compito>.

PRIMO PASSO OBBLIGATORIO, prima di leggere o toccare codice: `git remote get-url origin` e `git remote get-url --push origin`
nella tua copia devono essere {{repository}}, push non disabilitato. Se no: fermati con BLOCCATO e scrivi cosa hai trovato.
Dove: la tua worktree; ramo {{ramo}} (`git switch -c {{ramo}}`).
Puoi toccare: {{tocca}}.
NON toccare: {{non_tocca}}. Se ti servono, scrivilo nel rapporto.
Già deciso: <interfacce e scelte già prese>.

Fatto quando:
{{fatto_quando}}
Verifiche: test visto rosso e poi verde; suite intera una volta (`.venv\Scripts\python.exe -m pytest -q -n 2`).
PR: aprila IN BOZZA con `gh pr create --draft --body-file <file>` (mai `--body` scritto al volo).
Descrizione: prima riga `Aree: …`, poi `Closes #{{issue}}` (o `Parte di #{{issue}}`), poi le sezioni `## Cosa cambia`,
`## Perché`, `## Come l'ho provato` (non vuote) e `## Revisione` vuota (la riempie il coordinatore). Mai `gh pr ready` sulla tua PR,
mai unire: una PR non in bozza si unisce da sola appena i controlli sono verdi, senza revisione.
iOS: non lanciare screenshot.yml e non mettere l'etichetta «screenshot»: scrivi «Foto da fare: <schermate>» nella PR
(`python script/squadra/squadra.py foto <PR>` le ricava dai file cambiati). Le foto si fanno su main dopo l'unione.

Non fare: unire a mano, toccare server o rete, lanciare altri agenti, lavorare fuori dalla tua area, aggiungere funzioni
non chieste.
Rapporto (≤10 righe, in italiano): stato FATTO / FATTO CON DUBBI / SERVE CONTESTO / BLOCCATO; commit; prove fatte con il
risultato; cosa NON è verificato; scelte prese («Scelta mia: … perché …»); worktree da togliere.
