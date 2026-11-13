import Foundation
import Testing
@testable import Schieraxi

/// La Formazione mostra la formazione che conta anche con la sola copia del telefono, come la web (revisione della #694):
/// - a giornata in corso titolari e panchina sono quelli di `/api/oggi` (`in_corso.giocatori`, `live` di `mostraFormazione`), con lo
///   stato vero della partita, e sopra il campo niente modulo né punti attesi;
/// - prima della scadenza la scelta letta resta sul telefono accanto alla copia della Formazione (`CopiaScelta`, come la copia
///   «giornata» della web, che ha dentro la scelta): riaprendo senza rete, e mentre arrivano i dati nuovi, in campo c'è la formazione
///   salvata e mai la consigliata al suo posto; i comandi che scrivono restano spenti finché il server non risponde;
/// - un errore di `/api/oggi` si vede (striscia dei dati salvati, o l'errore con «Riprova») e con la giornata vecchia le decisioni
///   che scrivono si spengono.
/// Ogni prova ha un indirizzo suo: le copie sul telefono sono per indirizzo. Dati inventati (fixture).
@MainActor
@Suite("Formazione: la formazione che conta anche con la copia del telefono")
struct FormazioneCopiaEInCorsoTests {
    // MARK: giornata in corso

    @Test("A giornata in corso, anche con la sola copia del telefono, in campo la formazione di Oggi con lo stato vero della partita")
    func inCorsoConLaCopia() async throws {
        let dove = Self.indirizzo()
        let schierati = try SalvataggioAutomaticoTests.altroModulo()        // la tua scelta: non sono gli 11 della consigliata
        let panchina = [7481, 7463, 5578, 7183]
        let giu = Scatola<Bool>()
        let srv = try Self.server(dove, oggi: Self.oggiInCorso(titolari: schierati, panchina: panchina), giu: giu)
        // con la rete: le copie restano sul telefono
        let giornataPrima = OggiViewModel(server: srv, conPromemoria: false)
        await FormazioneView.ricarica(FormazioneViewModel(server: srv, oggi: giornataPrima), oggi: giornataPrima)
        // allo stadio, senza rete, l'app appena aperta ha solo le copie
        giu.valore = true
        let oggi = OggiViewModel(server: srv, conPromemoria: false)
        let vm = FormazioneViewModel(server: srv, oggi: oggi)
        await FormazioneView.ricarica(vm, oggi: oggi)
        let f = try #require(vm.formazione, "la copia della Formazione")
        #expect(vm.copiaFerma && oggi.copia, "si vedono le copie")
        let v = vm.vista(f)
        #expect(v.titolari.map(\.id) == schierati, "gli 11 schierati, nell'ordine di Oggi, non quelli della consigliata")
        #expect(v.panchina.map(\.id) == panchina, "la panchina schierata, nel suo ordine")
        #expect(v.titolari.first?.fantavotoPreso == 7.5, "con il fantavoto preso, quello dei punti della testa")
        #expect(v.titolari.first.flatMap { LetturaPedina.contenuto($0).valore } == 7.5)
        #expect(v.titolari.dropFirst().allSatisfy { LetturaPedina.contenuto($0).attesa }, "chi deve ancora giocare ha il disco vuoto")
        #expect(vm.chiusa, "a giornata in corso non si cambia più niente")
        #expect(!vm.conModulo(f), "niente modulo né punti attesi sopra il campo, come la web")
    }

    @Test("Con la giornata in corso di un'altra giornata (copia vecchia) il campo non la usa")
    func inCorsoDiUnAltraGiornata() async throws {
        let schierati = try SalvataggioAutomaticoTests.altroModulo()
        let altra = String(decoding: Self.oggiInCorso(titolari: schierati, panchina: []), as: UTF8.self)
            .replacingOccurrences(of: "\"giornata\": 9", with: "\"giornata\": 8")
        let srv = try Self.server(Self.indirizzo(), oggi: Data(altra.utf8))
        let oggi = OggiViewModel(server: srv, conPromemoria: false)
        let vm = FormazioneViewModel(server: srv, oggi: oggi)
        await FormazioneView.ricarica(vm, oggi: oggi)
        let f = try #require(vm.formazione)
        #expect(Set(vm.vista(f).titolari.map(\.id)) == Set(vm.consigliati(f)))
        #expect(vm.conModulo(f))
    }

    // MARK: prima della scadenza, con la copia della scelta

