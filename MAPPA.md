# MAPPA: dove sta ogni cosa

Una riga per cartella o file importante. I dettagli di ogni modulo, i contratti delle API, il modo con più utenti e i punti
delicati stanno in `docs/RIFERIMENTO.md`: si cercano lì con una ricerca (per nome di file o di campo), non si leggono per intero.
Regole: `CLAUDE.md` e `.claude/rules/`. Comandi: `CLAUDE.md`.

## Radice
- `fanta/`: server e logica (pacchetto Python; «fanta» è il nome interno storico).
- `fanta/web/`: la web app. `fanta/testi/`: catalogo dei testi. `fanta/novita.d/`: voci di novità in attesa di rilascio.
- `ios/`: app per iPhone e iPad (SwiftUI) e widget.
- `sito/`: sito di presentazione, statico.
- `lega/esempio/`: lega inventata per prove e test. La lega vera sta fuori dal repository (`FANTA_LEGA=<cartella>`).
- `tests/`: test Python, un file per modulo; dati inventati in `tests/dati/`.
- `script/`: `server/` (cron e aggiornamento del server), `ci/` (controlli e rilascio), `squadra/` (comandi di chi coordina),
  `controlli/` (controllo prima del commit), `testi.py`, `coerenza.py`, `blocca_dipendenze.py`.
- `prove/`: strumenti di misura e di collaudo che non girano in produzione.
- `docs/`: guide e contratti. `.github/workflows/`: controlli, rilascio, foto. `.claude/`: regole, skill e divieti per Claude Code.
- `dati/`: database, cache e chiavi locali. Mai in git.

## `fanta/`: il server
| Parte | File |
|---|---|
| Rotte | `server.py` (tutte le `/api/...`), `rotte_account.py`, `versioni.py` (ETag), `calcolo.py` (coda dei calcoli), `contesto.py` (cartelle per utente), `limiti.py` |
| Fantavoto atteso | `modello.py` (fantavoto atteso e probabilità di giocare), `incertezza.py`, `nostri.py` (gol e assist attesi calcolati in casa), `taratura_probabili.py` |
| Formazione | `formazione.py` (11 titolari e panchina), `consigli.py` (consigliata stabile e spiegazioni), `perche_scelta.py`, `scelte.py` (formazione salvata), `copia_scadenza.py` |
| Giornata | `turno.py`, `fasi.py` (prima, in corso, finita), `rinvii.py`, `punteggio.py` (fantavoto con le regole della lega), `diario.py`, `da_fare.py` |
| Lega | `regole.py`, `regole_testo.py`, `rose.py` (Excel, CSV, testo), `lega.py`, `squadre.py`, `movimenti.py`, `nomi.py` (riconoscimento dei nomi), `listone.py`, `stagione.py` |
| Fonti e archivio | `fonti/` (un lettore per fonte), `aggiorna.py` (riempie `dati/fanta.sqlite`), `archivio.py`, `rete.py`, `fonti_attive.py`, `controlli.py`, `stato_dati.py` |
| Avvisi | `notifiche.py`, `push.py`, `avvisi.py`, `avvisi_utenti.py`, `pianificatore.py`, `frasi.py` e `frasi_avvisi.py` (frasi con chiave) |
| Account | `account.py` (sessioni, inviti, migrazioni), `account_email.py`, `posta.py`, `social.py` (Google), `onboarding.py`, `testi_legali.py` |
| Misura e sorveglianza | `verifica*.py` (misure sul passato), `registro_giornate.py`, `registro_nostri.py`, `indicatori_consiglio.py`, `affidabilita.py`, `sentinella.py`, `salute.py`, `misura_ingresso.py` |
| Altro | `widget.py`, `live.py` (risultati in diretta), `scambi.py`, `scambi_multi.py`, `asta.py`, `coppe.py`, `osservati.py`, `immagini.py`, `avatar.py`, `backup.py`, `funzioni.py` (interruttori delle funzioni), `gestione.py`, `percorsi.py` |

## `fanta/web/`: la web app
`index.html` (testata e contenitore), `app.js` (schermate e navigazione), `impostazioni.js`, `dafare.js`, `primoavvio.js`,
`avatar.js`, `anteprima.js`, `legale.js`, `testi.js` (generato dal catalogo, più le funzioni `t`, `tp`), `stile.css`,
`sw.js` (service worker), `caratteri/`, icone.

## `ios/`
`project.yml` (progetto), `Sources/` (app), `WidgetSources/` (widget), `Tests/`, `testi/` (chiavi del catalogo usate),
`fotografie/` (risposte registrate per foto e test), `scripts/`, `docs/` (`WIDGET.md`, linee guida), `README.md`.

## `script/` e `prove/`
- `script/server/`: `aggiorna.sh` (dati, 4 volte al giorno), `aggiorna-app.sh` (installa le release firmate), `backup-dati.sh`,
  `controllo-salute.sh`, `sentinella.sh`, `promemoria.sh`, `pubblica-sito.sh`, `verifica-firme.sh`, `prova/` (ambiente di
  prova). Guida: `script/server/LEGGIMI.md`.
- `script/ci/`: `controlla_pr.py`, `controlla_ambito.py`, `controlla_versione.py`, `assegna_versione.py`, `note_rilascio.py`,
  `aggiorna_openapi.py`, `aspetto_web.py` (confronto delle foto della web con `main`), `collaudo_prova.py`, `metriche.py`.
- `script/squadra/`: `squadra.py <comando>` (`stato`, `brief`, `pr-pronta`, `attendi`, `foto`, `giro`, `pulisci`,
  `annulla-superate`, `giornata`), `aree.json`, `foto.json`, `modello-brief.md`, `LEGGIMI.md`.
- `prove/`: `foto_web/foto.py` (foto e accessibilità della web), `web_comportamento/` (test della web in un browser vero),
  `amico_nuovo/percorso.py` (ingresso di un utente nuovo), `fotografie_dal_vero.py` (scenari per le foto dell'iPhone),
  misure e tarature del modello.

## `docs/`
- Per chi usa l'app: `GUIDA-UTENTE.md`, `INSTALLAZIONE-IPHONE.md`.
- Per chi sviluppa: `RIFERIMENTO.md` (dettagli e contratti), `API.md`, `openapi.json`, `METODO.md`, `DESIGN.md`,
  `STILE-SENZA-AI.md`, `ARCHITETTURA-INFORMAZIONI.md`, `COERENZA-WEB-IPHONE.md` (generato da `coerenza/`),
  `SOTTO-IL-COFANO.md` (come si calcola), `INCERTEZZA.md`, `AVATAR.md`, `RIPRISTINO-SERVER.md`, `CI-IOS-COSTI.md`.
- `decisioni/`: le scelte durevoli e il loro perché, una per file. `superpowers/specs/` e `plans/`: spec e piani.

## `.github/workflows/`
`test.yml` (controlli, `ambito`, `versione`, `ios`, `unisci`, `rilascia`, `prova-main`), `revisione.yml` (revisione IA),
`ios.yml`, `ipa.yml` (build per SideStore), `screenshot.yml` (foto dell'iPhone), `ios-simulatore.yml`, `aspetto-web.yml`,
`collaudo-prova.yml`, `salute.yml`.
