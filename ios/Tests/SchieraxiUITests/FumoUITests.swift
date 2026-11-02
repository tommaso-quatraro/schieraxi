import XCTest

/// Test di fumo dell'interfaccia: l'app parte in modalità demo (dati finti, senza rete, tutte le funzioni accese), le quattro sezioni si raggiungono
/// e le schermate principali mostrano il testo atteso. Si cerca per testo (etichetta di accessibilità), non per posizione.
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

    private func vaiA(_ sezione: String) {
        let barra = app.tabBars.firstMatch
        XCTAssertTrue(barra.waitForExistence(timeout: 30), "la barra delle sezioni deve comparire")
        barra.buttons[sezione].firstMatch.tap()   // con iOS 26 la barra a volte espone due elementi per la stessa scheda
    }

    func testLeQuattroSezioniSonoRaggiungibili() {
        let barra = app.tabBars.firstMatch
        XCTAssertTrue(barra.waitForExistence(timeout: 30), "la barra delle sezioni deve comparire")
        for nome in ["Oggi", "Formazione", "Squadra", "Altro"] {
            XCTAssertTrue(barra.buttons[nome].exists, "manca la sezione \(nome)")
        }
    }

    func testOggiMostraLaGiornataELaFormazione() {
        attendi("La tua scelta")
        attendi("Da controllare")
        attendi("Apri la formazione")
        attendi("punti attesi", contiene: true)
        XCTAssertTrue(app.navigationBars["Oggi"].exists)
    }

    func testFormazioneConCampoEModificaAMano() {
        vaiA("Formazione")
        attendi("Campo")
        attendi("Modulo proposto", contiene: true)
        attendi("Panchina")
        let modifica = app.buttons["Modifica a mano"]
        XCTAssertTrue(modifica.waitForExistence(timeout: 20), "il pulsante «Modifica a mano» deve esserci")
        modifica.tap()
        attendi("Salva come mia scelta")
        attendi("Torna alla consigliata")
        app.buttons["Torna alla consigliata"].tap()
        XCTAssertTrue(app.buttons["Modifica a mano"].waitForExistence(timeout: 20), "tornando alla consigliata ricompare «Modifica a mano»")
    }

    func testSquadraConLeSuePagine() {
        vaiA("Squadra")
        attendi("Aggiorna le rose")
        for voce in ["Aggiorna le rose", "Squadre e rose", "Cambi consigliati", "Seguiti", "Elenco dei giocatori", "Calendario"] {
            attendiScorrendo(voce, contiene: true)
        }
        XCTAssertFalse(elemento("Asta e riparazione", contiene: true).exists, "l'asta sta in Altro")
        elemento("Cambi consigliati", contiene: true).tap()
        attendi("Svincolati che migliorano la squadra")
    }

    func testElencoDeiGiocatoriDentroSquadra() {
        vaiA("Squadra")
        attendiScorrendo("Elenco dei giocatori", contiene: true)
        elemento("Elenco dei giocatori", contiene: true).tap()
        attendi("Solo svincolati")
    }

    func testScambiConOffertaEAnalisi() {
        vaiA("Altro")
        attendi("Scambi", contiene: true)
        elemento("Scambi", contiene: true).tap()
        XCTAssertTrue(app.buttons["Cerca scambi"].waitForExistence(timeout: 20), "le proposte si cercano con il pulsante")
        for modo in ["Trova per me", "Costruisci", "Valuta un'offerta"] {
            XCTAssertTrue(app.buttons[modo].waitForExistence(timeout: 10), "manca il modo «\(modo)»")
        }
        attendi("Chi accetta più volentieri")
        app.buttons["Valuta un'offerta"].tap()
        attendi("Ho ricevuto un'offerta")
        app.buttons["Costruisci"].tap()
        attendi("Squadra")
    }

    func testAltroConLeSuePagine() {
        vaiA("Altro")
        attendi("Scambi", contiene: true)
        for voce in ["Scambi", "Movimenti e storico", "Asta e riparazione", "Regole", "Diario delle giornate", "Novità"] {
            attendiScorrendo(voce, contiene: true)
        }
        // ogni voce in un posto solo: niente copia di sicurezza, niente rimando alle Impostazioni (c'è l'ingranaggio)
        XCTAssertFalse(elemento("Copia di sicurezza", contiene: true).exists)
        XCTAssertFalse(elemento("Impostazioni dell'app e dell'account").exists)
    }

    func testImpostazioniDallIngranaggio() {
        vaiA("Altro")
        let ingranaggio = app.buttons["Impostazioni"]
        XCTAssertTrue(ingranaggio.waitForExistence(timeout: 20), "l'ingranaggio sta accanto alla lente")
        ingranaggio.tap()
        attendi("Aspetto")
        attendi("Avvisi e promemoria")
        // le voci tolte non ci sono più
        for tolta in ["Icona dell'app", "Sotto il cofano", "Copia di sicurezza", "Configurazione guidata", "Copia il codice per il widget"] {
            XCTAssertFalse(elemento(tolta, contiene: true).exists, "«\(tolta)» non deve stare nelle Impostazioni")
        }
        elemento("Aspetto").tap()
        attendi("Automatico")
        attendiScorrendo("Animazioni ridotte", contiene: true)
        XCTAssertFalse(elemento("Colore principale").exists, "l'aspetto ha solo tema e animazioni")
    }

    func testSchedaDiUnGiocatoreSiApreEDiChiude() {
        // un tocco su una riga di Oggi apre la scheda (foglio) con la previsione, la forma e il grafico dei voti
        let riga = app.buttons.matching(NSPredicate(format: "label CONTAINS 'fantavoto atteso'")).firstMatch
        XCTAssertTrue(riga.waitForExistence(timeout: 30), "serve almeno una riga di giocatore in Oggi")
        riga.tap()
        attendi("Prossima partita")
        attendi("Forma")
        let chiudi = app.buttons["Chiudi"]
        XCTAssertTrue(chiudi.waitForExistence(timeout: 10))
        chiudi.tap()
        XCTAssertTrue(app.tabBars.firstMatch.waitForExistence(timeout: 10))
    }

    func testUnCsvDelleRoseSiImportaDaUnAltraApp() {
        // la demo scrive un CSV vero (separatore «;») e lo importa come se arrivasse da «Apri con SchieraXI»
        app.terminate()
        app.launchArguments += ["-DEMO_SCHERMATA", "lega-importa-csv"]
        app.launch()
        // prima l'anteprima (niente si salva), poi «Conferma e salva»
        attendi("Controlla prima di salvare")
        XCTAssertFalse(elemento("Usa un Excel (.xlsx), un CSV o un file di testo.").exists, "il CSV non deve essere rifiutato")
        let conferma = app.buttons["Conferma e salva"]
        for _ in 0..<8 where !conferma.isHittable { app.swipeUp() }
        conferma.tap()
        attendi("Rose salvate", contiene: true)
    }

    func testLaLenteApreLaRicerca() {
        let lente = app.buttons["Cerca un giocatore"]
        XCTAssertTrue(lente.waitForExistence(timeout: 30), "la lente della ricerca deve esserci in Oggi")
        lente.tap()
        attendi("Scrivi almeno due lettere del nome.")
    }
}
