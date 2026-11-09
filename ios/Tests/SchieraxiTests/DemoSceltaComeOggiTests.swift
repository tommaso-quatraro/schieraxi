import Foundation
import Testing
@testable import Schieraxi

/// #418: nella demo Oggi e Formazione dicono lo stesso stato della tua scelta, con le parole della web. Prima della scadenza la
/// consigliata non salvata («La tua formazione» in Oggi, «Stai vedendo la consigliata: non hai salvato una tua formazione.» in
/// Formazione); con la scelta salvata «La tua formazione · la tua scelta» e «La tua formazione è salvata (…)», a giornata
/// iniziata «… · vale quella che hai salvato». Il widget dice la tua scelta quando la dice Oggi (`tua_scelta`, come controlla la
/// sentinella del server). Prima la Formazione diceva «non hai salvato» e Oggi «la tua scelta», nella stessa demo.
/// Dati inventati: la lega della demo (`LegaDemo.swift`, `DatiDemo.swift`).
@MainActor
@Suite("Demo: Oggi e Formazione con lo stesso stato della scelta (#418)")
struct DemoSceltaComeOggiTests {
    /// Lo stesso istante fisso degli altri test della demo.
    static let adesso = Date(timeIntervalSinceReferenceDate: 815_000_000)

    /// La demo di una fotografia (`oggi` è la demo di sempre, la stessa della «Prova con dati di esempio»).
    private func demo(_ schermata: String) throws -> FinteServer {
        if schermata == "oggi" { return FinteServer.demoFissata(adesso: Self.adesso) }
        return try #require(FinteServer.demoFase(schermata, adesso: Self.adesso), "la demo «\(schermata)» non esiste")
    }

    private func oggi(_ server: FinteServer) async throws -> Oggi {
        try Decodifica.decodifica(try await server.richiesta("GET", "/api/oggi", corpo: nil))
    }

    /// La riga dello stato della scelta che la Formazione mostra con quella demo (la stessa logica della schermata).
    private func statoFormazione(_ server: FinteServer) async -> StatoScelta {
        let vm = FormazioneViewModel(server: server)
        await vm.carica()
        return vm.statoScelta
    }

    @Test("Oggi e Formazione dicono lo stesso stato della scelta in ogni foto della demo",
          arguments: ["oggi", "formazione-salvata", "formazione-chiusa", "oggi-in-corso"])
    func stessoStato(schermata: String) async throws {
        let s = try demo(schermata)
        let tua = try await oggi(s).formazione?.tuaScelta ?? false
        let stato = await statoFormazione(s)
        let salvata: Bool
        switch stato {
        case .salvata, .chiusa(tua: true): salvata = true
        case .consigliata, .chiusa(tua: false): salvata = false
        default:
            Issue.record("\(schermata): la Formazione dice «\(stato.titolo())», uno stato che la demo non usa")
            return
        }
        #expect(tua == salvata,
                "\(schermata): Oggi dice «\(TestiOggi.titoloFormazione(tuaScelta: tua))», la Formazione «\(stato.titolo())»")
    }

    @Test("Prima della scadenza la demo mostra la consigliata non salvata, con le parole della web in Oggi e in Formazione")
    func consigliataNonSalvata() async throws {
        let web = try TestiWeb()
        let titoloWeb = try web.italiano("oggi.tua_formazione")
        let rigaWeb = Catalogo.Formazione.statoConsigliata
        let s = try demo("oggi")
        let tua = try await oggi(s).formazione?.tuaScelta ?? false
        #expect(TestiOggi.titoloFormazione(tuaScelta: tua) == titoloWeb)
        let stato = await statoFormazione(s)
        #expect(stato == .consigliata)
        #expect(stato.titolo() == rigaWeb)
    }

    @Test("Con la scelta salvata Oggi dice «la tua scelta» con le parole della web",
          arguments: ["formazione-salvata", "formazione-chiusa"])
    func sceltaSalvata(schermata: String) async throws {
        let titoloWeb = try TestiWeb().italiano("oggi.tua_formazione_scelta")
        let tua = try await oggi(try demo(schermata)).formazione?.tuaScelta ?? false
        #expect(TestiOggi.titoloFormazione(tuaScelta: tua) == titoloWeb, "\(schermata)")
    }

    @Test("Il widget dice la tua scelta quando la dice Oggi, prima, durante e dopo la giornata",
          arguments: zip(["oggi", "oggi-in-corso", "oggi-finita"], [LegaDemo.Fase.prima, .inCorso, .finita]))
    func widgetComeOggi(schermata: String, fase: LegaDemo.Fase) async throws {
        let tua = try await oggi(try demo(schermata)).formazione?.tuaScelta ?? false
        let w = try #require(RiassuntoWidget.leggi(LegaDemo.widget(adesso: Self.adesso, fase: fase)), "il widget \(fase) non si legge")
        #expect((w.formazione?.tuaScelta ?? false) == tua, "\(schermata): il widget e Oggi non dicono la stessa cosa sulla tua scelta")
    }
}
