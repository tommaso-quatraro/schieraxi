# Metodo di lavoro

Come si sviluppa SchieraXI, dall'idea al telefono. Vale per chi lavora a mano e per gli agenti di Claude Code.
Regole del repository: `CLAUDE.md`. Dove sta ogni cosa: `MAPPA.md`.

## Chi decide il metodo
- Per il **come** (idea, piano, test, ricerca dei difetti, revisione, verifica) si usano le skill del plugin
  [Superpowers](https://github.com/obra/superpowers) così come sono, senza riscriverle.
- Questo repository aggiunge solo ciò che è suo: ogni lavoro finisce in una pull request, le novità in `fanta/novita.d/`,
  il repository è pubblico, l'app per iPhone si compila e si fotografa su GitHub Actions, web e iPhone devono essere uguali,
  tutto in italiano semplice.

## Dall'idea al telefono
1. **Issue**: cosa, perché, «fatto quando…». Priorità `P1` (rotto o sicurezza), `P2` (da fare ora), `P3` (dopo).
   Gli obiettivi scendono dal generale allo specifico: quattro macro obiettivi sono issue con l'etichetta `obiettivo`
   (statistiche nostre affidabili, consiglio di formazione giusto e spiegato, app semplice e uguale su iPhone e web, app aperta
   agli altri) e ogni lavoro concreto è una loro sotto-issue, creata quando ci si lavora. Si lavora su un macro obiettivo alla
   volta; le idee nuove diventano issue `P3` sotto il macro obiettivo giusto e aspettano.
2. **Misura del lavoro** (skill `brainstorming`): compito chiaro, modifica piccola o progetto.
3. **Progetto**: spec in `docs/superpowers/specs/` e piano in `docs/superpowers/plans/` (skill `writing-plans`), uniti con
   una pull request di soli documenti prima di scrivere il codice.
4. **Codice**: ramo da `main` in una copia di lavoro propria; test che fallisce prima del codice (`test-driven-development`;
   il codice già scritto non si butta: prima il test che fallisce sul comportamento sbagliato, poi la correzione);
   i difetti si cercano dalla causa (`systematic-debugging`). Un piano procede un compito alla volta, con una revisione dopo
   ogni compito (`subagent-driven-development`); piani su parti diverse del codice possono andare insieme.
5. **Revisione del ramo** e verifica (`requesting-code-review`, `verification-before-completion`) **prima** di aprire la pull request:
   la pull request del proprietario si unisce da sola appena i controlli sono verdi.
6. **Pull request** su `main` con `Closes #N` e le prove fatte; mai unione in locale o a mano: la fa il job `unisci`. Ramo indietro: si unisce `main` nel ramo (niente push forzato).
7. **Rilascio automatico**: il job `rilascia` dà il numero di versione e crea la release; il server installa `main` da solo.
8. **Verifica sul dispositivo**: versione nuova sul server, nuova build dell'app.
9. **Controlli su `main`** (`docs/decisioni/0008`): dopo l'unione il job `prova-main` lancia di nuovo i controlli sul nuovo `main`
   (iOS compreso se `ios/` è cambiata). Se uno è rosso si apre l'issue `P1` «CI: main rosso» con il link alla corsa: si vede nel
   giro del coordinatore (`gh issue list --label P1`) e si corregge con una pull request. L'issue la chiude chi ha corretto.

## Chi rivede cosa
- **Chi scrive** non rivede il proprio lavoro: apre la pull request in bozza con le prove fatte; la revisione la fa chi coordina (agente revisore e `/code-review`), poi la pull request esce dalla bozza.
- **Revisione IA in CI** (job `revisione-ia`, `docs/decisioni/0007-revisione-ia-in-ci.md`): ogni pull request non in bozza
  del repository, non dei bot. Claude Code con la skill `.claude/skills/revisione-pr/SKILL.md` presa da `main`: correttezza,
  sicurezza, errori silenziosi, test, web e iPhone uguali, documenti, aspetto. Solo problemi certi, commenti sulle righe e una
  sintesi in italiano. Un problema «bloccante» ferma l'unione automatica: si corregge il ramo (un falso allarme si sistema nella skill, su `main`).
  Senza il segreto `CLAUDE_CODE_OAUTH_TOKEN` il job passa senza revisione. Per rifare la revisione dopo un falso allarme corretto su `main`: «Re-run failed jobs» nella corsa dei controlli.
- **Il proprietario** guarda le pull request che cambiano la configurazione dei dispositivi e della rete (in bozza fino al suo ok), le decisioni di prodotto
  e i falsi allarmi della revisione IA. Le regole della revisione si cambiano solo con una pull request su `main`.
- **Foto iOS** (dopo l'unione): il fotografo, come scritto sotto.

## Quando un lavoro è finito
- **Server**: test verdi; `python -m fanta verifica` prima e dopo se cambia il calcolo; voce in `fanta/novita.d/`;
  `docs/API.md` o `docs/GUIDA-UTENTE.md` aggiornati.
- **Web**: come il server, più la prova nel browser a 390, 768, 1024 e 1440 px, tema chiaro e scuro, con dati verosimili e
  le schermate guardate davvero.
- **iPhone**: prima dell'unione compilazione e test verdi in CI (`ios / test`) e revisione fatta; nella pull request le schermate
  da fotografare e l'elenco di cosa provare sul telefono. Dopo l'unione le foto delle schermate toccate, guardate davvero.
- **Ogni schermata**: stessi testi, numeri e stati su web e iPhone (`docs/COERENZA-WEB-IPHONE.md`), oppure un'issue «coerenza: …»;
  niente segni da interfaccia generata (`docs/STILE-SENZA-AI.md`).

## Contratto delle API
- `docs/openapi.json` è l'istantanea di tutte le rotte del server (parametri, corpi, risposte). `tests/test_contratto_api.py`
  la confronta con l'API vera: se una pull request cambia l'API senza aggiornarla, il test fallisce e dice cosa è cambiato.
- Cambio voluto: `python script/ci/aggiorna_openapi.py` e il file aggiornato nella stessa pull request. Così rotte e campi nuovi
  o tolti si vedono nel diff.
- **Un cambio dell'istantanea richiede di controllare iPhone e web**: chi rivede la pull request guarda il diff di
  `docs/openapi.json` e verifica che la web app e l'app per iPhone (e il widget) reggano il cambio. Aggiungere campi si può;
  togliere o cambiare un campo che un client legge rompe le app già installate: prima si adeguano i client, oppure si apre
  un'issue «coerenza: …» per il lato che resta indietro.

## App per iPhone
- Al massimo tre pull request iOS aperte insieme, su schermate diverse; i file comuni li cambia una pull request alla volta.
- Le foto (`screenshot.yml`) usano un Mac di GitHub alla volta e le lancia una sola persona. Si fanno su `main` DOPO l'unione
  (la pull request si unisce da sola appena i controlli sono verdi): ogni 60-90 minuti una corsa con le schermate delle pull
  request iOS unite nel frattempo. Ogni difetto visto diventa un'issue `P1` con la foto.
- Le pull request che cambiano molto l'aspetto possono chiedere una corsa di foto sul loro ramo prima di uscire dalla bozza,
  una alla volta. Le altre non restano in bozza ad aspettare le foto.

## Cosa non fare
- Codice senza test, correzioni senza causa, «dovrebbe andare».
- Pull request enormi o aperte prima della revisione.
- Una schermata cambiata su un lato solo.
- Controlli che scattano solo dopo l'unione: ciò che può rompere `main` si controlla già nella pull request (la corsa su `main` dopo l'unione, punto 9, è una rete di sicurezza, non il controllo).
- Dati veri, indirizzi o chiavi nel repository, anche nei piani e nelle foto.
