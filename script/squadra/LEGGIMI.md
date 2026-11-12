# Comandi della squadra

I passi che il coordinatore ripeteva a mano, come comandi con parametri e test (`tests/test_squadra_*.py`).
Entrata unica, dalla radice del repository:

```
python script/squadra/squadra.py <comando> [opzioni]
python script/squadra/squadra.py <comando> --help      # opzioni e codici di uscita
```

Regole comuni:
- Un comando che cambia qualcosa (annulla corse, toglie worktree, toglie la bozza, rilancia controlli) di default fa solo la
  **prova** e stampa cosa farebbe. Agisce solo con `--esegui` (per `foto`: `--lancia`).
- Nessun comando unisce una PR né scrive su `main`.
- `gh` e `git` passano da una sola funzione (`comune.esegui_vero`); i test le danno risposte finte e non toccano GitHub.
- Ogni comando ha `--json` per gli altri script. I codici di uscita stanno nel `--help` di ogni comando; argomenti sbagliati
  escono sempre con 64 (mai con un codice che un comando usa per altro).
- Niente dati privati: l'indirizzo del server arriva solo dalla variabile d'ambiente `SCHIERAXI_URL`, se c'è.
- Lo stato fra due giri sta in `.superpowers/squadra/` (fuori da git: la cartella ha un suo `.gitignore`).
- Serve `gh` autenticato. Python della sola libreria standard.

## Dati
- `aree.json`: aree del repository (percorsi, primo che corrisponde vince), gruppi con il tetto delle PR aperte
  (`server-web` 4, `ios` 3), aree neutre (documenti e test: non contano nel tetto), workflow con job sui Mac,
  etichetta degli obiettivi. Una PR che tocca `ios/` e un'altra area conta nel gruppo `ios`.
- `foto.json`: dai file iOS alle schermate di `ios/scripts/screenshot.sh`. Un test controlla che i nomi esistano e che ogni
  file Swift di oggi abbia una regola. Le regole larghe hanno `"ripiego": true`: un file di `ios/Sources/Presentation/` ci
  finisce solo se è scritto in `ripiego_dichiarato` (parti usate da più schermate); per gli altri una regola per file o per
  cartella stretta (anche questo lo controlla un test).
- `modello-brief.md`: modello pubblico del brief per un agente.

