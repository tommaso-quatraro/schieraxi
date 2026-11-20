import Foundation
import Testing
@testable import Schieraxi

/// Regole e versioni (ETag) con modifiche non salvate (#808, dalla revisione): una rilettura (ritorno sulle Regole da un'altra
/// scheda, Cmd+R) che porta regole cambiate altrove non deve far passare un «Salva» fatto sui campi vecchi. Il «Salva» manda l'ETag
/// della versione da cui vengono i campi: se le regole sono cambiate, il server risponde 412 e si va per la strada del 412 (frase,
/// campi ricaricati). Senza modifiche, una rilettura ricarica campi ed ETag insieme. Il server finto si comporta come quello vero:
/// ogni risposta mette il suo ETag (come fa il trasporto, `VersioniRisorse`), ogni scrittura controlla quello ricordato.
@MainActor
@Suite("Regole: versioni con modifiche non salvate (#808)")
struct RegoleVersioniTests {
    /// Le regole sul server finto e la loro versione (l'ETag è «"vN"»). Si possono cambiare «dalla web».
    final class RegoleSulServer: @unchecked Sendable {
        private let blocco = NSLock()
        private var regole: JSONValue
        private var versione = 1
        private var rotte = false

        init() throws {
            regole = try JSONDecoder().decode(JSONValue.self, from: Fixture.dati("regole"))
        }

        /// Le letture che non rispondono (rete giù).
        var lettureRotte: Bool {
            get { blocco.lock(); defer { blocco.unlock() }; return rotte }
            set { blocco.lock(); defer { blocco.unlock() }; rotte = newValue }
        }

        func numero(_ percorso: String) -> Double? {
            blocco.lock(); defer { blocco.unlock() }
            return regole.valore(percorso)?.numero
        }

        /// Un altro dispositivo salva le regole con un valore cambiato: nuova versione.
        func cambiaDallaWeb(_ percorso: String, _ valore: Double) {
            blocco.lock(); defer { blocco.unlock() }
            regole.imposta(percorso, .numero(valore))
            versione += 1
        }

        func leggi() throws -> (regole: JSONValue, etag: String) {
            blocco.lock(); defer { blocco.unlock() }
            if rotte { throw ErroreApi.rete("spento") }
            return (regole, "\"v\(versione)\"")
        }

        /// Scrive se l'ETag mandato (If-Match) è quello di adesso, o se non ce n'è uno; dice l'ETag della risposta.
        func scrivi(_ nuove: JSONValue, ifMatch: String?) -> (riuscita: Bool, etag: String) {
            blocco.lock(); defer { blocco.unlock() }
            if let ifMatch, ifMatch != "\"v\(versione)\"" { return (false, "\"v\(versione)\"") }
            regole = nuove
            versione += 1
            return (true, "\"v\(versione)\"")
        }
    }

    private func server(_ r: RegoleSulServer) -> ServerDiProva {
        let indirizzo = "https://prova-\(UUID().uuidString).invalid"
        return ServerDiProva(indirizzo: indirizzo) { metodo, _, corpo in
            if metodo == "PUT" {
                // If-Match è l'ETag ricordato dal trasporto; la risposta (anche il 412) porta l'ETag di adesso
                let nuove = try JSONDecoder().decode(JSONValue.self, from: corpo ?? Data())
                let esito = r.scrivi(nuove, ifMatch: VersioniRisorse.condivise.leggi(server: indirizzo, risorsa: "regole"))
                VersioniRisorse.condivise.imposta(esito.etag, server: indirizzo, risorsa: "regole")
                guard esito.riuscita else { throw ErroreApi.conflitto }
                return try JSONEncoder().encode(nuove)
            }
            let letto = try r.leggi()
            VersioniRisorse.condivise.imposta(letto.etag, server: indirizzo, risorsa: "regole")
            return try JSONEncoder().encode(letto.regole)
        }
    }

    @Test("Modifiche non salvate e regole cambiate sulla web: dopo la rilettura «Salva» riceve 412 e la modifica della web resta")
    func rilettutaConModificheNonPassaSopraLaWeb() async throws {
        let r = try RegoleSulServer()
        let vm = RegoleEditorViewModel(server: server(r), attesaDopoConflitto: .zero)
        await vm.carica()
        vm.numero("bonus.mvp").wrappedValue = 1          // modifica non salvata
        r.cambiaDallaWeb("bonus.assist", 2)              // intanto sulla web
        await vm.carica()                                // si torna sulle Regole: la rilettura
        #expect(vm.modificato, "la modifica non salvata resta")
        #expect(vm.numero("bonus.assist").wrappedValue == 1, "i campi restano quelli su cui si sta modificando")
        let riuscito = await vm.salva()
        #expect(!riuscito, "«Salva» riceve il 412")
        #expect(r.numero("bonus.assist") == 2, "sul server resta la modifica della web")
        #expect(r.numero("bonus.mvp") == 0, "i campi vecchi non sono stati scritti")
        #expect(vm.esito == Catalogo.Err.conflitto)
        #expect(vm.numero("bonus.assist").wrappedValue == 2, "i campi si ricaricano con le regole del server")
        #expect(!vm.modificato)
    }

    @Test("Senza modifiche una rilettura ricarica campi e versione insieme: «Salva» riesce e tiene la modifica della web")
    func rilettutaSenzaModificheRicaricaTutto() async throws {
        let r = try RegoleSulServer()
        let vm = RegoleEditorViewModel(server: server(r), attesaDopoConflitto: .zero)
        await vm.carica()
        r.cambiaDallaWeb("bonus.assist", 2)
        await vm.carica()
        #expect(vm.numero("bonus.assist").wrappedValue == 2, "i campi hanno le regole nuove")
        vm.numero("bonus.mvp").wrappedValue = 1
        #expect(await vm.salva())
        #expect(r.numero("bonus.assist") == 2)
        #expect(r.numero("bonus.mvp") == 1)
    }

    @Test("Dopo un 412 la rilettura non riesce: si dice perché, i campi restano, e il prossimo «Salva» riceve di nuovo 412")
    func rilettutaFallitaDopoIlConflitto() async throws {
        let r = try RegoleSulServer()
        let vm = RegoleEditorViewModel(server: server(r), attesaDopoConflitto: .zero)
        await vm.carica()
        vm.numero("bonus.assist").wrappedValue = 1.5
        r.cambiaDallaWeb("bonus.mvp", 1)
        r.lettureRotte = true
        #expect(await vm.salva() == false)
        #expect(vm.esito == ErroreApi.testoNonRaggiungibile, "l'errore della rilettura, non «Ho ricaricato la versione nuova»")
        #expect(vm.esito != Catalogo.Err.conflitto)
        #expect(vm.numero("bonus.assist").wrappedValue == 1.5, "senza le regole nuove i campi restano come sono")
        #expect(vm.modificato)
        r.lettureRotte = false
        #expect(await vm.salva() == false, "il server ha ancora una versione che i campi non hanno visto")
        #expect(r.numero("bonus.assist") == 1, "i campi vecchi non sono stati scritti")
        #expect(r.numero("bonus.mvp") == 1)
        #expect(vm.numero("bonus.mvp").wrappedValue == 1, "ora i campi hanno le regole nuove")
        #expect(vm.esito == Catalogo.Err.conflitto)
    }
}
