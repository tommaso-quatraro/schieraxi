import UIKit
import UniformTypeIdentifiers

/// Gli appunti veri: il codice resta solo su QUESTO telefono (niente Appunti universali verso Mac e iPad) e solo fino alla scadenza.
@MainActor
final class AppuntiDiSistema: AppuntiCodice {
    /// Le opzioni della copia: solo locale e con scadenza (si provano nei test).
    nonisolated static func opzioni(scade: Date) -> [UIPasteboard.OptionsKey: Any] {
        [.localOnly: true, .expirationDate: scade]
    }

    func copia(_ codice: String, scade: Date) {
        UIPasteboard.general.setItems([[UTType.plainText.identifier: codice]], options: Self.opzioni(scade: scade))
    }
}
