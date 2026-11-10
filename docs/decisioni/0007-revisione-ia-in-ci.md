# 0007. Revisione IA di ogni pull request in CI

Data: 2/11/2026. Stato: accettata (attiva quando c'è il segreto `CLAUDE_CODE_OAUTH_TOKEN`).

## Contesto
Le pull request del proprietario si uniscono da sole appena i controlli sono verdi (job `unisci`). I test fermano ciò che
rompe un test, non un controllo di accesso dimenticato, un errore inghiottito o una schermata cambiata su un lato solo.
La revisione fatta dagli agenti prima della pull request a volte manca o è parziale: serve un secondo sguardo che non si salta.

## Decisione
- Ogni pull request non in bozza, aperta da un ramo di questo repository e non da un bot, passa una revisione con Claude Code
  tramite l'azione ufficiale `anthropics/claude-code-action` (job `revisione-ia` di `test.yml`, che chiama `revisione.yml`).
- Le istruzioni stanno nella skill `.claude/skills/revisione-pr/SKILL.md`. L'azione, prima di avviare Claude, rimette
  `.claude/` e `CLAUDE.md` come sono su `main`: una pull request non può cambiare le regole con cui viene rivista.
- Claude scrive i commenti sulle righe e una sintesi, e restituisce `{"bloccanti": int, "sintesi": string}`. Il passo
  «Cancello» fallisce se l'esito manca o se `bloccanti > 0`; `unisci` aspetta `revisione-ia` verde.
- Senza segreto (prima che l'utente lo crei, o se lo toglie) il job passa senza revisione e lo scrive nel riepilogo.
  Una sola pull request, niente seconda pull request per «accendere» il blocco: il controllo sul segreto sta nel job.

## Sicurezza (il repository è pubblico)
- Solo evento `pull_request`: mai gli eventi che danno i segreti al codice di una PR da fork, né `workflow_run`. Le PR da fork non hanno segreti e il job non parte;
  le PR di Dependabot e degli altri bot non partono (`user.type != 'Bot'`) e comunque non vedono i segreti di Actions.
- Solo server di GitHub (`ubuntu-latest`). Permessi: `contents: read`, `pull-requests: write`. Niente `id-token`: l'azione usa
  il token del job (`github_token`) e non l'app di Claude.
- Claude rivede il codice della PR e basta (dal 6/11, #479): il job prepara il diff in `.revisione-ia/diff.patch` e l'elenco
  dei file in `.revisione-ia/file.txt` con `git diff` sul commit di unione, prima di avviare Claude, con gli attributi di
  `main` e in testo (un `.gitattributes` della PR non nasconde il codice). Claude non ha `gh`: descrizione, commenti e
  revisioni della PR non gli arrivano, e la skill non blocca per ciò che non si può verificare dal diff.
- Strumenti di Claude: `Skill`, `Read(./**)` (letture solo nella cartella del checkout; la regola vale anche per `Grep` e
  `Glob`) e i commenti sulle righe. Divieti espliciti (`--disallowedTools`): Bash, scrittura, rete, sotto-agenti e le letture
  fuori dal checkout (file di sistema, cartella temporanea del job, configurazione dell'utente del runner, `.git`).
  `--max-turns 30`, `timeout-minutes: 25`, una corsa per pull request (le vecchie si annullano).
- La sintesi pubblicata passa da un filtro (passo «Cancello») che toglie ciò che somiglia a un token o a un segreto (forme
  note di token, valori di variabili con TOKEN, SECRET, PASSWORD o KEY nel nome, chiavi private, stringhe lunghe casuali) e
  le menzioni. Il filtro non cambia l'esito del cancello. Il cancello legge l'esito dal file dell'esecuzione dell'azione
  (`execution_file`), non da `env:`, che finirebbe nel log pubblico.
- Mai `allowed_non_write_users`, mai `allowed_bots`, `show_full_output` spento (i log sono pubblici). Il segreto passa per
  nome (niente `secrets: inherit`) e solo tramite `env`.

## Versioni
- Azione fissata per commit: v1.0.266, commit `d535f5172dec02b204866b393d6b20b9b2aaf98d` del 31/10/2026, adottata il 10/11 dopo i 7 giorni di attesa di Dependabot.
- La versione di Claude Code è scritta nell'azione (ogni versione dell'azione ha la sua) e si installa con lo script ufficiale: fissare
  l'azione fissa anche Claude Code. `path_to_claude_code_executable` permetterebbe di usarne un'altra, ma l'azione avvisa che
  versioni diverse possono non funzionare: non lo usiamo. Bun (1.4.4) e `oven-sh/setup-bun` sono fissati dentro l'azione.
- L'aggiornamento arriva da Dependabot come per le altre azioni: si legge il cambiamento prima di unirlo.

## Impostazione del repository
Il repository accetta solo azioni di GitHub più un elenco. Senza le due voci qui sotto l'intero workflow «Controlli»
non parte (anche `unisci`): vanno aggiunte PRIMA di unire questa decisione, e aggiornate quando cambia il commit dell'azione.
- `anthropics/claude-code-action@d535f5172dec02b204866b393d6b20b9b2aaf98d`
- `oven-sh/setup-bun@0c5077e51419868618aeaa5fe8019c62421857d6` (usata dentro l'azione)

## Conseguenze
- Ogni pull request consuma un po' dell'abbonamento Claude del proprietario (token OAuth di `claude setup-token`).
- Un falso «bloccante» ferma l'unione: se è davvero un falso allarme si corregge la skill su `main` con una pull request
  e si rilancia il job. Se la revisione si rompe (token scaduto, servizio giù) il job è rosso e la pull request aspetta.
- Se si toglie il segreto, la revisione si spegne senza bloccare nulla. Un token scaduto o revocato ma ancora nel segreto
  invece blocca (job rosso): il token di `claude setup-token` dura un anno, poi si rifà con gli stessi due comandi.

## Note
- 2/11/2026: alla prima corsa Claude non è riuscito a pubblicare la sintesi con `gh pr comment` (permesso negato). Ora la
  sintesi sta solo nell'esito e la pubblica il job, in un unico commento aggiornato a ogni giro; a Claude resta
  `gh pr diff/view` e i commenti sulle righe.
- 6/11/2026 (#479, irrobustimento): niente più `gh pr diff/view` (il diff lo prepara il job), letture limitate al checkout,
  filtro dei segreti sulla sintesi. Comportamento dell'azione da verificare alla prima corsa in CI (la prima volta che la PR
  esce dalla bozza). Da controllare: che `Grep` e `Glob` funzionino nel checkout con la sola regola `Read(./**)`.
