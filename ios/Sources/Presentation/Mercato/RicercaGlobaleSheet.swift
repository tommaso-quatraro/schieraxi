import SwiftUI

/// Il foglio della ricerca di un giocatore: l'elenco dei risultati e, al tocco, la scheda del giocatore scelto.
struct RicercaGlobaleSheet: View {
    let server: any ServerClient
    @Environment(\.dismiss) private var chiudi

    var body: some View {
        NavigationStack {
            RicercaGiocatoreView(titolo: "Cerca un giocatore", server: server)
                .toolbar { ToolbarItem(placement: .navigationBarTrailing) { Button("Chiudi") { chiudi() } } }
                .destinazioniGiocatore(server: server)
        }
    }
}
