import Foundation
import Testing
@testable import Schieraxi

/// La giornata (`/api/oggi`) porta i giorni che mancano alla scadenza del certificato dell'app (`certificato_giorni`): il server
/// li usa per la voce «Rinnova l'app» del «Da fare» (da 3 giorni in giù). Prima l'indirizzo si calcolava una volta sola, quando
/// nasceva la sessione: con l'app in memoria per giorni il server riceveva un numero vecchio e la voce non compariva, o diceva un
/// numero sbagliato. Ora si calcola a ogni lettura. Dati inventati (fixture).
@MainActor
@Suite("Giornata: i giorni del certificato sono quelli del momento della lettura")
struct GiornataCertificatoTests {
    @Test("Con l'app in memoria per giorni ogni lettura manda il numero di quel momento")
    func percorsoACiascunaLettura() async throws {
        let giorni = Scatola<Int>()
        giorni.valore = 5
        let srv = ServerDiProva { _, _, _ in try Fixture.dati("oggi") }
        let vm = OggiViewModel(server: srv, conPromemoria: false,
                               percorso: { OggiRepository.percorso(giorniCertificato: giorni.valore) })
        await vm.carica()
        #expect(srv.richieste.last == "GET /api/oggi?certificato_giorni=5")
        giorni.valore = 2
        await vm.carica()
        #expect(srv.richieste.last == "GET /api/oggi?certificato_giorni=2", "il giorno dopo il numero nuovo, per «Rinnova l'app»")
        giorni.valore = 1
        await vm.rileggi()          // la rilettura ogni 5 minuti a giornata in corso (`FormazioneView.seguiGiornata`)
        #expect(srv.richieste.last == "GET /api/oggi?certificato_giorni=1")
    }

    @Test("Cambiato il numero, mentre arriva la giornata nuova si vede quella già letta, non la copia del telefono")
    func datiAVideoRestano() async throws {
        let giorni = Scatola<Int>()
        giorni.valore = 5
        let libera = Scatola<Bool>()
        defer { libera.valore = true }          // anche se una prova si ferma prima, la lettura in viaggio finisce
        let passo = Contatore()
        let srv = ServerDiProva { _, _, _ in
            if passo.passo() > 0 {
                while libera.valore != true { try await Task.sleep(nanoseconds: 10_000_000) }
            }
            return try Fixture.dati("oggi")
        }
        let vm = OggiViewModel(server: srv, conPromemoria: false,
                               percorso: { OggiRepository.percorso(giorniCertificato: giorni.valore) })
        await vm.carica()
        try #require(vm.oggi?.giornata == 9 && !vm.copia)
        giorni.valore = 4
        let lettura = Task { await vm.carica() }
        for _ in 0..<250 where srv.richieste.count < 2 {
            try await Task.sleep(nanoseconds: 20_000_000)
        }
        try #require(srv.richieste.count == 2, "la seconda lettura è in viaggio")
        #expect(vm.oggi?.giornata == 9, "si vede la giornata già letta")
        #expect(!vm.copia, "e non come copia del telefono: le decisioni restano accese")
        libera.valore = true
        await lettura.value
        #expect(vm.oggi?.giornata == 9)
        #expect(!vm.copia)
    }
}
