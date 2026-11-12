import Foundation
import Testing
@testable import Schieraxi

/// Nuova stagione: i passi dopo l'archivio sono quelli della web (`apriNuovaStagione` di `app.js`), senza l'asta né i crediti
/// delle squadre (le loro pagine non ci sono più sull'iPhone, #634). «Aggiorna i dati» solo per chi amministra il server.
@Suite("Nuova stagione: i passi")
struct PassiNuovaStagioneTests {
    @Test("Chi amministra vede i tre passi della web, numerati da 1 a 3")
    func amministratoreTrePassi() {
        let passi = PassiNuovaStagione.elenco(amministratore: true)
        #expect(passi.map(\.titolo) == ["Importa le nuove rose", "Controlla le regole", "Aggiorna i dati"])
        #expect(passi.map(\.numero) == [1, 2, 3])
        #expect(passi.map(\.pagina) == [.importa, .regole, .stato])
    }

    @Test("Senza amministratore niente «Aggiorna i dati»: due passi, numerati da 1 a 2")
    func senzaAmministratoreDuePassi() {
        let passi = PassiNuovaStagione.elenco(amministratore: false)
        #expect(passi.map(\.titolo) == ["Importa le nuove rose", "Controlla le regole"])
        #expect(passi.map(\.numero) == [1, 2])
    }

    @Test("Il passo dell'asta non c'è", arguments: [true, false])
    func nienteAsta(amministratore: Bool) {
        let testi = PassiNuovaStagione.elenco(amministratore: amministratore).flatMap { [$0.titolo, $0.dettaglio] }
        let conAsta = testi.filter { $0.range(of: #"\basta\b"#, options: [.regularExpression, .caseInsensitive]) != nil }
        #expect(conAsta.isEmpty)
    }
}
