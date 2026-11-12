import XCTest
@testable import Schieraxi

/// Quali «Da fare» si vedono: le voci tecniche solo a chi gestisce l'app, mai i consigli delle funzioni tolte (#634).
final class FunzioniLegaTests: XCTestCase {
    private func oggi(_ daFare: String) throws -> Oggi {
        try Decodifica.decodifica(Data(#"{"giornata": 11, "inizio": "2026-10-31 18:30", "da_fare": \#(daFare)}"#.utf8))
    }

    // Le voci dei menu le prova MenuLegaComeLaWebTests.

    func testLeImmaginiWebSpenteDalServerRestanoSpente() {
        let bloccate = StatoFunzioni(scelte: ["immagini_web": false])
        XCTAssertFalse(bloccate.acceso(Funzione.immaginiWeb), "il server le blocca: il pulsante non si vede")
        XCTAssertTrue(StatoFunzioni.tutteAccese.acceso(Funzione.immaginiWeb), "server vecchio: come prima")
    }

    func testUtenteNormaleNonVedeLeVociTecniche() throws {
        let o = try oggi(#"""
        [{"id": "1", "tipo": "dubbio", "testo": "Dubbio"}, {"id": "2", "tipo": "certificato", "testo": "Certificato"},
         {"id": "3", "tipo": "server", "testo": "Server"}, {"id": "4", "tipo": "backup", "testo": "Backup"},
         {"id": "5", "tipo": "rose", "testo": "Rose"}]
        """#)
        XCTAssertEqual(o.cose(tecniche: false).map(\.id), ["1", "5"])
        XCTAssertEqual(o.cose(tecniche: true).map(\.id), ["1", "2", "3", "5"], "la copia di sicurezza non si fa dall'app")
    }

    /// Cambi consigliati e Scambi non ci sono più (#634): il server manda ancora i loro consigli (li usa chi ha un'app vecchia)
    /// e l'app non li mostra, come la web (`DF_TIPI_TOLTI`). Il Diario si vede sempre: la sua voce resta.
    func testIConsigliDelleFunzioniTolteNonSiVedono() throws {
        let o = try oggi(#"""
        [{"id": "1", "tipo": "diario", "testo": "Diario"}, {"id": "2", "tipo": "scambio", "testo": "Scambio"},
         {"id": "3", "tipo": "svincolato", "testo": "Svincolato"}, {"id": "4", "tipo": "formazione", "testo": "Formazione"},
         {"id": "5", "tipo": "copertura", "testo": "Non hai nessun portiere disponibile"}]
        """#)
        XCTAssertEqual(o.cose(tecniche: true).map(\.id), ["1", "4", "5"])
        XCTAssertEqual(DaFareVoce.tipiTolti, ["svincolato", "scambio"])
    }

    /// Il reparto scoperto resta (è un avviso da non perdere) ma portava a Cambi consigliati: come sulla web il pulsante dice
    /// «Vedi la rosa» e apre la rosa della propria squadra. Le altre righe tengono il pulsante del server.
    func testIlRepartoScopertoApreLaRosa() throws {
        let o = try oggi(#"""
        [{"id": "copertura:P", "tipo": "copertura", "testo": "Non hai nessun portiere disponibile", "priorita": 1,
          "azione": "Cerca un rimpiazzo", "destinazione": {"scheda": "mercato", "sezione": null, "link": "schieraxi://mercato"}},
         {"id": "dubbio:1", "tipo": "dubbio", "testo": "Dubbio", "azione": "Apri la formazione",
          "destinazione": {"scheda": "formazione", "sezione": null, "link": "schieraxi://formazione"}},
         {"id": "senza", "tipo": "rose", "testo": "Rose", "destinazione": {"scheda": "lega", "sezione": "rose", "link": "schieraxi://lega/rose"}}]
        """#)
        let cose = o.cose(tecniche: false)
        let scoperto = try XCTUnwrap(cose.first { $0.tipo == "copertura" })
        XCTAssertTrue(scoperto.allaRosa)
        XCTAssertEqual(scoperto.testoPulsante, Catalogo.Lega.vediRosa)
        XCTAssertEqual(scoperto.destinazione?.destinazione, .sezione(.squadra), "l'indirizzo vecchio apre la scheda più vicina che resta")
        let dubbio = try XCTUnwrap(cose.first { $0.tipo == "dubbio" })
        XCTAssertFalse(dubbio.allaRosa)
        XCTAssertEqual(dubbio.testoPulsante, "Apri la formazione")
        let senza = try XCTUnwrap(cose.first { $0.tipo == "rose" })
        XCTAssertEqual(senza.testoPulsante, Catalogo.Df.apri, "senza il testo del server: «Apri»")
    }

    func testPiuGiornateFinitePerLaDiarioDiventanoUnaRiga() throws {
        let o = try oggi(#"""
        [{"id": "diario:6", "tipo": "diario", "testo": "La giornata 6 è finita: dimmi se hai schierato la consigliata.", "priorita": 3, "azione": "Ho schierato la consigliata", "destinazione": {"link": "schieraxi://lega"}},
         {"id": "diario:5", "tipo": "diario", "testo": "La giornata 5 è finita: dimmi se hai schierato la consigliata.", "priorita": 3},
         {"id": "9", "tipo": "dubbio", "testo": "Dubbio"}]
        """#)
        let cose = o.cose(tecniche: false)
        XCTAssertEqual(cose.count, 2)
        let riga = cose.first { $0.tipo == "diario" }
        XCTAssertEqual(riga?.testo, "Le giornate 5 e 6 sono finite: dimmi se hai schierato la consigliata.")
        XCTAssertEqual(riga?.azione, "Vedi")
        XCTAssertNotNil(riga?.destinazione)
    }

    func testUnaSolaGiornataFinitaResta() throws {
        let o = try oggi(#"[{"id": "diario:5", "tipo": "diario", "testo": "La giornata 5 è finita: dimmi se hai schierato la consigliata."}]"#)
        XCTAssertEqual(o.cose(tecniche: false).first?.id, "diario:5")
    }
}
