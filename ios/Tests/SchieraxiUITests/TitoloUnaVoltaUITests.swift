import XCTest

/// Issue #419: VoiceOver legge il titolo di una pagina una volta sola, con ogni dimensione del testo. Con il testo normale lo
/// legge nella barra (`TitoloInBarra`, #340); con il testo grande nella pagina (`TitoloNellaPagina`, intestazione), e la barra
/// è nascosta a VoiceOver anche quando mostra il titolo perché ci sta (se no un titolo corto si sentirebbe due volte).
/// Si contano i testi che vede XCUITest, cioè gli elementi che VoiceOver può leggere: un elemento nascosto a VoiceOver qui
/// non c'è. Questo controlla la barra vera, che i test unitari non possono disegnare.
final class TitoloUnaVoltaUITests: XCTestCase {
    /// Il nome della squadra che apre `-DEMO_SCHERMATA lega-rosa` (inventato, 32 lettere: con il testo grande non ci sta nella barra).
    private static let squadra = "Gli Amici del Bar Sport Centrale"
    /// Il testo più grande di iOS (Accessibilità 5).
    private static let testoMassimo = "UICTContentSizeCategoryAccessibilityXXXL"

    override func setUpWithError() throws {
        continueAfterFailure = false
    }

    /// Apre la demo su `schermata`, con il testo `testo` (nil = quello normale).
    private func avvia(_ schermata: String, testo: String?) -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments += ["-DEMO", "-DEMO_SCHERMATA", schermata, "-AppleLanguages", "(it)", "-AppleLocale", "it_IT"]
        if let testo { app.launchArguments += ["-UIPreferredContentSizeCategoryName", testo] }
        app.launch()
        return app
    }

    /// I testi con esattamente questa etichetta in tutta l'app.
    private func testi(_ etichetta: String, _ app: XCUIApplication) -> XCUIElementQuery {
        app.staticTexts.matching(NSPredicate(format: "label == %@", etichetta))
    }

    /// I testi con esattamente questa etichetta nelle barre in alto.
    private func testiNellaBarra(_ etichetta: String, _ app: XCUIApplication) -> XCUIElementQuery {
        app.navigationBars.descendants(matching: .staticText).matching(NSPredicate(format: "label == %@", etichetta))
    }

    func testTestoNormaleIlNomeSiLeggeNellaBarraUnaVolta() {
        let app = avvia("lega-rosa", testo: nil)
        XCTAssertTrue(testiNellaBarra(Self.squadra, app).firstMatch.waitForExistence(timeout: 30),
                      "testo normale: il nome intero nella barra (#340)")
        XCTAssertEqual(testi(Self.squadra, app).count, 1, "VoiceOver deve leggere il nome una volta sola")
    }

    func testTestoMassimoIlNomeLungoSiLeggeNellaPaginaUnaVolta() {
        let app = avvia("lega-rosa", testo: Self.testoMassimo)
        XCTAssertTrue(testi(Self.squadra, app).firstMatch.waitForExistence(timeout: 30), "testo massimo: il nome intero nella pagina")
        XCTAssertTrue(app.navigationBars.buttons.firstMatch.waitForExistence(timeout: 10), "la barra in alto deve esserci")
        XCTAssertEqual(testiNellaBarra(Self.squadra, app).count, 0, "testo massimo: VoiceOver non legge il nome nella barra")
        XCTAssertEqual(testi(Self.squadra, app).count, 1, "VoiceOver deve leggere il nome una volta sola")
    }

    /// «Squadre» ci sta nella barra anche con il testo massimo: si vede lì e nella pagina, ma VoiceOver lo legge una volta.
    func testTestoMassimoIlTitoloCortoSiLeggeUnaVoltaSola() {
        let app = avvia("lega-squadre", testo: Self.testoMassimo)
        XCTAssertTrue(testi("Squadre", app).firstMatch.waitForExistence(timeout: 30), "testo massimo: il titolo nella pagina")
        XCTAssertTrue(app.navigationBars.buttons.firstMatch.waitForExistence(timeout: 10), "la barra in alto deve esserci")
        XCTAssertEqual(testiNellaBarra("Squadre", app).count, 0, "testo massimo: VoiceOver non legge il titolo nella barra")
        XCTAssertEqual(testi("Squadre", app).count, 1, "VoiceOver deve leggere il titolo una volta sola")
    }
}
