import XCTest
@testable import Schieraxi

/// Stili della formazione con i nomi del server e la frase della stella; testo che va a capo solo tra i pezzi.
final class StileFormazioneTests: XCTestCase {
    private func livello(rischio: Int, nome: String, modulo: String, moduli: [(String, Double)]) throws -> LivelloRischio {
        let elenco = moduli.map { "{\"modulo\": \"\($0.0)\", \"punteggio_atteso\": \($0.1), \"titolari\": [], \"panchina\": []}" }
            .joined(separator: ",")
        let json = "{\"rischio\": \(rischio), \"nome\": \"\(nome)\", \"modulo\": \"\(modulo)\", \"punteggio_atteso\": 70, \"moduli\": [\(elenco)]}"
        return try Decodifica.decodifica(Data(json.utf8))
    }

    func testINomiSonoQuelliDelServer() {
        XCTAssertEqual(StileFormazione.nomi[-2], "Molto sicura")
        XCTAssertEqual(StileFormazione.nomi[-1], "Sicura")
        XCTAssertEqual(StileFormazione.nomi[0], "Equilibrata")
        XCTAssertEqual(StileFormazione.nomi[1], "Rischiosa")
        XCTAssertEqual(StileFormazione.nomi[2], "Molto rischiosa")
        XCTAssertTrue(StileFormazione.descrizione(0).hasPrefix("La via di mezzo"), "Equilibrata non promette il massimo dei punti")
    }

    func testLaStellaSiSpiegaSoloSeUnAltroModuloHaDiPiu() throws {
        let prudente = try livello(rischio: 0, nome: "Equilibrata", modulo: "3-4-3", moduli: [("3-4-3", 73.7), ("4-3-3", 74.3)])
        XCTAssertEqual(StileFormazione.stellaNonMassimo(prudente),
                       "Il 4-3-3 ha qualche decimo di punti attesi in più, ma con titolari meno sicuri: con lo stile «Equilibrata» il 3-4-3 è la scelta più prudente.")
        let pari = try livello(rischio: 0, nome: "Equilibrata", modulo: "3-4-3", moduli: [("3-4-3", 73.71), ("4-3-3", 73.74)])
        XCTAssertNil(StileFormazione.stellaNonMassimo(pari), "a schermo uguali: niente da spiegare")
        let massimo = try livello(rischio: -1, nome: "Sicura", modulo: "4-3-3", moduli: [("3-4-3", 73.7), ("4-3-3", 74.3)])
        XCTAssertNil(StileFormazione.stellaNonMassimo(massimo))
        let rischiosa = try livello(rischio: 1, nome: "Rischiosa", modulo: "3-4-3", moduli: [("3-4-3", 73.7), ("4-3-3", 74.3)])
        XCTAssertNil(StileFormazione.stellaNonMassimo(rischiosa), "solo gli stili prudenti")
    }

    func testLaFasciaVaACapoSoloTraIPezzi() {
        let t = TestoACapo.soloTraIPezzi("punti attesi · tra 66 e 82 · 8 volte su 10")
        XCTAssertEqual(t.components(separatedBy: " · ").count, 3)
        XCTAssertFalse(t.replacingOccurrences(of: " · ", with: "").contains(" "), "dentro i pezzi niente spazi che si spezzano")
        XCTAssertTrue(t.contains("8\u{00A0}volte\u{00A0}su\u{00A0}10"))
    }
}
