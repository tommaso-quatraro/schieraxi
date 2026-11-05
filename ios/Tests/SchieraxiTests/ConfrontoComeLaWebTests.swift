import Foundation
import Testing
@testable import Schieraxi

/// «Chi schierare?» con le parole della web (#281): il posto in formazione è «Titolare», «Panchina 2» o «Non schierato»
/// (`testoPosto` di app.js, chiavi `mercato.posto_*` di testi.js), mai «Fuori», che è una parola della titolarità; i numeri
/// negativi delle cause hanno il meno tipografico («−1,12», `numMeno` di app.js). Dati inventati (`Tests/Fixtures`).
@Suite("Confronto come la web")
struct ConfrontoComeLaWebTests {
    // MARK: posto in formazione

    @Test("Il posto a parole, con le chiavi della web")
    func testoPosto() throws {
        let web = try TestiWeb()
        let titolare = try web.italiano("mercato.posto_titolare")
        let panchina = try web.italiano("mercato.panchina_n").replacingOccurrences(of: "{n}", with: "2")
        let fuori = try web.italiano("mercato.posto_fuori")
        #expect(SceltaDallaRosaViewModel.testoPosto("titolare") == titolare)
        #expect(SceltaDallaRosaViewModel.testoPosto("panchina 2") == panchina)
        #expect(SceltaDallaRosaViewModel.testoPosto("fuori") == fuori)
        #expect(SceltaDallaRosaViewModel.testoPosto("fuori") != "Fuori", "«Fuori» è la titolarità di chi è infortunato o squalificato")
        #expect(SceltaDallaRosaViewModel.testoPosto("") == "")
        #expect(SceltaDallaRosaViewModel.testoPosto("strano") == "")
    }

    @Test("Nella scelta del confronto: titolare, panchina e chi non è schierato")
    @MainActor
    func postoNellaScelta() async throws {
        let server = ServerDiProva { _, _, _ in try Fixture.dati("formazione") }
        let vm = SceltaDallaRosaViewModel(id: 7575, server: server)
        await vm.carica()
        try #require(vm.formazione.dato != nil)
        #expect(vm.posto(7575) == "Titolare")
        #expect(vm.posto(7481) == "Panchina 1")
        #expect(vm.posto(5678) == "Non schierato", "nella rosa ma né titolare né in panchina")
    }

    // MARK: numeri delle cause

    private static func fattore(percentuale: Bool? = nil) -> FattoreConfronto {
        FattoreConfronto(chiave: "porta", etichetta: "Porta inviolata", a: nil, b: nil, effetto: 0.3, percentuale: percentuale)
    }

    /// Il valore e come lo scrive la web (`numMeno(v, 2)`): il meno tipografico, niente «+», «0,00» senza segno, «–» se manca.
    static let valori: [(Double?, String)] = [
        (-1.12, "\u{2212}1,12"), (1.12, "1,12"), (-0.001, "0,00"), (0, "0,00"), (nil, "–"), (-0.5, "\u{2212}0,50"),
    ]

    @Test("I valori delle cause con il meno tipografico, come la web", arguments: ConfrontoComeLaWebTests.valori)
    func valoreDellaCausa(valore: Double?, atteso: String) {
        let testo = Confronto.valoreFattore(Self.fattore(), valore)
        #expect(testo == atteso)
        #expect(!testo.contains("-"), "mai il trattino al posto del meno")
    }

    @Test("Le percentuali restano percentuali")
    func percentuale() {
        #expect(Confronto.valoreFattore(Self.fattore(percentuale: true), 0.45) == "45%")
    }

    // MARK: «Tutti i numeri» (#293)

