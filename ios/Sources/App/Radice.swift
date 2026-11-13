import SwiftUI
import TipKit

/// Le voci della barra, come la web dal 12/11/2026 (#673 passo 3, web #675): Formazione, Giornate, Impostazioni, più la ricerca di un
/// giocatore. Squadra e Altro non ci sono più: rose e regole stanno in Impostazioni > La mia lega. Sull'iPhone sono le schede in basso,
/// sull'iPad (e in orizzontale sui telefoni grandi) la barra laterale. La ricerca (`cerca`) è la voce con il ruolo di ricerca: non è fra
/// le tre (`allCases`), che sono anche le voci del menu «Vai a» con Cmd+1…3.
enum Sezione: String, CaseIterable, Identifiable, Hashable {
    case formazione, giornate, impostazioni, cerca

    /// Le tre voci della barra, nell'ordine della web (la ricerca ha la sua, a parte).
    static let allCases: [Sezione] = [.formazione, .giornate, .impostazioni]

    var id: String { rawValue }

    var titolo: String {
        switch self {
        case .formazione: return Catalogo.Nav.formazione
        case .giornate: return Catalogo.Nav.giornate
        case .impostazioni: return Catalogo.Shell.impostazioni
        case .cerca: return Catalogo.Shell.cerca
        }
    }

    var icona: String {
        switch self {
        case .formazione: return "sportscourt"
        case .giornate: return "calendar"
        case .impostazioni: return "gearshape"
        case .cerca: return "magnifyingglass"
        }
    }

    /// Cmd+1 ... Cmd+3 con la tastiera (iPad con tastiera, iPhone con tastiera Bluetooth), per le tre voci del menu «Vai a».
    var scorciatoia: KeyEquivalent {
        switch self {
        case .formazione: return "1"
        case .giornate: return "2"
        case .impostazioni: return "3"
        case .cerca: return "f"
        }
    }

    /// All'apertura l'app torna qui: solo Formazione e Giornate (Impostazioni e ricerca si aprono quando servono).
    var siRicorda: Bool { self == .formazione || self == .giornate }

    /// Da un nome scritto (indirizzi `schieraxi://`, «Da fare», scelta salvata). I nomi delle sezioni e delle pagine tolte
    /// continuano a funzionare e aprono la voce più vicina che resta, come `dove` della web: Oggi è la Formazione (#673), il Diario è
    /// Giornate (#673 passo 2), Squadra, Mercato, Altro, Lega e Scambi sono le Impostazioni (#673 passo 3; `Collegamenti` le porta
    /// su La mia lega).
    static func da(nome: String?) -> Sezione? {
        switch (nome ?? "").lowercased() {
        case "oggi", "formazione": return .formazione
        case "giornate", "diario": return .giornate
        case "impostazioni", "squadra", "mercato", "altro", "lega", "scambi": return .impostazioni
        default: return nil
        }
    }
}

/// Stato condiviso della navigazione: sezione aperta e, se serve, un giocatore da aprire (da Spotlight).
@MainActor
final class Navigazione: ObservableObject {
    /// La sezione aperta; si ricorda l'ultima fra Formazione e Giornate: all'apertura l'app torna lì.
    @Published var sezione: Sezione = .formazione {
        didSet { if !Demo.attivo, sezione.siRicorda { UserDefaults.standard.set(sezione.rawValue, forKey: "ultimaSezione") } }
    }
    /// Un file delle rose arrivato da un'altra app («Apri con SchieraXI», Condividi): Impostazioni > Aggiorna le rose lo importa.
    @Published var fileDaImportare: URL?
    /// Un'immagine arrivata da un'altra app («Apri con SchieraXI»): si chiede se è lo stemma o la divisa e di quale squadra.
    @Published var immagineRicevuta: ImmagineRicevuta?
    /// La scheda di un giocatore aperta sopra la schermata corrente (tocco su una riga della Formazione, di una rosa...).
    @Published var scheda: IdGiocatore?
    /// La parte delle Impostazioni da portare in vista (La mia lega per gli indirizzi di Squadra e Altro): la pagina la prende e la
    /// rimette a nil.
    @Published var parteImpostazioni: ParteImpostazioni?
    /// «Collega il widget» (`schieraxi://widget/collega`, il tocco sul widget non collegato, o la configurazione guidata).
    @Published var collegaWidgetAperto = false
    /// La configurazione guidata («Primo avvio»): parte da sola senza rose, si riapre dalla lista «Da fare» di Oggi.
    @Published var guidaAperta = false {
        // riaperta: la prossima chiusura torna a essere dell'utente
        didSet { if guidaAperta { guidaChiusaDallApp = false } }
    }
    /// Una pagina delle Impostazioni da aprire (da un indirizzo `schieraxi://` o dalle decisioni della Formazione): la radice la apre.
    @Published var paginaDaAprire: PaginaImpostazioni?
    /// La giornata (numero di Serie A) da aprire nella pagina Giornate («Com'è andata» della Formazione): la pagina la prende e la
    /// rimette a nil.
    @Published var giornataDaAprire: Int?
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

