import Foundation
import Testing
@testable import Schieraxi

/// I widget «Giocatore seguito» e «Chi gioca» (#267): quando gioca un giocatore si scrive con la stessa funzione delle partite
/// dei widget Live e Cruscotto (`PartitaLive.orari`): il giorno e l'ora come la web («oggi 20:45», «domani 11:23»,
/// «mar 3 18:30»). Dove lo spazio non basta una partita di oggi ripiega sulla sola ora («20:45»), mai quelle degli altri giorni.
/// Prima i due widget scrivevano «11:23» anche per una partita di domani. Dati inventati.
@Suite("Widget Seguito e Chi gioca: il giorno delle partite")
struct OrarioGiocatoriWidgetTests {
    /// Sabato 31 ottobre 2026 alle 14:00, ora italiana.
    private func adesso(_ testo: String = "2026-10-31 14:00") throws -> Date { try #require(Quando.data(testo)) }

    private func giocatore(_ data: String?, avversario: String? = "roma", inCasa: Bool = true) -> GiocatoreWidget {
        GiocatoreWidget(id: 31, nome: "Marzio Zaviani", ruolo: "C", puntiAttesi: 6.46, avversario: avversario, inCasa: inCasa,
                        dataPartita: data)
    }

    @Test("Quando gioca: lo stesso testo, e le stesse forme corte, della partita nel widget Live",
          arguments: OrarioPartiteWidgetTests.casi)
    func stessoTestoDelLive(data: String, atteso: String) throws {
        let ora = try adesso()
        let partita = PartitaLive(casa: "genoa", trasferta: "como", data: data, stato: "da_giocare")
        #expect(giocatore(data).quandoGioca(adesso: ora) == atteso)
        #expect(giocatore(data).quandoGioca(adesso: ora) == partita.etichetta(adesso: ora))
        #expect(giocatore(data).formeQuandoGioca(adesso: ora) == partita.formeEtichetta(adesso: ora))
    }

    @Test("La partita in una riga: con l'avversario, poi senza «oggi», poi solo quando gioca", arguments: [
        ("2026-11-01 11:23", true, ["vs ROM · domani 11:23", "domani 11:23"]),
        ("2026-10-31 20:45", false, ["@ ROM · oggi 20:45", "@ ROM · 20:45", "20:45"]),
        ("2026-11-03 18:30", true, ["vs ROM · mar 3 18:30", "mar 3 18:30"]),
    ])
    func partitaInUnaRiga(data: String, inCasa: Bool, attese: [String]) throws {
        #expect(giocatore(data, inCasa: inCasa).formePartita(adesso: try adesso()) == attese)
    }

    @Test("Senza avversario o senza data resta quello che si sa; senza niente il trattino")
    func datiMancanti() throws {
        let ora = try adesso()
        #expect(giocatore("2026-11-01 11:23", avversario: nil).formePartita(adesso: ora) == ["domani 11:23"])
        #expect(giocatore("2026-10-31 20:45", avversario: nil).formePartita(adesso: ora) == ["oggi 20:45", "20:45"])
        #expect(giocatore(nil).formePartita(adesso: ora) == ["vs ROM"])
        #expect(giocatore(nil, avversario: nil).formePartita(adesso: ora) == ["—"])
        #expect(giocatore(nil).quandoGioca(adesso: ora) == "—")
        #expect(giocatore(nil).formeQuandoGioca(adesso: ora) == ["—"])
    }

    @Test("La riga del Seguito sulla schermata di blocco si accorcia di pezzi interi", arguments: [
        ("2026-11-01 11:23", ["Zaviani 6,5 · vs ROM · domani 11:23", "Zaviani 6,5 · domani 11:23", "Zaviani 6,5"]),
        ("2026-10-31 20:45", ["Zaviani 6,5 · vs ROM · oggi 20:45", "Zaviani 6,5 · vs ROM · 20:45", "Zaviani 6,5 · 20:45", "Zaviani 6,5"]),
    ])
    func rigaInLinea(data: String, attese: [String]) throws {
        #expect(giocatore(data).formeInLineaSeguito(adesso: try adesso()) == attese)
    }

    @Test("La riga di Chi gioca sulla schermata di blocco: via l'ora (oggi via «oggi»), poi resta il cognome", arguments: [
        ("2026-11-01 11:23", ["Zaviani domani 11:23", "Zaviani domani", "Zaviani"]),
        ("2026-10-31 20:45", ["Zaviani oggi 20:45", "Zaviani 20:45", "Zaviani"]),
        ("2026-11-10 20:45", ["Zaviani mar 10 nov 20:45", "Zaviani mar 10 nov", "Zaviani"]),
    ])
    func rigaInLineaChiGioca(data: String, attese: [String]) throws {
        let forme = giocatore(data).formeInLineaChiGioca(adesso: try adesso())
        #expect(forme == attese)
        // VoiceOver legge la prima (`RigaInLinea`): sempre intera, con il giorno e l'ora di quando gioca
        #expect(forme.first == "Zaviani \(giocatore(data).quandoGioca(adesso: try adesso()))")
    }

    @Test("Senza la partita la riga di Chi gioca ha solo il cognome")
    func rigaInLineaChiGiocaSenzaData() throws {
        #expect(giocatore(nil).formeInLineaChiGioca(adesso: try adesso()) == ["Zaviani"])
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
        #expect(g.quandoGioca(adesso: voce) == "oggi 00:15")
        #expect(g.formePartita(adesso: voce).first == "vs ROM · oggi 00:15")
    }

    @Test("VoiceOver legge la forma intera, con il giorno; un altro giorno non perde mai il giorno")
    func voiceOver() throws {
        let ora = try adesso()
        let domani = giocatore("2026-11-01 11:23")
        // `TestoCheEntra` e `RigaInLinea` fanno leggere a VoiceOver la prima forma
        #expect(domani.formePartita(adesso: ora).first == "vs ROM · domani 11:23")
        #expect(giocatore("2026-10-31 20:45").formePartita(adesso: ora).first == "vs ROM · oggi 20:45")
        let tutte = domani.formePartita(adesso: ora) + domani.formeInLineaSeguito(adesso: ora) + domani.formeQuandoGioca(adesso: ora)
            + domani.formeInLineaChiGioca(adesso: ora)
        #expect(tutte.allSatisfy { !$0.contains("11:23") || $0.contains("domani 11:23") }, "\(tutte)")
    }
}
