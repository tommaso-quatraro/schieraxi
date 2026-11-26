import SwiftUI

/// «Collega il widget»: si apre dal tocco sul widget non collegato (`schieraxi://widget/collega`), dalla configurazione guidata e
/// dalla riga «Widget» delle Impostazioni. Quell'indirizzo lo può aprire anche un'altra app o una pagina: per questo la schermata,
/// appena aperta, non fa niente e aspetta il tocco su «Collega» (#482, logica in `CollegaWidgetModello`). Al tocco prova il
/// collegamento AUTOMATICO (chiede il token del widget se manca e lo passa con App Group o Keychain condiviso): se va, non c'è niente
/// da copiare. Solo se non va crea il codice di collegamento (indirizzo + token del WIDGET `fw_`, mai quello della sessione) e lo
/// mette negli appunti di QUESTO telefono (niente Appunti universali) per 2 minuti; l'utente lo incolla una volta in
/// «Modifica widget» > «Collegamento manuale».
struct CollegaWidgetView: View {
    @EnvironmentObject private var sessione: SessioneAccount
    @Environment(\.dismiss) private var chiudi
    @State private var modello = CollegaWidgetModello()
    /// Il collegamento in corso: «Annulla» o il foglio chiuso lo fermano (niente codice negli appunti dopo).
    @State private var lavoro: Task<Void, Never>?
    /// Il simbolo in alto segue la dimensione del testo.
    @ScaledMetric(relativeTo: .largeTitle) private var dimensioneSimbolo: CGFloat = 44

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 18) {
                    Image(systemName: icona)
                        .font(.system(size: dimensioneSimbolo))
                        .symbolRenderingMode(.hierarchical)
                        .foregroundStyle(modello.stato == .senzaPermesso ? Color.attenzione : Color.verde)
                        .accessibilityHidden(true)
                    Text(titolo).font(.title2.bold()).multilineTextAlignment(.center)
                    Text(spiegazione).font(.body).foregroundStyle(Color.testoSecondario).multilineTextAlignment(.center)
                        .fixedSize(horizontal: false, vertical: true)
                    if let azione {
                        Button(action: collega) {
                            Label(azione.testo, systemImage: azione.simbolo)
                                .frame(maxWidth: .infinity, minHeight: Tema.areaTocco)
                        }
                        .pulsanteVetro(prominente: attesaDelTocco)
                        .keyboardShortcut(attesaDelTocco ? KeyboardShortcut.defaultAction : nil)
                        .disabled(modello.stato == .inCorso)
                    }
                    Button(action: chiudiFoglio) {
                        Text(attesaDelTocco ? "Annulla" : "Fatto").frame(maxWidth: .infinity, minHeight: Tema.areaTocco)
                    }
                    .pulsanteVetro(prominente: !attesaDelTocco)
                    .keyboardShortcut(attesaDelTocco ? .cancelAction : .defaultAction)
                    if modello.stato == .copiato || modello.stato == .senzaPermesso {
                        Text("Il codice permette al widget solo di leggere la tua formazione e vale 90 giorni. Non mandarlo a nessuno.")
                            .font(.footnote).foregroundStyle(Color.testoSecondario).multilineTextAlignment(.center)
                            .fixedSize(horizontal: false, vertical: true)
                    }
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
        .sensoryFeedback(.success, trigger: modello.riuscite)
        // chiuso trascinando in basso: si ferma anche il collegamento in corso
        .onDisappear(perform: fermaIlLavoro)
    }

    /// Il tocco su «Collega» (o «Copia di nuovo», «Riprova»): solo da qui partono collegamento e copia del codice.
    private func collega() {
        let conAccount = sessione.utente != nil
        lavoro = Task { await modello.collega(conAccount: conAccount) }
    }

    private func chiudiFoglio() {
        fermaIlLavoro()
        chiudi()
    }

    private func fermaIlLavoro() {
        lavoro?.cancel()
        lavoro = nil
    }

    /// La schermata aspetta ancora il tocco su «Collega» (o lo sta eseguendo).
    private var attesaDelTocco: Bool {
        modello.stato == .pronto || modello.stato == .inCorso
    }

    /// Il pulsante dell'azione, se in questo stato ce n'è uno.
    private var azione: (testo: String, simbolo: String)? {
        switch modello.stato {
        case .pronto, .inCorso: ("Collega", "link")
        case .copiato: ("Copia di nuovo", "doc.on.doc")
        case .senzaPermesso: ("Riprova", "arrow.clockwise")
        case .automatico, .prova: nil
        }
    }

    private var icona: String {
        switch modello.stato {
        case .pronto, .inCorso: "link"
        case .automatico, .copiato: "checkmark.circle.fill"
        case .senzaPermesso: "exclamationmark.triangle"
        case .prova: "rectangle.on.rectangle"
        }
    }

    private var titolo: String {
        switch modello.stato {
        case .pronto: "Collega il widget"
        case .inCorso: "Collego il widget…"
        case .automatico: "Widget collegato"
        case .copiato: "Codice copiato"
        case .senzaPermesso: "Codice non pronto"
        case .prova: "Widget"
        }
    }

    private var spiegazione: String {
        switch modello.stato {
        case .pronto: "Il widget legge la tua formazione da SchieraXI. Tocca «Collega» per dargli il permesso."
        case .inCorso: "Un attimo: chiedo al server il permesso per il widget."
        case .automatico: "Il widget si collega da solo e si aggiorna tra poco. Non serve copiare niente."
        case .copiato: CollegamentoWidget.istruzione + " " + Self.durataNegliAppunti
        case .senzaPermesso: "Il server non ha risposto. Controlla la connessione e riprova."
        case .prova: "Con i dati di esempio il widget non si collega: accedi con il tuo account."
        }
    }

    /// «Il codice resta negli appunti per 2 minuti.»
    private static var durataNegliAppunti: String {
        let minuti = max(1, Int((CollegamentoWidget.durataAppunti / 60).rounded()))
        return "Il codice resta negli appunti per \(minuti) \(minuti == 1 ? "minuto" : "minuti")."
    }
}

#Preview {
    CollegaWidgetView()
        .environmentObject(SessioneAccount(server: FinteServer.esempio))
}
