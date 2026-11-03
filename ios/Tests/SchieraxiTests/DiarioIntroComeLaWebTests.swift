import Foundation
import Testing
@testable import Schieraxi

/// Il testo in cima al Diario è quello della web, letto da `fanta/web/testi.js` del repository: la riga sotto il titolo
/// (`avv.diario_riga`) e la spiegazione (`avv.per_ogni_giornata`) dentro la parte richiudibile «Come si legge» (`mercato.come_legge`).
@MainActor
struct DiarioIntroComeLaWebTests {

    @Test("La riga in cima al Diario è quella della web")
    func rigaComeLaWeb() throws {
        let web = try TestiDellaWeb().testo("avv.diario_riga")
        #expect(DiarioView.rigaIntro == web)
    }

    @Test("La parte richiudibile si chiama come sulla web")
    func titoloComeLaWeb() throws {
        let web = try TestiDellaWeb().testo("mercato.come_legge")
        #expect(DiarioView.comeSiLegge == web)
    }

    @Test("La spiegazione dentro «Come si legge» è quella della web")
    func spiegazioneComeLaWeb() throws {
        let web = try TestiDellaWeb().testo("avv.per_ogni_giornata")
        #expect(DiarioView.perOgniGiornata == web)
    }
}

/// I testi italiani della web: le righe `"chiave": "testo",` di `fanta/web/testi.js`. L'italiano sta prima dell'inglese,
/// quindi vale la prima riga con quella chiave. Il file si legge dal repository (il test gira nel checkout di GitHub).
private struct TestiDellaWeb {
    struct Errore: Error, CustomStringConvertible {
        let description: String
    }

    private let righe: [Substring]

    init(file: String = #filePath) throws {
        var url = URL(fileURLWithPath: file)
        for _ in 0..<4 { url.deleteLastPathComponent() }          // SchieraxiTests, Tests, ios, radice del repository
        url.appendPathComponent("fanta/web/testi.js")
        guard let sorgente = try? String(contentsOf: url, encoding: .utf8) else {
            throw Errore(description: "non riesco a leggere fanta/web/testi.js dal repository")
        }
        righe = sorgente.split(whereSeparator: \.isNewline)
    }

    /// Il testo italiano della chiave, senza le virgolette e la virgola finale.
    func testo(_ chiave: String) throws -> String {
        let inizio = "\"\(chiave)\": \""
        for riga in righe {
            let t = riga.trimmingCharacters(in: .whitespaces)
            guard t.hasPrefix(inizio) else { continue }
            var resto = t.dropFirst(inizio.count)
            if resto.hasSuffix(",") { resto = resto.dropLast() }
            guard resto.hasSuffix("\""), !resto.contains("\\") else {
                throw Errore(description: "«\(chiave)»: riga di testi.js in una forma che il test non sa leggere")
            }
            return String(resto.dropLast())
        }
        throw Errore(description: "manca «\(chiave)» in fanta/web/testi.js")
    }
}
