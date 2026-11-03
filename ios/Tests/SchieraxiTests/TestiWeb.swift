import Foundation

/// I testi italiani della web (`fanta/web/testi.js`), letti dal repository: le prove di parità li confrontano con quelli
/// dell'app, così una frase cambiata su un lato solo fa fallire i test. Il file sta accanto ai test sul Mac di GitHub
/// (come `fanta/frasi.py` per `DemoDaFareTests`).
struct TestiWeb {
    struct Errore: Error, CustomStringConvertible {
        let description: String
    }

    private let righe: [String]

    init(file: String = #filePath) throws {
        var url = URL(fileURLWithPath: file)
        for _ in 0..<4 { url.deleteLastPathComponent() }          // TestiWeb.swift, SchieraxiTests, Tests, ios
        url.appendPathComponent("fanta/web/testi.js")
        guard let sorgente = try? String(contentsOf: url, encoding: .utf8) else {
            throw Errore(description: "non riesco a leggere fanta/web/testi.js dal repository")
        }
        righe = sorgente.split(whereSeparator: \.isNewline).map { $0.trimmingCharacters(in: .whitespaces) }
    }

    /// Il testo italiano di una chiave: la prima riga `"chiave": "…",` del file (il blocco italiano viene prima di quello inglese).
    func italiano(_ chiave: String) throws -> String {
        let inizio = "\"\(chiave)\": \""
        for riga in righe where riga.hasPrefix(inizio) {
            guard let fine = riga.lastIndex(of: "\"") else { continue }
            let apertura = riga.index(riga.startIndex, offsetBy: inizio.count - 1)
            guard apertura < fine else { continue }
            // la stringa tra virgolette, con gli eventuali «\"» sciolti come in JSON
            return try JSONDecoder().decode(String.self, from: Data(riga[apertura...fine].utf8))
        }
        throw Errore(description: "in testi.js manca la chiave \(chiave)")
    }
}
