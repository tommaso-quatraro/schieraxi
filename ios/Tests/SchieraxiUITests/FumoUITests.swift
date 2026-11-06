import XCTest

/// Test di fumo dell'interfaccia: l'app parte in modalità demo (dati finti, senza rete, tutte le funzioni accese), le quattro sezioni si raggiungono
/// e le schermate principali mostrano il testo atteso. Si cerca per testo (etichetta di accessibilità), non per posizione.
/// Ogni tocco che apre qualcosa passa da `tocca(_:finchéCompare:_:)` (Tocchi.swift): se il tocco si perde, si ritocca (#212).
final class FumoUITests: XCTestCase {
    private var app: XCUIApplication!

    override func setUpWithError() throws {
        continueAfterFailure = false
        app = XCUIApplication()
        app.launchArguments += ["-DEMO", "-AppleLanguages", "(it)", "-AppleLocale", "it_IT"]
        app.launch()
    }

    /// Un elemento qualsiasi (testo, pulsante, riga) con quell'etichetta, anche solo contenuta.
    private func elemento(_ testo: String, contiene: Bool = false) -> XCUIElement {
        let predicato = NSPredicate(format: contiene ? "label CONTAINS[c] %@" : "label ==[c] %@", testo)
        return app.descendants(matching: .any).matching(predicato).firstMatch
    }

    private func attendi(_ testo: String, contiene: Bool = false, secondi: TimeInterval = 20, file: StaticString = #filePath, line: UInt = #line) {
        XCTAssertTrue(elemento(testo, contiene: contiene).waitForExistence(timeout: secondi), "non compare «\(testo)»", file: file, line: line)
    }

    /// Per le liste: le righe fuori dallo schermo non esistono ancora, quindi si scorre finché compare l'elemento.
    private func attendiScorrendo(_ testo: String, contiene: Bool = false, file: StaticString = #filePath, line: UInt = #line) {
        for _ in 0..<12 {
            if elemento(testo, contiene: contiene).waitForExistence(timeout: 2) { return }
            app.swipeUp()
        }
        XCTFail("non compare «\(testo)» nemmeno scorrendo", file: file, line: line)
    }

    /// Apre una sezione dalla barra in basso: è aperta quando c'è la sua barra del titolo.
    private func vaiA(_ sezione: String, file: StaticString = #filePath, line: UInt = #line) {
        let barra = app.tabBars.firstMatch
        XCTAssertTrue(barra.waitForExistence(timeout: 30), "la barra delle sezioni deve comparire", file: file, line: line)
        // con iOS 26 la barra a volte espone due elementi per la stessa scheda
        tocca(barra.buttons[sezione].firstMatch, finchéCompare: app.navigationBars[sezione], "la sezione «\(sezione)» non si apre",
              file: file, line: line)
    }

    func testLeQuattroSezioniSonoRaggiungibili() {
        let barra = app.tabBars.firstMatch
        XCTAssertTrue(barra.waitForExistence(timeout: 30), "la barra delle sezioni deve comparire")
        for nome in ["Oggi", "Formazione", "Squadra", "Altro"] {
            XCTAssertTrue(barra.buttons[nome].exists, "manca la sezione \(nome)")
        }
    }

    func testOggiMostraLaGiornataELaFormazione() {
        // il titolo della web (oggi.tua_formazione, #416): la demo mostra la consigliata non salvata, come la Formazione (#418)
        attendi("La tua formazione")
        attendi("Da controllare")
        attendi("Apri la formazione")
        attendi("punti attesi", contiene: true)
        XCTAssertTrue(app.navigationBars["Oggi"].exists)
    }

    func testFormazioneConCampoEModificaAMano() {
        vaiA("Formazione")
        attendi("Campo")
        attendi("Propone il", contiene: true)   // la frase dello stile della web (formazione.propone, #437)
        attendi("Panchina")
        tocca(app.buttons["Modifica a mano"], finchéCompare: app.buttons["Torna alla consigliata"], "«Modifica a mano» apre la modifica")
        attendi("Salva come mia scelta")
        tocca(app.buttons["Torna alla consigliata"], finchéCompare: app.buttons["Modifica a mano"],
              "tornando alla consigliata ricompare «Modifica a mano»")
    }

