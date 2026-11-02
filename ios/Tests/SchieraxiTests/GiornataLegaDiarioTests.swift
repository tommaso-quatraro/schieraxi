import XCTest
@testable import Schieraxi

/// Il Diario e il widget «Attesi e fatti» usano il numero della giornata della lega, come Oggi e la web («Giornata 8»).
final class GiornataLegaDiarioTests: XCTestCase {
    private func voce(_ json: String) throws -> VoceDiario {
        try Decodifica.decodifica(Data(json.utf8))
    }

    func testIlDiarioMostraIlNumeroDellaLega() throws {
        let v = try voce(#"{"giornata": 11, "giornata_lega": 8, "stagione": "2026-27"}"#)
        XCTAssertEqual(v.titolo, "Giornata 8", "come la web: il numero della lega, senza quello di Serie A")
        XCTAssertEqual(v.numero, 8)
        XCTAssertEqual(v.giornata, 11, "al server si manda sempre il numero di Serie A")
    }

    func testSenzaNumeroDiLegaRestaQuelloDiSerieA() {
        let v = try? voce(#"{"giornata": 11}"#)
        XCTAssertEqual(v?.titolo, "Giornata 11")
        XCTAssertEqual(v?.numero, 11)
        let nulla = try? voce(#"{"giornata": 11, "giornata_lega": null}"#)
        XCTAssertEqual(nulla?.numero, 11)
        let vuota = try? voce("{}")
        XCTAssertEqual(vuota?.titolo, "Giornata", "mai «Giornata 0»")
    }

    func testIPuntiDelGraficoUsanoIlNumeroDellaLega() throws {
        let v = try voce(#"{"giornata": 11, "giornata_lega": 8, "stagione": "2026-27", "atteso_vs_fatto": {"atteso": 70, "fatti": 72, "basso": 60, "alto": 80, "dentro": true}}"#)
        let punti = PuntoAttesoFatto.elenco([v])
        XCTAssertEqual(punti.map(\.giornata), [8])
    }

    func testIlWidgetRiportaLeGiornateDelDiarioAlNumeroDellaLega() throws {
        let json = #"""
        {"giornata": 11, "giornata_lega": 8, "diario": [
          {"giornata": 10, "attesi": 66, "fatti": 63.5},
          {"giornata": 9, "attesi": 67, "fatti": 70},
          {"giornata": 3, "attesi": 60, "fatti": 61}]}
        """#
        let w = try XCTUnwrap(RiassuntoWidget.leggi(Data(json.utf8)))
        XCTAssertEqual(w.giornateGiocate.map(\.giornata), [7, 6, 3], "stesso scarto della giornata attuale; prima della lega resta Serie A")
        XCTAssertEqual(w.numeroDiLega(11), 8)
        let senza = try XCTUnwrap(RiassuntoWidget.leggi(Data(#"{"giornata": 11, "diario": [{"giornata": 10, "attesi": 66, "fatti": 63.5}]}"#.utf8)))
        XCTAssertEqual(senza.giornateGiocate.map(\.giornata), [10])
    }

    func testPluraleDelleGiornateInSintesi() {
        XCTAssertEqual(Formato.giornate(1), "1 giornata")
        XCTAssertEqual(Formato.giornate(4), "4 giornate")
    }
}
