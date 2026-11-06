import XCTest

/// Issue #419: VoiceOver legge il titolo di una pagina una volta sola, con ogni dimensione del testo. Con il testo normale lo
/// legge nella barra (`TitoloInBarra`, #340); con il testo grande nella pagina (`TitoloNellaPagina`, intestazione), e la barra
/// resta senza titolo. Si contano tutti i testi accessibili con il titolo, anche quelli che non si vedono, e nella barra
/// nessun testo vuoto (VoiceOver si fermerebbe su niente). Le versioni di prova lasciavano nella barra elementi invisibili
/// con il nome: il titolo di sistema sotto `TitoloInBarra` (con il testo normale il nome due volte) e, con il testo grande,
/// l'elemento del titolo «solo se ci sta» anche se nascosto a VoiceOver (con il nome corto, o vuoto con quello lungo).
/// Ogni messaggio d'errore descrive tutti i testi trovati (posizione, misura, se si vedono), su una riga sola.
/// Questo controlla la barra vera, che i test unitari non possono disegnare.
final class TitoloUnaVoltaUITests: XCTestCase {
    /// Il nome della squadra che apre `-DEMO_SCHERMATA lega-rosa` (inventato, 32 lettere: con il testo grande non ci sta nella barra).
    private static let squadra = "Gli Amici del Bar Sport Centrale"
    /// Il testo più grande di iOS (Accessibilità 5).
    private static let testoMassimo = "UICTContentSizeCategoryAccessibilityXXXL"

    override func setUpWithError() throws {
        continueAfterFailure = true
    }

    /// Apre la demo su `schermata`, con il testo `testo` (nil = quello normale).
    private func avvia(_ schermata: String, testo: String?) -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments += ["-DEMO", "-DEMO_SCHERMATA", schermata, "-AppleLanguages", "(it)", "-AppleLocale", "it_IT"]
        if let testo { app.launchArguments += ["-UIPreferredContentSizeCategoryName", testo] }
        app.launch()
        return app
    }

    /// I testi con esattamente questa etichetta, in tutta l'app o solo nelle barre in alto.
    private func testi(_ etichetta: String, in radice: XCUIElementQuery) -> [XCUIElement] {
        radice.descendants(matching: .staticText).matching(NSPredicate(format: "label == %@", etichetta)).allElementsBoundByIndex
    }

    /// Tutti i testi con quell'etichetta, su una riga: dove stanno, quanto sono grandi, se si vedono.
    private func descrivi(_ etichetta: String, _ app: XCUIApplication) -> String {
        let barra = testi(etichetta, in: app.navigationBars).map { "barra " + riga($0) }
        let tutti = testi(etichetta, in: app.windows).map { "app " + riga($0) }
        return (barra + tutti).joined(separator: " | ")
    }

    /// I testi senza parole nelle barre in alto.
    private func vuotiNellaBarra(_ app: XCUIApplication) -> Int {
        app.navigationBars.descendants(matching: .staticText).matching(NSPredicate(format: "label == ''")).count
    }

    private func riga(_ e: XCUIElement) -> String {
        let f = e.frame
        return "x \(Int(f.minX)) y \(Int(f.minY)) \(Int(f.width))×\(Int(f.height)) visibile \(e.isHittable)"
    }

    func testTestoNormaleIlNomeSiLeggeNellaBarraUnaVolta() {
        let app = avvia("lega-rosa", testo: nil)
        let nellaBarra = app.navigationBars.descendants(matching: .staticText)
            .matching(NSPredicate(format: "label == %@", Self.squadra)).firstMatch
        XCTAssertTrue(nellaBarra.waitForExistence(timeout: 30), "testo normale: il nome intero nella barra (#340)")
        let dettagli = descrivi(Self.squadra, app)
        XCTAssertEqual(testi(Self.squadra, in: app.navigationBars).count, 1, "testo normale: il nome si vede nella barra. \(dettagli)")
        XCTAssertEqual(testi(Self.squadra, in: app.windows).count, 1, "VoiceOver deve leggere il nome una volta sola. \(dettagli)")
        XCTAssertEqual(vuotiNellaBarra(app), 0, "nella barra nessun testo vuoto")
    }

    func testTestoMassimoIlNomeLungoSiLeggeNellaPaginaUnaVolta() {
        let app = avvia("lega-rosa", testo: Self.testoMassimo)
        XCTAssertTrue(app.staticTexts.matching(NSPredicate(format: "label == %@", Self.squadra)).firstMatch.waitForExistence(timeout: 30),
                      "testo massimo: il nome intero nella pagina")
        XCTAssertTrue(app.navigationBars.buttons.firstMatch.waitForExistence(timeout: 10), "la barra in alto deve esserci")
        let dettagli = descrivi(Self.squadra, app)
        XCTAssertEqual(testi(Self.squadra, in: app.navigationBars).count, 0, "testo massimo: il nome non c'è nella barra. \(dettagli)")
        XCTAssertEqual(testi(Self.squadra, in: app.windows).count, 1, "VoiceOver deve leggere il nome una volta sola. \(dettagli)")
        XCTAssertEqual(vuotiNellaBarra(app), 0, "nella barra nessun testo vuoto: VoiceOver si fermerebbe su niente")
    }

    /// Un titolo corto, «Squadre» (una pagina senza `piccoloInBarra`): con il testo massimo anche lui solo nella pagina.
    func testTestoMassimoIlTitoloCortoSiLeggeUnaVoltaSola() {
        let app = avvia("lega-squadre", testo: Self.testoMassimo)
        XCTAssertTrue(app.staticTexts.matching(NSPredicate(format: "label == %@", "Squadre")).firstMatch.waitForExistence(timeout: 30),
                      "testo massimo: il titolo nella pagina")
        XCTAssertTrue(app.navigationBars.buttons.firstMatch.waitForExistence(timeout: 10), "la barra in alto deve esserci")
        let dettagli = descrivi("Squadre", app)
        XCTAssertEqual(testi("Squadre", in: app.navigationBars).count, 0, "testo massimo: VoiceOver non legge il titolo nella barra. \(dettagli)")
        XCTAssertEqual(testi("Squadre", in: app.windows).count, 1, "VoiceOver deve leggere il titolo una volta sola. \(dettagli)")
        XCTAssertEqual(vuotiNellaBarra(app), 0, "nella barra nessun testo vuoto: VoiceOver si fermerebbe su niente")
    }
}
