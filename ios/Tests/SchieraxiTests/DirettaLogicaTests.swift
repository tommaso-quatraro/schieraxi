import XCTest
@testable import Schieraxi

/// Partite in diretta (Oggi > Partite del turno): lettura tollerante, quando chiedere di nuovo, testi per VoiceOver.
final class DirettaLogicaTests: XCTestCase {
    private func live(_ json: String) throws -> LiveWidget {
        try Decodifica.decodifica(Data(json.utf8))
    }

    private let inizio = Quando.data("2026-10-31 15:00") ?? Date()

    func testLeggeLaRispostaEIgnoraCampiEStatiSconosciuti() throws {
        let l = try live("""
        {"aggiornato_il": "2026-10-31 15:20:04", "fonte": "espn", "in_corso": 1, "campo_nuovo": [1, 2],
         "partite": [{"casa": "inter", "trasferta": "roma", "data": "2026-10-31 15:00", "stato": "tempi_supplementari",
                      "minuto": "34'", "gol_casa": 1, "gol_trasferta": 0,
                      "eventi": [{"tipo": "gol", "minuto": "10'", "squadra": "casa", "chi": "Thorvan"}, {"tipo": "cosa_nuova"}]},
                     {"casa": "milan", "trasferta": "napoli"}]}
        """)
        XCTAssertEqual(l.partite?.count, 2)
        XCTAssertTrue(l.partite?[0].inGioco ?? false, "uno stato nuovo con un punteggio conta come in corso")
        XCTAssertFalse(l.partite?[1].inGioco ?? true)
        XCTAssertEqual(l.partite?[0].punteggio, "1–0")
        XCTAssertEqual(l.partite?[1].punteggio, "–")
    }

    // MARK: eventi in elenco

