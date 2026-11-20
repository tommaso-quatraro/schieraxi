import Foundation
import Testing
@testable import Schieraxi

/// Un salvataggio automatico della Formazione che non riesce quando sei già su un'altra scheda (#726), come `nonSalvata` di
/// `mostraFormazione` della web (#667, PR #724): lasciata la Formazione l'avviso nomina la formazione, con le frasi del catalogo
/// `formazione.non_salvata_rete` (rete giù o server troppo lento) e `formazione.non_salvata` (rifiuto del server); nella tua
/// Formazione resta l'avviso di prima, con il motivo. Tornando sulla Formazione l'avviso delle altre schede se ne va e lì compare
/// quello di sempre, a ogni ritorno, finché un salvataggio non riesce (o arriva la giornata dopo): un guasto resta visibile anche
/// se l'avviso in basso è passato sotto un foglio. Un salvataggio che riesce non lascia avvisi. Le scritture sono una alla volta,
/// quindi quella che non riesce è sempre l'ultima partita dalla Formazione.
/// Il 412 (scelta cambiata da un altro dispositivo) a scheda lasciata ha la frase della web, `comune.cambiato_altrove`, nello stesso
/// avviso in basso (#751); guardando un'altra squadra la stessa frase sotto il campo.
/// Il cambio di scheda è `inVista`, che nell'app imposta la radice. Dati inventati (fixture).
@MainActor
@Suite("Formazione: salvataggio non riuscito a scheda lasciata, come la web (#726)", .timeLimit(.minutes(1)))
struct SalvataggioFuoriDallaFormazioneTests {
    @Test("Lasciata la Formazione, un salvataggio che non riesce dà un avviso che nomina la formazione, con il motivo giusto",
          arguments: [
              (ErroreApi.rete("spento"), Catalogo.Formazione.nonSalvataRete),
              (ErroreApi.timeout, Catalogo.Formazione.nonSalvataRete),
              (ErroreApi.senzaRete, Catalogo.Formazione.nonSalvataRete),
              (ErroreApi.server("Un giocatore di prova gioca una partita già cominciata."), Catalogo.Formazione.nonSalvata),
              (ErroreApi.codificato(codice: "formazione_chiusa", messaggio: "La formazione di prova è chiusa."),
               Catalogo.Formazione.nonSalvata),
          ])
    func lasciataLaFormazione(errore: ErroreApi, frase: String) async throws {
        let cancello = Cancello()
        let esito = Scatola<ErroreApi>()
        esito.valore = errore
        let (vm, f) = try await Self.caricata(try Self.server(cancello: cancello, esito: esito))
        let (esce, entra) = try SalvataggioAutomaticoTests.cambio(f, vm)
        let salvataggio = Task { await vm.sostituisciTitolare(esce, con: entra) }
        await cancello.richiestaArrivata()
        vm.inVista = false                      // tocca Giornate mentre il salvataggio è in volo
        await cancello.apri()
        _ = await salvataggio.value
        #expect(vm.avvisoAltrove == frase)
        #expect(vm.messaggio == nil, "finché sei sull'altra scheda l'avviso è quello in basso, non quello della Formazione")
    }

    @Test("«Torna alla consigliata» che non riesce a scheda lasciata: lo stesso avviso")
    func consigliataFuori() async throws {
        let cancello = Cancello()
        let esito = Scatola<ErroreApi>()
        esito.valore = .rete("spento")
        let srv = try Self.server(cancello: cancello, esito: esito, salvata: try SalvataggioAutomaticoTests.altroModulo())
        let (vm, _) = try await Self.caricata(srv)
        try #require(vm.salvata != nil, "c'è una scelta salvata: «Torna alla consigliata» la toglie")
        let togli = Task { await vm.tornaAllaConsigliata() }
        await cancello.richiestaArrivata()
        vm.inVista = false
        await cancello.apri()
        await togli.value
        #expect(vm.avvisoAltrove == Catalogo.Formazione.nonSalvataRete)
        #expect(vm.messaggio == nil)
    }

    @Test("Nella tua Formazione resta l'avviso di prima, con il motivo, e sulle altre schede niente")
    func nellaFormazione() async throws {
        let cancello = Cancello()
        await cancello.apri()
        let esito = Scatola<ErroreApi>()
        esito.valore = .rete("spento")
        let (vm, f) = try await Self.caricata(try Self.server(cancello: cancello, esito: esito))
        let (esce, entra) = try SalvataggioAutomaticoTests.cambio(f, vm)
        let fatto = await vm.sostituisciTitolare(esce, con: entra)
        #expect(fatto)
        #expect(vm.messaggio == ErroreApi.testoNonRaggiungibile)
        #expect(vm.avvisoAltrove == nil)
    }

