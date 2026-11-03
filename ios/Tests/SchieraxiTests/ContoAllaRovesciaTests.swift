import Foundation
import Testing
@testable import Schieraxi

/// Il conto alla rovescia alla scadenza come la web (`testoConto` di `fanta/web/app.js`): i minuti che mancano, arrotondati
/// come `Math.round`; «2 giorni 3 h», «6 h 44 min», «12 min»; mai i secondi («6:44:45») né «3 giorni e 3 h».
/// Lo stesso testo in Oggi, nella barra sotto le schede e nei widget (`docs/COERENZA-WEB-IPHONE.md`, «Stato della giornata»).
@Suite("Conto alla rovescia come la web")
struct ContoAllaRovesciaTests {
    /// La scadenza delle prove: sabato 31 ottobre 2026, 15:00 (ora italiana).
    private func scadenza() throws -> Date { try #require(Quando.data("2026-10-31 15:00")) }

    /// Secondi che mancano alla scadenza e testo atteso (la web: `${h} h ${m} min`, `oggi.giorni_ore`, `${m} min`).
    static let casi: [(Double, String)] = [
        (24_240, "6 h 44 min"),
        (24_269, "6 h 44 min"),
        (24_285, "6 h 45 min"),
        (3_600, "1 h 0 min"),
        (3_540, "59 min"),
        (720, "12 min"),
        (31, "1 min"),
        (270_000, "3 giorni 3 h"),
        (273_540, "3 giorni 3 h"),
        (97_200, "1 giorno 3 h"),
        (172_800, "2 giorni 0 h"),
        (86_370, "1 giorno 0 h"),
        (86_369, "23 h 59 min"),
    ]

    @Test("Giorni e ore, ore e minuti, solo minuti", arguments: ContoAllaRovesciaTests.casi)
    func comeLaWeb(secondi: Double, atteso: String) throws {
        let fine = try scadenza()
        #expect(Quando.contoAllaRovescia(fino: fine, adesso: fine.addingTimeInterval(-secondi)) == atteso)
    }

    @Test("Scadenza passata o a meno di mezzo minuto: niente conto (la web scrive «Chiusa»)", arguments: [29.0, 0, -60, -86400])
    func chiusa(secondi: Double) throws {
        let fine = try scadenza()
        #expect(Quando.contoAllaRovescia(fino: fine, adesso: fine.addingTimeInterval(-secondi)) == nil)
    }

    @Test("Mai i secondi né la «e» tra giorni e ore")
    func senzaSecondiNeE() throws {
        let fine = try scadenza()
        for secondi in stride(from: 31.0, through: 4 * 86400, by: 3917) {
            let testo = try #require(Quando.contoAllaRovescia(fino: fine, adesso: fine.addingTimeInterval(-secondi)))
            #expect(!testo.contains(":"), "\(testo)")
            #expect(!testo.contains(" e "), "\(testo)")
        }
    }

    @Test("Giorni e ore con le parole della web (`oggi.giorni_ore` di testi.js)", arguments: [1, 3])
    func giorniOreDellaWeb(giorni: Int) throws {
        let web = try TestiWeb()
        let chiave = giorni == 1 ? "oggi.giorni_ore.one" : "oggi.giorni_ore.other"
        let atteso = try web.italiano(chiave).replacingOccurrences(of: "{n}", with: "\(giorni)").replacingOccurrences(of: "{h}", with: "5")
        let fine = try scadenza()
        let secondi = Double(giorni) * 86400 + 5 * 3600 + 10 * 60
        #expect(Quando.contoAllaRovescia(fino: fine, adesso: fine.addingTimeInterval(-secondi)) == atteso)
    }

    /// Lo stesso conto a voce, con le parole intere.
    static let casiAVoce: [(Double, String)] = [
        (24_240, "6 ore e 44 minuti"),
        (21_600, "6 ore"),
        (3_660, "1 ora e 1 minuto"),
        (720, "12 minuti"),
        (183_600, "2 giorni e 3 ore"),
        (87_600, "1 giorno"),
    ]

    @Test("A voce (VoiceOver): parole intere", arguments: ContoAllaRovesciaTests.casiAVoce)
    func aVoce(secondi: Double, atteso: String) throws {
        let fine = try scadenza()
        #expect(Quando.contoAllaRovesciaParlato(fino: fine, adesso: fine.addingTimeInterval(-secondi)) == atteso)
        #expect(Quando.contoAllaRovesciaParlato(fino: fine, adesso: fine) == nil)
    }

    // MARK: istanti del widget

    /// Il widget non può contare da solo un testo come «6 h 44 min»: ogni cambio è una voce della timeline (non una ricarica).

    @Test("Sotto le 24 ore: una voce per ogni minuto, sempre con un testo nuovo")
    func ogniMinuto() throws {
        let fine = try scadenza()
        let adesso = fine.addingTimeInterval(-(6 * 3600 + 44 * 60))
        let istanti = Quando.istantiDelConto(fino: fine, adesso: adesso, entro: adesso.addingTimeInterval(3600))
        #expect(istanti.count == 59)
        #expect(istanti.first == adesso.addingTimeInterval(60))
        #expect(istanti == istanti.sorted())
        #expect(istanti.allSatisfy { $0 > adesso && $0 < adesso.addingTimeInterval(3600) })
        let testi = istanti.compactMap { Quando.contoAllaRovescia(fino: fine, adesso: $0) }
        #expect(testi.first == "6 h 43 min")
        #expect(Set(testi).count == istanti.count, "ogni voce cambia il testo")
    }

    @Test("Sopra le 24 ore il testo cambia solo con l'ora: una voce sola nell'ora dopo")
    func ogniOra() throws {
        let fine = try scadenza()
        let adesso = fine.addingTimeInterval(-(3 * 86400 + 3 * 3600 + 10 * 60))
        let istanti = Quando.istantiDelConto(fino: fine, adesso: adesso, entro: adesso.addingTimeInterval(3600))
        #expect(istanti == [adesso.addingTimeInterval(11 * 60)])
        #expect(Quando.contoAllaRovescia(fino: fine, adesso: adesso) == "3 giorni 3 h")
        #expect(istanti.first.flatMap { Quando.contoAllaRovescia(fino: fine, adesso: $0) } == "3 giorni 2 h")
    }

    @Test("La mezzanotte è una voce: lì «domani» diventa «oggi»")
    func mezzanotte() throws {
        let fine = try #require(Quando.data("2026-10-31 15:00")).addingTimeInterval(30)
        let adesso = try #require(Quando.data("2026-10-30 23:50"))
        let notte = try #require(Quando.data("2026-10-31 00:00"))
        let istanti = Quando.istantiDelConto(fino: fine, adesso: adesso, entro: adesso.addingTimeInterval(3600))
        #expect(istanti.contains(notte))
        #expect(istanti.count == 61)
        #expect(istanti == istanti.sorted())
    }

    @Test("Mai oltre la scadenza (ha già la sua voce) né oltre il tetto")
    func limiti() throws {
        let fine = try scadenza()
        let vicino = fine.addingTimeInterval(-10 * 60)
        let fino = Quando.istantiDelConto(fino: fine, adesso: vicino, entro: vicino.addingTimeInterval(3600))
        #expect(fino.count == 9)
        #expect(fino.allSatisfy { $0 < fine })
        let lontano = fine.addingTimeInterval(-5 * 3600)
        #expect(Quando.istantiDelConto(fino: fine, adesso: lontano, entro: lontano.addingTimeInterval(4 * 3600), massimo: 90).count == 90)
        #expect(Quando.istantiDelConto(fino: fine, adesso: fine, entro: fine.addingTimeInterval(3600)).isEmpty)
        #expect(Quando.istantiDelConto(fino: fine, adesso: lontano, entro: lontano).isEmpty)
    }
}
