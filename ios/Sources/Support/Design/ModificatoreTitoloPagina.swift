import SwiftUI

/// Il modificatore di `View.titoloPagina(_:piccoloInBarra:)`: titolo nella barra secondo la dimensione del testo e la
/// pagina, e lo stesso titolo nell'ambiente per `TitoloNellaPagina`. Nella barra il titolo non si taglia mai: grande di
/// sistema (testo normale), intero a capo (`TitoloInBarra`, pagine con `piccoloInBarra`, #293) o niente (testo grande,
/// `TitoloPagina.barraSenzaTitolo`, #419: il titolo intero è nella pagina).
struct ModificatoreTitoloPagina: ViewModifier {
    let titolo: String
    var piccoloInBarra = false
    @Environment(\.dynamicTypeSize) private var dimensione

    func body(content: Content) -> some View {
        let grande = TitoloPagina.grandeInBarra(dimensione, piccoloInBarra: piccoloInBarra)
        content
            // Il titolo di sistema c'è solo dove la barra lo mostra grande. Con `TitoloInBarra` o con la barra senza titolo
            // resta vuoto: sotto `TitoloInBarra` non si vede, ma VoiceOver lo trovava lo stesso (#419), in un riquadro largo
            // quanto lo spazio del titolo (con il testo massimo su una zona vuota, con il testo normale come secondo
            // titolo); con il testo grande si tagliava. Così il pulsante «indietro» della pagina dopo non ha il nome di questa.
            .navigationTitle(grande ? titolo : "")
            .toolbarTitleDisplayMode(grande ? .large : .inline)
            .titoloInBarra(TitoloPagina.interoInBarra(dimensione, piccoloInBarra: piccoloInBarra) ? TitoloInBarra(titolo: titolo) : nil)
            .environment(\.titoloPagina, titolo)
    }
}
