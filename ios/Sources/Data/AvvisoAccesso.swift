import Foundation

/// Una frase da mostrare una volta sulla schermata di accesso, con il suo tipo: la web la scrive con `mostraMessaggioAccesso`.
struct AvvisoAccesso: Equatable {
    enum Tipo: Equatable {
        /// È andata come voleva l'utente (uscita da tutti i dispositivi, account eliminato, codice inviato, password cambiata):
        /// verde, con il segno di spunta.
        case conferma
        /// Qualcosa che l'utente non ha chiesto, come la sessione chiusa dal server: il colore «attenzione» con l'icona d'avviso,
        /// come lo stile «attenzione» della web. Non è un errore: niente vibrazione d'errore.
        case attenzione
    }

    let testo: String
    let tipo: Tipo

    static func conferma(_ testo: String) -> AvvisoAccesso { AvvisoAccesso(testo: testo, tipo: .conferma) }
    static func attenzione(_ testo: String) -> AvvisoAccesso { AvvisoAccesso(testo: testo, tipo: .attenzione) }
}
