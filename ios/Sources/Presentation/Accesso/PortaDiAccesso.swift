import SwiftUI
import WidgetKit

/// La porta dell'app: decide cosa mostrare secondo lo stato dell'accesso.
/// - server senza account (come sempre): l'app, subito;
/// - server con account e nessuna sessione: la schermata di accesso;
/// - sessione valida: l'app (ricostruita da zero a ogni cambio di utente, così non restano dati di un altro);
/// - codice di recupero appena creato: la schermata «Salva il tuo codice», prima di tutto il resto.
struct PortaDiAccesso: View {
    @EnvironmentObject private var sessione: SessioneAccount
    @Environment(\.scenePhase) private var fase
    @AppStorage("indirizzo") private var indirizzo = ""
    /// La prova con dati di esempio (`ProvaEsempio`): accesa o spenta, la porta si ridisegna.
    @AppStorage(ProvaEsempio.chiave) private var prova = false

    var body: some View {
        Group {
            if Demo.schermata == "marchio" {
                ProvaMarchio()
            } else if Demo.schermata == "primo-avvio" {
                PrimoAvvioView()
            } else if IndirizzoServer.manca && !prova {
                // l'indirizzo del server non sta nell'app: prima di tutto si chiede e si prova
                PrimoAvvioView()
            } else if let codice = sessione.codiceDaMostrare, sessione.utente != nil {
                NavigationStack {
                    CodiceRecuperoView(codice: codice) { sessione.codiceDaMostrare = nil }
                }
            } else if sessione.stato == .daAccedere {
                SchermataAccesso(iniziale: Demo.schedaAccesso)
            } else {
                ContenitoreApp().id(sessione.generazione)
            }
        }
        .animation(Tema.morbida, value: sessione.stato == .daAccedere)
        .animation(Tema.morbida, value: indirizzo.isEmpty)
        .tint(Color.verde)   // anche accesso e codice di recupero con il colore dell app (prima restavano blu)
        // All'apertura, e poco dopo che si è cambiato l'indirizzo del server, si chiede chi siamo.
        .task(id: indirizzo) {
            try? await Task.sleep(nanoseconds: 700_000_000)
            if Task.isCancelled { return }
            await sessione.cambiaServer()
            Accesso.sincronizzaConIlWidget()
            WidgetCenter.shared.reloadAllTimelines()
        }
        .onChange(of: fase) { _, nuova in
            if nuova == .active {
                Task { await sessione.verifica() }   // in prova non fa niente (nessun server vero)
                // all'apertura il widget riparte con dati nuovi (senza aspettare il suo turno)
                if !Demo.attivo { WidgetCenter.shared.reloadAllTimelines() }
            }
        }
    }
}

/// L'app vera (le cinque sezioni): i ViewModel nascono qui, una volta per accesso.
struct ContenitoreApp: View {
    @EnvironmentObject private var nav: Navigazione
    @StateObject private var modello = AppModel()

    var body: some View {
        RadiceView()
            .environmentObject(modello)
            .onAppear {
                // Solo con l'argomento di lancio -DEMO (fotografie nel simulatore): apre la schermata chiesta.
                Demo.applica(nav: nav, modello: modello)
            }
            .sheet(isPresented: $nav.guidaAperta) {
                ConfigurazioneGuidataView(server: modello.server, vai: apriDaGuida)
                    .tint(Color.verde)
            }
            .task { await avviaGuidaSeServe() }
    }

    /// Una sola volta all'apertura: se la lega non ha le rose e la guida non è mai stata iniziata, parte da sola.
    private func avviaGuidaSeServe() async {
        guard !Demo.attivo else { return }
        try? await Task.sleep(nanoseconds: 1_500_000_000)
        if Task.isCancelled { return }
        if await ConfigurazioneGuidataViewModel.devePartire(server: modello.server) { nav.guidaAperta = true }
    }

    /// Un passo della guida porta in un'altra schermata (la guida si è già chiusa).
    private func apriDaGuida(_ azione: AzioneGuida) {
        switch azione {
        case .importaRose:
            modello.lega.percorso = [.importa]
            nav.sezione = .lega
        case .squadre(let nome):
            var pagine: [PaginaLega] = [.squadre]
            if let nome { pagine.append(.rosa(nome)) }
            modello.lega.percorso = pagine
            nav.sezione = .lega
        case .impostazioni:
            // il foglio della guida si sta chiudendo: si aspetta un attimo prima di aprire quello delle Impostazioni
            Task {
                try? await Task.sleep(nanoseconds: 600_000_000)
                nav.impostazioniAperte = true
            }
        }
    }
}
