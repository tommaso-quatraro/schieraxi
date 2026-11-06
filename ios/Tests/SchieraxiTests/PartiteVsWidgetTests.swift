import Foundation
import Testing
@testable import Schieraxi

/// Issue #391: nel widget «Partite live» (e nel Cruscotto) una partita non ancora iniziata si leggeva «NAP – ATA oggi 12:30»: il
/// trattino era il posto vuoto del punteggio. L'app e la web scrivono le partite del turno «NAP vs ATA», prima la squadra di
/// casa (`docs/COERENZA-WEB-IPHONE.md`, «Partite del turno»; il trattino tra le sigle è la forma da non usare, #310), e il giorno
/// dopo «·» come la riga di una partita («ATA vs PAR · oggi 20:45»). Con il punteggio resta il tabellone «INT 2–1 ROM 63'».
/// Le sigle di `ColoriSquadra`, come negli altri test dei widget; orari inventati.
@Suite("Widget Partite live: le partite senza punteggio con «vs», come l'app e la web (#391)")
struct PartiteVsWidgetTests {
    /// Sabato 31 ottobre 2026 alle 14:00, ora italiana.
    private func adesso() throws -> Date { try #require(Quando.data("2026-10-31 14:00")) }

    @Test("Da giocare oggi: «NAP vs ATA · oggi 18:00», poi la forma corta «NAP vs ATA · 18:00»")
    func daGiocareOggi() throws {
        let p = PartitaLive(casa: "napoli", trasferta: "atalanta", data: "2026-10-31 18:00", stato: "da_giocare")
        #expect(p.formeRiga(adesso: try adesso()) == ["NAP vs ATA · oggi 18:00", "NAP vs ATA · 18:00"])
    }

    @Test("Un altro giorno il giorno non si toglie: «GEN vs COM · domani 12:30»")
    func daGiocareDomani() throws {
        let p = PartitaLive(casa: "genoa", trasferta: "como", data: "2026-11-01 12:30", stato: "da_giocare")
        #expect(p.formeRiga(adesso: try adesso()) == ["GEN vs COM · domani 12:30"])
    }

    @Test("Senza punteggio tra le sigle c'è «vs», mai il trattino", arguments: ["da_giocare", "rinviata", "finita", nil] as [String?])
    func senzaTrattino(stato: String?) throws {
        let p = PartitaLive(casa: "bologna", trasferta: "torino", data: "2026-10-31 15:00", stato: stato)
        #expect(p.traLeSigle == "vs")
        #expect(p.squadre == "BOL vs TOR")
        let forme = p.formeRiga(adesso: try adesso())
        #expect(!forme.isEmpty)
        for f in forme {
            #expect(f.hasPrefix("BOL vs TOR"), "\(f)")
            #expect(!f.contains("–"), "trattino tra le sigle: \(f)")
        }
    }

    @Test("Con il punteggio resta il tabellone: «INT 2–1 ROM 63'», «MIL 0–0 JUV Intervallo»")
    func conPunteggio() throws {
        let ora = try adesso()
        let inGioco = PartitaLive(casa: "inter", trasferta: "roma", data: "2026-10-31 12:30", stato: "secondo_tempo", minuto: "63'",
                                  golCasa: 2, golTrasferta: 1)
        #expect(inGioco.traLeSigle == "2–1")
        #expect(inGioco.formeRiga(adesso: ora) == ["INT 2–1 ROM 63'"])
        let intervallo = PartitaLive(casa: "milan", trasferta: "juventus", data: "2026-10-31 13:00", stato: "intervallo",
                                     golCasa: 0, golTrasferta: 0)
        #expect(intervallo.formeRiga(adesso: ora) == ["MIL 0–0 JUV Intervallo"])
    }

    @Test("Senza data restano le squadre, senza il trattino del dato che manca: «NAP vs ATA»")
    func senzaData() throws {
        let p = PartitaLive(casa: "napoli", trasferta: "atalanta", data: nil, stato: "da_giocare")
        #expect(p.formeRiga(adesso: try adesso()) == ["NAP vs ATA"])
    }
}