    private static func giocatore(_ id: Int, inCasa: Bool, difficolta: Int, quota: Double?) throws -> Giocatore {
        let q = quota.map { #""quota_titolare": \#($0),"# } ?? ""
        let json = #"""
        {"id": \#(id), "nome": "Aldo Pinarotti", "ruolo": "C", "squadra": "genoa", "avversario": "como", "in_casa": \#(inCasa), \#(q)
         "p_voto": 0.8, "fv_atteso": 6.4, "punti_attesi": 5.125, "indice": 72, "difficolta": \#(difficolta),
         "p_gol": 0.18, "p_assist": 0.12, "p_giallo": 0.2}
        """#
        return try Decodifica.decodifica(Data(json.utf8))
    }

    @Test("Le voci della tabella con le parole della web, nello stesso ordine")
    @MainActor
    func vociComeLaWeb() throws {
        let web = try TestiWeb()
        let chiavi = ["mercato.indice", "mercato.avversario", "mercato.partita", "mercato.gioca_riga", "mercato.fantavoto_atteso_riga",
                      "mercato.atteso_ponderato", "mercato.parte_titolare", "mercato.segna", "mercato.assist", "mercato.giallo"]
        // in testa a una riga con la maiuscola: la web scrive «segna», «assist», «giallo» con le chiavi della scheda
        let attese = try chiavi.map { try web.italiano($0).primaMaiuscola }
        let x = try Self.giocatore(1, inCasa: true, difficolta: 3, quota: 0.75)
        let y = try Self.giocatore(2, inCasa: false, difficolta: 2, quota: 0.2)
        #expect(VoceNumeriConfronto.voci(x, y).map(\.titolo) == attese)
    }

    @Test("I valori come la web: «vs COM» / «@ COM», la difficoltà e «Quando gioca» a parole")
    @MainActor
    func valoriComeLaWeb() throws {
        let web = try TestiWeb()
        let x = try Self.giocatore(1, inCasa: true, difficolta: 3, quota: 0.75)
        let y = try Self.giocatore(2, inCasa: false, difficolta: 2, quota: 0.2)
        let voci = VoceNumeriConfronto.voci(x, y)
        try #require(voci.count == 10)
        #expect(voci[1].a == "vs COM", "come le pedine e le righe, mai «COM casa»")
        #expect(voci[1].b == "@ COM")
        let normale = try web.italiano("diff.3"), abbordabile = try web.italiano("diff.2")
        #expect(voci[2].a == normale)
        #expect(voci[2].b == abbordabile)
        let quasiSempre = try web.italiano("mercato.parte_quasi_sempre"), diRado = try web.italiano("mercato.parte_di_rado")
        #expect(voci[6].a == quasiSempre)
        #expect(voci[6].b == diRado)
        #expect(voci[5].a == "5,13")
    }

    @Test("«Quando gioca» a parole, con le soglie della web (`partenzaAParole`)", arguments: [
        (0.7, "mercato.parte_quasi_sempre"), (0.95, "mercato.parte_quasi_sempre"), (0.4, "mercato.parte_a_volte"),
        (0.69, "mercato.parte_a_volte"), (0.39, "mercato.parte_di_rado"), (0, "mercato.parte_di_rado"),
    ])
    func quandoGioca(quota: Double, chiave: String) throws {
        let parola = try TestiWeb().italiano(chiave)
        #expect(VoceNumeriConfronto.quandoGioca(quota) == parola)
    }

    @Test("«Quando gioca» senza il dato: il trattino")
    func quandoGiocaSenzaDato() {
        #expect(VoceNumeriConfronto.quandoGioca(nil) == "–")
    }

    @Test("VoiceOver legge l'avversario per intero: «in casa contro Como»")
    @MainActor
    func avversarioAVoce() throws {
        let x = try Self.giocatore(1, inCasa: true, difficolta: 3, quota: 0.75)
        let y = try Self.giocatore(2, inCasa: false, difficolta: 2, quota: 0.2)
        let voce = VoceNumeriConfronto.voci(x, y)[1]
        #expect(voce.frase(x, y) == "Avversario: Aldo Pinarotti in casa contro Como, Aldo Pinarotti in trasferta contro Como")
    }

    @Test("Sotto i nomi in cima, la partita come la web: «GEN vs COM», «GEN @ COM»")
    func partitaInCima() throws {
        let x = try Self.giocatore(1, inCasa: true, difficolta: 3, quota: 0.75)
        let y = try Self.giocatore(2, inCasa: false, difficolta: 2, quota: 0.2)
        #expect(ColonnaDuello.partita(x) == "GEN vs COM")
        #expect(ColonnaDuello.partita(y) == "GEN @ COM")
    }
}
