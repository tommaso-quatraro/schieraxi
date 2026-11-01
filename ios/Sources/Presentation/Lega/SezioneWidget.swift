import SwiftUI

/// Solo per chi amministra (Impostazioni > Avanzate): come stanno i dati condivisi tra app e widget.
struct DiagnosticaWidgetSezione: View {
    @State private var diagnostica = Condiviso.diagnostica()
    @State private var dettagli = false

    var body: some View {
        Section {
            DisclosureGroup(isExpanded: $dettagli) {
                VStack(alignment: .leading, spacing: 6) {
                    Text(diagnostica.lungo).font(.caption).foregroundStyle(.secondary).textSelection(.enabled)
                    Button("Aggiorna la diagnostica") { diagnostica = Condiviso.diagnostica() }.font(.caption).frame(minHeight: 44)
                }
            } label: {
                Label("Diagnostica widget", systemImage: "stethoscope").font(.subheadline)
            }
        } footer: {
            Text(diagnostica.breve)
        }
        .onAppear { diagnostica = Condiviso.diagnostica() }
    }
}
