import XCTest

/// La schermata di accesso e il resto dell'account, con l'app in modalità demo (`-DEMO_ACCESSO <scenario>`): server finto, nessuna rete.
final class AccessoUITests: XCTestCase {
    private var app: XCUIApplication!

    private func avvia(_ scenario: String, altri: [String] = []) {
        continueAfterFailure = false
        app = XCUIApplication()
        app.launchArguments += ["-DEMO", "-DEMO_ACCESSO", scenario, "-AppleLanguages", "(it)", "-AppleLocale", "it_IT"] + altri
        app.launch()
    }

    private func elemento(_ testo: String, contiene: Bool = false) -> XCUIElement {
        let predicato = NSPredicate(format: contiene ? "label CONTAINS[c] %@" : "label ==[c] %@", testo)
        return app.descendants(matching: .any).matching(predicato).firstMatch
    }

    private func attendi(_ testo: String, contiene: Bool = false, secondi: TimeInterval = 30, file: StaticString = #filePath, line: UInt = #line) {
        XCTAssertTrue(elemento(testo, contiene: contiene).waitForExistence(timeout: secondi), "non compare «\(testo)»", file: file, line: line)
    }

    /// Tocca il pulsante `tocco` e aspetta il pulsante `atteso` della schermata d'arrivo. Sul simulatore carico di GitHub un tocco
    /// a volte non arriva all'app (successo il 1/11/2026: dopo «Accedi» la scheda selezionata era ancora «Registrati»):invece di
    /// toccare subito il pulsante dopo, si controlla l'effetto e, se manca, si ritocca (al massimo 3 volte, solo se il pulsante c'è ancora).
    private func tocca(_ tocco: String, finchéCompare atteso: String, file: StaticString = #filePath, line: UInt = #line) {
        let pulsante = app.buttons[tocco]
        XCTAssertTrue(pulsante.waitForExistence(timeout: 10), "manca il pulsante «\(tocco)»", file: file, line: line)
        var arrivato = false
        for _ in 0..<3 where !arrivato {
            if pulsante.exists { pulsante.tap() }
            arrivato = app.buttons[atteso].waitForExistence(timeout: 10)
        }
        XCTAssertTrue(arrivato, "dopo «\(tocco)» non compare «\(atteso)»", file: file, line: line)
    }

    func testAccessoConNomePasswordEPassaggioTraLeSchede() {
        avvia("accedi")
        let nome = app.textFields["Nome utente"]
        XCTAssertTrue(nome.waitForExistence(timeout: 30), "la schermata di accesso deve comparire")
        XCTAssertTrue(app.secureTextFields["Password"].exists)
        XCTAssertFalse(app.tabBars.firstMatch.exists, "senza accesso non si vede l'app")
        let entra = app.buttons["Entra"]
        XCTAssertTrue(entra.exists)
        XCTAssertFalse(entra.isEnabled, "con i campi vuoti non si può entrare")

        // Registrati: compare il codice d'invito (il server non si vede: è nascosto nell'area avanzata)
        tocca("Registrati", finchéCompare: "Crea l'account")
        attendi("Codice d'invito", contiene: true)
        // Recupera: compare il codice di recupero (prima si torna su Accedi e si aspetta che ci sia davvero)
        tocca("Accedi", finchéCompare: "Password dimenticata?")
        tocca("Password dimenticata?", finchéCompare: "Cambia la password")
        XCTAssertTrue(app.textFields["Codice di recupero"].waitForExistence(timeout: 10))

        // di nuovo Accedi, con nome e password: si entra
        tocca("Accedi", finchéCompare: "Entra")
        nome.tap()
        nome.typeText("mister.rossi")
        let password = app.secureTextFields["Password"]
        password.tap()
        password.typeText("Prova-Finta-Zero")
        XCTAssertTrue(entra.isEnabled)
        entra.tap()
        XCTAssertTrue(app.tabBars.firstMatch.waitForExistence(timeout: 30), "dopo l'accesso compare l'app")
    }

