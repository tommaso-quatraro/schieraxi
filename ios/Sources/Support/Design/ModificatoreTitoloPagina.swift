import SwiftUI

/// Il modificatore di `View.titoloPagina(_:piccoloInBarra:)`: titolo nella barra, grande o piccolo secondo la dimensione del
/// testo e la pagina (`TitoloPagina.grandeInBarra`), e lo stesso titolo nell'ambiente per `TitoloNellaPagina`.
struct ModificatoreTitoloPagina: ViewModifier {
    let titolo: String
    var piccoloInBarra = false
    @Environment(\.dynamicTypeSize) private var dimensione

    func body(content: Content) -> some View {
        content
            .navigationTitle(titolo)
            .toolbarTitleDisplayMode(TitoloPagina.grandeInBarra(dimensione, piccoloInBarra: piccoloInBarra) ? .large : .inline)
            .environment(\.titoloPagina, titolo)
    }
}
