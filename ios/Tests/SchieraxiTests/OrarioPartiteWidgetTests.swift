import Foundation
import Testing
@testable import Schieraxi

/// Il widget «Partite live» e il Cruscotto: accanto a una partita da giocare c'è l'ora, e il giorno quando non è oggi, con le parole
/// della web e di Oggi («domani 11:23», «mar 3 18:30»). Prima si leggeva «11:23» anche per una partita di domani (#249).
/// Le partite in gioco o finite restano come prima («63'», «Intervallo», «Finita»). Squadre e orari inventati.
@Suite("Widget: il giorno delle partite che non sono di oggi")
struct OrarioPartiteWidgetTests {
    /// Sabato 31 ottobre 2026 alle 14:00, ora italiana.
    private func adesso(_ testo: String = "2026-10-31 14:00") throws -> Date { try #require(Quando.data(testo)) }

    private func partita(_ data: String?, stato: String? = "da_giocare", minuto: String? = nil) -> PartitaLive {
        PartitaLive(casa: "genoa", trasferta: "como", data: data, stato: stato, minuto: minuto)
    }

    static let casi: [(String, String)] = [
        ("2026-10-31 20:45", "20:45"),
        ("2026-11-01 11:23", "domani 11:23"),
        ("2026-10-30 20:45", "ieri 20:45"),
        ("2026-11-03 18:30", "mar 3 18:30"),
        ("2026-11-10 20:45", "mar 10 nov 20:45"),
    ]

    @Test("Una partita di oggi ha solo l'ora, le altre anche il giorno", arguments: OrarioPartiteWidgetTests.casi)
    func daGiocare(data: String, atteso: String) throws {
        #expect(partita(data).etichetta(adesso: try adesso()) == atteso)
    }

    @Test("Il giorno cambia a mezzanotte, ora italiana")
    func mezzanotte() throws {
        let p = partita("2026-11-01 00:15")
        #expect(p.etichetta(adesso: try adesso("2026-10-31 23:50")) == "domani 00:15")
        #expect(p.etichetta(adesso: try adesso("2026-11-01 00:05")) == "00:15")
    }

    @Test("Senza stato vale come da giocare; senza data resta il trattino")
    func senzaStatoOData() throws {
        #expect(partita("2026-11-01 11:23", stato: nil).etichetta(adesso: try adesso()) == "domani 11:23")
        #expect(partita(nil).etichetta(adesso: try adesso()) == "—")
    }

    @Test("Le partite in gioco, sospese o finite non cambiano, qualunque sia il giorno")
    func inGiocoOFinite() throws {
        let ora = try adesso()
        #expect(partita("2026-11-01 11:23", stato: "secondo_tempo", minuto: "63'").etichetta(adesso: ora) == "63'")
        #expect(partita("2026-11-01 11:23", stato: "intervallo").etichetta(adesso: ora) == "Intervallo")
        #expect(partita("2026-10-30 20:45", stato: "finita").etichetta(adesso: ora) == "Finita")
        #expect(partita("2026-11-01 11:23", stato: "rinviata").etichetta(adesso: ora) == "Rinviata")
        #expect(partita("2026-11-01 11:23", stato: "sospesa").etichetta(adesso: ora) == "Sospesa")
    }

    @Test("VoiceOver legge lo stesso giorno della scritta")
    func fraseConIlGiorno() throws {
        let frase = partita("2026-11-01 11:23").frase(adesso: try adesso())
        #expect(frase.hasSuffix(", domani 11:23"), "\(frase)")
    }
}
