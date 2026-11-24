import Foundation
import Testing
@testable import Schieraxi

/// La scelta della propria squadra dopo #863: «Le altre squadre» è solo l'elenco, come la web (`vistaAltreSquadre`); la propria si
/// sceglie dove la sceglie la web, in «La mia squadra»: «Non è la tua squadra?» nella sua rosa o, se non è ancora scelta, la pagina
/// con «Scegli quale delle squadre è la tua.» (`vistaRosa("")` e `collegaSceltaMia` di `app.js`). Scelta la squadra, al posto della
/// pagina aperta c'è la sua rosa, come la web che ridisegna «La mia squadra». Dati inventati.
@MainActor
@Suite("La mia squadra: la scelta come la web (#863)")
struct SceltaMiaSquadraTests {
    /// Un server con le squadre della fixture; `PUT /api/mia-squadra` risponde bene o, con `rifiuto`, con quell'errore.
    private static func server(rifiuto: String? = nil) -> ServerDiProva {
        ServerDiProva { metodo, percorso, _ in
            if metodo == "PUT", percorso == "/api/mia-squadra" {
                if let rifiuto { throw ErroreApi.server(rifiuto) }
                return Data("{}".utf8)
            }
            if percorso == "/api/squadre" { return try Fixture.dati("squadre") }
            throw ErroreApi.server("nessuna risposta per \(percorso)")
        }
    }

    @Test("«Non è la tua squadra?» nella rosa: la scelta si salva, le squadre si rileggono e c'è la rosa della squadra scelta")
    func dallaRosa() async throws {
        let s = Self.server()
        let lega = LegaViewModel(server: s)
        lega.percorso = [.rosa("Nuvola Ovest")]
        let errore = await lega.scegliMiaSquadra("Borgo Alto")
        #expect(errore == nil)
        let corpo = String(decoding: try #require(s.corpiInviati(a: "PUT /api/mia-squadra").last), as: UTF8.self)
        #expect(corpo == #"{"nome":"Borgo Alto"}"#)
        #expect(lega.percorso == [.rosa("Borgo Alto")])
        #expect(s.quante("GET /api/squadre") == 1, "le squadre si rileggono: «La mia squadra» in Impostazioni dice quella nuova")
    }

    @Test("Dalla pagina della scelta (la mia squadra non c'era ancora): al suo posto la rosa della squadra scelta")
    func dallaScelta() async throws {
        let lega = LegaViewModel(server: Self.server())
        lega.percorso = [.sceltaSquadra]
        #expect(await lega.scegliMiaSquadra("Borgo Alto") == nil)
        #expect(lega.percorso == [.rosa("Borgo Alto")])
    }

    @Test("Uscito dalla pagina mentre si salvava: la pila delle Impostazioni non cambia")
    func usciti() async throws {
        let pile: [[PaginaImpostazioni]] = [[], [.regole], [.squadre]]
        for percorso in pile {
            let lega = LegaViewModel(server: Self.server())
            lega.percorso = percorso
            #expect(await lega.scegliMiaSquadra("Borgo Alto") == nil)
            #expect(lega.percorso == percorso)
        }
    }

    @Test("Il server rifiuta: il suo motivo, la pagina resta quella e le squadre non si rileggono")
    func rifiuto() async throws {
        let s = Self.server(rifiuto: "Squadra non trovata")
        let lega = LegaViewModel(server: s)
        lega.percorso = [.rosa("Nuvola Ovest")]
        #expect(await lega.scegliMiaSquadra("Borgo Alto") == "Squadra non trovata")
        #expect(lega.percorso == [.rosa("Nuvola Ovest")])
        #expect(s.quante("GET /api/squadre") == 0)
    }
}
