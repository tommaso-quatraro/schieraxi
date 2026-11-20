import Foundation
import Testing
@testable import Schieraxi

/// Regole, un salvataggio che non riesce (#808), come la web: `salva()` dice se è riuscito (la domanda sulle modifiche non salvate
/// chiude la pagina solo allora). Con il 412 (regole cambiate su un altro dispositivo) la frase della web e, dopo un attimo, i campi
/// si ricaricano con le regole del server: la pagina resta aperta, le modifiche non salvate si perdono, e un nuovo «Salva» non
/// scrive mai sopra la versione dell'altro dispositivo senza che si vedano i valori nuovi. Regole della fixture `regole.json`.
@MainActor
@Suite("Regole: salvataggio che non riesce (#808)")
struct RegoleSalvataggioTests {
    /// Le regole della fixture (assist 1); dalla seconda lettura quelle salvate dall'altro dispositivo (assist 2). I primi
    /// `conflitti` PUT rispondono 412, quelli dopo rimandano il corpo ricevuto. Senza ETag: le versioni sono in `RegoleVersioniTests`.
    private func server(conflitti: Int = 1) -> ServerDiProva {
        let rifiuti = Scatola<Int>()
        rifiuti.valore = conflitti
        let letture = Scatola<Int>()
        letture.valore = 0
        return ServerDiProva { metodo, _, corpo in
            if metodo == "PUT" {
                let restano = rifiuti.valore ?? 0
                if restano > 0 {
                    rifiuti.valore = restano - 1
                    throw ErroreApi.conflitto
                }
                return corpo ?? Data("{}".utf8)
            }
            let n = (letture.valore ?? 0) + 1
            letture.valore = n
            let testo = try Fixture.testo("regole")
            return Data((n == 1 ? testo : testo.replacingOccurrences(of: "\"assist\":1.0", with: "\"assist\":2.0")).utf8)
        }
    }

    /// Aspetta (al massimo 5 secondi) che una condizione diventi vera.
    private func aspetta(_ condizione: () -> Bool) async {
        var tentativi = 0
        while !condizione() && tentativi < 250 {
            try? await Task.sleep(for: .milliseconds(20))
            tentativi += 1
        }
    }

    @Test("Con il 412 la frase della web, poi i campi si ricaricano con le regole del server e la pagina resta aperta")
    func conflittoRicaricaLeRegoleDelServer() async throws {
        let s = server()
        let vm = RegoleEditorViewModel(server: s, attesaDopoConflitto: .zero)
        await vm.carica()
        vm.numero("bonus.assist").wrappedValue = 1.5
        let riuscito = await vm.salva()
        #expect(!riuscito, "un 412 non è un salvataggio riuscito: la domanda non chiude la pagina")
        #expect(vm.numero("bonus.assist").wrappedValue == 2, "i campi hanno le regole salvate dall'altro dispositivo")
        #expect(!vm.modificato, "le modifiche non salvate si perdono, come sulla web")
        #expect(vm.esito == Catalogo.Err.conflitto, "la frase della web per il 412 resta da leggere")
        #expect(!vm.esitoRiuscito)
        #expect(s.quante("GET /api/regole") >= 2, "dopo il 412 le regole del server si rileggono")
    }

    @Test("Dopo il 412 un nuovo «Salva» parte dalle regole dell'altro dispositivo, mai dai campi scritti prima")
    func dopoIlConflittoNonSiScriveSopra() async throws {
        let s = server()
        let vm = RegoleEditorViewModel(server: s, attesaDopoConflitto: .zero)
        await vm.carica()
        vm.numero("bonus.assist").wrappedValue = 1.5
        await vm.salva()
        vm.numero("bonus.mvp").wrappedValue = 1
        let riuscito = await vm.salva()
        #expect(riuscito)
        let corpo = try #require(s.corpiInviati(a: "PUT /api/regole").last)
        let inviate = try JSONDecoder().decode(JSONValue.self, from: corpo)
        #expect(inviate.valore("bonus.assist")?.numero == 2, "l'assist resta quello dell'altro dispositivo")
        #expect(inviate.valore("bonus.mvp")?.numero == 1, "parte la modifica fatta sui valori nuovi")
    }

    @Test("Mentre si aspetta di ricaricare dopo il 412, un altro «Salva» non parte")
    func nienteSecondoSalvaDuranteLAttesa() async throws {
        let s = server()
        let vm = RegoleEditorViewModel(server: s, attesaDopoConflitto: .milliseconds(500))
        await vm.carica()
        vm.numero("bonus.assist").wrappedValue = 1.5
        let primo = Task { await vm.salva() }
        await aspetta { vm.esito == Catalogo.Err.conflitto }
        #expect(vm.inCorso, "durante l'attesa il salvataggio è ancora in corso")
        #expect(vm.numero("bonus.assist").wrappedValue == 1.5, "per un attimo si vede ancora quello che si era scritto")
        #expect(await vm.salva() == false, "il secondo «Salva» non parte")
        #expect(s.quante("PUT /api/regole") == 1)
        #expect(await primo.value == false)
        #expect(vm.numero("bonus.assist").wrappedValue == 2)
    }

    @Test("Chiusa la pagina durante l'attesa dopo il 412, la rilettura non parte")
    func chiusaLaPaginaNienteRilettura() async throws {
        let s = server()
        let vm = RegoleEditorViewModel(server: s, attesaDopoConflitto: .seconds(2))
        await vm.carica()
        vm.numero("bonus.assist").wrappedValue = 1.5
        let primo = Task { await vm.salva() }
        await aspetta { vm.esito == Catalogo.Err.conflitto }
        vm.fermaAttese()                                  // la pagina si chiude
        #expect(await primo.value == false)
        #expect(vm.numero("bonus.assist").wrappedValue == 1.5, "niente rilettura: i campi non sono stati ricaricati")
        #expect(!vm.inCorso)
    }

    @Test("L'errore dell'ultimo salvataggio se ne va appena si cambia un campo")
    func unCampoCambiatoTogliLErrore() async {
        let vm = RegoleEditorViewModel(server: server(conflitti: 0))
        await vm.carica()
        for m in vm.moduliAttivi { vm.alternaModulo(m) }
        await vm.salva()
        #expect(vm.esito == "Scegli almeno un modulo.")
        vm.alternaModulo("4-4-2")
        #expect(vm.esito == nil, "il campo è cambiato: l'errore di prima non vale più")
        #expect(vm.esitoRiuscito)

        let dopo412 = RegoleEditorViewModel(server: server(), attesaDopoConflitto: .zero)
        await dopo412.carica()
        dopo412.numero("bonus.assist").wrappedValue = 1.5
        await dopo412.salva()
        #expect(dopo412.esito == Catalogo.Err.conflitto, "la frase resta anche con i campi ricaricati")
        dopo412.numero("bonus.mvp").wrappedValue = 1
        #expect(dopo412.esito == nil)
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
