import SwiftUI

/// Impostazioni > App: com'è collegato il widget, in una riga. «Widget collegato automaticamente» quando l'app riesce a passargli
/// da sola indirizzo e token (App Group o Keychain condiviso, `Accesso.sincronizzaConIlWidget`); altrimenti «Tocca per collegare»,
/// che apre «Collega il widget» (riprova l'automatico e, solo se non va, copia il codice).
struct RigaCollegamentoWidget: View {
    @EnvironmentObject private var sessione: SessioneAccount
    @State private var collegato = true
    @State private var aperto = false

    var body: some View {
        Group {
            if collegato {
                Label("Widget collegato automaticamente", systemImage: "checkmark.circle.fill")
                    .labelStyle(.voce(.green))
                    .frame(minHeight: 44)
                    .accessibilityElement(children: .combine)
            } else {
                Button { aperto = true } label: {
                    Label("Widget: tocca per collegare", systemImage: "link")
                        .labelStyle(.voce(.orange))
                        .frame(maxWidth: .infinity, minHeight: 44, alignment: .leading)
                        .contentShape(Rectangle())
                }
                .accessibilityLabel("Widget non collegato")
                .accessibilityHint("Tocca per collegare il widget all'app")
            }
        }
        .onAppear(perform: aggiorna)
        .sheet(isPresented: $aperto, onDismiss: aggiorna) {
            CollegaWidgetView()
                .environmentObject(sessione)
                .tint(Color.verde)
        }
    }

    private func aggiorna() {
        // fotografie del simulatore: nessun Keychain, si mostra il caso normale
        if Demo.attivo { collegato = true; return }
        let indirizzo = IndirizzoServer.attuale
        collegato = CollegamentoWidget.automatico(canale: Accesso.sincronizzaConIlWidget(), conAccount: sessione.utente != nil,
                                                  haToken: TokenWidget.leggi(server: indirizzo) != nil)
    }
}

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
