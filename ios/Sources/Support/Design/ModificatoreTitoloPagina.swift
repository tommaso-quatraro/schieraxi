import SwiftUI

/// Il modificatore di `View.titoloPagina(_:piccoloInBarra:)`: titolo nella barra secondo la dimensione del testo e la
/// pagina, e lo stesso titolo nell'ambiente per `TitoloNellaPagina`. Nella barra il titolo non si taglia mai: grande di
/// sistema (testo normale), intero a capo (`TitoloInBarra`, pagine con `piccoloInBarra`, #293) o niente (testo grande,
/// `TitoloPagina.barraSenzaTitolo`, #419: il titolo intero è nella pagina). Nelle pagine a colonna dell'iPad il titolo grande
/// sta nella pagina anche con il testo normale (`titoliNellaColonna()`, #930).
struct ModificatoreTitoloPagina: ViewModifier {
    let titolo: String
    var piccoloInBarra = false
    @Environment(\.dynamicTypeSize) private var dimensione
    @Environment(\.titoloNellaColonna) private var pilaInColonna

    func body(content: Content) -> some View {
        let inColonna = TitoloPagina.inColonna(iPadLargo: pilaInColonna, piccoloInBarra: piccoloInBarra)
        let grande = TitoloPagina.grandeInBarra(dimensione, piccoloInBarra: piccoloInBarra, inColonna: inColonna)
        content
            // Il titolo di sistema c'è solo dove la barra lo mostra grande. Con `TitoloInBarra` o con la barra senza titolo
            // resta vuoto: sotto `TitoloInBarra` non si vede, ma VoiceOver lo trovava lo stesso (#419), in un riquadro largo
            // quanto lo spazio del titolo (con il testo massimo su una zona vuota, con il testo normale come secondo
            // titolo); con il testo grande si tagliava. Così il pulsante «indietro» della pagina dopo non ha il nome di questa.
            .navigationTitle(grande ? titolo : "")
            .toolbarTitleDisplayMode(grande ? .large : .inline)
            .titoloInBarra(TitoloPagina.interoInBarra(dimensione, piccoloInBarra: piccoloInBarra) ? TitoloInBarra(titolo: titolo) : nil)
            .environment(\.titoloPagina, titolo)
            // per `TitoloNellaPagina` e `bordoSottoLaBarraVuota()` di questa pagina: spento se il titolo è piccolo nella barra
            .environment(\.titoloNellaColonna, inColonna)
    }
}