    @Test("Prima della scadenza, riaprendo senza rete, in campo la formazione salvata e non la consigliata; non si può cambiare")
    func sceltaConLaCopia() async throws {
        let dove = Self.indirizzo()
        let salvati = try SalvataggioAutomaticoTests.altroModulo()
        let giu = Scatola<Bool>()
        let srv = try Self.server(dove, scelta: SalvataggioAutomaticoTests.json(salvati), giu: giu)
        let lettaPrima = await FormazioneViewModel(server: srv).carica()
        #expect(lettaPrima)
        giu.valore = true
        let vm = FormazioneViewModel(server: srv)
        let letta = await vm.carica()
        #expect(!letta, "il server non ha risposto")
        let f = try #require(vm.formazione, "la copia della Formazione")
        #expect(Set(vm.vista(f).titolari.map(\.id)) == Set(salvati), "la formazione salvata, dalla copia del telefono")
        #expect(vm.statoScelta == .cambiata(diversi: 2, punti: 70.7 - 71.1), "con la sua riga, come la web")
        #expect(vm.conModulo(f))
        #expect(vm.copiaFerma && vm.comandiSpenti)
        let (esce, entra) = try SalvataggioAutomaticoTests.cambio(f, vm)
        let fatto = await vm.sostituisciTitolare(esce, con: entra)
        #expect(!fatto)
        #expect(srv.quante("POST") == 0, "dalla copia non si scrive niente")
    }

    @Test("All'apertura, mentre arrivano i dati nuovi, in campo c'è già la formazione salvata: niente salto dalla consigliata")
    func senzaSaltoAllApertura() async throws {
        let dove = Self.indirizzo()
        let salvati = try SalvataggioAutomaticoTests.altroModulo()
        let scelta = SalvataggioAutomaticoTests.json(salvati)
        let lettaPrima = await FormazioneViewModel(server: try Self.server(dove, scelta: scelta)).carica()
        #expect(lettaPrima)
        let cancello = Cancello()
        let vm = FormazioneViewModel(server: try Self.server(dove, scelta: scelta, cancello: cancello))
        let apertura = Task { await vm.carica() }
        await cancello.richiestaArrivata()
        let f = try #require(vm.formazione, "la copia della Formazione, subito")
        #expect(Set(vm.vista(f).titolari.map(\.id)) == Set(salvati), "già la formazione salvata")
        #expect(vm.statoScelta == .cambiata(diversi: 2, punti: 70.7 - 71.1))
        #expect(vm.comandiSpenti, "finché il server non risponde non si scrive")
        await cancello.apri()
        _ = await apertura.value
        let nuova = try #require(vm.formazione)
        #expect(Set(vm.vista(nuova).titolari.map(\.id)) == Set(salvati))
        #expect(vm.sceltaLetta && !vm.comandiSpenti)
    }

    @Test("Una scelta tolta («Torna alla consigliata») resta tolta anche nella copia del telefono")
    func sceltaTolta() async throws {
        let dove = Self.indirizzo()
        let salvata = Scatola<String>()
        salvata.valore = SalvataggioAutomaticoTests.json(try SalvataggioAutomaticoTests.altroModulo())
        let giu = Scatola<Bool>()
        let srv = try Self.server(dove, salvata: salvata, giu: giu)
        let prima = FormazioneViewModel(server: srv)
        await prima.carica()
        await prima.tornaAllaConsigliata()
        #expect(prima.salvata == nil)
        giu.valore = true
        let vm = FormazioneViewModel(server: srv)
        await vm.carica()
        let f = try #require(vm.formazione)
        #expect(Set(vm.vista(f).titolari.map(\.id)) == Set(vm.consigliati(f)))
        #expect(vm.statoScelta == .consigliata)
    }

    @Test("Con la copia della Formazione ma senza quella della scelta, se il server dice che ne hai una salvata la riga lo dice")
    func copiaSenzaScelta() async throws {
        let dove = Self.indirizzo()
        var json = try #require(try JSONSerialization.jsonObject(with: try Fixture.dati("formazione")) as? [String: Any])
        json["stato_scelta"] = "valida"
        let formazione = try JSONSerialization.data(withJSONObject: json)
        let giu = Scatola<Bool>()
        let srv = try Self.server(dove, scelta: SalvataggioAutomaticoTests.json(try SalvataggioAutomaticoTests.altroModulo()),
                                  formazione: formazione, giu: giu)
        let lettaPrima = await FormazioneViewModel(server: srv).carica()
        #expect(lettaPrima)
        Cache.rimuovi(CopiaScelta.percorso, indirizzo: dove)          // per esempio la prima apertura dopo l'aggiornamento dell'app
        giu.valore = true
        let vm = FormazioneViewModel(server: srv)
        await vm.carica()
        #expect(vm.formazione != nil && vm.copiaFerma)
        #expect(vm.statoScelta == .nonLetta, "mai la consigliata come se fosse la formazione salvata")
    }

    // MARK: errori di /api/oggi

