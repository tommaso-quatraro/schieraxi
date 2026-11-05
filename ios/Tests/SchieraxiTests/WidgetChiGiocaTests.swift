import Foundation
import Testing
@testable import Schieraxi

/// Il widget «Chi gioca» (#194): l'ora della partita si scrive una volta sola, a destra e con il giorno come la web («oggi 18:30»,
/// «domani 18:30»; stessa funzione delle partite del widget Live, #267); sotto
/// il nome l'avversario e le parole di ogni avviso. Ogni colore e ogni segno ha la sua parola: la riga arancione dice perché
/// («Diffidato», «In dubbio · gioca 70%»), il rigorista è scritto («Rigorista») e non solo un simbolo. Dati inventati.
@Suite("Widget «Chi gioca»")
struct WidgetChiGiocaTests {
    private static let partita = "2026-11-08 18:30"

    private func giocatore(pVoto: Double = 0.96, inCasa: Bool = true, stato: String = "titolare", dubbio: Bool? = nil,
                           diffidato: Bool? = nil, rigorista: Bool? = nil) -> GiocatoreWidget {
        GiocatoreWidget(id: 105, nome: "Fabio Dimarzi", ruolo: "D", pVoto: pVoto, avversario: inCasa ? "roma" : "milan", inCasa: inCasa,
                        dataPartita: Self.partita, stato: stato, percentuale: 90, dubbio: dubbio, diffidato: diffidato,
                        titolare: true, rigorista: rigorista)
    }

    @Test("Sotto il nome solo l'avversario: l'ora sta a destra, una volta sola")
    func oraUnaVoltaSola() {
        #expect(giocatore().formeChiGioca == ["vs ROM"])
        #expect(giocatore(inCasa: false).formeChiGioca == ["@ MIL"])
        #expect(!giocatore().formeChiGioca.contains { $0.contains("18:30") })
    }

    @Test("Ogni avviso ha la sua parola; l'arancione solo se c'è da guardare", arguments: [
        (Avviso.dubbio, "vs ROM · In dubbio · gioca 70%", true),
        (Avviso.diffidato, "vs ROM · Diffidato", true),
        (Avviso.rigorista, "vs ROM · Rigorista", false),
        (Avviso.diffidatoERigorista, "vs ROM · Diffidato · Rigorista", true),
        (Avviso.infortunato, "vs ROM · Infortunato", true),
    ])
    func paroleDegliAvvisi(avviso: Avviso, riga: String, daGuardare: Bool) {
        let g: GiocatoreWidget
        switch avviso {
        case .dubbio: g = giocatore(pVoto: 0.7, dubbio: true)
        case .diffidato: g = giocatore(diffidato: true)
        case .rigorista: g = giocatore(rigorista: true)
        case .diffidatoERigorista: g = giocatore(diffidato: true, rigorista: true)
        case .infortunato: g = giocatore(pVoto: 0, stato: "infortunato")
        }
        #expect(g.formeChiGioca.first == riga)
        #expect(g.daGuardare == daGuardare)
    }

    @Test("Se non entra, prima via l'avversario, poi resta «gioca 70%»: mai una parola tagliata")
    func formePiuCorte() {
        #expect(giocatore(pVoto: 0.7, dubbio: true).formeChiGioca == ["vs ROM · In dubbio · gioca 70%", "In dubbio · gioca 70%", "gioca 70%"])
        #expect(giocatore(diffidato: true).formeChiGioca == ["vs ROM · Diffidato", "Diffidato"])
    }

    /// Con la funzione delle partite del widget Live (#258, #267).
    @Test("A destra quando gioca, con il giorno come la web", arguments: [
        ("2026-11-08 10:00", "oggi 18:30"),
        ("2026-11-07 22:00", "domani 18:30"),
        ("2026-11-06 22:00", "dom 8 18:30"),
    ])
    func quandoGioca(adesso: String, atteso: String) throws {
        let momento = try #require(Quando.data(adesso))
        #expect(giocatore().quandoGioca(adesso: momento) == atteso)
    }

    @Test("Se a destra non c'è posto, una partita di oggi resta con la sola ora; le altre tengono il giorno")
    func quandoGiocaCorto() throws {
        #expect(giocatore().formeQuandoGioca(adesso: try #require(Quando.data("2026-11-08 10:00"))) == ["oggi 18:30", "18:30"])
        #expect(giocatore().formeQuandoGioca(adesso: try #require(Quando.data("2026-11-07 22:00"))) == ["domani 18:30"])
    }

    @Test("Senza la partita: un trattino a destra, niente riga vuota sotto il nome")
    func senzaPartita() throws {
        let g = GiocatoreWidget(id: 1, nome: "Ivo Sorvani", ruolo: "P")
        let momento = try #require(Quando.data("2026-11-08 10:00"))
        #expect(g.quandoGioca(adesso: momento) == "—")
        #expect(g.formeChiGioca.isEmpty)
    }

    enum Avviso: CaseIterable, Sendable { case dubbio, diffidato, rigorista, diffidatoERigorista, infortunato }
}