    func testCodiceDiRecuperoSiVedeEsiConfermaPrimaDiProseguire() {
        avvia("codice")
        attendi("Salva il tuo codice di recupero")
        attendi("K 7 M 2 P", contiene: true)   // per VoiceOver il codice si legge lettera per lettera
        let continua = app.buttons["Continua"]
        XCTAssertTrue(continua.waitForExistence(timeout: 10))
        XCTAssertFalse(continua.isEnabled, "senza la conferma «l'ho salvato» non si va avanti")
        XCTAssertTrue(app.buttons["Copia"].exists)
        let conferma = app.switches.firstMatch
        XCTAssertTrue(conferma.waitForExistence(timeout: 10))
        // Il tocco sull'interruttore a volte non arriva al primo colpo nel simulatore: si tocca la levetta (a destra) e si
        // riprova finché il pulsante si accende (al massimo tre volte, sempre con attesa).
        var acceso = false
        for _ in 0..<3 where !acceso {
            if (conferma.value as? String) != "1" { conferma.coordinate(withNormalizedOffset: CGVector(dx: 0.92, dy: 0.5)).tap() }
            acceso = XCTWaiter().wait(for: [expectation(for: NSPredicate(format: "isEnabled == true"), evaluatedWith: continua)], timeout: 5) == .completed
        }
        XCTAssertTrue(acceso, "dopo la conferma il pulsante Continua si accende")
        continua.tap()
        XCTAssertTrue(app.tabBars.firstMatch.waitForExistence(timeout: 30))
    }

    func testSezioneIlTuoAccountInLega() {
        avvia("account")
        attendi("Il tuo account")
        attendi("mister.rossi")
        attendi("Cambia password")
        attendi("Nuovo codice per recuperare l'accesso")
        attendi("Elimina l'account")
        // un solo nome e niente voci tolte (maiuscole del nome, esci da tutti i telefoni)
        XCTAssertFalse(elemento("Per accedere").exists)
        XCTAssertFalse(elemento("Cambia le maiuscole del nome").exists)
        XCTAssertFalse(elemento("Esci da tutti", contiene: true).exists)
        // «Esci» è l'ultima voce delle Impostazioni: si scorre fino in fondo
        let esci = app.buttons["Esci"]
        for _ in 0..<8 where !esci.exists { app.swipeUp() }
        XCTAssertTrue(esci.waitForExistence(timeout: 5))
    }

    /// Apre un foglio dell'account toccando `voce` e aspetta `segno` (un elemento del foglio). Il tocco perso sul simulatore
    /// carico si ripete (al massimo 3 volte, solo se la voce c'è ancora).
    private func apriFoglio(_ voce: XCUIElement, segno: XCUIElement, file: StaticString = #filePath, line: UInt = #line) {
        XCTAssertTrue(voce.waitForExistence(timeout: 30), "manca la voce del foglio", file: file, line: line)
        var aperto = false
        for _ in 0..<3 where !aperto {
            if voce.exists {
                if !voce.isHittable { app.swipeUp() }   // voce sotto il bordo (iPhone piccolo, testo grande)
                voce.tap()
            }
            aperto = segno.waitForExistence(timeout: 10)
        }
        XCTAssertTrue(aperto, "il foglio non si apre", file: file, line: line)
    }

    /// Mentre il foglio è aperto arrivano dati nuovi dell'account (in demo ogni mezzo secondo): deve restare aperto.
    private func restaAperto(_ segno: XCUIElement, _ nome: String, file: StaticString = #filePath, line: UInt = #line) {
        XCTAssertFalse(segno.waitForNonExistence(timeout: 4), "il foglio «\(nome)» si è chiuso da solo", file: file, line: line)
    }

    /// Chiude il foglio con il pulsante della sua barra (`titolo`): sotto c'è la barra delle Impostazioni con un altro «Chiudi».
    private func chiudiFoglio(_ titolo: String, _ pulsante: String, segno: XCUIElement, file: StaticString = #filePath, line: UInt = #line) {
        let b = app.navigationBars[titolo].buttons[pulsante]
        XCTAssertTrue(b.waitForExistence(timeout: 10), "manca «\(pulsante)»", file: file, line: line)
        b.tap()
        XCTAssertTrue(segno.waitForNonExistence(timeout: 10), "il foglio non si chiude con «\(pulsante)»", file: file, line: line)
    }

