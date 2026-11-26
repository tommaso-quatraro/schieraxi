import SwiftUI

private struct ApriRosaDiChiave: EnvironmentKey {
    static let defaultValue: ((String) -> Void)? = nil
}

extension EnvironmentValues {
    /// Apre Impostazioni > la rosa di una squadra (dalla Formazione: «Vedi la rosa», «Aggiungi la tua divisa»). `nil` dove non c'è.
    var apriRosaDi: ((String) -> Void)? {
        get { self[ApriRosaDiChiave.self] }
        set { self[ApriRosaDiChiave.self] = newValue }
    }
}

private struct ApriImpostazioniChiave: EnvironmentKey {
    static let defaultValue: (() -> Void)? = nil
}

extension EnvironmentValues {
    /// Apre la voce Impostazioni della barra. `nil` dove non c'è (anteprime, fogli).
    var apriImpostazioni: (() -> Void)? {
        get { self[ApriImpostazioniChiave.self] }
        set { self[ApriImpostazioniChiave.self] = newValue }
    }
}

/// Impostazioni, la terza voce della barra: una pagina sola come la web (#673 passo 3, web #675). In ordine: Avvisi («Avvisi su
/// questo dispositivo», «Ore tranquille»), La mia lega (Aggiorna le rose, La mia squadra, Regole e scadenza, Le altre squadre),
/// Il tuo account, Aspetto, e le righe di Informazioni e di Gestione (solo per chi gestisce il server). Restano solo dell'iPhone il
/// widget, «C'è una versione nuova», la prova con dati di esempio e «Animazioni ridotte». La pila delle pagine vive in
/// `LegaViewModel.percorso`, così un indirizzo o la Formazione possono aprire una pagina (`LegaViewModel.apri`).
struct ImpostazioniView: View {
    @ObservedObject var vm: LegaViewModel
    @StateObject private var avvisi: AvvisiDispositivoViewModel
    @EnvironmentObject private var sessione: SessioneAccount
    @EnvironmentObject private var nav: Navigazione
    @Environment(\.funzioni) private var funzioni
    @Environment(\.dynamicTypeSize) private var dimensione

    init(vm: LegaViewModel) {
        self.vm = vm
        _avvisi = StateObject(wrappedValue: AvvisiDispositivoViewModel(server: vm.server))
    }

    var body: some View {
        NavigationStack(path: $vm.percorso) {
            ScrollViewReader { proxy in
                List {
                    TitoloNellaPagina()
                    // come la web: l'avviso della nuova stagione in cima, solo quando serve
                    if vm.nuovaStagione { bannerStagione }
                    SessioneMinimaSezione(nonRaggiungibile: vm.info.datiSalvati != nil || vm.info.errore != nil)
                    if ProvaEsempio.attiva { SezioneProvaEsempio() }
                    AvvisiDispositivoSezione(vm: avvisi)
                    sezioneLega
                    if let voce = VociImpostazioni.account(nome: nomeAccount) {
                        Section { RigaVoceImpostazioni(voce: voce) }
                    }
                    AspettoSezione()
                    Section { RigaCollegamentoWidget() }
                    NuovaVersioneSezione()
                    Section {
                        ForEach(VociImpostazioni.informazioni(gestisce: sessione.puoAmministrare)) { voce in
                            RigaVoceImpostazioni(voce: voce).id("imp-\(voce.id)")
                        }
                    }
                }
                // sull'iPad una colonna larga come quella della web: interruttori e valori vicini al loro nome (#896)
                .colonnaPagina()
                .scrollContentBackground(.hidden)
                .contentMargins(.bottom, 24, for: .scrollContent)
                .background(Sfondo())
                // con il testo grande la barra è vuota: senza, le righe passavano nitide sotto l'ora (#848)
                .bordoSottoLaBarraVuota()
                // fotografia `impostazioni-fondo`: la fine della pagina, quando le righe della lega sono arrivate (con le righe che
                // arrivano dopo, `demoInFondo` da solo restava in cima)
                .demoScorriA("imp-informazioni", proxy: proxy, schermate: ["impostazioni"], inFondo: true, ancora: .bottom,
                             pronto: vm.squadre.dato != nil)
                // fotografia `impostazioni-aspetto` con il testo grande (#857): `portaInVista` mette a metà schermo la prima riga di
                // Aspetto, che con il testo massimo è più alta di mezzo schermo, e il titolo «Aspetto» restava sopra, sotto l'ora e
                // la fascia. Solo per la foto, dopo `portaInVista` e con le righe della lega arrivate: in cima l'ultima riga di La
                // mia lega, sotto il titolo «Aspetto» e il Tema. Con il testo normale la foto resta com'è.
                .demoScorriA(ultimaRigaLega, proxy: proxy,
                             schermate: TitoloPagina.barraSenzaTitolo(dimensione) ? ["impostazioni-aspetto"] : [],
                             pronto: vm.squadre.dato != nil)
                .refreshable {
                    await vm.carica()
                    await avvisi.carica()
                }
                .onAppear { portaInVista(proxy) }
                .onChange(of: nav.parteImpostazioni) { _, _ in portaInVista(proxy) }
            }
            .titoloPagina(Catalogo.Shell.impostazioni)
            // anche le pagine interne in una colonna larga come quella della web (#896)
            .navigationDestination(for: PaginaImpostazioni.self) { destinazione($0).colonnaPagina() }
            .task { await vm.carica() }
            .task { await avvisi.carica() }
        }
        .schermoProtetto()   // rose, nomi e dati dell'account non devono comparire nell'anteprima del selettore delle app
    }

