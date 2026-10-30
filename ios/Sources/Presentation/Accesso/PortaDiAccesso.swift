import SwiftUI

/// La porta dell'app: decide cosa mostrare secondo lo stato dell'accesso.
/// - server senza account (come sempre): l'app, subito;
/// - server con account e nessuna sessione: la schermata di accesso;
/// - sessione valida: l'app (ricostruita da zero a ogni cambio di utente, così non restano dati di un altro);
/// - codice di recupero appena creato: la schermata «Salva il tuo codice», prima di tutto il resto.
struct PortaDiAccesso: View {
    @EnvironmentObject private var sessione: SessioneAccount
    @Environment(\.scenePhase) private var fase
    @AppStorage("indirizzo") private var indirizzo = ""

    var body: some View {
        Group {
            if Demo.schermata == "marchio" {
                ProvaMarchio()
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
        .tint(Color.verde)   // anche accesso e codice di recupero con il colore dell app (prima restavano blu)
        // All'apertura, e poco dopo che si è cambiato l'indirizzo del server, si chiede chi siamo.
        .task(id: indirizzo) {
            try? await Task.sleep(nanoseconds: 700_000_000)
            if Task.isCancelled { return }
            await sessione.cambiaServer()
        }
        .onChange(of: fase) { _, nuova in
            if nuova == .active { Task { await sessione.verifica() } }
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
    }
}
