import Foundation
import Testing
@testable import Schieraxi

/// Gli istanti della timeline del widget dopo la prima voce: il conto alla rovescia, la scadenza e la mezzanotte (ora italiana).
/// Di notte iOS può rimandare le ricariche di ore: senza una voce a mezzanotte «domani 12:30» calcolato sabato alle 23:50 resterebbe
/// scritto anche domenica mattina (#249, revisione della PR #258). Le voci non consumano il limite di ricariche di iOS. Date inventate.
@Suite("Widget: le voci della timeline, mezzanotte compresa")
struct VociTimelineWidgetTests {
    private func data(_ testo: String) throws -> Date { try #require(Quando.data(testo)) }

    @Test("Senza scadenza resta solo la mezzanotte che viene, in ora italiana")
    func soloMezzanotte() throws {
        let istanti = VociTimeline.istanti(adesso: try data("2026-10-31 23:50"), scadenza: nil, conConto: true)
        #expect(istanti == [try data("2026-11-01 00:00")])
    }

    @Test("Con la scadenza domani sera: prima la mezzanotte, poi la scadenza")
    func mezzanotteEScadenza() throws {
        let istanti = VociTimeline.istanti(adesso: try data("2026-10-31 23:50"), scadenza: try data("2026-11-01 20:45"), conConto: false)
        #expect(istanti == [try data("2026-11-01 00:00"), try data("2026-11-01 20:45")])
    }

    @Test("Con il conto alla rovescia la mezzanotte c'è una volta sola e gli istanti sono in ordine")
    func contoEMezzanotte() throws {
        let adesso = try data("2026-10-31 23:30")
        let scadenza = try data("2026-11-01 00:20")
        let istanti = VociTimeline.istanti(adesso: adesso, scadenza: scadenza, conConto: true)
        let mezzanotte = try data("2026-11-01 00:00")
        #expect(istanti.filter { $0 == mezzanotte }.count == 1)
        #expect(istanti == istanti.sorted())
        #expect(Set(istanti).count == istanti.count)
        #expect(istanti.last == scadenza)
        #expect(istanti.allSatisfy { $0 > adesso })
        // i minuti del conto ci sono (uno per ogni cambio del testo nell'ora che viene)
        #expect(istanti.count > 20)
    }

    @Test("Senza conto: niente minuti, solo mezzanotte e scadenza")
    func senzaConto() throws {
        let istanti = VociTimeline.istanti(adesso: try data("2026-10-31 14:00"), scadenza: try data("2026-10-31 14:30"), conConto: false)
        #expect(istanti == [try data("2026-10-31 14:30"), try data("2026-11-01 00:00")])
    }

    @Test("A scadenza passata niente voce della scadenza né del conto")
    func scadenzaPassata() throws {
        let istanti = VociTimeline.istanti(adesso: try data("2026-10-31 21:00"), scadenza: try data("2026-10-31 20:45"), conConto: true)
        #expect(istanti == [try data("2026-11-01 00:00")])
    }

    @Test("Alle 00:00 in punto la mezzanotte che viene è quella dopo")
    func aMezzanotte() throws {
        let istanti = VociTimeline.istanti(adesso: try data("2026-11-01 00:00"), scadenza: nil, conConto: false)
        #expect(istanti == [try data("2026-11-02 00:00")])
    }
}
