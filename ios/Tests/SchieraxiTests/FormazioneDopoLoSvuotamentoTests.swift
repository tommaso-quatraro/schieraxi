import Foundation
import Testing
@testable import Schieraxi

// Issue #846. Nella foto `ipad_scuro_orizzontale_formazione-in-corso` (corsa 44738994894) la Formazione mostrava solo lo scheletro
// del caricamento. La scena segue `giocatore`, che nella demo ha un altro indirizzo finto: 0,7 secondi dopo l'avvio la porta
// (`SessioneAccount.cambiaServer`) vede l'indirizzo cambiato e svuota i dati locali (`DatiLocali.svuota`: copie su disco, immagini,
// versioni) mentre la Formazione sta ancora leggendo formazione, scelta e giornata. Gli stessi passi qui, con il server della foto
// (`FinteServer.demoFase("formazione-in-corso")`, dati inventati) sotto un indirizzo suo: lo svuotamento cade durante ciascuna delle
// tre letture, e alla fine la Formazione deve esserci, senza errore e senza restare «in lettura». Vale anche per chi cambia server
// o esce e rientra: lo svuotamento è lo stesso.

@MainActor
@Suite("La Formazione arriva anche se i dati locali si svuotano mentre carica (#846)")
struct FormazioneDopoLoSvuotamentoTests {
    /// Il server della foto `formazione-in-corso` con un indirizzo suo (niente copie su disco di altri test). Con `trattieni` la
    /// prima richiesta GET che comincia così risponde solo quando `rilascio` finisce.
    private static func server(trattieni: String? = nil, rilascio: AsyncStream<Void>? = nil) throws -> ServerDiProva {
        let demo = try #require(FinteServer.demoFase("formazione-in-corso"), "la demo della giornata in corso c'è")
        let trattenuta = Scatola<Bool>()
        return ServerDiProva(indirizzo: "https://prova-846-\(UUID().uuidString).invalid") { metodo, percorso, corpo in
            if let trattieni, let rilascio, metodo == "GET", percorso.hasPrefix(trattieni), trattenuta.valore != true {
                trattenuta.valore = true
                for await _ in rilascio {}
            }
            return try await demo.richiesta(metodo, percorso, corpo: corpo)
        }
    }

    /// La sessione dell'app su `server`, nata con un altro indirizzo ricordato (l'avvio di prima era su un'altra scena della demo):
    /// `cambiaServer` svuota i dati locali con la pulizia vera. Widget e portachiavi finti: mai quelli veri del simulatore.
    private static func sessione(_ server: ServerDiProva, memoria: UserDefaults) -> SessioneAccount {
        memoria.set("https://prova-846-prima.invalid", forKey: "account.indirizzo")
        let luoghi = TokenWidget.Luoghi(archivio: MemoriaToken(), memoria: memoria, cartella: { nil }, portachiavi: MemoriaCollegamento(),
                                        sincronizza: {})
        return SessioneAccount(server: server, archivio: MemoriaToken(), memoria: memoria, pulisci: { DatiLocali.svuota() }, widget: luoghi)
    }

    @Test("Svuotati i dati mentre una lettura della Formazione è in viaggio: la Formazione arriva lo stesso",
          .timeLimit(.minutes(1)),
          arguments: ["/api/formazione", "/api/scelta", "/api/oggi"])
    func svuotamentoDuranteLaLettura(trattieni percorso: String) async throws {
        let nome = "formazione-846-\(UUID().uuidString)"
        let memoria = try #require(UserDefaults(suiteName: nome))
        defer { memoria.removePersistentDomain(forName: nome) }
        let (rilascio, apri) = AsyncStream<Void>.makeStream()
        let s = try Self.server(trattieni: percorso, rilascio: rilascio)
        let sessione = Self.sessione(s, memoria: memoria)
        let oggi = OggiViewModel(server: s, conPromemoria: false)
        let vm = FormazioneViewModel(server: s, oggi: oggi, memoria: memoria, promemoria: {})

        // la Formazione compare e legge giornata, formazione e scelta (la `task` della schermata)
        let apertura = Task { await FormazioneView.ricarica(vm, oggi: oggi) }
        for _ in 0..<500 where s.quante("GET \(percorso)") == 0 { try await Task.sleep(for: .milliseconds(10)) }
        try #require(s.quante("GET \(percorso)") == 1, "la lettura di \(percorso) è in viaggio")

        // intanto la porta vede l'indirizzo cambiato e svuota i dati locali
        await sessione.cambiaServer()
        apri.finish()
        await apertura.value

        #expect(vm.formazione != nil, "svuotati i dati durante \(percorso), la Formazione resta sullo scheletro")
        #expect(vm.errore == nil)
        #expect(!vm.leggendo, "la Formazione resta «in lettura»")
        #expect(oggi.oggi != nil, "la giornata (testa e decisioni) arriva")
    }

    @Test("Svuotati i dati a Formazione già arrivata: resta a video e la rilettura dopo arriva", .timeLimit(.minutes(1)))
    func svuotamentoDopoLaLettura() async throws {
        let nome = "formazione-846-dopo-\(UUID().uuidString)"
        let memoria = try #require(UserDefaults(suiteName: nome))
        defer { memoria.removePersistentDomain(forName: nome) }
        let s = try Self.server()
        let sessione = Self.sessione(s, memoria: memoria)
        let oggi = OggiViewModel(server: s, conPromemoria: false)
        let vm = FormazioneViewModel(server: s, oggi: oggi, memoria: memoria, promemoria: {})

        await FormazioneView.ricarica(vm, oggi: oggi)
        try #require(vm.formazione != nil)
        let prima = vm.caricatore.risposte

        await sessione.cambiaServer()
        #expect(vm.formazione != nil, "lo svuotamento non toglie la Formazione già a video")

        await FormazioneView.ricarica(vm, oggi: oggi)
        #expect(vm.caricatore.risposte == prima + 1, "la rilettura dopo lo svuotamento arriva dal server")
        #expect(vm.formazione != nil)
        #expect(!vm.leggendo)
    }
}
