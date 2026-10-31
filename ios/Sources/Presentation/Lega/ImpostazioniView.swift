import SwiftUI

/// Le pagine che si aprono dalle Impostazioni.
enum PaginaImpostazioni: Hashable {
    case aspetto, icona, avvisi, backup, stato, novita, cofano, crediti
}

private struct ApriRosaDiChiave: EnvironmentKey {
    static let defaultValue: ((String) -> Void)? = nil
}

extension EnvironmentValues {
    /// Apre Lega > Squadre > la rosa di una squadra (da Oggi: «Aggiungi la tua divisa»). `nil` dove non c'è.
    var apriRosaDi: ((String) -> Void)? {
        get { self[ApriRosaDiChiave.self] }
        set { self[ApriRosaDiChiave.self] = newValue }
    }
}

private struct ApriImpostazioniChiave: EnvironmentKey {
    static let defaultValue: (() -> Void)? = nil
}

extension EnvironmentValues {
    /// Apre le Impostazioni (l'ingranaggio accanto alla lente in ogni testata). `nil` dove non ci sono (anteprime, fogli).
    var apriImpostazioni: (() -> Void)? {
        get { self[ApriImpostazioniChiave.self] }
        set { self[ApriImpostazioniChiave.self] = newValue }
    }
}

/// Impostazioni: tutto quello che riguarda l'app e l'account, in gruppi. Lega resta solo la lega (rose, regole, storico).
/// Si apre come foglio dall'ingranaggio in testata, accanto alla lente.
struct ImpostazioniView: View {
    @ObservedObject var vm: LegaViewModel
    @ObservedObject var funzioni: ArchivioFunzioni
    @EnvironmentObject private var sessione: SessioneAccount
    @EnvironmentObject private var nav: Navigazione
    @Environment(\.dismiss) private var chiudi
    @State private var percorso: [PaginaImpostazioni] = []

