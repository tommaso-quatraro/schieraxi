import Foundation
import Testing
@testable import Schieraxi

/// Regole, un salvataggio che non riesce (#808), come la web: `salva()` dice se è riuscito (la domanda sulle modifiche non salvate
/// chiude la pagina solo allora) e con il 412 (regole cambiate su un altro dispositivo) i campi scritti restano, la pagina resta
/// aperta e le regole del server si rileggono. Regole della fixture `regole.json` (inventate).
@MainActor
@Suite("Regole: salvataggio che non riesce (#808)")
struct RegoleSalvataggioTests {
    /// Le regole della fixture; i primi `conflitti` PUT rispondono 412, quelli dopo rimandano il corpo ricevuto.
    private func server(conflitti: Int = 1) -> ServerDiProva {
        let rifiuti = Scatola<Int>()
        rifiuti.valore = conflitti
        return ServerDiProva { metodo, _, corpo in
            if metodo == "PUT" {
                let restano = rifiuti.valore ?? 0
                if restano > 0 {
                    rifiuti.valore = restano - 1
                    throw ErroreApi.conflitto
                }
                return corpo ?? Data("{}".utf8)
            }
            return try Fixture.dati("regole")
        }
    }

    @Test("Con il 412 i campi scritti restano, la pagina non si chiude e le regole si rileggono")
    func conflittoTieneICampi() async {
        let s = server()
        let vm = RegoleEditorViewModel(server: s)
        await vm.carica()
        vm.numero("bonus.assist").wrappedValue = 1.5
        let riuscito = await vm.salva()
        #expect(!riuscito, "un 412 non è un salvataggio riuscito: la domanda non chiude la pagina")
        #expect(vm.modificato, "la modifica resta da salvare")
        #expect(vm.numero("bonus.assist").wrappedValue == 1.5, "il campo scritto resta com'è")
        #expect(vm.esito == Catalogo.Err.conflitto, "la frase della web per il 412")
        #expect(!vm.esitoRiuscito)
        #expect(s.quante("GET /api/regole") == 2, "dopo il 412 le regole del server si rileggono")
    }

    @Test("Dopo il 412 un nuovo «Salva» manda i campi scritti")
    func dopoIlConflittoSiSalvanoICampiScritti() async throws {
        let s = server()
        let vm = RegoleEditorViewModel(server: s)
        await vm.carica()
        vm.numero("bonus.assist").wrappedValue = 1.5
        await vm.salva()
        let riuscito = await vm.salva()
        #expect(riuscito)
        #expect(!vm.modificato)
        #expect(vm.esito == Catalogo.Regole.regoleSalvateConsigli)
        let corpo = try #require(s.corpiInviati(a: "PUT /api/regole").last)
        let inviate = try JSONDecoder().decode(JSONValue.self, from: corpo)
        #expect(inviate.valore("bonus.assist")?.numero == 1.5, "parte quello che c'è nei campi")
    }

    @Test("Un controllo che non passa o un errore del server: non riuscito, e la modifica resta")
    func erroreNonRiuscito() async {
        let s = ServerDiProva { metodo, _, _ in
            if metodo == "PUT" { throw ErroreApi.server("Regole non valide") }
            return try Fixture.dati("regole")
        }
        let vm = RegoleEditorViewModel(server: s)
        await vm.carica()
        for m in vm.moduliAttivi { vm.alternaModulo(m) }
        #expect(await vm.salva() == false)
        #expect(vm.esito == "Scegli almeno un modulo.")
        #expect(!vm.esitoRiuscito)
        #expect(vm.modificato)
        vm.alternaModulo("4-4-2")
        #expect(await vm.salva() == false)
        #expect(vm.esito == "Regole non valide")
        #expect(vm.modificato)
    }

    @Test("Un salvataggio riuscito lo dice")
    func riuscito() async {
        let vm = RegoleEditorViewModel(server: server(conflitti: 0))
        await vm.carica()
        vm.numero("bonus.assist").wrappedValue = 2
        #expect(await vm.salva())
        #expect(vm.esitoRiuscito)
        #expect(!vm.modificato)
    }
}
