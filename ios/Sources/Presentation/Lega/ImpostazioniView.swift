import SwiftUI

/// Le pagine che si aprono dalle Impostazioni.
enum PaginaImpostazioni: Hashable {
    case aspetto, avvisi, stato, crediti, avanzate, cambiaServer
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

/// Impostazioni: l'account, l'app (aspetto e avvisi), le informazioni e «Esci». Solo l'essenziale: la lega (scambi, regole,
/// storico, novità) sta in Altro. Chi amministra il server ha in più «Avanzate». Si apre come foglio dall'ingranaggio in testata.
struct ImpostazioniView: View {
    @ObservedObject var vm: LegaViewModel
    @ObservedObject var funzioni: ArchivioFunzioni
    @EnvironmentObject private var sessione: SessioneAccount
    @Environment(\.dismiss) private var chiudi
    @State private var percorso: [PaginaImpostazioni] = []

    var body: some View {
        NavigationStack(path: $percorso) {
            List {
                AccountSezione()
                SessioneMinimaSezione(nonRaggiungibile: vm.info.datiSalvati != nil || vm.info.errore != nil)
                if ProvaEsempio.attiva { SezioneProvaEsempio() }
                sezioneApp
                NuovaVersioneSezione()
                sezioneInformazioni
                sezioneAvanzateLink
                EsciSezione()
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
                // Solo per le fotografie del simulatore (-DEMO_SCHERMATA impostazioni-crediti, ...).
                if Demo.schermata == "impostazioni-crediti", percorso.isEmpty { percorso = [.crediti] }
                if Demo.schermata == "impostazioni-avanzate", percorso.isEmpty { percorso = [.avanzate] }
                if Demo.schermata == "impostazioni-aspetto", percorso.isEmpty { percorso = [.aspetto] }
            }
        }
        .tint(Color.verde)
        .schermoProtetto()   // l'email e i dati dell'account non devono comparire nell'anteprima del selettore delle app
    }

    @ViewBuilder
    private func destinazione(_ pagina: PaginaImpostazioni) -> some View {
        switch pagina {
        case .aspetto: AspettoView()
        case .avvisi: AvvisiServerView(server: vm.server, lega: vm)
        case .stato: StatoDatiView(server: vm.server, aggiornamento: vm.aggiornamento)
        case .crediti: LicenzeECreditiView(server: vm.server)
        case .avanzate: paginaAvanzate
        case .cambiaServer: PaginaCambiaServer(dopoProva: { await vm.info.ricarica() })
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
                    Label("Non riesco a raggiungere SchieraXI. Quello che vedi è stato salvato il \(salvati.formatted(date: .abbreviated, time: .shortened)) e può essere vecchio.", systemImage: "icloud.slash")
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

    /// L'app su questo telefono: aspetto e avvisi.
    private var sezioneApp: some View {
        Section("App") {
            NavigationLink(value: PaginaImpostazioni.aspetto) { Label("Aspetto", systemImage: "paintpalette").labelStyle(.voce(.pink)).frame(minHeight: 44) }
            NavigationLink(value: PaginaImpostazioni.avvisi) {
                Label("Avvisi e promemoria", systemImage: "bell.badge").labelStyle(.voce(.red)).frame(minHeight: 44)
            }
            RigaValore(titolo: "Notifiche", valore: vm.permesso)
        }
    }

    /// Privacy, termini, licenze e la versione. Le novità stanno in Altro.
    private var sezioneInformazioni: some View {
        Section("Informazioni") {
            RigheLegali(server: vm.server)
            RigaValore(titolo: "Versione dell'app", valore: Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "—")
        }
    }

    /// La riga «Avanzate» c'è solo per chi amministra il server (o per chi usa il server di sempre, senza account).
    @ViewBuilder
    private var sezioneAvanzateLink: some View {
        if sessione.puoAmministrare {
            Section {
                NavigationLink(value: PaginaImpostazioni.avanzate) {
                    Label("Avanzate", systemImage: "wrench.and.screwdriver").labelStyle(.voce(.gray)).frame(minHeight: 44)
                }
            } footer: {
                Text("Server, aggiornamento e rinnovo con SideStore, stato dei dati, diagnostica del widget.")
            }
        }
    }

    /// La pagina «Avanzate»: tutto quello che serve a chi gestisce il server e l'installazione, non a chi usa l'app.
    private var paginaAvanzate: some View {
        List {
            if !ProvaEsempio.attiva { sezioneCollegamento }
            Section {
                Toggle(isOn: Binding(get: { funzioni.stato.mostraTutte }, set: { v in Task { await funzioni.impostaMostraTutte(v) } })) {
                    Text("Mostra tutte le funzioni")
                }
                .tint(Color.verde)
                .frame(minHeight: 44)
                .disabled(funzioni.inSalvataggio)
                if let e = funzioni.errore { Text(e).font(.footnote).foregroundStyle(Color.attenzione) }
                NavigationLink(value: PaginaImpostazioni.stato) { Label("Stato dei dati", systemImage: "externaldrive").labelStyle(.voce(.gray)).frame(minHeight: 44) }
                AggiornaDatiSezione(vm: vm.aggiornamento)
                if let v = vm.info.dato?.versione { RigaValore(titolo: "Versione del server", valore: v) }
            } footer: {
                Text("Di norma SchieraXI mostra solo l'essenziale: formazione, squadra e scambi. Se lo accendi vedi anche tutto il resto (risultati in diretta, asta, confronto, seguiti, diario e altro). Vale solo per te.")
            }
            DiagnosticaWidgetSezione()
            CertificatoSezione()
            RinnovoSideStoreSezione()
            NotificheNtfySezione()
        }
        .scrollContentBackground(.hidden)
        .background(Sfondo())
        .navigationTitle("Avanzate")
        .navigationBarTitleDisplayMode(.inline)
    }
}

#Preview("Impostazioni") {
    ImpostazioniView(vm: LegaViewModel(server: FinteServer.esempio), funzioni: ArchivioFunzioni(server: FinteServer.esempio))
        .environmentObject(Navigazione())
}
