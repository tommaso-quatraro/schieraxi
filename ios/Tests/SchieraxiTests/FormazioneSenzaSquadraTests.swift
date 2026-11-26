import Foundation
import Testing
@testable import Schieraxi

/// Collaudo del 26/11 e revisione della #929: con le rose salvate e la tua squadra non scelta `/api/oggi` e `/api/formazione`
/// rispondono 400 («Indica la tua squadra in «La mia squadra»») e la Formazione era un errore con «Riprova». Come la web
/// (`caricaGiornata`, `mostraSenzaSquadra`): lo dice `/api/stato` (`rose_importate` vero, `mia_squadra` vuota) e la Formazione
/// mostra la domanda della guida, «Quale squadra è la tua?» con «Questa è la mia», senza chiedere giornata e formazione quando sa
/// già che la squadra manca. Dati inventati.
@MainActor
@Suite("Formazione senza la tua squadra: la domanda della guida, come la web")
struct FormazioneSenzaSquadraTests {
    private static let rifiuto = "Indica la tua squadra in «La mia squadra»"

    /// Il server: `/api/stato` con o senza la mia squadra (`mia.valore`); senza, Oggi e Formazione rispondono 400 come lui.
    /// `PUT /api/mia-squadra` segna la squadra scelta. Con `rotto` vero `/api/stato` non risponde.
    private static func server(mia: Scatola<String>, rotto: Scatola<Bool> = Scatola<Bool>()) -> ServerDiProva {
        ServerDiProva { metodo, percorso, corpo in
            if metodo == "PUT", percorso == "/api/mia-squadra" {
                let scelta = try JSONDecoder().decode([String: String].self, from: corpo ?? Data())
                mia.valore = scelta["nome"]
                return Data(#"{"mia_squadra": "x"}"#.utf8)
            }
            if percorso == "/api/stato" {
                if rotto.valore == true { throw ErroreApi.rete("senza rete") }
                let nome = mia.valore.map { "\"\($0)\"" } ?? "null"
                return Data(#"{"prossima_giornata": 11, "prossima_giornata_lega": 8, "rose_importate": true, "mia_squadra": \#(nome)}"#.utf8)
            }
            if percorso == "/api/squadre" {
                return Data(#"[{"nome": "Borgo Alto", "mia": false}, {"nome": "Nuvola Ovest", "mia": false}]"#.utf8)
            }
            guard mia.valore != nil else { throw ErroreApi.server(rifiuto) }
            if percorso.hasPrefix("/api/oggi") { return try Fixture.dati("oggi") }
            if percorso.hasPrefix("/api/scelta") { return Data("null".utf8) }
            if percorso.hasPrefix("/api/formazione") { return try Fixture.dati("formazione") }
            throw ErroreApi.server("nessuna risposta per \(percorso)")
        }
    }

    private static func modelli(_ srv: ServerDiProva) -> (FormazioneViewModel, OggiViewModel) {
        let oggi = OggiViewModel(server: srv, conPromemoria: false)
        return (FormazioneViewModel(server: srv, oggi: oggi, promemoria: {}), oggi)
    }

    @Test("Lo stato dice rose sì e squadra no: la domanda; la volta dopo giornata e formazione non si chiedono più")
    func laDomanda() async throws {
        let srv = Self.server(mia: Scatola<String>())
        let (vm, oggi) = Self.modelli(srv)
        await FormazioneView.ricarica(vm, oggi: oggi)
        #expect(oggi.squadra.manca)
        #expect(oggi.squadra.squadre.dato?.map(\.nome) == ["Borgo Alto", "Nuvola Ovest"], "il menu ha le squadre della lega")
        let oggiPrima = srv.quante("GET /api/oggi"), formazionePrima = srv.quante("GET /api/formazione")
        await FormazioneView.ricarica(vm, oggi: oggi)
        #expect(oggi.squadra.manca)
        #expect(srv.quante("GET /api/oggi") == oggiPrima && srv.quante("GET /api/formazione") == formazionePrima,
                "sapendo che la squadra manca, Oggi e Formazione (400) non si chiedono")
        #expect(srv.quante("GET /api/stato") >= 2, "lo stato si rilegge: la squadra può essere stata scelta altrove")
    }

    @Test("«Questa è la mia» salva la squadra: la domanda sparisce e la Formazione arriva")
    func scelta() async throws {
        let mia = Scatola<String>()
        let srv = Self.server(mia: mia)
        let (vm, oggi) = Self.modelli(srv)
        await FormazioneView.ricarica(vm, oggi: oggi)
        #expect(oggi.squadra.manca)
        #expect(await oggi.squadra.scegli("Borgo Alto") == nil)
        #expect(mia.valore == "Borgo Alto", "la prima squadra dell'elenco si sceglie, come sulla web")
        #expect(!oggi.squadra.manca)
        await FormazioneView.ricarica(vm, oggi: oggi)
        #expect(vm.formazione != nil && vm.errore == nil)
    }

    @Test("Con la squadra scelta niente domanda, e con un server di prima (senza rose_importate) nemmeno")
    func senzaDomanda() async throws {
        let mia = Scatola<String>()
        mia.valore = "Nuvola Ovest"
        let srv = Self.server(mia: mia)
        let (vm, oggi) = Self.modelli(srv)
        await FormazioneView.ricarica(vm, oggi: oggi)
        #expect(!oggi.squadra.manca)
        #expect(vm.formazione != nil)
        #expect(srv.quante("GET /api/squadre") == 0, "le squadre servono solo alla domanda")

        let vecchio = ServerDiProva { _, percorso, _ in
            if percorso == "/api/stato" { return Data(#"{"prossima_giornata": 11, "mia_squadra": null}"#.utf8) }
            throw ErroreApi.server(Self.rifiuto)
        }
        let squadra = SquadraDaScegliere(server: vecchio)
        #expect(await squadra.controlla() == false)
    }

    @Test("Se lo stato non si rilegge non si sa se la squadra manca: niente domanda, la Formazione di sempre (con «Riprova»)")
    func statoNonLetto() async throws {
        let rotto = Scatola<Bool>()
        let srv = Self.server(mia: Scatola<String>(), rotto: rotto)
        let (vm, oggi) = Self.modelli(srv)
        await FormazioneView.ricarica(vm, oggi: oggi)
        #expect(oggi.squadra.manca)
        rotto.valore = true
        await FormazioneView.ricarica(vm, oggi: oggi)
        #expect(!oggi.squadra.manca, "senza una risposta fresca la domanda non si mostra")
        #expect(vm.errore != nil, "la Formazione dice l'errore, con «Riprova»")
    }
}
