import XCTest
@testable import Schieraxi

/// Scheda del giocatore ed elenco: numeri e colori che si spiegano da soli.
@MainActor
final class SchedaChiaraTests: XCTestCase {
    private func giocatore(_ extra: String) throws -> Giocatore {
        let json = "{\(extra) \"id\": 7, \"nome\": \"Retalli\", \"ruolo\": \"A\", \"punti_attesi\": 7.2, \"p_voto\": 0.9}"
        return try Decodifica.decodifica(Data(json.utf8))
    }

    func testGolAttesiConINomiDelleSquadre() throws {
        let g = try giocatore(#""squadra": "genoa", "avversario": "como", "gol_squadra": 1.8, "gol_avversario": 1.2,"#)
        XCTAssertEqual(GiocatoreCorpo.golAttesi(g, squadra: "GENOA"), "Gol attesi: Genoa 1,8 · Como 1,2")
        XCTAssertEqual(GiocatoreCorpo.golAttesi(g, squadra: nil), "Gol attesi: Genoa 1,8 · Como 1,2")
        let senzaNomi = try giocatore(#""gol_squadra": 1.8, "gol_avversario": 1.2,"#)
        XCTAssertEqual(GiocatoreCorpo.golAttesi(senzaNomi, squadra: nil), "Gol attesi: 1,8 fatti, 1,2 subiti")
        XCTAssertNil(GiocatoreCorpo.golAttesi(try giocatore(""), squadra: "Genoa"))
    }

    func testLEtichettaDiTitolaritaDiceCheEDellaProbabili() throws {
        let g = try giocatore(#""titolarita": "titolare", "stato": "titolare", "percentuale": 90,"#)
        XCTAssertEqual(g.etichette.first?.testo, "Titolare · probabili 90%", "non si confonde con «gioca 88%»")
    }

    func testLaLegendaDellElencoSpiegaAnelloEPercentuale() {
        XCTAssertTrue(ClassificaView.legenda.contains("indice"))
        XCTAssertTrue(ClassificaView.legenda.contains("gioca"))
    }

    func testLaSchedaCaricaTuttoInsieme() async throws {
        let s = ServerDiProva.conFixture(["/api/giocatore/": "giocatore", "/api/calendario": "calendario",
                                          "/api/osservati": "osservati", "/api/formazione": "formazione"])
        let vm = SchedaGiocatoreViewModel(id: 1, server: s)
        await vm.carica()
        XCTAssertNotNil(vm.caricatore.dato)
        XCTAssertNotNil(vm.calendario.dato)
        XCTAssertNotNil(vm.formazione.dato)
        XCTAssertNotNil(vm.osservato)
    }
}
