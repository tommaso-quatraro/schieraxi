import Foundation

/// Il corpo di `POST /api/diario/schierata` («Non è quello che ho schierato» della pagina Giornate).
struct CorpoSchierata: Encodable {
    let giornata: Int
    /// «manuale» (con `titolari`); il server accetta anche «consigliata», che l'app non manda più.
    let tipo: String
    var titolari: [Int]? = nil
    /// La stagione della voce del diario: il server rifiuta le stagioni passate invece di scrivere sulla giornata con lo stesso
    /// numero di quest'anno. Senza (nil) il campo non si manda e il server usa la stagione in corso.
    var stagione: String? = nil
}
