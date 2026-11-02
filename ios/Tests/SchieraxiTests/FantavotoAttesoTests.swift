import XCTest
@testable import Schieraxi

/// Fantavoto atteso: «Perché questo numero» (campi `perche_numero` e `fv_atteso_medio_ruolo`) e «Quanto ci abbiamo preso»
/// del Diario (`affidabilita`, `atteso_vs_fatto`). Tutti facoltativi: con un server vecchio non cambia niente.
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

    // MARK: Diario: quanto ci abbiamo preso

    private func diario(_ json: String) throws -> DiarioRisposta {
        try Decodifica.decodifica(Data(json.utf8))
    }

    func testAffidabilitaInLinea() throws {
        let d = try diario(#"""
        {"affidabilita": {"giornate": 10, "scarto_medio": 4.2, "errore_medio": -1.5, "punti_medi_attesi": 68.4, "punti_medi_fatti": 66.9,
                          "dentro_fascia": 8, "con_fascia": 10, "percentuale_dentro": 80, "fascia_dichiarata": 80, "pochi_dati": false,
                          "giornate_minime": 8, "giudizio": "in_linea"},
         "giornate": []}
        """#)
        let t = try XCTUnwrap(TestoAffidabilita(d.affidabilita))
        XCTAssertEqual(t.dentro, "8/10")
        XCTAssertEqual(t.scarto, "4,2")
        XCTAssertEqual(t.media, "66,9 / 68,4")
        XCTAssertEqual(t.riga, "Su 10 giornate i punti fatti sono caduti nella fascia prevista 8 volte, l'80% (dichiarato: 8 volte su 10).")
        XCTAssertEqual(t.verso, "In media i punti fatti sono stati 1,5 punti in meno di quelli previsti.")
        XCTAssertEqual(t.giudizio, "È in linea con quello che dichiariamo.")
        XCTAssertFalse(t.fuoriLinea)
        XCTAssertFalse(t.pochiDati)
    }

    func testAffidabilitaAncheQuandoVaMale() throws {
        let a = AffidabilitaDiario(giornate: 12, scartoMedio: 9.1, erroreMedio: -6.0, dentroFascia: 5, conFascia: 12, percentualeDentro: 42,
                                   fasciaDichiarata: 80, pochiDati: false, giornateMinime: 8, giudizio: "sotto_le_attese")
        let t = try XCTUnwrap(TestoAffidabilita(a))
        XCTAssertTrue(t.fuoriLinea)
        XCTAssertEqual(t.giudizio, "Questo periodo è andato peggio del previsto: i punti veri sono stati spesso sotto la fascia.")
        XCTAssertEqual(t.riga, "Su 12 giornate i punti fatti sono caduti nella fascia prevista 5 volte, il 42% (dichiarato: 8 volte su 10).")
        XCTAssertEqual(t.scarto, "9,1")
    }

    func testPochiDati() throws {
        let a = AffidabilitaDiario(giornate: 1, scartoMedio: 2, erroreMedio: 0.01, dentroFascia: 1, conFascia: 1, percentualeDentro: 100,
                                   pochiDati: true, giornateMinime: 8, giudizio: "pochi_dati")
        let t = try XCTUnwrap(TestoAffidabilita(a))
        XCTAssertTrue(t.pochiDati)
        XCTAssertEqual(t.giudizio, "Ancora pochi dati: servono almeno 8 giornate per dire quanto ci prendiamo.")
        XCTAssertEqual(t.riga, "Su 1 giornata i punti fatti sono caduti nella fascia prevista 1 volta (dichiarato: 8 volte su 10).")
        XCTAssertEqual(t.verso, "In media i punti fatti e quelli previsti coincidono.")
        // giudizio mancante ma sotto le giornate minime: pochi dati lo stesso
        XCTAssertTrue(try XCTUnwrap(TestoAffidabilita(AffidabilitaDiario(giornate: 3, giornateMinime: 8))).pochiDati)
    }

    func testAffidabilitaAssenteOVuota() throws {
        XCTAssertNil(TestoAffidabilita(nil))
        XCTAssertNil(TestoAffidabilita(AffidabilitaDiario(giornate: 0, pochiDati: true, giornateMinime: 8, giudizio: "pochi_dati")))
        // server vecchio: il Diario si legge come prima
        let d = try diario(#"{"giornate": [{"giornata": 3, "consigliata": {"atteso": 60, "reale": 61}}]}"#)
        XCTAssertNil(d.affidabilita)
        XCTAssertNil(d.giornate?.first?.attesoVsFatto)
        // campi strani: il Diario non si rompe
        let e = try diario(#"{"affidabilita": "boh", "giornate": [{"giornata": 3, "atteso_vs_fatto": [1, 2]}]}"#)
        XCTAssertNil(TestoAffidabilita(e.affidabilita))
        XCTAssertEqual(e.giornate?.count, 1)
        XCTAssertNil(PuntoAttesoFatto(giornata: 3, e.giornate?.first?.attesoVsFatto))
    }

    func testPercentualeConArticolo() {
        XCTAssertEqual(TestoAffidabilita.percentualeConArticolo(80), "l'80%")
        XCTAssertEqual(TestoAffidabilita.percentualeConArticolo(8), "l'8%")
        XCTAssertEqual(TestoAffidabilita.percentualeConArticolo(11), "l'11%")
        XCTAssertEqual(TestoAffidabilita.percentualeConArticolo(50), "il 50%")
        XCTAssertEqual(TestoAffidabilita.percentualeConArticolo(100), "il 100%")
    }

    func testAttesoVsFattoPerGiornata() throws {
        let d = try diario(#"""
        {"giornate": [
          {"stagione": "2026-27", "giornata": 9, "atteso_vs_fatto": {"riferimento": "consigliata", "atteso": 68.5, "fatti": 58.0, "scarto": -10.5,
                                                                    "nella_fascia": false, "intervallo": {"basso": 60.5, "alto": 77.0}}},
          {"stagione": "2026-27", "giornata": 8, "atteso_vs_fatto": {"atteso": 67.0, "fatti": 70.0, "scarto": 3.0, "nella_fascia": true,
                                                                    "intervallo": {"basso": 59.0, "alto": 75.5}}},
          {"stagione": "2026-27", "giornata": 7, "atteso_vs_fatto": {"atteso": 65.0, "fatti": 80.0, "scarto": 15.0, "nella_fascia": false,
                                                                    "intervallo": {"basso": 57.0, "alto": 73.5}}},
          {"stagione": "2026-27", "giornata": 6, "atteso_vs_fatto": {"atteso": 64.0, "fatti": 66.5, "scarto": 2.5, "nella_fascia": null, "intervallo": null}},
          {"stagione": "2026-27", "giornata": 5, "atteso_vs_fatto": null},
          {"stagione": "2025-26", "giornata": 38, "atteso_vs_fatto": {"atteso": 70.0, "fatti": 70.0}}
        ]}
        """#)
        let punti = PuntoAttesoFatto.elenco(d.giornate ?? [])
        XCTAssertEqual(punti.map(\.giornata), [6, 7, 8, 9], "solo la stagione più recente, in ordine, senza le giornate senza dati")
        XCTAssertEqual(punti[3].frase, "Previsti tra 60,5 e 77,0: sotto la fascia (−2,5)")
        XCTAssertEqual(punti[2].frase, "Previsti tra 59,0 e 75,5: dentro la fascia")
        XCTAssertEqual(punti[1].frase, "Previsti tra 57,0 e 73,5: sopra la fascia (+6,5)")
        XCTAssertEqual(punti[0].frase, "Previsti 64,0, fatti 66,5 (+2,5)")
        XCTAssertNil(punti[0].dentro)
        XCTAssertEqual(punti[3].voce, "Giornata 9: attesi 68,5 punti, fatti 58,0, fascia prevista tra 60,5 e 77,0, fuori")
        XCTAssertEqual(PuntoAttesoFatto.elenco(d.giornate ?? [], massimo: 2).map(\.giornata), [8, 9])
    }
}
