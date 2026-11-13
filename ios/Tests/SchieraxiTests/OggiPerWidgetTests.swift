import Foundation
import Testing
@testable import Schieraxi

/// Il rischio principale del passo 1b (#673, piano §5): senza la scheda Oggi, widget e promemoria ricevono ancora la giornata. La
/// Formazione è l'unica schermata che legge `/api/oggi` (`FormazioneView.ricarica`), e ogni lettura fresca passa la giornata a
/// `OggiViewModel.dopoLetturaFresca` (nell'app: permesso, promemoria, riassunto per il widget con `Aggiornamento.elabora`); mai la
/// copia sul telefono, che sarebbe una giornata vecchia. I collegamenti di prima dei widget (`schieraxi://oggi`) aprono la Formazione.
/// Il comando «Aggiorna» lo mandano anche altre prove: qui si conta «almeno», mai «esattamente».
@MainActor
@Suite("Widget e promemoria ricevono ancora la giornata")
struct OggiPerWidgetTests {
    /// Le giornate arrivate a widget e promemoria, nell'ordine.
    @MainActor
    final class Arrivate {
        var giornate: [Int?] = []
    }

    /// Un server con la giornata e la formazione delle fixture; `giu`: non risponde niente.
    static func server(indirizzo: String = "https://prova-\(UUID().uuidString).invalid", giu: Bool = false) -> ServerDiProva {
        ServerDiProva(indirizzo: indirizzo) { _, percorso, _ in
            if giu { throw ErroreApi.rete("spento") }
            if percorso.hasPrefix("/api/oggi") { return try Fixture.dati("oggi") }
            if percorso.hasPrefix("/api/scelta") { return Data("null".utf8) }
            return try Fixture.dati("formazione")
        }
    }

    /// La giornata come nell'app, ma quello che andrebbe a widget e promemoria finisce in `arrivate`.
    static func oggi(_ srv: ServerDiProva, _ arrivate: Arrivate) -> OggiViewModel {
        let vm = OggiViewModel(server: srv, conPromemoria: false)
        vm.dopoLetturaFresca = { arrivate.giornate.append($0.giornata) }
        return vm
    }

    @Test("Aprendo e rileggendo la Formazione la giornata letta dal server arriva a widget e promemoria, ogni volta")
    func formazionePassaLaGiornata() async throws {
        let srv = Self.server()
        let arrivate = Arrivate()
        let oggi = Self.oggi(srv, arrivate)
        let formazione = FormazioneViewModel(server: srv)
        await FormazioneView.ricarica(formazione, oggi: oggi)
        #expect(arrivate.giornate.count >= 1)
        #expect(arrivate.giornate.allSatisfy { $0 == 9 })
        #expect(formazione.formazione != nil, "insieme alla formazione")
        let prima = arrivate.giornate.count
        await FormazioneView.ricarica(formazione, oggi: oggi)
        #expect(arrivate.giornate.count >= prima + 1, "anche rileggendo")
        #expect(srv.quante("GET /api/oggi") >= 2)
    }

    @Test("Anche il comando «Aggiorna» (Cmd+R) rilegge la giornata e la passa")
    func comandoAggiorna() async throws {
        let arrivate = Arrivate()
        let oggi = Self.oggi(Self.server(), arrivate)
        NotificationCenter.default.post(name: .aggiornaTutto, object: nil)
        await attendi("la giornata arriva al widget", finche: { !arrivate.giornate.isEmpty })
        #expect(arrivate.giornate.allSatisfy { $0 == 9 })
        withExtendedLifetime(oggi) {}
    }

    @Test("Con il server spento resta la copia sul telefono: niente promemoria né widget su una giornata vecchia")
    func copiaNonPassa() async throws {
        let indirizzo = "https://prova-copia-\(UUID().uuidString).invalid"
        let primaApertura = Arrivate()
        let primo = Self.oggi(Self.server(indirizzo: indirizzo), primaApertura)
        await primo.carica()
        #expect(!primaApertura.giornate.isEmpty)
        // la copia si scrive in secondo piano: si aspetta che ci sia
        var presente = false
        for _ in 0..<100 where !presente {
            presente = await Cache.leggi(OggiRepository.percorso, indirizzo: indirizzo) != nil
            if !presente { try await Task.sleep(nanoseconds: 20_000_000) }
        }
        try #require(presente, "la giornata letta è stata salvata sul telefono")
        // nuova apertura con il server spento: si vede la copia, ma non va a widget e promemoria
        let secondaApertura = Arrivate()
        let secondo = Self.oggi(Self.server(indirizzo: indirizzo, giu: true), secondaApertura)
        await secondo.carica()
        #expect(secondo.oggi?.giornata == 9, "la copia si vede")
        #expect(secondo.datiSalvati != nil)
        #expect(secondaApertura.giornate.isEmpty, "niente a widget e promemoria")
        withExtendedLifetime(primo) {}
    }

    @Test("I widget già sulla Home e gli avvisi di prima aprono la Formazione (`schieraxi://oggi`, `formazione`)")
    func collegamentiDeiWidget() throws {
        for indirizzo in ["schieraxi://oggi", "schieraxi://formazione"] {
            let url = try #require(URL(string: indirizzo))
            #expect(Collegamenti.interpreta(url) == .sezione(.formazione), "\(indirizzo)")
        }
        #expect(Sezione.da(nome: "oggi") == .formazione, "anche l'ultima sezione salvata da chi era su Oggi")
        #expect(!Sezione.allCases.map(\.rawValue).contains("oggi"))
    }
}
