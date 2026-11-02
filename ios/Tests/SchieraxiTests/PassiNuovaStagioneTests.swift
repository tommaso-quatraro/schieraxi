import Foundation
import Testing
@testable import Schieraxi

/// Altro > Nuova stagione: i passi dopo l'archivio sono quelli della web (`nuovaStagione` di `app.js`), senza l'asta
/// (la pagina «Asta e riparazione» non c'è più sull'iPhone). «Aggiorna i dati» solo per chi amministra il server.
@Suite("Nuova stagione: i passi")
struct PassiNuovaStagioneTests {
    @Test("Chi amministra vede i quattro passi della web, numerati da 1 a 4")
    func amministratoreQuattroPassi() {
        let passi = PassiNuovaStagione.elenco(amministratore: true)
        #expect(passi.map(\.titolo) == ["Importa le nuove rose", "Controlla le regole", "Inserisci i crediti delle squadre", "Aggiorna i dati"])
        #expect(passi.map(\.numero) == [1, 2, 3, 4])
        #expect(passi.map(\.pagina) == [.importa, .regole, .crediti, .stato])
    }

    @Test("Senza amministratore niente «Aggiorna i dati»: tre passi, numerati da 1 a 3")
    func senzaAmministratoreTrePassi() {
        let passi = PassiNuovaStagione.elenco(amministratore: false)
        #expect(passi.map(\.titolo) == ["Importa le nuove rose", "Controlla le regole", "Inserisci i crediti delle squadre"])
        #expect(passi.map(\.numero) == [1, 2, 3])
    }

    @Test("Il passo dell'asta non c'è", arguments: [true, false])
    func nienteAsta(amministratore: Bool) {
        let testi = PassiNuovaStagione.elenco(amministratore: amministratore).flatMap { [$0.titolo, $0.dettaglio] }
        let conAsta = testi.filter { $0.range(of: #"\basta\b"#, options: [.regularExpression, .caseInsensitive]) != nil }
        #expect(conAsta.isEmpty)
    }
}
