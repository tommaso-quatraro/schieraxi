import SwiftUI

/// «Salva il tuo codice di recupero»: il codice compare UNA volta sola (alla registrazione, dopo un recupero, o quando se ne chiede uno
/// nuovo). Si può copiare o condividere, e si va avanti solo dopo aver confermato «l'ho salvato».
struct CodiceRecuperoView: View {
    let codice: String
    var titolo = "Salva il tuo codice di recupero"
    var testoPulsante = "Continua"
    let alConfermare: () -> Void
    @State private var salvato = false
    @State private var copiato = false

    var body: some View {
        ScrollView {
            VStack(spacing: 18) {
                Marchio(lato: 72)
                    .padding(.top, 8)
                Text(titolo)
                    .font(.title2.bold())
                    .multilineTextAlignment(.center)
                    .accessibilityAddTraits(.isHeader)
                Text("Se dimentichi la password, questo codice è l'unico modo per rientrare. Compare una volta sola: scrivilo o copialo in un posto sicuro.")
                    .font(.subheadline).foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)

                Carta {
                    Text(codice)
                        .font(.system(.title, design: .monospaced).weight(.bold))
                        .minimumScaleFactor(0.6)
                        .lineLimit(2)
                        .multilineTextAlignment(.center)
                        .frame(maxWidth: .infinity)
                        .textSelection(.enabled)
                        .accessibilityLabel("Codice di recupero: \(codice.map(String.init).joined(separator: " "))")
                }

                HStack(spacing: 12) {
                    Button {
                        // Si tiene negli appunti solo per tre minuti e solo su questo telefono.
                        UIPasteboard.general.setItems([["public.utf8-plain-text": codice]],
                                                      options: [.localOnly: true, .expirationDate: Date().addingTimeInterval(180)])
                        copiato = true
                    } label: {
                        Label(copiato ? "Copiato" : "Copia", systemImage: copiato ? "checkmark" : "doc.on.doc")
                            .contentTransition(.symbolEffect(.replace))
                            .frame(maxWidth: .infinity, minHeight: Tema.areaTocco)
                    }
                    .pulsanteVetro()
                    .sensoryFeedback(.success, trigger: copiato)
                    ShareLink(item: codice, subject: Text("Codice di recupero di SchieraXI")) {
                        Label("Condividi", systemImage: "square.and.arrow.up")
                            .frame(maxWidth: .infinity, minHeight: Tema.areaTocco)
                    }
                    .pulsanteVetro()
                }

                Toggle("L'ho salvato in un posto sicuro", isOn: $salvato)
                    .tint(Color.verde)
                    .frame(minHeight: Tema.areaTocco)
                    .padding(.horizontal, 4)

                Button(action: alConfermare) {
                    Text(testoPulsante).font(.headline).frame(maxWidth: .infinity, minHeight: Tema.areaTocco)
                }
                .pulsanteVetro(prominente: true)
                .disabled(!salvato)
                .accessibilityHint(salvato ? "" : "Prima conferma di aver salvato il codice")
            }
            .frame(maxWidth: 520)
            .padding(Tema.margine)
            .frame(maxWidth: .infinity)
        }
        .background(Sfondo())
        .navigationBarTitleDisplayMode(.inline)
    }
}
