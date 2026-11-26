import Foundation
import Testing
import UserNotifications
@testable import Schieraxi

/// I promemoria suonano all'ora della scadenza italiana anche con il telefono in un altro fuso (26/11/2026). Prima l'app li
/// fissava con giorno, ora e minuto senza fuso: iOS li legge nell'ora del telefono, quindi chi li programmava in Italia e poi
/// cambiava fuso (o li programmava all'estero e poi tornava) li riceveva ore prima o dopo. Ora l'attesa si conta in secondi da
/// adesso (`Notifiche.attivazione`): lo stesso istante in ogni fuso.
@Suite("Promemoria all'ora giusta anche all'estero")
struct PromemoriaFusoTests {
    private let nome = NomeGiornata(serieA: 13, lega: 10)

    /// L'istante in cui il calendario di un telefono nel `fuso` indicato segna quel giorno di novembre 2026 a quell'ora.
    private func orologio(_ fuso: String, giorno: Int, ore: Int, minuti: Int = 0) throws -> Date {
        var calendario = Calendar(identifier: .gregorian)
        calendario.timeZone = try #require(TimeZone(identifier: fuso))
        return try #require(calendario.date(from: DateComponents(year: 2026, month: 11, day: giorno, hour: ore, minute: minuti)))
    }

    @Test("Telefono in un altro fuso: i promemoria della scadenza delle 21:45 italiane suonano un'ora e un quarto d'ora prima",
          arguments: zip(["America/New_York", "Asia/Tokyo", "Europe/London", "Europe/Rome"], [14, 4, 19, 20]))
    func altroFuso(fuso: String, oraDelTelefono: Int) throws {
        let scadenza = try #require(Quando.data("2026-11-29 21:45"))          // ora italiana
        // le 20:00 in Italia, lette dall'orologio del telefono (le 4 di Tokyo sono già il 30 novembre)
        let adesso = try orologio(fuso, giorno: fuso == "Asia/Tokyo" ? 30 : 29, ore: oraDelTelefono)
        let venti = try #require(Quando.data("2026-11-29 20:00"))
        #expect(adesso == venti)
        let elenco = Notifiche.promemoriaDaProgrammare(giornata: nome, inizio: scadenza, testi: nil, lettaIl: nil, ore: .predefinite,
                                                       attivi: [60, 15], tace: false, dalServer: false, adesso: adesso)
        #expect(elenco.map(\.id) == ["fanta-60", "fanta-15"])
        let attese: [UNTimeIntervalNotificationTrigger] = elenco.map { Notifiche.attivazione(per: $0.quando, adesso: adesso) }
        let secondi: [TimeInterval] = attese.map(\.timeInterval)
        let attesi: [TimeInterval] = [2700, 5400]          // 45 minuti: alle 20:45 italiane; 90 minuti: alle 21:30
        #expect(secondi == attesi)
        let ripetute: Bool = attese.contains { $0.repeats }
        #expect(!ripetute)
    }

    @Test("Un promemoria il cui momento è appena passato suona subito: iOS non accetta un'attesa nulla")
    func appenaPassato() {
        let adesso = Date(timeIntervalSince1970: 1_795_000_000)
        let passato: TimeInterval = Notifiche.attivazione(per: adesso.addingTimeInterval(-0.5), adesso: adesso).timeInterval
        let traUnOra: TimeInterval = Notifiche.attivazione(per: adesso.addingTimeInterval(3600), adesso: adesso).timeInterval
        #expect(passato == 1)
        #expect(traUnOra == 3600)
    }
}
