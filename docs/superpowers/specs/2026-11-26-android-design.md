# App Android nativa di SchieraXI: spec

Data: 26/11/2026. Stato: proposta (da unire con una PR di soli documenti prima del codice, `docs/METODO.md`).
Piano di esecuzione: `docs/superpowers/plans/2026-11-26-android.md`.

## Decisioni per il proprietario, in parole semplici
Per ognuna c'è una proposta: basta un «sì» oppure la scelta diversa. I dettagli tecnici sono al §13.
- **D1 Con che cosa si scrive**: con gli strumenti ufficiali di Google (Kotlin), come l'iPhone usa quelli di Apple. Proposta: sì.
- **D2 Telefoni vecchi**: l'app va da Android 8 (2017) in su. Proposta: sì, dopo aver chiesto agli amici che versione hanno.
- **D3 Avvisi**: due promemoria prima della scadenza, come sull'iPhone; niente avviso «è cambiata la consigliata». Proposta: sì.
- **D4 Aggiornamenti**: l'app dice «C'è una versione nuova» e la scarica col tasto; esce al massimo un APK al giorno, o quando
  lo chiedi tu. L'app Obtainium per chi vuole l'aggiornamento da solo: proposta sì, facoltativa.
- **D5 Piccole differenze inevitabili** (§3.8: niente widget sulla schermata di blocco, niente Siri, niente suggerimenti a
  fumetto). Proposta: sì.
- **D6 Nome del documento della coerenza**: resta quello di oggi. Proposta: sì.
- **D7 Prove gratuite su telefoni veri in rete** (Firebase Test Lab). Proposta: più avanti, solo se serve.
- **D8 Ritorno da Google ancora più sicuro** (un file in più sul server). Proposta: più avanti.
- **D9 Iscrizione come sviluppatore Google**, se diventerà obbligatoria anche per gli APK. Proposta: decidere quando sarà chiaro.
- **D10 Gestione del server solo su web e iPhone**: serve solo a chi gestisce il server. Proposta: sì, circa 6 PR in meno.
- **D11 Tablet e tastiera**: su Android il tablet mostra la pagina del telefono, senza scorciatoie. Proposta: sì, circa 3 PR in meno.

## 0. In breve
- App **Kotlin + Jetpack Compose**, nativa, cartella `android/`, pacchetto `it.schieraxi.app`, Android 8.0 (API 26) o più nuovo.
- **Stesse funzioni dell'iPhone, sempre**: la web resta il riferimento, iPhone e Android la seguono. La parità la controllano le
  macchine: un registro delle funzioni a tre colonne con un test che fallisce quando la colonna Android non torna, il catalogo
  dei testi generato anche in Kotlin, esempi condivisi che i test di tutte e due le app devono superare, gli stessi nomi delle
  schermate di prova, una riga obbligatoria nella pull request.
