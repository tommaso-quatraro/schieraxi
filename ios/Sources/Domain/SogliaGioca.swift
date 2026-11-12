import Foundation

/// Quando conta «gioca N%», come `SOGLIA_GIOCA`, `SOGLIA_BASSA` e `giocaLetto` di app.js (#616): sotto l'80% si mostra (arancio
/// fra 50 e 79, rosso sotto 50); sopra, il fantavoto atteso basta. Si decide sul numero che si legge: 79,6% si scrive «80%» e non è
/// «sotto l'80%». Un solo posto per la scheda del giocatore e, con la Formazione unica, per pedina e sostituti (`SogliaGiocaTests`).
enum SogliaGioca {
    static let alta = 0.8
    static let bassa = 0.5

    enum Livello: Equatable, Sendable {
        /// Dall'80% in su: «gioca N%» non serve.
        case sicuro
        /// Fra 50 e 79: arancio.
        case medio
        /// Sotto 50: rosso.
        case basso
    }

    /// La probabilità di giocare come si legge, al centesimo (0,796 → 0,80); 0 se il server non la manda (`p_voto ?? 0`).
    static func letta(_ pVoto: Double?) -> Double {
        guard let p = pVoto, p.isFinite else { return 0 }
        return (p * 100).rounded() / 100
    }

    static func livello(_ pVoto: Double?) -> Livello {
        let q = letta(pVoto)
        if q >= alta { return .sicuro }
        return q >= bassa ? .medio : .basso
    }

    /// «gioca N%» si mostra solo sotto l'80%.
    static func daMostrare(_ pVoto: Double?) -> Bool {
        livello(pVoto) != .sicuro
    }
}