    @Test("Se /api/oggi non si aggiorna lo si dice (striscia dei dati salvati) e le decisioni che scrivono si spengono")
    func giornataVecchia() async throws {
        let guasto = Scatola<Bool>()
        let formazione = try Fixture.dati("formazione")
        let giornata = try Fixture.dati("oggi")
        let srv = ServerDiProva(indirizzo: Self.indirizzo()) { _, percorso, _ in
            if percorso.hasPrefix("/api/oggi") {
                if guasto.valore == true { throw ErroreApi.server("Il server ha un guasto") }
                return giornata
            }
            if percorso.hasPrefix("/api/scelta") { return Data("null".utf8) }
            return formazione
        }
        let oggi = OggiViewModel(server: srv, conPromemoria: false)
        let vm = FormazioneViewModel(server: srv, oggi: oggi)
        await FormazioneView.ricarica(vm, oggi: oggi)
        #expect(!vm.decisioniSpente)
        #expect(vm.striscia == nil)
        guasto.valore = true
        await FormazioneView.ricarica(vm, oggi: oggi)
        let striscia = try #require(vm.striscia, "la striscia dei dati salvati, anche se è vecchia solo la giornata")
        #expect(striscia.data == oggi.datiSalvati)
        #expect(striscia.motivo != nil && striscia.motivo == oggi.caricatore.motivoDatiSalvati)
        #expect(vm.decisioniSpente, "con la giornata vecchia le decisioni che scrivono si spengono")
        #expect(!vm.comandiSpenti, "formazione e scelta sono fresche: il resto si cambia")
        #expect(vm.erroreGiornata == nil, "c'è la copia: basta la striscia")
    }

    @Test("Se /api/oggi non risponde e non c'è una copia, l'errore si vede")
    func giornataMaiArrivata() async throws {
        let srv = try Self.server(Self.indirizzo())          // senza giornata: un errore del server
        let oggi = OggiViewModel(server: srv, conPromemoria: false)
        let vm = FormazioneViewModel(server: srv, oggi: oggi)
        await FormazioneView.ricarica(vm, oggi: oggi)
        #expect(vm.formazione != nil)
        #expect(vm.erroreGiornata != nil && vm.erroreGiornata == oggi.errore)
    }

    // MARK: aiuti

    static func indirizzo() -> String { "https://prova-\(UUID().uuidString).invalid" }

    /// La giornata in corso con `titolari` e `panchina` schierati (id della fixture della Formazione): il primo titolare ha già il
    /// voto, gli altri devono ancora giocare.
    nonisolated static func oggiInCorso(titolari: [Int], panchina: [Int]) -> Data {
        func riga(_ id: Int, titolare: Bool, conVoto: Bool) -> String {
            let partita = conVoto ? #""stato": "fatto", "fantavoto": 7.5, "etichetta": {"codice": "voto", "testo": "Ha giocato", "tono": "positivo"}"#
                                  : #""stato": "da_giocare", "data": "2026-11-08 20:45""#
            return #"{"id": \#(id), "nome": "Giocatore \#(id)", "titolare": \#(titolare), "a_punteggio": \#(titolare), \#(partita)}"#
        }
        let righe = titolari.enumerated().map { riga($0.element, titolare: true, conVoto: $0.offset == 0) }
            + panchina.map { riga($0, titolare: false, conVoto: false) }
        let json = #"{"giornata": 9, "iniziata": true, "fase": "in_corso", "formazione": {"modulo": "5-3-2", "punteggio_atteso": 70.7}, "#
            + #""in_corso": {"giornata": 9, "formazione_di": "tua", "punti_fatti": 7.5, "punti_previsti": 72.0, "ancora_da_giocare": 10, "#
            + #""giocatori": [\#(righe.joined(separator: ", "))], "sostituzioni": []}}"#
        return Data(json.utf8)
    }

    /// Un server con la Formazione della fixture (o `formazione`), la scelta `scelta` (JSON, "null" = nessuna; oppure quella in
    /// `salvata`, che «Torna alla consigliata» toglie) e la giornata `oggi` (senza: un errore del server). Con `giu` vero non
    /// risponde niente; con `cancello` la lettura della Formazione aspetta il test.
    static func server(_ indirizzo: String, scelta: String = "null", salvata: Scatola<String>? = nil, oggi: Data? = nil,
                       formazione: Data? = nil, giu: Scatola<Bool> = Scatola(), cancello: Cancello? = nil) throws -> ServerDiProva {
        let dati = try formazione ?? Fixture.dati("formazione")
        return ServerDiProva(indirizzo: indirizzo) { metodo, percorso, _ in
            if giu.valore == true { throw ErroreApi.rete("spento") }
            if percorso.hasPrefix("/api/oggi") {
                guard let oggi else { throw ErroreApi.server("nessuna giornata") }
                return oggi
            }
            if percorso.hasPrefix("/api/scelta") {
                guard let salvata else { return Data(scelta.utf8) }
                if metodo == "DELETE" {
                    salvata.valore = nil
                    return Data("{\"ok\": true}".utf8)
                }
                return Data((salvata.valore ?? "null").utf8)
            }
            if percorso.hasPrefix("/api/formazione"), let cancello { await cancello.passa() }
            return dati
        }
    }
}
