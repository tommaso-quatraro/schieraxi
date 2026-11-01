import SwiftUI
import UniformTypeIdentifiers

/// «Collega il widget»: si apre dal tocco sul widget non collegato (`schieraxi://widget/collega`) o dalla configurazione guidata.
/// Con l'Apple ID gratuito e SideStore non è sicuro che app e widget condividano i dati (App Group), quindi l'app crea il codice
/// di collegamento (indirizzo + token del WIDGET `fw_`, mai quello della sessione) e lo mette negli appunti di QUESTO telefono
/// (niente Appunti universali) per 5 minuti. L'utente lo incolla una volta in «Modifica widget».
struct CollegaWidgetView: View {
    @EnvironmentObject private var sessione: SessioneAccount
    @Environment(\.dismiss) private var chiudi

    enum Stato: Equatable {
        case inCorso, copiato, senzaPermesso, prova
    }

    @State private var stato: Stato = .inCorso
    /// Cambia a ogni copia riuscita: fa partire il feedback aptico.
    @State private var copie = 0

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 18) {
                    Image(systemName: icona)
                        .font(.system(size: 44))
                        .symbolRenderingMode(.hierarchical)
                        .foregroundStyle(stato == .senzaPermesso ? Color.orange : Color.verde)
                        .accessibilityHidden(true)
                    Text(titolo).font(.title2.bold()).multilineTextAlignment(.center)
                    Text(spiegazione).font(.body).foregroundStyle(.secondary).multilineTextAlignment(.center)
                        .fixedSize(horizontal: false, vertical: true)
                    if stato == .copiato || stato == .senzaPermesso {
                        Button { Task { await copia() } } label: {
                            Label(stato == .copiato ? "Copia di nuovo" : "Riprova", systemImage: "doc.on.doc")
                                .frame(maxWidth: .infinity, minHeight: Tema.areaTocco)
                        }
                        .pulsanteVetro()
                    }
                    Button { chiudi() } label: {
                        Text("Fatto").frame(maxWidth: .infinity, minHeight: Tema.areaTocco)
                    }
                    .pulsanteVetro(prominente: true)
                    .keyboardShortcut(.defaultAction)
                    Text("Il codice permette al widget solo di leggere la tua formazione e vale 90 giorni. Non mandarlo a nessuno.")
                        .font(.footnote).foregroundStyle(.secondary).multilineTextAlignment(.center)
                        .fixedSize(horizontal: false, vertical: true)
                }
                .padding(24)
                // su iPad e in orizzontale il contenuto non si allarga troppo
                .frame(maxWidth: 520)
                .frame(maxWidth: .infinity)
            }
            .navigationTitle("Widget")
            .navigationBarTitleDisplayMode(.inline)
        }
        // a tutta altezza: a metà, su iPad e con il testo grande, «Fatto» restava sotto la piega
        .presentationDragIndicator(.visible)
        .sensoryFeedback(.success, trigger: copie)
        .task { await copia() }
    }

    private var icona: String {
        switch stato {
        case .inCorso: return "link"
        case .copiato: return "checkmark.circle.fill"
        case .senzaPermesso: return "exclamationmark.triangle"
        case .prova: return "rectangle.on.rectangle"
        }
    }

    private var titolo: String {
        switch stato {
        case .inCorso: return "Preparo il codice…"
        case .copiato: return "Codice copiato"
        case .senzaPermesso: return "Codice non pronto"
        case .prova: return "Widget"
        }
    }

    private var spiegazione: String {
        switch stato {
        case .inCorso: return "Un attimo: chiedo al server il permesso per il widget."
        case .copiato: return CollegamentoWidget.istruzione
        case .senzaPermesso: return "Il server non ha risposto. Controlla la connessione e riprova."
        case .prova: return "Con i dati di esempio il widget non si collega: accedi con il tuo account."
        }
    }

    /// Crea il codice (chiede il token del widget se manca) e lo mette negli appunti di questo telefono per 5 minuti.
    private func copia() async {
        if Demo.daLancio {
            // fotografie del simulatore: nessun token, appunti intatti
            stato = .copiato
            return
        }
        if ProvaEsempio.attiva { stato = .prova; return }
        let indirizzo = IndirizzoServer.attuale
        if sessione.utente != nil, TokenWidget.leggi(server: indirizzo) == nil {
            stato = .inCorso
            await TokenWidget.assicura(server: ServerCorrente.condiviso)
        }
        let token = TokenWidget.leggi(server: indirizzo)
        // con gli account serve il token: un codice senza farebbe dire al widget di nuovo «Tocca per collegare»
        if sessione.utente != nil, token == nil { stato = .senzaPermesso; return }
        let codice = CodiceWidget.crea(indirizzo: indirizzo, token: token)
        UIPasteboard.general.setItems([[UTType.plainText.identifier: codice]],
                                      options: [.localOnly: true, .expirationDate: Date().addingTimeInterval(CollegamentoWidget.durataAppunti)])
        stato = .copiato
        copie += 1
    }
}

#Preview {
    CollegaWidgetView()
        .environmentObject(SessioneAccount(server: FinteServer.esempio))
}
