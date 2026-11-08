import Foundation

/// Dove va il codice di collegamento del widget: gli appunti di iOS (`AppuntiDiSistema`) o, nei test, degli appunti finti.
@MainActor
protocol AppuntiCodice: AnyObject {
    /// Mette il codice negli appunti fino a `scade`; poi iOS lo toglie da solo.
    func copia(_ codice: String, scade: Date)
}
