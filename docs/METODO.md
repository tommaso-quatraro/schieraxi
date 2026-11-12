# Metodo di lavoro

Per chi coordina il lavoro su SchieraXI (una persona, o la sessione principale di Claude Code con i suoi agenti).
Le regole che valgono per tutti stanno in `CLAUDE.md`; quelle di ogni area in `.claude/rules/`. Qui c'è il resto: cosa si fa
prima, chi rivede, come si passa il lavoro, come si misura.

## Obiettivi e priorità
- Gli obiettivi sono quattro issue con l'etichetta `obiettivo` (statistiche nostre affidabili, consiglio giusto e spiegato,
  app semplice e uguale su web e iPhone, app aperta agli altri). I lavori concreti sono loro sotto-issue.
- Si lavora sulle `P1` e sulle sotto-issue dell'obiettivo in corso. Un'idea nuova diventa un'issue `P3` e aspetta.
- Lo stato si legge, non si ricopia: `python script/squadra/squadra.py stato` (pull request, corse, issue per obiettivo,
  worktree, tetti delle pull request aperte per area).

## Quanto processo serve
| Lavoro | Cosa serve |
|---|---|
| Correzione piccola, testi | Solo la pull request |
| Un difetto visto dall'utente, o un lavoro che chiede una decisione | Issue con «cosa», «perché», «fatto quando» |
| Tre o più pull request, o più aree insieme (server, web, iPhone) | Spec e piano in `docs/superpowers/specs/` e `plans/`, uniti con una pull request di soli documenti prima del codice |

Nei piani e nei documenti si scrive «chiuderà #N»: «Closes #N» chiude l'issue all'unione.

## Lavoro in parallelo
- Un agente per area di file, ognuno nella sua worktree; mai due sugli stessi file. Il brief dice quali file può toccare e
  quali no (`python script/squadra/squadra.py brief <issue>`).
- I colli di bottiglia sono tre: `fanta/web/app.js` (un file solo: i lavori sulla web vanno in fila), i Mac di GitHub (5 job)
  e il PC (test con `-n 3`, un browser alla volta). Si lanciano agenti su lavori veri, non per riempire.
- Prima si chiude, poi si apre: una pull request ferma costa più di una non iniziata.

## Chi rivede cosa
- **Una revisione indipendente** per ogni pull request, fatta da chi non l'ha scritta (agente `revisore`), sul ramo, prima
  di togliere la bozza. Si registra nella sezione «## Revisione» della descrizione, una riga «- <chi>: <esito>».
- **Revisione di sicurezza** (`/security-review`) quando il diff tocca accessi, token, file caricati, rotte che scrivono o
  segreti.
- **Revisione IA in CI** (job `revisione-ia`, `docs/decisioni/0007`): parte fuori dalla bozza e blocca l'unione se trova un
  problema certo. Un falso allarme si corregge nella skill `.claude/skills/revisione-pr`, su `main`.
- **Il proprietario** decide funzioni nuove o tolte, spese, testi legali, account, e tutto ciò che tocca dispositivi e rete.
- La bozza si toglie con `python script/squadra/squadra.py pr-pronta <PR> --esegui`.

## Passaggio di consegne
Chi riprende un lavoro parte da ciò che è scritto, non dalla memoria della chat.
- **Lavoro fermo a metà**: un commento sull'issue che inizia con `## Consegne`, con quattro voci brevi: **Fatto** (ramo,
  commit o pull request), **Resta**, **Trappole** (ciò che il codice non dice), **Prossimo passo** (il primo comando o file).
- **Lavoro finito**: la descrizione della pull request fa da consegna. Una trappola che vale per tutti va nella scheda
  dell'area (`.claude/rules/`), in una riga e senza racconto; meglio ancora, diventa un controllo.
- Vale solo il commento del proprietario del repository: su un'issue pubblica chiunque può scrivere.

## Dopo l'unione
- **Server**: la versione nuova compare in produzione di solito entro 10 minuti (l'installazione si rimanda durante le
  partite e nell'ora prima di una scadenza); l'ambiente di prova
  (`script/server/prova/LEGGIMI.md`, `docs/decisioni/0012`) la riceve prima e il workflow «Collaudo della prova» la collauda
  da solo. Se non passa apre un'issue `P1`.
- **iPhone**: release `build-<N>`; le foto delle schermate toccate si scattano su `main`
  (`python script/squadra/squadra.py foto --da <commit> --lancia`, al massimo due corse insieme) e si guardano davvero.
- **Controlli su `main`** (`docs/decisioni/0008`): se uno è rosso nasce l'issue `P1` «CI: main rosso».

## Contratto delle API
- `docs/openapi.json` è l'istantanea di tutte le rotte; `tests/test_contratto_api.py` la confronta con l'API vera. Cambio
  voluto: `python script/ci/aggiorna_openapi.py`, con il file nella stessa pull request.
- Chi rivede un cambio dell'istantanea controlla che web, iPhone e widget lo reggano: aggiungere campi si può, togliere o
  cambiare un campo letto da un client rompe le app già installate.
- Contratto iPhone-server senza Mac: `tests/test_contratto_ios.py` (`docs/decisioni/0014`).

## Le misure
- **Precisione del fantavoto atteso e del consiglio**: `python -m fanta verifica` (anche `--consiglio`, `--pacchetti`) e il
  registro delle giornate, che salva i numeri mostrati prima di ogni giornata e li confronta con i voti veri.
- **Giornata senza errori** (`docs/decisioni/0013`): `python script/squadra/squadra.py giornata …`, guida in
  `script/squadra/LEGGIMI.md`.
- **Ingresso di un amico** in meno di 10 minuti: percorso automatico `prove/amico_nuovo/percorso.py` (trova gli ostacoli) e
  `python -m fanta ingresso --dal <data>` sul server (misura gli amici veri, senza nomi).

## Sicurezza
I problemi di sicurezza trovati restano in privato finché la correzione è pronta: il rapporto sta solo sul PC del
proprietario; la pull request e la sua issue hanno titoli neutri che descrivono il cambiamento, senza i dettagli del problema.
