import Observation

/// Il tocco su un avviso dell'app aspetta qui che l'app lo prenda (`DelegatoAvvisi`): anche quando è il tocco ad aprire l'app e le
/// schermate non ci sono ancora. L'app lo prende appena può (`toccoSugliAvvisi`) e va dove porta, una volta sola.
@MainActor
@Observable
final class AvvisiToccati {
    static let condiviso = AvvisiToccati()

    /// Dove porta l'ultimo tocco, finché l'app non ci va (`consegna`).
    private(set) var destinazione: Destinazione?

    /// Un avviso toccato: se porta da qualche parte (`Notifiche.destinazione`), la destinazione aspetta l'app.
    func tocca(identificativo: String) {
        guard let destinazione = Notifiche.destinazione(identificativo: identificativo) else { return }
        self.destinazione = destinazione
    }

    /// Porta la navigazione dove dice l'ultimo tocco (come un indirizzo `schieraxi://`, `Navigazione.vai`) e lo dimentica.
    func consegna(a nav: Navigazione) {
        guard let destinazione else { return }
        self.destinazione = nil
        nav.vai(a: destinazione)
    }
}
