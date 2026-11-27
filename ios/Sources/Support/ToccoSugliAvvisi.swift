import SwiftUI

/// Porta l'app dove dice il tocco su un avviso (`AvvisiToccati`): subito con l'app aperta, appena c'è la schermata se il tocco l'ha
/// aperta.
struct ToccoSugliAvvisi: ViewModifier {
    let nav: Navigazione

    func body(content: Content) -> some View {
        content.onChange(of: AvvisiToccati.condiviso.destinazione, initial: true) { _, _ in
            AvvisiToccati.condiviso.consegna(a: nav)
        }
    }
}

extension View {
    /// Il tocco su un avviso dell'app porta `nav` dove dice l'avviso (`AvvisiToccati`).
    func toccoSugliAvvisi(_ nav: Navigazione) -> some View {
        modifier(ToccoSugliAvvisi(nav: nav))
    }
}
