import Foundation

/// La forma di un giocatore nella scheda, come `formaGiocatore` della web: le ultime cinque giornate e l'andamento, che decide il
/// server (`andamento` di `GET /api/giocatore`, `scheda.andamento`, #895). L'app non lo ricalcola dai voti: scrive la freccia e la
/// parola del catalogo. Un valore che non conosce, o un server di prima senza il campo: niente andamento, come la web.
struct Forma: Equatable {
    /// I codici del server.
    enum Andamento: String, Equatable {
        case pochiDati = "pochi_dati"
        case crescita = "in_crescita"
        case calo = "in_calo"
        case stabile = "stabile"

        var freccia: String {
            switch self {
            case .crescita: return "↗"
            case .calo: return "↘"
            default: return "→"
            }
        }

        /// La parola del catalogo (`mercato.in_crescita`, `mercato.in_calo`, `mercato.stabile`, `mercato.pochi_dati`), come la web.
        var parola: String {
            switch self {
            case .pochiDati: return Catalogo.Mercato.pochiDati
            case .crescita: return Catalogo.Mercato.inCrescita
            case .calo: return Catalogo.Mercato.inCalo
            case .stabile: return Catalogo.Mercato.stabile
            }
        }
    }

    /// Le ultime (al massimo cinque) giornate, anche senza voto, in ordine di giornata.
    let ultime: [VotoGiornata]
    /// nil: il server non lo manda (server di prima) o manda un valore che l'app non conosce.
    let andamento: Andamento?

    /// La forma dai voti della scheda e dal codice dell'andamento del server; nil senza presenze.
    static func di(_ voti: [VotoGiornata], andamento: String?) -> Forma? {
        let ordinati = voti.sorted { $0.giornata < $1.giornata }
        guard !ordinati.isEmpty else { return nil }
        return Forma(ultime: Array(ordinati.suffix(5)), andamento: andamento.flatMap(Andamento.init(rawValue:)))
    }
}
