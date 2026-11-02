import XCTest
@testable import Schieraxi

/// La fascia «tra X e Y · 8 volte su 10» al posto di «oscilla di ±N».
final class IntervalloPuntiTests: XCTestCase {
    private func leggi(_ json: String) throws -> IntervalloPunti {
        try Decodifica.decodifica(Data(json.utf8))
    }

    func testTestoConFasciaCompleta() throws {
        let i = try leggi(#"{"basso": 61.6, "alto": 84.2, "confidenza": 0.8, "indicativo": false}"#)
        XCTAssertEqual(i.testo, "tra 62 e 84 · 8 volte su 10")
    }

    func testIndicativoSiDice() throws {
        let i = try leggi(#"{"basso": 60, "alto": 80, "confidenza": 0.8, "indicativo": true}"#)
        XCTAssertEqual(i.testo, "tra 60 e 80 · 8 volte su 10 (indicativo)")
    }

    func testSenzaConfidenzaNonSiInventa() throws {
        XCTAssertEqual(try leggi(#"{"basso": 60, "alto": 80}"#).testo, "tra 60 e 80")
        XCTAssertEqual(try leggi(#"{"basso": 60, "alto": 80, "confidenza": 0.95}"#).testo, "tra 60 e 80 · 19 volte su 20")
        XCTAssertEqual(try leggi(#"{"basso": 60, "alto": 80, "confidenza": 7}"#).testo, "tra 60 e 80", "valore assurdo ignorato")
    }

    func testCampiMancantiOSbagliatiNonRompono() throws {
        XCTAssertNil(try leggi("{}").testo)
        XCTAssertNil(try leggi(#"{"basso": 90, "alto": 10}"#).testo, "estremi al contrario")
        XCTAssertNil(try leggi(#"{"basso": "boh", "alto": 10}"#).testo)
        let o: Formazione? = try? Decodifica.decodifica(Data(#"{"giornata": 9, "modulo": "3-4-3", "punteggio_atteso": 60, "titolari": [], "panchina": [], "intervallo": "boh"}"#.utf8))
        XCTAssertNotNil(o, "una fascia sbagliata non rompe la formazione")
        XCTAssertNil(o?.intervallo?.testo)
    }

    func testRipiegoSuOscillaDi() throws {
        XCTAssertEqual(IntervalloPunti.frase(nil, dev: 3.2), "oscilla di ±3")
        XCTAssertEqual(IntervalloPunti.frase(try leggi("{}"), dev: 3.2), "oscilla di ±3", "fascia vuota: si usa la deviazione")
        XCTAssertEqual(IntervalloPunti.frase(try leggi(#"{"basso": 1, "alto": 5, "confidenza": 0.8}"#), dev: 3.2), "tra 1 e 5 · 8 volte su 10")
        XCTAssertNil(IntervalloPunti.frase(nil, dev: nil))
        XCTAssertNil(IntervalloPunti.frase(nil, dev: .nan))
    }

    @MainActor
    func testLaFormazioneMostraLaFasciaDelModuloScelto() async throws {
        let json = """
        {"giornata": 9, "modulo": "3-4-3", "punteggio_atteso": 60, "dev": 3, "titolari": [], "panchina": [],
         "intervallo": {"basso": 52, "alto": 70, "confidenza": 0.8, "indicativo": true},
         "livelli": [{"rischio": 0, "nome": "Equilibrata", "modulo": "3-4-3", "punteggio_atteso": 60,
                      "intervallo": {"basso": 52, "alto": 70, "confidenza": 0.8, "indicativo": true},
                      "moduli": [{"modulo": "3-4-3", "punteggio_atteso": 60, "dev": 3, "titolari": [], "panchina": [],
                                  "intervallo": {"basso": 52, "alto": 70, "confidenza": 0.8, "indicativo": true}},
                                 {"modulo": "4-3-3", "punteggio_atteso": 58, "dev": 3, "titolari": [], "panchina": [],
                                  "intervallo": {"basso": 50, "alto": 67, "confidenza": 0.8, "indicativo": false}},
                                 {"modulo": "3-5-2", "punteggio_atteso": 57, "dev": 2.6, "titolari": [], "panchina": []}]}]}
        """
        let f: Formazione = try Decodifica.decodifica(Data(json.utf8))
        let vm = FormazioneViewModel(server: ServerDiProva { _, _, _ in Data("{}".utf8) })
        XCTAssertEqual(vm.fascia(f), "tra 52 e 70 · 8 volte su 10 (indicativo)")
        vm.moduloScelto = "4-3-3"
        XCTAssertEqual(vm.fascia(f), "tra 50 e 67 · 8 volte su 10")
        vm.moduloScelto = "3-5-2"
        XCTAssertEqual(vm.fascia(f), "oscilla di ±3", "il modulo non ha la fascia: si ripiega sulla sua deviazione")
    }
}
