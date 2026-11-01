import SwiftUI
import TipKit

/// Le quattro sezioni dell'app (la «dieta delle funzioni»: la formazione al centro). Sull'iPhone sono le schede in basso,
/// sull'iPad (e in orizzontale sui telefoni grandi) la barra laterale. Mercato, Scambi e Lega sono diventati pagine dentro Squadra e Altro.
enum Sezione: String, CaseIterable, Identifiable, Hashable {
    case oggi, formazione, squadra, altro

    var id: String { rawValue }

    var titolo: String {
        switch self {
        case .oggi: return "Oggi"
        case .formazione: return "Formazione"
        case .squadra: return "Squadra"
        case .altro: return "Altro"
        }
    }

    var icona: String {
        switch self {
        case .oggi: return "calendar"
        case .formazione: return "sportscourt"
        case .squadra: return "person.3"
        case .altro: return "ellipsis.circle"
        }
    }

    /// Cmd+1 ... Cmd+4 con la tastiera (iPad con tastiera, iPhone con tastiera Bluetooth).
    var scorciatoia: KeyEquivalent {
        switch self {
        case .oggi: return "1"
        case .formazione: return "2"
        case .squadra: return "3"
        case .altro: return "4"
        }
    }

    /// Da un nome scritto (indirizzi `schieraxi://`, «Da fare», scelta salvata). I nomi delle vecchie cinque sezioni
    /// continuano a funzionare: Mercato è Squadra, Scambi e Lega sono in Altro.
    static func da(nome: String?) -> Sezione? {
        switch (nome ?? "").lowercased() {
        case "oggi": return .oggi
        case "formazione": return .formazione
        case "squadra", "mercato": return .squadra
        case "altro", "lega", "scambi": return .altro
        default: return nil
        }
    }
}

/// Stato condiviso della navigazione: sezione aperta e, se serve, un giocatore da aprire (da Spotlight).
@MainActor
final class Navigazione: ObservableObject {
    /// La sezione aperta; si ricorda l'ultima: all'apertura l'app torna lì.
    @Published var sezione: Sezione = .oggi {
        didSet { if !Demo.attivo { UserDefaults.standard.set(sezione.rawValue, forKey: "ultimaSezione") } }
    }
    /// Un file delle rose arrivato da un'altra app («Apri con SchieraXI», Condividi): Lega > Aggiorna le rose lo importa.
    @Published var fileDaImportare: URL?
    /// Un'immagine arrivata da un'altra app («Apri con SchieraXI»): si chiede se è lo stemma o la divisa e di quale squadra.
    @Published var immagineRicevuta: ImmagineRicevuta?
    /// La scheda di un giocatore aperta sopra la schermata corrente (tocco su una riga di Oggi, Formazione, Lega...).
    @Published var scheda: IdGiocatore?
    /// Il foglio delle Impostazioni (l'ingranaggio in testata, o `schieraxi://impostazioni`).
    @Published var impostazioniAperte = false
    /// La configurazione guidata («Primo avvio»): parte da sola senza rose, si riapre dalla lista «Da fare» di Oggi.
    @Published var guidaAperta = false
    /// Una pagina di Squadra o di Altro da aprire (da un indirizzo `schieraxi://` o da Oggi): la radice la apre nella scheda giusta.
    @Published var paginaDaAprire: PaginaLega?

    init() {
        if !Demo.attivo { sezione = Self.sezioneDiAvvio() }
    }

    /// Dove si apre l'app: l'ultima sezione in cui si era (una scelta vecchia in `sezioneAvvio` vale ancora, ma all'avvio si toglie).
    static func sezioneDiAvvio(_ memoria: UserDefaults = .standard) -> Sezione {
        let scelta = memoria.string(forKey: "sezioneAvvio") ?? "ultima"
        let nome = scelta == "ultima" ? memoria.string(forKey: "ultimaSezione") : scelta
        return Sezione.da(nome: nome) ?? .oggi
    }

    /// Un file arrivato da fuori: si accetta solo se l'estensione è di quelle delle rose (il controllo vero è all'importazione).
    func apriFile(_ url: URL) {
        guard url.isFileURL else { return }
        if Self.eImmagine(url) {
            immagineRicevuta = ImmagineRicevuta(url: url)
        } else {
            fileDaImportare = url
        }
    }

    /// Le immagini che si accettano per stemma e divisa (il controllo vero sul contenuto è al caricamento).
    static func eImmagine(_ url: URL) -> Bool {
        ["png", "jpg", "jpeg", "heic", "heif", "webp"].contains(url.pathExtension.lowercased())
    }

    func apriScheda(_ id: Int) {
        Suggerimenti.schedaAperta()
        scheda = IdGiocatore(id: id)
    }

    /// Apre una sezione o la scheda di un giocatore (da Spotlight o da un indirizzo schieraxi://).
    func vai(a destinazione: Destinazione) {
        switch destinazione {
        case .sezione(let s):
            sezione = s
        case .giocatore(let id):
            apriScheda(id)
        case .pagina(let pagina):
            paginaDaAprire = pagina
        case .impostazioni:
            impostazioniAperte = true
        }
    }
}