    @Test("Guardando la formazione di un'altra squadra l'avviso nomina la formazione anche nella Formazione, come la web")
    func altraSquadra() async throws {
        let cancello = Cancello()
        let esito = Scatola<ErroreApi>()
        esito.valore = .rete("spento")
        let (vm, f) = try await Self.caricata(try Self.server(cancello: cancello, esito: esito))
        let (esce, entra) = try SalvataggioAutomaticoTests.cambio(f, vm)
        let salvataggio = Task { await vm.sostituisciTitolare(esce, con: entra) }
        await cancello.richiestaArrivata()
        vm.vediSquadra("Squadra di prova")      // da Impostazioni › Le altre squadre: la Formazione si apre con la loro
        await cancello.apri()
        _ = await salvataggio.value
        #expect(vm.messaggio == Catalogo.Formazione.nonSalvataRete)
        #expect(vm.avvisoAltrove == nil)
    }

    @Test("Lasciata la Formazione, un salvataggio che riesce non dà avvisi")
    func riuscitoFuori() async throws {
        let cancello = Cancello()
        let (vm, f) = try await Self.caricata(try Self.server(cancello: cancello, esito: Scatola()))
        let altro = try #require(vm.moduli(f).first { $0.modulo != vm.consigliato(f)?.modulo })
        let salvataggio = Task { await vm.scegliModulo(altro.modulo) }
        await cancello.richiestaArrivata()
        vm.inVista = false
        await cancello.apri()
        await salvataggio.value
        #expect(vm.avvisoAltrove == nil && vm.messaggio == nil)
        #expect(vm.salvata?.titolari == altro.titolari)
    }

    @Test("Tornando sulla Formazione l'avviso se ne va; il salvataggio dopo riesce e lasciandola di nuovo non c'è nessun avviso")
    func tornaERiprova() async throws {
        let cancello = Cancello()
        let esito = Scatola<ErroreApi>()
        esito.valore = .rete("spento")
        let (vm, f) = try await Self.caricata(try Self.server(cancello: cancello, esito: esito))
        let (esce, entra) = try SalvataggioAutomaticoTests.cambio(f, vm)
        let primo = Task { await vm.sostituisciTitolare(esce, con: entra) }
        await cancello.richiestaArrivata()
        vm.inVista = false
        await cancello.apri()
        _ = await primo.value
        #expect(vm.avvisoAltrove == Catalogo.Formazione.nonSalvataRete)
        vm.inVista = true                       // torna sulla Formazione
        #expect(vm.avvisoAltrove == nil)
        esito.valore = nil                      // la rete è tornata
        let fatto = await vm.sostituisciTitolare(esce, con: entra)
        #expect(fatto)
        vm.inVista = false
        #expect(vm.avvisoAltrove == nil && vm.messaggio == nil)
        #expect(vm.vista(f).titolari.map(\.id).contains(entra))
    }

    // MARK: il guasto resta visibile

    @Test("Un salvataggio non riuscito a scheda lasciata resta visibile: tornando sulla Formazione l'avviso di sempre, a ogni ritorno, finché uno dopo non riesce")
    func guastoAlRitorno() async throws {
        let cancello = Cancello()
        let esito = Scatola<ErroreApi>()
        esito.valore = .rete("spento")
        let (vm, f) = try await Self.caricata(try Self.server(cancello: cancello, esito: esito))
        let (esce, entra) = try SalvataggioAutomaticoTests.cambio(f, vm)
        let primo = Task { await vm.sostituisciTitolare(esce, con: entra) }
        await cancello.richiestaArrivata()
        vm.inVista = false                      // su Giornate, magari con un foglio aperto sopra l'avviso in basso
        await cancello.apri()
        _ = await primo.value
        vm.avvisoAltrove = nil                  // passati gli 8 secondi senza vederlo
        vm.inVista = true                       // torna sulla Formazione
        #expect(vm.messaggio == ErroreApi.testoNonRaggiungibile, "l'avviso di sempre, con il motivo")
        vm.messaggio = nil                      // passati gli 8 secondi anche qui
        vm.inVista = false
        vm.inVista = true
        #expect(vm.messaggio == ErroreApi.testoNonRaggiungibile, "finché non riesce un salvataggio, a ogni ritorno")
        esito.valore = nil                      // la rete è tornata
        let fatto = await vm.sostituisciTitolare(esce, con: entra)
        #expect(fatto)
        #expect(vm.messaggio == nil, "salvata: l'avviso non vale più")
        vm.inVista = false
        vm.inVista = true
        #expect(vm.messaggio == nil && vm.avvisoAltrove == nil)
    }

