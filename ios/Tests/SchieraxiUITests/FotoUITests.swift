import XCTest

/// Le condizioni delle fotografie automatiche (`scripts/screenshot.sh`), con l'app in modalità demo: l'orizzontale chiesto con
/// `-DEMO_ORIENTAMENTO` vale anche per l'accesso (prima la foto usciva girata), la Formazione in orizzontale finisce di caricare,
/// la foto `accesso-account-fondo` mostra «Esci».
final class FotoUITests: XCTestCase {
    private var app: XCUIApplication!

    private func avvia(_ argomenti: [String]) {
        continueAfterFailure = false
        app = XCUIApplication()
        app.launchArguments += ["-DEMO"] + argomenti + ["-AppleLanguages", "(it)", "-AppleLocale", "it_IT"]
        app.launch()
    }

    /// Ripete `condizione` ogni mezzo secondo finché è vera, al massimo per `secondi`.
    private func aspetta(_ secondi: TimeInterval, finché condizione: () -> Bool) -> Bool {
        let fine = Date().addingTimeInterval(secondi)
        repeat {
            if condizione() { return true }
            Thread.sleep(forTimeInterval: 0.5)
        } while Date() < fine
        return condizione()
    }

    /// L'app è disegnata in orizzontale: altezza «compatta» del telefono girato, o finestra più larga che alta.
    private var inOrizzontale: Bool {
        let finestra = app.windows.firstMatch
        guard finestra.exists else { return false }
        return finestra.verticalSizeClass == .compact || finestra.frame.width > finestra.frame.height
    }

    func testLAccessoSiGiraInOrizzontaleQuandoLaFotoLoChiede() {
        avvia(["-DEMO_ACCESSO", "accedi", "-DEMO_ORIENTAMENTO", "orizzontale"])
        XCTAssertTrue(app.textFields["Nome utente"].waitForExistence(timeout: 30), "la schermata di accesso deve comparire")
        XCTAssertTrue(aspetta(15) { inOrizzontale }, "con -DEMO_ORIENTAMENTO orizzontale anche l'accesso va in orizzontale")
    }

    func testLaFormazioneInOrizzontaleFinisceDiCaricare() {
        avvia(["-DEMO_SCHERMATA", "formazione", "-DEMO_ORIENTAMENTO", "orizzontale"])
        let modifica = app.buttons["Modifica a mano"]
        // Il tempo delle foto: 3 secondi dopo l'avvio più al massimo 8 di attesa dello schermo fermo (scripts/screenshot.sh).
        let inTempo = modifica.waitForExistence(timeout: 10)
        var perché = ""
        if !inTempo {
            // Per capire la causa: arriva più tardi? Cambiando scheda e tornando, carica?
            let tardi = modifica.waitForExistence(timeout: 20)
            var cambiandoScheda = tardi
            if !tardi {
                let barra = app.tabBars.firstMatch
                barra.buttons["Oggi"].firstMatch.tap()
                barra.buttons["Formazione"].firstMatch.tap()
                cambiandoScheda = modifica.waitForExistence(timeout: 15)
            }
            perché = " (dopo altri 20 s: \(tardi ? "sì" : "no"); cambiando scheda: \(cambiandoScheda ? "sì" : "no"); orizzontale: \(inOrizzontale ? "sì" : "no"))"
        }
        XCTAssertTrue(inTempo, "in orizzontale la Formazione resta in caricamento oltre il tempo delle foto" + perché)
        XCTAssertTrue(aspetta(5) { inOrizzontale }, "la Formazione deve essere in orizzontale")
    }

    func testIlFondoDellAccountMostraEsci() {
        avvia(["-DEMO_ACCESSO", "account", "-DEMO_FONDO", "1"])
        let esci = app.buttons["account-esci"]
        XCTAssertTrue(aspetta(20) { esci.exists && esci.isHittable }, "nella foto accesso-account-fondo «Esci» deve essere a video")
        XCTAssertEqual(esci.label, "Esci")
    }

    /// `confronto-fondo` (#393): la foto era uguale a `formazione-confronto` perché il foglio del Confronto non scorreva.
    /// Con -DEMO_FONDO l'ultima scheda («Perché» di ognuno) deve essere a video, sotto la piega.
    func testIlFondoDelConfrontoMostraUltimaScheda() {
        avvia(["-DEMO_SCHERMATA", "confronto", "-DEMO_FONDO", "1"])
        let ultima = app.descendants(matching: .any)
            .matching(NSPredicate(format: "identifier BEGINSWITH 'confronto-motivi-'")).firstMatch
        XCTAssertTrue(aspetta(30) { ultima.exists && ultima.isHittable },
                      "nella foto confronto-fondo l'ultima scheda del Confronto deve essere a video")
    }
}
