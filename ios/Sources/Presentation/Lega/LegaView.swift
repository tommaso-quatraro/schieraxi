import SwiftUI

/// Le schede Squadra e Altro (la «dieta delle funzioni»): un elenco di voci, ognuna una pagina. Squadra ha la mia squadra e le rose,
/// i cambi consigliati, i seguiti, l'elenco dei giocatori e il calendario; Altro ha Scambi, il diario, le regole, l'asta e il resto.
/// Le voci di una funzione spenta (`GET /api/funzioni`) non si vedono. Logica in `LegaViewModel`, `MercatoViewModel` e `ScambiViewModel`.
struct LegaView: View {
    @ObservedObject var vm: LegaViewModel
    let mercato: MercatoViewModel
    let scambi: ScambiViewModel
    /// `.squadra` o `.altro`: quali voci mostra.
    var ambito: Sezione = .altro
    @EnvironmentObject private var sessione: SessioneAccount
    @Environment(\.apriImpostazioni) private var apriImpostazioni
    @Environment(\.funzioni) private var funzioni

    @Environment(\.horizontalSizeClass) private var classe

    var body: some View {
        Group { if classe == .regular { colonne } else { pila } }
            .schermoProtetto()   // rose e nomi non devono comparire nell'anteprima del selettore delle app
    }

    /// Le pagine aperte in questa scheda (Squadra e Altro hanno ciascuna il suo percorso).
    private var percorso: Binding<[PaginaLega]> {
        ambito == .squadra ? $vm.percorsoSquadra : $vm.percorso
    }

    /// iPhone e finestre strette: una pila, come prima.
    private var pila: some View {
        NavigationStack(path: percorso) {
            elenco
                .navigationDestination(for: PaginaLega.self) { pagina in destinazione(pagina) }
        }
    }

    /// iPad e finestre larghe: l'elenco a sinistra, la pagina scelta a destra (le pagine che ne aprono altre restano nella colonna di destra).
    /// Il percorso resta quello della scheda: la prima pagina è la scelta nell'elenco, le altre stanno sopra nella colonna di destra.
    private var colonne: some View {
        NavigationSplitView {
            elenco
        } detail: {
            NavigationStack(path: percorsoSopra) {
                Group {
                    if let prima = percorso.wrappedValue.first {
                        destinazione(prima)
                    } else {
                        ContentUnavailableView("Scegli una voce", systemImage: "list.bullet.rectangle", description: Text(testoVuoto))
                    }
                }
                .navigationDestination(for: PaginaLega.self) { pagina in destinazione(pagina) }
            }
            // Cambiando voce nell'elenco la colonna di destra riparte pulita.
            .id(percorso.wrappedValue.first)
        }
    }

    private var testoVuoto: String {
        ambito == .squadra
            ? "La tua squadra, i cambi consigliati e le rose si aprono qui."
            : "Gli scambi, le regole e lo storico della tua lega si aprono qui."
    }

    private var voceScelta: Binding<PaginaLega?> {
        Binding(
            get: { percorso.wrappedValue.first },
            set: { nuova in percorso.wrappedValue = nuova.map { [$0] } ?? [] }
        )
    }

    private var percorsoSopra: Binding<[PaginaLega]> {
        Binding(
            get: { Array(percorso.wrappedValue.dropFirst()) },
            set: { resto in
                guard let prima = percorso.wrappedValue.first else { return }
                percorso.wrappedValue = [prima] + resto
            }
        )
    }

    private var elenco: some View {
        List(selection: classe == .regular ? voceScelta : nil) {
            if ambito == .squadra {
                sezioneSquadra
            } else {
                if vm.nuovaStagione { bannerStagione }
                sezioneAltro
                sezioneImpostazioni
            }
        }
        .scrollContentBackground(.hidden)
        .contentMargins(.bottom, 24, for: .scrollContent)
        .background(Sfondo())
        .demoInFondo()
        .navigationTitle(ambito.titolo)
        .ricercaGlobale()
        .refreshable { await vm.carica() }
        .task { await vm.carica() }
    }