    var body: some View {
        NavigationStack(path: $percorso) {
            List {
                AccountSezione()
                if ProvaEsempio.attiva { SezioneProvaEsempio() } else { sezioneCollegamento }
                sezioneAspetto
                sezioneAvvisi
                SezioneWidget()
                sezioneDati
                NuovaVersioneSezione()
                CertificatoSezione()
                RinnovoSideStoreSezione()
                sezioneInformazioni
                sezioneAvanzate
                NotificheNtfySezione()
            }
            .scrollContentBackground(.hidden)
            .background(Sfondo())
            .demoInFondo()
            .navigationTitle("Impostazioni")
            .navigationBarTitleDisplayMode(.large)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) { Button("Chiudi") { chiudi() } }
            }
            .navigationDestination(for: PaginaImpostazioni.self) { destinazione($0) }
            .task { await vm.carica() }
            .onAppear {
                // Solo per le fotografie del simulatore (-DEMO_SCHERMATA impostazioni-cofano).
                if Demo.schermata == "impostazioni-cofano", percorso.isEmpty { percorso = [.cofano] }
                if Demo.schermata == "impostazioni-crediti", percorso.isEmpty { percorso = [.crediti] }
            }
        }
        .tint(Color.verde)
    }

    @ViewBuilder
    private func destinazione(_ pagina: PaginaImpostazioni) -> some View {
        switch pagina {
        case .aspetto: AspettoView()
        case .icona: IconaAppView()
        case .avvisi: AvvisiServerView(server: vm.server, lega: vm)
        case .backup: BackupView(server: vm.server)
        case .stato: StatoDatiView(server: vm.server, aggiornamento: vm.aggiornamento)
        case .novita: NovitaView(server: vm.server)
        case .cofano: SottoIlCofanoView(server: vm.server, vai: apriDaCofano)
        case .crediti: LicenzeECreditiView(server: vm.server)
        }
    }

    /// Un rimando di «Sotto il cofano»: un'altra pagina delle Impostazioni, oppure si chiude il foglio e si va alla schermata.
    private func apriDaCofano(_ destinazione: DestinazioneCofano) {
        switch destinazione {
        case .impostazioni(let pagina):
            percorso.append(pagina)
        case .sezione(let sezione):
            nav.sezione = sezione
            chiudi()
        case .lega(let pagina):
            nav.sezione = vm.apri([pagina])
            chiudi()
        }
    }

    // MARK: gruppi

    private var sezioneCollegamento: some View {
        Section("Collegamento") {
            ProvaServerView(utente: sessione.utente?.nome, dopoProva: { await vm.info.ricarica() })
            if vm.info.inCorso {
                ProgressView()
            } else if let s = vm.info.dato {
                if let salvati = vm.info.datiSalvati {
                    Label("Server non raggiungibile. Dati salvati del \(salvati.formatted(date: .abbreviated, time: .shortened))", systemImage: "icloud.slash")
                        .font(.footnote).foregroundStyle(Color.attenzione)
                }
                RigaValore(titolo: "Squadra", valore: s.miaSquadra ?? "—")
                RigaValore(titolo: "Stagione", valore: s.stagione ?? "—")
                RigaValore(titolo: "Dati aggiornati", valore: Quando.leggibile((s.ultimoAggiornamento ?? "").replacingOccurrences(of: "T", with: " ")))
            } else if let e = vm.info.errore {
                Text(e).foregroundStyle(Color.attenzione)
            }
        }
    }

    private var sezioneAspetto: some View {
        Section("Aspetto") {
            NavigationLink(value: PaginaImpostazioni.aspetto) { Label("Tema, colore e densità", systemImage: "paintpalette").labelStyle(.voce(.pink)).frame(minHeight: 44) }
            if funzioni.stato.acceso(Funzione.aspettoAvanzato) {
                NavigationLink(value: PaginaImpostazioni.icona) { Label("Icona dell'app", systemImage: "app.badge").labelStyle(.voce(.purple)).frame(minHeight: 44) }
            }
        }
    }

    private var sezioneAvvisi: some View {
        Section("Avvisi e promemoria") {
            NavigationLink(value: PaginaImpostazioni.avvisi) {
                Label("Avvisi, promemoria e ore tranquille", systemImage: "bell.badge").labelStyle(.voce(.red)).frame(minHeight: 44)
            }
            RigaValore(titolo: "Notifiche", valore: vm.permesso)
        }
    }

    @ViewBuilder
    private var sezioneDati: some View {
        if funzioni.stato.acceso(Funzione.backup) {
            Section("Dati e backup") {
                NavigationLink(value: PaginaImpostazioni.backup) { Label("Copia di sicurezza", systemImage: "externaldrive.badge.timemachine").labelStyle(.voce(.cyan)).frame(minHeight: 44) }
            }
        }
    }

    private var sezioneInformazioni: some View {
        Section("Informazioni") {
            if funzioni.stato.acceso(Funzione.novita) {
                NavigationLink(value: PaginaImpostazioni.novita) { Label("Novità", systemImage: "sparkles").labelStyle(.voce(.yellow)).frame(minHeight: 44) }
            }
            Button {
                // si chiude il foglio e, appena è sparito, si apre la guida
                chiudi()
                Task {
                    try? await Task.sleep(nanoseconds: 600_000_000)
                    nav.guidaAperta = true
                }
            } label: {
                Label("Configurazione guidata", systemImage: "list.bullet.clipboard").labelStyle(.voce(.teal)).frame(minHeight: 44)
            }
            .accessibilityHint("Rose, squadra, stemma, widget e avvisi, un passo alla volta")
            NavigationLink(value: PaginaImpostazioni.cofano) { Label("Sotto il cofano", systemImage: "gearshape.2").labelStyle(.voce(.indigo)).frame(minHeight: 44) }
            RigheLegali(server: vm.server)
            RigaValore(titolo: "Versione dell'app", valore: Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "—")
            if let v = vm.info.dato?.versione { RigaValore(titolo: "Versione del server", valore: v) }
        }
    }

    /// Avanzate: «Mostra tutte le funzioni» per tutti; lo stato dei dati e l'aggiornamento solo per l'amministratore.
    private var sezioneAvanzate: some View {
        Section {
            Toggle(isOn: Binding(get: { funzioni.stato.mostraTutte }, set: { v in Task { await funzioni.impostaMostraTutte(v) } })) {
                Text("Mostra tutte le funzioni")
            }
            .tint(Color.verde)
            .frame(minHeight: 44)
            .disabled(funzioni.inSalvataggio)
            if let e = funzioni.errore { Text(e).font(.footnote).foregroundStyle(Color.attenzione) }
            if sessione.puoAmministrare {
                NavigationLink(value: PaginaImpostazioni.stato) { Label("Stato dei dati", systemImage: "externaldrive").labelStyle(.voce(.gray)).frame(minHeight: 44) }
                AggiornaDatiSezione(vm: vm.aggiornamento)
            }
        } header: {
            Text("Avanzate")
        } footer: {
            Text("Di norma SchieraXI mostra solo l'essenziale: formazione, squadra e scambi. Se lo accendi vedi anche tutto il resto (risultati in diretta, asta, confronto, seguiti, diario e altro). Vale solo per te.")
        }
    }
}

#Preview("Impostazioni") {
    ImpostazioniView(vm: LegaViewModel(server: FinteServer.esempio), funzioni: ArchivioFunzioni(server: FinteServer.esempio))
        .environmentObject(Navigazione())
}