- Distribuzione come **APK firmato** nelle release `android-<N>` del repository (mai «Latest», che resta all'iPhone), al
  massimo uno al giorno o a richiesta, con l'avviso della versione nuova dentro l'app. Tutto su GitHub Actions, con runner
  Ubuntu gratuiti: niente Mac, niente spese.
- Avvisi come l'iPhone (promemoria locali con i testi del server), senza Firebase. Tre widget Glance come quelli dell'iPhone.
- **Circa 100 pull request o più** (stima fra 100 e 120; fra 90 e 110 se passano D10 e D11) in sei fasi: l'app dell'iPhone ha circa
  38.000 righe di Swift più 29.000 di test, con file grandi come `WidgetRiassunto.swift` (1764 righe). Al ritmo possibile
  con tre agenti su Android sono da 3 a 5 settimane di lavoro pieno (§11). La fase 1 dà un APK che un amico usa davvero
  (accesso, Formazione, Giornate, Impostazioni di base).

## 1. Perché e vincoli
Decisioni del proprietario del 26/11/2026:
- gli amici, una decina, hanno tutti Android: serve un'app Android nativa;
- distribuzione come APK, per ora senza Play Store;
- **tassativo: Android e iOS con le stesse funzioni, sempre in parallelo**; la web è il riferimento («i client mostrano, non
  ricalcolano»);
- la sezione feedback «Scrivici» (in lavorazione per server, web e iPhone) ci deve essere anche su Android;
- registrazione libera senza inviti (in lavorazione a parte): l'accesso Android segue il campo `registrazione` del 401 come
  l'iPhone; il modo `aperta` c'è già sul server (`fanta/account_email.py`) e in `ModalitaRegistrazione.swift`, quindi
  funziona senza lavoro in più; quello che il lavoro in corso aggiunge arriva con la sua riga del registro (§10, F64);
- sviluppo solo da un PC Windows e da GitHub Actions; niente spese.

Le regole di sempre (`CLAUDE.md`) valgono anche qui: niente dati veri nel repository, testi in italiano semplice, mai testo
tagliato con «…», numeri e frasi dal server.

## 2. Le decisioni, con il motivo
| Tema | Scelta | Motivo |
|---|---|---|
| Tecnologia | Kotlin 2 + Jetpack Compose (Material 3) | È l'equivalente di SwiftUI: dichiarativo, a stati, con le anteprime. Si porta una vista SwiftUI in una Composable quasi riga per riga e i nomi restano gli stessi. Scartati: Flutter e React Native (un terzo linguaggio e niente codice in comune con l'iPhone già scritto); Kotlin Multiplatform condiviso con iOS (vorrebbe riscrivere il dominio dell'iPhone, che funziona); la web dentro un'app (TWA: niente widget né promemoria nativi, quindi niente parità con l'iPhone). |
| Versione minima | `minSdk 26` (Android 8.0); `targetSdk` e `compileSdk` le più recenti stabili (36 oggi) | Dalla 26 ci sono `java.time` senza librerie, icone adattive e canali delle notifiche. Copre quasi tutti i telefoni in uso, e quelli degli amici di sicuro (da confermare: D2). |
| Identificativi | `applicationId` `it.schieraxi.app`, schema `schieraxi://`, nome del file `SchieraXI.apk`, tag `android-<N>` | Uguali all'iPhone dove c'è un equivalente. **Non si cambiano mai**: con un id o una firma diversa Android non aggiorna l'app e l'amico deve disinstallarla. |
| Moduli | due: `:dominio` (Kotlin puro, senza Android) e `:app` (Android: rete, interfaccia, widget, avvisi) | Come `Domain/` contro il resto sull'iPhone. I test del dominio girano sulla JVM in pochi secondi, e due moduli dividono bene il lavoro fra agenti. Il widget sta nell'app (su Android non serve un'estensione a parte). |
| Dipendenze | poche e fissate (elenco al §4), con le impronte in `verification-metadata.xml`, generato solo in CI | Come `--require-hashes` per Python. Una dipendenza nuova si propone in un'issue. Il file si genera su Linux in CI (§9.1) e mai sul PC: Windows scarica alcuni file diversi (per esempio `aapt2`), e le impronte non tornerebbero. |
| Rete | OkHttp + kotlinx.serialization, stesse rotte e intestazioni dell'iPhone (§5) | Una libreria HTTP sola, con `MockWebServer` per i test. Retrofit non serve per circa 70 rotte già scritte a mano sull'iPhone. |
| Salvataggio | `SharedPreferences` per le scelte; token della sessione cifrato con una chiave dell'Android Keystore; cache delle risposte e delle immagini su file | Equivale a `UserDefaults`, Keychain e `Caches/api` dell'iPhone. Niente Room e niente DataStore come dipendenze dirette. |
| Accesso | nome e password con `nativo: true`; Google con il giro del server aperto in una Custom Tab | Il giro con Google lo fa già il server (PKCE). Il client apre un indirizzo e riceve `schieraxi://social?codice=`. Niente SDK di Google. |
| Avvisi | promemoria locali (AlarmManager) con i testi del server, come l'iPhone; ntfy per chi gestisce il server; nessun Firebase | Stesse funzioni dell'iPhone. UnifiedPush darebbe ad Android un avviso che l'iPhone non ha: si decide a parte (D3). |
| Widget | Glance: Prossima giornata, Formazione consigliata, Da controllare | Gli stessi tre dell'iPhone. Su Android non ci sono i widget della schermata di blocco (differenza ammessa). |
| Aspetto | Material 3 con i colori di SchieraXI (`docs/DESIGN.md`, `Tema.swift`), tema Automatico, Chiaro o Scuro, niente colori dinamici di Android | Stessi colori e stesse parole; i componenti sono quelli del sistema, come sull'iPhone. |
| Testo grande | `sp` ovunque, testo che va a capo, prove con il testo al 200% | Come Dynamic Type; mai «…». |
| Distribuzione | APK firmato da GitHub Actions con una chiave salvata come segreto di un ambiente legato a `main` | Il proprietario fa un passaggio una volta sola (§9.5); nessuna password nel repository né nei log. |
| Aggiornamento | l'app legge `versione.json` dalla release fissa `android-ultima` e dice «C'è una versione nuova» con il pulsante per scaricare l'APK | Fa quello che fa `NuovaVersione.swift`, ma senza l'elenco delle release (§9.4). Volendo, Obtainium aggiorna da solo (D4). |

## 3. Parità garantita dalle macchine
Si regge su cinque controlli e su una regola scritta. Tutti girano su Linux in pochi secondi, tranne gli esempi condivisi
(§3.3), che girano anche nei test delle due app.

### 3.1 Registro delle funzioni a tre colonne
- File nuovo `docs/coerenza/funzioni.json`, letto da `script/coerenza.py`, che genera nel documento della coerenza la sezione
  «Funzioni nelle tre app»: l'elenco delle righe, **senza conti** (un numero che cambia a ogni PR farebbe litigare fra loro
  le PR aperte nello stesso momento). Il conto dell'avanzamento lo stampa `python script/coerenza.py --porting` nel
  terminale, senza scriverlo in nessun file.
- **Due numerazioni separate.** Le righe delle schermate (`docs/coerenza/schermate/*.json`) hanno già gli id da 1 a 106. Le
  funzioni hanno un id loro con la lettera F davanti (`"F12"`), così «riga 12» e «funzione F12» non si confondono mai.
- Forma di una riga:
  `{"id": "F12", "area": "Formazione", "funzione": "Riga dello stato della scelta", "web": "fatto", "ios": "fatto", "android": "da-fare",
  "fase_android": 1, "prova_ios": "StatoSceltaTests", "prova_android": "", "foto": ["formazione", "formazione-cambiata"],
  "issue": "", "motivo": ""}`.
  Stati possibili: `fatto`, `da-fare`, `non-serve`. In cima al file c'è
  `"porting": {"base": 64, "schermate_base": 106, "chiuso": false}`: `base` è il numero dell'ultima funzione
  dell'inventario iniziale (F64), `schermate_base` l'id più alto fra le righe delle schermate il giorno dell'unione di P0.3
  (106 oggi; lo scrive quella PR).
- **Quando si aggiorna.** Le righe passano a `fatto` (con `prova_android`) solo nelle PR di chiusura di una fase, non in
  ogni PR Android: così due PR che portano schermate diverse non toccano lo stesso file. Le righe nuove (dopo `base`) le
  scrive invece la PR che crea la funzione, già con la colonna Android a posto.
- `coerenza.py --controlla` (e quindi `tests/test_coerenza_dati.py`) **fallisce** se:
  1. una riga è `fatto` su iPhone e su Android non è `fatto` né `non-serve`, a meno che sia `da-fare` con un numero
     ≤ `porting.base`, `porting.chiuso` falso e `fase_android` indicata (è il debito del porting di oggi, che può solo
     scendere), oppure abbia `issue` («#N», un'issue «coerenza: …»);
  2. `non-serve` non ha un `motivo` uguale al titolo di una voce di `docs/coerenza/ammesse.json`;
  3. un lato è `fatto` ma il suo test non c'è: `prova_ios` deve essere un file `ios/Tests/**/<nome>.swift` e `prova_android`
     una classe in `android/**/src/test/**/<nome>.kt` (o in `androidTest`);
  4. un nome di schermata di prova dell'iPhone non compare nel campo `foto` di nessuna riga. L'elenco vero è `TUTTE` in
     `ios/scripts/screenshot.sh` (60 nomi oggi), non i `case` di `Demo.swift`: comprende i nomi `accesso-*` (aperti con
     `-DEMO_ACCESSO`), i `*-fondo` (la stessa schermata scorsa in fondo), `marchio`, `primo-avvio` e le varianti
     `lega-stato-*` (aperte con `-DEMO_FONDO`);
  5. una riga ha Android `fatto` ma uno dei nomi del suo campo `foto` non è in `TUTTE` di `Demo.kt` (l'elenco delle
     schermate di prova di Android, nella stessa forma) e non è segnato come solo iPhone in una voce di `ammesse.json`.
- Alla fine della fase 5 `porting.chiuso` diventa vero, il debito deve essere zero, e da lì ogni differenza vuole un'issue.
- Il file `docs/COERENZA-WEB-IPHONE.md` **non si rinomina** (decine di riferimenti in regole, test e script). Il titolo
  diventa «Web, iPhone e Android uguali» e la regola 5 della testa passa a «iPhone e Android, app e widget, seguono lo stesso
  vocabolario». Le righe delle schermate prendono il campo facoltativo `android`, obbligatorio solo per le righe con id
  oltre `porting.schermate_base`: le righe di oggi restano valide così come sono, e niente si rompe il giorno
  dell'unione.

### 3.2 Catalogo dei testi anche in Kotlin
- `script/testi.py --scrivi` genera in più `android/dominio/src/main/kotlin/it/schieraxi/catalogo/Catalogo.kt`: un file
  solo, con `object Catalogo { object Oggi { … } … }`, solo italiano, per le chiavi elencate in `ios/testi/*.txt` **più**
  quelle che stanno solo su Android in `android/testi/*.txt` (per esempio il permesso delle notifiche). Così ogni testo che
  l'iPhone mostra è disponibile su Android dal primo giorno, e una PR della web che cambia un testo dell'iPhone rigenera
  anche Android nella stessa PR.
- Nomi uguali a quelli di Swift: `Catalogo.Oggi.tuaFormazione` si scrive identico nei due linguaggi (stessa funzione
  `_nome_membro`). Con segnaposto: `fun giorniOre(giorni: String, ore: String): String = "…${giorni}…"`; plurali:
  `fun titolari(n: Int, …): String = if (n == 1) "…" else "…"`. Attenzione: `$` va scritto `\$`, e le parole riservate di
  Kotlin (`in`, `is`, `object`, `fun`, `val`, `when`, `typealias`, …) vanno tra apici inversi.
- `--controlla` e `tests/test_catalogo_testi.py` controllano anche il file Kotlin. Un test Python nuovo
  (`tests/test_testi_a_mano.py`) fallisce se nel Kotlin di `android/app/src/main` c'è una stringa uguale a un testo italiano
  del catalogo (dai 15 caratteri in su): il testo va preso da `Catalogo`. Lo stesso controllo si può allargare a Swift e
  spostare su Linux alcuni test che oggi girano sul Mac.
- `python script/coerenza.py --porting` stampa anche le chiavi usate in `ios/Sources` e non ancora in `android/` (letto dal
  sorgente), senza scriverle nel documento generato: serve a seguire l'avanzamento finché il porting è aperto. Quando si
  chiude (`porting.chiuso`), `--controlla` fallisce se ne resta qualcuna.

### 3.3 Esempi condivisi (stessi ingressi, stessi testi attesi)
- Cartella `tests/dati/casi/`, un JSON per funzione pura: `{"funzione": "NomeGiornata", "casi": [{"ingresso": {"serie_a": 11,
  "lega": 8, "forma": "intera"}, "atteso": "Giornata 8 · 11ª di Serie A"}]}`. Si comincia con `Formato` (virgola, segno meno
  tipografico, «–»), `Quando` (oggi, domani, «sab 31 20:45», giorno senza ora), `NomeGiornata`, `elidiOrdinali`,
  `SogliaGioca`, `Collegamenti` (indirizzo → destinazione); poi `StatoScelta`, `TestaFormazione`, `LetturaPedina`,
  `Decisioni`, le righe di Giornate e le estrazioni dei volti (`docs/AVATAR.md`).
- Le leggono un test Swift (`CasiCondivisiTests`, cartella elencata in `ios/Tests/file-esterni.txt`) e un test Kotlin
  (`CasiCondivisiTest`, cartella elencata in `android/file-esterni.txt`). Se un'app sbaglia, il test di quell'app è rosso.
  Gli attesi si scrivono dal vocabolario della coerenza, cioè dalla web.
- Facoltativo ma consigliato: il job `browser` esegue gli stessi casi sulle funzioni della web (`nomeGiornata`,
  `elidiOrdinali` e simili) nella pagina vera. Così il riferimento è provato anche lui.

### 3.4 Contratto con il server
- `tests/contratto_ios.py` si allarga (o nasce `tests/contratto_android.py` sulla stessa base) per leggere le classi
  `@Serializable` di `android/` (con `@SerialName` o il nome in stile snake_case): ogni campo letto da Android deve
  esistere come chiave in `fanta/`. Le eccezioni vanno in `tests/dati/contratto_android_eccezioni.json`, ognuna col motivo
  (decisione 0014).
- Un test Kotlin (`ContrattoDalVeroTest`) decodifica le risposte vere registrate (`ios/fotografie/vero-*.json`) e le
  fixture di `ios/Tests/Fixtures/*.json` con i modelli e il decodificatore dell'app. Fixture comuni ai due lati, senza
  copie.

### 3.5 Stesse schermate di prova
La demo Android usa **gli stessi nomi** dell'elenco `TUTTE` di `ios/scripts/screenshot.sh` (`formazione`,
`formazione-fondo`, `formazione-in-corso`, `giornate-aperta`, `lega-importa-csv`, `lega-stato-taratura`, `marchio`,
`primo-avvio`, `accesso-accedi`, …), con le stesse regole: `accesso-<scenario>` apre la demo con gli account accesi nello
scenario indicato (come `-DEMO_ACCESSO`), `<nome>-fondo` apre la schermata già scorsa in fondo (come `-DEMO_FONDO 1`),
`lega-stato-nostri`, `-taratura` e `-prova` si fermano sul loro riquadro. Il nome arriva come extra dell'intent
(`adb shell am start … -e DEMO_SCHERMATA formazione-fondo`) o dai test. `Demo.kt` tiene il suo elenco `TUTTE`, letto dal
controllo: il §3.1 (punti 4 e 5) lo confronta con l'elenco dell'iPhone e con il registro.

### 3.6 Controllo nella pull request
- Il job `ambito` (con `script/ci/controlla_ambito.py` o un `script/ci/controlla_parita.py` nuovo) legge i file cambiati:
  - i file generati del catalogo non contano mai come «toccato» né da una parte né dall'altra: `ios/Sources/Support/Catalogo/*`
    (come oggi in `NON_CONTANO`) e `android/dominio/src/main/kotlin/it/schieraxi/catalogo/Catalogo.kt`, che `testi.py
    --scrivi` rigenera insieme. Così una PR dell'iPhone che cambia un testo non risulta «fatta anche su Android» solo perché
    il catalogo Kotlin si è rigenerato, e viceversa. `Catalogo.kt` entra anche in `NON_CONTANO` per la dimensione della PR;
  - se la PR cambia `ios/Sources/**`, `ios/WidgetSources/**` o `ios/testi/**` e non tocca `android/` (a parte il catalogo),
    la descrizione deve avere la riga `Android:` con uno di questi valori: `in questa PR` (allora un file di `android/`
    diverso dal catalogo deve essere fra i cambiati), `da portare (id F<N>)` (la funzione è ancora nel debito del porting:
    il job controlla che in `funzioni.json` la riga F<N> sia `da-fare` con `fase_android`, e chi la porterà rilegge il
    codice dell'iPhone del giorno), `#N` (issue «coerenza: …» aperta: il job la verifica con `gh api`, in sola lettura),
    `non serve: <motivo>` (almeno tre parole: lo giudicano la revisione e la revisione IA);
  - simmetrico: se la PR cambia `android/app/src/main/**` o `android/dominio/src/main/**` (a parte il catalogo) e non
    `ios/`, serve la riga `iPhone:`. Durante il porting il valore tipico è `già fatto (id F12)`.
- Il modello di PR prende le due righe, più `Foto Android:` (§9.1). La skill `revisione-pr` controlla che quello che la riga
  dichiara sia vero.

### 3.7 Regola nuova: `.claude/rules/android.md` (testo proposto)
```
---
paths:
  - "android/**"
---
# App per Android (`android/`)

- **Parità.** Ogni funzione visibile dell'iPhone c'è anche qui, con gli stessi testi e numeri della web
  (`docs/coerenza/funzioni.json`). Una PR che cambia una schermata qui cambia anche l'iPhone, oppure lo dichiara nella riga
  `iPhone:` della descrizione.
- **Compilazione.** Il riferimento è la CI (`android.yml`, runner Ubuntu). Sul PC si può compilare (JDK 21 e command-line
  tools dell'SDK), sempre con `--no-daemon --max-workers=2`: con più agenti al lavoro il PC è un collo di bottiglia.
- **Identità.** `applicationId`, schema `schieraxi://`, nome dell'APK, prefisso dei tag e alias della firma non si cambiano:
  romperebbero l'aggiornamento sui telefoni degli amici. `build.gradle.kts`, `libs.versions.toml`,
  `verification-metadata.xml`, `AndroidManifest.xml`, `Navigazione.kt` e `ServerClient.kt` li cambia una PR alla volta.
- **Dipendenze.** Solo quelle della spec; una nuova si propone in un'issue (licenza compatibile con AGPL) e porta con sé
  `verification-metadata.xml` rigenerato dal job `impronte` di `android.yml` (mai sul PC: le impronte di Windows non tornano
  su Linux).
- **Dal server.** Numeri, stati, etichette e frasi si mostrano, non si ricalcolano. Testi fissi solo da `Catalogo`
  (`python script/testi.py --scrivi`); le chiavi che servono solo ad Android vanno in `android/testi/<prefisso>.txt`.
- **Codice.** Niente `!!`; modelli `@Serializable` con i campi a `null` per difetto; nessun `maxLines = 1` né
  `TextOverflow.Ellipsis` sul testo (lo controlla un test); TalkBack con una frase intera per riga; tema scuro; sul tablet
  l'impaginazione decisa con D11.
- **Foto.** Nella PR scrivi nella riga `Foto Android:` le schermate di prova che cambiano: la corsa di `android.yml` le
  fotografa e le pubblica nell'artifact `screenshot-android`, e si guardano davvero prima di togliere la bozza. Tutte le
  schermate in tutte le varianti si fotografano su `main` dopo l'unione.
- Nella PR scrivi cosa va provato su un telefono vero (ciò che emulatore e Robolectric non vedono).
```
Vanno aggiornati anche: `CLAUDE.md` (quattro parti; «iPhone e Android mostrano le stesse cose»; righe della tabella «Cosa
impone la macchina» per `android / test`, la parità nella PR e la firma), `.claude/rules/web.md` e `ios.md` («iPhone e
Android»), `.claude/rules/ci.md` (release `android-<N>` e `android-ultima` sempre con `--latest=false`; `apk.yml` non si
rinomina, perché il suo numero di corsa è il `versionCode`),
`MAPPA.md`, `script/squadra/aree.json` (area e gruppo `android`, tetto 3), la skill `coordinatore`.

### 3.8 Differenze ammesse proposte per Android (voci di `ammesse.json`)
1. **Widget sulla schermata di blocco**: su Android non ci sono (i telefoni non li hanno). Restano i widget della Home.
2. **«Collega il widget»**: non c'è, perché il widget fa parte dell'app e legge la sessione dell'app. Nella riga del widget
   in Impostazioni compare solo come aggiungerlo dalla Home.
3. **Gestione: certificato e SideStore**: solo iPhone, perché un APK non scade.
4. **Siri e Comandi**: su Android le scorciatoie del lanciatore (icona tenuta premuta: Formazione, Giornate, Cerca).
5. **Componenti**: Material 3 (barra di navigazione, fogli in basso) al posto di Liquid Glass; stessi colori e parole.
6. **Versione nuova**: su Android il pulsante scarica l'APK; sull'iPhone si aggiorna da SideStore.
7. **Crediti e fonti**: Android elenca le sue librerie di terzi (AndroidX, Kotlin, OkHttp, con le licenze); l'iPhone non ne ha.
8. **Permesso delle notifiche** (Android 13 e più nuovi): chiesto da «Avvisi su questo dispositivo», come il permesso di iOS.
9. **Conto alla rovescia del widget**: si aggiorna a ogni cambio del testo quando lo schermo è acceso, non con la timeline di
   iOS. L'ora della scadenza è sempre scritta.
10. **Suggerimenti di TipKit**: solo iPhone (se il proprietario non vuole un equivalente: D5).
11. **Gestione** (da decidere: D10): righe 46-48 del §10, cioè aggiorna i dati, stato dei dati, collegamento e cambio di
   server, diagnostica e ntfy. Solo web e iPhone, perché servono solo a chi gestisce il server; su Android la sezione non
   c'è. Le schermate di prova `impostazioni-gestione` e `lega-stato*` diventano solo iPhone.
12. **Tablet e tastiera fisica** (da decidere: D11): righe 56-57 del §10. Su un tablet Android l'app mostra l'impaginazione
   del telefono, centrata e con una larghezza massima, senza barra laterale né due colonne, e senza le scorciatoie da
   tastiera. Le foto del tablet non si fanno.

## 4. Struttura di `android/`
```
android/
  README.md                      cosa c'è, come si compila, da provare sul telefono (come ios/README.md)
  settings.gradle.kts  build.gradle.kts  gradle.properties  gradlew  gradlew.bat
  gradle/libs.versions.toml      versioni fissate
  gradle/verification-metadata.xml   impronte sha256 di ogni libreria scaricata
  gradle/wrapper/                gradle-wrapper.jar (impronta controllata da un test) e .properties (distributionSha256Sum)
  file-esterni.txt               file fuori da android/ che i test leggono (fa partire la CI Android, come per l'iPhone)
  testi/<prefisso>.txt           chiavi del catalogo usate solo da Android
  docs/LINEE-GUIDA.md            corrispondenze SwiftUI → Compose, misure, colori
  docs/WIDGET.md
  dominio/                       Kotlin/JVM puro (niente android.*)
    src/main/kotlin/it/schieraxi/dominio/   modelli, Formato, Quando, TempiLega, SogliaGioca, StatoScelta, TestaFormazione,
                                            LetturaPedina, Decisioni, Giornate, Precisione, RegoleLogica, GeneratoreVolto, …
    src/main/kotlin/it/schieraxi/catalogo/Catalogo.kt   (generato)
    src/test/kotlin/…            unitari, CasiCondivisiTest, ContrattoDalVeroTest
  app/
    src/main/AndroidManifest.xml
    src/main/kotlin/it/schieraxi/app/
      App.kt  MainActivity.kt  AppModel.kt  Navigazione.kt
      dati/        ServerClient, ServerHttp, FinteServer, Cache, Stato/Caricatore, Sessione (Keystore), Immagini, Lingua
      ui/design/   Tema, Carta, Stati, Marchio, TitoloPagina, Pillole, RigaGiocatore, Volto, Grafici
      ui/accesso/  ui/formazione/  ui/scheda/  ui/giornate/  ui/cerca/  ui/impostazioni/  ui/lega/
      avvisi/      Promemoria (AlarmManager), Aggiornamento (WorkManager), Riavvio (BOOT_COMPLETED)
      widget/      tre GlanceAppWidget e i loro ricevitori
      sistema/     Collegamenti, VersioneNuova, Scorciatoie, Demo
    src/main/res/  icone adattive, colori, xml dei widget, network_security_config (solo https)
    src/debug/     GalleriaWidget (per le foto dei widget; non entra nell'APK di rilascio)
    src/test/      unitari, interfaccia con Robolectric, foto con Roborazzi
    src/androidTest/   pochi test di fumo per l'emulatore
```

**Dipendenze ammesse** (fissate nel catalogo delle versioni):
- di esecuzione: libreria standard di Kotlin, kotlinx-coroutines-android, kotlinx-serialization-json, androidx core-ktx,
  activity-compose, Compose BOM (ui, foundation, material3, tooling-preview), lifecycle viewmodel/runtime compose,
  glance-appwidget (+ material3), work-runtime-ktx, androidx.browser (Custom Tabs), OkHttp;
- solo per i test: junit4, kotlinx-coroutines-test, mockwebserver, Robolectric, compose ui-test-junit4, Roborazzi,
  glance-appwidget-testing.

**Vietate**: Firebase e Play Services, analisi e raccolta dei crash, Hilt/Dagger, Retrofit, Room, Coil e Glide, Accompanist,
material-icons-extended (le poche icone sono vettori nel progetto), navigation-compose (la navigazione è uno stato nostro,
come `Navigazione` dell'iPhone: tre voci più la ricerca, una pila per voce, fogli).

## 5. Rete, dati, accesso
- **Indirizzo**: il predefinito dell'iPhone, mai chiesto. Server proprio solo `https://` (area avanzata col tocco lungo sul
  marchio, «Prova la connessione»). `network_security_config` vieta l'http in chiaro.
- **Intestazioni**, come `ServerHTTP` dell'iPhone: `Authorization: Bearer <token>`; `X-Fanta: 1` su ogni scrittura;
  `Accept-Language: it` sempre (`LinguaServer`: l'app è solo in italiano); `X-Schieraxi-Client: android` (il server oggi
  riconosce solo `ios` in `_da_dove`, `fanta/server.py`: compito server P0.9, che serve solo quando non c'è il token,
  perché con `Bearer` il salvataggio risulta già «dall'app»). Niente `X-Fanta-Dispositivo`: il server lo accetta dalle app
  native (dispositivo fidato, `fanta/rotte_account.py`), ma l'iPhone oggi non lo manda (nessun riferimento in
  `ios/Sources`). Se lo si vuole, si aggiunge sui due lati con un'issue.
- **Tempi massimi**, uguali all'iPhone (`ServerClient.swift`, `costruisci`): 20 secondi per le rotte `/api/account/`, 25 per
  tutte le altre, 120 per i caricamenti di file (`carica`: rose, stemmi, maglie). Scaduto il tempo si mostra
  `comune.server_non_risponde` e si può riprovare.
- **Codici**: `202` → «sto calcolando», si riprova dopo `Retry-After`, altrimenti dopo 3 secondi, fino a 40 volte (mai per
  accedi, registra e recupero), come `attesaCalcolo` e `massimoTentativiCalcolo` dell'iPhone. `429` → frase `detail`, riprova dopo `Retry-After`
  dove l'iPhone lo fa.
  `401` → schermata d'accesso (sessione scaduta). `412` → si rilegge e si mostra `err.conflitto` o
  `comune.cambiato_altrove`. `409` `formazione_chiusa` o `campionato_finito` e `400` `giocatore_bloccato` → frase del server.
  `503` e `507` senza `Retry-After` → si mostra e non si riprova.
- **ETag**: `If-None-Match` su widget, immagini e dove l'iPhone lo manda; `If-Match` sulle scritture con l'ETag letto (regole,
  avvisi, `scelta:<giornata>`, rose). L'ETag col suffisso `-en` si rimanda così com'è.
- **Errori di rete**, con le frasi del catalogo dell'iPhone: senza rete `comune.rete_no`; server spento o tempo scaduto
  `comune.server_non_risponde`; risposta con errore e copia salvata `comune.cache_errore` con giorno e ora.
- **Cache**: l'ultima risposta di ogni schermata in `cacheDir/api/<server>/` (al massimo 150 file, la più vecchia esce per
  prima), con la striscia «dati salvati il …». La copia della scelta (`CopiaScelta`) e la spunta «L'ho messa» locale come
  sull'iPhone.
- **Sessione**: token della sessione cifrato con AES-GCM e una chiave dell'Android Keystore; `allowBackup=false`
  (un token copiato su un altro telefono non si decifra comunque). «Esci» e «Esci da tutti» cancellano tutto.
- **Google**: `POST /api/account/social/google/inizia` con `sfida` e `piattaforma: "ios"`. Per il server `"ios"` vuol dire
  «app nativa»: è il valore che fa tornare a `schieraxi://social?codice=` invece che alla pagina web
  (`fanta/rotte_account.py`, `piattaforma == "ios"`). **Non si aggiunge** `"android"` a `PIATTAFORME` (`fanta/social.py`):
  la tabella `flussi_social` ha il vincolo `piattaforma IN ('web', 'ios')` (`fanta/account.py`), e `social.py` confronta
  ancora con `"ios"` per i ritorni oltre il limite. Cambiare tutto questo vorrebbe una migrazione del database per nessun
  vantaggio. `docs/API.md` lo scrive accanto alla rotta. Si apre l'indirizzo in una Custom Tab, si riceve il
  codice con un intent-filter, poi `social/scambio` col verificatore tenuto in memoria. Lo schema personalizzato può essere
  intercettato da un'altra app, ma senza il verificatore il codice non vale (PKCE). In più si potrebbe usare un App Link
  https verificato (D8).
- **Registrazione**: modi `invito`, `email` e `aperta` dal 401, casella dei termini, codice di recupero mostrato una volta,
  come `ModalitaRegistrazione.swift`.

## 6. Avvisi e lavoro in background
- **«Avvisi su questo dispositivo»**: un interruttore che chiede il permesso delle notifiche (Android 13 e più nuovi) e
  programma due promemoria, un'ora e un quarto d'ora prima della scadenza. Stessa logica dell'iPhone: tacciono con
  `serve_promemoria: false`; titolo e testo da `testi_promemoria` (validi solo se la giornata è stata letta al massimo due
  ore prima), altrimenti la frase minima `oggi.prossima_chiude`; niente promemoria nelle ore tranquille (`silenzio` del
  server); nessun promemoria locale se il server manda già i suoi all'app (`app_nativa` con `canale` e `dispositivi` a 0,
  `ArchivioAvvisiDalServer`).
- **Ora esatta**: sempre `setExactAndAllowWhileIdle`, con il permesso `USE_EXACT_ALARM` (Android 13 e più nuovi: concesso
  all'installazione, l'utente non deve fare niente). Il Play Store lo ammette solo per sveglie e calendari, ma l'app non ci
  va: per un APK va bene. Per Android 12 il manifest dichiara anche `SCHEDULE_EXACT_ALARM` con `maxSdkVersion="32"` (lì è
  concesso per difetto); dalla 8 alla 11 non serve permesso. Niente ripiego a finestra e niente riga d'aiuto. Questo non
  vuol dire «mai in ritardo»: alcuni produttori (§12) possono ritardare o fermare le sveglie delle app; si verifica sul
  telefono vero. Dopo un riavvio i promemoria si riprogrammano dalla giornata salvata (`RECEIVE_BOOT_COMPLETED`). Canali
  «Promemoria» e «Aggiornamenti dell'app».
- **Aggiornamento in background**: WorkManager periodico (ogni ora, con la rete), come `BGAppRefreshTask`: rilegge
  `GET /api/oggi`, riprogramma i promemoria e aggiorna i widget. Più fitto vicino alla scadenza, se la batteria lo permette.
- **ntfy** (solo per chi gestisce il server, in Gestione): il tocco su un avviso ntfy con `Click: schieraxi://formazione`
  apre l'app grazie all'intent-filter dello schema.
- **UnifiedPush**: il server lo reggerebbe già (`/api/push/iscrivi` accetta endpoint Web Push pubblici; UnifiedPush usa la
  stessa cifratura), ma vuole l'app ntfy sul telefono come distributore e darebbe ad Android l'avviso «cambio della
  formazione» che l'iPhone non ha. Proposta: non adesso (D3). Chi vuole tenere quell'avviso lascia accese le notifiche della
  web in Chrome, come può fare chi ha l'iPhone.

## 7. Widget (Glance)
- Tre widget come `ios/docs/WIDGET.md`, con le misure che Android ha: Prossima giornata (piccolo, medio), Formazione
  consigliata (piccolo, medio, grande), Da controllare (medio, grande). `SizeMode.Responsive`.
- Dati: `GET /api/widget` con la sessione dell'app (stesso processo) e `If-None-Match`; `304` tiene i dati di prima; `202`
  tiene i dati di prima e riprova più tardi. Dopo ogni lettura fresca di Oggi l'app aggiorna i widget (`updateAll`), come
  `dopoLetturaFresca`.
- Fasi, campionato finito, «senza formazione», frasi del server: la stessa logica, portata dal dominio dell'iPhone
  (`WidgetRiassunto`, `RiassuntoOggi`, `CasoWidget`) in `:dominio`, con gli esempi condivisi (§3.3).
- Testi che non entrano: Glance non ha `ViewThatFits`. Le forme vengono da `ParoleWidget` portato in Kotlin e si sceglie la
  prima che entra in base alla misura (`LocalSize`) e alla scala del testo. Mai «…».
- Tocco: apre `schieraxi://formazione`. Tema chiaro e scuro con i colori dell'app.
- Foto: attività di debug `GalleriaWidget` che compone ogni widget in ogni misura (RemoteViews generate da Glance e mostrate
  in una vista; l'API esatta va verificata nel compito) e l'emulatore la fotografa.

## 8. Aspetto e accessibilità
- Colori da `Tema.swift` e `docs/DESIGN.md`. Accento verde `#3DDC97` nel tema scuro, oliva `#526600` nel chiaro (con testo
  bianco sopra); lime `#D4F34A` e `#86A800` solo per fondi e dettagli. Colori semantici solo per gli esiti. Carattere di
  sistema.
- Tema Automatico, Chiaro o Scuro (Impostazioni › Aspetto) e «Animazioni ridotte» come sull'iPhone. Si rispetta anche
  «Rimuovi animazioni» di sistema.
- Testo grande: tutto in `sp`, scala del testo fino al 200% (non lineare da Android 14). Nessuna altezza fissa attorno al
  testo; il cognome sul campo non si rimpicciolisce sotto 12 sp.
- TalkBack: una frase intera per riga (`semantics(mergeDescendants)`) con le stesse parole di VoiceOver. Grafici con
  etichetta e l'elenco dei numeri. Aree di tocco da 48 dp. Controlli di accessibilità nei test Compose (ATF), dove la
  versione di Compose li offre.
- Tablet e pieghevoli (da decidere, D11): proposta, l'impaginazione del telefono centrata con una larghezza massima (§3.8
  voce 12). Se il proprietario li vuole come l'iPad: da 600 dp barra laterale e due colonne (`ColonneUguali`), sempre in
  ordine di lettura, e tastiera fisica con Ctrl+1…3 per le tre voci e Ctrl+R per aggiornare.
- Ritorno indietro predittivo e da bordo a bordo (obbligatorio con il `targetSdk` nuovo).

## 9. CI su GitHub (runner Ubuntu, gratuiti)
Solo azioni di GitHub fissate per hash (`actions/checkout`, `setup-java`, `cache`, `upload-artifact`, `download-artifact`);
permessi minimi; nessun segreto nei job delle PR.

### 9.1 `android.yml` (in ogni PR che tocca Android, blocca l'unione)
- Lo chiama `test.yml` (job `android`, dopo `cambi`) quando la PR tocca `android/`, `.github/workflows/android.yml` o un file
  di `android/file-esterni.txt` (le fixture dell'iPhone, `tests/dati/casi/`, il catalogo `fanta/testi/` per via dei file
  generati), e non è in bozza. `unisci` lo aspetta come aspetta `ios`; `main-rosso` lo conta.
- Job unico su `ubuntu-latest`: JDK 21 (`setup-java` con la cache di Gradle), poi `./gradlew --no-daemon :dominio:test
  :app:testDebugUnitTest :app:lintDebug :app:assembleDebug :app:assembleRelease` (rilascio senza firma, con R8). Tempo
  stimato da 8 a 12 minuti, la metà con la cache. Le versioni dell'SDK mancanti si installano con `sdkmanager`.
- Nei test unitari: dominio, rete con `MockWebServer`, ViewModel, interfaccia con Robolectric (il «fumo» dell'iPhone: demo
  che si apre, le tre voci, la Formazione con la giornata e la riga dello stato, un modulo che si salva, «Torna alla
  consigliata», Impostazioni con Aspetto e Novità, scheda che si apre e si chiude, ricerca) e **foto con Roborazzi**.
- **Quali foto.** Nelle PR solo le schermate scritte nella riga `Foto Android:` della descrizione (come la riga `Aspetto:`
  della web), in chiaro e scuro, testo normale e al 200%; senza riga, nessuna foto. Su `main`, dopo l'unione, la matrice
  completa: tutte le schermate di `TUTTE` in chiaro e scuro, testo normale e al 200% (e tablet se D11 lo chiede). Così la
  corsa di una PR resta corta, e una schermata rotta di nascosto si vede comunque il giorno stesso.
- Artifact: `screenshot-android` (14 giorni), resoconti dei test se qualcosa fallisce (7 giorni). Al posto del «Foto da
  fare» dell'iPhone, chi rivede guarda l'artifact.
- **Job `impronte`** (a mano con `workflow_dispatch` sul ramo, e da solo nelle PR quando il file manca, come nella prima, P0.7):
  rigenera `gradle/verification-metadata.xml` con `--write-verification-metadata sha256` e lo pubblica come artifact, da
  mettere nella PR che cambia una dipendenza. Il job normale fallisce se un file scaricato non ha la sua impronta.
- Più avanti, facoltativo: confronto delle foto con quelle di `main`, come `aspetto-web.yml`.

### 9.2 Emulatore (non blocca l'unione)
- Job `emulatore` in `android.yml`: a mano, con l'etichetta `emulatore` sulla PR, e su `main` dopo l'unione se `android/` è
  cambiata. Attiva KVM sul runner (regola udev), installa con `sdkmanager` un'immagine `google_apis` x86_64, avvia
  l'emulatore senza finestra, installa l'APK di debug e quello dei test, lancia `connectedDebugAndroidTest` (fumo,
  collegamenti `schieraxi://`, promemoria con l'orologio accorciato, importazione di un CSV da un intent) e fotografa i
  widget dalla `GalleriaWidget` con `adb exec-out screencap`. Tempo stimato da 12 a 20 minuti. A mano anche con API 26, per
  la versione minima.
- In caso di errore: issue `P1` come per gli altri controlli di `main`, solo se rosso su `main`.

### 9.3 `apk.yml`: compilazione, firma, release
- **Al massimo un APK al giorno**, non uno per unione: parte una volta al giorno di notte (`schedule`, fuori dall'orario
  delle partite) e fa la release solo se `android/` è cambiata dall'ultimo APK pubblicato; in più a richiesta del
  proprietario (`gh workflow run apk.yml`, per esempio per una correzione urgente). Senza release: lancio a mano su un ramo,
  per le prove. Agli amici arriva così al massimo un avviso al giorno, e le release non riempiono l'elenco. **Il file non
  si rinomina**: il numero di corsa è il `versionCode`.
- Job `compila` (sola lettura, nessun segreto): `assembleRelease` senza firma, `versionCode = numero di corsa`,
  `versionName = 1.0.<N>`, repository letto da `GITHUB_REPOSITORY` in `BuildConfig`. Passa l'APK come artifact.
- Job `firma-e-pubblica` (`environment: android-firma`, solo `main`; non scarica il repository, quindi nessuno script del
  progetto vede i segreti): prende l'APK, decodifica la chiave in `$RUNNER_TEMP`, `apksigner sign --ks …
  --ks-pass env:ANDROID_FIRMA_PASSWORD` (schemi v2 e v3), `apksigner verify --print-certs`, confronta l'impronta SHA-256 con
  la variabile `ANDROID_IMPRONTA_FIRMA` (si ferma se è diversa), cancella la chiave e crea la release:
  `gh release create android-<N> SchieraXI.apk versione.json --latest=false`. Solo dopo, aggiorna la release fissa
  `android-ultima` (creata la prima volta, sempre con `--latest=false`):
  `gh release upload android-ultima versione.json SchieraXI.apk --clobber`. `versione.json` contiene
  `{versionCode, versionName, sha256, apk, note}`, dove `apk` è l'indirizzo dell'APK nella release `android-<N>`. In questo
  ordine l'app non vede mai una versione il cui APK non c'è ancora. Permessi: `contents: write` solo qui.
- `build-<N>` dell'iPhone resta l'unica «Latest» (è il sorgente di SideStore). `NuovaVersione.swift` legge le ultime 30
  release e tiene solo i tag `build-`: con un APK al giorno le release Android sono poche e non spingono fuori le `build-`.
  Il server installa la punta di `main`, non i tag: non è toccato.

### 9.4 Avviso di aggiornamento nell'app
- **Non** come `NuovaVersione.swift`, che legge le ultime 30 release: nel repository escono una release `v` per ogni
  versione nuova del server e una `build-` per ogni IPA, mescolate, e oggi le ultime 30 coprono circa 7 ore. Una release
  Android di ieri sarebbe già fuori dall'elenco, e l'app non saprebbe mai della versione nuova.
- L'app legge un solo file a indirizzo fisso:
  `https://github.com/<repository>/releases/download/android-ultima/versione.json` (un file scaricato, non l'API di
  GitHub, quindi niente limite di richieste dell'API). Se `versionCode` è più alto del suo, Impostazioni mostra «C'è una
  versione nuova» con «Scarica», che apre nel browser l'indirizzo `apk` del file (Android chiede di installarlo e lo
  aggiorna, perché la firma è la stessa). Controllo a ogni apertura, al massimo una volta ogni 6 ore. La notifica «C'è una
  versione nuova», una volta per versione e con gli avvisi accesi, arriva con gli avvisi (fase 4).
- Alternativa scartata: i tag con `GET /repos/{repo}/git/matching-refs/tags/android-` (solo tag Android, ma con un tag al
  giorno l'elenco cresce e va letto tutto, ordinato a mano perché `android-10` viene prima di `android-9`).
- Nessun installatore dentro l'app (servirebbe il permesso `REQUEST_INSTALL_PACKAGES`). Chi vuole l'aggiornamento automatico
  usa Obtainium, libero e gratuito (guida in `docs/INSTALLAZIONE-ANDROID.md`, D4). Come configurarlo (release fissa
  `android-ultima` o filtro dei tag `^android-[0-9]+$`) si prova in P0.10: anche Obtainium legge le release di GitHub e
  potrebbe avere lo stesso limite dell'elenco.

### 9.5 Cosa deve fare il proprietario (una volta sola, dal PC)
1. Installare un JDK gratuito: `winget install EclipseAdoptium.Temurin.21.JDK` (serve solo `keytool`).
2. Creare la chiave **fuori dal repository**. `keytool` chiede la password senza mostrarla; usa una password lunga e
   salvala nel gestore delle password:
   `keytool -genkeypair -keystore "$env:USERPROFILE\schieraxi-firma.jks" -storetype PKCS12 -alias schieraxi -keyalg RSA -keysize 4096 -validity 18250 -dname "CN=SchieraXI, O=SchieraXI, C=IT"`
   (il certificato si legge dentro ogni APK, che è pubblico: per questo il nome è SchieraXI e non quello di una persona).
3. Fare **due copie di riserva** del file `.jks` e della password, fuori dal PC (chiavetta e gestore delle password). Se la
   chiave si perde, ogni amico deve disinstallare e reinstallare l'app (i dati stanno sul server: rifà solo l'accesso e
   rimette i widget).
4. Su GitHub: Settings › Environments › New environment `android-firma`; Deployment branches: solo `main` (o «Protected
   branches»).
5. Mettere i due segreti nell'ambiente, senza scrivere password in chiaro né nella storia dei comandi:
   - `[Convert]::ToBase64String([IO.File]::ReadAllBytes("$env:USERPROFILE\schieraxi-firma.jks")) | gh secret set ANDROID_FIRMA_KEYSTORE --env android-firma`
   - `gh secret set ANDROID_FIRMA_PASSWORD --env android-firma` (chiede il valore senza mostrarlo).
6. Mettere l'impronta pubblica del certificato come variabile, non come segreto: leggerla con
   `keytool -list -v -keystore "$env:USERPROFILE\schieraxi-firma.jks" -alias schieraxi` (riga «SHA256:»), poi
   `gh variable set ANDROID_IMPRONTA_FIRMA --body "<impronta>"`.
7. Prendere le decisioni (in testa a questo documento) e provare il primo APK su un telefono (lista «Da provare sul
   telefono» del piano).
Nessun agente tocca chiave, password o segreti: solo il proprietario.

## 10. Le funzioni dell'iPhone di oggi da portare
Ricavato da `ios/Sources`, `ios/WidgetSources` e `ios/README.md` su `main` del 26/11/2026. È l'inventario iniziale di
`funzioni.json`: il numero della prima colonna è l'id della funzione (1 → `F1`), e `porting.base` è l'ultimo (64). «F» =
fase Android. I nomi fra parentesi sono file Swift (senza `.swift`) o tipi dentro un file; dove la prova sta solo nei test
è scritto. La riga 64 e la 63 nascono `da-fare` anche su web e iPhone: i due lavori in corso le aggiornano invece di
crearne di nuove.

| # | Area | Funzione dell'iPhone (file principali) | F | Note per Android |
|---|---|---|---|---|
| 1 | Accesso | Prima schermata Accedi / Registrati, modi `invito`, `email` (con codice), `aperta`, termini, codice di recupero mostrato una volta (`AccessoView`, `ModuloAccesso`, `ModalitaRegistrazione`, `CodiceRecuperoView`) | 1 | |
| 2 | Accesso | Password dimenticata: con il codice di recupero e via email | 1 | |
| 3 | Accesso | 429 con `Retry-After`, frasi d'errore annunciate anche a voce (`ErroreVista` in `Stati.swift`, `ErroreApi` in `ServerClient.swift`, `SchermataAccesso` in `AccessoView.swift`); il 401 di una password sbagliata non cambia il modo di registrazione (`ModalitaRegistrazione`). Prove iPhone: `PasswordSbagliataTests`, `AnnuncioErroreTests`, `MessaggiErroreTests` | 1 | |
| 4 | Accesso | Accesso con Google (`AccessoGoogleView`, `AccessoSocial`) | 3 | Custom Tab; `piattaforma: "ios"` = app nativa (§5) |
| 5 | Accesso | Area avanzata: server proprio https, «Prova la connessione», «Prova con dati di esempio» ed «Esci dalla prova» (`ProvaConnessione`, `ProvaEsempio`) | 1 | |
| 6 | Accesso | Configurazione guidata con passi saltabili, ripresa dal server, ritorno alla guida (`PrimoAvvioGuidato`, `ConfigurazioneGuidataView`, `RitornoAllaGuida`) | 3 | |
| 7 | Sistema | Spostamento dal server vecchio (`MigrazioneServer`) | – | non-serve: Android nasce nuovo |
| 8 | Formazione | Testa per fase: prima della scadenza con conto ogni 30 s, chiusa, in corso (rilettura ogni 5 min), finita con «Com'è andata», senza data, campionato finito, «per la prossima» (`TestaFormazione`, `TestaFormazioneView`, `FasiGiornata`) | 1 | |
| 9 | Formazione | Decisioni: al massimo 2 voci di `da_fare` con la loro azione (`Decisioni`, `DecisioniFormazione`) | 2 | |
| 10 | Formazione | Modulo con i punti attesi e «di solito fra» (`IntervalloPunti`) | 1 | |
| 11 | Formazione | Campo: pedina con pillola del fantavoto, «gioca N%» sotto l'80%, stato; tocco → scheda (`CampoFormazione`, `LetturaPedina`, `EsitoPedina`) | 1 | volto dalla fase 2, prima la maglia |
| 12 | Formazione | Riga dello stato della scelta, con le frasi della web (`StatoScelta`, `RigaStatoScelta`) | 1 | |
| 13 | Formazione | Salvataggio automatico: `valuta` con `salva`, `DELETE /api/scelta`, If-Match, 412, 409, 400, avviso «non salvata» sulle altre schede (`FormazioneViewModel`, `AvvisoNonSalvata`) | 1 | |
| 14 | Formazione | «Copia per l'app della lega» e «L'ho messa» (`TestoFormazione`) | 1 | |
| 15 | Formazione | Panchina in ordine, «Non schierati», «Infortunati e squalificati» | 1 | |
| 16 | Formazione | Giornata in corso: campo da `in_corso.giocatori`, cambi dalla panchina | 1 | |
| 17 | Formazione | Partite rinviate, con il menu per la giornata (`PartiteRinviate`, `PartiteRinviateView`) | 2 | |
| 18 | Formazione | Formazione di un'altra squadra, in sola lettura | 2 | |
| 19 | Formazione | Anticipi bloccati (`bloccati`, `err.giocatore_bloccato`) | 2 | |
| 20 | Formazione | Copia offline della scelta e striscia dei dati salvati (`CopiaScelta`, `DatiVecchi`) | 1 | |
| 21 | Formazione | «Sostituisci» (`SceltaSostituto`) | 1 | |
| 22 | Formazione | «Metti in campo» e «Chi esce per …» (`SceltaChiEsce`, `MettiInCampo`) | 2 | |
| 23 | Scheda | Testa: volto, ruolo e club, partita, fantavoto atteso, «gioca N%», stato, nota della fonte (`TestaScheda`, `LetturaScheda`) | 1 | |
| 24 | Scheda | «Perché è titolare», «Perché questo numero», «Ultimi voti» (`PercheTitolare`, `BloccoPercheNumero`) | 1 | |
| 25 | Scheda | «Tutti i numeri»: quotazione, partita, prossime partite, forma, grafico dei voti, occasioni, stagione (`TuttiINumeri`, `Grafici`) | 2 | grafici con Canvas |
| 26 | Volti | Volti illustrati versione 3 (`GeneratoreVolto`, `AvatarVolto`, `docs/AVATAR.md`); foto, stemmi e maglie in cache (`Immagini`) | 2 | estrazioni negli esempi condivisi |
| 27 | Giornate | Riga di stato (stemma, giornata, squadra, «dati del …») (`RigaStato`) | 1 | |
| 28 | Giornate | Errore medio + «Dettagli» → «Quanto ci abbiamo preso» con grafico e giornata per giornata (`Precisione`, `PrecisioneView`) | 1 | grafico dalla fase 2 |
| 29 | Giornate | Una riga per giornata finita: punti, attesi, «+2,8 sul previsto», frase della scelta (`Giornate`, `RigaGiornataView`) | 1 | |
| 30 | Giornate | Dettaglio: frase meglio e peggio, gli 11 con Atteso e Preso, «Al posto di …» (`DettaglioGiornataView`) | 1 | |
| 31 | Giornate | «Non è quello che ho schierato» (`FormazioneManualeDiarioView`, `/api/diario/schierata`) | 2 | |
| 32 | Cerca | Ricerca di un giocatore, al massimo 12 righe → scheda (`RicercaGiocatoreView`, `DatiRigaRicerca`) | 2 | |
| 33 | Impostazioni | Pagina unica: Avvisi, La mia lega, Il tuo account, Aspetto, Informazioni, Gestione, nell'ordine della web (`ImpostazioniView`, `VociImpostazioni`) | 1 | sezioni accese man mano |
| 34 | Impostazioni | Nuova stagione, passaggio guidato (`PassiNuovaStagione`) | 3 | |
| 35 | Avvisi | «Avvisi su questo dispositivo»: promemoria locali con testi del server, `serve_promemoria`, ore tranquille, avvisi dal server (`Notifiche`, `AvvisiDispositivo*`, `OreTranquille`) | 4 | AlarmManager (§6) |
| 36 | Lega | Aggiorna le rose: Excel, CSV, testo e incolla, «Apri con», anteprima, conferma con If-Match, correzione dei non riconosciuti (`ImportaRoseView`, `AnteprimaRose`, `FileRose`, `EsitoRoseSalvate`) | 3 | intent-filter per file e condivisione |
| 37 | Lega | La mia squadra: rosa con previsioni e crediti, stemma e maglia (galleria o indirizzo), scelta della squadra, «Non è la tua squadra?» (`SceltaSquadraView`, `SelettoreMiaSquadra`, `RigaRosa`) | 3 | Photo Picker senza permessi |
| 38 | Lega | Le altre squadre, con `squadre_altrui` (`ParoleSquadre`) | 3 | |
| 39 | Lega | Regole e scadenza: editor con i limiti, controlli, modificatore della difesa, moduli, panchina, tempi della lega, importazione dal regolamento con «Non applicato», regola dei rinvii (`RegoleEditor`, `CampiRegole`, `LimitiRegole`, `AnteprimaRegolamento`) | 3 | |
| 40 | Lega | Immagine arrivata da un'altra app → stemma o maglia (`ImmagineRicevutaView`) | 3 | |
| 41 | Account | Nome, email (collega, conferma, togli), cambia password, codice di recupero, accessi Google (collega, scollega, imposta password), elimina, Esci, Esci da tutti (`AccountPagina`, `Account`, `TestiAccount`) | 1 (Esci, Esci da tutti, nome) e 3 (il resto) | |
| 42 | Aspetto | Tema e «Animazioni ridotte» (`TemaScelto`, `Aspetto`) | 1 | |
| 43 | Sistema | Riga del widget e «Collega il widget» (`CollegaWidgetView`, `TokenWidget`) | – | non-serve (§3.8, 2) |
| 44 | Sistema | «C'è una versione nuova» (`NuovaVersione`) | 0, 1, 4 | logica e lettura di `versione.json` in fase 0 (P0.8), riga in Impostazioni in fase 1 (P1.11), notifica in fase 4 (§9.4) |
| 45 | Informazioni | Privacy, Termini d'uso, Crediti e fonti, Codice sorgente (se `sorgente`), Versione, Novità (`InformazioniLegali`, `ParoleNovita`) | 1 | |
| 46 | Gestione | Aggiorna i dati con avanzamento e «in corso altrove» (`AggiornaDatiViewModel`) | 5 o – | da decidere (D10, §3.8 voce 11): proposta non-serve |
| 47 | Gestione | Stato dei dati: prova del modello, registro delle giornate, taratura, gol attesi nostri, consiglio (`RegistroGiornateSezione`, `GolAttesiNostriSezione`, `ConsiglioFormazioneSezione`) | 5 o – | da decidere (D10): proposta non-serve |
| 48 | Gestione | Collegamento e cambio di server, diagnostica, ntfy («Notifiche ntfy che mandi tu», app nativa) | 5 o – | da decidere (D10): proposta non-serve |
| 49 | Gestione | Certificato e rinnovo con SideStore (`Certificato`) | – | non-serve (§3.8, 3) |
| 50 | Sistema | Funzioni accese (`/api/funzioni`) e «Non disponibile» (`Funzioni`, `ArchivioFunzioni`) | 3 | |
| 51 | Widget | Prossima giornata, Formazione consigliata, Da controllare; fasi, campionato finito, senza formazione, testi che entrano (`WidgetSources/*`, `WidgetRiassunto`) | 4 | Glance (§7) |
| 52 | Sistema | Collegamenti `schieraxi://` con i nomi vecchi (`Collegamenti`) | 1 | casi condivisi |
| 53 | Sistema | Aggiornamento in background (`Aggiornamento`) | 4 | WorkManager |
| 54 | Sistema | Siri e Comandi (`Comandi`) | 4 | scorciatoie del lanciatore (§3.8, 4) |
| 55 | Sistema | Cache offline e frasi della rete | 1 | |
| 56 | Sistema | Tastiera: Cmd+1…3, Cmd+R | 5 o – | da decidere (D11, §3.8 voce 12): proposta non-serve; altrimenti Ctrl |
| 57 | Sistema | iPad: colonne, barra laterale (`ColonneUguali`, `Colonne`) | 5 o – | da decidere (D11): proposta non-serve; altrimenti tablet da 600 dp |
| 58 | Sistema | Accessibilità: testo grande, VoiceOver, Riduci movimento, aree di tocco | 1–5 | controllata in ogni fase, verifica finale in 5 |
| 59 | Sistema | Modalità demo e schermate di prova (`Demo`, `DatiDemo`, `LegaDemo`) | 0–5 | stessi nomi (§3.5) |
| 60 | Sistema | Suggerimenti TipKit, aptica (`Suggerimenti`, `Haptics`) | 5 | aptica sì; suggerimenti: D5 |
| 61 | Account | «Scarica i tuoi dati»: il file dei dati personali da condividere (`DatiPersonali`, `GET /api/backup` con la sessione normale; prova iPhone `DatiPersonaliTests`) | 3 | foglio di condivisione di Android con un `FileProvider` |
| 62 | Sistema | Schermo protetto: l'anteprima nelle app recenti non mostra password, email, codice di recupero, nomi e punti (`schermoProtetto()` in `Protezione.swift`, usato in accesso, Google, codice di recupero, account e Giornate) | 1 | `FLAG_SECURE` sulle stesse schermate; su Android blocca anche le foto dello schermo, quindi in demo è spento (le schermate di prova si fotografano) |
| 63 | Feedback | «Scrivici»: la sezione del feedback (lavoro in corso per server, web e iPhone, non ancora su `main`) | quella in corso quando il lavoro arriva su `main` | quel lavoro aggiorna questa riga (web e iPhone) e apre l'issue Android; il compito passa davanti agli altri della sua area |
| 64 | Accesso | Registrazione libera senza inviti (lavoro in corso, non ancora su `main`; il modo `aperta` c'è già, riga 1) | quella in corso quando il lavoro arriva su `main` | come la riga 63 |

## 11. Fasi, traguardi, stima
Ogni fase finisce con un traguardo che si verifica, e con una PR di chiusura che segna `fatto` (con `prova_android`) le
righe della fase in `funzioni.json` (§3.1: solo lì, per non far litigare le PR fra loro).

| Fase | Contenuto | Traguardo verificabile | PR |
|---|---|---|---|
| 0. Fondamenta | regole e documenti, registro della parità, catalogo Kotlin, esempi condivisi, scheletro con due moduli, `android.yml`, `apk.yml` con firma e release, logica della versione nuova, intestazione del server, guida d'installazione | release `android-<N>` firmata (impronta controllata dal job) e `android-ultima/versione.json` aggiornato; un APK installato si apre col marchio; `coerenza.py --controlla` e i test del catalogo verdi | 11-12 |
| 1. Usabile dagli amici | rete e sessione, accesso, schermo protetto, Formazione (testa, campo, modulo, stato, salvataggio, copia, «L'ho messa», panchina, «Sostituisci»), scheda (testa e perché), Giornate (righe, dettaglio, «Quanto ci abbiamo preso» senza grafico), Impostazioni di base (account con Esci ed Esci da tutti, Aspetto, Informazioni, versione e «C'è una versione nuova»), demo, collegamenti | un amico Android installa l'APK, si registra, cambia la formazione e la ritrova uguale sulla web; l'app dice «C'è una versione nuova» quando esce la successiva; foto di tutte le schermate di prova della fase in chiaro e scuro e al 200%; fumo Robolectric verde | 25-30 |
| 2. Formazione e scheda complete | decisioni, rinvii, «Metti in campo», anticipi bloccati, altra squadra, «Tutti i numeri» con grafici, volti illustrati, ricerca, «Non è quello che ho schierato», grafico della precisione | tutte le schermate di prova `formazione-*`, `giocatore*`, `giornate-*`, `ricerca` presenti sui due lati; esempi condivisi di Formazione e volti verdi su iPhone e Android | 15-18 |
| 3. La mia lega e l'account | rose (tutti i formati, «Apri con»), La mia squadra con stemma e maglia, Le altre squadre, Regole, nuova stagione, configurazione guidata, funzioni, account completo con «Scarica i tuoi dati», Google | sull'emulatore un CSV aperto «con SchieraXI» arriva all'anteprima e si salva; foto `lega-*` (tranne `lega-stato*`), `guida*` e `accesso-account*` presenti | 20-25 |
| 4. Avvisi, widget, sistema | promemoria locali, ore tranquille, avvisi dal server, notifica della versione nuova, WorkManager, riavvio, tre widget, scorciatoie | sull'emulatore un promemoria con la scadenza vicina arriva all'ora giusta e tace con «L'ho messa»; foto dei widget in ogni misura, chiaro e scuro | 15-18 |
| 5. Gestione e chiusura | aptica, giro di accessibilità, debito di parità a zero; Gestione, tablet e tastiera solo se D10 e D11 dicono di farli | `porting.chiuso = true` con zero righe `da-fare` senza issue; controlli di parità severi | 4-5 (13-14 con Gestione, tablet e tastiera) |

**Totale: fra 100 e 120 PR** contando Gestione, tablet e tastiera, fra 90 e 110 se passano D10 e D11; più 2
o 3 per «Scrivici» e la registrazione libera. La prima stima (61) era troppo bassa. Il conto viene dalla misura del codice
da portare, su `main` del 26/11/2026:
- l'iPhone ha circa 38.400 righe di Swift (di cui 2.700 del catalogo generato, che non si porta a mano) in 270 file, più
  circa 29.000 righe di test;
- ci sono file grandi: `WidgetRiassunto.swift` 1764 righe, `Modelli.swift` 1482, `DatiDemo.swift` 1222,
  `Account.swift` 950, `FormazioneViewModel.swift` 871, `RegoleEditor.swift` 795. Ognuno da solo vale da 2 a 4 PR;
- ogni PR resta sotto le 600 righe che contano (`controlla_ambito.py --dimensione`), ma una PR che porta una schermata
  vuole anche i suoi test, le foto guardate e una revisione: nella pratica 300-400 righe di codice per PR. Circa 36.000
  righe da portare diviso 350 fa già un centinaio di PR, senza contare CI, documenti e chiusure di fase.

**L'effetto sul tempo.** Il progetto unisce in questi giorni dalle 20 alle 40 PR al giorno in tutto, ma su Android lavorano
al massimo tre agenti (tetto dell'area), molti compiti vanno in fila (stessi file: vedi il piano) e ogni PR aspetta una revisione
indipendente. Il ritmo realistico è di 5-8 PR Android al giorno: **da 3 a 5 settimane di lavoro pieno**, circa il doppio di
quanto lasciava pensare la prima stima. La fase 1, la prima che serve agli amici, da sola chiede circa una settimana.
Il collo di bottiglia è la revisione, non la CI. È una stima: si corregge alla fine della fase 1 con il ritmo vero.

**Il costo che resta dopo**: dalla fase 5 ogni modifica visibile si fa su tre lati. Una PR dell'iPhone su una schermata già
portata vuole la sua gemella Android (o un'issue): conviene stimarne il lavoro in più fra il 60 e l'80%.

## 12. Rischi e cosa non si verifica senza un telefono vero
**Rischi**
- **Verifica degli sviluppatori di Google.** Google ha annunciato che, dal 2026 in alcuni paesi e dal 2027 ovunque, anche
  le app installate da APK sui telefoni certificati dovranno venire da sviluppatori verificati, con un percorso per chi
  installa app non verificate. Date, costi e regole per l'Italia **vanno ricontrollati** quando si avvicinano. Se diventa
  obbligatorio serve un account sviluppatore del proprietario (identità, forse una quota): decisione D9.
- **Play Protect** può avvisare o fare un controllo su un'app «sconosciuta». L'app non chiede i permessi che Google
  blocca negli APK (SMS, accessibilità, lettura delle notifiche).
- **Chiave di firma persa**: tutti devono reinstallare (§9.5, punto 3).
- **Ottimizzazione della batteria** di alcuni produttori (Xiaomi, Huawei, Samsung): WorkManager in ritardo, e anche le
  sveglie esatte possono arrivare tardi o non arrivare se il sistema ferma l'app. Rimedi: AlarmManager esatto per i
  promemoria (§6), riprogrammazione dopo il riavvio, una riga della guida d'installazione su come escludere SchieraXI
  dall'ottimizzazione. Quanto funziona si sa solo provando sui telefoni degli amici.
- **L'iPhone è un bersaglio che si muove**: escono diverse PR iOS al giorno (#896, #900, #911). Si porta ogni schermata
  dal `main` del giorno, rileggendo il codice iOS al momento della PR; il registro e la riga `Android:` impediscono che una
  schermata già portata resti indietro.
- **Fedeltà delle foto**: Robolectric e Roborazzi disegnano sulla JVM, vicino al telefono ma non identico (caratteri,
  ombre). L'emulatore è più fedele ma più lento.
- **Glance** ha meno libertà di SwiftUI (niente `ViewThatFits`, poche forme): alcune disposizioni dei widget cambieranno
  di poco. Le parole no.
- **Lavoro**: fra 100 e 120 PR con revisione indipendente, da 3 a 5 settimane (§11). Il collo di bottiglia è la revisione,
  non la CI.
- **PC**: Gradle in locale usa molta memoria; con più agenti si compila in CI o con `--max-workers=2` (§3.7).

**Da provare su un telefono vero** (emulatore e Robolectric non lo provano):
installazione dell'APK (origini sconosciute, avvisi di Play Protect) e aggiornamento sopra la versione di prima;
promemoria in Doze, dopo un riavvio e con l'ottimizzazione della batteria del produttore, su Android 12, 13 e 14 (permessi
delle sveglie esatte diversi);
widget sui lanciatori veri (Pixel, One UI, MIUI) con misure, ridimensionamento, tema scuro, testo grande e conto alla
rovescia a schermo acceso; ritorno dall'accesso con Google nella Custom Tab; file delle rose aperti da File, Gmail e
WhatsApp (tipi MIME dell'Excel, indirizzi `content://`); Photo Picker; tocco su un avviso ntfy; TalkBack letto davvero;
navigazione a gesti e a tre pulsanti; pieghevoli; velocità su un telefono economico.
Facoltativo e gratuito: Firebase Test Lab, con una piccola quota giornaliera su telefoni veri (va verificata), fa girare i
test e le foto su apparecchi veri senza comprarne uno (D7).

## 13. Decisioni chieste al proprietario (dettagli tecnici)
La versione in parole semplici è in testa al documento.
- **D1** Kotlin + Jetpack Compose (consigliato).
- **D2** `minSdk 26`, da confermare chiedendo agli amici la versione di Android (Impostazioni › Info sul telefono ›
  Versione Android; il percorso cambia un po' da marca a marca).
- **D3** Avvisi come l'iPhone (promemoria locali con `USE_EXACT_ALARM`); UnifiedPush no per ora (consigliato no).
- **D4** Aggiornamento con avviso da `android-ultima/versione.json` e scaricamento dal browser (consigliato); al massimo un
  APK al giorno più quelli chiesti a mano; Obtainium da proporre agli amici sì o no; installatore dentro l'app no.
- **D5** Le differenze ammesse del §3.8, voci 1-10, compresi i suggerimenti di TipKit solo sull'iPhone.
- **D6** Il documento della coerenza tiene il nome di oggi (consigliato) o diventa `docs/COERENZA.md`.
- **D7** Firebase Test Lab gratuito per qualche prova su telefoni veri: sì o no.
- **D8** App Link https verificato per il ritorno da Google (serve un file sul server): più avanti, sì o no.
- **D9** Account sviluppatore Google, quando la verifica sarà obbligatoria in Italia.
- **D10** Gestione (righe 46-48 del §10) solo su web e iPhone: §3.8 voce 11. Da decidere; proposta sì.
- **D11** Tablet e tastiera fisica (righe 56-57) senza impaginazione propria su Android: §3.8 voce 12. Da decidere;
  proposta sì.

## 14. Fuori da questa spec
Play Store; l'app in inglese (l'iPhone è solo in italiano); funzioni che l'iPhone non ha; avvisi push del server su
Android (D3); installatore dentro l'app.
