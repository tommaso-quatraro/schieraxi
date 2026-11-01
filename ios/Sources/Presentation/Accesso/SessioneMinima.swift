import SwiftUI

/// Rete di sicurezza nelle Impostazioni: se c'è una sessione (o il server non risponde) ma «Il tuo account» non si vede
/// perché l'utente non si è caricato, restano comunque «Esci» e «Cambia server». Così nessuno resta intrappolato.
struct SessioneMinimaSezione: View {
    let nonRaggiungibile: Bool
    @EnvironmentObject private var sessione: SessioneAccount
    @State private var chiediEsci = false

    /// «Il tuo account» (AccountSezione) compare solo con gli account e un utente noto: negli altri casi serve questa.
    private var accountVisibile: Bool { sessione.multiutente && sessione.utente != nil }
    private var haSessione: Bool { Accesso.archivio.leggi(server: IndirizzoServer.attuale) != nil }

    var body: some View {
        if !Demo.attivo, !ProvaEsempio.attiva, !accountVisibile, haSessione || nonRaggiungibile {
            Section {
                if nonRaggiungibile {
                    Label("Non riesco a raggiungere SchieraXI.", systemImage: "wifi.exclamationmark")
                        .font(.subheadline).foregroundStyle(Color.attenzione)
                }
                NavigationLink(value: PaginaImpostazioni.cambiaServer) {
                    Label("Cambia server", systemImage: "server.rack").labelStyle(.voce(.gray)).frame(minHeight: Tema.areaTocco)
                }
                Button { chiediEsci = true } label: {
                    Label("Esci", systemImage: "rectangle.portrait.and.arrow.right").labelStyle(.voce(.gray)).frame(minHeight: Tema.areaTocco)
                }
            } header: {
                Text("Collegamento")
            } footer: {
                Text("Se l'app non si collega, puoi uscire e accedere di nuovo, oppure scegliere un altro server.")
            }
            .confirmationDialog("Esci da SchieraXI su questo telefono?", isPresented: $chiediEsci, titleVisibility: .visible) {
                Button("Esci", role: .destructive) { Task { await sessione.esci() } }
            } message: {
                Text("I dati salvati su questo telefono vengono cancellati.")
            }
        }
    }
}

/// Pagina per scegliere il server (con la prova prima di salvare), raggiungibile anche quando le altre voci non ci sono.
struct PaginaCambiaServer: View {
    var dopoProva: () async -> Void = {}

    var body: some View {
        List {
            Section {
                ProvaServerView(dopoProva: dopoProva)
            } footer: {
                Text("Lascia vuoto per tornare al server di SchieraXI.")
            }
        }
        .scrollContentBackground(.hidden)
        .background(Sfondo())
        .navigationTitle("Cambia server")
        .navigationBarTitleDisplayMode(.inline)
    }
}
