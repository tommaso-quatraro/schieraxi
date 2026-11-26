import Foundation
import Testing
@testable import Schieraxi

/// «Scrivici» come la web (26/11/2026, `paginaScrivici` di `fanta/web/impostazioni.js`): in Impostazioni la riga fra Informazioni e
/// Gestione, solo con un account; la pagina manda il commento a `POST /api/feedback` con la versione dell'app, «Invia» è spento
/// finché la casella è vuota, dopo l'invio la casella si svuota e compare «Grazie, l'abbiamo ricevuto.»; se non parte resta il
/// testo e si legge il messaggio del server. Testi dal catalogo comune (`fanta/testi/scrivici.json`). Solo dati inventati.
@MainActor
@Suite("Scrivici come la web")
struct ScriviciComeLaWebTests {
    private struct Corpo: Decodable {
        let testo: String
        let versione: String?
    }

    @Test("La riga «Scrivici» c'è solo con un account, fra Informazioni e Gestione, con i testi del catalogo")
    func riga() throws {
        #expect(VociImpostazioni.informazioni(gestisce: false).map(\.id) == ["informazioni"])
        #expect(VociImpostazioni.informazioni(gestisce: false, scrivici: true).map(\.id) == ["informazioni", "scrivici"])
        let voci = VociImpostazioni.informazioni(gestisce: true, scrivici: true)
        #expect(voci.map(\.id) == ["informazioni", "scrivici", "gestione"])
        let scrivici = try #require(voci.first { $0.id == "scrivici" })
        #expect(scrivici.nome == Catalogo.Scrivici.voce && scrivici.nome == "Scrivici")
        #expect(scrivici.sotto == Catalogo.Scrivici.voceSub)
        #expect(scrivici.pagina == .scrivici)
    }

    @Test("«Invia» resta spento con la casella vuota o di soli spazi")
    func vuota() {
        let vm = ScriviciViewModel(server: ServerDiProva { _, _, _ in Data("{}".utf8) })
        #expect(!vm.puoInviare)
        vm.testo = "  \n "
        #expect(!vm.puoInviare)
        vm.testo = "Un'idea"
        #expect(vm.puoInviare)
    }

    @Test("Inviato: va a /api/feedback con testo e versione, la casella si svuota e compare il grazie")
    func inviato() async throws {
        let server = ServerDiProva { _, _, _ in Data(#"{"ok": true, "id": 3}"#.utf8) }
        let vm = ScriviciViewModel(server: server, versione: "2.1")
        vm.testo = "La pagina delle giornate\nnon si apre."
        await vm.invia()
        #expect(server.richieste == ["POST /api/feedback"])
        let corpo = try JSONDecoder().decode(Corpo.self, from: try #require(server.corpiInviati(a: "/api/feedback").first))
        #expect(corpo.testo == "La pagina delle giornate\nnon si apre." && corpo.versione == "2.1")
        #expect(vm.testo.isEmpty && vm.errore == nil)
        #expect(vm.esito == Catalogo.Scrivici.grazie && vm.esito == "Grazie, l'abbiamo ricevuto.")
        #expect(!vm.puoInviare)
        // la casella che si svuota da sola non toglie il grazie; scrivere di nuovo sì
        vm.cambiato("")
        #expect(vm.esito == Catalogo.Scrivici.grazie)
        vm.testo = "Ancora una cosa"
        vm.cambiato(vm.testo)
        #expect(vm.esito == nil)
    }

    @Test("Non partito: resta il testo e si legge il messaggio del server")
    func nonPartito() async {
        let frase = "Il commento è troppo lungo: al massimo 2000 caratteri."
        let vm = ScriviciViewModel(server: ServerDiProva { _, _, _ in throw ErroreApi.server(frase) })
        vm.testo = "Un'idea per la formazione"
        await vm.invia()
        #expect(vm.errore == frase && vm.esito == nil)
        #expect(vm.testo == "Un'idea per la formazione" && vm.puoInviare)
    }

    @Test("La casella tiene al massimo 2000 caratteri, contati come il server")
    func massimo() {
        let vm = ScriviciViewModel(server: ServerDiProva { _, _, _ in Data("{}".utf8) })
        let lungo = String(repeating: "à", count: ScriviciViewModel.massimo + 30)
        vm.testo = lungo
        vm.cambiato(lungo)
        #expect(vm.testo.unicodeScalars.count == ScriviciViewModel.massimo)
        #expect(ScriviciViewModel.massimo == 2000)
    }
}
