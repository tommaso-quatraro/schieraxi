# SchieraXI

**Schierali. Schiera gli XI.**

![SchieraXI: la schermata Oggi](sito/img/schermata-larga.png)

> **In English:** SchieraXI is free software (AGPL-3.0) for fantasy football (*fantacalcio*) in a classic Serie A league.
> Every matchday it estimates each player's expected fantasy score (the *fantavoto atteso*), picks the 11 starters,
> the formation and the bench order, and helps with trades. It is a guide, not a guarantee. It has a web app (PWA) and an
> iPhone app; you run the server yourself. Data sources are **off by default**: read their terms before turning them on.
> Screens and docs are in Italian. Website: <https://schieraxi.it>.

## Cosa fa, in 3 righe
1. Ogni giornata ti dice quali 11 schierare, con quale modulo e in che ordine mettere la panchina.
2. Per ogni giocatore calcola il **fantavoto atteso**: il punteggio che ci si può aspettare con le regole della tua lega.
3. Ti aiuta con gli scambi, ti avvisa se cambia qualcosa (infortuni, probabili formazioni) e controlla da sola quanto ha azzeccato.

È una guida, non una garanzia: sono stime. Non fa l'asta e non schiera la squadra al posto tuo.

## Avviso
SchieraXI è un progetto indipendente. **Non è affiliata, approvata o sponsorizzata da Fantacalcio.it, da Leghe Fantacalcio
né dalla Lega Serie A.** I nomi citati appartengono ai rispettivi proprietari e servono solo a dire con cosa funziona.
Il progetto non include né ridistribuisce dati di terzi: le rose di prova sono inventate.

## Come provarla
Hai tre strade. La più semplice è la prima.

### 1. App web, sul tuo computer
Servono Python 3.11 e Git. I comandi sono per Windows, dalla cartella del progetto. Su macOS e Linux usa `.venv/bin/python` al posto di `.venv\Scripts\python.exe`.

1. Scarica il codice: `git clone https://github.com/tommaso-quatraro/schieraxi.git`, poi `cd schieraxi`.
2. Crea l'ambiente: `python -m venv .venv`.
3. Installa le librerie: `.venv\Scripts\python.exe -m pip install -r requirements.txt`.
4. Avvia il server: `.venv\Scripts\python.exe -m fanta server`.
5. Apri nel browser `http://127.0.0.1:8000`. Dal browser puoi anche installarla come app (PWA).

Il server ascolta solo sul tuo computer. Per usarla dal telefono serve un collegamento sicuro (per esempio una VPN privata): non aprire la porta su internet senza protezione.

### 2. App per iPhone, con SideStore
L'app nativa (cartella `ios/`) non è nell'App Store: si installa con SideStore, senza account Apple a pagamento.
Serve un server SchieraXI a cui collegarla (strada 1 o 3). Guida passo per passo: `docs/INSTALLAZIONE-IPHONE.md`.

### 3. Un server tutto tuo (Linux)
Per averla sempre accesa, per esempio su un piccolo computer di casa o su un server in affitto.

1. Scarica il codice in una cartella dell'utente, per esempio `/home/<utente>/fantacalcio`, e prepara l'ambiente come sopra
   (`python3 -m venv .venv` e `.venv/bin/python -m pip install -r requirements.txt`).
2. Copia `script/server/fantacalcio.service` in `/etc/systemd/system/`, sostituisci `<utente>` e controlla i percorsi.
3. Attiva il servizio: `sudo systemctl daemon-reload`, poi `sudo systemctl enable --now fantacalcio`.
4. Controlla che risponda: `curl -i http://127.0.0.1:8000/api/stato`. Va bene `200`, e anche `401` (vuol dire che gli account sono attivi e manca l'accesso).
5. Per aprirla fuori casa metti davanti un proxy con HTTPS (per esempio nginx). Quella configurazione non è nel repository.

Gli script di manutenzione (aggiornamenti, copie di sicurezza, controlli) sono spiegati in `script/server/LEGGIMI.md`.
Le variabili di configurazione (per esempio `FANTA_LEGA`) si mettono nel servizio con `Environment=NOME=valore`. Le chiavi, se servono, vanno in `.env` o in `dati/`, mai in git.

## La tua lega
Nel repository c'è una lega **inventata** in `lega/esempio/` (10 squadre finte): serve a provare l'app.
Per la tua, crea una cartella fuori dal progetto con `regole.json` e `rose.json` e avvia il server con `FANTA_LEGA=/percorso/della/cartella`.
Le regole non sono scritte nel codice: bonus, malus, moduli e panchina stanno in quel file. Non copiare dati veri di una lega dentro il repository.

## Fonti dati: spente di default
SchieraXI legge dati pubblici da siti di terzi (calendario, voti, probabili formazioni, statistiche dei tiri).
- Ogni fonte ha un interruttore e **è spenta di default**. Si accende con `FANTA_FONTE_<NOME>=1` (per esempio `FANTA_FONTE_UNDERSTAT=1`) o dalle impostazioni dell'amministratore.
- Prima di accenderla leggi e rispetta le condizioni d'uso del sito: chi la accende se ne assume la responsabilità.
- Le richieste sono poche, una alla volta, con pausa e cache locale. L'agente di rete si presenta come `SchieraXI/<versione>`.

## Limiti
- Sono stime. Il voto vero può cadere lontano dalla previsione, per questo la formazione mostra una fascia.
- Rispetto a chi sceglie solo con la media dei voti il modello va un po' meglio, ma di poco e su campioni piccoli. Numeri e formule: `docs/SOTTO-IL-COFANO.md`.
- Dipende dalle fonti: se un sito cambia, i dati mancano finché non si sistema il lettore. Gli abbinamenti dei nomi tra fonti possono sbagliare.
- Pensata per una lega classic di Serie A. L'app Android è in pausa.

## Struttura delle cartelle
- `fanta/`: il server Python (FastAPI) e la logica: modello, formazione, scambi, account.
- `fanta/web/`: la web app (HTML, CSS e JavaScript senza librerie).
- `ios/`: l'app per iPhone (SwiftUI).
- `lega/esempio/`: la lega inventata.
- `tests/`: i test automatici (`.venv\Scripts\python.exe -m pytest -q`).
- `docs/`: guide. Per chi usa l'app: `GUIDA-UTENTE.md`. Per chi sviluppa: `API.md`, `SOTTO-IL-COFANO.md`, `DESIGN.md`.
- `script/`: script di controllo e di manutenzione del server.
- `sito/`: il sito <https://schieraxi.it>.
- `assets/marchio/`: logo e icone (vedi `TRADEMARKS.md`).

## Contribuire
Le proposte sono benvenute: leggi `CONTRIBUTING.md` (apri prima una issue, fai passi piccoli, niente dati personali).
Per una falla di sicurezza non aprire una issue pubblica: leggi `SECURITY.md`. Si applica `CODE_OF_CONDUCT.md`.
Le versioni pubblicate e le loro note sono nella pagina **Releases**.

## Licenza
Il codice è sotto **AGPL-3.0** (file `LICENSE`): puoi usarlo, studiarlo e modificarlo. Se offri una versione modificata a qualcuno
via rete, devi mettere a disposizione anche il codice modificato. Il nome SchieraXI e il logo sono marchi di Tommaso Quatraro e
non rientrano nella licenza: vedi `TRADEMARKS.md`. Librerie di terzi: `THIRD-PARTY-NOTICES.md`.

Titolare: Tommaso Quatraro. Contatti: contatti@schieraxi.it.
