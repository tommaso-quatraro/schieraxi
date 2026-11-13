import XCTest
@testable import Schieraxi

/// Fantavoto atteso: «Perché questo numero» (campi `perche_numero` e `fv_atteso_medio_ruolo`). «Quanto ci abbiamo preso» sta
/// nella pagina Giornate (`PrecisioneTests`, `GiornateTests`). Tutti facoltativi: con un server vecchio non cambia niente.
final class FantavotoAttesoTests: XCTestCase {
    private func giocatore(_ extra: String) throws -> Giocatore {
        try Decodifica.decodifica(Data(#"{"id": 1, "nome": "Prova", "ruolo": "A", "p_voto": 0.7, "fv_atteso": 7.6\#(extra)}"#.utf8))
    }

    // MARK: Perché questo numero

    func testMotiviDecodificatiEScritti() throws {
        let g = try giocatore(#"""
        , "fv_atteso_medio_ruolo": 6.9,
          "perche_numero": [{"chiave": "gioca", "testo": "gioca il 70%: dubbio", "effetto": null},
                            {"chiave": "gol", "testo": "segna più della media del ruolo (41% di segnare)", "effetto": 1.12},
                            {"chiave": "partita", "testo": "partita difficile in casa", "effetto": -0.4}]
        """#)
        XCTAssertEqual(g.motiviNumero?.count, 3)
        XCTAssertEqual(g.mediaRuolo, 6.9)
        let p = try XCTUnwrap(PercheNumero(g))
        XCTAssertEqual(p.righe.map(\.testo), ["Gioca il 70%: dubbio", "Segna più della media del ruolo (41% di segnare)", "Partita difficile in casa"])
        XCTAssertEqual(p.righe.map(\.effetto), [nil, "+1,1", "−0,4"])
        XCTAssertEqual(p.righe.map(\.verso), [.avviso, .su, .giu])
        XCTAssertEqual(p.righe[0].voce, "Attenzione: gioca il 70%: dubbio")
        XCTAssertEqual(p.righe[2].voce, "meno 0,4: partita difficile in casa")
        XCTAssertEqual(p.nota, "Un giocatore medio del suo ruolo ha 6,9. Il resto sono differenze piccole.")
    }

    func testServerVecchioNienteRiquadro() throws {
        let g = try giocatore("")
        XCTAssertNil(g.motiviNumero)
        XCTAssertNil(g.mediaRuolo)
        XCTAssertNil(PercheNumero(g))
        // le fixture di oggi (server senza i campi nuovi) si leggono come prima
        let f: Formazione = try Fixture.decodifica("formazione")
        XCTAssertFalse(f.titolari.isEmpty)
        XCTAssertTrue(f.titolari.allSatisfy { PercheNumero($0) == nil })
    }

    func testNessunMotivoMaConLaMedia() throws {
        let g = try giocatore(#", "perche_numero": [], "fv_atteso_medio_ruolo": 7.0"#)
        let p = try XCTUnwrap(PercheNumero(g))
        XCTAssertTrue(p.righe.isEmpty)
        XCTAssertEqual(p.nota, "Nessun motivo spicca: il numero è vicino a quello di un giocatore medio del suo ruolo, che ha 7,0.")
        // lista vuota e niente media: non c'è niente da dire
        XCTAssertNil(PercheNumero(try giocatore(#", "perche_numero": [], "fv_atteso_medio_ruolo": null"#)))
    }

    func testCampiStraniNonRomponoLaScheda() throws {
        // tipo sbagliato: la scheda si legge, il riquadro no
        let g = try giocatore(#", "perche_numero": "boh", "fv_atteso_medio_ruolo": "sei""#)
        XCTAssertEqual(g.fvAtteso, 7.6)
        XCTAssertNil(g.motiviNumero)
        XCTAssertNil(g.mediaRuolo)
        // un elemento sbagliato si salta, gli altri restano; senza testo non si mostra; chiave nuova senza numero = neutro
        let h = try giocatore(#"""
        , "perche_numero": [42, {"chiave": "voti", "testo": "", "effetto": 0.3}, {"chiave": "meteo", "testo": "campo pesante", "effetto": "x"},
                            {"testo": "rigorista", "effetto": 0.5}, {"chiave": "assist", "testo": "fa più assist", "effetto": 0.2}]
        """#)
        let p = try XCTUnwrap(PercheNumero(h))
        XCTAssertEqual(p.righe.map(\.testo), ["Campo pesante", "Rigorista", "Fa più assist"])
        XCTAssertEqual(p.righe.map(\.verso), [.neutro, .su, .su])
        XCTAssertEqual(p.righe[1].chiave, "altro")
        XCTAssertEqual(p.nota, "I numeri sono le differenze rispetto a un giocatore medio del suo ruolo.")
    }

    func testAlMassimoTreMotiviENienteAssenti() throws {
        let quattro = (1...4).map { #"{"chiave": "altro", "testo": "motivo \#($0)", "effetto": 0.\#($0)}"# }.joined(separator: ",")
        let p = try XCTUnwrap(PercheNumero(try giocatore(", \"perche_numero\": [\(quattro)]")))
        XCTAssertEqual(p.righe.count, 3)
        XCTAssertNil(PercheNumero(try giocatore(#", "assente": true, "perche_numero": [{"testo": "x", "effetto": 1}]"#)))
    }

    func testSegnoEPiccoliEffetti() {
        XCTAssertEqual(FantavotoAtteso.conSegno(1.12), "+1,1")
        XCTAssertEqual(FantavotoAtteso.conSegno(-0.4), "−0,4")
        XCTAssertEqual(FantavotoAtteso.conSegno(0.04), "+0,04")
        XCTAssertEqual(FantavotoAtteso.conSegnoVoce(-1.26), "meno 1,3")
    }
}
