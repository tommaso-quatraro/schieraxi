import XCTest
@testable import Schieraxi

/// L'importazione delle rose in due passi (anteprima, poi «Conferma e salva»): modelli tolleranti, logica pura e ViewModel.
/// Squadre e giocatori INVENTATI.
final class AnteprimaRoseTests: XCTestCase {
    /// Un'anteprima come la manda il server: una squadra con un dubbio simile, uno ambiguo e uno non trovato; una nuova con un portiere in meno.
    static let risposta = #"""
    {"squadre": [
      {"nome": "Real Fantasia", "nuova": false, "crediti_residui": 12, "sicuri": 2, "da_controllare": 2, "non_trovati": 1,
       "totale": 5, "attesi": 25, "ruoli": {"P": 1, "D": 1, "C": 1, "A": 2}, "mancano": {"P": 2, "D": 7, "C": 7, "A": 4},
       "in_piu": {}, "senza_ruolo": 0, "completa": false, "avvisi": ["5 giocatori su 25"], "giocatori": [
        {"testo": "Pirlotti", "stato": "sicuro", "metodo": "esatto", "id": 901, "nome": "Ugo Pirlotti", "ruolo": "P", "squadra": "inter", "costo": 10, "avviso": "", "alternative": []},
        {"testo": "Zappaterra", "stato": "sicuro", "metodo": "esatto", "id": 902, "nome": "Gino Zappaterra", "ruolo": "D", "squadra": "milan", "costo": 5, "avviso": "", "alternative": []},
        {"testo": "Mancuzzi", "stato": "da_controllare", "metodo": "simile", "id": 903, "nome": "Leo Mancuso", "ruolo": "C", "squadra": "JUV", "costo": 8,
         "avviso": "squadra diversa: Juventus", "alternative": [{"id": 903, "nome": "Leo Mancuso", "ruolo": "C", "squadra": "JUV"}]},
        {"testo": "Bertolazzi", "stato": "da_controllare", "metodo": "ambiguo", "id": null, "nome": null, "ruolo": "A", "squadra": null, "costo": 20,
         "avviso": "", "alternative": [{"id": 904, "nome": "Aldo Bertolazzi", "ruolo": "A", "squadra": "roma"}, {"nome": "senza codice"},
                                      {"id": 905, "nome": "Rino Bertolazzi", "ruolo": "A", "squadra": "lazio"}]},
        {"testo": "Quintavalle", "stato": "non_trovato", "metodo": "non trovato", "id": null, "nome": null, "ruolo": "A", "squadra": null, "costo": 1, "avviso": "", "alternative": []}
      ]},
      {"nome": "Atletico Pigiama", "nuova": true, "crediti_residui": 1, "sicuri": 1, "da_controllare": 0, "non_trovati": 0,
       "totale": 1, "attesi": 1, "mancano": {}, "in_piu": {"A": 1}, "senza_ruolo": 1, "avvisi": [], "giocatori": [
        {"testo": "Oddone", "stato": "sicuro", "id": 906, "nome": "Oddone Brivio", "ruolo": "A", "squadra": "napoli"}
      ]}
    ],
    "avvisi": ["Real Fantasia: 5 giocatori su 25", "Il file ha una riga illeggibile"],
    "mia_squadra": "Real Fantasia", "totale_squadre": 2, "sicuri": 3, "da_controllare": 2, "non_trovati": 1,
    "differenze": {"prima_importazione": true, "testo": "Prima importazione"}, "riepilogo": "Prima importazione"}
    """#

    private func anteprima() throws -> AnteprimaRose {
        try Decodifica.decodifica(Data(Self.risposta.utf8))
    }

    // MARK: modelli

    func testLaRispostaSiLeggeTuttaESaltaLeAlternativeRotte() throws {
        let r = try anteprima()
        XCTAssertEqual(r.squadre.map(\.nome), ["Real Fantasia", "Atletico Pigiama"])
        XCTAssertEqual(r.miaSquadra, "Real Fantasia")
        XCTAssertEqual([r.sicuri, r.daControllare, r.nonTrovati], [3, 2, 1])
        let s = try XCTUnwrap(r.squadre.first)
        XCTAssertEqual(s.creditiResidui, 12)
        XCTAssertEqual(s.mancano["D"], 7)
        let ambiguo = try XCTUnwrap(s.giocatori.first { $0.testo == "Bertolazzi" })
        XCTAssertEqual(ambiguo.stato, .daControllare)
        XCTAssertNil(ambiguo.id)
        XCTAssertEqual(ambiguo.alternative.map(\.id), [904, 905], "un'alternativa senza codice si salta, le altre restano")
        XCTAssertEqual(r.squadre.last?.nuova, true)
        XCTAssertEqual(r.squadre.last?.inPiu["A"], 1)
    }

    func testCampiMancantiOStatiNuoviNonRompono() throws {
        let r: AnteprimaRose = try Decodifica.decodifica(Data(#"{"squadre": [{"nome": "X", "giocatori": [{"nome": "Solo Nome", "stato": "boh"}]}, {"giocatori": []}]}"#.utf8))
        XCTAssertEqual(r.squadre.count, 1, "una squadra senza nome non si mostra")
        let g = try XCTUnwrap(r.squadre.first?.giocatori.first)
        XCTAssertEqual(g.testo, "Solo Nome", "senza testo si usa il nome")
        XCTAssertEqual(g.stato, .daControllare, "uno stato sconosciuto si mostra da controllare")
        XCTAssertEqual(r.squadre.first?.daControllare, 1, "i conteggi mancanti si ricavano dai giocatori")
        XCTAssertNil(r.miaSquadra)
        XCTAssertTrue(r.avvisi.isEmpty)
    }

    // MARK: correzioni

    func testLeCorrezioniPartonoDalleProposteDelServer() throws {
        let r = try anteprima()
        let c = AnteprimaLogica.correzioni(r.squadre, scelte: [:])
        // il «simile» con una proposta si conferma; l'ambiguo senza proposta e il non trovato restano come sono
        XCTAssertEqual(c, [CorrezioneRosa(squadra: "Real Fantasia", testo: "Mancuzzi", id: 903)])
    }

    func testSceltaTogliECercaFinisconoNelleCorrezioni() throws {
        let r = try anteprima()
        let scelte: [String: SceltaDubbio] = [
            AnteprimaLogica.chiave("Real Fantasia", "Mancuzzi"): .togli,
            AnteprimaLogica.chiave("Real Fantasia", "Bertolazzi"): .giocatore(905),
            AnteprimaLogica.chiave("Real Fantasia", "Quintavalle"): .giocatore(999),
            AnteprimaLogica.chiave("Real Fantasia", "Pirlotti"): .togli,     // un sicuro non si tocca
        ]
        let c = AnteprimaLogica.correzioni(r.squadre, scelte: scelte)
        XCTAssertEqual(c, [
            CorrezioneRosa(squadra: "Real Fantasia", testo: "Mancuzzi", id: nil),
            CorrezioneRosa(squadra: "Real Fantasia", testo: "Bertolazzi", id: 905),
            CorrezioneRosa(squadra: "Real Fantasia", testo: "Quintavalle", id: 999),
        ])
    }

    func testTogliSiMandaConIdNull() throws {
        let dati = try JSONEncoder().encode([CorrezioneRosa(squadra: "A", testo: "B", id: nil), CorrezioneRosa(squadra: "A", testo: "C", id: 7)])
        let oggetti = try XCTUnwrap(JSONSerialization.jsonObject(with: dati) as? [[String: Any]])
        XCTAssertTrue(oggetti[0]["id"] is NSNull, "togli = id null, non un campo mancante")
        XCTAssertEqual(oggetti[1]["id"] as? Int, 7)
        XCTAssertEqual(oggetti[0]["squadra"] as? String, "A")
    }

    func testIDubbiUnaVoltaSolaPrimaQuelliDaControllare() throws {
        var s = try XCTUnwrap(try anteprima().squadre.first)
        s.giocatori.insert(GiocatoreAnteprima(testo: "Quintavalle", stato: .nonTrovato), at: 0)   // stesso nome due volte
        XCTAssertEqual(AnteprimaLogica.dubbi(s).map(\.testo), ["Mancuzzi", "Bertolazzi", "Quintavalle"])
    }

    func testIlGiocatoreTrovatoSiAggiungeAlleOpzioni() throws {
        let g = try XCTUnwrap(try anteprima().squadre.first?.giocatori.first { $0.testo == "Bertolazzi" })
        let nuovo = CandidatoAnteprima(id: 777, nome: "Altro Bertolazzi", ruolo: "C", squadra: "como")
        XCTAssertEqual(AnteprimaLogica.opzioni(g, trovato: nuovo).map(\.id), [904, 905, 777])
        XCTAssertEqual(AnteprimaLogica.opzioni(g, trovato: g.alternative[0]).map(\.id), [904, 905], "niente doppioni")
    }

    // MARK: testi

    func testProblemiEConteggiConIPluraliGiusti() throws {
        let r = try anteprima()
        let prima = r.squadre[0], seconda = r.squadre[1]
        XCTAssertEqual(AnteprimaLogica.problemi(prima), ["Mancano 2 portieri", "Mancano 7 difensori", "Mancano 7 centrocampisti", "Mancano 4 attaccanti"])
        XCTAssertEqual(AnteprimaLogica.problemi(seconda), ["1 attaccante in più", "1 giocatore senza ruolo"])
        let uno = SquadraAnteprima(nome: "X", mancano: ["P": 1], giocatori: [])
        XCTAssertEqual(AnteprimaLogica.problemi(uno), ["Manca 1 portiere"])
        XCTAssertEqual(AnteprimaLogica.conteggio(prima), "5 giocatori su 25 · 12 crediti")
        XCTAssertEqual(AnteprimaLogica.conteggio(seconda), "1 giocatore · 1 credito")
    }

    func testRiassuntoEAvvisiDiTuttoIlFile() throws {
        let r = try anteprima()
        XCTAssertEqual(AnteprimaLogica.riassunto(r),
                       "2 squadre: 3 giocatori riconosciuti, 2 da controllare, 1 non trovato. Sistema i dubbi qui sotto, poi conferma.")
        XCTAssertEqual(AnteprimaLogica.avvisiGenerali(r), ["Il file ha una riga illeggibile"], "gli avvisi di una squadra stanno nella sua scheda")
        let pulita = AnteprimaRose(squadre: [SquadraAnteprima(nome: "Y", giocatori: [GiocatoreAnteprima(testo: "A", stato: .sicuro)])])
        XCTAssertEqual(AnteprimaLogica.riassunto(pulita), "1 squadra: 1 giocatore riconosciuto.")
        XCTAssertFalse(AnteprimaLogica.mostraDifferenze(r.differenze), "alla prima importazione non c'è niente da confrontare")
    }

    func testLaMiaSquadraPreselezionata() throws {
        let r = try anteprima()
        XCTAssertEqual(AnteprimaLogica.mia(decisa: nil, r), "Real Fantasia", "il suggerimento del server")
        XCTAssertEqual(AnteprimaLogica.mia(decisa: "Atletico Pigiama", r), "Atletico Pigiama", "la scelta dell'utente vince")
        XCTAssertEqual(AnteprimaLogica.mia(decisa: "Non c'è", r), "", "una squadra che non è tra le lette non si propone")
    }

    func testDescrizioneDelCandidatoEClub() {
        XCTAssertEqual(AnteprimaLogica.descrivi(CandidatoAnteprima(id: 1, nome: "Leo Mancuso", ruolo: "C", squadra: "JUV")), "Leo Mancuso · centrocampista · Juventus")
        XCTAssertEqual(AnteprimaLogica.club("inter"), "Inter")
        XCTAssertEqual(AnteprimaLogica.club("Squadra Ignota"), "Squadra Ignota")
        XCTAssertEqual(AnteprimaLogica.club(nil), "")
    }

    // MARK: una squadra basta

    func testScambiConUnaSolaRosaChiedonoLeAltre() throws {
        let una: [SquadraLega] = try Decodifica.decodifica(Data(#"[{"nome": "Real Fantasia", "mia": true}]"#.utf8))
        let due: [SquadraLega] = try Decodifica.decodifica(Data(#"[{"nome": "Real Fantasia", "mia": true}, {"nome": "Atletico Pigiama"}]"#.utf8))
        let soloAltra: [SquadraLega] = try Decodifica.decodifica(Data(#"[{"nome": "Atletico Pigiama"}]"#.utf8))
        XCTAssertTrue(ScambiLogica.servonoAltreRose(una))
        XCTAssertTrue(ScambiLogica.servonoAltreRose(soloAltra))
        XCTAssertTrue(ScambiLogica.servonoAltreRose([]))
        XCTAssertFalse(ScambiLogica.servonoAltreRose(due))
    }

    @MainActor
    func testScambiViewModelSaQuandoServonoLeAltreRose() async {
        let s = ServerDiProva { _, _, _ in Data(#"[{"nome": "Real Fantasia", "mia": true, "giocatori": 25}]"#.utf8) }
        let vm = ScambiViewModel(server: s)
        XCTAssertFalse(vm.servonoAltreRose, "finché le squadre non sono lette si mostra la schermata di sempre")
        await vm.caricaSquadre()
        XCTAssertTrue(vm.servonoAltreRose)
        XCTAssertEqual(s.quante("/api/scambi/proposte"), 0, "nessuna ricerca consumata")
    }
}

/// Il ViewModel: anteprima, scelte, «Conferma e salva», 412, 429, 400, file con i campi del modulo, If-Match dell'anteprima.
@MainActor
final class AnteprimaRoseViewModelTests: XCTestCase {
    private let esito = #"{"squadre_importate": ["Real Fantasia"], "totale_squadre": 2, "avvisi": [], "mia_squadra": "Real Fantasia", "riepilogo": "Fatto"}"#

    /// Risponde con l'anteprima per `/api/rose/anteprima*` e con l'esito per il resto.
    private func server(indirizzo: String = "https://prova-\(UUID().uuidString).invalid",
                        salva: (@Sendable (String) throws -> Void)? = nil) -> ServerDiProva {
        let esito = self.esito
        return ServerDiProva(indirizzo: indirizzo) { _, percorso, _ in
            if percorso.hasPrefix("/api/rose/anteprima") { return Data(AnteprimaRoseTests.risposta.utf8) }
            try salva?(percorso)
            return Data(esito.utf8)
        }
    }

    private func oggetto(_ dati: Data?) throws -> [String: Any] {
        try XCTUnwrap(JSONSerialization.jsonObject(with: try XCTUnwrap(dati)) as? [String: Any])
    }

    func testDalTestoAllAnteprimaPoiSalvaConScelteESquadra() async throws {
        let s = server()
        let vm = ImportaExcelViewModel(server: s)
        vm.testoRose = "Real Fantasia\nPirlotti\n..."
        await vm.importaTesto()
        XCTAssertNil(vm.errore)
        XCTAssertEqual(vm.anteprima?.squadre.count, 2)
        XCTAssertEqual(vm.mia, "Real Fantasia", "preselezionata con mia_squadra")
        XCTAssertEqual(s.quante("POST /api/rose/testo"), 0, "l'anteprima non salva")
        let anteprima = try oggetto(s.corpiInviati(a: "POST /api/rose/anteprima").last)
        XCTAssertEqual(anteprima["sostituisci_tutto"] as? Bool, false)

        vm.scegli(.togli, squadra: "Real Fantasia", testo: "Quintavalle")
        vm.scegli(trovato: CandidatoAnteprima(id: 905, nome: "Rino Bertolazzi", ruolo: "A", squadra: "lazio"), squadra: "Real Fantasia", testo: "Bertolazzi")
        vm.mia = "Atletico Pigiama"
        await vm.conferma()

        XCTAssertNil(vm.errore)
        XCTAssertEqual(vm.esito?.riepilogo, "Fatto")
        XCTAssertNil(vm.anteprima)
        XCTAssertEqual(vm.testoRose, "", "dopo il salvataggio il testo con i nomi della lega non resta")
        let corpo = try oggetto(s.corpiInviati(a: "POST /api/rose/testo").last)
        XCTAssertEqual(corpo["testo"] as? String, "Real Fantasia\nPirlotti\n...")
        XCTAssertEqual(corpo["mia_squadra"] as? String, "Atletico Pigiama")
        let correzioni = try XCTUnwrap(corpo["correzioni"] as? [[String: Any]])
        XCTAssertEqual(correzioni.count, 3)
        XCTAssertEqual(correzioni.map { $0["testo"] as? String }, ["Mancuzzi", "Bertolazzi", "Quintavalle"])
        XCTAssertEqual(correzioni[0]["id"] as? Int, 903)
        XCTAssertEqual(correzioni[1]["id"] as? Int, 905)
        XCTAssertTrue(correzioni[2]["id"] is NSNull)
    }

    func testSenzaScelteNonSiMandanoCampiVuoti() async throws {
        let s = ServerDiProva { _, percorso, _ in
            if percorso.hasPrefix("/api/rose/anteprima") {
                return Data(#"{"squadre": [{"nome": "A", "giocatori": [{"testo": "X", "stato": "sicuro", "id": 1}]}, {"nome": "B", "giocatori": []}]}"#.utf8)
            }
            return Data("{}".utf8)
        }
        let vm = ImportaExcelViewModel(server: s)
        vm.testoRose = "A\nX"
        await vm.importaTesto()
        XCTAssertEqual(vm.mia, "", "con due squadre e nessun suggerimento non si sceglie al posto dell'utente")
        await vm.conferma()
        let corpo = try oggetto(s.corpiInviati(a: "POST /api/rose/testo").last)
        XCTAssertNil(corpo["correzioni"])
        XCTAssertNil(corpo["mia_squadra"])
    }

    func testRoseCambiateNelFrattempoRifaLAnteprimaTenendoLeScelte() async throws {
        let volte = Scatola<Int>()
        volte.valore = 0
        let s = server { _ in
            volte.valore = (volte.valore ?? 0) + 1
            if volte.valore == 1 { throw ErroreApi.conflitto }
        }
        let vm = ImportaExcelViewModel(server: s)
        vm.testoRose = "Real Fantasia"
        await vm.importaTesto()
        vm.scegli(.togli, squadra: "Real Fantasia", testo: "Mancuzzi")
        vm.mia = "Atletico Pigiama"
        await vm.conferma()
        XCTAssertNil(vm.esito)
        XCTAssertNotNil(vm.anteprima, "si torna all'anteprima, riletta")
        XCTAssertEqual(s.quante("POST /api/rose/anteprima"), 2)
        XCTAssertEqual(vm.messaggioAnteprima, ImportaExcelViewModel.roseCambiate)
        XCTAssertEqual(vm.scelte[AnteprimaLogica.chiave("Real Fantasia", "Mancuzzi")], .togli, "le scelte restano")
        XCTAssertEqual(vm.mia, "Atletico Pigiama", "la squadra scelta resta")
        XCTAssertNil(vm.errore)
        await vm.conferma()
        XCTAssertEqual(vm.esito?.riepilogo, "Fatto")
    }

    func testTroppeImportazioniDiceQuandoRiprovare() async {
        let s = ServerDiProva { _, _, _ in throw ErroreApi.troppiTentativi("Hai fatto troppe importazioni oggi.", riprovaTra: 600) }
        let vm = ImportaExcelViewModel(server: s)
        vm.testoRose = "x"
        await vm.importaTesto()
        XCTAssertNil(vm.anteprima)
        XCTAssertEqual(vm.errore, "Hai fatto troppe importazioni oggi. Riprova tra 10 minuti.")
        XCTAssertFalse(vm.inCorso)
    }

    func testUnaSceltaRifiutataMostraIlMessaggioDelServerERestaNellAnteprima() async {
        let s = server { _ in throw ErroreApi.server("Uno dei giocatori scelti non è nel listone: rifai il controllo delle rose e scegli di nuovo.") }
        let vm = ImportaExcelViewModel(server: s)
        vm.testoRose = "Real Fantasia"
        await vm.importaTesto()
        await vm.conferma()
        XCTAssertNil(vm.esito)
        XCTAssertNotNil(vm.anteprima)
        XCTAssertEqual(vm.errore, "Uno dei giocatori scelti non è nel listone: rifai il controllo delle rose e scegli di nuovo.")
        XCTAssertEqual(vm.testoRose, "Real Fantasia", "niente si perde")
    }

    func testAnnullaTornaAlTesto() async {
        let vm = ImportaExcelViewModel(server: server())
        vm.testoRose = "Real Fantasia"
        await vm.importaTesto()
        vm.annulla()
        XCTAssertNil(vm.anteprima)
        XCTAssertEqual(vm.testoRose, "Real Fantasia")
    }

    func testUnFileMandaCorrezioniESquadraComeCampiDelModulo() async throws {
        let s = server()
        let vm = ImportaExcelViewModel(server: s)
        vm.sostituisciTutto = true
        let url = FileManager.default.temporaryDirectory.appendingPathComponent("rose-\(UUID().uuidString).csv")
        try Data("Real Fantasia;P;Pirlotti\n".utf8).write(to: url)
        defer { try? FileManager.default.removeItem(at: url) }
        await vm.importa(.success([url]))
        XCTAssertEqual(s.quante("UPLOAD /api/rose/anteprima/file?sostituisci_tutto=true"), 1)
        vm.sostituisciTutto = false   // cambiarlo dopo l'anteprima non cambia cosa si salva
        vm.scegli(.togli, squadra: "Real Fantasia", testo: "Quintavalle")
        await vm.conferma()
        XCTAssertEqual(s.quante("UPLOAD /api/rose/file?sostituisci_tutto=true"), 1)
        let campi = try XCTUnwrap(s.campiCaricati.last)
        XCTAssertEqual(campi.map(\.nome), ["correzioni", "mia_squadra"])
        XCTAssertEqual(campi.last?.valore, "Real Fantasia")
        let correzioni = try XCTUnwrap(JSONSerialization.jsonObject(with: Data(campi[0].valore.utf8)) as? [[String: Any]])
        XCTAssertEqual(correzioni.map { $0["testo"] as? String }, ["Mancuzzi", "Quintavalle"])
        XCTAssertTrue(correzioni[1]["id"] is NSNull)
        XCTAssertEqual(s.campiCaricati.first, [], "l'anteprima manda solo il file")
        XCTAssertEqual(vm.esito?.riepilogo, "Fatto")
    }

    func testIlSalvataggioRimandaLETagDellAnteprima() async throws {
        let indirizzo = "https://prova-etag-\(UUID().uuidString).invalid"
        let visto = Scatola<String>()
        let s = ServerDiProva(indirizzo: indirizzo) { _, percorso, _ in
            if percorso.hasPrefix("/api/rose/anteprima") {
                VersioniRisorse.condivise.imposta("\"anteprima-1\"", server: indirizzo, risorsa: "rose")   // come fa ServerHTTP con l'ETag
                return Data(AnteprimaRoseTests.risposta.utf8)
            }
            visto.valore = VersioniRisorse.condivise.leggi(server: indirizzo, risorsa: "rose")
            return Data("{}".utf8)
        }
        let vm = ImportaExcelViewModel(server: s)
        vm.testoRose = "Real Fantasia"
        await vm.importaTesto()
        XCTAssertEqual(vm.etagAnteprima, "\"anteprima-1\"")
        // un'altra schermata rilegge le squadre nel frattempo: l'ETag ricordato cambia
        VersioniRisorse.condivise.imposta("\"dopo\"", server: indirizzo, risorsa: "rose")
        await vm.conferma()
        XCTAssertEqual(visto.valore, "\"anteprima-1\"", "If-Match = l'ETag dell'anteprima, non quello letto dopo")
    }
}

/// Il trasporto vero: i campi del modulo e If-Match sull'invio di un file delle rose.
final class InvioModuloRoseTests: XCTestCase {
    func testCampiDelModuloEIfMatchSoloPerLeRose() async throws {
        let configurazione = URLSessionConfiguration.ephemeral
        configurazione.protocolClasses = [ProtocolloFinto.self]
        let server = ServerHTTP(sessione: URLSession(configuration: configurazione), archivioToken: MemoriaToken())
        let indirizzo = "https://prova-modulo.invalid"
        let prima = UserDefaults.standard.string(forKey: "indirizzo")
        UserDefaults.standard.set(indirizzo, forKey: "indirizzo")
        defer {
            if let prima { UserDefaults.standard.set(prima, forKey: "indirizzo") } else { UserDefaults.standard.removeObject(forKey: "indirizzo") }
            ProtocolloFinto.gestore = nil
            VersioniRisorse.condivise.azzera()
        }
        VersioniRisorse.condivise.imposta("\"v1\"", server: indirizzo, risorsa: "rose")
        ProtocolloFinto.gestore = { r in
            (HTTPURLResponse(url: r.url ?? URL(fileURLWithPath: "/"), statusCode: 200, httpVersion: nil, headerFields: ["ETag": "\"v2\""]) ?? HTTPURLResponse(),
             Data("{}".utf8))
        }

        _ = try await server.carica("/api/rose/file", nome: "rose.csv", dati: Data("A;P;S".utf8), tipo: "text/csv",
                                    campi: [CampoModulo(nome: "correzioni", valore: #"[{"squadra":"A","testo":"S","id":null}]"#),
                                            CampoModulo(nome: "mia_squadra", valore: "Real Fantasia")])
        XCTAssertEqual(ProtocolloFinto.ultimaRichiesta?.value(forHTTPHeaderField: "If-Match"), "\"v1\"")
        let corpo = String(decoding: try XCTUnwrap(ProtocolloFinto.ultimoCorpo), as: UTF8.self)
        XCTAssertTrue(corpo.contains("name=\"correzioni\"\r\n\r\n[{\"squadra\":\"A\",\"testo\":\"S\",\"id\":null}]\r\n"), corpo)
        XCTAssertTrue(corpo.contains("name=\"mia_squadra\"\r\n\r\nReal Fantasia\r\n"), corpo)
        XCTAssertTrue(corpo.contains("name=\"file\"; filename=\"rose.csv\""), corpo)
        XCTAssertEqual(VersioniRisorse.condivise.leggi(server: indirizzo, risorsa: "rose"), "\"v2\"", "l'ETag nuovo si ricorda")

        // stemma e maglia: niente If-Match (come prima)
        _ = try await server.carica("/api/squadre/immagine?squadra=A&tipo=stemma", nome: "a.png", dati: Data([1, 2]))
        XCTAssertNil(ProtocolloFinto.ultimaRichiesta?.value(forHTTPHeaderField: "If-Match"))
    }
}
