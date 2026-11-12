import Foundation

extension Giocatore {
    /// Il nome senza le iniziali finali («Marteni L.» → «Marteni»): per i titoli stretti.
    var nomeCorto: String {
        var parti = nome.split(separator: " ").map(String.init)
        while parti.count > 1, let ultima = parti.last, ultima.hasSuffix("."), ultima.count <= 3 { parti.removeLast() }
        return parti.joined(separator: " ")
    }
}
