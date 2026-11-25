import Foundation

/// «Importa le rose» aperta da un passo della configurazione guidata (#880). Sulla web le rose si caricano dentro la guida, che poi
/// continua con i passi che restano fino a «Tutto pronto»; sull'iPhone il passo porta alla pagina delle rose delle Impostazioni.
/// Quando quella pagina si lascia (rose salvate, o «indietro» senza salvare) la guida si riapre e riparte da ciò che resta da fare.
/// Vive nel `LegaViewModel` della sessione: uscendo dall'account se ne va con lui.
struct RitornoAllaGuida {
    private enum Fase { case nessuna, chiesta, aperta }
    private var fase = Fase.nessuna

    /// La guida ha chiesto la pagina delle rose.
    mutating func importaChiesta() { fase = .chiesta }

    /// La pila delle Impostazioni è cambiata: vero, una volta, quando la pagina delle rose chiesta dalla guida è stata aperta e poi
    /// lasciata. Se la pagina non si apre (le Regole con modifiche da salvare la fanno aspettare) e si torna indietro, la richiesta
    /// cade: la pagina aperta più tardi dalle Impostazioni non riapre la guida.
    mutating func pilaCambiata(_ pagine: [PaginaImpostazioni]) -> Bool {
        let rose = pagine.contains(.importa)
        switch (fase, rose) {
        case (.chiesta, true):
            fase = .aperta
        case (.chiesta, false):
            fase = .nessuna
        case (.aperta, false):
            fase = .nessuna
            return true
        default:
            break
        }
        return false
    }

    /// La pagina delle rose è stata chiesta dalla guida e non è ancora stata lasciata: salvate le rose, la pagina si chiude da sola.
    var attivo: Bool { fase != .nessuna }
}
