import SwiftUI
import UniformTypeIdentifiers

/// Lega > Widget: il ripiego che funziona anche senza App Group (codice da incollare nel widget) e la diagnostica della condivisione.
struct SezioneWidget: View {
    @EnvironmentObject private var sessione: SessioneAccount
    @State private var diagnostica = Condiviso.diagnostica()
    @State private var copiato = false
    @State private var dettagli = false

    var body: some View {
        Section {
            Button {
                Task { await copiaCodice() }
            } label: {
                Label(copiato ? "Codice copiato (resta negli appunti 2 minuti)" : "Copia il codice per il widget", systemImage: copiato ? "checkmark.circle.fill" : "doc.on.doc")
                    .frame(minHeight: 44)
            }
            .disabled(IndirizzoServer.manca)
            .sensoryFeedback(.success, trigger: copiato)
            Text("Se il widget dice «Serve l'accesso» o «Manca il server»: copia il codice, poi tieni premuto sul widget > Modifica widget > Codice di collegamento e incollalo. Il codice contiene un token del widget (solo lettura di Oggi e del widget, vale 90 giorni, si revoca uscendo): non condividerlo.")
                .font(.footnote).foregroundStyle(.secondary)
            DisclosureGroup(isExpanded: $dettagli) {
                VStack(alignment: .leading, spacing: 6) {
                    Text(diagnostica.lungo).font(.caption).foregroundStyle(.secondary).textSelection(.enabled)
                    Button("Aggiorna la diagnostica") { diagnostica = Condiviso.diagnostica() }.font(.caption).frame(minHeight: 44)
                }
            } label: {
                Label("Diagnostica widget", systemImage: "stethoscope").font(.subheadline)
            }
        } header: {
            Text("Widget")
        } footer: {
            Text(diagnostica.breve)
        }
        .onAppear { diagnostica = Condiviso.diagnostica() }
    }

    private func copiaCodice() async {
        let indirizzo = IndirizzoServer.attuale
        // con gli account: il token del widget (mai quello della sessione); se manca lo chiede al server
        if sessione.utente != nil, TokenWidget.leggi(server: indirizzo) == nil { await TokenWidget.assicura(server: ServerCorrente.condiviso) }
        let codice = CodiceWidget.crea(indirizzo: indirizzo, token: TokenWidget.leggi(server: indirizzo))
        // negli appunti solo su questo telefono (niente Appunti universali) e per poco: contiene la sessione
        UIPasteboard.general.setItems([[UTType.plainText.identifier: codice]],
                                      options: [.localOnly: true, .expirationDate: Date().addingTimeInterval(120)])
        copiato = true
        Task {
            try? await Task.sleep(nanoseconds: 3_000_000_000)
            copiato = false
        }
    }
}
