import UIKit

/// Feedback aptico: solo per azioni significative (salvataggi, errori di un'azione dell'utente, cambi di selezione), mai per un semplice aggiornamento.
enum Haptics {
    static func esito(riuscito: Bool) {
        UINotificationFeedbackGenerator().notificationOccurred(riuscito ? .success : .error)
    }

    static func selezione() {
        UISelectionFeedbackGenerator().selectionChanged()
    }
}
