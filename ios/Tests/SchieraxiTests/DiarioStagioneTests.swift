import Foundation
import Testing
@testable import Schieraxi

/// Giornate con due stagioni (#176, parte iPhone; la web l'ha fatto nella #198): la giornata 10 dell'anno scorso e quella di
/// quest'anno sono due voci diverse.
/// - «Non è quello che ho schierato» (pagina Giornate, #673 passo 2) manda la `stagione` della voce (il server rifiuta le stagioni
///   passate);
/// - la correzione c'è solo se il server non dice `modificabile: false` (server vecchio senza il campo: c'è).
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

    /// Un server che accetta ogni correzione e rimanda un diario vuoto.
    private func serverCheAccetta() -> ServerDiProva {
        ServerDiProva { metodo, _, _ in
            metodo == "POST" ? Data("{}".utf8) : Data(#"{"giornate": []}"#.utf8)
        }
    }

    private func corpi(_ s: ServerDiProva) throws -> [CorpoInviato] {
        try s.corpiInviati(a: "/api/diario/schierata").map { try JSONDecoder().decode(CorpoInviato.self, from: $0) }
    }

    // MARK: la stagione nel corpo del POST

    @Test("La correzione manda la stagione della voce insieme agli 11 titolari, con il tipo «manuale»")
    func correzioneMandaLaStagioneDellaVoce() async throws {
        let s = serverCheAccetta()
        let vm = GiornateViewModel(server: s)
        let annoScorso = try voce(#"{"giornata": 10, "stagione": "2025-26", "schierata": {"modulo": "4-4-2", "tipo": "manuale"}}"#)
        let questAnno = try voce(#"{"giornata": 10, "giornata_lega": 7, "stagione": "2026-27"}"#)
        #expect(await vm.correggi(annoScorso, titolari: Array(21...31)) == nil)
        #expect(await vm.correggi(questAnno, titolari: Array(1...11)) == nil)
        #expect(try corpi(s) == [
            CorpoInviato(giornata: 10, tipo: "manuale", titolari: Array(21...31), stagione: "2025-26"),
            CorpoInviato(giornata: 10, tipo: "manuale", titolari: Array(1...11), stagione: "2026-27"),
        ])
    }

    @Test("Una voce senza stagione non manda una stagione vuota: il server usa quella in corso")
    func senzaStagioneIlCampoManca() async throws {
        let s = serverCheAccetta()
        let vm = GiornateViewModel(server: s)
        _ = await vm.correggi(try voce(#"{"giornata": 10}"#), titolari: Array(1...11))
        let corpo = try #require(s.corpiInviati(a: "/api/diario/schierata").first)
        #expect(!String(decoding: corpo, as: UTF8.self).contains("stagione"))
    }

    @Test("Dopo la correzione la giornata resta aperta, l'esito si legge sotto i suoi 11 e VoiceOver lo dice")
    func esitoDellaCorrezione() async throws {
        let vm = GiornateViewModel(server: serverCheAccetta())
        var annunci: [String] = []
        vm.annuncia = { annunci.append($0) }
        let v = try voce(#"{"giornata": 11, "giornata_lega": 8, "stagione": "2026-27"}"#)
        #expect(await vm.correggi(v, titolari: Array(1...11)) == nil)
        #expect(vm.aperte == [v.id])
        #expect(vm.esito(per: v.id) == Catalogo.Diario.salvataManuale)
        #expect(vm.esito(per: "2025-26-11") == nil, "con due stagioni l'esito va solo sotto la giornata giusta")
        #expect(annunci == [Catalogo.Diario.salvataManuale])
    }

    @Test("Se il server rifiuta, l'errore torna al foglio e la pagina non cambia")
    func errorePerIlFoglio() async throws {
        let rifiuto = "Servono 11 giocatori della tua rosa con un modulo valido."
        let vm = GiornateViewModel(server: ServerDiProva.chePrecipita(.server(rifiuto)))
        let v = try voce(#"{"giornata": 11, "stagione": "2026-27"}"#)
        let errore = await vm.correggi(v, titolari: Array(1...11))
        #expect(errore != nil)
        #expect(vm.esito(per: v.id) == nil)
        #expect(vm.aperte.isEmpty)
    }

    // MARK: la correzione segue `modificabile`

    @Test("La correzione segue `modificabile`", arguments: [
        (#"{"giornata": 10, "stagione": "2026-27", "modificabile": true}"#, true),
        (#"{"giornata": 10, "stagione": "2025-26", "modificabile": false}"#, false),
        (#"{"giornata": 10, "stagione": "2026-27"}"#, true),                        // server vecchio senza il campo: come prima
        (#"{"giornata": 10, "stagione": "2026-27", "modificabile": null}"#, true),
        (#"{"stagione": "2026-27", "modificabile": true}"#, false),                 // senza giornata non c'è niente da salvare
    ])
    func correzioneSecondoModificabile(json: String, conPulsante: Bool) throws {
        #expect(try voce(json).siPuoCambiare == conPulsante)
    }

    @Test("Con `modificabile: false` non parte nessun salvataggio verso il server")
    func stagionePassataNonScrive() async throws {
        let s = serverCheAccetta()
        let vm = GiornateViewModel(server: s)
        let v = try voce(#"{"giornata": 10, "stagione": "2025-26", "modificabile": false}"#)
        let errore = await vm.correggi(v, titolari: Array(1...11))
        #expect(errore != nil, "il foglio resta aperto con un errore")
        #expect(s.quante("POST /api/diario/schierata") == 0)
    }

    @Test("Due stagioni con la stessa giornata sono due voci, ognuna con la sua correzione")
    func dueStagioniDueVoci() throws {
        let d: DiarioRisposta = try Decodifica.decodifica(Data(#"""
            {"giornate": [{"giornata": 10, "giornata_lega": 7, "stagione": "2026-27", "modificabile": true},
                          {"giornata": 10, "stagione": "2025-26", "modificabile": false}]}
            """#.utf8))
        let voci = try #require(d.giornate)
        #expect(Set(voci.map(\.id)).count == 2)
        #expect(voci.map(\.siPuoCambiare) == [true, false])
        let p = PaginaGiornate(d)
        #expect(p.righe.map(\.stagione) == ["2026-27", "2025-26"])
    }
}
