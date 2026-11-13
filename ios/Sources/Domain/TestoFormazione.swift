import Foundation

/// La formazione scritta a parole, da copiare nell'app della lega, come `testoFormazione` della web (#616): l'app della lega non
/// permette di incollarla, si inserisce a mano leggendola da qui («Copia per l'app della lega»).
enum TestoFormazione {
    /// «Giornata 9 · 4-3-3», una riga per reparto («P: Noraldi»), poi «Panchina: 1) Pelucci, 2) ...».
    static func crea(giornata: Int, giornataLega: Int? = nil, modulo: String, titolari: [Giocatore], panchina: [Giocatore]) -> String {
        var righe = ["\(TempiLega.etichetta(serieA: giornata, lega: giornataLega)) · \(modulo)"]
        for ruolo in ["P", "D", "C", "A"] {
            righe.append("\(ruolo): " + titolari.filter { $0.ruolo == ruolo }.map(\.nome).joined(separator: ", "))
        }
        if !panchina.isEmpty {
            righe.append("Panchina: " + panchina.enumerated().map { "\($0.offset + 1)) \($0.element.nome)" }.joined(separator: ", "))
        }
        return righe.joined(separator: "\n")
    }
}
