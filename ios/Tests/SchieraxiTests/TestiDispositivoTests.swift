import Foundation
import Testing
@testable import Schieraxi

/// Le frasi del primo avvio e di «Esci» valgono per iPhone e iPad (foto di `main`, corsa 45951751934): sull'iPad il primo avvio
/// diceva «Resta solo su questo telefono» e l'uscita parlava di «questo telefono». Ora dicono «questo dispositivo», come la web
/// (`account.esci_conferma`, «Esci da SchieraXI su questo dispositivo?»), e vengono dal catalogo comune.
struct TestiDispositivoTests {

    @Test("Primo avvio, «Esci solo da…» e l'aiuto di VoiceOver su «Esci» dicono «questo dispositivo», mai «telefono»", arguments: [
        Catalogo.Accesso.indirizzoSpiega(esempio: "https://esempio.invalid"),
        Catalogo.Account.esciSoloQui,
        Catalogo.Account.esciAiuto,
    ])
    func frasiPerIPhoneEIPad(_ frase: String) {
        #expect(frase.contains("questo dispositivo"), "«\(frase)»")
        #expect(!frase.lowercased().contains("telefono") && !frase.contains("iPhone"), "«\(frase)»")
    }

    @Test("La frase del primo avvio ha l'indirizzo d'esempio dentro")
    func indirizzoDEsempio() {
        #expect(Catalogo.Accesso.indirizzoSpiega(esempio: Config.esempioIndirizzo).contains(Config.esempioIndirizzo))
    }

    /// Il codice (senza commenti) dei due file: nessuna frase per l'utente con «telefono», le frasi vengono dal catalogo.
    @Test("Primo avvio e riga di «Esci» non scrivono più «telefono» a mano", arguments: [
        ("Sources/Presentation/Accesso/PrimoAvvioView.swift", "Catalogo.Accesso.indirizzoSpiega("),
        ("Sources/Presentation/Accesso/AccountSezione.swift", "Catalogo.Account.esciAiuto"),
    ])
    func nienteTelefonoNelCodice(percorso: String, usa: String) throws {
        var url = URL(fileURLWithPath: #filePath)
        for _ in 0..<3 { url.deleteLastPathComponent() }          // TestiDispositivoTests.swift, SchieraxiTests, Tests
        let testo = try String(contentsOf: url.appendingPathComponent(percorso), encoding: .utf8)
        let codice = testo.components(separatedBy: .newlines)
            .map { $0.trimmingCharacters(in: .whitespaces) }
            .filter { !$0.hasPrefix("//") }
            .map { riga in riga.range(of: " //").map { String(riga[..<$0.lowerBound]) } ?? riga }
        let conTelefono = codice.filter { $0.contains("\"") && $0.contains("telefono") }
        #expect(conTelefono.isEmpty, "\(percorso): \(conTelefono)")
        #expect(codice.contains { $0.contains(usa) }, "\(percorso) non usa \(usa)")
    }
}
