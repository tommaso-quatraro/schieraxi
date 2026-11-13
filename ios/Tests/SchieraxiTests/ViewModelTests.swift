import XCTest
@testable import Schieraxi

/// ViewModel della giornata, della Formazione, della ricerca e della scheda con un server finto che risponde con le fixture (risposte vere del server).
@MainActor
final class OggiViewModelTests: XCTestCase {
    private func vm(_ server: ServerDiProva) -> OggiViewModel { OggiViewModel(server: server, conPromemoria: false) }

    func testCaricaLaGiornata() async throws {
        let server = ServerDiProva.conFixture(["/api/oggi": "oggi", "/api/stato": "stato"])
        let vm = vm(server)
        XCTAssertNil(vm.oggi)
        await vm.carica()
        XCTAssertEqual(vm.oggi?.giornata, 9)
        XCTAssertNil(vm.errore)
        XCTAssertEqual(server.quante("GET /api/oggi"), 1)
        XCTAssertEqual(server.quante("/api/live"), 0, "le partite in diretta non ci sono più (#634): Oggi non le chiede")
        XCTAssertEqual(server.quante("/api/stato"), 0, "né la versione del server, che serviva al banner delle novità")
    }

    func testServerSpentoMostraUnErroreInItaliano() async throws {
        let vm = vm(.chePrecipita())
        await vm.carica()
        XCTAssertNil(vm.oggi)
        XCTAssertEqual(vm.errore, "Non riesco a collegarmi a SchieraXI. Controlla la connessione e riprova.")
    }

    func testIlComandoAggiornaRicaricaOggi() async throws {
        let server = ServerDiProva.conFixture(["/api/oggi": "oggi", "/api/stato": "stato"])
        let vm = vm(server)
        await vm.carica()
        NotificationCenter.default.post(name: .aggiornaTutto, object: nil)
        await attendi("seconda richiesta di /api/oggi", finche: { server.quante("GET /api/oggi") >= 2 })
        withExtendedLifetime(vm) {}
    }
}

