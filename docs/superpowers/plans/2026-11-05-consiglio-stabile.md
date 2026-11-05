# Consiglio stabile (L2, #335): piano

> **Per chi esegue:** un compito alla volta, test prima del codice (`superpowers:test-driven-development`).

**Obiettivo:** la consigliata già mostrata per una giornata cambia solo se la nuova vale almeno 1 punto atteso in più
(ricalcolata con i dati nuovi), oppure se un suo titolare è uscito dalla rosa, fuori o improbabile.

**Architettura:** il calcolo della migliore (`consigli._calcola_formazione`, in cache) non cambia. Sopra c'è un passo nuovo,
`consigli.stabile`, che confronta la migliore con la consigliata di prima e decide quale tenere. `consigli.formazione` legge la
consigliata di prima, chiama `stabile` (in cache con la consigliata di prima nella chiave) e ricorda la scelta. Tutti i
chiamanti (Formazione, Oggi, widget, Da fare, avvisi, copia alla scadenza, sentinella, riscaldamento) passano già da
`consigli.formazione`: leggono la stessa consigliata senza cambiare una riga.

**Spec:** `docs/superpowers/specs/2026-11-05-consiglio-giusto-proposta.md` (§2 C2, §3 L2, §4 D2).

## Vincoli
- Soglia: `notifiche.SOGLIA_AVVISO_PUNTI` (1 punto atteso), la stessa dell'avviso alla scadenza, riusata con un nome in `consigli`.
- Titolare che non gioca più: fuori dalla rosa o senza previsione, oppure DIVENTATO «fuori» o «improbabile» (`titolarita`, sotto
  il 20%) → si passa alla migliore, se la migliore non lo tiene anche lei. Chi era già fuori o improbabile quando la consigliata
  è stata mostrata (il sistema lo teneva con una riserva sicura dietro) si ricorda in `non_giocano` e non fa cambiare da solo:
  senza questo, prima della #329, la consigliata cambiava ancora in metà dei ritocchi.
- Dopo la scadenza nulla cambia: la consigliata di prima resta (titolari e panchina), il file non si riscrive.
- La scelta salvata dall'utente non si tocca (`consigli` non scrive in `scelte`).
- File toccati: `fanta/consigli.py`, `tests/`, `prove/`, `MAPPA.md`, `docs/API.md`, `fanta/novita.d/consiglio-stabile.json`.
  Non `formazione.py`, `da_fare.py`, `verifica*.py`, `__main__.py`, `fanta/web/`, `ios/`.

## Scelta mia: dove sta «la consigliata di prima»
La proposta dice «l'istantanea del Diario». `consigli.formazione` però non sa di quale utente è la richiesta (riceve solo
archivio, regole e rose) e la chiamano 12 punti in 9 file, alcuni in processi a parte (avvisi del cron, sentinella). Leggere
l'istantanea vorrebbe dire passare il file del diario a tutti, anche a `da_fare.py` (vietato qui, #333/#334): Da fare
leggerebbe una consigliata diversa da Oggi, proprio il difetto di #333. In più l'istantanea si scrive solo aprendo la
Formazione o 10 minuti prima della scadenza: chi guarda solo Oggi o il widget vedrebbe la consigliata ballare fino ad allora.
Quindi: un file comune piccolo, `dati/consigliate.json`, con chiave = impronta (sha256) di stagione, giornata, nome della
squadra, rosa, regole e simulazioni; valore = id di titolari e panchina, modulo, ora. Niente nomi né id utente: è come la
cache dei calcoli (già condivisa fra utenti con la stessa rosa e le stesse regole), ma sopravvive ai riavvii e vale fra
processi. Tetto di voci, si toglie la più vecchia. L'istantanea del Diario resta com'è: si scrive da `f`, quindi coincide.
Costo se sbagliata: il file si toglie e la lettura passa all'istantanea in una PR che tocca anche i chiamanti.

## Compito 1: `stabile` (funzione pura)
**File:** `fanta/consigli.py`, test `tests/test_consigliata_stabile.py`.
- `stabile(migliore: dict, prima: dict | None, prev: pd.DataFrame, s: Squadra, regole: Regole, simulazioni: int,
  chiusa: bool = False) -> dict`. `prima` = `{"titolari": [id], "panchina": [id], ...}`.
- Tenuta la consigliata di prima: titolari di prima, panchina rifatta dal sistema (`fz._panchina`) prima della scadenza, quella
  di prima dopo; punti attesi, fascia, `moduli` (la voce del suo modulo), `livelli` (stile 0), `alternative`, `fuori` rifatti.
- Test (visti rossi, poi verdi): ritocco sotto 1 punto → resta; almeno 1 punto → la migliore; titolare infortunato,
  improbabile o uscito dalla rosa → la migliore anche sotto 1 punto; nessuna consigliata di prima → la migliore; dopo la
  scadenza resta anche per molti punti; la voce di `moduli` e `livelli[0]` mostrano i titolari tenuti.

## Compito 2: `formazione` ricorda e legge
**File:** `fanta/consigli.py`, `tests/conftest.py` (file nella cartella temporanea), stesso file di test.
- `FILE_CONSIGLIATE`, `leggi_consigliata(impronta, file=None) -> dict | None`, `_ricorda(...)` con `BloccoFile` e
  `scrivi_sicuro`, tetto `MAX_CONSIGLIATE`.
- Test: due calcoli con un ritocco in mezzo → stessi titolari; dopo un riavvio (cache svuotata) → stessi; dopo la scadenza
  il file non cambia; il file non contiene nomi di squadre o giocatori; file rovinato → la migliore, senza errori.

## Compito 3: misura, documenti, novità
- `prove/misura_stabilita.py`: sulla lega d'esempio e l'archivio locale, ritocchi come la proposta (gioca ±3 punti,
  fantavoto ±0,1, 3 prove per squadra): titolari cambiati prima (la migliore) e dopo (`stabile`).
- `MAPPA.md`, `docs/API.md` («la consigliata resta quella già mostrata…»), `fanta/novita.d/consiglio-stabile.json`.
- `python -m fanta verifica` prima e dopo (non deve cambiare: `verifica` non passa da `consigli.formazione`), suite intera.

## Da guardare in revisione
- Due utenti con la stessa squadra, rosa e regole condividono la consigliata ricordata: è quella che vedrebbero comunque.
- Rosa cambiata a metà settimana: impronta nuova, si riparte dalla migliore.
- Anticipo già cominciato (L5): fuori da qui.
