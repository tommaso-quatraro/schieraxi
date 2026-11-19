import Foundation
import Testing
@testable import Schieraxi

/// La frase del server a campionato finito (`campionato.finito`, `fanta/testi/frase.json`): la stessa delle fixture.
private let fraseCampionatoFinito = "Il campionato è finito: previsioni e consigli ripartono con il calendario della prossima stagione."

/// A campionato finito (#727, seguito di #656) il server risponde a `GET /api/oggi` con `campionato_finito` = {testo, frase} e, nelle
/// 48 ore dopo l'ultima giornata, con il suo `riepilogo`; `GET /api/formazione` risponde 409 con codice `campionato_finito`. Come
/// `mostraCampionatoFinito` della web: la Formazione mostra il riepilogo, se c'è, e poi la frase del server, senza errore né
/// «Riprova». Prima l'iPhone mostrava il messaggio del 409 o la formazione di prima con la striscia dei dati salvati. Risposte
/// inventate nelle fixture `oggi-campionato-finito` (dopo le 48 ore) e `oggi-campionato-finito-riepilogo` (nelle 48 ore).
@Suite("Campionato finito: il riepilogo e la frase del server, niente errore")
struct CampionatoFinitoTests {
    /// martedì 25 maggio 2027, il giorno dopo l'ultima giornata.
    static func adesso() throws -> Date { try #require(Quando.data("2027-05-25 10:00")) }

    static func oggi(_ fixture: String) throws -> Oggi { try Fixture.decodifica(fixture) }

    // MARK: lettura

    @Test("Oggi a campionato finito si legge con la frase del server; senza il campo, o con un campo strano, niente frase")
    func lettura() throws {
        #expect(try Self.oggi("oggi-campionato-finito").testoCampionatoFinito == fraseCampionatoFinito)
        #expect(try Self.oggi("oggi-campionato-finito-riepilogo").testoCampionatoFinito == fraseCampionatoFinito)
        #expect(try Self.oggi("oggi").testoCampionatoFinito == nil, "una giornata come tutte")
        for strano in [#"{"campionato_finito": "sì"}"#, #"{"campionato_finito": {"testo": "  "}}"#, #"{"campionato_finito": null}"#,
                       #"{"campionato_finito": {"testo": 3}, "giornata": 9}"#] {
            let o: Oggi = try Decodifica.decodifica(Data(strano.utf8))
            #expect(o.testoCampionatoFinito == nil, "\(strano)")
        }
    }

    // MARK: testa della Formazione

    @Test("Nelle 48 ore: la giornata finita con i suoi punti e «Com'è andata», poi la frase del server al posto della prossima")
    func testaConRiepilogo() throws {
        let t = TestaFormazione.per(oggi: try Self.oggi("oggi-campionato-finito-riepilogo"), formazione: nil, adesso: try Self.adesso())
        #expect(t.giornata == "Giornata 35 · 38ª di Serie A: finita")
        #expect(t.punti == "74,5")
        #expect(t.testoPunti == Catalogo.Formazione.puntiEAttesi(n: "71,7"))
        #expect(t.comeAndata == 38)
        #expect(t.sotto == Catalogo.Oggi.conConsigliata(attesi: "72,4", fatti: "70,0"))
        #expect(t.campionatoFinito == fraseCampionatoFinito)
        #expect(t.prossima == nil && t.chiude == nil && t.manca == nil,
                "nessuna giornata da preparare: niente «Calendario non disponibile» né scadenza")
    }

    @Test("Dopo le 48 ore: solo la frase del server")
    func testaSoloFrase() throws {
        let t = TestaFormazione.per(oggi: try Self.oggi("oggi-campionato-finito"), formazione: nil, adesso: try Self.adesso())
        #expect(t == TestaFormazione(campionatoFinito: fraseCampionatoFinito))
    }

