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
        // «Accedi» è sia la scheda sia il pulsante del modulo (come sulla web): si distinguono per identificativo
        let entra = app.buttons["accesso-invia"]
        XCTAssertTrue(entra.exists)
        XCTAssertEqual(entra.label, "Accedi")
        XCTAssertFalse(entra.isEnabled, "con i campi vuoti non si può entrare")
        XCTAssertFalse(elemento("Bentornato", contiene: true).exists, "niente frasi che la web non ha")

        // Registrati: compare il codice d'invito, l'email facoltativa e la casella con l'età minima
        tocca("scheda-registrati", finchéCompare: "Crea l'account")
        attendi("Codice d'invito", contiene: true)
        attendi("Email (facoltativa", contiene: true)
        attendi("ho almeno 14 anni", contiene: true)
        // Password dimenticata: un collegamento sotto il modulo, con l'email o con il codice di recupero
        tocca("scheda-accedi", finchéCompare: "Password dimenticata")
        tocca("Password dimenticata", finchéCompare: "Scegli la nuova password")
        XCTAssertTrue(app.textFields["Codice"].waitForExistence(timeout: 10))
        tocca("Con l'email", finchéCompare: "Mandami il codice")
        XCTAssertTrue(app.textFields["Email"].waitForExistence(timeout: 10))
        XCTAssertTrue(app.buttons["Torna all'accesso"].exists)

        // di nuovo Accedi, con nome e password: si entra
        tocca("scheda-accedi", finchéCompare: "Password dimenticata")
        nome.tap()
        nome.typeText("mister.rossi")
        let password = app.secureTextFields["Password"]
        password.tap()
        password.typeText("Prova-Finta-Zero")
        XCTAssertTrue(entra.isEnabled)
        entra.tap()
        XCTAssertTrue(app.tabBars.firstMatch.waitForExistence(timeout: 30), "dopo l'accesso compare l'app")
    }

    /// Registrati senza la casella (invio dalla tastiera, dall'ultimo campo): compare la frase della web, non si va avanti e la
    /// password scritta resta.
    func testRegistrazioneSenzaCasellaSpiegaCosaMancaETieneLaPassword() {
        avvia("registra")
        let invito = app.textFields["Codice d'invito"]
        XCTAssertTrue(invito.waitForExistence(timeout: 30), "la scheda Registrati deve comparire")
        invito.tap()
        invito.typeText("INV-123\n")          // l'invio dalla tastiera passa al campo dopo: nome utente
        app.typeText("mister.rossi\n")       // poi l'email facoltativa
        app.typeText("\n")                   // lasciata vuota: si passa alla password
        app.typeText("Prova-Finta-Zero\n")   // dall'ultimo campo l'invio manda il modulo
        attendi("Per registrarti spunta la casella: hai letto Privacy e Termini d'uso e hai almeno 14 anni", contiene: true)
        XCTAssertFalse(app.tabBars.firstMatch.exists, "senza la casella non si entra")
        XCTAssertEqual(app.buttons["accesso-invia"].label, "Crea l'account", "si resta sul modulo")
        let password = app.secureTextFields["Password (almeno 10 caratteri)"]
        XCTAssertTrue(password.exists)
        XCTAssertTrue((password.value as? String ?? "").contains("•"), "la password scritta resta")
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
        attendi("mister.rossi", contiene: true)
        attendi("Utente · dal 1 settembre 2026", contiene: true)   // la riga intera, come la web (ruolo e data italiana)
        attendi("Nessuna email collegata.")
        attendi("Cambia la password")
        attendi("Codice di recupero")
        attendi("Elimina l'account")
        // un solo nome e niente voci tolte (maiuscole del nome, esci da tutti i telefoni)
        XCTAssertFalse(elemento("Per accedere").exists)
        XCTAssertFalse(elemento("Cambia le maiuscole del nome").exists)
        XCTAssertFalse(elemento("Esci da tutti", contiene: true).exists)
        // «Esci» è l'ultima riga di «Il tuo account», subito sotto «Elimina l'account» (come sulla web), non una sezione a parte in fondo
        let esci = app.buttons["Esci"].firstMatch   // con la conferma aperta i pulsanti «Esci» sono due
        for _ in 0..<8 where !(esci.exists && esci.isHittable) { app.swipeUp() }
        XCTAssertTrue(esci.waitForExistence(timeout: 5))
        let elimina = app.buttons["Elimina l'account"].firstMatch
        XCTAssertTrue(elimina.exists, "«Elimina l'account» sta subito sopra «Esci»")
        let fraLeDue = esci.frame.minY - elimina.frame.maxY
        // stessa sezione: fra le due righe al massimo il margine delle righe; una sezione nuova aggiunge lo spazio fra le sezioni (oltre 30 punti)
        XCTAssertTrue(fraLeDue > -1 && fraLeDue < 20, "«Esci» deve seguire «Elimina l'account» nella stessa sezione (spazio: \(fraLeDue))")
        // il tocco chiede conferma (il tocco perso sul simulatore carico si ripete, al massimo 3 volte)
        let conferma = elemento("Esci da SchieraXI su questo telefono?")
        for _ in 0..<3 where !conferma.exists {
            esci.tap()
            _ = conferma.waitForExistence(timeout: 5)
        }
        XCTAssertTrue(conferma.exists, "toccando «Esci» compare la conferma")
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

    /// Vero se il foglio (il suo `segno`) si chiude entro `secondi`. Conta solo un'assenza confermata: `waitForNonExistence`
    /// legge senza ripetere (`existsNoRetry`) e sul Mac di GitHub carico una lettura che l'app serve in ritardo vale «sparito»
    /// anche con il foglio aperto (#177: subito dopo c'erano il campo e la barra del foglio, e la voce sotto era ancora coperta).
    /// La conferma è la lettura dopo, che ripete (`exists`): un foglio chiuso davvero non torna, si riapre solo con un tocco.
    private func siChiude(_ segno: XCUIElement, entro secondi: TimeInterval) -> Bool {
        let fine = Date().addingTimeInterval(secondi)
        repeat {
            if segno.waitForNonExistence(timeout: max(fine.timeIntervalSinceNow, 0.1)), !segno.exists { return true }
        } while Date() < fine
        return false
    }

    /// Mentre il foglio è aperto arrivano dati nuovi dell'account (in demo ogni mezzo secondo): deve restare aperto.
    private func restaAperto(_ segno: XCUIElement, _ nome: String, file: StaticString = #filePath, line: UInt = #line) {
        XCTAssertFalse(siChiude(segno, entro: 4), "il foglio «\(nome)» si è chiuso da solo", file: file, line: line)
    }

    /// Chiude il foglio con il pulsante della sua barra (`titolo`): sotto c'è la barra delle Impostazioni con un altro «Chiudi».
    /// La chiusura si controlla con `siChiude`, la stessa prova di `restaAperto`: così ogni corsa mostra che vede un foglio che si chiude davvero.
    private func chiudiFoglio(_ titolo: String, _ pulsante: String, segno: XCUIElement, file: StaticString = #filePath, line: UInt = #line) {
        let b = app.navigationBars[titolo].buttons[pulsante]
        XCTAssertTrue(b.waitForExistence(timeout: 10), "manca «\(pulsante)»", file: file, line: line)
        b.tap()
        XCTAssertTrue(siChiude(segno, entro: 10), "il foglio non si chiude con «\(pulsante)»", file: file, line: line)
    }

    /// Build 219: «Cambia password» si apriva e si chiudeva subito da solo. Con i dati dell'account che cambiano di continuo
    /// (`-DEMO_ACCOUNT_CHE_CAMBIA`) ogni foglio dell'account deve restare aperto e non perdere quello che si scrive.
    func testFogliDellAccountRestanoApertiQuandoArrivanoDatiNuovi() {
        avvia("account", altri: ["-DEMO_ACCOUNT_CHE_CAMBIA", "1"])
        attendi("Il tuo account")

        // Cambia password: si apre, resta aperto, il testo scritto resta
        let attuale = app.secureTextFields["Password attuale"]
        apriFoglio(app.buttons["account-cambia-password"], segno: attuale)
        restaAperto(attuale, "Cambia la password")
        attuale.tap()
        attuale.typeText("vecchia-prova-1")
        restaAperto(attuale, "Cambia la password")
        XCTAssertFalse((attuale.value as? String ?? "").isEmpty, "la password scritta non deve sparire")
        XCTAssertTrue(app.secureTextFields["Nuova password (almeno 10 caratteri)"].exists)
        XCTAssertTrue(app.secureTextFields["Ripeti la nuova password"].exists)
        chiudiFoglio("Cambia la password", "Annulla", segno: attuale)

        // Codice di recupero
        let codice = app.navigationBars["Codice di recupero"]
        apriFoglio(app.buttons["account-codice"], segno: codice)
        restaAperto(codice, "Codice di recupero")
        chiudiFoglio("Codice di recupero", "Annulla", segno: codice)

        // Email (la voce cambia nome mentre l'email va e viene)
        let email = app.navigationBars["Email"]
        let voceEmail = app.buttons.matching(NSPredicate(format: "label IN %@", ["Aggiungi un'email", "Gestisci l'email"])).firstMatch
        apriFoglio(voceEmail, segno: email)
        restaAperto(email, "Email")
        chiudiFoglio("Email", "Chiudi", segno: email)

        // Elimina l'account
        let elimina = app.navigationBars["Elimina l'account"]
        apriFoglio(app.buttons["account-elimina"], segno: elimina)
        restaAperto(elimina, "Elimina l'account")
        chiudiFoglio("Elimina l'account", "Annulla", segno: elimina)
    }

    // MARK: - Diagnosi temporanea #177 (da togliere prima della pull request)

    private func adesso() -> TimeInterval { Date().timeIntervalSinceReferenceDate }
    private func f(_ t: TimeInterval) -> String { String(format: "%.2f", t) }

    /// Apre il foglio come `apriFoglio`, ma conta tempo, tocchi e scorrimenti.
    private func apriFoglioMisurato(_ voce: XCUIElement, segno: XCUIElement) -> String? {
        guard voce.waitForExistence(timeout: 30) else { return nil }
        let inizio = adesso()
        var tocchi = 0
        var scorrimenti = 0
        var aperto = false
        for _ in 0..<3 where !aperto {
            if voce.exists {
                if !voce.isHittable { app.swipeUp(); scorrimenti += 1 }
                voce.tap()
                tocchi += 1
            }
            aperto = segno.waitForExistence(timeout: 10)
        }
        return aperto ? "\(f(adesso() - inizio))s/\(tocchi)t/\(scorrimenti)sc" : nil
    }

    private func chiudiSeAperto(_ titolo: String, _ pulsante: String, segno: XCUIElement, voce: XCUIElement) {
        let b = app.navigationBars[titolo].buttons[pulsante]
        for _ in 0..<3 {
            if !b.waitForExistence(timeout: 3) { break }
            b.tap()
            if segno.waitForNonExistence(timeout: 5) { break }
        }
        let toccabile = XCTNSPredicateExpectation(predicate: NSPredicate(format: "isHittable == true"), object: voce)
        _ = XCTWaiter().wait(for: [toccabile], timeout: 5)
    }

    /// Fili che tengono occupata la CPU del Mac, come su un Mac di GitHub carico (la corsa da 89 secondi). Solo per la diagnosi.
    private final class Carico: @unchecked Sendable {
        private let lucchetto = NSLock()
        private var acceso = true
        var attivo: Bool { lucchetto.lock(); defer { lucchetto.unlock() }; return acceso }
        func ferma() { lucchetto.lock(); acceso = false; lucchetto.unlock() }
        init(fili: Int) {
            for _ in 0..<fili {
                Thread.detachNewThread { [self] in
                    var x = 0.0
                    while self.attivo { for i in 0..<200_000 { x += sin(Double(i)) } }
                    if x == 42 { print(x) }
                }
            }
        }
    }

    /// Sotto carico, con i dati che cambiano, sulle stesse aperture: il controllo vecchio (`waitForNonExistence` da solo) e
    /// quello nuovo (`siChiude`), a turno per primo. Poi «Annulla»: `siChiude` deve vedere la chiusura vera.
    func testDiagnosiConfrontoSottoCarico() {
        avvia("account", altri: ["-DEMO_ACCOUNT_CHE_CAMBIA", "1"])
        continueAfterFailure = true
        attendi("Il tuo account")
        let carico = Carico(fili: 6)
        defer { carico.ferma() }
        let fogli: [(voce: XCUIElement, segno: XCUIElement, titolo: String)] = [
            (app.buttons["account-cambia-password"], app.secureTextFields["Password attuale"], "Cambia la password"),
            (app.buttons["account-elimina"], app.navigationBars["Elimina l'account"], "Elimina l'account"),
        ]
        var aperture = 0
        var mancate = 0
        var allarmiVecchi = 0
        var allarmiNuovi = 0
        var chiusureViste = 0
        var chiusureNonViste = 0
        var toccoAnnullaPerso = 0
        var note: [String] = []
        let inizio = adesso()
        ciclo: for giro in 1...80 {
            for foglio in fogli {
                if adesso() - inizio > 1080 { break ciclo }
                guard let apertura = apriFoglioMisurato(foglio.voce, segno: foglio.segno) else {
                    mancate += 1
                    chiudiSeAperto(foglio.titolo, "Annulla", segno: foglio.segno, voce: foglio.voce)
                    continue
                }
                aperture += 1
                let ordine = aperture.isMultiple(of: 2) ? ["nuovo", "vecchio"] : ["vecchio", "nuovo"]
                for quale in ordine {
                    let t = adesso()
                    let allarme = quale == "vecchio" ? foglio.segno.waitForNonExistence(timeout: 4) : siChiude(foglio.segno, entro: 4)
                    guard allarme else { continue }
                    if quale == "vecchio" { allarmiVecchi += 1 } else { allarmiNuovi += 1 }
                    let apertoDavvero = foglio.segno.exists && app.navigationBars[foglio.titolo].exists
                    note.append("giro \(giro) «\(foglio.titolo)» controllo \(quale) (aperto in \(apertura)): allarme dopo \(f(adesso() - t))s, foglio aperto davvero=\(apertoDavvero)")
                }
                let b = app.navigationBars[foglio.titolo].buttons["Annulla"]
                if b.waitForExistence(timeout: 10) {
                    b.tap()
                    if siChiude(foglio.segno, entro: 10) {
                        chiusureViste += 1
                    } else if foglio.segno.exists {
                        toccoAnnullaPerso += 1
                    } else {
                        chiusureNonViste += 1
                    }
                }
                chiudiSeAperto(foglio.titolo, "Annulla", segno: foglio.segno, voce: foglio.voce)
            }
        }
        carico.ferma()
        var parti: [String] = []
        parti.append("CONFRONTO carico 6 fili, dati che cambiano: aperture \(aperture) (non aperte \(mancate))")
        parti.append("allarmi controllo vecchio \(allarmiVecchi) su \(aperture), controllo nuovo \(allarmiNuovi) su \(aperture)")
        parti.append("dopo Annulla chiusure viste \(chiusureViste), non viste \(chiusureNonViste), tocco perso \(toccoAnnullaPerso)")
        let riassunto = (parti + note).joined(separator: " || ")
        print(riassunto)
        XCTFail(riassunto)
    }

    func testRetAssenteDiceCosaFare() {
        avvia("rete")
        attendi("Non riesco a collegarmi a SchieraXI", contiene: true)
        XCTAssertTrue(app.buttons["accesso-invia"].waitForExistence(timeout: 10), "si può riprovare")
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
            ("scheda-registrati", "Crea l'account"),
            ("scheda-accedi", "Password dimenticata"),
            ("Password dimenticata", "Scegli la nuova password"),
            ("scheda-accedi", "Password dimenticata"),
        ]
        for giro in 1...6 {
            for passo in arrivi {
                XCTContext.runActivity(named: "giro \(giro): \(passo.tocco)") { _ in tocca(passo.tocco, finchéCompare: passo.atteso) }
            }
        }
        // Con i tocchi a raffica sul Mac di GitHub un tocco può perdersi: si rimette «Accedi» finché «Password dimenticata» compare.
        var tornata = false
        for _ in 0..<6 where !tornata {
            if app.buttons["Password dimenticata"].waitForExistence(timeout: 8) { tornata = true; break }
            app.buttons["scheda-accedi"].tap()
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
