import SwiftUI

/// Schermata Lega: solo la lega (rose, regole, storico, diario, asta, crediti). Il resto sta nelle Impostazioni. Logica in `LegaViewModel`.
struct LegaView: View {
    @ObservedObject var vm: LegaViewModel
    @EnvironmentObject private var sessione: SessioneAccount
    @Environment(\.apriImpostazioni) private var apriImpostazioni

    var body: some View {
        NavigationStack(path: $vm.percorso) {
            List {
                if vm.nuovaStagione { bannerStagione }
                sezioneLega
                sezioneImpostazioni
            }
            .scrollContentBackground(.hidden)
            .background(Sfondo())
            .demoInFondo()
            .navigationTitle("Lega")
            .ricercaGlobale()
            .navigationDestination(for: PaginaLega.self) { pagina in destinazione(pagina) }
            .refreshable { await vm.carica() }
            .task { await vm.carica() }
        }
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
        case .avvisi: AvvisiServerView(server: vm.server)
        case .stato: StatoDatiView(server: vm.server, aggiornamento: vm.aggiornamento)
        case .novita: NovitaView(server: vm.server)
        case .movimenti: MovimentiView(server: vm.server)
        case .stagione: StagioneView(server: vm.server)
        case .aspetto: AspettoView()
        case .icona: IconaAppView()
        case .diario: DiarioView(server: vm.server)
        case .backup: BackupView(server: vm.server)
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

    private var sezioneLega: some View {
        Section("Lega") {
            NavigationLink(value: PaginaLega.importa) { Label("Aggiorna le rose", systemImage: "doc.badge.plus").labelStyle(.voce(.blue)).frame(minHeight: 44) }
            NavigationLink(value: PaginaLega.squadre) { Label("Squadre e rose", systemImage: "person.3").labelStyle(.voce(.green)).frame(minHeight: 44) }
            NavigationLink(value: PaginaLega.movimenti) { Label("Movimenti e storico", systemImage: "list.bullet.clipboard").labelStyle(.voce(.orange)).frame(minHeight: 44) }
            NavigationLink(value: PaginaLega.diario) { Label("Diario delle giornate", systemImage: "book").labelStyle(.voce(.teal)).frame(minHeight: 44) }
            NavigationLink(value: PaginaLega.asta) { Label("Asta e riparazione", systemImage: "hammer").labelStyle(.voce(.brown)).frame(minHeight: 44) }
            NavigationLink(value: PaginaLega.regole) { Label("Regole", systemImage: "list.bullet.rectangle").labelStyle(.voce(.indigo)).frame(minHeight: 44) }
            NavigationLink(value: PaginaLega.crediti) { Label("Crediti delle squadre", systemImage: "eurosign.circle").labelStyle(.voce(.mint)).frame(minHeight: 44) }
            NavigationLink(value: PaginaLega.stagione) { Label("Nuova stagione", systemImage: "calendar").labelStyle(.voce(.red)).frame(minHeight: 44) }
        }
    }

    /// Un solo rimando alle Impostazioni (account, collegamento, aspetto, avvisi, widget, copia di sicurezza, informazioni).
    @ViewBuilder
    private var sezioneImpostazioni: some View {
        if let apri = apriImpostazioni {
            Section {
                Button { apri() } label: {
                    Label("Impostazioni dell'app e dell'account", systemImage: "gearshape").labelStyle(.voce(.gray)).frame(minHeight: 44)
                }
            } footer: {
                Text("Account, collegamento al server, aspetto, avvisi, widget e copia di sicurezza stanno nelle Impostazioni (l'ingranaggio in alto).")
            }
        }
    }
}

#Preview("Lega") {
    LegaView(vm: LegaViewModel(server: FinteServer.esempio))
}