## stato
Una tabella: PR aperte (numero, titolo, bozza, unibile, controlli, gruppo, età), tetti per gruppo, corse dei workflow con job
sui Mac in corso o in coda (i test iOS dentro «Controlli» non si vedono qui), issue aperte per obiettivo (sotto-issue delle issue
con l'etichetta `obiettivo`), worktree degli agenti. Sola lettura.

```
python script/squadra/squadra.py stato
```

## attendi
Aspetta una PR guardando solo l'ultima corsa di ogni workflow sul commit in testa; stampa una riga solo quando cambia qualcosa.
Esce con 0 unita, 2 conflitto, 3 rosso vero, 4 guasto d'infrastruttura (da rilanciare), 5 tempo scaduto, 6 verde ma in bozza,
1 errore o PR chiusa. Va lanciato in background, una sola attesa per volta.

```
python script/squadra/squadra.py attendi 123 --intervallo 60 --massimo 3600
```

## annulla-superate
Annulla le corse in coda o in corso partite da `push` o `pull_request` su un commit che non è più la testa del suo ramo.
Mai `workflow_dispatch` né `schedule`, mai il ramo `main`. Limite: per le PR da un fork il ramo si riconosce solo dal nome.

```
python script/squadra/squadra.py annulla-superate            # prova
python script/squadra/squadra.py annulla-superate --esegui   # annulla davvero
```

## pulisci
Le worktree di `.claude/worktrees/` in gruppi: da togliere (ramo unito e niente modifiche), con modifiche, senza PR, sessioni
dell'app, con PR aperta, bloccate da un agente, cartelle sparite (cancellate a mano: si tolgono dall'elenco con
`git worktree prune`). Con `--esegui` toglie solo il primo gruppo: `git worktree remove` senza `--force`, poi il ramo
locale. «Unito» vuole sempre una PR `MERGED`: con la stessa testa; oppure con la testa locale già dentro `origin/main`
(dell'ultimo `git fetch`); oppure portata in pari con main da GitHub («Update branch»): la testa locale è un antenato di
quella della PR (`compare/<testa PR>...<testa locale>` con `status` uguale a `behind` o `identical`; un errore vale «non unito»).

Una worktree con la testa già in `origin/main` ma senza PR unita (ramo senza commit propri, o staccata su un commit di main)
non è «unita»: è anche lo stato di una sessione appena aperta e ancora al lavoro. Sta in «Senza PR» con la nota «nessun
commit proprio» e si toglie a mano dopo aver chiesto.

Le sessioni aperte dall'app lavorano in `.claude/worktrees/<nome>` sul ramo `claude/<nome>` e possono restare aperte anche
dopo l'unione della loro PR. Una worktree con il ramo `claude/…` unito e senza modifiche non va in «da togliere» ma in
«Sessioni dell'app»: `pulisci` non la toglie mai, `giro` la mostra, e si toglie a mano quando la sessione è chiusa. Limite:
una sessione passata a un altro ramo non si riconosce più; se la PR di quel ramo è unita e non ci sono modifiche finisce
in «da togliere». Per proteggerla: `git worktree lock <cartella>`.

Poi i rami locali senza worktree (mai `main`, mai il ramo corrente): da togliere (PR unita e lavoro su main, come sopra), da
chiedere (senza PR, PR chiusa, commit non uniti: non si toccano mai), con PR aperta. Con `--esegui` toglie solo i primi.

```
python script/squadra/squadra.py pulisci
```

## brief
Stampa il brief di un agente per un'issue: titolo, «Fatto quando», agente e «Puoi toccare / NON toccare» dalle etichette di
area dell'issue (`aree.json`). Esce con 3 se restano parti `<da scrivere…>`.

```
python script/squadra/squadra.py brief 123 --modello sonnet --tocca "fanta/web/app.js, tests/test_x.py"
```

## foto
Dai file iOS di una PR (o di `main` dopo un commit, con `--da`) ricava le schermate da fotografare e stampa il comando di
`screenshot.yml`. Un file iOS senza schermata in `foto.json` dà un avviso (uscita 3). Le foto le lancia solo il fotografo,
su `main`, con `--lancia`.

```
python script/squadra/squadra.py foto 123
python script/squadra/squadra.py foto --da abc1234 --lancia
```

## giro
La procedura del coordinatore in un comando: `stato`, PR in conflitto, guasti d'infrastruttura, corse superate, worktree da
pulire (sempre solo prova) e versione in produzione se c'è `SCHIERAXI_URL` (letta dal file pubblico `/sw.js`). Stampa solo
ciò che è cambiato dal giro prima (`+` nuovo, `~` cambiato, `-` finito); `--tutto` stampa anche il resto. Con `--esegui`
rilancia una volta sola i guasti, e solo le corse al primo tentativo (`gh run rerun <id> --failed`) e annulla le corse superate. Esce con 10 se c'è qualcosa da
guardare.

```
python script/squadra/squadra.py giro
```

## pr-pronta
Toglie la bozza solo se tutto torna: PR aperta, `mergeable` esattamente `MERGEABLE`, ramo non indietro (`compare/main...<testa>`, `behind_by` uguale a 0), controlli verdi sul
commit in testa, descrizione, revisione e novità (`script/ci/controlla_pr.py`), coerenza web-iPhone (`script/coerenza.py
--controlla` sui file della PR, se li tocca), «Foto da fare» se la PR tocca `ios/`. Altrimenti stampa ogni motivo ed esce con 1.
Se `controlla_pr.py` o `coerenza.py` non ci sono su questo `main`, rifiuta («controllo non disponibile su questo main").

Caso a parte: è rosso solo il job «ambito» ma la descrizione attuale va bene (`controlla_pr.py` senza problemi, aree di
`controlla_ambito.py` che coprono i file). Il job ha letto la descrizione di prima e un «Re-run» la rilegge uguale: il comando
lo dice e suggerisce update-branch (ramo indietro) o un push. Con `--esegui`, se l'unico altro motivo è il ramo indietro, fa
l'update-branch su GitHub ed esce con 4: controlli ripartiti, riprova fra qualche minuto.

```
python script/squadra/squadra.py pr-pronta 123            # prova
python script/squadra/squadra.py pr-pronta 123 --esegui   # gh pr ready
```

## giornata
Dice se una giornata è passata senza errori: è la misura che chiude #167 (decisione `docs/decisioni/0013`, `docs/METODO.md`,
«Le misure»). Sola lettura. La finestra va dalla scadenza della lega a due giorni dopo l'inizio dell'ultima partita;
`--dal` e `--al` sono date ISO con il fuso (`2026-11-15T13:50:00+01:00` o `…Z`) e il comando si lancia a finestra finita.

Raccoglie con `gh` le corse di `test.yml` su `main` e di `collaudo-prova.yml`, le issue nuove della finestra e quelle con i titoli
«CI: main rosso», «Collaudo della prova: v<N> non passa» e «La prova non si aggiorna». Rosso se: la sentinella ha un allarme o non gira per più di
2 ore; nasce un'issue `P1` o `dall-utente`; una di quelle tre issue è aperta in qualche momento della finestra; una corsa è rossa
(«annullato» non conta); nessun collaudo riuscito davvero nella finestra (job «Collaudo delle schermate»); manca il file della
sentinella. Ogni motivo stampato dice cosa, quando e il link.

Il file della sentinella si prende dal server, in sola lettura, a finestra finita: `python -m fanta sentinella --giri --dal <ISO con
fuso> --al <ISO con fuso>` stampa i giri in JSON; si salva in un file sul PC e si passa con `--sentinella`. Va bene anche il file di
stato intero della sentinella (`dati/sentinella.json`, campo `giri`). Senza `--sentinella` la giornata non è mai verde.

Uscite: 0 senza errori; 1 non ok (stampa i motivi); 2 date rifiutate (senza fuso, rovesciate o `--al` nel futuro); 3 errore di `gh`
o file della sentinella illeggibile. Eccezione alla regola comune del 64: le date sbagliate escono con 2, perché le controlla il
comando dopo la lettura degli argomenti; con 64 escono solo gli argomenti che mancano o non si leggono (per esempio senza `--dal`).

```
python script/squadra/squadra.py giornata --dal 2026-11-15T13:50:00+01:00 --al 2026-11-19T20:45:00+01:00 --sentinella giri.json
```
