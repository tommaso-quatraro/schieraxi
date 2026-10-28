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
    /// La sezione aperta; si ricorda l'ultima per «All'apertura mostra: l'ultima sezione» (Lega > Aspetto).
    @Published var sezione: Sezione = .oggi {
        didSet { if !Demo.attivo { UserDefaults.standard.set(sezione.rawValue, forKey: "ultimaSezione") } }
    }
    @Published var giocatoreDaAprire: Int?
    /// La scheda di un giocatore aperta sopra la schermata corrente (tocco su una riga di Oggi, Formazione, Lega...).
    @Published var scheda: IdGiocatore?

    init() {
        if !Demo.attivo { sezione = Self.sezioneDiAvvio() }
    }

    /// Dove si apre l'app: la sezione scelta in Lega > Aspetto, oppure (predefinito) l'ultima in cui si era.
    static func sezioneDiAvvio(_ memoria: UserDefaults = .standard) -> Sezione {
        let scelta = memoria.string(forKey: "sezioneAvvio") ?? "ultima"
        let nome = scelta == "ultima" ? memoria.string(forKey: "ultimaSezione") : scelta
        return nome.flatMap { Sezione(rawValue: $0) } ?? .oggi
    }

    func apriScheda(_ id: Int) { scheda = IdGiocatore(id: id) }

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
    /// Lega > Aspetto: colore principale e animazioni. Cambiando il colore l'albero delle viste si ricostruisce (`.id`), i dati restano.
    @AppStorage("accento") private var accento = "verde"
    @AppStorage("animazioniRidotte") private var animazioniRidotte = false
    /// Barra laterale visibile o no (di solito decide iOS; solo la demo può nasconderla per le fotografie).
    @State private var colonne: NavigationSplitViewVisibility = Demo.attivo && Demo.argomento("DEMO_BARRA") == "nascosta" ? .detailOnly : .automatic

    var body: some View {
        Group {
            if classe == .regular {
                barraLaterale
            } else {
                schede
            }
        }
        .tint(Color.verde)
        .id(accento)
        .transaction { if animazioniRidotte { $0.animation = nil } }
        .environment(\.server, modello.server)
        .environment(\.apriGiocatore) { nav.apriScheda($0) }
        .environment(\.vaiASezione) { nav.sezione = $0 }
        .environment(\.apriNovita) {
            modello.lega.percorso = [.novita]
            nav.sezione = .lega
        }
        .environment(\.vediFormazioneDi) { nome in
            modello.formazione.vediSquadra(nome)
            nav.sezione = .formazione
        }
        .sheet(item: $nav.scheda) { g in
            GiocatoreSheet(id: g.id, server: modello.server, contesto: modello.formazione.contestoConfronto)
                .tint(Color.verde)
        }
        .task { await Aggiornamento.riprogrammaScadenza() }   // a ogni apertura
        .task { await Immagini.condivise.caricaElenchi() }    // chi ha la foto, stemmi e maglie delle squadre
        .onReceive(NotificationCenter.default.publisher(for: .aggiornaTutto)) { _ in
            Task { await Immagini.condivise.caricaElenchi() }
        }
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
        NavigationSplitView(columnVisibility: $colonne) {
            List(selection: Binding<Sezione?>(get: { nav.sezione }, set: { if let s = $0 { nav.sezione = s } })) {
                ForEach(Sezione.allCases) { s in
                    // icona in una colonna di larghezza fissa: «person.3» è più larga delle altre e spostava il testo
                    Label {
                        Text(s.titolo)
                    } icon: {
                        Image(systemName: s.icona).resizable().scaledToFit().frame(width: 28, height: 22)
                    }
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
        case .mercato: MercatoView(vm: modello.mercato)
        case .scambi: ScambiView(vm: modello.scambi)
        case .lega: LegaView(vm: modello.lega)
        }
    }
}
