# Percorso automatico «amico nuovo»

`percorso.py` fa nel browser, senza finestra, l'ingresso di un amico invitato, come lo farebbe lui dal telefono: apre il link
d'invito, si registra, salva il codice di recupero, carica le rose della sua lega, sceglie la sua squadra, imposta i tempi e le
regole della lega, salva la prima formazione, rientra con il codice di recupero ed elimina l'account. Per ogni passo dice quanti
secondi e quanti tocchi sono serviti, se la pagina ha scritto errori e se axe trova problemi gravi di accessibilità.

Serve a trovare gli ostacoli prima di aprire agli amici (obiettivo #168) e a provare che una correzione li toglie: è il «fatto
quando» delle sotto-issue degli ostacoli.

## Una volta sola: il venv con Playwright
Playwright non sta nei requisiti del progetto: si mette in un venv a parte, fuori dal repository (per esempio nella cartella
temporanea della sessione), con le versioni e gli hash fissati. Nessun browser da scaricare: si usa Chrome già installato.

```
py -3.13 -m venv <cartella-temporanea>\pw-amico
<cartella-temporanea>\pw-amico\Scripts\python.exe -m pip install --require-hashes --only-binary=:all: -r .github\playwright-requisiti.txt
```

Il file Excel delle rose si crea con `openpyxl`, che sta nel `.venv` del repository (o della cartella principale): lo script lo
usa da solo, in un sottoprocesso.

## Sul computer: `--locale`
Dalla radice del repository (anche da una worktree):

```
<cartella-temporanea>\pw-amico\Scripts\python.exe prove\amico_nuovo\percorso.py <cartella-dei-risultati> --locale --telefono iphone --larghezza 390 --formato excel
```

Lo script avvia da solo un server di prova e lo ferma alla fine, anche se qualcosa va storto (come `prove/foto_web/foto.py`):
copia di `fanta/` di questa cartella, lega d'esempio, copia dell'archivio dei dati di calcio (`dati/fanta.sqlite`, mai l'originale),
account accesi (`FANTA_MULTIUTENTE=1`), un invito monouso creato nella copia con `python -m fanta invito --etichetta amico-nuovo`.
Il server ascolta su un indirizzo di loopback suo (`127.0.0.NN`) e il browser lo apre come `localhost`: è lì (come su https) che
l'app registra il service worker, che serve per l'installazione sulla Home.

Solo in locale ci sono due passi in più: `file_sbagliato` (un calendario scelto al posto delle rose, subito prima delle rose) e
`invito_usato` (un secondo browser, senza sessione, riapre lo stesso link d'invito).

Le tre corse di riferimento: `--telefono iphone --larghezza 390 --formato excel`, `--telefono android --larghezza 360 --formato testo`,
`--telefono iphone --larghezza 390 --formato rosters`.

## Sull'ambiente di prova: `--remoto`
Indirizzo e invito arrivano **solo** dalle variabili d'ambiente, mai dalla riga di comando:

```
set /p SCHIERAXI_INDIRIZZO=Indirizzo: 
set /p SCHIERAXI_INVITO=Invito: 
<cartella-temporanea>\pw-amico\Scripts\python.exe prove\amico_nuovo\percorso.py <cartella-dei-risultati> --remoto --telefono android --larghezza 360 --formato testo
```

Se ne manca una lo script si ferma subito (uscita 2) dicendo quali servono, mai i valori. Freno contro la produzione: con
`--remoto` il nome del server deve cominciare con `prova.`, altrimenti lo script si ferma (uscita 2) senza toccare niente; non c'è
un'opzione per scavalcarlo. L'invito si consuma: per ogni corsa ne serve uno nuovo.

L'account creato (`amico-<6 cifre>`) si elimina sempre alla fine. Se l'eliminazione dall'app non riesce, o la corsa si ferma a
metà (anche subito dopo il tocco su «Crea l'account»), lo script la rifà con l'API provando ogni password usata nel giro (prima e
dopo il rientro). Se la cancellazione non risponde 200 scrive «ATTENZIONE» con il nome dell'account da controllare ed eliminare a
mano (mai la password).

## Opzioni
- `--telefono iphone|android`: emulazione di Chrome come `iPhone 13` o `Pixel 7` (tocco, schermo del telefono), profilo temporaneo.
- `--larghezza 360|390`: larghezza dello schermo in px.
- `--formato testo|rosters|excel`: come arrivano le rose, costruite al momento da `lega/esempio/rose.json` nella cartella dei
  risultati. `testo`: colonne `ruolo;nome;club;prezzo` incollate nel riquadro; `rosters`: il CSV di Leghe, una riga
  «squadra,codice,costo» per giocatore e «$,$,$» tra una squadra e l'altra; `excel`: per ogni squadra il nome, l'intestazione e
  una riga per giocatore.
- `--a-secco`: prepara i file delle rose e stampa i passi, senza browser né server.

## I passi e cosa vuol dire «ok»
| Passo | Ok quando |
|---|---|
| `invito` | il link apre la registrazione con il codice già scritto, e il codice non resta nell'indirizzo |
| `registrazione` | nome `amico-<6 cifre>`, password a caso, casella di Privacy e Termini: compare il codice di recupero |
| `recupero_salvato` | «Copia il codice», «Ho salvato il codice», «Entra nell'app»: si apre il primo avvio |
| `installabile` | manifesto con nome, icone 192 e 512, schermo intero e `start_url`; `apple-touch-icon` e meta di Apple; aperta di nuovo (come dall'icona della Home) la pagina è controllata dal service worker e Chrome non ha motivi per non installarla (`Page.getInstallabilityErrors` vuoto) |
| `file_sbagliato` | solo `--locale`: il calendario dà il messaggio «nessuna rosa» e con «Torna indietro» si può riprovare o saltare |
| `rose` | l'anteprima mostra tutte e 10 le squadre d'esempio |
| `squadra` | «Qual è la tua squadra?» → `Real Esempio`, i dubbi restano sulla prima proposta, «Conferma e salva» |
| `tempi` | scadenza 10 minuti, prima giornata quella proposta, «Salva», poi «Tutto pronto» e «Vai a Oggi» |
| `regole` | Altro > Regole, incolla il testo `ESEMPIO` di `tests/test_regole_testo.py`, «Riconosci», «Applica ai campi», «Salva le regole» |
| `formazione` | Formazione > «Salva questa»: 11 titolari e un modulo salvati |
| `rientro` | Impostazioni > Il tuo account > Esci, «Password dimenticata» con il codice di recupero e una password nuova, poi dentro |
| `invito_usato` | solo `--locale`: lo stesso invito una seconda volta dà una frase che nomina l'invito |
| `elimina` | Impostazioni > Il tuo account > Elimina l'account: dopo, l'accesso con quelle credenziali è rifiutato. Si fa sempre |

Un passo si prova solo se sono riusciti quelli da cui dipende (le rose prima della squadra, la squadra prima dei tempi e della
formazione...): gli altri risultano `bloccato` con «non provato» in `dettagli.txt`.

## Cosa scrive
Nella cartella dei risultati, che deve stare **fuori dal repository** (le schermate mostrano nomi di calciatori veri; lo script
si rifiuta di scrivere dentro il repository o, da una worktree, dentro la cartella principale):
- `riepilogo.txt`, una riga per passo:

```
<passo> secondi=<s> tocchi=<n> errori-console=<n> gravi=<n> esito=<ok|bloccato|errore:<tipo>>
```

- `dettagli.txt`: il motivo di ogni passo non ok, i messaggi visti (file sbagliato, invito usato), il riassunto dell'anteprima;
- `<nn>-<passo>.png`: la schermata alla fine di ogni passo, con i campi del codice d'invito e del codice di recupero coperti;
- `axe-<nn>-<passo>.json`: le violazioni di axe (regole WCAG 2.0, 2.1 e 2.2, livelli A e AA) sulla schermata di fine passo;
- i file delle rose (`rose.txt`, `rosters.csv` o `rose.xlsx`) e, in locale, `calendario.csv` e `server.log`.

`tocchi`: uno per pulsante o campo toccato, due per una tendina (aprirla e scegliere), uno per l'«OK» di una conferma.
`errori-console`: errori scritti dalla pagina più le risposte 4xx e 5xx del server, tranne quelle che il passo si aspetta (la
pagina d'accesso riceve 401 prima di entrare, l'invito già usato 403, il file sbagliato 400). `gravi`: violazioni di axe
`critical` o `serious`. Esce con 0 se ogni passo è `ok` con 0 errori e 0 gravi, 1 altrimenti, 2 con argomenti sbagliati.

## Cosa non si salva mai
Indirizzo del server (con `--remoto`), codice d'invito, password e codici di recupero: non si stampano e non si scrivono in nessun
file. Restano solo in memoria durante la corsa; ogni testo scritto (dettagli, axe, registro del server) passa prima da un filtro
che li sostituisce con «nascosto», e nelle foto i campi che li mostrano sono coperti. Le password sono a caso
(`secrets.token_urlsafe(18)`), mai credenziali vere.
