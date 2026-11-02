import XCTest
@testable import Schieraxi

/// Fasi della giornata in Oggi (`fase`, `in_corso`, `riepilogo`, `prossima`, `partite[].stato`): lettura tollerante e testi.
final class FasiGiornataTests: XCTestCase {
    private func oggi(_ json: String) throws -> Oggi { try Decodifica.decodifica(Data(json.utf8)) }

    private let inCorso = #"""
    {"giornata": 11, "giornata_lega": 8, "iniziata": true, "fase": "in_corso",
     "formazione": {"modulo": "3-4-3", "punteggio_atteso": 73.7},
     "avvisi": [{"id": 120, "nome": "Leonel", "tipo": "dubbio", "in_formazione": true}],
     "partite": [{"data": "2026-11-07 15:00", "casa": "inter", "trasferta": "roma", "giocata": true, "stato": "finita"},
                 {"data": "2026-11-07 18:00", "casa": "milan", "trasferta": "juventus", "giocata": false, "stato": "in_corso"}],
     "in_corso": {"giornata": 11, "giornata_lega": 8, "formazione_di": "tua", "punti_fatti": 39.0, "punti_attesi_restanti": 38.7,
                  "punti_previsti": 77.7, "modificatore": null, "ancora_da_giocare": 6,
                  "giocatori": [{"id": 101, "nome": "Ivo Sorvani", "ruolo": "P", "squadra": "inter", "titolare": true, "a_punteggio": true,
                                 "stato": "fatto", "fantavoto": 5, "data": "2026-11-07 15:00"},
                                {"nome": "senza id"},
                                {"id": 105, "nome": "Fabio Dimarzi", "ruolo": "D", "squadra": "inter", "titolare": false, "a_punteggio": true,
                                 "stato": "fatto", "fantavoto": 6.5, "data": "2026-11-07 15:00"}],
                  "sostituzioni": [{"esce": {"id": 104, "nome": "Alvise Bastrani", "ruolo": "D"},
                                    "entra": {"id": 105, "nome": "Fabio Dimarzi", "ruolo": "D"}, "certa": true, "motivo": "senza_voto"},
                                   {"esce": {"id": 107, "nome": "Aurelio Buonvicini", "ruolo": "D"}, "entra": null, "certa": false, "motivo": "fuori"}],
                  "partite": {"in_corso": 1, "finite": 1, "da_giocare": 8, "rinviate": 0}}}
    """#

    func testGiornataInCorsoSiLegge() throws {
        let o = try oggi(inCorso)
        XCTAssertEqual(o.faseGiornata, .inCorso)
        XCTAssertFalse(o.conConsigli, "durante la giornata niente «Da controllare» né migliori")
        let b = try XCTUnwrap(o.giornataInCorso)
        XCTAssertEqual(b.puntiFatti, 39)
        XCTAssertEqual(b.puntiPrevisti, 77.7)
        XCTAssertNil(b.modificatore)
        XCTAssertEqual(b.ancoraDaGiocare, 6)
        XCTAssertEqual(b.giocatori.map(\.id), [101, 105], "l'elemento senza id si salta, gli altri restano")
        XCTAssertEqual(b.giocatori.first?.fantavoto, 5)
        XCTAssertEqual(b.giocatori.last?.titolare, false)
        XCTAssertEqual(b.sostituzioni.count, 2)
        XCTAssertEqual(b.sostituzioni.first?.certa, true)
        XCTAssertNil(b.sostituzioni.last?.entra)
        XCTAssertEqual(o.contoPartite, ContoPartite(inCorso: 1, finite: 1, daGiocare: 8))
        XCTAssertEqual(o.partite?.map { $0.stato ?? "" }, ["finita", "in_corso"])
        XCTAssertNil(o.riepilogoGiornata, "il riepilogo vale solo nella fase finita")
    }

    func testFaseMancanteStranaOSbagliataValePrima() throws {
        XCTAssertEqual(try oggi(#"{"giornata": 9}"#).faseGiornata, .prima)
        XCTAssertEqual(try oggi(#"{"giornata": 9, "fase": "boh"}"#).faseGiornata, .prima)
        let numero = try oggi(#"{"giornata": 9, "fase": 3, "in_corso": "rotto", "partite": [{"casa": "a", "trasferta": "b", "stato": 7}]}"#)
        XCTAssertEqual(numero.faseGiornata, .prima)
        XCTAssertEqual(numero.giornata, 9, "un campo nuovo strano non rompe Oggi")
        XCTAssertNil(numero.partite?.first?.stato)
        XCTAssertTrue(numero.conConsigli)
    }

    func testInCorsoNullONonOggettoNonRompeOggi() throws {
        let o = try oggi(#"{"giornata": 11, "fase": "in_corso", "in_corso": null, "partite": [{"casa": "a", "trasferta": "b", "stato": "in_corso"}, {"casa": "c", "trasferta": "d", "stato": "da_giocare"}]}"#)
        XCTAssertEqual(o.faseGiornata, .inCorso)
        XCTAssertNil(o.giornataInCorso)
        XCTAssertEqual(o.contoPartite, ContoPartite(inCorso: 1, daGiocare: 1), "senza il blocco il conto viene dalle partite")
    }

    func testGiornataFinita() throws {
        let o = try oggi(#"""
        {"giornata": 12, "fase": "finita",
         "riepilogo": {"giornata": 11, "giornata_lega": 8, "formazione_di": "tua", "nel_diario": true, "punti_fatti": 74.5, "punti_attesi": 71.2,
                       "intervallo": {"basso": 63.2, "alto": 79.7, "confidenza": 0.8}, "consigliata": {"punti_fatti": 78.0, "punti_attesi": 73.7}},
         "prossima": {"giornata": 12, "giornata_lega": 9, "scadenza": "2026-11-14 14:30", "prepara_da": "2026-11-11 14:30", "con_probabili": false}}
        """#)
        XCTAssertEqual(o.faseGiornata, .finita)
        XCTAssertFalse(o.conConsigli)
        let r = try XCTUnwrap(o.riepilogoGiornata)
        XCTAssertTrue(r.nelDiario)
        XCTAssertEqual(r.consigliata?.puntiFatti, 78)
        XCTAssertEqual(TestiFase.scarto(fatti: r.puntiFatti, attesi: r.puntiAttesi), "3,3 punti più del previsto")
        XCTAssertEqual(TestiFase.fascia(r), "Dentro la fascia prevista (tra 63 e 80)")
        XCTAssertEqual(TestiFase.confronto(r), "Con la consigliata avresti fatto 78,0 punti: 3,5 punti in più.")
        XCTAssertNil(TestiFase.notaDiario(r))
        let p = try XCTUnwrap(o.prossimaGiornata)
        XCTAssertEqual(p.preparaDa, "2026-11-11 14:30")
        XCTAssertNil(o.giornataInCorso)
    }

    func testTestiDelRiepilogo() {
        XCTAssertEqual(TestiFase.scarto(fatti: 70, attesi: 71), "1 punto meno del previsto")
        XCTAssertEqual(TestiFase.scarto(fatti: 70, attesi: 70.02), "Proprio come previsto")
        XCTAssertNil(TestiFase.scarto(fatti: 70, attesi: nil))
        let meglio = RiepilogoGiornata(formazioneDi: "tua", nelDiario: true, puntiFatti: 74.5, consigliata: PuntiConsigliata(puntiFatti: 70, puntiAttesi: nil))
        XCTAssertEqual(TestiFase.confronto(meglio), "Con la consigliata avresti fatto 70,0 punti: hai fatto meglio tu di 4,5 punti.")
        let consigliata = RiepilogoGiornata(formazioneDi: "consigliata", nelDiario: true, puntiFatti: 74.5, consigliata: PuntiConsigliata(puntiFatti: 74.5, puntiAttesi: nil))
        XCTAssertNil(TestiFase.confronto(consigliata), "con la consigliata schierata il confronto non serve")
        let fuori = RiepilogoGiornata(nelDiario: false, puntiFatti: 50, intervallo: IntervalloPunti(basso: 60, alto: 80))
        XCTAssertEqual(TestiFase.fascia(fuori), "Fuori dalla fascia prevista (tra 60 e 80)")
        XCTAssertNotNil(TestiFase.notaDiario(fuori))
    }

    func testTestiDellaGiornataInCorso() {
        XCTAssertEqual(TestiFase.partite(ContoPartite(inCorso: 2, finite: 1, daGiocare: 7)), "2 in corso · 1 finita · 7 da giocare")
        XCTAssertEqual(TestiFase.partite(ContoPartite(finite: 3, rinviate: 2)), "3 finite · 2 rinviate")
        XCTAssertNil(TestiFase.partite(ContoPartite()))
        XCTAssertEqual(TestiFase.partiteVoce(ContoPartite(inCorso: 1, rinviate: 1)), "Partite: 1 in corso, 1 rinviata")
        XCTAssertEqual(TestiFase.fantavoto(7.5), "7,5")
        XCTAssertEqual(TestiFase.fantavoto(6.25), "6,25")
        XCTAssertEqual(TestiFase.fantavoto(10), "10,0")
        XCTAssertEqual(TestiFase.ancora(0), "Hanno tutti il voto.")
        XCTAssertEqual(TestiFase.ancora(1), "Manca il voto di 1 giocatore.")
        XCTAssertEqual(TestiFase.ancora(4), "Mancano i voti di 4 giocatori.")
        XCTAssertNil(TestiFase.ancora(nil))
        XCTAssertEqual(TestiFase.modificatore(1), "Modificatore della difesa: +1,0, già contato")
        XCTAssertNil(TestiFase.modificatore(nil))

        let daGiocare = GiocatoreInCorso(id: 1, nome: "Ivo", stato: "da_giocare", data: "2026-11-07 18:00")
        XCTAssertEqual(TestiFase.valore(daGiocare), "sab 18:00")
        XCTAssertEqual(TestiFase.valoreVoce(daGiocare), "gioca sabato 7 novembre alle 18:00")
        XCTAssertEqual(TestiFase.valore(GiocatoreInCorso(id: 1, nome: "Ivo", stato: "fatto", fantavoto: 6.5)), "6,5")
        XCTAssertEqual(TestiFase.valoreVoce(GiocatoreInCorso(id: 1, nome: "Ivo", stato: "fatto", fantavoto: 6.5)), "fantavoto 6,5")
        XCTAssertEqual(TestiFase.valore(GiocatoreInCorso(id: 1, nome: "Ivo", stato: "in_corso")), "In campo")
        XCTAssertEqual(TestiFase.valore(GiocatoreInCorso(id: 1, nome: "Ivo", stato: "senza_voto")), "Senza voto")
        XCTAssertEqual(TestiFase.valore(GiocatoreInCorso(id: 1, nome: "Ivo", stato: "qualcosa")), "—")

        let certo = CambioPanchina(esce: PersonaCambio(id: 1, nome: "Bastrani"), entra: PersonaCambio(id: 2, nome: "Dimarzi"), certa: true, motivo: "senza_voto")
        XCTAssertEqual(TestiFase.cambio(certo), "Esce Bastrani, entra Dimarzi")
        XCTAssertEqual(TestiFase.etichettaCambio(certo), "Già fatto")
        XCTAssertEqual(TestiFase.motivo(certo.motivo), "Non ha preso il voto")
        let senza = CambioPanchina(esce: PersonaCambio(id: 3, nome: "Buonvicini"), entra: nil, certa: false, motivo: "fuori")
        XCTAssertEqual(TestiFase.cambio(senza), "Esce Buonvicini: nessun sostituto in panchina")
        XCTAssertEqual(TestiFase.etichettaCambio(senza), "Probabile")
        XCTAssertEqual(TestiFase.motivo("fuori"), "Infortunato o squalificato")
    }

    func testProssimaGiornata() throws {
        let adesso = try XCTUnwrap(Quando.data("2026-11-09 10:00"))
        XCTAssertEqual(TestiFase.prossima(ProssimaGiornata(preparaDa: "2026-11-11 14:30"), adesso: adesso),
                       "Prepara la formazione da mercoledì 11 novembre alle 14:30: di solito le probabili escono allora.")
        XCTAssertEqual(TestiFase.prossima(ProssimaGiornata(preparaDa: "2026-11-09 10:00"), adesso: adesso), "Puoi già preparare la formazione.")
        XCTAssertEqual(TestiFase.prossima(ProssimaGiornata(preparaDa: "2026-11-11 14:30", conProbabili: true), adesso: adesso),
                       "Le probabili formazioni ci sono già: puoi preparare la formazione.")
        XCTAssertNil(TestiFase.scadenza(ProssimaGiornata()))
    }

    /// I dati delle fotografie (`-DEMO_SCHERMATA oggi-in-corso` e `oggi-finita`) hanno la forma giusta.
    func testLeDemoDelleFasiSiLeggono() async throws {
        let corso = try XCTUnwrap(FinteServer.demoFase("oggi-in-corso"))
        let o: Oggi = try Decodifica.decodifica(try await corso.richiesta("GET", "/api/oggi", corpo: nil))
        XCTAssertEqual(o.faseGiornata, .inCorso)
        XCTAssertEqual(o.giornataInCorso?.giocatori.count, 18)
        XCTAssertEqual(o.giornataInCorso?.giocatori.filter(\.titolare).count, 11)
        XCTAssertEqual(o.giornataInCorso?.sostituzioni.count, 3)
        let finita = try XCTUnwrap(FinteServer.demoFase("oggi-finita"))
        let f: Oggi = try Decodifica.decodifica(try await finita.richiesta("GET", "/api/oggi", corpo: nil))
        XCTAssertEqual(f.faseGiornata, .finita)
        XCTAssertNotNil(f.riepilogoGiornata)
        XCTAssertNotNil(f.prossimaGiornata)
        XCTAssertNil(FinteServer.demoFase("oggi"))
        XCTAssertNil(FinteServer.demoFase(nil))
    }
}