    @Test("Con la formazione di prima ancora sul telefono la testa non parla della sua giornata")
    func testaConLaFormazioneDiPrima() throws {
        let vecchia = try TestaFormazioneTests.formazione(giornata: 38, lega: 35)
        let t = TestaFormazione.per(oggi: try Self.oggi("oggi-campionato-finito"), formazione: vecchia, adesso: try Self.adesso())
        #expect(t == TestaFormazione(campionatoFinito: fraseCampionatoFinito))
    }

    // MARK: Formazione

    /// Oggi e Formazione come il server, in una giornata come tutte o, con `finito` vero, a campionato finito (409 sulla Formazione).
    /// Lo stesso server per tutti e due i momenti: la stessa copia sul telefono.
    private static func server(_ finito: Scatola<Bool>) -> ServerDiProva {
        ServerDiProva { _, percorso, _ in
            let fine = finito.valore == true
            if percorso.hasPrefix("/api/oggi") { return try Fixture.dati(fine ? "oggi-campionato-finito-riepilogo" : "oggi") }
            if percorso.hasPrefix("/api/scelta") { return Data("null".utf8) }
            if fine { throw ErroreApi.codificato(codice: "campionato_finito", messaggio: fraseCampionatoFinito) }
            return try Fixture.dati("formazione")
        }
    }

    @MainActor
    @Test("A campionato finito la Formazione lo sa: niente errore del 409 e niente striscia, anche con la formazione di prima in memoria")
    func formazione() async throws {
        let finito = Scatola<Bool>()
        let srv = Self.server(finito)
        let oggi = OggiViewModel(server: srv, conPromemoria: false)
        let vm = FormazioneViewModel(server: srv, oggi: oggi, promemoria: {})
        await FormazioneView.ricarica(vm, oggi: oggi)
        #expect(!vm.campionatoFinito, "una giornata come tutte")
        #expect(vm.formazione != nil)

        finito.valore = true
        await FormazioneView.ricarica(vm, oggi: oggi)
        #expect(vm.campionatoFinito)
        #expect(vm.striscia?.data == nil, "la formazione di prima non si mostra: la sua copia non fa comparire «dati salvati»")
        #expect(vm.erroreGiornata == nil)
    }

    @MainActor
    @Test("La formazione di un'altra squadra non diventa il campionato finito della tua")
    func altraSquadra() async throws {
        let finito = Scatola<Bool>()
        finito.valore = true
        let srv = Self.server(finito)
        let oggi = OggiViewModel(server: srv, conPromemoria: false)
        let vm = FormazioneViewModel(server: srv, oggi: oggi, promemoria: {})
        await FormazioneView.ricarica(vm, oggi: oggi)
        #expect(vm.campionatoFinito)
        vm.vediSquadra("Gli Amici")
        #expect(!vm.campionatoFinito)
    }

    // MARK: demo delle fotografie

    @Test("La demo delle foto a campionato finito risponde come il server, con la stessa frase nell'app e nei widget")
    func demo() async throws {
        let server = try #require(FinteServer.demoFase("formazione-campionato-finito"), "la demo «formazione-campionato-finito» non esiste")
        let o: Oggi = try Decodifica.decodifica(try await server.richiesta("GET", "/api/oggi", corpo: nil))
        #expect(o.testoCampionatoFinito == fraseCampionatoFinito)
        #expect(o.giornata == nil && o.prossimaGiornata == nil)
        #expect(o.riepilogoGiornata?.giornata == 38, "nelle 48 ore il riepilogo dell'ultima giornata, la 38ª di Serie A")
        do {
            _ = try await server.richiesta("GET", "/api/formazione", corpo: nil)
            Issue.record("a campionato finito la Formazione della demo risponde come il server: 409 con codice campionato_finito")
        } catch ErroreApi.codificato(let codice, let messaggio) {
            #expect(codice == "campionato_finito")
            #expect(messaggio == fraseCampionatoFinito)
        }
        let w = try #require(RiassuntoWidget.leggi(LegaDemo.widgetCampionatoFinito(adesso: try Self.adesso())),
                             "il widget della demo a campionato finito non si legge")
        #expect(w.campionatoFinito == fraseCampionatoFinito)
        #expect(w.giornata == nil)
    }
}
