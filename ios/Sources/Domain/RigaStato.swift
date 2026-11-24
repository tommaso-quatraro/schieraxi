import Foundation

/// La riga sotto il titolo della pagina Giornate (#863). Da scrivere: per ora non c'è (i test la vogliono).
struct RigaStato: Equatable {
    let pezzi: [String]
    let squadra: String?
    let voce: String

    var testo: String { pezzi.joined(separator: " · ") }

    init?(info: InfoServer?, nonRaggiungibile: Bool) {
        return nil
    }
}