    @Test("Anche «Torna alla consigliata» riuscito toglie la traccia del salvataggio non riuscito")
    func guastoTolto() async throws {
        let cancello = Cancello()
        let esito = Scatola<ErroreApi>()
        esito.valore = .rete("spento")
        let srv = try Self.server(cancello: cancello, esito: esito, salvata: try SalvataggioAutomaticoTests.altroModulo())
        let (vm, _) = try await Self.caricata(srv)
        try #require(vm.salvata != nil, "c'è una scelta salvata: «Torna alla consigliata» la toglie")
        let togli = Task { await vm.tornaAllaConsigliata() }
        await cancello.richiestaArrivata()
        vm.inVista = false
        await cancello.apri()
        await togli.value
        vm.inVista = true
        #expect(vm.messaggio == ErroreApi.testoNonRaggiungibile)
        esito.valore = nil
        await vm.tornaAllaConsigliata()
        #expect(vm.salvata == nil)
        #expect(vm.messaggio == nil)
        vm.inVista = false
        vm.inVista = true
        #expect(vm.messaggio == nil)
    }

    @Test("Con la giornata dopo la traccia del salvataggio non riuscito se ne va: era della giornata di prima")
    func guastoDellaGiornataPrima() async throws {
        let cancello = Cancello()
        let esito = Scatola<ErroreApi>()
        esito.valore = .rete("spento")
        let prossima = Scatola<Bool>()
        let (vm, f) = try await Self.caricata(try Self.server(cancello: cancello, esito: esito, prossima: prossima))
        let (esce, entra) = try SalvataggioAutomaticoTests.cambio(f, vm)
        let primo = Task { await vm.sostituisciTitolare(esce, con: entra) }
        await cancello.richiestaArrivata()
        vm.inVista = false
        await cancello.apri()
        _ = await primo.value
        vm.inVista = true
        #expect(vm.messaggio == ErroreApi.testoNonRaggiungibile)
        vm.messaggio = nil
        prossima.valore = true                  // scadenza passata: il server prepara la giornata dopo
        await vm.carica()
        #expect(vm.formazione?.giornata == f.giornata + 1)
        vm.inVista = false
        vm.inVista = true
        #expect(vm.messaggio == nil)
    }

    // MARK: 412 a scheda lasciata (#751)

