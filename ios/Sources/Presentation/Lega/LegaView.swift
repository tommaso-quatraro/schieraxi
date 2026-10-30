import SwiftUI

/// Schermata Lega: server, strumenti di gestione della lega, aspetto, promemoria, certificato. Logica in `LegaViewModel`.
struct LegaView: View {
    @ObservedObject var vm: LegaViewModel
    @EnvironmentObject private var sessione: SessioneAccount

    var body: some View {
        NavigationStack(path: $vm.percorso) {
            List {
                testata
                AccountSezione()
                if vm.nuovaStagione { bannerStagione }
                sezioneServer
                sezioneLega
                sezioneApp
                sezionePromemoria
                NuovaVersioneSezione()
                CertificatoSezione()
                RinnovoSideStoreSezione()
                NotificheNtfySezione()
                Section("App") {
                    riga("Versione", Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "—")
                }
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

    /// Il marchio di SchieraXI in cima a Lega, con il nome e una frase da spogliatoio.
    private var testata: some View {
        VStack(alignment: .leading, spacing: 8) {
            MarchioConNome(lato: 52)
            Text("Gli undici giusti, giornata dopo giornata.")
                .font(.subheadline).foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .listRowBackground(Color.clear)
        .listRowSeparator(.hidden)
    }

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

    private var sezioneServer: some View {
        Section("Server") {
            ProvaServerView(dopoProva: { await vm.info.ricarica() })
            if vm.info.inCorso {
                ProgressView()
            } else if let s = vm.info.dato {
                if let salvati = vm.info.datiSalvati {
                    Label("Server non raggiungibile. Dati salvati del \(salvati.formatted(date: .abbreviated, time: .shortened))", systemImage: "icloud.slash")
                        .font(.footnote).foregroundStyle(.orange)
                }
                riga("Squadra", s.miaSquadra ?? "—")
                riga("Stagione", s.stagione ?? "—")
                riga("Versione del server", s.versione ?? "—")
                riga("Dati aggiornati", Quando.leggibile((s.ultimoAggiornamento ?? "").replacingOccurrences(of: "T", with: " ")))
            } else if let e = vm.info.errore {
                Text(e).foregroundStyle(.orange)
            }
            if sessione.puoAmministrare { AggiornaDatiSezione(vm: vm.aggiornamento) }
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

    private var sezioneApp: some View {
        Section("App e dati") {
            NavigationLink(value: PaginaLega.aspetto) { Label("Aspetto", systemImage: "paintpalette").labelStyle(.voce(.pink)).frame(minHeight: 44) }
            NavigationLink(value: PaginaLega.icona) { Label("Icona dell'app", systemImage: "app.badge").labelStyle(.voce(.purple)).frame(minHeight: 44) }
            NavigationLink(value: PaginaLega.backup) { Label("Backup dei dati", systemImage: "externaldrive.badge.timemachine").labelStyle(.voce(.cyan)).frame(minHeight: 44) }
            NavigationLink(value: PaginaLega.avvisi) { Label("Avvisi del server", systemImage: "bell.badge").labelStyle(.voce(.red)).frame(minHeight: 44) }
            if sessione.puoAmministrare {
                NavigationLink(value: PaginaLega.stato) { Label("Stato dei dati", systemImage: "externaldrive").labelStyle(.voce(.gray)).frame(minHeight: 44) }
            }
            NavigationLink(value: PaginaLega.novita) { Label("Novità", systemImage: "sparkles").labelStyle(.voce(.yellow)).frame(minHeight: 44) }
        }
    }

    private var sezionePromemoria: some View {
        Section("Promemoria") {
            riga("Notifiche", vm.permesso)
            Button("Attiva i promemoria sul telefono") { Task { await vm.attivaPromemoria() } }.frame(minHeight: 44)
            riga("Aggiornamento in background", vm.aggiornamentoInBackground)
            Text("Un'ora e un quarto d'ora prima della prima partita, anche con l'app chiusa. Si programmano quando apri la schermata Oggi e, ogni tanto, da soli: iOS sveglia l'app in background, riscarica la giornata e ti avvisa se la formazione consigliata cambia. Quando succede lo decide iOS (di solito poche volte al giorno).")
                .font(.footnote).foregroundStyle(.secondary)
        }
    }

    private func riga(_ titolo: String, _ valore: String) -> some View {
        RigaValore(titolo: titolo, valore: valore)
    }
}

#Preview("Lega") {
    LegaView(vm: LegaViewModel(server: FinteServer.esempio))
}
