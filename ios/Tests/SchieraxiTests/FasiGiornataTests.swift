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
        XCTAssertEqual(b.partite, ContoPartite(inCorso: 1, finite: 1, daGiocare: 8))
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
        XCTAssertEqual(o.partite?.count, 2, "senza il blocco le partite del turno restano")
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
        XCTAssertEqual(TestiFase.confronto(r), "Con la consigliata: 78,0 punti (73,7 attesi).", "come la web (`oggi.con_consigliata`)")
        XCTAssertNil(TestiFase.notaDiario(r))
        let p = try XCTUnwrap(o.prossimaGiornata)
        XCTAssertEqual(p.preparaDa, "2026-11-11 14:30")
        XCTAssertNil(o.giornataInCorso)
    }

    func testTestiDelRiepilogo() {
        let meglio = RiepilogoGiornata(formazioneDi: "tua", nelDiario: true, puntiFatti: 74.5, consigliata: PuntiConsigliata(puntiFatti: 70, puntiAttesi: nil))
        XCTAssertEqual(TestiFase.confronto(meglio), "Con la consigliata: 70,0 punti (– attesi).", "come la web: «–» per un numero che manca")
        let consigliata = RiepilogoGiornata(formazioneDi: "consigliata", nelDiario: true, puntiFatti: 74.5, consigliata: PuntiConsigliata(puntiFatti: 74.5, puntiAttesi: nil))
        XCTAssertNil(TestiFase.confronto(consigliata), "con la consigliata schierata il confronto non serve")
        let fuori = RiepilogoGiornata(nelDiario: false, puntiFatti: 50, intervallo: IntervalloPunti(basso: 60, alto: 80))
        XCTAssertEqual(TestiFase.notaDiario(fuori), "Il confronto con la consigliata arriva nel Diario.")
    }

    func testTestiDellaGiornataInCorso() {
        XCTAssertEqual(TestiFase.fantavoto(7.5), "7,5")
        XCTAssertEqual(TestiFase.fantavoto(6.25), "6,25")
        XCTAssertEqual(TestiFase.fantavoto(10), "10,0")
        // `ancora_da_giocare` è chi deve ancora giocare (o sta giocando), non i voti che mancano (#436)
        XCTAssertEqual(TestiFase.ancora(0), "Hanno giocato tutti: mancano solo i voti ufficiali.")
        XCTAssertEqual(TestiFase.ancora(1), "1 giocatore deve ancora giocare")
        XCTAssertEqual(TestiFase.ancora(4), "4 giocatori devono ancora giocare")
        XCTAssertNil(TestiFase.ancora(nil))

        let daGiocare = GiocatoreInCorso(id: 1, nome: "Ivo", stato: "da_giocare", data: "2026-11-07 18:00")
        XCTAssertEqual(TestiFase.valore(daGiocare), Quando.leggibile("2026-11-07 18:00", adesso: Orologio.adesso()), "la data, come la web")
        XCTAssertEqual(TestiFase.valoreVoce(daGiocare), "gioca sabato 7 novembre alle 18:00")
        XCTAssertEqual(TestiFase.valore(GiocatoreInCorso(id: 1, nome: "Ivo", stato: "fatto", fantavoto: 6.5)), "6,5")
        XCTAssertEqual(TestiFase.valoreVoce(GiocatoreInCorso(id: 1, nome: "Ivo", stato: "fatto", fantavoto: 6.5)), "fantavoto 6,5")
        XCTAssertEqual(TestiFase.valore(GiocatoreInCorso(id: 1, nome: "Ivo", stato: "in_corso")), "Partita in corso")
        XCTAssertEqual(TestiFase.valore(GiocatoreInCorso(id: 1, nome: "Ivo", stato: "attesa_voti")), "Voto in arrivo")
        XCTAssertEqual(TestiFase.valore(GiocatoreInCorso(id: 1, nome: "Ivo", stato: "rinviata")), "Rinviata")
        XCTAssertEqual(TestiFase.valore(GiocatoreInCorso(id: 1, nome: "Ivo", stato: "senza_voto")), "Senza voto")
        XCTAssertEqual(TestiFase.valore(GiocatoreInCorso(id: 1, nome: "Ivo", stato: "qualcosa")), "Da giocare", "come la web: uno stato sconosciuto vale «Da giocare»")

        let certo = CambioPanchina(esce: PersonaCambio(id: 1, nome: "Bastrani"), entra: PersonaCambio(id: 2, nome: "Dimarzi"), certa: true, motivo: "senza_voto")
        XCTAssertEqual(TestiFase.cambio(certo), "Bastrani → Dimarzi")
        XCTAssertEqual(TestiFase.etichettaCambio(certo), "già fatto")
        let senza = CambioPanchina(esce: PersonaCambio(id: 3, nome: "Buonvicini"), entra: nil, certa: false, motivo: "fuori")
        XCTAssertEqual(TestiFase.cambio(senza), "Buonvicini → nessun sostituto")
        XCTAssertEqual(TestiFase.etichettaCambio(senza), "probabile")
    }

    func testProssimaGiornata() throws {
        let adesso = try XCTUnwrap(Quando.data("2026-11-09 10:00"))
        XCTAssertEqual(TestiFase.prossima(ProssimaGiornata(giornata: 12, giornataLega: 9, scadenza: "2026-11-14 14:30", preparaDa: "2026-11-11 14:30"), adesso: adesso),
                       "Giornata 9 · 12ª di Serie A: la formazione si chiude sab 14 14:30. Conviene prepararla da mer 11 14:30, quando escono le probabili formazioni.")
        XCTAssertEqual(TestiFase.prossima(ProssimaGiornata(giornata: 12, giornataLega: 9, scadenza: "2026-11-14 14:30", preparaDa: "2026-11-09 10:00"), adesso: adesso),
                       "Giornata 9 · 12ª di Serie A: la formazione si chiude sab 14 14:30. Puoi già prepararla.")
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
