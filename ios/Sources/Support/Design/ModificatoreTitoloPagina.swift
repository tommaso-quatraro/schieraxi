import SwiftUI

/// Il modificatore di `View.titoloPagina(_:piccoloInBarra:)`: titolo nella barra, grande o piccolo secondo la dimensione del
/// testo e la pagina (`TitoloPagina.grandeInBarra`), e lo stesso titolo nell'ambiente per `TitoloNellaPagina`. Il titolo
/// piccolo, sotto la soglia, è intero e va a capo se serve (`TitoloInBarra`, #293).
struct ModificatoreTitoloPagina: ViewModifier {
    let titolo: String
    var piccoloInBarra = false
    @Environment(\.dynamicTypeSize) private var dimensione

    func body(content: Content) -> some View {
        content
            .navigationTitle(titolo)
            .toolbarTitleDisplayMode(TitoloPagina.grandeInBarra(dimensione, piccoloInBarra: piccoloInBarra) ? .large : .inline)
            .titoloInteroInBarra(TitoloPagina.interoInBarra(dimensione, piccoloInBarra: piccoloInBarra) ? titolo : nil)
            .environment(\.titoloPagina, titolo)
    }
}
