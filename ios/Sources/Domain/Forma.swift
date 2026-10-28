import Foundation

/// La forma di un giocatore: le ultime cinque giornate e se è in crescita o in calo (stessa regola della web app).
struct Forma: Equatable {
    enum Andamento: String, Equatable {
        case pochiDati = "pochi dati"
        case crescita = "in crescita"
        case calo = "in calo"
        case stabile = "stabile"

        var freccia: String {
            switch self {
            case .crescita: return "↗"
            case .calo: return "↘"
            default: return "→"
            }
        }
    }

    /// Le ultime (al massimo cinque) giornate, anche senza voto.
    let ultime: [VotoGiornata]
    let andamento: Andamento

    /// Con meno di 4 giornate con voto non si giudica; altrimenti si confronta la media delle ultime 3 con quella di tutte:
    /// più di 0,6 sopra = in crescita, più di 0,6 sotto = in calo.
    static func calcola(_ voti: [VotoGiornata]) -> Forma? {
        let ordinati = voti.sorted { $0.giornata < $1.giornata }
        guard !ordinati.isEmpty else { return nil }
        let ultime = Array(ordinati.suffix(5))
        let conVoto = ordinati.compactMap(\.fv)
        guard conVoto.count >= 4 else { return Forma(ultime: ultime, andamento: .pochiDati) }
        func media(_ valori: [Double]) -> Double { valori.reduce(0, +) / Double(valori.count) }
        let differenza = media(Array(conVoto.suffix(3))) - media(conVoto)
        if differenza > 0.6 { return Forma(ultime: ultime, andamento: .crescita) }
        if differenza < -0.6 { return Forma(ultime: ultime, andamento: .calo) }
        return Forma(ultime: ultime, andamento: .stabile)
    }
}
