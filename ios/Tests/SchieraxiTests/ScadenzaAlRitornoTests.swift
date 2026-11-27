import Foundation
import Testing
@testable import Schieraxi

/// La Formazione rilegge la giornata 5 secondi dopo la scadenza, e diventa di sola lettura (`FormazioneView`). Quel lavoro si ferma
/// quando l'app non è più attiva: se l'app era fuori alla scadenza e si tornava entro 10 minuti (prima che la porta ricarichi tutto,
/// `DatiVecchi.serveAggiornareAlRitorno`), la rilettura saltava, la Formazione sembrava modificabile e il primo cambio riceveva
/// «La formazione è chiusa». Ora tornando si rilegge subito. Ore inventate, a metà giornata.
@Suite("Formazione: tornando nell'app dopo la scadenza si rilegge")
struct ScadenzaAlRitornoTests {
    private static let scadenza = Date(timeIntervalSince1970: 1_795_000_000)

    /// `secondi` dopo la scadenza (prima, se negativo).
    private func t(_ secondi: TimeInterval) -> Date { Self.scadenza.addingTimeInterval(secondi) }

    @Test("Fuori quando toccava rileggere, di ritorno prima che la porta ricarichi tutto: si rilegge subito")
    func fuoriAllaScadenza() {
        #expect(DatiVecchi.rileggiPerLaScadenza(Self.scadenza, fuoriDal: t(-60), inBackgroundDal: t(-59), adesso: t(120)))
        // solo il Centro di controllo, senza andare in secondo piano: anche lì il lavoro della scadenza si era fermato
        #expect(DatiVecchi.rileggiPerLaScadenza(Self.scadenza, fuoriDal: t(-10), inBackgroundDal: nil, adesso: t(30)))
        // uscito fra la scadenza e la rilettura di 5 secondi dopo
        #expect(DatiVecchi.rileggiPerLaScadenza(Self.scadenza, fuoriDal: t(2), inBackgroundDal: t(3), adesso: t(60)))
        // di ritorno poco prima che la porta ricarichi tutto
        #expect(DatiVecchi.rileggiPerLaScadenza(Self.scadenza, fuoriDal: t(-60), inBackgroundDal: t(-59),
                                                adesso: t(-59 + DatiVecchi.sogliaRitorno - 1)))
    }

    @Test("Negli altri casi no: aspetta il lavoro della scadenza, la rilettura c'era già, o la porta ricarica tutto")
    func altriCasi() {
        // di ritorno prima della rilettura: il lavoro della scadenza riparte e la fa lui
        #expect(!DatiVecchi.rileggiPerLaScadenza(Self.scadenza, fuoriDal: t(-60), inBackgroundDal: t(-59), adesso: t(-30)))
        #expect(!DatiVecchi.rileggiPerLaScadenza(Self.scadenza, fuoriDal: t(-60), inBackgroundDal: t(-59), adesso: t(3)))
        // uscito dopo la rilettura: si vedeva già la formazione chiusa
        #expect(!DatiVecchi.rileggiPerLaScadenza(Self.scadenza, fuoriDal: t(30), inBackgroundDal: t(31), adesso: t(120)))
        // fuori da 10 minuti o più: la porta manda già «Aggiorna» a tutte le schermate
        #expect(!DatiVecchi.rileggiPerLaScadenza(Self.scadenza, fuoriDal: t(-60), inBackgroundDal: t(-59),
                                                 adesso: t(-59 + DatiVecchi.sogliaRitorno)))
        // nessuna scadenza nota, o l'app non era uscita
        #expect(!DatiVecchi.rileggiPerLaScadenza(nil, fuoriDal: t(-60), inBackgroundDal: t(-59), adesso: t(120)))
        #expect(!DatiVecchi.rileggiPerLaScadenza(Self.scadenza, fuoriDal: nil, inBackgroundDal: nil, adesso: t(120)))
    }
}
