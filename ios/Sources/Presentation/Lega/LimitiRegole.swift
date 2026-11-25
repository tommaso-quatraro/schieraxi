import Foundation

/// SCHELETRO per vedere fallire i test (#889): la versione vera arriva nel commit dopo.
struct LimitiRegole: Equatable, Sendable {
    struct Limite: Equatable, Sendable {
        let min: Double
        let max: Double
    }

    let valori: [String: Limite]

    init(valori: [String: Limite]) {
        self.valori = valori
    }

    init?(dati: Data) {
        return nil
    }

    func intervallo(_ chiave: String) -> ClosedRange<Double> {
        guard let l = valori[chiave] else { return -Double.greatestFiniteMagnitude...Double.greatestFiniteMagnitude }
        return l.min...l.max
    }

    static let riserva = LimitiRegole(valori: [:])
}