    func testSquadraConLeSuePagine() {
        vaiA("Squadra")
        attendi("Squadre e rose", contiene: true)
        // le voci e l'ordine della web (VOCI_LEGA): «Aggiorna le rose» per ultima
        for voce in ["Squadre e rose", "Cambi consigliati", "Seguiti", "Elenco dei giocatori", "Calendario", "Aggiorna le rose"] {
            attendiScorrendo(voce, contiene: true)
        }
        tocca(elemento("Cambi consigliati", contiene: true), finchéCompare: elemento("Svincolati che migliorano la squadra"),
              "«Cambi consigliati» apre i cambi")
    }

    func testElencoDeiGiocatoriDentroSquadra() {
        vaiA("Squadra")
        attendiScorrendo("Elenco dei giocatori", contiene: true)
        tocca(elemento("Elenco dei giocatori", contiene: true), finchéCompare: elemento("Solo svincolati"), "«Elenco dei giocatori» apre l'elenco")
    }

    func testScambiConOffertaEAnalisi() {
        vaiA("Altro")
        tocca(elemento("Scambi", contiene: true), finchéCompare: app.buttons["Cerca scambi"], "le proposte si cercano con il pulsante")
        for modo in ["Trova per me", "Costruisci", "Valuta un'offerta"] {
            XCTAssertTrue(app.buttons[modo].waitForExistence(timeout: 10), "manca il modo «\(modo)»")
        }
        attendi("Chi accetta più volentieri")
        // il titolo del riquadro («Valuta un'offerta») è anche il nome del pulsante del modo: si aspetta la frase che lo spiega (testi.js)
        tocca(app.buttons["Valuta un'offerta"], finchéCompare: elemento("Incolla il messaggio che hai ricevuto", contiene: true), "«Valuta un'offerta» mostra il riquadro dell'offerta")
        // «Costruisci»: le due rose da cui scegliere («Dai   0 su 4»; prima si aspettava «Squadra», che c'è sempre nella barra in basso)
        tocca(app.buttons["Costruisci"], finchéCompare: elemento("0 su 4", contiene: true), "«Costruisci» mostra la tua rosa da cui scegliere")
    }

    /// Il rimedio di #212 funziona davvero: il primo tocco su «Scambi» si perde (non lo si manda all'app) e `tocca` deve
    /// accorgersene e ritoccare finché compare «Cerca scambi». Senza il nuovo tocco questo test fallisce.
    func testUnToccoPersoSiRitocca() {
        vaiA("Altro")
        var tocchi = 0
        tocca(elemento("Scambi", contiene: true), finchéCompare: app.buttons["Cerca scambi"], "dopo un tocco perso si ritocca",
              entro: 5, tap: { riga in
                  tocchi += 1
                  if tocchi > 1 { riga.tap() }   // il primo tocco «si perde»
              })
        XCTAssertGreaterThanOrEqual(tocchi, 2, "un tocco perso e almeno uno arrivato")
    }

    func testAltroConLeSuePagine() {
        vaiA("Altro")
        attendi("Scambi", contiene: true)
        // le voci della web (VOCI_LEGA), «Nuova stagione» compresa
        for voce in ["Scambi", "Diario delle giornate", "Regole", "Movimenti e storico", "Crediti delle squadre", "Nuova stagione", "Novità"] {
            attendiScorrendo(voce, contiene: true)
        }
        // ogni voce in un posto solo: niente copia di sicurezza, niente rimando alle Impostazioni (c'è l'ingranaggio)
        XCTAssertFalse(elemento("Copia di sicurezza", contiene: true).exists)
        XCTAssertFalse(elemento("Impostazioni dell'app e dell'account").exists)
    }

    func testImpostazioniDallIngranaggio() {
        vaiA("Altro")
        // l'ingranaggio sta accanto alla lente
        tocca(app.buttons["Impostazioni"], finchéCompare: elemento("Aspetto"), "l'ingranaggio apre le Impostazioni")
        attendi("Notifiche", contiene: true)
        // le voci tolte non ci sono più
        for tolta in ["Icona dell'app", "Sotto il cofano", "Copia di sicurezza", "Configurazione guidata", "Copia il codice per il widget"] {
            XCTAssertFalse(elemento(tolta, contiene: true).exists, "«\(tolta)» non deve stare nelle Impostazioni")
        }
        tocca(elemento("Aspetto"), finchéCompare: elemento("Automatico"), "«Aspetto» apre tema e animazioni")
        attendiScorrendo("Animazioni ridotte", contiene: true)
        XCTAssertFalse(elemento("Colore principale").exists, "l'aspetto ha solo tema e animazioni")
    }

