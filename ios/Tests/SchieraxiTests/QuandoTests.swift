import XCTest
@testable import Schieraxi

final class QuandoTests: XCTestCase {
    /// Le date del server sono in ora italiana: ora e giorno si controllano con un calendario di Roma.
    private var roma: Calendar {
        var c = Calendar(identifier: .gregorian)
        c.timeZone = TimeZone(identifier: "Europe/Rome")!
        return c
    }

    func testLeggeLaDataDelServer() throws {
        let data = try XCTUnwrap(Quando.data("2026-10-27 18:30"))
        let parti = roma.dateComponents([.year, .month, .day, .hour, .minute], from: data)
        XCTAssertEqual(parti.year, 2026)
        XCTAssertEqual(parti.month, 10)
        XCTAssertEqual(parti.day, 27)
        XCTAssertEqual(parti.hour, 18)
        XCTAssertEqual(parti.minute, 30)
    }

    func testIgnoraLaCodaDopoIPrimiSediciCaratteri() throws {
        // "2026-10-27 18:30:45" → si usano solo i primi 16 caratteri
        let a = try XCTUnwrap(Quando.data("2026-10-27 18:30:45"))
        let b = try XCTUnwrap(Quando.data("2026-10-27 18:30"))
        XCTAssertEqual(a, b)
    }

    func testTestoNonValidoDaNil() {
        XCTAssertNil(Quando.data(nil))
        XCTAssertNil(Quando.data(""))
        XCTAssertNil(Quando.data("domani sera"))
    }

    func testAccettaLaTDiISO() throws {
        // `ultimo_aggiornamento` arriva con la «T» (widget Stato: prima diceva sempre «Dati delle —»)
        let conT = try XCTUnwrap(Quando.data("2026-10-26T23:55:13"))
        XCTAssertEqual(conT, Quando.data("2026-10-26 23:55"))
        XCTAssertEqual(roma.component(.hour, from: conT), 23)
        XCTAssertEqual(roma.component(.minute, from: conT), 55)
        XCTAssertNotNil(Quando.data("2026-10-27T18:30"))
    }

    func testLeggibileInItaliano() {
        let testo = Quando.leggibile("2026-10-27 18:30")
        XCTAssertTrue(testo.lowercased().hasPrefix("mar"), "martedì: \(testo)")
        XCTAssertTrue(testo.contains("27"), testo)
        XCTAssertTrue(testo.lowercased().contains("ott"), testo)
        XCTAssertTrue(testo.hasSuffix("18:30"), testo)
    }

    func testLeggibileConTestoNonValidoRestituisceIlTestoOVuoto() {
        XCTAssertEqual(Quando.leggibile("boh"), "boh")
        XCTAssertEqual(Quando.leggibile(nil as String?), "")
    }

    func testLeggibileDaDataEquivaleAlTesto() throws {
        let data = try XCTUnwrap(Quando.data("2026-11-08 18:30"))
        XCTAssertEqual(Quando.leggibile(data), Quando.leggibile("2026-11-08 18:30"))
    }

    /// L'ora legale finisce il 25 ottobre 2026: tra le 18:30 di sabato e quelle di domenica passano 25 ore.
    func testCambioOraLegale() throws {
        let sabato = try XCTUnwrap(Quando.data("2026-10-24 18:30"))
        let domenica = try XCTUnwrap(Quando.data("2026-10-25 18:30"))
        XCTAssertEqual(domenica.timeIntervalSince(sabato), 25 * 3600, accuracy: 1)
    }
}
