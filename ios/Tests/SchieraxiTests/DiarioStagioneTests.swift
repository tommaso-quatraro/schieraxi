import Foundation
import Testing
@testable import Schieraxi

/// Diario con due stagioni (#176, parte iPhone; la web l'ha fatto nella #198): la giornata 10 dell'anno scorso e quella di
/// quest'anno sono due voci diverse.
/// - «Ho schierato la consigliata» e «Correggi a mano» mandano la `stagione` della voce (il server rifiuta le stagioni passate);
/// - i pulsanti per cambiare una voce ci sono solo se il server non dice `modificabile: false` (server vecchio senza il campo: ci sono).
@MainActor
struct DiarioStagioneTests {
    private func voce(_ json: String) throws -> VoceDiario {
        try Decodifica.decodifica(Data(json.utf8))
    }

    /// Il corpo di `POST /api/diario/schierata` come l'ha ricevuto il server finto.
    private struct CorpoInviato: Decodable, Equatable {
        let giornata: Int?
        let tipo: String?
        let titolari: [Int]?
        let stagione: String?
    }

    /// Un server che accetta ogni «Ho schierato…» e rimanda un diario vuoto.
    private func serverCheAccetta() -> ServerDiProva {
        ServerDiProva { metodo, _, _ in
            metodo == "POST" ? Data("{}".utf8) : Data(#"{"giornate": []}"#.utf8)
        }
    }

    private func corpi(_ s: ServerDiProva) throws -> [CorpoInviato] {
        try s.corpiInviati(a: "/api/diario/schierata").map { try JSONDecoder().decode(CorpoInviato.self, from: $0) }
    }

    // MARK: la stagione nel corpo del POST

    @Test("«Ho schierato la consigliata» manda la stagione della voce: la giornata 10 di due stagioni non si confonde")
    func laConsigliataMandaLaStagioneDellaVoce() async throws {
        let s = serverCheAccetta()
        let vm = DiarioViewModel(server: s)
        let annoScorso = try voce(#"{"giornata": 10, "stagione": "2025-26"}"#)
        let questAnno = try voce(#"{"giornata": 10, "giornata_lega": 7, "stagione": "2026-27"}"#)
        await vm.haSchieratoLaConsigliata(annoScorso)
        await vm.haSchieratoLaConsigliata(questAnno)
        #expect(try corpi(s) == [
            CorpoInviato(giornata: 10, tipo: "consigliata", titolari: nil, stagione: "2025-26"),
            CorpoInviato(giornata: 10, tipo: "consigliata", titolari: nil, stagione: "2026-27"),
        ])
    }

    @Test("«Correggi a mano» manda la stagione della voce insieme agli 11 titolari")
    func aManoMandaLaStagioneDellaVoce() async throws {
        let s = serverCheAccetta()
        let vm = DiarioViewModel(server: s)
        let v = try voce(#"{"giornata": 10, "stagione": "2025-26", "schierata": {"modulo": "4-4-2", "tipo": "manuale"}}"#)
        let errore = await vm.haSchieratoAMano(v, titolari: Array(21...31))
        #expect(errore == nil)
        #expect(try corpi(s) == [CorpoInviato(giornata: 10, tipo: "manuale", titolari: Array(21...31), stagione: "2025-26")])
    }

    @Test("Una voce senza stagione non manda una stagione vuota: il server usa quella in corso")
    func senzaStagioneIlCampoManca() async throws {
        let s = serverCheAccetta()
        let vm = DiarioViewModel(server: s)
        await vm.haSchieratoLaConsigliata(try voce(#"{"giornata": 10}"#))
        let corpo = try #require(s.corpiInviati(a: "/api/diario/schierata").first)
        #expect(!String(decoding: corpo, as: UTF8.self).contains("stagione"))
    }

    // MARK: pulsanti «Ho schierato…» e «Correggi a mano»

    @Test("I pulsanti per cambiare la voce seguono `modificabile`", arguments: [
        (#"{"giornata": 10, "stagione": "2026-27", "modificabile": true}"#, true),
        (#"{"giornata": 10, "stagione": "2025-26", "modificabile": false}"#, false),
        (#"{"giornata": 10, "stagione": "2026-27"}"#, true),                        // server vecchio senza il campo: come prima
        (#"{"giornata": 10, "stagione": "2026-27", "modificabile": null}"#, true),
        (#"{"stagione": "2026-27", "modificabile": true}"#, false),                 // senza giornata non c'è niente da salvare
    ])
    func pulsantiSecondoModificabile(json: String, conPulsanti: Bool) throws {
        #expect(try voce(json).siPuoCambiare == conPulsanti)
    }

    @Test("Con `modificabile: false` non parte nessun salvataggio verso il server")
    func stagionePassataNonScrive() async throws {
        let s = serverCheAccetta()
        let vm = DiarioViewModel(server: s)
        let v = try voce(#"{"giornata": 10, "stagione": "2025-26", "modificabile": false}"#)
        await vm.haSchieratoLaConsigliata(v)
        let errore = await vm.haSchieratoAMano(v, titolari: Array(1...11))
        #expect(errore != nil, "il foglio resta aperto con un errore")
        #expect(s.quante("POST /api/diario/schierata") == 0)
        #expect(vm.inSalvataggio == nil)
    }

    @Test("Due stagioni con la stessa giornata sono due voci, ognuna con i suoi pulsanti")
    func dueStagioniDueVoci() throws {
        let d: DiarioRisposta = try Decodifica.decodifica(Data(#"""
            {"giornate": [{"giornata": 10, "giornata_lega": 7, "stagione": "2026-27", "modificabile": true},
                          {"giornata": 10, "stagione": "2025-26", "modificabile": false}]}
            """#.utf8))
        let voci = try #require(d.giornate)
        #expect(Set(voci.map(\.id)).count == 2)
        #expect(voci.map(\.siPuoCambiare) == [true, false])
    }
}