    private func eventi(_ json: String) throws -> [EventoLive] {
        try live(#"{"partite": [{"casa": "a", "trasferta": "b", "gol_casa": 0, "gol_trasferta": 0, "eventi": \#(json)}]}"#).partite?.first?.eventi ?? []
    }

    func testGliEventiMostranoSoloGolRigoriAutogolERossi() throws {
        let e = try eventi("""
        [{"tipo": "gol", "minuto": "33'", "squadra": "casa", "chi": "Poberga", "assist": "Lemao"},
         {"tipo": "giallo", "minuto": "40'", "squadra": "casa", "chi": "Tizio"},
         {"tipo": "rigore", "minuto": "6'", "squadra": "trasferta", "chi": "Varsone"},
         {"tipo": "autogol", "minuto": "50'", "squadra": "casa", "chi": "Caio"},
         {"tipo": "rigore_sbagliato", "minuto": "55'", "squadra": "trasferta", "chi": "Sempronio"},
         {"tipo": "rigore_parato", "minuto": "56'", "squadra": "casa", "chi": "Mevio"},
         {"tipo": "rosso", "minuto": "71'", "squadra": "trasferta", "chi": "De Valk"},
         {"tipo": "doppio_giallo", "minuto": "90'+2'", "squadra": "casa", "chi": "Lobrenka"},
         {"tipo": "cosa_nuova", "minuto": "1'", "squadra": "casa", "chi": "Nessuno"}]
        """)
        XCTAssertEqual(EventiPartita.visibili(e).map(\.testoCompatto), [
            "33' Poberga (ass. Lemao)", "6' Varsone (rig.)", "50' Caio (aut.)", "55' Sempronio (rig. sbagl.)",
            "56' Mevio (rig. parato)", "71' De Valk", "90'+2' Lobrenka (2° giallo)"])
        let c = EventiPartita.colonne(e)
        XCTAssertEqual(c.casa.count, 4)
        XCTAssertEqual(c.trasferta.count, 3)
        XCTAssertEqual(EventiPartita.righe(e), 4)
    }

    func testGliEventiStortiNonRompono() throws {
        let e = try eventi(#"[{"tipo": "gol", "minuto": 12, "squadra": "casa", "chi": "Thorvan", "assist": {"nome": "X"}}, {"tipo": "gol"}]"#)
        XCTAssertEqual(e.count, 2)
        XCTAssertEqual(e[0].testoCompatto, "12' Thorvan")
        XCTAssertNil(e[0].assist)
        XCTAssertEqual(e[1].testoCompatto, "Gol")
        XCTAssertTrue(EventiPartita.visibili(nil).isEmpty)
    }

    func testIGialliNonStannoNellaFrasePerVoiceOver() throws {
        let l = try live(#"{"partite": [{"casa": "inter", "trasferta": "roma", "stato": "finita", "gol_casa": 1, "gol_trasferta": 0, "eventi": [{"tipo": "giallo", "minuto": "3'", "squadra": "casa", "chi": "Tizio"}, {"tipo": "gol", "minuto": "10'", "squadra": "casa", "chi": "Thorvan", "assist": "Barlesi"}]}]}"#)
        let frase = DirettaLogica.frase(casa: "inter", trasferta: "roma", live: l.partite?.first, ora: nil, titolari: [])
        XCTAssertEqual(frase, "Inter 1, Roma 0, finita. Gol di Thorvan al minuto 10, assist di Barlesi")
    }

    func testRispostaVuotaNonRompeNiente() throws {
        let l = try live("{}")
        XCTAssertNil(l.partite)
        XCTAssertNil(DirettaLogica.attesa(live: l, turno: [], adesso: inizio))
    }

    // MARK: quando chiedere di nuovo

    func testSiChiedeSpessoSoloConPartiteInCorso() throws {
        let inCorso = try live(#"{"in_corso": 1, "partite": [{"casa": "inter", "trasferta": "roma", "stato": "primo_tempo", "gol_casa": 0, "gol_trasferta": 0}]}"#)
        XCTAssertEqual(DirettaLogica.attesa(live: inCorso, turno: [], adesso: inizio), DirettaLogica.passo)
        XCTAssertTrue((30...60).contains(DirettaLogica.passo), "tra 30 e 60 secondi, come dice il contratto")
    }

    func testNienteDaChiedereSeSonoTutteFinite() throws {
        let finite = try live(#"{"in_corso": 0, "partite": [{"casa": "inter", "trasferta": "roma", "data": "2026-10-31 15:00", "stato": "finita", "gol_casa": 2, "gol_trasferta": 0}]}"#)
        let turno = [Partita(data: "2026-10-31 15:00", casa: "inter", trasferta: "roma", giocata: true)]
        XCTAssertNil(DirettaLogica.attesa(live: finite, turno: turno, adesso: inizio.addingTimeInterval(3 * 3600)))
    }

    func testPrimaDellaPartitaSiAspettaSenzaChiedere() {
        let turno = [Partita(data: "2026-10-31 15:00", casa: "inter", trasferta: "roma", giocata: false)]
        // 2 ore prima: si aspetta fino a 10 minuti prima dell'inizio, ma al massimo mezz'ora alla volta
        XCTAssertEqual(DirettaLogica.attesa(live: nil, turno: turno, adesso: inizio.addingTimeInterval(-2 * 3600)), 1800)
        // 15 minuti prima: mancano 5 minuti ai 10 minuti d'anticipo
        XCTAssertEqual(DirettaLogica.attesa(live: nil, turno: turno, adesso: inizio.addingTimeInterval(-15 * 60)) ?? 0, 300, accuracy: 0.5)
        // 5 minuti prima e dopo il calcio d'inizio: si chiede spesso
        XCTAssertEqual(DirettaLogica.attesa(live: nil, turno: turno, adesso: inizio.addingTimeInterval(-5 * 60)), DirettaLogica.passo)
        XCTAssertEqual(DirettaLogica.attesa(live: nil, turno: turno, adesso: inizio.addingTimeInterval(20 * 60)), DirettaLogica.passo)
    }

    func testPartitaLontanaONonPiuAttesaNonFaChiedere() {
        let turno = [Partita(data: "2026-10-31 15:00", casa: "inter", trasferta: "roma", giocata: false)]
        XCTAssertNil(DirettaLogica.attesa(live: nil, turno: turno, adesso: inizio.addingTimeInterval(-20 * 3600)), "troppo lontana")
        XCTAssertNil(DirettaLogica.attesa(live: nil, turno: turno, adesso: inizio.addingTimeInterval(4 * 3600)), "da ore dovrebbe essere finita")
    }

    // MARK: gol e lampo

    func testIlLampoSoloQuandoIlPunteggioSale() throws {
        func p(_ c: Int?, _ t: Int?) throws -> PartitaLive? {
            let g = c.map { String($0) } ?? "null", h = t.map { String($0) } ?? "null"
            return try live(#"{"partite": [{"casa": "a", "trasferta": "b", "stato": "primo_tempo", "gol_casa": \#(g), "gol_trasferta": \#(h)}]}"#).partite?.first
        }
        XCTAssertTrue(DirettaLogica.golSegnato(prima: try p(0, 0), dopo: try p(1, 0)))
        XCTAssertTrue(DirettaLogica.golSegnato(prima: try p(1, 0), dopo: try p(1, 1)))
        XCTAssertFalse(DirettaLogica.golSegnato(prima: try p(1, 0), dopo: try p(1, 0)))
        XCTAssertFalse(DirettaLogica.golSegnato(prima: try p(nil, nil), dopo: try p(1, 0)), "il primo dato non è un gol nuovo")
        XCTAssertFalse(DirettaLogica.golSegnato(prima: try p(2, 1), dopo: try p(1, 1)), "un gol annullato non fa lampeggiare")
        XCTAssertFalse(DirettaLogica.golSegnato(prima: nil, dopo: try p(1, 0)))
    }

    func testAnnuncioDelGolPerVoiceOver() throws {
        let prima = try live(#"{"partite": [{"casa": "inter", "trasferta": "roma", "stato": "primo_tempo", "gol_casa": 0, "gol_trasferta": 0}]}"#).partite?.first
        let dopo = try live("""
        {"partite": [{"casa": "inter", "trasferta": "roma", "stato": "primo_tempo", "minuto": "10'", "gol_casa": 1, "gol_trasferta": 0,
                      "eventi": [{"tipo": "giallo", "minuto": "5'", "squadra": "casa", "chi": "Bastrani"}, {"tipo": "gol", "minuto": "10'", "squadra": "casa", "chi": "Thorvan"}]}]}
        """).partite?.first
        XCTAssertEqual(DirettaLogica.annuncioGol(casa: "inter", trasferta: "roma", prima: prima, dopo: dopo), "Gol! Inter 1, Roma 0. Gol di Thorvan al minuto 10")
        XCTAssertNil(DirettaLogica.annuncioGol(casa: "inter", trasferta: "roma", prima: dopo, dopo: dopo), "nessun gol nuovo, nessun annuncio")
        XCTAssertNil(DirettaLogica.annuncioGol(casa: "inter", trasferta: "roma", prima: nil, dopo: dopo), "il primo dato non si annuncia")
    }

    // MARK: abbinamento e recuperi

    func testAbbinaPerCasaETrasfertaEAggiungeIRecuperiInCorso() throws {
        let l = try live("""
        {"partite": [{"casa": "inter", "trasferta": "roma", "stato": "secondo_tempo", "gol_casa": 1, "gol_trasferta": 0},
                     {"casa": "lecce", "trasferta": "genoa", "data": "2026-10-30 18:00", "stato": "primo_tempo", "gol_casa": 0, "gol_trasferta": 0},
                     {"casa": "pisa", "trasferta": "como", "stato": "finita", "gol_casa": 0, "gol_trasferta": 0}]}
        """)
        let turno = [Partita(data: "2026-10-31 15:00", casa: "Inter", trasferta: "roma", giocata: false)]
        XCTAssertEqual(DirettaLogica.dalVivo(l, per: turno[0])?.punteggio, "1–0")
        let tutte = DirettaLogica.conRecuperi(turno, live: l)
        XCTAssertEqual(tutte.map(\.casa), ["Inter", "lecce"], "il recupero in corso c'è, la partita finita fuori turno no")
    }

    // MARK: i miei titolari

    func testITitolariSiLeggonoAncheConElementiSbagliati() throws {
        let json = #"""
        {"giornata": 9, "miei_titolari": {"inter": [{"id": 1, "nome": "Sorvani", "ruolo": "P"}, {"nome": "senza id"}, 7],
                                          "hellas_verona": [{"id": 2, "nome": "Montifò", "ruolo": "P"}], "roma": "boh"}}
        """#
        let o: Oggi = try Decodifica.decodifica(Data(json.utf8))
        let m = o.mieiTitolari
        XCTAssertEqual(m?.titolari(di: "inter").map(\.nome), ["Sorvani"])
        XCTAssertEqual(m?.titolari(di: "hellas_verona").map(\.nome), ["Montifò"], "anche se il decodificatore cambia la chiave")
        XCTAssertEqual(m?.titolari(di: "roma").count, 0)
        XCTAssertEqual(m?.titolari(casa: "inter", trasferta: "hellas-verona").count, 2)
    }

    func testOggiSenzaTitolariFunzionaCome() throws {
        let o: Oggi = try Decodifica.decodifica(Data(#"{"giornata": 9}"#.utf8))
        XCTAssertNil(o.mieiTitolari)
        let sbagliato: Oggi = try Decodifica.decodifica(Data(#"{"giornata": 9, "miei_titolari": [1, 2]}"#.utf8))
        XCTAssertEqual(sbagliato.mieiTitolari?.titolari(di: "inter").count ?? 0, 0)
    }

    // MARK: testi

    func testLaFrasePerVoiceOverEPiena() throws {
        let l = try live("""
        {"partite": [{"casa": "inter", "trasferta": "roma", "stato": "secondo_tempo", "minuto": "90'+3'", "gol_casa": 2, "gol_trasferta": 1,
                      "eventi": [{"tipo": "gol", "minuto": "10'", "squadra": "casa", "chi": "Thorvan"}, {"tipo": "rosso", "minuto": "80'", "squadra": "trasferta", "chi": "Cristoni"}]}]}
        """)
        let uno = [MioTitolare(id: 1, nome: "Sorvani", ruolo: "P")]
        let frase = DirettaLogica.frase(casa: "inter", trasferta: "roma", live: l.partite?.first, ora: "15:00", titolari: uno)
        XCTAssertEqual(frase, "Inter 2, Roma 1, al minuto 90 più 3. Gol di Thorvan al minuto 10. Espulso Cristoni al minuto 80. Giocano il tuo titolare Sorvani")
        let due = uno + [MioTitolare(id: 2, nome: "Bastrani", ruolo: "D")]
        XCTAssertTrue(DirettaLogica.frase(casa: "inter", trasferta: "roma", live: nil, ora: "15:00", titolari: due).hasSuffix("Giocano i tuoi titolari Sorvani, Bastrani"))
        XCTAssertEqual(DirettaLogica.frase(casa: "inter", trasferta: "roma", live: nil, ora: "15:00", titolari: []), "Inter contro Roma, alle 15:00")
    }

    func testLaNotaDellaFonte() {
        XCTAssertEqual(DirettaLogica.nota(fonte: "espn"), "Risultati in diretta: fonte ESPN, uso personale.")
        XCTAssertNotNil(DirettaLogica.nota(fonte: "fantacalcio"))
        XCTAssertNil(DirettaLogica.nota(fonte: nil))
    }

    // MARK: schermata

    @MainActor
    func testIlViewModelUsaLiveSoloSeLaLetturaRiesce() async throws {
        let corpo = #"{"fonte": "espn", "in_corso": 1, "partite": [{"casa": "inter", "trasferta": "roma", "stato": "primo_tempo", "minuto": "5'", "gol_casa": 0, "gol_trasferta": 0}]}"#
        let riesce = ServerDiProva { _, percorso, _ in
            if percorso.hasPrefix("/api/live") { return Data(corpo.utf8) }
            return Data("{\"giornata\": 9, \"partite\": [{\"casa\": \"inter\", \"trasferta\": \"roma\", \"data\": \"2026-10-31 15:00\", \"giocata\": false}]}".utf8)
        }
        let vm = OggiViewModel(server: riesce, conPromemoria: false)
        await vm.carica()
        XCTAssertNil(vm.risultatiLive)
        await vm.live.ricarica()
        XCTAssertEqual(vm.risultatiLive?.inCorso, 1)
        let partita = try XCTUnwrap(vm.oggi?.partite?.first)
        XCTAssertEqual(vm.dalVivo(partita)?.minuto, "5'")
    }
}
