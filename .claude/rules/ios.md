---
paths:
  - "ios/**"
---
# App per iPhone e iPad (`ios/`)

- **Non c'è un Mac.** L'app si compila, si prova e si fotografa solo su GitHub Actions, e i Mac gratuiti sono pochi (5 job
  in tutto): raggruppa le modifiche, controlla a mente le API rispetto alla versione minima di iOS, e leggi gli errori con
  `gh run view <id> --log-failed`. Se sull'ultimo commit del ramo c'è già una corsa, annulla quelle vecchie (`gh run cancel`).
- **Provare un ramo.** In bozza il job `ios / test` è saltato: `gh workflow run ios.yml --ref <ramo>` (`-f parte=unitari`
  prova solo i test unitari, circa 10 minuti). `ios / gia-verde` salta il test quando lo stesso codice è già passato da
  poco: è giusto così.
- **File fuori da `ios/`.** Un test Swift che legge un file del resto del repository lo elenca in
  `ios/Tests/file-esterni.txt`, altrimenti `tests/test_ios_file_esterni.py` è rosso.
- **Progetto.** Si genera da `ios/project.yml` (XcodeGen), mai un `.xcodeproj` a mano. Identificativo dell'app, nome
  dell'IPA, schema degli indirizzi e identificativi dei lavori in background non si cambiano: rompono l'installazione con
  SideStore. `project.yml` e gli altri file comuni (client API, formati, colori) li cambia una pull request alla volta.
- **Apple ID gratuito.** Niente notifiche push di Apple; widget, gruppo condiviso e portachiavi come spiega la skill
  `widget-ios`.
- **Dal server.** Numeri, stati, etichette e frasi arrivano dal server e si mostrano: non si ricalcolano. I testi fissi
  vengono dal catalogo (`ios/testi/<prefisso>.txt` elenca le chiavi usate; `python script/testi.py --scrivi` rigenera
  `ios/Sources/Support/Catalogo/`).
- **Codice.** Niente `!` forzati né `try!`; modelli `Decodable` con campi facoltativi; testo grande, modo scuro, VoiceOver,
  Riduci movimento; iPad con le sue colonne, non il telefono allargato.
- **Foto.** Non lanciare `screenshot.yml`: scrivi nella pull request «Foto da fare: <schermate>»
  (`python script/squadra/squadra.py foto <PR>` le ricava dai file cambiati). Le scatta chi coordina su `main` dopo
  l'unione e ogni difetto visto diventa un'issue. Solo una schermata nuova o rifatta si fotografa sul ramo prima dell'unione.
- Nella pull request scrivi anche cosa va provato sul telefono vero (ciò che il simulatore non vede).
