import SwiftUI

/// «Il tuo codice di recupero»: il codice compare UNA volta sola (alla registrazione, dopo un recupero, o quando se ne chiede uno
/// nuovo). Si può copiare o condividere, e si va avanti solo dopo aver confermato «Ho salvato il codice». Le frasi sono quelle
/// della web (`htmlCodiceUnaVolta` e `mostraCodiceAccesso` in `fanta/web/app.js`, chiavi `codice.*`).
struct CodiceRecuperoView: View {
    let codice: String
    /// Il titolo sopra «Il tuo codice di recupero», come sulla web dopo un recupero («Password cambiata»). Senza, il titolo è
    /// «Il tuo codice di recupero».
    var titolo: String?
    var testoPulsante = "Continua"
    let alConfermare: () -> Void
    @State private var salvato = false
    @State private var copiato = false
    /// Durante una registrazione dello schermo (o AirPlay) il codice non si mostra.
    @StateObject private var schermo = StatoRegistrazioneSchermo()

    var body: some View {
        ScrollView {
            VStack(spacing: 18) {
                Marchio(lato: 72)
                    .padding(.top, 8)
                if let titolo {
                    Text(titolo)
                        .font(.title2.bold())
                        .multilineTextAlignment(.center)
                        .accessibilityAddTraits(.isHeader)
                }
                Text(Catalogo.Codice.titolo)
                    .font(titolo == nil ? .title2.bold() : .headline)
                    .multilineTextAlignment(.center)
                    .accessibilityAddTraits(.isHeader)
                VStack(spacing: 8) {
                    Text(Catalogo.Codice.aCosaServe)
                        .foregroundStyle(Color.testoSecondario)
                    // come la web: «Salva questo codice.» in grassetto, poi il perché, nel colore degli avvisi
                    Text("\(Text(Catalogo.Codice.salva).bold()) \(Catalogo.Codice.spiega)")
                        .foregroundStyle(Color.attenzione)
                }
                .font(.subheadline)
                .multilineTextAlignment(.center)
                .fixedSize(horizontal: false, vertical: true)

                Carta {
                    if schermo.registrato {
                        Label("Codice nascosto: lo schermo è in registrazione.", systemImage: "eye.slash")
                            .font(.subheadline).foregroundStyle(Color.testoSecondario)
                            .frame(maxWidth: .infinity)
                    } else {
                        Text(codice)
                            .font(.system(.title, design: .monospaced).weight(.bold))
                            .minimumScaleFactor(0.6)
                            .lineLimit(2)
                            .multilineTextAlignment(.center)
                            .frame(maxWidth: .infinity)
                            .textSelection(.enabled)
                            .privacySensitive()
                            .accessibilityLabel("\(Catalogo.Account.recupero): \(codice.map(String.init).joined(separator: " "))")
                    }
                }

                HStack(spacing: 12) {
                    Button {
                        // Si tiene negli appunti solo per tre minuti e solo su questo telefono.
                        UIPasteboard.general.setItems([["public.utf8-plain-text": codice]],
                                                      options: [.localOnly: true, .expirationDate: Date().addingTimeInterval(180)])
                        copiato = true
                    } label: {
                        Label(copiato ? Catalogo.Codice.copiato : Catalogo.Codice.copia, systemImage: copiato ? "checkmark" : "doc.on.doc")
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

                Toggle(Catalogo.Codice.salvato, isOn: $salvato)
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
        .schermoProtetto()
    }
}
