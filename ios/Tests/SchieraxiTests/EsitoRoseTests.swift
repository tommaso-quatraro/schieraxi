import Foundation
import Testing
@testable import Schieraxi

/// Aggiorna le rose, il riepilogo di un salvataggio («Rose salvate», «Cosa è cambiato»): resta solo finché non si riprova.
/// Come la web, che a ogni nuovo controllo sostituisce il riepilogo: se il tentativo dopo non va (file scartato, testo o file
/// rifiutati dal server) in cima non deve restare «Rose salvate» del salvataggio di prima. Squadre INVENTATE.
@MainActor
@Suite("Aggiorna le rose: riepilogo del salvataggio")
struct EsitoRoseTests {
    /// L'esito di un salvataggio come lo manda il server.
    private static let esitoSalvato = #"{"squadre_importate": ["Real Fantasia"], "totale_squadre": 2, "avvisi": [], "riepilogo": "Fatto"}"#

    /// Come non va il tentativo fatto dopo il salvataggio.
    enum TentativoCheNonVa: CaseIterable {
        case testoRifiutatoDalServer
        case fileScartatoSulTelefono
        case fileRifiutatoDalServer
    }

    /// Accetta la prima anteprima e il salvataggio; ogni anteprima dopo la rifiuta.
    private func serverCheRifiutaLaSecondaAnteprima() -> ServerDiProva {
        let anteprime = Scatola<Int>()
        let anteprima = AnteprimaRoseTests.risposta
        let esito = Self.esitoSalvato
        return ServerDiProva { _, percorso, _ in
            guard percorso.hasPrefix("/api/rose/anteprima") else { return Data(esito.utf8) }
            let numero = (anteprime.valore ?? 0) + 1
            anteprime.valore = numero
            if numero > 1 { throw ErroreApi.server("Nessuna rosa trovata") }
            return Data(anteprima.utf8)
        }
    }

    /// Anteprima e «Conferma e salva» riusciti: il riepilogo c'è.
    private func dopoUnSalvataggio() async throws -> ImportaExcelViewModel {
        let vm = ImportaExcelViewModel(server: serverCheRifiutaLaSecondaAnteprima())
        vm.testoRose = "Real Fantasia\nPirlotti"
        await vm.importaTesto()
        await vm.conferma()
        try #require(vm.esito != nil, "prima serve un salvataggio riuscito")
        return vm
    }

    /// Un file in una cartella tutta sua (chi lo usa la toglie alla fine).
    private func file(_ nome: String, _ contenuto: String) throws -> URL {
        let cartella = FileManager.default.temporaryDirectory.appendingPathComponent("esito-rose-\(UUID().uuidString)", isDirectory: true)
        try FileManager.default.createDirectory(at: cartella, withIntermediateDirectories: true)
        let url = cartella.appendingPathComponent(nome)
        try Data(contenuto.utf8).write(to: url)
        return url
    }

    @Test("Un nuovo tentativo che non va toglie il riepilogo del salvataggio di prima", arguments: TentativoCheNonVa.allCases)
    func tentativoCheNonVa(_ tentativo: TentativoCheNonVa) async throws {
        let vm = try await dopoUnSalvataggio()
        switch tentativo {
        case .testoRifiutatoDalServer:
            vm.testoRose = "Real Fantasia\nQuintavalle"
            await vm.importaTesto()
        case .fileScartatoSulTelefono:
            let url = try file("rose.pdf", "%PDF-1.4")
            defer { try? FileManager.default.removeItem(at: url.deletingLastPathComponent()) }
            await vm.importa(.success([url]))
        case .fileRifiutatoDalServer:
            let url = try file("rose.csv", "Real Fantasia;P;Pirlotti\n")
            defer { try? FileManager.default.removeItem(at: url.deletingLastPathComponent()) }
            await vm.importa(.success([url]))
        }
        #expect(vm.esito == nil, "in cima non resta «Rose salvate» del salvataggio di prima")
        #expect(vm.errore != nil, "si dice cosa non va")
        #expect(vm.anteprima == nil)
    }

    @Test("Il testo vuoto è solo un avviso, come sulla web: il riepilogo resta")
    func testoVuoto() async throws {
        let vm = try await dopoUnSalvataggio()
        #expect(vm.testoRose.isEmpty, "dopo il salvataggio il testo incollato non resta")
        await vm.importaTesto()
        #expect(vm.errore == "Incolla prima il testo delle rose")
        #expect(vm.esito != nil)
    }
}

/// L'esito finto delle fotografie (`-DEMO_SCHERMATA lega-importa-salvate` e `lega-importa-salvate-ok`): il JSON si legge.
@Suite("Demo: esito delle rose salvate")
struct DemoEsitoRoseTests {
    @Test("Le due schermate delle foto hanno un esito, con e senza avvisi",
          arguments: [("lega-importa-salvate", 1), ("lega-importa-salvate-ok", 0)])
    func schermateDelleFoto(_ schermata: String, _ avvisi: Int) throws {
        let esito = try #require(DemoEsitoRose.esito(schermata))
        #expect(esito.avvisi?.count == avvisi)
        #expect(esito.differenze != nil)
        #expect(esito.squadreImportate?.isEmpty == false)
    }

    @Test("Fuori da quelle schermate nessun esito finto", arguments: [nil, "lega-importa", "lega-importa-csv"] as [String?])
    func altreSchermate(_ schermata: String?) {
        #expect(DemoEsitoRose.esito(schermata) == nil)
    }
}
