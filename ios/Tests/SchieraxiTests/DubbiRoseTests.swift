import XCTest
@testable import Schieraxi

// Giocatori da sistemare: solo nomi e indirizzi finti.

final class DubbiRoseTests: XCTestCase {
    func testTrovaSoloIGiocatoriSenzaCodice() throws {
        let json = """
        [{"nome": "Squadra A", "giocatori": [{"id": 1, "nome": "Rossi"}, {"id": null, "nome": "Bianchi M."}]},
         {"nome": "Squadra B", "giocatori": [{"nome": "Verdi"}, {"id": 7, "nome": "Neri"}]}]
        """
        let rose: [Rosa] = try Decodifica.decodifica(Data(json.utf8))
        let dubbi = DubbiRose.trova(in: rose)
        XCTAssertEqual(dubbi.map(\.nome), ["Bianchi M.", "Verdi"])
        XCTAssertEqual(dubbi.map(\.squadra), ["Squadra A", "Squadra B"])
    }

    @MainActor
    func testAbbinaMandaLaCorrezioneERimuoveIlDubbio() async throws {
        let server = ServerDiProva { _, percorso, _ in
            if percorso.hasPrefix("/api/squadre") { return Data(#"[{"nome": "Squadra A"}]"#.utf8) }
            if percorso.hasPrefix("/api/rosa") { return Data(#"{"nome": "Squadra A", "giocatori": [{"id": null, "nome": "Bianchi M."}]}"#.utf8) }
            return Data("{}".utf8)
        }
        let vm = DubbiRoseViewModel(server: server)
        await vm.carica()
        XCTAssertEqual(vm.dubbi.count, 1)
        let giusto = GiocatoreBreve(id: 42, nome: "Bianchi", ruolo: "C", squadra: "Prova", quotazione: nil)
        await vm.abbina(vm.dubbi[0], a: giusto)
        XCTAssertTrue(vm.dubbi.isEmpty)
        XCTAssertEqual(vm.sistemati, 1)
        let corpo = try XCTUnwrap(server.corpiInviati(a: "/api/rose/correggi").first)
        let testo = String(decoding: corpo, as: UTF8.self)
        XCTAssertTrue(testo.contains("\"id\":42"))
        XCTAssertTrue(testo.contains("Squadra A"))
    }
}