    /// Dove si apre l'app: l'ultima sezione in cui si era fra Formazione e Giornate (una scelta vecchia in `sezioneAvvio` vale ancora,
    /// ma all'avvio si toglie). Chi aveva lasciato l'app su Squadra o su Altro si ritrova sulla Formazione.
    static func sezioneDiAvvio(_ memoria: UserDefaults = .standard) -> Sezione {
        let scelta = memoria.string(forKey: "sezioneAvvio") ?? "ultima"
        let nome = scelta == "ultima" ? memoria.string(forKey: "ultimaSezione") : scelta
        guard let sezione = Sezione.da(nome: nome), sezione.siRicorda else { return .formazione }
        return sezione
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

    /// La pagina Giornate, aperta sulla giornata `giornata` (numero di Serie A) se c'è, come `vaiGiornate` della web.
    func apriGiornate(_ giornata: Int?) {
        giornataDaAprire = giornata
        sezione = .giornate
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
        case .impostazioni(let parte):
            parteImpostazioni = parte
            sezione = .impostazioni
        case .collegaWidget:
            collegaWidgetAperto = true
        }
    }
}

/// Radice dell'app: una `TabView` moderna con le tre voci e la ricerca. Sull'iPhone è la barra delle schede in basso (con il Liquid
/// Glass di iOS 26 si riduce scorrendo e la ricerca è il tondo a destra); sull'iPad diventa in alto una barra che si apre in barra
/// laterale (`sidebarAdaptable`), con tastiera e puntatore, come le app di sistema.
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
            // la ricerca di un giocatore, come la lente della web: il nome della voce lo dà iOS («Cerca»)
            Tab(value: Sezione.cerca, role: .search) {
                NavigationStack {
                    RicercaGiocatoreView(server: modello.server)
                        .destinazioniGiocatore(server: modello.server)
                }
            }
        }
        .tabViewStyle(.sidebarAdaptable)
        .onAppear { apriPaginaRichiesta() }
        .onChange(of: nav.paginaDaAprire) { _, _ in apriPaginaRichiesta() }
        // un indirizzo che porta a una parte delle Impostazioni (La mia lega) torna alla pagina, anche se sopra ce n'era un'altra
        .onChange(of: nav.parteImpostazioni) { _, parte in if parte != nil { modello.lega.percorso = [] } }
        .barraSchedeCheSiRiduce()
        // Il conto alla rovescia sta nell'intestazione di Oggi (e nel widget): sotto la barra delle schede faceva due barre sovrapposte.
        .tint(Color.verde)
        .preferredColorScheme(tema == "chiaro" ? ColorScheme.light : tema == "scuro" ? ColorScheme.dark : nil)
        .transaction { if animazioniRidotte { $0.animation = nil } }
        .environment(\.server, modello.server)
        .environment(\.spazioZoom, zoom)
        .environment(\.apriGiocatore) { nav.apriScheda($0) }
        .environment(\.vaiASezione) { nav.sezione = $0 }
        .environment(\.apriImpostazioni) { nav.sezione = .impostazioni }
        .environment(\.funzioni, modello.funzioni.stato)
        .environment(\.apriRosaDi) { nome in
            nav.sezione = modello.lega.apri([.rosa(nome)])
        }
        .environment(\.apriImportazione) {
            nav.sezione = modello.lega.apri([.importa])
        }
        .environment(\.vediFormazioneDi) { nome in
            modello.formazione.vediSquadra(nome)
            nav.sezione = .formazione
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
        .onReceive(modello.lega.$percorso) { percorso in
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
        nav.controllaFineArrivo(importaAperta: modello.lega.percorso.contains(.importa))
    }

    /// Una pagina chiesta da fuori (le decisioni della Formazione, un indirizzo): si apre nelle Impostazioni.
    private func apriPaginaRichiesta() {
        guard let pagina = nav.paginaDaAprire else { return }
        nav.paginaDaAprire = nil
        nav.sezione = modello.lega.apri([pagina])
    }

    @ViewBuilder
    private func vista(_ s: Sezione) -> some View {
        switch s {
        case .formazione:
            // la Formazione unica (#673): formazione e scelta da `formazione`, la giornata (testa, decisioni, widget e promemoria) da
            // `oggi`. Dalla Formazione la scheda si apre subito con la previsione già letta, il perché del titolare e «Sostituisci»
            FormazioneView(vm: modello.formazione, oggi: modello.oggi)
                .environment(\.apriGiocatore) { id in nav.apriScheda(id, contesto: modello.formazione.contestoScheda(id)) }
        case .giornate: GiornateView(vm: modello.giornate)
        case .impostazioni: ImpostazioniView(vm: modello.lega)
        case .cerca: EmptyView()   // la ricerca ha la sua voce, con il suo contenuto (sopra)
        }
    }
}
