import XCTest
@testable import Schieraxi

final class ConfrontoDiarioTests: XCTestCase {
    private func voce(_ json: String) throws -> VoceDiario {
        try Decodifica.decodifica(Data(json.utf8))
    }

    private func titolari(_ ids: [Int], ruoli: [String]? = nil) -> String {
        "[" + ids.enumerated().map { #"{"id": \#($0.element), "nome": "G\#($0.element)", "ruolo": "\#(ruoli?[$0.offset] ?? "C")"}"# }.joined(separator: ",") + "]"
    }

    func testIstantaneaESchierataConDueCambi() throws {
        let v = try voce("""
        {"giornata": 9, "stagione": "2026-27",
         "istantanea": {"giornata": 9, "modulo": "3-4-3", "titolari": \(titolari([1, 2, 3, 4])), "panchina": [{"id": 50, "nome": "Pan"}, {"id": 51, "nome": "China"}],
                        "atteso": 68.5, "stile": "Equilibrato", "calcolata": "2026-10-31T10:05:00"},
         "consigliata": {"modulo": "4-3-3", "titolari": \(titolari([1, 2])), "reale": 70.0},
         "schierata": {"modulo": "3-5-2", "titolari": \(titolari([1, 2, 7, 8]))}}
        """)
        let c = try XCTUnwrap(v.confronto)
        XCTAssertTrue(c.registrata)
        XCTAssertEqual(c.titoloConsigliata, "Cosa consigliava SchieraXI (3-4-3)")
        XCTAssertEqual(c.sottoConsigliata, "Calcolata il sab 31 ott, 10:05 · Equilibrato")
        XCTAssertEqual(c.titoloSchierata, "Cosa hai schierato (3-5-2)")
        XCTAssertEqual(c.cambiati, 2)
        XCTAssertEqual(c.fraseCambi, "Hai cambiato 2: G7 e G8 al posto di G3 e G4.")
        XCTAssertEqual(c.consigliata.filter(\.diverso).map(\.nome), ["G3", "G4"])
        XCTAssertEqual(c.schierata?.filter(\.diverso).map(\.nome), ["G7", "G8"])
        XCTAssertEqual(c.panchina, "Panchina: Pan, China")
    }

    func testUnSoloCambio() throws {
        let v = try voce(#"{"giornata": 1, "istantanea": {"modulo": "3-4-3", "titolari": \#(titolari([1, 2]))}, "schierata": {"titolari": \#(titolari([1, 9]))}}"#)
        XCTAssertEqual(try XCTUnwrap(v.confronto).fraseCambi, "Hai cambiato 1: G9 al posto di G2.")
    }

    func testStessiSchieraxi() throws {
        let v = try voce(#"{"giornata": 1, "istantanea": {"modulo": "3-4-3", "titolari": \#(titolari([1, 2]))}, "schierata": {"titolari": \#(titolari([2, 1]))}}"#)
        let c = try XCTUnwrap(v.confronto)
        XCTAssertEqual(c.fraseCambi, "Hai schierato gli stessi 11 consigliati.")
        XCTAssertEqual(c.cambiati, 0)
    }

    func testNienteSchierataMostraSoloLaConsigliata() throws {
        let v = try voce(#"{"giornata": 1, "istantanea": {"modulo": "3-4-3", "titolari": \#(titolari([1, 2]))}}"#)
        let c = try XCTUnwrap(v.confronto)
        XCTAssertNil(c.schierata)
        XCTAssertNil(c.fraseCambi)
        XCTAssertNil(c.titoloSchierata)
        XCTAssertTrue(c.consigliata.allSatisfy { !$0.diverso })
    }

    func testSenzaIstantaneaUsaLaRicostruzioneEDiceCheNonEraRegistrata() throws {
        for json in [#"{"giornata": 1, "consigliata": {"modulo": "4-3-3", "titolari": \#(titolari([1, 2]))}}"#,
                     #"{"giornata": 1, "istantanea": null, "consigliata": {"modulo": "4-3-3", "titolari": \#(titolari([1, 2]))}}"#] {
            let c = try XCTUnwrap(try voce(json).confronto)
            XCTAssertFalse(c.registrata)
            XCTAssertEqual(c.titoloConsigliata, "Ricostruita oggi (4-3-3)")
            XCTAssertTrue(c.sottoConsigliata.hasPrefix("Consigliata non registrata"))
        }
    }

    func testNienteDaMostrare() throws {
        XCTAssertNil(try voce(#"{"giornata": 8}"#).confronto)
        XCTAssertNil(try voce(#"{"giornata": 8, "istantanea": {"modulo": "3-4-3", "titolari": []}}"#).confronto)
    }

    func testDecodificaTolleranteConCampiStrani() throws {
        // istantanea in un formato che non conosco = non registrata; calcolata rotta = niente ora; stile null; ruoli e id mancanti.
        let v = try voce(#"{"giornata": 2, "istantanea": "boh", "consigliata": {"modulo": "3-4-3", "titolari": [{"nome": "A"}]}}"#)
        XCTAssertNil(v.istantanea)
        XCTAssertFalse(try XCTUnwrap(v.confronto).registrata)
        let w = try voce(#"{"giornata": 2, "istantanea": {"modulo": "3-4-3", "titolari": [{"nome": "A"}, {"id": 5}], "stile": null, "calcolata": "ieri"}}"#)
        let c = try XCTUnwrap(w.confronto)
        XCTAssertEqual(c.sottoConsigliata, "")
        XCTAssertEqual(c.consigliata.map(\.nome), ["A", "–"])
    }

    func testRisposteVecchieSenzaIstantaneaSiLeggonoLoStesso() throws {
        let d: DiarioRisposta = try Decodifica.decodifica(Data(#"{"giornate": [{"giornata": 9, "stagione": "2026-27"}, {"giornata": 8}], "sintesi": {"giornate": 0}}"#.utf8))
        XCTAssertEqual(d.giornate?.count, 2)
        XCTAssertNil(d.giornate?.first?.istantanea)
    }

    func testOrdinePerRuoloEPluraleDellElenco() throws {
        let v = try voce(#"{"giornata": 1, "istantanea": {"modulo": "3-4-3", "titolari": [{"id": 1, "nome": "Att", "ruolo": "A"}, {"id": 2, "nome": "Por", "ruolo": "P"}, {"id": 3, "nome": "Dif", "ruolo": "D"}]}}"#)
        XCTAssertEqual(try XCTUnwrap(v.confronto).consigliata.map(\.ruolo), ["P", "D", "A"])
        XCTAssertEqual(ConfrontoDiario.elenco(["A"]), "A")
        XCTAssertEqual(ConfrontoDiario.elenco(["A", "B", "C"]), "A, B e C")
    }

    func testChiSchieraLaConsigliataLoDice() throws {
        let v = try voce(#"{"giornata": 1, "istantanea": {"modulo": "3-4-3", "titolari": \#(titolari([1]))}, "schierata": {"modulo": "3-4-3", "tipo": "consigliata", "titolari": \#(titolari([1]))}}"#)
        XCTAssertEqual(try XCTUnwrap(v.confronto).titoloSchierata, "Cosa hai schierato: la consigliata (3-4-3)")
    }
}
