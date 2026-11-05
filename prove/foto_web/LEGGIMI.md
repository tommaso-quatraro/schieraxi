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
- spegne i lavori di sfondo e le fonti (nessuna richiesta a siti esterni) e ascolta su un indirizzo di loopback suo
  (`127.0.0.NN`, mai `127.0.0.1`) con una porta libera;
- il Python del server è il `.venv` del repository o della cartella principale (`--python-server` per sceglierne un altro);
  il suo registro finisce in `server.log` nella cartella delle foto.

Con un server già acceso: `foto.py http://127.0.0.NN:80NN <cartella-delle-foto>`.

Opzioni: `--scene oggi,formazione` (di norma tutte), `--larghezze 390,768,1024,1440`, `--temi chiaro,scuro`, `--lingua it|en`.
Scene: `oggi`, `formazione`, `squadra`, `elenco` (Squadra > Elenco dei giocatori), `rosa`, `scheda` (scheda del primo
titolare), `confronto` (i primi due titolari), `altro`, `diario`, `regole`, `scambi`, `impostazioni`. Tutte le scene, a 4
larghezze e 2 temi, sono 96 foto: circa 10 minuti.

## Cosa scrive
Per ogni scena, larghezza e tema:
- `<scena>-<larghezza>-<tema>.png`: la pagina intera. Le barre ferme (la barra in basso) compaiono dove stavano nella prima
  schermata, non in fondo: è il modo in cui Chrome fotografa la pagina intera. Con un foglio aperto (`scheda`, `confronto`,
  `diario`) il foglio scorre da sé: si fotografa a pezzi della grandezza dello schermo, con 80 px ripetuti tra un pezzo e
  l'altro (`<nome>.png`, `<nome>-2.png`, …, al massimo 8);
- `axe-<scena>-<larghezza>-<tema>.json`: le violazioni di axe (`tests/strumenti/axe/axe.min.js`, regole WCAG 2.0, 2.1 e 2.2,
  livelli A e AA), con fino a 5 elementi per regola;
- `console-<scena>-<larghezza>-<tema>.txt`, solo se la pagina ha scritto errori nella console;
- una riga in `riepilogo.txt`:

```
<scena> <larghezza> <tema> gravi=<n> scorrimento-di-lato=<sì|no> errori-console=<n>
```

`gravi` = regole violate di gravità `critical` o `serious` (l'obiettivo della nuova grafica è zero ovunque);
`scorrimento-di-lato=sì` = la pagina è più larga dello schermo. Una scena che non si apre scrive `errore=…` al posto dei numeri.
Esce con 0 se è tutto a posto, 1 se ci sono violazioni gravi, 2 se una scena non si è aperta.

## Perché le foto non vanno nel repository
Il repository è pubblico e le schermate mostrano nomi di calciatori veri: le foto restano fuori. Lo strumento si rifiuta di
scrivere in una cartella dentro il repository. Nelle pull request vanno solo le misure e l'esito di axe.
