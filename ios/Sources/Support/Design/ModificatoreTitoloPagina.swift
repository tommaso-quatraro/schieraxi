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
        let piccolo = titoloPiccolo
        content
            // Con `TitoloInBarra` il titolo di sistema resta vuoto: sotto il nostro non si vede, ma VoiceOver lo trovava lo
            // stesso (#419), in un riquadro largo quanto lo spazio del titolo: con il testo massimo su una zona vuota, con il
            // testo normale come secondo titolo. Così il pulsante «indietro» della pagina dopo non ha il nome di questa.
            .navigationTitle(piccolo == nil ? titolo : "")
            .toolbarTitleDisplayMode(TitoloPagina.grandeInBarra(dimensione, piccoloInBarra: piccoloInBarra) ? .large : .inline)
            .titoloInBarra(piccolo)
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
