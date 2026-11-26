import Foundation
import Testing
@testable import Schieraxi

/// «Da controllare» nei widget (26/11/2026): `/api/widget` manda al più 6 avvisi e il widget contava i titolari su quei sei; con tanti
/// infortunati fuori formazione il numero era sbagliato. Ora il server manda il conto in `da_controllare` (contato su tutti gli avvisi)
/// e i widget mostrano quello, senza contare. Con un server di prima, senza il campo, si contano quelli arrivati come prima.
/// Nomi inventati.
@Suite("Il numero di «Da controllare» viene dal server")
struct ContoDaControllareWidgetTests {
    /// Un avviso di un titolare (`in_formazione`) o di un altro della rosa.
    private func avviso(_ id: Int, titolare: Bool) -> String {
        #"{"id": \#(id), "nome": "Giocatore\#(id)", "ruolo": "C", "tipo": "dubbio", "in_formazione": \#(titolare)}"#
    }

    private func widget(_ avvisi: [String], altro: String = "") throws -> RiassuntoWidget {
        let corpo = #"{"giornata": 11, "avvisi": [\#(avvisi.joined(separator: ","))]\#(altro)}"#
        return try #require(RiassuntoWidget.leggi(Data(corpo.utf8)))
    }

    @Test("Il conto del server vale anche oltre i sei avvisi arrivati")
    func contoDelServer() throws {
        let w = try widget((1...6).map { avviso($0, titolare: true) }, altro: #", "da_controllare": 8"#)
        #expect(w.daControllare.count == 6, "i nomi sono quelli arrivati")
        #expect(w.contoDaControllare == 8)
        let r = try #require(w.comeRiassuntoOggi())
        #expect(r.daControllare == 8, "anche Prossima giornata e Da controllare, che leggono il riassunto")
        #expect(r.dubbi?.count == 6)
    }

    @Test("Il widget non conta da sé: vale il numero del server anche se i titolari arrivati sono di meno")
    func nienteContoNelWidget() throws {
        let w = try widget([avviso(1, titolare: true), avviso(2, titolare: false)], altro: #", "da_controllare": 3"#)
        #expect(w.contoDaControllare == 3)
    }

    @Test("Senza il campo (server di prima) o con un valore strano si contano i titolari arrivati", arguments: ["", #", "da_controllare": "tre""#,
                                                                                                                  #", "da_controllare": -1"#])
    func senzaIlCampo(altro: String) throws {
        let w = try widget([avviso(1, titolare: true), avviso(2, titolare: false), avviso(3, titolare: true)], altro: altro)
        #expect(w.contoDaControllare == 2)
        #expect(w.comeRiassuntoOggi()?.daControllare == 2)
    }

    @Test("A formazione chiusa niente «Da controllare», anche con il conto del server")
    func formazioneChiusa() throws {
        let w = try widget([avviso(1, titolare: true)], altro: #", "da_controllare": 4, "fase": "in_corso""#)
        #expect(w.contoDaControllare == 0)
        #expect(w.comeRiassuntoOggi()?.daControllare == 0)
    }
}
