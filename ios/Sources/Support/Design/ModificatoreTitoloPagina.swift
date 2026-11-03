import SwiftUI

/// Il modificatore di `View.titoloPagina(_:)`: titolo nella barra, grande o piccolo secondo la dimensione del testo
/// (`TitoloPagina.nellaPagina`), e lo stesso titolo nell'ambiente per `TitoloNellaPagina`.
struct ModificatoreTitoloPagina: ViewModifier {
    let titolo: String
    @Environment(\.dynamicTypeSize) private var dimensione

    func body(content: Content) -> some View {
        content
            .navigationTitle(titolo)
            .toolbarTitleDisplayMode(TitoloPagina.nellaPagina(dimensione) ? .inline : .large)
            .environment(\.titoloPagina, titolo)
    }
}
