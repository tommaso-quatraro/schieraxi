import SwiftUI

/// Il titolo intero della pagina, in cima alla lista o alla colonna che scorre. C'è solo con il testo grande
/// (`TitoloPagina.soglia`), quando la barra mostra il titolo piccolo: va a capo invece di tagliarsi e scorre con la pagina.
/// Il testo arriva da `.titoloPagina(_:)` della pagina. Con il testo normale non occupa spazio, nemmeno una riga vuota
/// nella lista. Nelle pagine a colonna dell'iPad c'è anche con il testo normale, in cima alla colonna (#930).
struct TitoloNellaPagina: View {
    @Environment(\.titoloPagina) private var titolo
    @Environment(\.dynamicTypeSize) private var dimensione
    @Environment(\.titoloNellaColonna) private var inColonna

    var body: some View {
        if let titolo, TitoloPagina.nellaPagina(dimensione, inColonna: inColonna) {
            let voce = TitoloPagina.voceNellaPagina(dimensione, inColonna: inColonna)
            Text(titolo)
                .font(.largeTitle.bold())
                .dynamicTypeSize(...TitoloPagina.tetto)
                .fixedSize(horizontal: false, vertical: true)
                .frame(maxWidth: .infinity, alignment: .leading)
                // VoiceOver legge il titolo una volta sola (#419): qui, come intestazione, quando la barra è senza titolo;
                // se no lo legge nella barra e qui lo ripeterebbe
                .accessibilityHidden(!voce)
                .accessibilityAddTraits(voce ? .isHeader : [])
                // In una lista: allineato al bordo delle schede, come il titolo grande della barra, senza fondo né riga.
                .listRowInsets(EdgeInsets())
                .listRowBackground(Color.clear)
                .listRowSeparator(.hidden)
        }
    }
}

#Preview("Testo grande: titolo nella pagina") {
    NavigationStack {
        List {
            TitoloNellaPagina()
            Section("Promemoria sul telefono") {
                Text("Notifiche")
            }
        }
        .titoloPagina("Avvisi e promemoria")
    }
    .dynamicTypeSize(.accessibility2)
}

#Preview("Testo normale: titolo grande nella barra") {
    NavigationStack {
        List {
            TitoloNellaPagina()
            Section("Promemoria sul telefono") {
                Text("Notifiche")
            }
        }
        .titoloPagina("Avvisi e promemoria")
    }
}
