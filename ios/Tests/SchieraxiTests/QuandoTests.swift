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

    /// «Adesso» fisso per le prove: sabato 31 ottobre 2026, ore 12:00 (ora italiana).
    private func adesso() throws -> Date { try XCTUnwrap(Quando.data("2026-10-31 12:00")) }

    /// Le regole di `quando` della web (`app.js`): oggi, domani, ieri; entro la settimana «sab 31 20:45»; oltre, con il mese.
    func testLeggibileComeLaWeb() throws {
        let ora = try adesso()
        XCTAssertEqual(Quando.leggibile("2026-10-31 20:45", adesso: ora), "oggi 20:45")
        XCTAssertEqual(Quando.leggibile("2026-10-31 00:05", adesso: ora), "oggi 00:05")
        XCTAssertEqual(Quando.leggibile("2026-11-01 18:30", adesso: ora), "domani 18:30")
        XCTAssertEqual(Quando.leggibile("2026-10-30 15:00", adesso: ora), "ieri 15:00")
        XCTAssertEqual(Quando.leggibile("2026-11-02 20:45", adesso: ora), "lun 2 20:45", "entro la settimana: giorno e numero")
        XCTAssertEqual(Quando.leggibile("2026-11-06 20:45", adesso: ora), "ven 6 20:45", "6 giorni avanti: ancora senza mese")
        XCTAssertEqual(Quando.leggibile("2026-10-25 20:45", adesso: ora), "dom 25 20:45", "6 giorni indietro")
        XCTAssertEqual(Quando.leggibile("2026-11-07 20:45", adesso: ora), "sab 7 nov 20:45", "oltre la settimana anche il mese")
        XCTAssertEqual(Quando.leggibile("2026-10-24 18:30", adesso: ora), "sab 24 ott 18:30")
        XCTAssertEqual(Quando.leggibile("2027-01-09 18:30", adesso: ora), "sab 9 gen 18:30")
    }

    func testLeggibileEntroLaSettimana() throws {
        // «sab 31 20:45» dalla scheda e dalle righe: la partita è tra due giorni
        let ora = try XCTUnwrap(Quando.data("2026-10-29 09:00"))
        XCTAssertEqual(Quando.leggibile("2026-10-31 20:45", adesso: ora), "sab 31 20:45")
    }

    func testLeggibileUsaLaMezzanotteDiRoma() throws {
        // 23:50 di venerdì a Roma: sabato appena dopo mezzanotte è «domani»
        let ora = try XCTUnwrap(Quando.data("2026-10-30 23:50"))
        XCTAssertEqual(Quando.leggibile("2026-10-31 00:10", adesso: ora), "domani 00:10")
        XCTAssertEqual(Quando.leggibile("2026-10-30 23:59", adesso: ora), "oggi 23:59")
    }

    func testLeggibileAttraversaIlCambioDiOraLegale() throws {
        // il 25 ottobre 2026 il giorno dura 25 ore: «ieri» e «domani» restano giusti
        let ora = try XCTUnwrap(Quando.data("2026-10-25 12:00"))
        XCTAssertEqual(Quando.leggibile("2026-10-24 18:30", adesso: ora), "ieri 18:30")
        XCTAssertEqual(Quando.leggibile("2026-10-26 18:30", adesso: ora), "domani 18:30")
    }

    func testLeggibileConLaTEISecondi() throws {
        let ora = try adesso()
        XCTAssertEqual(Quando.leggibile("2026-10-31T20:45:10", adesso: ora), "oggi 20:45")
    }

    func testLeggibileUsaLeSigleDeiGiorniFisse() throws {
        // le sigle sono quelle della web (`tempo.giorno_N`), non quelle del telefono
        let ora = try XCTUnwrap(Quando.data("2026-11-03 12:00"))
        let attese = ["2026-11-05": "gio", "2026-11-06": "ven", "2026-11-07": "sab", "2026-11-08": "dom", "2026-11-09": "lun"]
        for (giorno, sigla) in attese {
            let t = Quando.leggibile(giorno + " 20:45", adesso: ora)
            XCTAssertTrue(t.hasPrefix(sigla + " "), t)
        }
        XCTAssertEqual(Quando.leggibile("2026-11-04 20:45", adesso: ora), "domani 20:45")
        XCTAssertTrue(Quando.leggibile("2026-11-10 20:45", adesso: ora).hasPrefix("mar 10 "))
    }

    func testLeggibileConLOrologioVero() {
        // senza «adesso» si usa l'orologio: una data lontana non dice «oggi»
        XCTAssertFalse(Quando.leggibile("2001-02-03 20:45").hasPrefix("oggi"))
        XCTAssertTrue(Quando.leggibile("2001-02-03 20:45").hasSuffix("20:45"))
    }

    func testLeggibileConTestoNonValidoRestituisceIlTestoOVuoto() {
        XCTAssertEqual(Quando.leggibile("boh"), "boh")
        XCTAssertEqual(Quando.leggibile(nil as String?), "")
    }

    func testRelativaEquivaleAlTesto() throws {
        let data = try XCTUnwrap(Quando.data("2026-11-08 18:30"))
        let ora = try XCTUnwrap(Quando.data("2026-11-03 12:00"))
        XCTAssertEqual(Quando.relativa(data, adesso: ora), Quando.leggibile("2026-11-08 18:30", adesso: ora))
    }

    /// Un momento già pronto (per esempio «Calcolata il …» nel Diario) resta con giorno e mese, senza «oggi».
    func testLeggibileDaDataConGiornoEMese() throws {
        let data = try XCTUnwrap(Quando.data("2026-10-31 10:05"))
        XCTAssertEqual(Quando.leggibile(data), "sab 31 ott, 10:05")
    }

    /// L'ora legale finisce il 25 ottobre 2026: tra le 18:30 di sabato e quelle di domenica passano 25 ore.
    func testCambioOraLegale() throws {
        let sabato = try XCTUnwrap(Quando.data("2026-10-24 18:30"))
        let domenica = try XCTUnwrap(Quando.data("2026-10-25 18:30"))
        XCTAssertEqual(domenica.timeIntervalSince(sabato), 25 * 3600, accuracy: 1)
    }
}
