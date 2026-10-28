import SwiftUI

/// Schermata Lega: server, strumenti di gestione della lega, promemoria, certificato. Logica in `LegaViewModel`.
struct LegaView: View {
    @ObservedObject var vm: LegaViewModel
    @AppStorage("indirizzo") private var indirizzo = ""

    var body: some View {
        NavigationStack(path: $vm.percorso) {
            List {
                sezioneServer
                sezioneLega
                sezionePromemoria
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
        case .stato: StatoDatiView(server: vm.server)
        case .novita: NovitaView(server: vm.server)
        }
    }

    private var sezioneServer: some View {
        Section("Server") {
            TextField(Config.indirizzoPredefinito, text: $indirizzo)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
                .keyboardType(.URL)
                .frame(minHeight: 44)
            if !indirizzo.trimmingCharacters(in: .whitespaces).isEmpty && !IndirizzoServer.valido(indirizzo) {
                Label("Indirizzo non valido: deve iniziare con https://. Finché non lo correggi l'app usa quello predefinito.", systemImage: "exclamationmark.triangle")
                    .font(.footnote).foregroundStyle(.orange)
            }
            Button("Prova la connessione") { Task { await vm.info.ricarica() } }.frame(minHeight: 44)
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
        }
    }

    private var sezioneLega: some View {
        Section("Lega") {
            NavigationLink(value: PaginaLega.importa) { Label("Aggiorna le rose da Excel", systemImage: "doc.badge.plus") }
            NavigationLink(value: PaginaLega.squadre) { Label("Squadre e rose", systemImage: "person.3") }
            NavigationLink(value: PaginaLega.asta) { Label("Asta e riparazione", systemImage: "hammer") }
            NavigationLink(value: PaginaLega.regole) { Label("Regole", systemImage: "list.bullet.rectangle") }
            NavigationLink(value: PaginaLega.crediti) { Label("Crediti delle squadre", systemImage: "eurosign.circle") }
            NavigationLink(value: PaginaLega.avvisi) { Label("Avvisi del server", systemImage: "bell.badge") }
            NavigationLink(value: PaginaLega.stato) { Label("Stato dei dati", systemImage: "externaldrive") }
            NavigationLink(value: PaginaLega.novita) { Label("Novità del server", systemImage: "sparkles") }
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
