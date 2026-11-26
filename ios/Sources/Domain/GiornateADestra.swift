import Foundation

/// Cosa mostra la colonna di destra di Giornate sull'iPad (#896): i numeri di «Dettagli», una giornata, o niente (pagina vuota).
/// Sul telefono non serve: lì «Dettagli» e le giornate si aprono sotto la loro riga.
enum ADestraGiornate: Equatable {
    case dettagli
    case giornata(String)
    case niente

    /// La riga da segnare come scelta nell'elenco: quella di «Dettagli» o quella della giornata.
    var id: String? {
        switch self {
        case .dettagli: return PaginaGiornate.idDettagli
        case .giornata(let id): return id
        case .niente: return nil
        }
    }
}

extension PaginaGiornate {
    /// L'identità della riga «Dettagli» nell'elenco dell'iPad. Quelle delle giornate sono «stagione-numero» (`VoceDiario.id`):
    /// non possono essere uguali.
    static let idDettagli = "dettagli"

    /// Cosa va a destra con la riga scelta `scelta` (nil: nessuna ancora): «Dettagli» se è quella e ci sono i numeri; la giornata
    /// scelta se c'è; se no la più recente; senza giornate i Dettagli, se ci sono.
    func aDestra(scelta: String?) -> ADestraGiornate {
        if scelta == Self.idDettagli, dettagli != nil { return .dettagli }
        if let scelta, righe.contains(where: { $0.id == scelta }) { return .giornata(scelta) }
        if let prima = righe.first?.id { return .giornata(prima) }
        return dettagli != nil ? .dettagli : .niente
    }
}
