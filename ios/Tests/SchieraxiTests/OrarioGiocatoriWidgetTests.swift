import Foundation
import Testing
@testable import Schieraxi

/// I widget «Giocatore seguito» e «Chi gioca» (#267): quando gioca un giocatore si scrive con la stessa funzione delle partite
/// dei widget Live e Cruscotto (#258, `PartitaLive.etichetta(adesso:)`): l'ora se è oggi, altrimenti anche il giorno
/// («domani 11:23», «mar 3 18:30»). Prima i due widget scrivevano «11:23» anche per una partita di domani. Dati inventati.
@Suite("Widget Seguito e Chi gioca: il giorno delle partite che non sono di oggi")
struct OrarioGiocatoriWidgetTests {
    /// Sabato 31 ottobre 2026 alle 14:00, ora italiana.
    private func adesso(_ testo: String = "2026-10-31 14:00") throws -> Date { try #require(Quando.data(testo)) }

    private func giocatore(_ data: String?, avversario: String? = "roma", inCasa: Bool = true) -> GiocatoreWidget {
        GiocatoreWidget(id: 31, nome: "Marzio Zaviani", ruolo: "C", puntiAttesi: 6.46, avversario: avversario, inCasa: inCasa,
                        dataPartita: data)
    }

    @Test("Quando gioca: lo stesso testo della partita nel widget Live", arguments: OrarioPartiteWidgetTests.casi)
    func stessoTestoDelLive(data: String, atteso: String) throws {
        let ora = try adesso()
        let partita = PartitaLive(casa: "genoa", trasferta: "como", data: data, stato: "da_giocare")
        #expect(giocatore(data).quandoGioca(adesso: ora) == atteso)
        #expect(giocatore(data).quandoGioca(adesso: ora) == partita.etichetta(adesso: ora))
    }

    @Test("La partita in una riga: con l'avversario, poi solo quando gioca", arguments: [
        ("2026-11-01 11:23", true, ["vs ROM · domani 11:23", "domani 11:23"]),
        ("2026-10-31 20:45", false, ["@ ROM · 20:45", "20:45"]),
        ("2026-11-03 18:30", true, ["vs ROM · mar 3 18:30", "mar 3 18:30"]),
    ])
    func partitaInUnaRiga(data: String, inCasa: Bool, attese: [String]) throws {
        #expect(giocatore(data, inCasa: inCasa).formePartita(adesso: try adesso()) == attese)
    }

    @Test("Senza avversario o senza data resta quello che si sa; senza niente il trattino")
    func datiMancanti() throws {
        let ora = try adesso()
        #expect(giocatore("2026-11-01 11:23", avversario: nil).formePartita(adesso: ora) == ["domani 11:23"])
        #expect(giocatore(nil).formePartita(adesso: ora) == ["vs ROM"])
        #expect(giocatore(nil, avversario: nil).formePartita(adesso: ora) == ["—"])
        #expect(giocatore(nil).quandoGioca(adesso: ora) == "—")
    }

    @Test("La riga del Seguito sulla schermata di blocco si accorcia di pezzi interi")
    func rigaInLinea() throws {
        let forme = giocatore("2026-11-01 11:23").formeInLineaSeguito(adesso: try adesso())
        #expect(forme == ["Zaviani 6,5 · vs ROM · domani 11:23", "Zaviani 6,5 · domani 11:23", "Zaviani 6,5"])
    }

    @Test("Il giorno cambia alla voce della timeline di mezzanotte, ora italiana")
    func mezzanotte() throws {
        let g = giocatore("2026-11-01 00:15")
        let sera = try adesso("2026-10-31 23:50")
        let mezzanotte = try adesso("2026-11-01 00:00")
        #expect(g.quandoGioca(adesso: sera) == "domani 00:15")
        // la voce che il `Fornitore` dei due widget aggiunge dopo la prima (`VociTimeline.istanti`)
        let voce = try #require(VociTimeline.istanti(adesso: sera, scadenza: nil, conConto: false).first)
        #expect(voce == mezzanotte)
        #expect(g.quandoGioca(adesso: voce) == "00:15")
        #expect(g.formePartita(adesso: voce).first == "vs ROM · 00:15")
    }

    @Test("VoiceOver legge la forma intera, con il giorno; nessuna forma ha l'ora senza il giorno")
    func voiceOver() throws {
        let ora = try adesso()
        let g = giocatore("2026-11-01 11:23")
        // `TestoCheEntra` fa leggere a VoiceOver la prima forma
        #expect(g.formePartita(adesso: ora).first == "vs ROM · domani 11:23")
        let tutte = g.formePartita(adesso: ora) + g.formeInLineaSeguito(adesso: ora)
        #expect(tutte.allSatisfy { !$0.contains("11:23") || $0.contains("domani 11:23") }, "\(tutte)")
    }
}
