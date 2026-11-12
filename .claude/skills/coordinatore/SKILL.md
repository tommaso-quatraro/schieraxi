---
name: coordinatore
description: Come la sessione principale coordina il lavoro su SchieraXI con più agenti - leggere lo stato, dividere il lavoro per aree di file, lanciare gli agenti con un brief, far rivedere e unire le pull request, foto dell'iPhone, controllo della produzione, pulizia e stato di fine sessione. Usala all'inizio di una sessione di coordinamento e ogni volta che un agente finisce.
---
# Coordinare il lavoro

Chi coordina decide, divide, controlla e informa il proprietario dopo. Le regole sono in `CLAUDE.md` e `docs/METODO.md`;
qui c'è solo la procedura. I comandi stanno in `script/squadra/` (`python script/squadra/squadra.py <comando> --help`):
senza `--esegui` mostrano solo cosa farebbero.

## 1. Leggere lo stato (inizio sessione, e quando un agente finisce)
- `python script/squadra/squadra.py giro`: stampa solo ciò che è cambiato (pull request, conflitti, guasti dei controlli,
  corse superate, worktree da togliere, versione in produzione). `stato` stampa tutto.
- `gh issue list --label P1`: prima le cose rotte.
- La memoria della sessione (`stato.md` nella cartella di memoria del progetto): cosa aspetta il proprietario, quali agenti
  sono al lavoro, le prossime mosse.

## 2. Dividere e lanciare
- Un agente per area di file, mai due sugli stessi file. La web sta quasi tutta in `fanta/web/app.js`: i lavori sulla web
  vanno in fila. I Mac di GitHub sono 5 job: al massimo tre pull request dell'iPhone aperte.
- Brief: `python script/squadra/squadra.py brief <issue>` e si completano le parti tra `< >` («già deciso», file da non
  toccare). Il brief non ripete le regole: dice il compito, i file, cosa è già deciso e il «fatto quando».
- Agenti: `sviluppatore-web` (server, web, controlli), `sviluppatore-ios`, `collaudatore`, `revisore`. Un lavoro di
  giudizio (modello, schermate rifatte, revisione) merita il modello più forte; uno meccanico no.
- Lavoro da tre pull request in su: prima spec e piano in una pull request di soli documenti.

## 3. Portare una pull request all'unione
1. L'agente consegna la pull request in bozza. Si lancia `revisore` sul ramo (non ha visto come è nato il codice); se il
   diff tocca accessi, token, file caricati o rotte che scrivono, anche `/security-review`.
2. I rilievi bloccanti tornano all'agente che ha scritto il codice (o a uno nuovo, con il rilievo nel brief).
3. Si scrive l'esito nella sezione «## Revisione» della descrizione, una riga «- revisore: <esito>».
4. `python script/squadra/squadra.py pr-pronta <PR> --esegui`, poi `attendi <PR>` in background. Conflitto: `git merge
   origin/main` nel ramo. Controllo fallito in pochi secondi senza passi: `gh run rerun <id> --failed`, una volta.
5. Dopo l'unione: la versione arriva sul server (lo dice `giro`); la worktree si toglie con `pulisci --esegui` solo dopo
   aver visto la pull request unita.

## 4. Foto dell'iPhone
Dopo l'unione di pull request che cambiano le viste: `python script/squadra/squadra.py foto --da <ultimo commit
fotografato> --lancia` (una corsa su `main`, al massimo due insieme), poi si scaricano e si guardano. Ogni difetto visto è
un'issue con il nome della foto.

## 5. Cosa si chiede al proprietario
Funzioni nuove o tolte, spese, testi legali, account e password, cancellazioni definitive, gesti fisici, modifiche a
dispositivi e rete. Il resto si decide e si riferisce: «Scelta mia: … perché …». Le domande si fanno tutte insieme, con
una proposta pronta.

## 6. Fine sessione
- Niente lasciato a metà senza traccia: un lavoro fermo ha il commento «Consegne» sull'issue (`docs/METODO.md`).
- `stato.md` si riscrive intero, mai aggiunte in fondo, al massimo 30 righe: obiettivo in corso; in attesa del
  proprietario; agenti al lavoro (issue e ramo); prossime tre mosse; promemoria con data. Ciò che è su GitHub non si ricopia.
- Una lezione imparata diventa un controllo o una riga nella scheda dell'area giusta, oppure si scarta: non si elenca.
- Al proprietario: cosa è arrivato sul telefono, cosa provare, e le decisioni che spettano a lui.
