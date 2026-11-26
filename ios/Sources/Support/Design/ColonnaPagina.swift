import SwiftUI

/// Le pagine a elenco sull'iPad (#896), come la web larga: una colonna di al massimo 720 punti (`.imp-colonna`) e selettori a
/// segmenti di al massimo 520 (`#aspetto .segmenti`). Così interruttori e valori restano vicini al loro nome invece di finire a
/// 1200-1600 punti di distanza. Sull'iPhone, più stretto della colonna, non cambia niente.
enum LarghezzaPagina {
    /// La colonna delle pagine a elenco.
    static let colonna: CGFloat = 720
    /// I selettori a segmenti.
    static let segmenti: CGFloat = 520

    /// Il margine da aggiungere a ogni lato perché il contenuto non superi `massima`: 0 se lo spazio è già più stretto (o se la
    /// misura non c'è ancora).
    static func margine(larghezza: CGFloat, massima: CGFloat = colonna) -> CGFloat {
        guard larghezza.isFinite, larghezza > massima else { return 0 }
        return ((larghezza - massima) / 2).rounded(.down)
    }
}

/// Lo spazio che avanza oltre la colonna va ai due lati come margine sicuro (`safeAreaPadding`): la lista scorre ancora da tutta
/// la larghezza e lo sfondo resta pieno, ma righe e schede stanno nella colonna al centro. Con margine 0 (iPhone) è come senza.
private struct ColonnaPagina: ViewModifier {
    @State private var larghezza: CGFloat = 0

    func body(content: Content) -> some View {
        content
            .safeAreaPadding(.horizontal, LarghezzaPagina.margine(larghezza: larghezza))
            .onGeometryChange(for: CGFloat.self) { $0.size.width } action: { larghezza = $0 }
    }
}

extension View {
    /// Una pagina a elenco: sull'iPad in una colonna larga al massimo come quella della web (`LarghezzaPagina.colonna`).
    func colonnaPagina() -> some View {
        modifier(ColonnaPagina())
    }

    /// Un selettore a segmenti largo al massimo come quelli della web (`LarghezzaPagina.segmenti`), allineato a sinistra.
    func segmentiDellaPagina() -> some View {
        frame(maxWidth: LarghezzaPagina.segmenti, alignment: .leading)
            .frame(maxWidth: .infinity, alignment: .leading)
    }
}
