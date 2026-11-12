import SwiftUI
import TipKit

/// Le quattro sezioni dell'app (la formazione al centro). Sull'iPhone sono le schede in basso, sull'iPad (e in orizzontale sui
/// telefoni grandi) la barra laterale. Squadra ha le rose, Altro il diario e le regole.
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

    /// Da un nome scritto (indirizzi `schieraxi://`, «Da fare», scelta salvata). I nomi delle sezioni e delle pagine tolte
    /// continuano a funzionare e aprono la scheda più vicina che resta (#634, come la web): Mercato è Squadra, Scambi e Lega sono Altro.
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
    /// «Collega il widget» (`schieraxi://widget/collega`, il tocco sul widget non collegato, o la configurazione guidata).
    @Published var collegaWidgetAperto = false
    /// La configurazione guidata («Primo avvio»): parte da sola senza rose, si riapre dalla lista «Da fare» di Oggi.
    @Published var guidaAperta = false {
        // riaperta: la prossima chiusura torna a essere dell'utente
        didSet { if guidaAperta { guidaChiusaDallApp = false } }
    }
    /// Una pagina di Squadra o di Altro da aprire (da un indirizzo `schieraxi://` o da Oggi): la radice la apre nella scheda giusta.
    @Published var paginaDaAprire: PaginaLega?
    /// È arrivato un file o un'immagine da un'altra app (Condividi, «Apri con SchieraXI»): all'apertura la configurazione guidata
    /// non parte da sola, per non coprire l'importazione o la scelta dello stemma (come l'arrivo da Condividi della web).
    /// Torna falso quando l'arrivo è finito (`controllaFineArrivo`) o si esce dall'account (`uscitoDallAccount`).
    private(set) var apertaDaFuori = false
    /// La guida l'ha chiusa l'app e non l'utente (un file o un'immagine da fuori, la sessione cambiata): alla chiusura del
    /// foglio i passi rimasti non diventano saltati.
    private(set) var guidaChiusaDallApp = false
    /// Il foglio della guida è sullo schermo: dalla comparsa alla fine della chiusura (`guidaComparsa`, `guidaSparita`); si
    /// azzera anche quando la chiude l'app, così una scomparsa mancata non fa aspettare per sempre le immagini.
    private var guidaSulloSchermo = false
    /// Un'immagine arrivata con la guida aperta, in arrivo o in chiusura: il suo foglio si apre quando quello della guida è
    /// sparito, uno alla volta.
    private var immagineInAttesa: ImmagineRicevuta?
    /// Quanto si aspetta la scomparsa del foglio della guida prima di aprire comunque l'immagine in attesa (se non arriva, per
    /// esempio perché il foglio non era mai comparso). I test la accorciano.
    var attesaFoglio: Duration = .seconds(1)

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
    /// Con la guida aperta, la guida si chiude (senza segnare saltati i passi) e lascia il posto all'importazione o allo stemma.
    func apriFile(_ url: URL) {
        guard url.isFileURL else { return }
        apertaDaFuori = true
        // guida aperta (anche col foglio non ancora comparso), in chiusura o con un'immagine già in attesa: si aspetta il suo turno
        let aspetta = guidaAperta || guidaSulloSchermo || immagineInAttesa != nil
        chiudiGuidaDallApp()
        if Self.eImmagine(url) {
            let ricevuta = ImmagineRicevuta(url: url)
            if aspetta { mettiInAttesa(ricevuta) } else { immagineRicevuta = ricevuta }
        } else {
            fileDaImportare = url
        }
    }

    /// Chiude la guida senza che l'abbia scelto l'utente (un file da fuori, la sessione cambiata o il contenitore ricostruito):
    /// i passi restano come erano. Se si stava già chiudendo per scelta dell'utente, la scelta resta sua.
    func chiudiGuidaDallApp() {
        guidaSulloSchermo = false
        guard guidaAperta else { return }
        guidaChiusaDallApp = true
        guidaAperta = false
    }

    /// Il foglio della guida è comparso.
    func guidaComparsa() {
        guidaSulloSchermo = true
    }

    /// Il foglio della guida è sparito (chiusura finita): si apre l'immagine arrivata nel frattempo.
    func guidaSparita() {
        guidaSulloSchermo = false
        apriImmagineInAttesa()
    }

    /// L'immagine aspetta la scomparsa del foglio della guida; se non arriva entro `attesaFoglio`, si apre lo stesso.
    private func mettiInAttesa(_ ricevuta: ImmagineRicevuta) {
        immagineInAttesa = ricevuta
        let attesa = attesaFoglio
        Task { [weak self] in
            try? await Task.sleep(for: attesa)
            self?.apriImmagineInAttesa()
        }
    }

    private func apriImmagineInAttesa() {
        guard !guidaAperta, let attesa = immagineInAttesa else { return }
        immagineInAttesa = nil
        immagineRicevuta = attesa
    }

    /// L'arrivo da fuori è finito quando il file è stato preso dall'importazione e la pagina «Aggiorna le rose» non è più aperta
    /// (salvato o lasciato), e il foglio dello stemma è chiuso: da lì la guida può di nuovo partire da sola, a un nuovo accesso.
    func controllaFineArrivo(importaAperta: Bool) {
        guard apertaDaFuori, fileDaImportare == nil, immagineRicevuta == nil, immagineInAttesa == nil, !importaAperta else { return }
        apertaDaFuori = false
    }

    /// Si è usciti dall'account (anche per la sessione scaduta): un arrivo da fuori già aperto non conta più, così al prossimo
    /// accesso la guida può partire da sola. Un file o un'immagine ancora da aprire restano: si aprono dopo l'accesso.
    func uscitoDallAccount() {
        controllaFineArrivo(importaAperta: false)
    }

    /// Le immagini che si accettano per stemma e divisa (il controllo vero sul contenuto è al caricamento).
    static func eImmagine(_ url: URL) -> Bool {
        ["png", "jpg", "jpeg", "heic", "heif", "webp"].contains(url.pathExtension.lowercased())
    }

    /// `contesto`: la scheda si apre dalla Formazione, con la previsione già letta e «Sostituisci» (come la web).
    func apriScheda(_ id: Int, contesto: ContestoScheda? = nil) {
        Suggerimenti.schedaAperta()
        scheda = IdGiocatore(id: id, contesto: contesto)
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
        case .collegaWidget:
            collegaWidgetAperto = true
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
                // niente pallino sulle schede: le novità si leggono in Impostazioni > Informazioni
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
        .environment(\.vediFormazioneDi) { nome in
            modello.formazione.vediSquadra(nome)
            nav.sezione = .formazione
        }
        .sheet(isPresented: $nav.impostazioniAperte) {
            ImpostazioniView(vm: modello.lega)
                .tint(Color.verde)
                // Su iPad un foglio ampio, come le Impostazioni di sistema.
                .presentationSizing(.page)
        }
        .sheet(isPresented: $nav.collegaWidgetAperto) {
            CollegaWidgetView()
                .tint(Color.verde)
        }
        .sheet(item: $nav.immagineRicevuta) { r in
            ImmagineRicevutaView(ricevuta: r, server: modello.server)
                .tint(Color.verde)
        }
        // «Sostituisci» nella scheda chiude il foglio: la scelta del sostituto si apre quando è sparito (un foglio alla volta)
        .sheet(item: $nav.scheda, onDismiss: { modello.formazione.apriSostituzioneInAttesa() }) { g in
            GiocatoreSheet(id: g.id, server: modello.server, contesto: g.contesto) {
                modello.formazione.chiediSostituzione(g.id)
                nav.scheda = nil
            }
            .navigationTransition(.zoom(sourceID: g.id, in: zoom))
            .presentationDragIndicator(.visible)
            .tint(Color.verde)
        }
        .onChange(of: nav.fileDaImportare) { _, nuovo in
            if nuovo != nil { vaiAllImportazione() } else { controllaFineArrivo() }
        }
        .onAppear { if nav.fileDaImportare != nil { vaiAllImportazione() } }
        // l'arrivo da un'altra app finisce lasciando «Aggiorna le rose» o chiudendo il foglio dello stemma
        .onChange(of: nav.immagineRicevuta) { _, nuova in
            if nuova == nil { controllaFineArrivo() }
        }
        .onReceive(modello.lega.$percorsoSquadra) { percorso in
            nav.controllaFineArrivo(importaAperta: percorso.contains(.importa))
        }
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

    private func controllaFineArrivo() {
        nav.controllaFineArrivo(importaAperta: modello.lega.percorsoSquadra.contains(.importa))
    }

    /// Una pagina chiesta da fuori («Da fare», «Apri il Diario»): si apre nella scheda a cui appartiene.
    private func apriPaginaRichiesta() {
        guard let pagina = nav.paginaDaAprire else { return }
        nav.paginaDaAprire = nil
        nav.sezione = modello.lega.apri([pagina])
    }

    @ViewBuilder
    private func vista(_ s: Sezione) -> some View {
        switch s {
        case .oggi: OggiView(vm: modello.oggi)
        case .formazione:
            // dalla Formazione la scheda si apre subito con la previsione già letta, il perché del titolare e «Sostituisci»
            FormazioneView(vm: modello.formazione)
                .environment(\.apriGiocatore) { id in nav.apriScheda(id, contesto: modello.formazione.contestoScheda(id)) }
        case .squadra: LegaView(vm: modello.lega, ambito: .squadra)
        case .altro: LegaView(vm: modello.lega, ambito: .altro)
        }
    }
}
