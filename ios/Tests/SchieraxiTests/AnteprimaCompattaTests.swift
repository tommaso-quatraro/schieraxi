import Foundation
import Testing
@testable import Schieraxi

/// Aggiorna le rose, l'anteprima come la web dopo la #878 (#873, punto 7, `anteprima.js`): alla prima importazione le squadre sono
/// tutte nuove e «Nuova» su ognuna non dice niente; una squadra senza dubbi sta in due righe, il nome e i conti da aprire (con dentro
/// i nomi), mentre con dei dubbi i conti restano una riga a sé sopra i dubbi. Squadre e giocatori INVENTATI.
@Suite("Aggiorna le rose: anteprima compatta come la web (#873)")
struct AnteprimaCompattaTests {
    /// La stessa anteprima di `AnteprimaRoseTests` («Atletico Pigiama» è nuova), ma con rose già salvate prima.
    static let conRoseSalvate = AnteprimaRoseTests.risposta.replacingOccurrences(
        of: #""prima_importazione": true"#, with: #""prima_importazione": false"#)

    private func anteprima(_ json: String) throws -> AnteprimaRose {
        try Decodifica.decodifica(Data(json.utf8))
    }

    // MARK: «Nuova»

    @Test("Prima importazione: nessuna squadra porta «Nuova», anche se il server le segna nuove")
    func primaImportazioneSenzaNuova() throws {
        let r = try anteprima(AnteprimaRoseTests.risposta)
        #expect(r.differenze?.primaImportazione == true)
        let nuova = try #require(r.squadre.first { $0.nuova })
        #expect(!AnteprimaLogica.mostraNuova(nuova, differenze: r.differenze))
        #expect(!r.squadre.contains { AnteprimaLogica.mostraNuova($0, differenze: r.differenze) })
    }

    @Test("Rose già salvate: «Nuova» solo sulla squadra che si aggiunge")
    func aggiuntaConNuova() throws {
        let r = try anteprima(Self.conRoseSalvate)
        #expect(r.differenze?.primaImportazione == false)
        #expect(r.squadre.map { AnteprimaLogica.mostraNuova($0, differenze: r.differenze) } == [false, true])
    }

    @Test("Senza differenze (server di prima): «Nuova» come la segna il server")
    func senzaDifferenze() throws {
        let r = try anteprima(AnteprimaRoseTests.risposta)
        #expect(r.squadre.map { AnteprimaLogica.mostraNuova($0, differenze: nil) } == [false, true])
    }

    // MARK: righe

    @Test("Una squadra senza dubbi: i conti stanno nella riga da aprire con i nomi, non in una riga a sé")
    func senzaDubbiDueRighe() throws {
        let r = try anteprima(AnteprimaRoseTests.risposta)
        let pulita = try #require(r.squadre.first { $0.nome == "Atletico Pigiama" })
        #expect(AnteprimaLogica.dubbi(pulita).isEmpty)
        #expect(AnteprimaLogica.contiNelRipiegato(pulita))
    }

    @Test("Con dei dubbi, o senza riconosciuti: i conti restano una riga a sé")
    func conDubbiRigaASe() throws {
        let r = try anteprima(AnteprimaRoseTests.risposta)
        let conDubbi = try #require(r.squadre.first { $0.nome == "Real Fantasia" })
        #expect(!AnteprimaLogica.contiNelRipiegato(conDubbi))
        let vuota = SquadraAnteprima(nome: "Sporting Ciabatta", giocatori: [])
        #expect(!AnteprimaLogica.contiNelRipiegato(vuota))
    }
}
