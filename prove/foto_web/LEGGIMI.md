# Foto e axe della web senza finestra

`foto.py` fotografa le schermate principali della web app e le controlla con axe (accessibilità), senza aprire nessuna
finestra: usa Chrome già installato sul computer, senza finestra, con un profilo temporaneo (nessun cookie di chi lo lancia).
Serve per le foto «prima» e «dopo» di ogni modifica della grafica.

## Una volta sola: il venv con Playwright
Playwright non sta nei requisiti del progetto: si mette in un venv a parte, fuori dal repository (per esempio nella cartella
temporanea della sessione). Nessun browser da scaricare: si usa Chrome di sistema.

```
py -3.13 -m venv <cartella-temporanea>\pw-foto
<cartella-temporanea>\pw-foto\Scripts\python.exe -m pip install playwright==1.64.1
```

## Il comando
Dalla radice del repository (anche da una worktree):

```
<cartella-temporanea>\pw-foto\Scripts\python.exe prove\foto_web\foto.py <cartella-delle-foto>
```

Senza indirizzo lo strumento avvia da solo un server di prova e lo ferma alla fine, anche se qualcosa va storto:
- copia `fanta/` della cartella da cui lo lanci (così fotografi il codice del tuo ramo) in una cartella temporanea;
- usa la lega d'esempio (`lega/esempio/`) e una copia dell'archivio dei dati di calcio `dati/fanta.sqlite` (dal repository o,
  da una worktree, dalla cartella principale; `--dati <cartella>` per sceglierne un altro). L'originale non si tocca;
  diario, scelte e account non si copiano. Senza archivio le schermate restano vuote;
- calcola nella copia il diario delle giornate finite della lega d'esempio (`python -m fanta affidabilita`, pochi secondi,
  nessuna rete), così la scena `diario` non è vuota;
- spegne i lavori di sfondo e le fonti (nessuna richiesta a siti esterni) e ascolta su un indirizzo di loopback suo
  (`127.0.0.NN`, mai `127.0.0.1`) con una porta libera;
- il Python del server è il `.venv` del repository o della cartella principale (`--python-server` per sceglierne un altro);
  il suo registro finisce in `server.log` nella cartella delle foto.

Con un server già acceso: `foto.py http://127.0.0.NN:80NN <cartella-delle-foto>`.

Opzioni: `--scene formazione,scheda` (di norma tutte), `--larghezze 390,768,1024,1440`, `--temi chiaro,scuro`, `--lingua it|en`,
`--accesso`, `--solo-misure` (sotto).
Scene: `formazione` (dal 12/11/2026 è anche la prima schermata: la scena «oggi» non c'è più), `squadra`, `rosa`, `scheda`
(scheda del primo titolare), `altro`, `diario` (dal 12/11/2026 la pagina Giornate), `regole`, `impostazioni`. Dal 12/11/2026
(#618) la barra ha tre voci: `rosa` è Impostazioni > La mia squadra, `regole` è Impostazioni > Regole e scadenza, e `squadra`
e `altro` aprono gli indirizzi di prima, che portano a Impostazioni (i nomi restano: li usa il collaudo dell'ambiente di prova).
Tutte le scene, a 4 larghezze e 2 temi, sono 64 foto: circa 10 minuti.

## Cosa scrive
Per ogni scena, larghezza e tema:
- `<scena>-<larghezza>-<tema>.png`: la pagina intera. Le barre ferme (la barra in basso) compaiono dove stavano nella prima
  schermata, non in fondo: è il modo in cui Chrome fotografa la pagina intera. Con un foglio aperto (`scheda`)
  il foglio scorre da sé: si fotografa a pezzi della grandezza dello schermo, con 80 px ripetuti tra un pezzo e
  l'altro (`<nome>.png`, `<nome>-2.png`, …, al massimo 8);
- `axe-<scena>-<larghezza>-<tema>.json`: le violazioni di axe (`tests/strumenti/axe/axe.min.js`, regole WCAG 2.0, 2.1 e 2.2,
  livelli A e AA), con fino a 5 elementi per regola;
- `console-<scena>-<larghezza>-<tema>.txt`, solo se la pagina ha scritto errori nella console;
- una riga in `riepilogo.txt`:

```
<scena> <larghezza> <tema> gravi=<n> scorrimento-di-lato=<sì|no> errori-console=<n> [regole=<id>,<id>]
```

`gravi` = regole violate di gravità `critical` o `serious` (l'obiettivo della nuova grafica è zero ovunque); se ce ne sono,
`regole=` dice quali (per esempio `regole=color-contrast`) e il file `axe-…json` della stessa foto dice su quali elementi;
`scorrimento-di-lato=sì` = la pagina è più larga dello schermo. Una scena che non si apre scrive `errore=…` al posto dei numeri.
Esce con 0 se è tutto a posto, 1 se ci sono violazioni gravi, 2 se una scena non si è aperta.

Gli errori della console comprendono le risposte 4xx e 5xx del server: Chrome le scrive nella console («Failed to load
resource: the server responded with a status of 500»). Prima di axe e dello scorrimento di lato le animazioni si portano alla
fine: le schermate entrano sfumando, e a metà animazione axe misurerebbe contrasti più bassi del vero.

## Server con gli account: `--accesso` e `--solo-misure`
Con gli account accesi (`FANTA_MULTIUTENTE=1`, come sull'ambiente di prova) le schermate si vedono solo dopo l'accesso.
`--accesso` entra prima delle scene con l'API di accesso; il cookie della sessione resta nel profilo temporaneo del browser.
Utente e password arrivano **solo** dalle variabili d'ambiente `SCHIERAXI_UTENTE` e `SCHIERAXI_PASSWORD`: non c'è un'opzione
sulla riga di comando e lo strumento non li stampa mai. Se mancano si ferma subito; se l'accesso è rifiutato esce dicendo solo
il codice della risposta.

`--solo-misure` non scrive nessun PNG: solo `riepilogo.txt`, i risultati di axe e gli errori della console. Lo usa il collaudo
automatico dell'ambiente di prova (`.github/workflows/collaudo-prova.yml`, con `script/ci/collaudo_prova.py`), che apre le
schermate principali a 390 e 1440 px e apre un'issue se qualcosa non va. Per una violazione grave l'issue e l'allegato
`esito.txt` dicono la regola di axe e fino a due elementi, senza i valori degli attributi (#697): per esempio
`scheda 390 chiaro: 1 violazione grave di accessibilità (color-contrast su #foglio-contenuto > .pulsanti > button[data-sostituisci])`.

Esempio contro un server locale con gli account accesi (account inventato, mai credenziali vere in un file):

```
set SCHIERAXI_UTENTE=collaudo
set /p SCHIERAXI_PASSWORD=Password: 
<cartella-temporanea>\pw-foto\Scripts\python.exe prove\foto_web\foto.py http://127.0.0.NN:80NN <cartella> --accesso --solo-misure --larghezze 390,1440
```

## Perché le foto non vanno nel repository
Il repository è pubblico e le schermate mostrano nomi di calciatori veri: le foto restano fuori. Lo strumento si rifiuta di
scrivere in una cartella dentro il repository (da una worktree, anche dentro la cartella principale, dove le foto non
sono escluse dai commit). Nelle pull request vanno solo le misure e l'esito di axe.
