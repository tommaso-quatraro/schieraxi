import SwiftUI

/// Il modificatore di `View.titoloPagina(_:piccoloInBarra:)`: titolo nella barra, grande o piccolo secondo la dimensione del
/// testo e la pagina (`TitoloPagina.grandeInBarra`), e lo stesso titolo nell'ambiente per `TitoloNellaPagina`. Il titolo
/// piccolo non è mai quello di sistema, che taglia con «…»: `TitoloInBarra` lo mostra intero (a capo se serve, #293) o, con
/// il testo grande, solo se ci sta intero su una riga (#419).
struct ModificatoreTitoloPagina: ViewModifier {
    let titolo: String
    var piccoloInBarra = false
    @Environment(\.dynamicTypeSize) private var dimensione

    func body(content: Content) -> some View {
        content
            .navigationTitle(titolo)
            .toolbarTitleDisplayMode(TitoloPagina.grandeInBarra(dimensione, piccoloInBarra: piccoloInBarra) ? .large : .inline)
            .titoloInBarra(titoloPiccolo)
            .environment(\.titoloPagina, titolo)
    }

    /// Il titolo piccolo della barra, se la barra non ha quello grande.
    private var titoloPiccolo: TitoloInBarra? {
        if TitoloPagina.interoInBarra(dimensione, piccoloInBarra: piccoloInBarra) {
            return TitoloInBarra(titolo: titolo)
        }
        if TitoloPagina.inBarraSeCiSta(dimensione) {
            return TitoloInBarra(titolo: titolo, soloSeCiSta: true)
        }
        return nil
    }
}