/// La Formazione unica (#673) con un server finto che risponde con le fixture: in campo la consigliata o la tua scelta salvata, un
/// solo stile, il modulo come menu, la scelta letta (e valutata se non è un modulo già calcolato), la formazione di un'altra squadra.
/// I salvataggi automatici stanno in `SalvataggioAutomaticoTests`, la giornata chiusa in `FormazioneChiusaTests`.
@MainActor
final class FormazioneViewModelTests: XCTestCase {
    /// Un server con la formazione della fixture, la scelta salvata (i suoi 11; nil = nessuna) e una valutazione che risponde
    /// 20 punti a qualunque formazione. `letturaGiu`: la lettura della scelta non riesce.
    private func server(scelta: [Int]? = nil, letturaGiu: Bool = false) -> ServerDiProva {
        ServerDiProva { metodo, percorso, _ in
            if percorso.hasPrefix("/api/formazione/valuta") {
                return Data(#"{"modulo": "4-3-3", "punteggio_atteso": 20.0, "dev": 4.0, "panchina": [], "intervallo": {"basso": 12, "alto": 29}}"#.utf8)
            }
            if percorso.hasPrefix("/api/scelta") {
                if metodo != "GET" { return Data("{\"ok\": true}".utf8) }
                if letturaGiu { throw ErroreApi.rete("giù") }
                guard let scelta else { return Data("null".utf8) }
                return Data("{\"titolari\": [\(scelta.map(String.init).joined(separator: ","))], \"salvata\": \"2026-11-02T21:40:00\"}".utf8)
            }
            if percorso.hasPrefix("/api/formazione") { return try Fixture.dati("formazione") }
            throw ErroreApi.server("nessuna fixture per \(percorso)")
        }
    }

    private func caricata(_ s: ServerDiProva) async throws -> (FormazioneViewModel, Formazione) {
        let vm = FormazioneViewModel(server: s)
        await vm.carica()
        let f = try XCTUnwrap(vm.formazione)
        return (vm, f)
    }

    /// Lo stile equilibrato della fixture e un suo modulo diverso dal consigliato (5-3-2: 2 titolari diversi, −0,4 punti attesi).
    private func moduli() throws -> (consigliato: OpzioneModulo, altro: OpzioneModulo) {
        let f: Formazione = try Fixture.decodifica("formazione")
        let livello = try XCTUnwrap(f.livelli?.first { $0.rischio == 0 })
        let consigliato = try XCTUnwrap(livello.moduli.first { $0.modulo == livello.modulo })
        let altro = try XCTUnwrap(livello.moduli.first { $0.modulo != livello.modulo })
        return (consigliato, altro)
    }

    func testLaFormazioneConsigliata() async throws {
        let (vm, f) = try await caricata(server())
        let v = vm.vista(f)
        XCTAssertEqual(v.modulo, "4-3-3")
        XCTAssertEqual(v.titolari.count, 11)
        XCTAssertEqual(v.panchina.count, 11)
        XCTAssertEqual(try XCTUnwrap(v.punti), 71.1, accuracy: 0.01)
        XCTAssertNil(vm.manuale)
        XCTAssertEqual(vm.statoScelta, .consigliata)
        XCTAssertFalse(vm.comandiSpenti)
        XCTAssertEqual(vm.testo(f).components(separatedBy: "\n").first, "9ª giornata di Serie A · 4-3-3", "la fixture non ha `giornata_lega`")
        // 25 in rosa, 11 titolari e 11 in panchina: i 3 rimasti sono infortunati
        XCTAssertEqual(vm.nonSchierati(f, v).count, 0)
        XCTAssertEqual(vm.indisponibili(f, v).count, 3)
        XCTAssertTrue(vm.indisponibili(f, v).allSatisfy { FormazioneViewModel.nonGioca($0) })
    }

    /// Un solo stile dal 12/11/2026 (#634): moduli, punti e fascia sono quelli dello stile equilibrato (rischio 0), anche se il
    /// server manda ancora gli altri livelli. Il menu dei moduli scrive le voci come la web.
    func testSoloLoStileEquilibratoEIlMenuDeiModuli() async throws {
        let (vm, f) = try await caricata(server())
        XCTAssertGreaterThan(f.livelli?.count ?? 0, 1, "la fixture ha più stili, come il server")
        XCTAssertNotEqual(f.livelli?.first?.rischio, 0, "nella fixture lo stile equilibrato non è il primo: non lo si sceglie per caso")
        let equilibrata = try XCTUnwrap(f.livelli?.first { $0.rischio == 0 })
        XCTAssertEqual(vm.livello(f)?.rischio, 0)
        let (consigliato, altro) = try moduli()
        XCTAssertEqual(vm.vista(f).modulo, equilibrata.modulo)
        XCTAssertEqual(try XCTUnwrap(vm.vista(f).punti), consigliato.punteggioAtteso, accuracy: 0.001)
        XCTAssertEqual(vm.moduli(f).map(\.modulo), equilibrata.moduli.map(\.modulo))
        XCTAssertEqual(vm.etichettaModulo(consigliato, f), "4-3-3 · 71,1 punti · consigliato")
        XCTAssertEqual(vm.etichettaModulo(altro, f), "5-3-2 · 70,7 punti")
        XCTAssertEqual(vm.fascia(f), "oscilla di ±4", "la fixture ha solo la deviazione del modulo")
    }

    /// Un server che non manda lo stile equilibrato: vale il primo livello; senza `livelli` niente livello (e la consigliata).
    func testSenzaLoStileEquilibrato() throws {
        let vm = FormazioneViewModel(server: server())
        let soloSicura = Data(#"""
        {"giornata": 9, "modulo": "4-3-3", "punteggio_atteso": 60.5, "titolari": [], "panchina": [],
         "livelli": [{"rischio": -1, "stile": -1, "nome": "Sicura", "modulo": "5-3-2", "punteggio_atteso": 59.0, "moduli": []}]}
        """#.utf8)
        let f: Formazione = try Decodifica.decodifica(soloSicura, snake: true)
        XCTAssertEqual(vm.livello(f)?.rischio, -1)
        let senza: Formazione = try Decodifica.decodifica(
            Data(#"{"giornata": 9, "modulo": "4-3-3", "punteggio_atteso": 60.5, "titolari": [], "panchina": []}"#.utf8), snake: true)
        XCTAssertNil(vm.livello(senza))
        XCTAssertEqual(vm.vista(senza).modulo, "4-3-3")
        XCTAssertTrue(vm.moduli(senza).isEmpty, "senza moduli il modulo resta fisso")
    }

    func testStileConDescrizioneESenza() throws {
        let nuovo = Data(#"""
        {"giornata": 9, "modulo": "4-3-3", "punteggio_atteso": 60.5, "titolari": [], "panchina": [], "stile_consigliato": 0,
         "livelli": [{"rischio": -1, "stile": -1, "nome": "Sicura", "descrizione": "Preferisce i titolari più sicuri.", "modulo": "5-3-2",
                      "punteggio_atteso": 59.0, "moduli": []}]}
        """#.utf8)
        let f: Formazione = try Decodifica.decodifica(nuovo, snake: true)
        XCTAssertEqual(f.stileConsigliato, 0)
        XCTAssertEqual(f.livelli?.first?.stile, -1)
        XCTAssertEqual(f.livelli?.first?.descrizione, "Preferisce i titolari più sicuri.")
        // un server vecchio non manda i campi nuovi: la formazione si legge lo stesso
        let vecchia: Formazione = try Fixture.decodifica("formazione")
        XCTAssertNotNil(vecchia.livelli)
        XCTAssertNil(vecchia.giornataSaltata)
    }

    func testLaSceltaSalvataSiVedeAncheRiaprendo() async throws {
        let (_, altro) = try moduli()
        let srv = server(scelta: altro.titolari)
        let (vm, f) = try await caricata(srv)
        XCTAssertEqual(vm.manuale, altro.titolari)
        XCTAssertEqual(vm.vista(f).modulo, altro.modulo)
        XCTAssertEqual(try XCTUnwrap(vm.vista(f).punti), altro.punteggioAtteso, accuracy: 0.001, "un modulo già calcolato: i suoi punti")
        XCTAssertEqual(vm.statoScelta.frase, "L'hai cambiata tu: 2 titolari diversi dalla consigliata (\u{2212}0,4 punti attesi).")
        XCTAssertEqual(srv.quante("POST /api/formazione/valuta"), 0, "un modulo già calcolato non si valuta")
        // tornando sulla Formazione si rilegge, e resta lei
        await vm.carica()
        XCTAssertEqual(vm.manuale, altro.titolari)
        XCTAssertEqual(srv.quante("GET /api/scelta"), 2)
        XCTAssertEqual(srv.quante("POST /api/formazione/valuta"), 0)
    }

    func testUnaSceltaFuoriDaiModuliLaValutaIlServerSenzaSalvare() async throws {
        let f0: Formazione = try Fixture.decodifica("formazione")
        // la consigliata con un difensore diverso (6994 al posto di 6523): non è un modulo già calcolato
        let scelta = f0.titolari.map(\.id).map { $0 == 6523 ? 6994 : $0 }
        let srv = server(scelta: scelta)
        let (vm, f) = try await caricata(srv)
        XCTAssertEqual(vm.manuale, scelta)
        XCTAssertEqual(vm.vista(f).punti, 20.0, "i punti della valutazione del server")
        XCTAssertEqual(vm.fascia(f), "di solito fra 12 e 29")
        let corpo = String(decoding: try XCTUnwrap(srv.corpiInviati(a: "POST /api/formazione/valuta").last), as: UTF8.self)
        XCTAssertTrue(corpo.contains("\"salva\":false"), corpo)
        XCTAssertEqual(vm.statoScelta, .cambiata(diversi: 1, punti: 20.0 - 71.1))
    }

    func testSeLaLetturaDellaSceltaNonRiesceLoDiceENonSiCambiaNiente() async throws {
        let srv = server(letturaGiu: true)
        let (vm, f) = try await caricata(srv)
        XCTAssertEqual(vm.statoScelta, .nonLetta, "non si dice «è la consigliata» se non lo si sa")
        XCTAssertTrue(vm.comandiSpenti)
        let (_, altro) = try moduli()
        await vm.scegliModulo(altro.modulo)
        let uscente = try XCTUnwrap(vm.vista(f).titolari.first)
        XCTAssertFalse(vm.sostituibile(uscente.id))
        XCTAssertEqual(srv.quante("POST"), 0, "una scrittura andrebbe sopra una scelta che non si è vista")
        XCTAssertNil(vm.manuale)
    }

    func testUnaSceltaCheIlServerNonValutaPiuNonSiCancellaDaSola() async throws {
        let f0: Formazione = try Fixture.decodifica("formazione")
        let scelta = f0.titolari.map(\.id).map { $0 == 6523 ? 6994 : $0 }
        let srv = ServerDiProva { metodo, percorso, _ in
            if percorso.hasPrefix("/api/formazione/valuta") {
                throw ErroreApi.codificato(codice: ValiditaScelta.codiceNonValida, messaggio: "Servono 11 titolari diversi, tutti della rosa")
            }
            if percorso.hasPrefix("/api/scelta") {
                if metodo == "DELETE" { return Data("{\"ok\": true}".utf8) }
                return Data("{\"titolari\": [\(scelta.map(String.init).joined(separator: ","))]}".utf8)
            }
            return try Fixture.dati("formazione")
        }
        let (vm, f) = try await caricata(srv)
        XCTAssertEqual(vm.statoScelta, .nonValida)
        XCTAssertNil(vm.manuale, "in campo la consigliata")
        XCTAssertEqual(Set(vm.vista(f).titolari.map(\.id)), Set(f0.titolari.map(\.id)))
        XCTAssertEqual(srv.quante("DELETE"), 0, "non si cancella da sola")
        await vm.tornaAllaConsigliata()
        XCTAssertEqual(srv.quante("DELETE /api/scelta?giornata=9"), 1)
        XCTAssertEqual(vm.statoScelta, .consigliata)
        XCTAssertNil(vm.salvata)
    }

    func testSeIlServerNonCancellaLaSceltaRestaDovEra() async throws {
        let ids = try moduli().altro.titolari
        let s = ServerDiProva { metodo, percorso, _ in
            if metodo == "DELETE" { throw ErroreApi.rete("giù") }
            if percorso.hasPrefix("/api/scelta") {
                return Data("{\"titolari\": [\(ids.map(String.init).joined(separator: ","))]}".utf8)
            }
            return try Fixture.dati("formazione")
        }
        let (vm, _) = try await caricata(s)
        await vm.tornaAllaConsigliata()
        XCTAssertEqual(vm.manuale, ids, "la scelta salvata non è stata cancellata: resta in campo")
        XCTAssertNotNil(vm.messaggio)
        XCTAssertFalse(vm.occupato)
    }

    func testFormazioneDiUnAltraSquadraSiGuardaEBasta() async throws {
        let s = server()
        let (vm, _) = try await caricata(s)
        vm.vediSquadra("Gli Amici")
        XCTAssertEqual(vm.squadraVista, "Gli Amici")
        XCTAssertEqual(vm.percorso, "/api/formazione?squadra=Gli%20Amici")
        // Non basta che la richiesta sia partita: finché la risposta non arriva il caricatore è in «loading» senza dati (indirizzo
        // nuovo). Si aspetta la formazione della squadra caricata davvero.
        await attendi("caricamento della squadra", finche: {
            s.quante("GET /api/formazione?squadra=Gli%20Amici") >= 1 && !vm.caricatore.inCorso && vm.formazione != nil
        })
        let f = try XCTUnwrap(vm.formazione)
        XCTAssertEqual(vm.statoScelta, .nessuno, "niente riga dello stato per un'altra squadra")
        XCTAssertTrue(vm.decisioni(nil, tecniche: false).isEmpty)
        // un altro modulo si guarda e basta: niente salvataggi
        let (_, altro) = try moduli()
        await vm.scegliModulo(altro.modulo)
        XCTAssertEqual(vm.vista(f).modulo, altro.modulo)
        XCTAssertNil(vm.manuale)
        XCTAssertEqual(s.quante("POST"), 0)
        XCTAssertFalse(vm.sostituibile(try XCTUnwrap(vm.vista(f).titolari.first).id), "niente «Sostituisci» per un'altra squadra")
        await vm.tornaAllaConsigliata()
        XCTAssertEqual(vm.vista(f).modulo, "4-3-3", "«Torna alla consigliata» rimette il modulo consigliato, senza cancellare niente")
        XCTAssertEqual(s.quante("DELETE"), 0)
        XCTAssertEqual(s.quante("GET /api/scelta"), 1, "la scelta salvata si legge solo per la propria squadra (una volta, all'inizio)")
        vm.tornaAllaMia()
        XCTAssertNil(vm.squadraVista)
        XCTAssertEqual(vm.percorso, "/api/formazione")
    }
}

@MainActor
final class RicercaESchedaViewModelTests: XCTestCase {
    func testRicercaConPausaEAnnullamento() async throws {
        let s = ServerDiProva { _, percorso, _ in
            if percorso.hasPrefix("/api/giocatori") { return Data(#"[{"id": 1, "nome": "Marco Rossi", "ruolo": "A", "squadra": "inter", "quotazione": 10}]"#.utf8) }
            throw ErroreApi.server("niente")
        }
        let vm = RicercaViewModel(server: s)
        vm.testo = "m"
        await vm.cerca()
        XCTAssertTrue(vm.risultati.isEmpty)
        XCTAssertEqual(s.quante("/api/giocatori"), 0, "con una sola lettera non si cerca")
        // la ricerca annullata (si continua a scrivere) non arriva al server
        vm.testo = "mar"
        let annullata = Task { await vm.cerca() }
        annullata.cancel()
        await annullata.value
        XCTAssertEqual(s.quante("/api/giocatori"), 0)
        // quella vera sì, con il nome codificato
        vm.testo = "mar co"
        await vm.cerca()
        XCTAssertEqual(vm.risultati.map(\.nome), ["Marco Rossi"])
        XCTAssertEqual(s.quante("GET /api/giocatori?limite=25&q=mar%20co"), 1)
        XCTAssertNil(vm.errore)
    }

    func testRicercaConErrore() async {
        let vm = RicercaViewModel(server: ServerDiProva.chePrecipita())
        vm.testo = "mar"
        await vm.cerca()
        XCTAssertNotNil(vm.errore)
        XCTAssertTrue(vm.risultati.isEmpty)
    }

    func testSchedaDelGiocatoreConLeProssimePartite() async throws {
        let s = ServerDiProva.conFixture(["/api/giocatore/": "giocatore", "/api/calendario": "calendario"])
        let vm = SchedaGiocatoreViewModel(id: 5585, server: s)
        await vm.carica()
        XCTAssertEqual(vm.caricatore.dato?.calciatore.nome, "Malvi")
        XCTAssertEqual(vm.prossime.first?.avversario, "cagliari", "dal calendario della sua squadra (roma)")
        XCTAssertEqual(s.quante("/api/osservati"), 0, "i seguiti non ci sono più (#634): la scheda non li chiede")
        XCTAssertEqual(s.quante("/api/formazione"), 0, "né la formazione, che serviva al confronto")
    }
}