    func testSchedaDiUnGiocatoreSiApreEDiChiude() {
        // un tocco su una riga di Oggi apre la scheda (foglio) con la previsione, la forma e il grafico dei voti
        let riga = app.buttons.matching(NSPredicate(format: "label CONTAINS 'fantavoto atteso'")).firstMatch
        XCTAssertTrue(riga.waitForExistence(timeout: 30), "serve almeno una riga di giocatore in Oggi")
        tocca(riga, finchéCompare: elemento("Prossima partita"), "un tocco sulla riga apre la scheda del giocatore")
        attendi("Forma")
        let chiudi = app.buttons["Chiudi"]
        XCTAssertTrue(chiudi.waitForExistence(timeout: 10))
        chiudi.tap()
        XCTAssertTrue(app.tabBars.firstMatch.waitForExistence(timeout: 10))
    }

    /// Riapre la demo direttamente su una schermata (`-DEMO_SCHERMATA`).
    private func apriDemo(_ schermata: String) {
        app.terminate()
        app.launchArguments += ["-DEMO_SCHERMATA", schermata]
        app.launch()
    }

    func testUnCsvDelleRoseSiImportaDaUnAltraApp() {
        // la demo scrive un CSV vero (separatore «;») e lo importa come se arrivasse da «Apri con SchieraXI»
        apriDemo("lega-importa-csv")
        // prima l'anteprima (niente si salva), poi «Conferma e salva»
        attendi("Controlla prima di salvare")
        XCTAssertFalse(elemento("Usa un Excel (.xlsx), un CSV o un file di testo.").exists, "il CSV non deve essere rifiutato")
        let conferma = app.buttons["Conferma e salva"]
        for _ in 0..<8 where !conferma.isHittable { app.swipeUp() }
        // l'esito come la web: «Cosa è cambiato», le squadre importate, poi «Da controllare:» con gli avvisi del server
        tocca(conferma, finchéCompare: elemento("Rose salvate", contiene: true), "«Conferma e salva» salva le rose", entro: 20)
        attendi("Cosa è cambiato")
        attendiScorrendo("Importate:", contiene: true)
        attendiScorrendo("Da controllare:")
        attendiScorrendo("24 giocatori invece di 25", contiene: true)
    }

    func testLEsitoConAvvisiDiceCosaControllare() {
        apriDemo("lega-importa-salvate")
        attendi("Rose salvate", contiene: true)
        XCTAssertFalse(elemento("La tua squadra:", contiene: true).exists, "come la web: l'esito non ripete la propria squadra")
        attendiScorrendo("Da controllare:")
        attendiScorrendo("«Bastrini» non è nel listone", contiene: true)
        XCTAssertFalse(elemento("tutto in ordine", contiene: true).exists, "con degli avvisi non si dice «tutto in ordine»")
    }

    func testLEsitoSenzaAvvisiDiceTuttoInOrdine() {
        apriDemo("lega-importa-salvate-ok")
        attendi("Rose salvate", contiene: true)
        attendiScorrendo("Rose controllate: tutto in ordine.", contiene: true)
        XCTAssertFalse(elemento("Da controllare", contiene: true).exists, "senza avvisi non c'è niente da controllare")
    }

    func testIlCollegamentoDelWidgetAspettaUnTocco() {
        // `schieraxi://widget/collega` lo può aprire qualsiasi app o pagina e apre questa schermata (`Navigazione.vai`, lo stesso
        // `collegaWidgetAperto` della demo): si apre solo la schermata, il collegamento e la copia del codice negli appunti partono
        // dal tocco su «Collega» (#482). La demo apre la schermata dall'argomento di lancio, senza `XCUIApplication.open`, che sul
        // simulatore a volte non consegna l'indirizzo all'app.
        apriDemo("collega-widget")
        attendi("Collega il widget")
        XCTAssertFalse(elemento("Codice copiato").exists, "senza un tocco il codice non si copia")
        // in demo il tocco dice «Codice copiato» senza toccare gli appunti veri
        tocca(app.buttons["Collega"].firstMatch, finchéCompare: elemento("Codice copiato"), "il tocco su «Collega» collega il widget")
    }

    func testLaLenteApreLaRicerca() {
        let lente = app.buttons["Cerca un giocatore"]
        XCTAssertTrue(lente.waitForExistence(timeout: 30), "la lente della ricerca deve esserci in Oggi")
        tocca(lente, finchéCompare: elemento("Scrivi almeno due lettere del nome."), "la lente apre la ricerca")
    }
}
