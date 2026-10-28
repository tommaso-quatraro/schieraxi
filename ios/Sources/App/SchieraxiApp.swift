import SwiftUI
import CoreSpotlight

/// SchieraXI nativa per iPhone/iPad: SwiftUI puro, parla con il server sul server (rete privata acceso) e usa le funzioni di iOS.
@main
struct SchieraxiApp: App {
    @StateObject private var nav = Navigazione()
    @StateObject private var modello = AppModel()
    @Environment(\.scenePhase) private var fase

    var body: some Scene {
        WindowGroup {
            // Colori chiari o scuri come il sistema: lo sfondo e il verde si adattano da soli.
            RadiceView()
                .environmentObject(nav)
                .environmentObject(modello)
                .onContinueUserActivity(CSSearchableItemActionType) { attivita in
                    // Aperta da Spotlight su un giocatore osservato: si va alla sua scheda.
                    if let id = Spotlight.idGiocatore(da: attivita) { nav.vai(a: .giocatore(id)) }
                }
                .onOpenURL { url in
                    // schieraxi://formazione, schieraxi://giocatore/12, ... (per esempio dal tocco su una notifica di ntfy)
                    if let destinazione = Collegamenti.interpreta(url) { nav.vai(a: destinazione) }
                }
                .onChange(of: fase) { nuova in
                    // Uscendo dall'app si chiede a iOS il prossimo aggiornamento in background.
                    if nuova == .background { Aggiornamento.programma() }
                }
        }
        // Aggiornamento in background (iOS lo avvia quando vuole): riscarica la giornata e riprogramma i promemoria.
        .backgroundTask(.appRefresh(Aggiornamento.identificativo)) {
            await Aggiornamento.esegui()
        }
        .commands {
            // Scorciatoie da tastiera (iPad con tastiera: tieni premuto Cmd per vederle).
            CommandMenu("Vai a") {
                ForEach(Sezione.allCases) { s in
                    Button(s.titolo) { nav.sezione = s }
                        .keyboardShortcut(s.scorciatoia, modifiers: .command)
                }
            }
            CommandMenu("Dati") {
                Button("Aggiorna") { NotificationCenter.default.post(name: .aggiornaTutto, object: nil) }
                    .keyboardShortcut("r", modifiers: .command)
            }
        }
    }
}
