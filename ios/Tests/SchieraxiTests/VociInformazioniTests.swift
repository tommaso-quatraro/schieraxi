import Foundation
import Testing
@testable import Schieraxi

/// Impostazioni > Informazioni: con un server vero le tre pagine del server si aprono nel browser, come sulla web
/// (`legale.privacy`, `legale.termini`, `legale.crediti` del catalogo comune). Nella prova con dati di esempio (e nelle foto, che
/// usano la stessa demo) non c'è un server da aprire: resta solo «Crediti e fonti», letta dentro l'app.
@Suite("Impostazioni > Informazioni: le voci")
struct VociInformazioniTests {
    @Test("Con un server vero: Privacy, Termini d'uso e Crediti e fonti nel browser, nell'ordine della web")
    func serverVeroApreLeTrePagineNelBrowser() throws {
        let voci = InformazioniLegali.vociInformazioni(prova: false, server: "https://schieraxi.example/")
        let privacy = try #require(URL(string: "https://schieraxi.example/privacy"))
        let termini = try #require(URL(string: "https://schieraxi.example/termini"))
        let crediti = try #require(URL(string: "https://schieraxi.example/crediti"))
        #expect(voci == [.browser(.privacy, privacy), .browser(.termini, termini), .browser(.crediti, crediti)])
        #expect(voci.map(\.titolo) == [Catalogo.Legale.privacy, Catalogo.Legale.termini, Catalogo.Legale.crediti])
    }

    @Test("Nella prova: solo «Crediti e fonti» dentro l'app, nessun collegamento verso un server finto")
    func provaMostraICreditiDentroLApp() {
        let voci = InformazioniLegali.vociInformazioni(prova: true, server: "https://server-demo.invalid:443")
        #expect(voci == [.creditiNellApp])
        #expect(voci.map(\.titolo) == [Catalogo.Legale.crediti])
    }
}