    /// Il nome sotto «Il tuo account»: solo con gli account e un utente noto (senza, c'è `SessioneMinimaSezione`).
    private var nomeAccount: String? {
        guard sessione.multiutente, let utente = sessione.utente else { return nil }
        return utente.nome
    }

    /// Le righe di La mia lega (`VociImpostazioni.lega`).
    private var vociLega: [VoceImpostazioni] {
        VociImpostazioni.lega(squadre: vm.squadre.dato ?? [], squadreAltrui: funzioni.acceso(Funzione.squadreAltrui))
    }

    /// L'ancora dell'ultima riga di La mia lega: la foto di Aspetto con il testo grande la porta in cima.
    private var ultimaRigaLega: String {
        vociLega.last.map { "imp-\($0.id)" } ?? ParteImpostazioni.aspetto.ancora
    }

    /// La mia lega, con le righe di `VociImpostazioni.lega`.
    private var sezioneLega: some View {
        Section(titolo: Catalogo.Imp.lega) {
            ForEach(vociLega) { voce in
                RigaVoceImpostazioni(voce: voce).id("imp-\(voce.id)")
            }
        }
    }

    private var bannerStagione: some View {
        Section {
            NavigationLink(value: PaginaImpostazioni.stagione) {
                VStack(alignment: .leading, spacing: 2) {
                    Label(Catalogo.Lega.nuovaStagioneN(s: vm.stagione.dato?.corrente ?? ""), systemImage: "calendar.badge.exclamationmark").font(.headline)
                    Text(Catalogo.Lega.bannerStagione(s: vm.stagione.dato?.rose ?? "")).font(.caption).foregroundStyle(Color.testoSecondario)
                }
                .frame(minHeight: Tema.areaTocco)
                .accessibilityElement(children: .combine)
            }
        }
    }

    /// Porta in vista la parte chiesta da un indirizzo (`schieraxi://lega` apre La mia lega) e la dimentica. La prima riga della
    /// parte va a metà schermo, non in cima: in cima il titolo della sezione («La mia lega») restava sopra la riga, sotto la barra
    /// e, con il testo massimo, sotto l'orologio e l'isola dinamica (#819). La lista scorre fino a una riga, non al titolo.
    private func portaInVista(_ proxy: ScrollViewProxy) {
        guard let parte = nav.parteImpostazioni else { return }
        nav.parteImpostazioni = nil
        Task {
            // la lista deve avere già le righe (le squadre arrivano dopo): un attimo di attesa, come per le foto della demo
            try? await Task.sleep(for: .milliseconds(400))
            proxy.scrollTo(parte.ancora, anchor: .center)
        }
    }

    @ViewBuilder
    private func destinazione(_ pagina: PaginaImpostazioni) -> some View {
        switch pagina {
        case .importa: ImportaExcelView(server: vm.server, dallaGuida: vm.ritornoAllaGuida.attivo(per: .importa),
                                        squadre: vm.squadre.dato)
        case .squadre: SquadreView(server: vm.server)
        case .sceltaSquadra: SceltaSquadraView(squadre: vm.squadre, scegli: vm.scegliMiaSquadra)
        case .rosa(let nome): RosaView(nome: nome, server: vm.server, squadre: vm.squadre, scegliMia: vm.scegliMiaSquadra)
        case .regole: RegoleEditorView(server: vm.server, lega: vm)
        case .stagione: StagioneView(server: vm.server)
        case .account: AccountPagina()
        case .informazioni: InformazioniPagina(server: vm.server)
        case .gestione: GestionePagina(vm: vm, avvisi: avvisi)
        case .stato: StatoDatiView(server: vm.server, aggiornamento: vm.aggiornamento)
        case .crediti: CreditiEFontiView()
        case .novita: NovitaView(server: vm.server)
        case .cambiaServer: PaginaCambiaServer(dopoProva: { await vm.info.ricarica() })
        }
    }
}

#Preview("Impostazioni") {
    ImpostazioniView(vm: LegaViewModel(server: FinteServer.esempio))
        .environmentObject(Navigazione())
}