    @ViewBuilder
    private func destinazione(_ pagina: PaginaLega) -> some View {
        switch pagina {
        case .importa: ImportaExcelView(server: vm.server)
        case .squadre: SquadreView(server: vm.server)
        case .rosa(let nome): RosaView(nome: nome, server: vm.server)
        case .asta: AstaView(server: vm.server)
        case .regole: RegoleEditorView(server: vm.server)
        case .crediti: CreditiView(server: vm.server)
        case .avvisi: AvvisiServerView(server: vm.server, lega: vm)
        case .stato: StatoDatiView(server: vm.server, aggiornamento: vm.aggiornamento)
        case .novita: NovitaView(server: vm.server)
        case .movimenti: MovimentiView(server: vm.server)
        case .stagione: StagioneView(server: vm.server)
        case .aspetto: AspettoView()
        case .icona: IconaAppView()
        case .diario: DiarioView(server: vm.server)
        case .backup: BackupView(server: vm.server)
        case .cambi: PaginaMercato(vm: mercato, titolo: "Cambi consigliati") { ConsigliatiView(vm: mercato) }
        case .seguiti: PaginaMercato(vm: mercato, titolo: "Seguiti") { OsservatiView(vm: mercato) }
        case .elenco: PaginaMercato(vm: mercato, titolo: "Elenco dei giocatori") { GiocatoriView(vm: mercato, ricerca: mercato.ricerca) }
        case .calendario: PaginaMercato(vm: mercato, titolo: "Calendario") { CalendarioView(vm: mercato) }
        case .scambi: ScambiView(vm: scambi, incorporata: true)
        }
    }

    // MARK: sezioni

    private var bannerStagione: some View {
        Section {
            NavigationLink(value: PaginaLega.stagione) {
                VStack(alignment: .leading, spacing: 2) {
                    Label("Nuova stagione \(vm.stagione.dato?.corrente ?? "")", systemImage: "calendar.badge.exclamationmark").font(.headline)
                    Text("Le rose sono ancora quelle del \(vm.stagione.dato?.rose ?? ""): archivia e riparti.").font(.caption).foregroundStyle(.secondary)
                }
                .frame(minHeight: 44)
                .accessibilityElement(children: .combine)
            }
        }
    }

    /// Squadra: la mia squadra e le rose, i cambi consigliati, i seguiti, l'elenco dei giocatori, il calendario.
    private var sezioneSquadra: some View {
        Section {
            NavigationLink(value: PaginaLega.importa) { Label("Aggiorna le rose", systemImage: "doc.badge.plus").labelStyle(.voce(.blue)).frame(minHeight: 44) }
            NavigationLink(value: PaginaLega.squadre) {
                Label(funzioni.acceso(Funzione.squadreAltrui) ? "Squadre e rose" : "La mia squadra e rosa", systemImage: "person.3")
                    .labelStyle(.voce(.green)).frame(minHeight: 44)
            }
            NavigationLink(value: PaginaLega.cambi) { Label("Cambi consigliati", systemImage: "arrow.triangle.2.circlepath").labelStyle(.voce(.orange)).frame(minHeight: 44) }
            if funzioni.acceso(Funzione.seguiti) {
                NavigationLink(value: PaginaLega.seguiti) { Label("Seguiti", systemImage: "star").labelStyle(.voce(.yellow)).frame(minHeight: 44) }
            }
            if funzioni.acceso(Funzione.elencoGiocatori) {
                NavigationLink(value: PaginaLega.elenco) { Label("Elenco dei giocatori", systemImage: "list.number").labelStyle(.voce(.teal)).frame(minHeight: 44) }
            }
            if funzioni.vedeCalendario {
                NavigationLink(value: PaginaLega.calendario) { Label("Calendario", systemImage: "calendar.badge.clock").labelStyle(.voce(.cyan)).frame(minHeight: 44) }
            }
        }
    }

