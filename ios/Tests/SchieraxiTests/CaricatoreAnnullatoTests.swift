import Foundation
import Testing
@testable import Schieraxi

/// Una lettura annullata dalla schermata (per esempio il telefono bloccato durante un aggiornamento: `FormazioneView` annulla il
/// lavoro quando la scena non è più attiva) non è una risposta del server: lo stato torna com'era prima, anche un errore o la
/// copia salvata con la sua data e la sua striscia. Prima tornavano i dati di prima come se fossero appena arrivati, e la striscia
/// «dati salvati» spariva; un errore senza dati diventava lo scheletro di un caricamento che non arrivava più. Dati inventati.
@MainActor
@Suite("Caricatore: una lettura annullata rimette lo stato di prima")
struct CaricatoreAnnullatoTests {
    /// Una risposta che resta in viaggio finché la lettura non viene annullata.
    nonisolated private static func inViaggio() async throws -> Data {
        try await Task.sleep(nanoseconds: 60_000_000_000)
        return try Fixture.dati("oggi")
    }

    /// Aspetta che il server abbia ricevuto almeno `n` richieste (al più 5 secondi).
    private func aspetta(_ server: ServerDiProva, richieste n: Int) async {
        for _ in 0..<250 where server.richieste.count < n {
            try? await Task.sleep(nanoseconds: 20_000_000)
        }
    }

    @Test("Copia salvata dopo un errore di rete, poi una lettura annullata: restano la copia, la sua data e la striscia")
    func restaLaCopiaConLaSuaData() async throws {
        let passo = Contatore()
        let server = ServerDiProva { _, _, _ in
            switch passo.passo() {
            case 0: return try Fixture.dati("oggi")
            case 1: throw ErroreApi.rete("spento")
            default: return try await Self.inViaggio()
            }
        }
        let c = Caricatore<Oggi>("/api/oggi", cache: false, ascolta: false, server: server)
        await c.ricarica()
        await c.ricarica()
        let data = try #require(c.datiSalvati, "la copia di prima, con la sua data")
        let errore = c.errore
        let lettura = Task { await c.ricarica() }
        await aspetta(server, richieste: 3)
        try #require(server.richieste.count == 3, "la terza lettura è in viaggio")
        lettura.cancel()
        await lettura.value
        #expect(c.datiSalvati == data, "la striscia «dati salvati» resta, con la data della copia")
        #expect(c.errore == errore)
        #expect(c.motivoDatiSalvati == nil, "rete assente: la frase di sempre")
        #expect(c.dato?.giornata == 9)
        #expect(!c.inCorso)
        #expect(c.risposte == 1, "una lettura annullata non è una risposta nuova")
    }

    @Test("Errore senza dati, poi una lettura annullata: resta l'errore con «Riprova», non lo scheletro del caricamento")
    func restaLErrore() async throws {
        let passo = Contatore()
        let server = ServerDiProva { _, _, _ in
            if passo.passo() == 0 { throw ErroreApi.server("Guasto") }
            return try await Self.inViaggio()
        }
        let c = Caricatore<Oggi>("/api/oggi", cache: false, ascolta: false, server: server)
        await c.ricarica()
        try #require(c.errore == "Guasto")
        let lettura = Task { await c.ricarica() }
        await aspetta(server, richieste: 2)
        try #require(server.richieste.count == 2, "la seconda lettura è in viaggio")
        lettura.cancel()
        await lettura.value
        #expect(c.errore == "Guasto")
        #expect(c.dato == nil)
        #expect(!c.inCorso)
    }

    @Test("Una lettura annullata non rimette i dati di prima sopra quelli arrivati nel frattempo")
    func nonCopreIDatiNuovi() async throws {
        let vecchia = try Fixture.dati("oggi")
        let testo = String(decoding: vecchia, as: UTF8.self)
        let nuova = Data(testo.replacingOccurrences(of: "{\"giornata\":9,", with: "{\"giornata\":10,").utf8)
        try #require(nuova != vecchia, "la giornata dopo")
        let passo = Contatore()
        let server = ServerDiProva { _, _, _ in
            switch passo.passo() {
            case 0: return vecchia
            case 1: return try await Self.inViaggio()      // per esempio la rilettura ogni 5 minuti, poi annullata
            default: return nuova                          // nel frattempo l'utente tira giù la pagina
            }
        }
        let c = Caricatore<Oggi>("/api/oggi", cache: false, ascolta: false, server: server)
        await c.ricarica()
        let lenta = Task { await c.ricarica() }
        await aspetta(server, richieste: 2)
        try #require(server.richieste.count == 2, "la lettura lenta è in viaggio")
        await c.ricarica()
        try #require(c.dato?.giornata == 10)
        lenta.cancel()
        await lenta.value
        #expect(c.dato?.giornata == 10, "restano i dati appena arrivati")
        #expect(c.datiSalvati == nil)
        #expect(!c.inCorso)
    }

    @Test("Una lettura della giornata annullata non passa a widget e promemoria i dati di prima come appena letti")
    func giornataAnnullataNonEFresca() async throws {
        let passo = Contatore()
        let srv = ServerDiProva { _, _, _ in
            if passo.passo() == 0 { return try Fixture.dati("oggi") }
            return try await Self.inViaggio()
        }
        let vm = OggiViewModel(server: srv, conPromemoria: false)
        let fresche = Contatore()
        vm.dopoLetturaFresca = { _, _, _ in _ = fresche.passo() }
        await vm.carica()
        try #require(fresche.valore == 1, "la prima lettura è fresca")
        let lettura = Task { await vm.carica() }
        await aspetta(srv, richieste: 2)
        try #require(srv.richieste.count == 2, "la seconda lettura è in viaggio")
        lettura.cancel()
        await lettura.value
        #expect(fresche.valore == 1, "i dati di prima non sono una lettura fresca: niente promemoria né widget con l'ora di adesso")
        #expect(vm.oggi?.giornata == 9, "e restano a video")
    }
}
