import XCTest
@testable import Schieraxi

final class JSONValueTests: XCTestCase {
    private func decodifica(_ testo: String) throws -> JSONValue {
        try JSONDecoder().decode(JSONValue.self, from: Data(testo.utf8))
    }

    private func codifica(_ valore: JSONValue) throws -> String {
        let e = JSONEncoder()
        e.outputFormatting = [.sortedKeys]
        return String(decoding: try e.encode(valore), as: UTF8.self)
    }

    func testTipiBase() throws {
        XCTAssertEqual(try decodifica("null"), .nullo)
        XCTAssertEqual(try decodifica("true"), .booleano(true))
        XCTAssertEqual(try decodifica("7"), .intero(7))
        XCTAssertEqual(try decodifica("1.5"), .decimale(1.5))
        XCTAssertEqual(try decodifica("\"ciao\""), .testo("ciao"))
        XCTAssertEqual(try decodifica("[1,\"a\"]"), .lista([.intero(1), .testo("a")]))
    }

    func testGliInteriRestanoInteriNelGiroDiAndataERitorno() throws {
        let originale = #"{"crediti":500,"moduli":["3-4-3"],"nome":"Lega","panchina":{"numero":11,"posti":null},"x":1.5,"y":true}"#
        let giro = try codifica(try decodifica(originale))
        XCTAssertEqual(giro, originale)
        XCTAssertFalse(giro.contains("500.0"))
    }

    func testRegoleVereDelServerFannoIlGiroSenzaPerdereNiente() throws {
        let dati = try Fixture.dati("regole")
        let valore = try JSONDecoder().decode(JSONValue.self, from: dati)
        let ancora = try JSONDecoder().decode(JSONValue.self, from: JSONEncoder().encode(valore))
        XCTAssertEqual(valore, ancora)
        guard case .oggetto(let regole) = valore else { return XCTFail("le regole sono un oggetto") }
        XCTAssertEqual(regole["crediti_iniziali"], .intero(500))
        XCTAssertNotNil(regole["bonus"])
        XCTAssertNotNil(regole["modificatore_difesa"])
    }

    func testDescrizione() {
        XCTAssertEqual(JSONValue.nullo.descrizione, "—")
        XCTAssertEqual(JSONValue.booleano(true).descrizione, "sì")
        XCTAssertEqual(JSONValue.intero(3).descrizione, "3")
        XCTAssertEqual(JSONValue.lista([.testo("a"), .intero(2)]).descrizione, "a, 2")
    }
}
