import XCTest

/// Controllo automatico di accessibilità (quello dell'Accessibility Inspector: contrasto, aree di tocco, testo tagliato,
/// Dynamic Type, elementi senza descrizione per VoiceOver) su ogni schermata della demo.
/// NON fa fallire niente: scrive i problemi trovati nel log come righe `AUDIT|schermata|tipo|descrizione|elemento`.
/// Parte SOLO se il test runner riceve `AUDIT_ACCESSIBILITA=1` (nel workflow: `TEST_RUNNER_AUDIT_ACCESSIBILITA=1`),
/// così il workflow `Test` di ogni PR lo salta in un attimo.
final class AuditAccessibilitaUITests: XCTestCase {
    private static let schermate = [
        "oggi", "formazione", "formazione-manuale", "formazione-confronto", "formazione-perche",
        "squadra", "mercato-consigliati", "mercato-classifica", "mercato-calendario", "mercato-osservati", "giocatore",
        "scambi", "scambi-offerta", "scambi-dettaglio", "scambi-analizza",
        "lega", "lega-squadre", "lega-rosa", "lega-regole", "lega-asta", "lega-stato", "lega-avvisi", "lega-diario", "lega-novita",
        "lega-importa", "lega-movimenti", "lega-stagione", "impostazioni", "impostazioni-aspetto", "impostazioni-crediti",
        "impostazioni-avanzate", "collega-widget", "guida", "primo-avvio",
    ]
    private static let accessi = ["accedi", "registra", "recupero", "codice", "account", "rose", "rete", "limite"]

    override func setUpWithError() throws {
        try XCTSkipUnless(ProcessInfo.processInfo.environment["AUDIT_ACCESSIBILITA"] == "1",
                          "controllo di accessibilità solo su richiesta (AUDIT_ACCESSIBILITA=1)")
        continueAfterFailure = true
    }

    private func controlla(_ nome: String, argomenti: [String]) {
        let app = XCUIApplication()
        app.launchArguments += ["-DEMO"] + argomenti + ["-AppleLanguages", "(it)", "-AppleLocale", "it_IT"]
        app.launch()
        sleep(4)   // il tempo di caricare i dati finti e aprire fogli e pagine
        var trovati = 0
        do {
            try app.performAccessibilityAudit { problema in
                trovati += 1
                let elemento = problema.element.map { "\($0.elementType.rawValue):\($0.label.prefix(60))" } ?? "-"
                let riga = "AUDIT|\(nome)|\(problema.auditType.rawValue)|\(problema.compactDescription)|\(elemento)"
                print(riga.replacingOccurrences(of: "\n", with: " "))
                return true   // segnato, non fa fallire
            }
        } catch {
            print("AUDIT|\(nome)|errore|\(error.localizedDescription)|-")
        }
        print("AUDIT-FINE|\(nome)|\(trovati)")
        app.terminate()
    }

    func testOgniSchermata() {
        for s in Self.schermate { controlla(s, argomenti: ["-DEMO_SCHERMATA", s]) }
    }

    func testAccesso() {
        for a in Self.accessi { controlla("accesso-" + a, argomenti: ["-DEMO_ACCESSO", a]) }
    }
}
