import SwiftUI

/// Le cinque sezioni dell'app. Sull'iPhone sono le schede in basso, sull'iPad (e in orizzontale sui telefoni grandi) la barra laterale.
enum Sezione: String, CaseIterable, Identifiable, Hashable {
    case oggi, formazione, mercato, scambi, lega

    var id: String { rawValue }

    var titolo: String {
        switch self {
        case .oggi: return "Oggi"
        case .formazione: return "Formazione"
        case .mercato: return "Mercato"
        case .scambi: return "Scambi"
        case .lega: return "Lega"
        }
    }

    var icona: String {
        switch self {
        case .oggi: return "calendar"
        case .formazione: return "sportscourt"
        case .mercato: return "bag"
        case .scambi: return "arrow.left.arrow.right"
        case .lega: return "person.3"
        }
    }

    /// Cmd+1 ... Cmd+5 con la tastiera (iPad con tastiera, iPhone con tastiera Bluetooth).
    var scorciatoia: KeyEquivalent {
        switch self {
        case .oggi: return "1"
        case .formazione: return "2"
        case .mercato: return "3"
        case .scambi: return "4"
        case .lega: return "5"
        }
    }
}

/// Stato condiviso della navigazione: sezione aperta e, se serve, un giocatore da aprire (da Spotlight).
@MainActor
final class Navigazione: ObservableObject {
    @Published var sezione: Sezione = .oggi
    @Published var giocatoreDaAprire: Int?

    /// Apre una sezione o la scheda di un giocatore (da Spotlight o da un indirizzo schieraxi://).
    func vai(a destinazione: Destinazione) {
        switch destinazione {
        case .sezione(let s):
            sezione = s
        case .giocatore(let id):
            sezione = .mercato
            giocatoreDaAprire = id
        }
    }
}

/// Radice dell'app: schede in basso con larghezza stretta, barra laterale con larghezza ampia.
struct RadiceView: View {
    @Environment(\.horizontalSizeClass) private var classe
    @EnvironmentObject private var nav: Navigazione
    @EnvironmentObject private var modello: AppModel

    var body: some View {
        Group {
            if classe == .regular {
                barraLaterale
            } else {
                schede
            }
        }
        .tint(Color.verde)
        .task { await Aggiornamento.riprogrammaScadenza() }   // a ogni apertura
    }

    private var schede: some View {
        TabView(selection: $nav.sezione) {
            ForEach(Sezione.allCases) { s in
                vista(s)
                    .tabItem { Label(s.titolo, systemImage: s.icona) }
                    .tag(s)
            }
        }
    }

    private var barraLaterale: some View {
        NavigationSplitView {
            List(selection: Binding<Sezione?>(get: { nav.sezione }, set: { if let s = $0 { nav.sezione = s } })) {
                ForEach(Sezione.allCases) { s in
                    Label(s.titolo, systemImage: s.icona)
                        .tag(s)
                        .frame(minHeight: 44)
                        .hoverEffect(.highlight)
                }
            }
            .navigationTitle("SchieraXI")
        } detail: {
            vista(nav.sezione)
        }
    }

    @ViewBuilder
    private func vista(_ s: Sezione) -> some View {
        switch s {
        case .oggi: OggiView(vm: modello.oggi)
        case .formazione: FormazioneView(vm: modello.formazione)
        case .mercato: MercatoView()
        case .scambi: ScambiView()
        case .lega: LegaView()
        }
    }
}