    /// Altro: Scambi, il diario, l'asta, le regole, la copia di sicurezza, le novità. I movimenti e i crediti delle squadre solo con «Squadre della lega»;
    /// la nuova stagione solo quando le rose sono di un anno passato (o con «Mostra tutte»).
    private var sezioneAltro: some View {
        Section {
            NavigationLink(value: PaginaLega.scambi) { Label("Scambi", systemImage: "arrow.left.arrow.right").labelStyle(.voce(.purple)).frame(minHeight: 44) }
            if funzioni.acceso(Funzione.diario) {
                NavigationLink(value: PaginaLega.diario) { Label("Diario delle giornate", systemImage: "book").labelStyle(.voce(.teal)).frame(minHeight: 44) }
            }
            if funzioni.acceso(Funzione.asta) {
                NavigationLink(value: PaginaLega.asta) { Label("Asta e riparazione", systemImage: "hammer").labelStyle(.voce(.brown)).frame(minHeight: 44) }
            }
            NavigationLink(value: PaginaLega.regole) { Label("Regole", systemImage: "list.bullet.rectangle").labelStyle(.voce(.indigo)).frame(minHeight: 44) }
            if funzioni.acceso(Funzione.squadreAltrui) && funzioni.acceso(Funzione.movimenti) {
                NavigationLink(value: PaginaLega.movimenti) { Label("Movimenti e storico", systemImage: "list.bullet.clipboard").labelStyle(.voce(.orange)).frame(minHeight: 44) }
            }
            if funzioni.acceso(Funzione.squadreAltrui) && funzioni.accesoSoloSeNominato(Funzione.crediti) {
                NavigationLink(value: PaginaLega.crediti) { Label("Crediti delle squadre", systemImage: "c.circle").labelStyle(.voce(.mint)).frame(minHeight: 44) }
            }
            if vm.nuovaStagione || funzioni.mostraTutte {
                NavigationLink(value: PaginaLega.stagione) { Label("Nuova stagione", systemImage: "calendar").labelStyle(.voce(.red)).frame(minHeight: 44) }
            }
            if funzioni.acceso(Funzione.backup) {
                NavigationLink(value: PaginaLega.backup) { Label("Copia di sicurezza", systemImage: "externaldrive.badge.timemachine").labelStyle(.voce(.cyan)).frame(minHeight: 44) }
            }
            if funzioni.acceso(Funzione.novita) {
                NavigationLink(value: PaginaLega.novita) { Label("Novità", systemImage: "sparkles").labelStyle(.voce(.yellow)).frame(minHeight: 44) }
            }
        }
    }

    /// Un solo rimando alle Impostazioni (account, collegamento, aspetto, avvisi, widget, informazioni).
    @ViewBuilder
    private var sezioneImpostazioni: some View {
        if let apri = apriImpostazioni {
            Section {
                Button { apri() } label: {
                    Label("Impostazioni dell'app e dell'account", systemImage: "gearshape").labelStyle(.voce(.gray)).frame(minHeight: 44)
                }
            } footer: {
                Text("Account, avvisi, widget e aspetto sono nelle Impostazioni (l'ingranaggio in alto).")
            }
        }
    }
}

/// Una pagina che prima stava in Mercato (cambi consigliati, seguiti, elenco, calendario): sfondo, titolo e la scheda del giocatore che sale dal basso.
struct PaginaMercato<Contenuto: View>: View {
    @ObservedObject var vm: MercatoViewModel
    let titolo: String
    @ViewBuilder var contenuto: () -> Contenuto
    @Environment(\.spazioZoom) private var zoom

    var body: some View {
        ZStack {
            Sfondo()
            contenuto()
        }
        .navigationTitle(titolo)
        .navigationBarTitleDisplayMode(.inline)
        .ricercaGlobale()
        .sheet(item: $vm.schedaAperta) { g in
            GiocatoreSheet(id: g.id, server: vm.server)
                .arrivoZoom(g.id, zoom)
                .presentationDragIndicator(.visible)
        }
    }
}

#Preview("Squadra") {
    LegaView(vm: LegaViewModel(server: FinteServer.esempio), mercato: MercatoViewModel(server: FinteServer.esempio),
             scambi: ScambiViewModel(server: FinteServer.esempio), ambito: .squadra)
}

#Preview("Altro") {
    LegaView(vm: LegaViewModel(server: FinteServer.esempio), mercato: MercatoViewModel(server: FinteServer.esempio),
             scambi: ScambiViewModel(server: FinteServer.esempio), ambito: .altro)
}