    /// Build 219: «Cambia password» si apriva e si chiudeva subito da solo. Con i dati dell'account che cambiano di continuo
    /// (`-DEMO_ACCOUNT_CHE_CAMBIA`) ogni foglio dell'account deve restare aperto e non perdere quello che si scrive.
    func testFogliDellAccountRestanoApertiQuandoArrivanoDatiNuovi() {
        avvia("account", altri: ["-DEMO_ACCOUNT_CHE_CAMBIA", "1"])
        attendi("Il tuo account")

        // Cambia password: si apre, resta aperto, il testo scritto resta
        let attuale = app.secureTextFields["Password attuale"]
        apriFoglio(app.buttons["Cambia password"], segno: attuale)
        restaAperto(attuale, "Cambia password")
        attuale.tap()
        attuale.typeText("vecchia-prova-1")
        restaAperto(attuale, "Cambia password")
        XCTAssertFalse((attuale.value as? String ?? "").isEmpty, "la password scritta non deve sparire")
        XCTAssertTrue(app.secureTextFields["Nuova password"].exists)
        chiudiFoglio("Cambia password", "Annulla", segno: attuale)

        // Nuovo codice di recupero
        let codice = app.navigationBars["Codice di recupero"]
        apriFoglio(app.buttons["Nuovo codice per recuperare l'accesso"], segno: codice)
        restaAperto(codice, "Codice di recupero")
        chiudiFoglio("Codice di recupero", "Annulla", segno: codice)

        // Email (la voce cambia nome mentre l'email va e viene)
        let email = app.navigationBars["Email dell'account"]
        let voceEmail = app.buttons.matching(NSPredicate(format: "label IN %@", ["Aggiungi un'email", "Gestisci l'email"])).firstMatch
        apriFoglio(voceEmail, segno: email)
        restaAperto(email, "Email dell'account")
        chiudiFoglio("Email dell'account", "Chiudi", segno: email)

        // Elimina l'account
        let elimina = app.navigationBars["Elimina l'account"]
        apriFoglio(app.buttons["Elimina l'account"].firstMatch, segno: elimina)
        restaAperto(elimina, "Elimina l'account")
        chiudiFoglio("Elimina l'account", "Annulla", segno: elimina)
    }

    func testRetAssenteDiceCosaFare() {
        avvia("rete")
        attendi("Non riesco a collegarmi a SchieraXI", contiene: true)
        XCTAssertTrue(app.buttons["Entra"].waitForExistence(timeout: 10), "si può riprovare")
        XCTAssertFalse(app.tabBars.firstMatch.exists)
    }

    func testTroppiTentativiMostraIlContoAllaRovescia() {
        avvia("limite")
        attendi("Troppi tentativi", contiene: true)
        let conto = app.buttons.matching(NSPredicate(format: "label BEGINSWITH 'Riprova tra'")).firstMatch
        XCTAssertTrue(conto.waitForExistence(timeout: 10))
        XCTAssertFalse(conto.isEnabled, "durante l'attesa non si riprova")
    }

    func testServerCheNonESchieraxi() {
        avvia("non-valido")
        attendi("non sembra un server di SchieraXI", contiene: true)
        XCTAssertFalse(app.tabBars.firstMatch.exists)
    }

    func testCambioRapidoTraLeSchedeNonRompeNiente() {
        avvia("accedi")
        XCTAssertTrue(app.textFields["Nome utente"].waitForExistence(timeout: 30))
        // Ogni cambio aspetta che compaia il pulsante della scheda d'arrivo prima del successivo: niente attese fisse.
        // Il pulsante si cerca ogni volta, così un tocco su una schermata che si sta ancora montando non resta appeso.
        let arrivi: [(tocco: String, atteso: String)] = [
            ("Registrati", "Crea l'account"),
            ("Accedi", "Entra"),
            ("Password dimenticata?", "Cambia la password"),
            ("Accedi", "Entra"),
        ]
        for giro in 1...6 {
            for passo in arrivi {
                XCTContext.runActivity(named: "giro \(giro): \(passo.tocco)") { _ in tocca(passo.tocco, finchéCompare: passo.atteso) }
            }
        }
        // Con i tocchi a raffica sul Mac di GitHub un tocco può perdersi: si rimette «Accedi» finché il pulsante «Entra» compare.
        var tornata = false
        for _ in 0..<6 where !tornata {
            if app.buttons["Entra"].waitForExistence(timeout: 8) { tornata = true; break }
            app.buttons["Accedi"].tap()
        }
        XCTAssertTrue(tornata, "dopo i cambi rapidi la scheda Accedi deve tornare")
        XCTAssertTrue(app.secureTextFields["Password"].waitForExistence(timeout: 20))
    }

    func testInSecondoPianoLaPasswordScrittaSiCancella() {
        avvia("accedi")
        let password = app.secureTextFields["Password"]
        XCTAssertTrue(password.waitForExistence(timeout: 30))
        password.tap()
        password.typeText("Prova-Finta-Zero")
        XCUIDevice.shared.press(.home)
        sleep(2)
        app.activate()
        XCTAssertTrue(password.waitForExistence(timeout: 10))
        XCTAssertFalse((password.value as? String ?? "").contains("•"), "tornando nell'app la password non c'è più")
    }

    func testLegaSenzaRoseSpiegaCosaFare() {
        avvia("rose")
        attendi("Manca la tua squadra")
        XCTAssertTrue(app.buttons["Importa le rose"].waitForExistence(timeout: 10))
        XCTAssertTrue(app.buttons["Apri la web app nel browser"].exists)
    }
}
