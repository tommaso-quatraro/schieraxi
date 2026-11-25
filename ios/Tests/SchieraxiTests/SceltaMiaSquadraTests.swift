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
    private static func server(rifiuto: ErroreApi? = nil) -> ServerDiProva {
        ServerDiProva { metodo, percorso, _ in
            if metodo == "PUT", percorso == "/api/mia-squadra" {
                if let rifiuto { throw rifiuto }
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

    // MARK: «Non è la tua squadra?» nella rosa

    /// Un server con la rosa della fixture (la scrittura della scelta la fa la closure `scegli` del test).
    private static func serverRosa() -> ServerDiProva {
        ServerDiProva { metodo, percorso, _ in
            if metodo == "GET", percorso.hasPrefix("/api/rosa") { return try Fixture.dati("rosa") }
            return Data("{}".utf8)
        }
    }

    /// Revisione della #868: dopo il 412 della scelta l'ETag della rosa è già quello nuovo (`ServerClient` lo tiene anche col 412),
    /// quindi un «Salva» dei crediti con i dati vecchi in pagina riscriverebbe sopra quelli salvati dal PC senza avviso. Come dopo
    /// il 412 di «Cambia il nome» e dei crediti, la rosa si rilegge dal server e i campi ripartono dai suoi valori.
    @Test("«Non è la tua squadra?» che non riesce (anche 412): la rosa si rilegge e i campi ripartono dal server")
    func sceltaNonRiuscitaRileggeLaRosa() async throws {
        let server = Self.serverRosa()
        let vm = RosaViewModel(nome: "Nuvola Ovest", server: server, immagini: Immagini(server: server), centro: NotificationCenter())
        await vm.carica()
        vm.crediti = "99"   // scritto e non salvato: dopo il rifiuto riparte dal valore del server (la fixture non ha crediti)
        let errore = await vm.scegliMia("Borgo Alto") { _ in ErroreApi.conflitto.localizedDescription }
        #expect(errore == ErroreApi.conflitto.localizedDescription)
        #expect(server.quante("GET /api/rosa") == 2, "la rosa si rilegge dopo il rifiuto")
        #expect(vm.crediti == "")
    }

    @Test("«Non è la tua squadra?» riuscita: la rosa di prima non si rilegge (al suo posto si apre quella della squadra scelta)")
    func sceltaRiuscitaNonRilegge() async throws {
        let server = Self.serverRosa()
        let vm = RosaViewModel(nome: "Nuvola Ovest", server: server, immagini: Immagini(server: server), centro: NotificationCenter())
        await vm.carica()
        let errore = await vm.scegliMia("Borgo Alto") { _ in nil }
        #expect(errore == nil)
        #expect(server.quante("GET /api/rosa") == 1)
    }

    /// Revisione della #868: una squadra rinominata dal PC, scelta sull'iPhone, dà 412 («Ho ricaricato la versione nuova…»); senza
    /// rileggere le squadre elenco e rosa restavano vecchi e riprovando arrivava «Squadra non trovata». Come faceva prima
    /// `SquadreViewModel.impostaMia`, le squadre si rileggono anche quando il salvataggio non riesce.
    @Test("Il server rifiuta (anche con 412): il suo motivo, la pagina resta quella e le squadre si rileggono")
    func rifiuto() async throws {
        for (errore, frase) in [(ErroreApi.server("Squadra non trovata"), "Squadra non trovata"),
                                (ErroreApi.conflitto, ErroreApi.conflitto.localizedDescription)] {
            let s = Self.server(rifiuto: errore)
            let lega = LegaViewModel(server: s)
            lega.percorso = [.rosa("Nuvola Ovest")]
            #expect(await lega.scegliMiaSquadra("Borgo Alto") == frase)
            #expect(lega.percorso == [.rosa("Nuvola Ovest")])
            #expect(s.quante("GET /api/squadre") == 1, "le squadre si rileggono: elenco e selettore con i nomi di adesso")
        }
    }
}