    @Test("412 a scheda lasciata: l'avviso in basso con la frase della web e la tua formazione già riletta; tornando la frase di sempre del 412, a ogni ritorno finché non fai una nuova modifica")
    func cambiataAltroveFuori() async throws {
        let cancello = Cancello()
        let esito = Scatola<ErroreApi>()
        esito.valore = .conflitto
        let altroDispositivo = try SalvataggioAutomaticoTests.altroModulo()
        let srv = try Self.server(cancello: cancello, esito: esito, altroDispositivo: altroDispositivo)
        let (vm, f) = try await Self.caricata(srv)
        let (esce, entra) = try SalvataggioAutomaticoTests.cambio(f, vm)
        let salvataggio = Task { await vm.sostituisciTitolare(esce, con: entra) }
        await cancello.richiestaArrivata()
        vm.inVista = false                      // tocca Giornate mentre il salvataggio è in volo
        await cancello.apri()
        _ = await salvataggio.value
        #expect(vm.avvisoAltrove == Catalogo.Comune.cambiatoAltrove, "la frase della web, nell'avviso in basso")
        #expect(vm.messaggio == nil, "niente «Sto ricaricando…» né «Controlla e rifai la modifica» nella Formazione lasciata")
        // dopo il 412 il telefono ha già la versione nuova della scelta: una scrittura partita dalla scelta vecchia passerebbe
        #expect(srv.quante("GET /api/formazione") == 2, "la tua formazione si rilegge subito, non al ritorno")
        #expect(Set(vm.vista(f).titolari.map(\.id)) == Set(altroDispositivo), "in campo la scelta dell'altro dispositivo")
        #expect(!vm.comandiSpenti)
        vm.inVista = true                       // torna sulla Formazione
        #expect(vm.avvisoAltrove == nil)
        #expect(vm.messaggio == ErroreApi.conflitto.localizedDescription,
                "chi non ha visto l'avviso in basso sa perché in campo c'è un'altra formazione")
        vm.messaggio = nil                      // passati gli 8 secondi
        vm.inVista = false
        vm.inVista = true
        #expect(vm.messaggio == ErroreApi.conflitto.localizedDescription, "a ogni ritorno, finché non fai una nuova modifica")
        esito.valore = nil                      // il server ora accetta
        let (esce2, entra2) = try SalvataggioAutomaticoTests.cambio(f, vm)
        let fatto = await vm.sostituisciTitolare(esce2, con: entra2)
        #expect(fatto)
        #expect(vm.messaggio == nil, "una nuova modifica: la frase del 412 non vale più, nemmeno a schermo")
        vm.inVista = false
        vm.inVista = true
        #expect(vm.messaggio == nil && vm.avvisoAltrove == nil)
    }

    @Test("Con la giornata dopo la frase del 412 a scheda lasciata non torna più: era della giornata di prima")
    func cambiataAltroveGiornataDopo() async throws {
        let cancello = Cancello()
        let esito = Scatola<ErroreApi>()
        esito.valore = .conflitto
        let prossima = Scatola<Bool>()
        let srv = try Self.server(cancello: cancello, esito: esito, prossima: prossima,
                                  altroDispositivo: try SalvataggioAutomaticoTests.altroModulo())
        let (vm, f) = try await Self.caricata(srv)
        let (esce, entra) = try SalvataggioAutomaticoTests.cambio(f, vm)
        let salvataggio = Task { await vm.sostituisciTitolare(esce, con: entra) }
        await cancello.richiestaArrivata()
        vm.inVista = false
        await cancello.apri()
        _ = await salvataggio.value
        vm.inVista = true
        #expect(vm.messaggio == ErroreApi.conflitto.localizedDescription)
        vm.messaggio = nil
        prossima.valore = true                  // scadenza passata: il server prepara la giornata dopo
        await vm.carica()
        #expect(vm.formazione?.giornata == f.giornata + 1)
        vm.inVista = false
        vm.inVista = true
        #expect(vm.messaggio == nil)
    }

    @Test("412 a scheda lasciata mentre guardi la formazione di un'altra squadra: l'avviso in basso, la tua non si rilegge da qui; tornando la frase della web sotto il campo")
    func cambiataAltroveFuoriAltraSquadra() async throws {
        let cancello = Cancello()
        let esito = Scatola<ErroreApi>()
        esito.valore = .conflitto
        let srv = try Self.server(cancello: cancello, esito: esito, altroDispositivo: try SalvataggioAutomaticoTests.altroModulo())
        let (vm, f) = try await Self.caricata(srv)
        let (esce, entra) = try SalvataggioAutomaticoTests.cambio(f, vm)
        let salvataggio = Task { await vm.sostituisciTitolare(esce, con: entra) }
        await cancello.richiestaArrivata()
        vm.vediSquadra("Squadra di prova")      // Impostazioni › Le altre squadre: la Formazione si apre con la loro
        vm.inVista = false                      // poi tocca Giornate
        await cancello.apri()
        _ = await salvataggio.value
        #expect(vm.avvisoAltrove == Catalogo.Comune.cambiatoAltrove)
        #expect(vm.messaggio == nil)
        #expect(srv.quante("GET /api/scelta") == 1, "guardando un'altra squadra la tua non si rilegge: si rilegge con «Torna alla tua»")
        vm.inVista = true
        #expect(vm.messaggio == Catalogo.Comune.cambiatoAltrove, "tornando, sotto la loro formazione la frase della web")
    }

    @Test("Dopo un 412 a scheda lasciata, tornando c'è la frase del 412 e non l'avviso di un salvataggio non riuscito prima: l'ultimo è il 412")
    func cambiataAltroveTogliIlGuasto() async throws {
        let cancello = Cancello()
        let esito = Scatola<ErroreApi>()
        esito.valore = .rete("spento")
        let altroDispositivo = try SalvataggioAutomaticoTests.altroModulo()
        let (vm, f) = try await Self.caricata(try Self.server(cancello: cancello, esito: esito, altroDispositivo: altroDispositivo))
        let (esce, entra) = try SalvataggioAutomaticoTests.cambio(f, vm)
        let primo = Task { await vm.sostituisciTitolare(esce, con: entra) }
        await cancello.richiestaArrivata()
        vm.inVista = false
        await cancello.apri()
        _ = await primo.value
        vm.inVista = true
        try #require(vm.messaggio == ErroreApi.testoNonRaggiungibile, "il guasto di prima, tornando sulla Formazione")
        vm.messaggio = nil                      // passati gli 8 secondi
        esito.valore = .conflitto               // intanto un altro dispositivo ha salvato la sua scelta
        vm.inVista = false                      // la risposta del secondo salvataggio arriva a scheda lasciata
        await vm.sostituisciTitolare(esce, con: entra)
        #expect(vm.avvisoAltrove == Catalogo.Comune.cambiatoAltrove)
        vm.inVista = true
        #expect(vm.messaggio == ErroreApi.conflitto.localizedDescription, "l'ultima scrittura è quella del 412, non il guasto di prima")
        #expect(Set(vm.vista(f).titolari.map(\.id)) == Set(altroDispositivo))
    }

    @Test("412 guardando la formazione di un'altra squadra: la frase della web sotto il campo, come la web")
    func cambiataAltroveAltraSquadra() async throws {
        let cancello = Cancello()
        let esito = Scatola<ErroreApi>()
        esito.valore = .conflitto
        let altroDispositivo = try SalvataggioAutomaticoTests.altroModulo()
        let (vm, f) = try await Self.caricata(try Self.server(cancello: cancello, esito: esito, altroDispositivo: altroDispositivo))
        let (esce, entra) = try SalvataggioAutomaticoTests.cambio(f, vm)
        let salvataggio = Task { await vm.sostituisciTitolare(esce, con: entra) }
        await cancello.richiestaArrivata()
        vm.vediSquadra("Squadra di prova")      // da Impostazioni › Le altre squadre: la Formazione si apre con la loro
        await cancello.apri()
        _ = await salvataggio.value
        #expect(vm.messaggio == Catalogo.Comune.cambiatoAltrove, "non «Sto ricaricando…»: la loro formazione non è cambiata")
        #expect(vm.avvisoAltrove == nil)
    }

    // MARK: aiuti

    /// La formazione della fixture e la scelta `salvata` (nil = nessuna). Ogni scrittura (salvataggio o «Torna alla consigliata»)
    /// passa dal `cancello`, così il test cambia scheda mentre è in volo; poi, se `esito` ha un errore, non riesce con quello,
    /// altrimenti riesce come il server vero. Con `prossima` vera la formazione è della giornata dopo (10 invece di 9). Con un 412
    /// la scelta diventa `altroDispositivo`, se c'è: l'ha salvata un altro dispositivo.
    static func server(cancello: Cancello, esito: Scatola<ErroreApi>, salvata titolari: [Int]? = nil,
                       prossima: Scatola<Bool> = Scatola(), altroDispositivo: [Int]? = nil) throws -> ServerDiProva {
        let questa = try Fixture.dati("formazione")
        let testo = String(decoding: questa, as: UTF8.self)
        try #require(testo.contains("\"giornata\":9"), "la fixture è della giornata 9")
        let dopo = Data(testo.replacingOccurrences(of: "\"giornata\":9", with: "\"giornata\":10").utf8)
        let salvata = Scatola<String>()
        salvata.valore = titolari.map { SalvataggioAutomaticoTests.json($0) }
        return ServerDiProva { metodo, percorso, corpo in
            let scrive = metodo == "DELETE" || SalvataggioAutomaticoTests.salva(corpo)
            if scrive {
                await cancello.passa()
                if let errore = esito.valore {
                    if errore.eConflitto, let altroDispositivo { salvata.valore = SalvataggioAutomaticoTests.json(altroDispositivo) }
                    throw errore
                }
            }
            if percorso.hasPrefix("/api/formazione/valuta") {
                if scrive, let corpo, let o = try? JSONSerialization.jsonObject(with: corpo) as? [String: Any],
                   let ids = o["titolari"] as? [Int] {
                    salvata.valore = SalvataggioAutomaticoTests.json(ids)
                }
                return Data(#"{"modulo": "4-3-3", "punteggio_atteso": 20.0, "panchina": []}"#.utf8)
            }
            if percorso.hasPrefix("/api/scelta") {
                if metodo == "DELETE" {
                    salvata.valore = nil
                    return Data("{\"ok\": true}".utf8)
                }
                return Data((salvata.valore ?? "null").utf8)
            }
            return prossima.valore == true ? dopo : questa
        }
    }

    static func caricata(_ s: ServerDiProva) async throws -> (FormazioneViewModel, Formazione) {
        let vm = FormazioneViewModel(server: s)
        await vm.carica()
        return (vm, try #require(vm.formazione))
    }
}
