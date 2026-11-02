import Foundation

/// Testi corti a più pezzi («tra 66 e 82 · 8 volte su 10»): si va a capo solo tra un pezzo e l'altro, mai a metà di un pezzo
/// («8 / volte su 10»). Dentro ogni pezzo gli spazi diventano spazi che non si spezzano.
enum TestoACapo {
    static let separatore = " · "

    static func soloTraIPezzi(_ testo: String) -> String {
        testo.components(separatedBy: separatore)
            .map { $0.replacingOccurrences(of: " ", with: "\u{00A0}") }
            .joined(separator: separatore)
    }
}
