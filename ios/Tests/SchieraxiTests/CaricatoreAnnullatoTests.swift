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

    // Revisione della #972: la prima lettura in viaggio con la copia del telefono a video, una seconda annullata; prima la
    // schermata tornava vuota e la data della copia si perdeva, e quando la prima non riusciva la striscia diceva «dati salvati
    // alle <adesso>» (`datiSalvati` ripiega sull'ora di adesso).
    @Test("Copia del telefono a video e lettura in viaggio, una seconda annullata, poi la prima non riesce: la striscia ha la data della copia")
    func laCopiaTieneLaSuaData() async throws {
        let indirizzo = "https://prova-copia-\(UUID().uuidString).invalid"
        Cache.salva(try Fixture.dati("oggi"), "/api/oggi", indirizzo: indirizzo)
        let letta = await Cache.leggi("/api/oggi", indirizzo: indirizzo)
        let copia = try #require(letta, "la copia è sul telefono")
        try await Task.sleep(nanoseconds: 50_000_000)          // l'ora di adesso non è più quella della copia
        let libera = Scatola<Bool>()
        defer { libera.valore = true }                          // anche se una prova si ferma prima, la prima lettura finisce
        let passo = Contatore()
        let server = ServerDiProva(indirizzo: indirizzo) { _, _, _ in
            if passo.passo() == 0 {
                // la prima lettura resta in viaggio finché la prova non la lascia andare, e poi la rete non c'è
                while libera.valore != true { try await Task.sleep(nanoseconds: 10_000_000) }
                throw ErroreApi.rete("spento")
            }
            return try await Self.inViaggio()                    // la seconda: annullata
        }
        let c = Caricatore<Oggi>("/api/oggi", ascolta: false, server: server, rete: RitornoRete())
        let prima = Task { await c.ricarica() }
        await aspetta(server, richieste: 1)
        try #require(server.richieste.count == 1 && c.dato?.giornata == 9, "la copia del telefono a video, la prima lettura in viaggio")
        let seconda = Task { await c.ricarica() }
        await aspetta(server, richieste: 2)
        try #require(server.richieste.count == 2, "la seconda lettura è in viaggio")
        seconda.cancel()
        await seconda.value
        #expect(c.dato?.giornata == 9, "annullata la seconda, la copia resta a video")
        libera.valore = true
        await prima.value
        #expect(c.dato?.giornata == 9)
        #expect(c.datiSalvati == copia.data, "la striscia dice di quando è la copia, non l'ora di adesso")
    }

    @Test("Si aspetta il ritorno della rete solo quando a video resta una copia perché la rete non c'era")
    func collegamentoConIlRitornoDellaRete() async throws {
        let reteGiu = await aspettaLaRete(dopo: ErroreApi.rete("spento"), conDati: true)
        #expect(reteGiu, "copia a video, rete assente: al ritorno della rete si riprova")
        let lento = await aspettaLaRete(dopo: ErroreApi.timeout, conDati: true)
        #expect(lento, "anche con il tempo scaduto")
        let guasto = await aspettaLaRete(dopo: ErroreApi.server("Guasto"), conDati: true)
        #expect(!guasto, "il server ha risposto con un errore: c'è «Riprova», la rete non c'entra")
        let senzaCopia = await aspettaLaRete(dopo: ErroreApi.rete("spento"), conDati: false)
        #expect(!senzaCopia, "senza copia a video c'è l'errore con «Riprova», come la web")
    }

    /// Una lettura riuscita (se `conDati`) e poi una che finisce con `errore`: il ritorno della rete aspetta?
    private func aspettaLaRete(dopo errore: ErroreApi, conDati: Bool) async -> Bool {
        let rete = RitornoRete()
        let passo = Contatore()
        let server = ServerDiProva { _, _, _ in
            if conDati, passo.passo() == 0 { return try Fixture.dati("oggi") }
            throw errore
        }
        let c = Caricatore<Oggi>("/api/oggi", cache: false, ascolta: false, server: server, rete: rete)
        if conDati { await c.ricarica() }
        await c.ricarica()
        return rete.inAttesa
    }
}