/// Radice dell'app: una `TabView` moderna. Sull'iPhone è la barra delle schede in basso (con il Liquid Glass di iOS 26 si riduce
/// scorrendo e ha l'accessorio con il conto alla rovescia); sull'iPad diventa in alto una barra che si apre in barra laterale
/// (`sidebarAdaptable`), con tastiera e puntatore, come le app di sistema.
struct RadiceView: View {
    @EnvironmentObject private var nav: Navigazione
    @EnvironmentObject private var modello: AppModel
    /// Impostazioni > Aspetto: tema e animazioni.
    @AppStorage("animazioniRidotte") private var animazioniRidotte = false
    @AppStorage("tema") private var tema = "auto"   // auto, chiaro, scuro
    /// Punto di partenza e arrivo della transizione a zoom tra una riga di giocatore e la sua scheda.
    @Namespace private var zoom

    var body: some View {
        TabView(selection: $nav.sezione) {
            ForEach(Sezione.allCases) { s in
                Tab(value: s) {
                    vista(s)
                } label: {
                    Label(s.titolo, systemImage: s.icona)
                }
                // niente pallino sulle schede: le novità dell'app le annuncia una riga in Oggi, che porta ad Altro > Novità
            }
        }
        .tabViewStyle(.sidebarAdaptable)
        .onAppear { apriPaginaRichiesta() }
        .onChange(of: nav.paginaDaAprire) { _, _ in apriPaginaRichiesta() }
        .barraSchedeCheSiRiduce()
        // Il conto alla rovescia sta nell'intestazione di Oggi (e nel widget): sotto la barra delle schede faceva due barre sovrapposte.
        .tint(Color.verde)
        .preferredColorScheme(tema == "chiaro" ? ColorScheme.light : tema == "scuro" ? ColorScheme.dark : nil)
        .transaction { if animazioniRidotte { $0.animation = nil } }
        .environment(\.server, modello.server)
        .environment(\.spazioZoom, zoom)
        .environment(\.apriGiocatore) { nav.apriScheda($0) }
        .environment(\.vaiASezione) { nav.sezione = $0 }
        .environment(\.apriImpostazioni) { nav.impostazioniAperte = true }
        .environment(\.funzioni, modello.funzioni.stato)
        .environment(\.apriRosaDi) { nome in
            nav.sezione = modello.lega.apri([.squadre, .rosa(nome)])
        }
        .environment(\.apriImportazione) {
            nav.sezione = modello.lega.apri([.importa])
        }
        .environment(\.apriNovita) {
            nav.sezione = modello.lega.apri([.novita])
        }
        .environment(\.vediFormazioneDi) { nome in
            modello.formazione.vediSquadra(nome)
            nav.sezione = .formazione
        }
        .sheet(isPresented: $nav.impostazioniAperte) {
            ImpostazioniView(vm: modello.lega, funzioni: modello.funzioni)
                .tint(Color.verde)
                // Su iPad un foglio ampio, come le Impostazioni di sistema.
                .presentationSizing(.page)
        }
        .sheet(item: $nav.immagineRicevuta) { r in
            ImmagineRicevutaView(ricevuta: r, server: modello.server)
                .tint(Color.verde)
        }
        .sheet(item: $nav.scheda) { g in
            GiocatoreSheet(id: g.id, server: modello.server, contesto: modello.formazione.contestoConfronto)
                .navigationTransition(.zoom(sourceID: g.id, in: zoom))
                .presentationDragIndicator(.visible)
                .tint(Color.verde)
        }
        .onChange(of: nav.fileDaImportare) { _, nuovo in
            if nuovo != nil { vaiAllImportazione() }
        }
        .onAppear { if nav.fileDaImportare != nil { vaiAllImportazione() } }
        .task { await Aggiornamento.riprogrammaScadenza() }   // a ogni apertura
        .task { await tornaAllIconaPrincipale() }
        .task { await Immagini.condivise.caricaElenchi() }    // chi ha la foto, stemmi e maglie delle squadre
        .task { await modello.funzioni.carica() }             // quali funzioni sono accese (se non risponde: tutte)
        .onReceive(NotificationCenter.default.publisher(for: .aggiornaTutto)) { _ in
            Task { await Immagini.condivise.caricaElenchi() }
            Task { await modello.funzioni.carica() }
        }
    }

    /// L'icona dell'app è una sola: chi ne aveva scelta un'altra (versioni vecchie) torna a quella principale.
    private func tornaAllIconaPrincipale() async {
        guard !Demo.attivo, UIApplication.shared.supportsAlternateIcons, UIApplication.shared.alternateIconName != nil else { return }
        try? await UIApplication.shared.setAlternateIconName(nil)
    }

    private func vaiAllImportazione() {
        nav.sezione = modello.lega.apri([.importa])
    }

    /// Una pagina chiesta da fuori (indirizzo `schieraxi://scambi`, «Da fare»): si apre nella scheda a cui appartiene.
    private func apriPaginaRichiesta() {
        guard let pagina = nav.paginaDaAprire else { return }
        nav.paginaDaAprire = nil
        nav.sezione = modello.lega.apri([pagina])
    }

    @ViewBuilder
    private func vista(_ s: Sezione) -> some View {
        switch s {
        case .oggi: OggiView(vm: modello.oggi)
        case .formazione: FormazioneView(vm: modello.formazione)
        case .squadra: LegaView(vm: modello.lega, mercato: modello.mercato, scambi: modello.scambi, ambito: .squadra)
        case .altro: LegaView(vm: modello.lega, mercato: modello.mercato, scambi: modello.scambi, ambito: .altro)
        }
    }
}
