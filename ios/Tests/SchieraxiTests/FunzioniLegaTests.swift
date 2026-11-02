import XCTest
@testable import Schieraxi

/// Quali voci di menu e quali «Da fare» vede un utente normale.
final class FunzioniLegaTests: XCTestCase {
    private func oggi(_ daFare: String) throws -> Oggi {
        try Decodifica.decodifica(Data(#"{"giornata": 11, "inizio": "2026-10-31 18:30", "da_fare": \#(daFare)}"#.utf8))
    }

    func testIlCalendarioSiVedeSoloSeNominatoOConMostraTutte() {
        XCTAssertFalse(StatoFunzioni.tutteAccese.vedeCalendario, "una chiave che manca vale spenta")
        XCTAssertFalse(StatoFunzioni(scelte: ["elenco_giocatori": true]).vedeCalendario, "non dipende più dall'elenco dei giocatori")
        XCTAssertTrue(StatoFunzioni(scelte: ["calendario": true]).vedeCalendario)
        XCTAssertTrue(StatoFunzioni(scelte: [:], mostraTutte: true).vedeCalendario)
    }

    func testLeImmaginiWebConMostraTutteRestanoSpenteSeIlServerLeBlocca() {
        let bloccate = StatoFunzioni(scelte: ["immagini_web": false], mostraTutte: true)
        XCTAssertTrue(bloccate.acceso(Funzione.immaginiWeb), "per i menu «Mostra tutte» apre tutto")
        XCTAssertFalse(bloccate.accesoDavvero(Funzione.immaginiWeb), "ma il server le blocca: il pulsante non si vede")
        XCTAssertTrue(StatoFunzioni.tutteAccese.accesoDavvero(Funzione.immaginiWeb), "server vecchio: come prima")
    }

    func testUtenteNormaleNonVedeLeVociTecniche() throws {
        let o = try oggi(#"""
        [{"id": "1", "tipo": "dubbio", "testo": "Dubbio"}, {"id": "2", "tipo": "certificato", "testo": "Certificato"},
         {"id": "3", "tipo": "server", "testo": "Server"}, {"id": "4", "tipo": "backup", "testo": "Backup"},
         {"id": "5", "tipo": "rose", "testo": "Rose"}]
        """#)
        XCTAssertEqual(o.cose(funzioni: .tutteAccese, tecniche: false).map(\.id), ["1", "5"])
        XCTAssertEqual(o.cose(funzioni: .tutteAccese, tecniche: true).map(\.id), ["1", "2", "3", "5"], "la copia di sicurezza non si fa dall'app")
    }

    func testLeCoseDiUnaFunzioneSpentaNonSiVedono() throws {
        let o = try oggi(#"""
        [{"id": "1", "tipo": "diario", "testo": "Diario"}, {"id": "2", "tipo": "scambio", "testo": "Scambio"},
         {"id": "3", "tipo": "backup", "testo": "Backup"}, {"id": "4", "tipo": "formazione", "testo": "Formazione"}]
        """#)
        let spente = StatoFunzioni(scelte: ["diario": false, "scambi_trova": false, "backup": false])
        XCTAssertEqual(o.cose(funzioni: spente, tecniche: true).map(\.id), ["4"])
    }

    func testPiuGiornateFinitePerLaDiarioDiventanoUnaRiga() throws {
        let o = try oggi(#"""
        [{"id": "diario:6", "tipo": "diario", "testo": "La giornata 6 è finita: dimmi se hai schierato la consigliata.", "priorita": 3, "azione": "Ho schierato la consigliata", "destinazione": {"link": "schieraxi://lega"}},
         {"id": "diario:5", "tipo": "diario", "testo": "La giornata 5 è finita: dimmi se hai schierato la consigliata.", "priorita": 3},
         {"id": "9", "tipo": "dubbio", "testo": "Dubbio"}]
        """#)
        let cose = o.cose(funzioni: .tutteAccese, tecniche: false)
        XCTAssertEqual(cose.count, 2)
        let riga = cose.first { $0.tipo == "diario" }
        XCTAssertEqual(riga?.testo, "Le giornate 5 e 6 sono finite: dimmi se hai schierato la consigliata.")
        XCTAssertEqual(riga?.azione, "Vedi")
        XCTAssertNotNil(riga?.destinazione)
    }

    func testUnaSolaGiornataFinitaResta() throws {
        let o = try oggi(#"[{"id": "diario:5", "tipo": "diario", "testo": "La giornata 5 è finita: dimmi se hai schierato la consigliata."}]"#)
        XCTAssertEqual(o.cose(funzioni: .tutteAccese, tecniche: false).first?.id, "diario:5")
    }

    func testCreditiSoloSeIlServerLiAccendeMovimentiSeNonSpenti() {
        XCTAssertFalse(StatoFunzioni.tutteAccese.accesoSoloSeNominato(Funzione.crediti))
        XCTAssertTrue(StatoFunzioni(scelte: ["crediti": true]).accesoSoloSeNominato(Funzione.crediti))
        XCTAssertTrue(StatoFunzioni.tutteAccese.acceso(Funzione.movimenti), "server senza la chiave: acceso")
        XCTAssertFalse(StatoFunzioni(scelte: ["movimenti": false]).acceso(Funzione.movimenti))
    }
}
