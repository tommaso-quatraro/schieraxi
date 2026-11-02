import XCTest
@testable import Schieraxi

final class ScelteTueTests: XCTestCase {
    private func leggi(_ json: String) throws -> ScelteTue {
        try Decodifica.decodifica(Data(json.utf8))
    }

    func testBloccoCompleto() throws {
        let s = try leggi("""
        {"giornate": 9, "meglio_tua": 5, "meglio_consigliata": 3, "pari": 1, "punti_differenza": 4.5, "percentuale_tua": 56, "pochi_dati": false,
         "per_giornata": [{"stagione": "2026-27", "giornata": 9, "hai_scelto": ["Orsetti"], "consigliava": ["Dunfrey"],
                           "punti_tua": 63.5, "punti_consigliata": 71.0, "differenza": -7.5, "esito": "consigliata"}]}
        """)
        let t = try XCTUnwrap(ScelteTueTesto(s))
        XCTAssertEqual(t.numeroGrande, "5 su 9")
        XCTAssertEqual(t.fraseCommento, "Hai avuto ragione nel 56% delle giornate.")
        XCTAssertEqual(t.frasePunti, "In totale +4,5 punti rispetto al consiglio: ci hai guadagnato.")
        XCTAssertEqual(t.righe.first?.frase, "Hai messo Orsetti al posto di Dunfrey.")
        XCTAssertEqual(t.righe.first?.esito, .consigliata)
        XCTAssertTrue(t.voceRiepilogo.contains("meglio tu 5 volte"))
    }

    func testPochiDatiNonCommentaLaPercentuale() throws {
        let s = try leggi(#"{"giornate": 3, "meglio_tua": 1, "meglio_consigliata": 2, "pari": 0, "punti_differenza": -1.0, "percentuale_tua": 33, "pochi_dati": true, "per_giornata": []}"#)
        let t = try XCTUnwrap(ScelteTueTesto(s))
        XCTAssertTrue(t.fraseCommento.hasPrefix("Ancora pochi dati"))
        XCTAssertFalse(t.fraseCommento.contains("33"))
        XCTAssertEqual(t.frasePunti, "In totale −1,0 punto rispetto al consiglio: ci hai perso.")
        XCTAssertTrue(t.sottotitolo.hasPrefix("volta "), "1 su 3: «volta» al singolare")
    }

    func testPluraliGiusti() {
        XCTAssertEqual(ScelteTueTesto.volte(1), "1 volta")
        XCTAssertEqual(ScelteTueTesto.volte(0), "0 volte")
        XCTAssertEqual(ScelteTueTesto.volte(2), "2 volte")
    }

    func testCampoMancanteOVuotoNonMostraNiente() throws {
        XCTAssertNil(ScelteTueTesto(nil))
        XCTAssertNil(ScelteTueTesto(try leggi(#"{"giornate": 0, "pochi_dati": true, "per_giornata": []}"#)))
        let d: DiarioRisposta = try Decodifica.decodifica(Data(#"{"giornate": [], "sintesi": {"giornate": 0}}"#.utf8))
        XCTAssertNil(d.scelteTue)
        XCTAssertNil(ScelteTueTesto(d.scelteTue))
    }

    func testDecodificaTolleranteConCampiStrani() throws {
        let s = try leggi(#"{"giornate": 10, "meglio_tua": 4, "per_giornata": [{"giornata": 2, "esito": "boh"}, {"hai_scelto": ["A", "B"], "consigliava": ["C", "D"], "esito": "tua"}]}"#)
        let t = try XCTUnwrap(ScelteTueTesto(s))
        XCTAssertEqual(t.righe.count, 2)
        XCTAssertEqual(t.righe[0].esito, .pari)
        XCTAssertEqual(t.righe[0].frase, "Hai scelto undici diversi da quelli consigliati.")
        XCTAssertEqual(t.righe[1].frase, "Hai messo A e B al posto di C e D.")
        XCTAssertEqual(t.percentuale, 40, "senza percentuale dal server la si calcola dai conteggi")
        XCTAssertFalse(t.pochiDati)
    }
}
