import SwiftUI

/// La lente accanto al titolo di ogni schermata: cerca un giocatore da qualsiasi sezione.
struct RicercaGlobale: ViewModifier {
    @Environment(\.server) private var server
    @Environment(\.apriImpostazioni) private var apriImpostazioni
    @State private var aperta = false
    /// false = niente lente e ingranaggio qui (per esempio l'elenco a sinistra sull'iPad: li ha già la pagina a destra).
    var attiva = true

    init(attiva: Bool = true) { self.attiva = attiva }

    func body(content: Content) -> some View {
        content
            .toolbar {
                if attiva {
                ToolbarItemGroup(placement: .navigationBarTrailing) {
                    Button { aperta = true } label: { Image(systemName: "magnifyingglass").frame(minWidth: 44, minHeight: 44) }
                        .accessibilityLabel("Cerca un giocatore")
                    // le Impostazioni stanno accanto alla lente in ogni testata (non nei fogli, dove la funzione non c'è)
                    if let apriImpostazioni {
                        Button { apriImpostazioni() } label: { Image(systemName: "gearshape").frame(minWidth: 44, minHeight: 44) }
                            .accessibilityLabel("Impostazioni")
                    }
                }
                }
            }
            .sheet(isPresented: $aperta) { RicercaGlobaleSheet(server: server) }
            .onAppear {
                // Solo per le fotografie del simulatore (argomento -DEMO_SCHERMATA ricerca).
                if Demo.attivo, Demo.schermata == "ricerca", !Demo.ricercaMostrata {
                    Demo.ricercaMostrata = true
                    aperta = true
                }
            }
    }
}

extension View {
    /// Aggiunge la lente della ricerca di un giocatore alla barra della schermata.
    /// `attiva: false` la toglie (stessa struttura della vista, così non si rifà nulla quando cambia).
    func ricercaGlobale(attiva: Bool = true) -> some View { modifier(RicercaGlobale(attiva: attiva)) }
}
