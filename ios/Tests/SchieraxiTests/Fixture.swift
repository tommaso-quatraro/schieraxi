import Foundation
import XCTest
@testable import Schieraxi

/// Legge i file JSON di `Tests/Fixtures` (risposte del server con dati inventati) dal bundle dei test.
enum Fixture {
    private final class Ancora {}

    static func dati(_ nome: String, file: StaticString = #filePath, line: UInt = #line) throws -> Data {
        let bundle = Bundle(for: Ancora.self)
        let url = bundle.url(forResource: nome, withExtension: "json")
            ?? bundle.url(forResource: nome, withExtension: "json", subdirectory: "Fixtures")
        guard let url else {
            XCTFail("Fixture mancante: \(nome).json", file: file, line: line)
            throw ErroreApi.dati("fixture \(nome)")
        }
        return try Data(contentsOf: url)
    }

    static func testo(_ nome: String) throws -> String {
        String(decoding: try dati(nome), as: UTF8.self)
    }

    /// Decodifica una fixture come fa l'app (chiavi snake_case convertite).
    static func decodifica<T: Decodable>(_ nome: String, snake: Bool = true) throws -> T {
        try Decodifica.decodifica(try dati(nome), snake: snake)
    }
}
