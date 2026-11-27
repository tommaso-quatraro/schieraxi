import SwiftUI
import CoreSpotlight

/// SchieraXI nativa per iPhone/iPad: SwiftUI puro, parla con il server (serve la rete, anche privata) e usa le funzioni di iOS.
@main
struct SchieraxiApp: App {
    @StateObject private var nav = Navigazione()
    // Con la «Prova con dati di esempio» l'app riparte con il server finto, ma l'accesso resta legato al server vero (per quando si esce dalla prova).
    @StateObject private var sessione = SessioneAccount(server: Demo.daLancio ? ServerCorrente.condiviso : ServerHTTP())
    @Environment(\.scenePhase) private var fase

    init() {
        // il delegato delle notifiche prima che l'app finisca di partire: con l'app aperta gli avvisi si vedono, e arriva anche il
        // tocco su un promemoria che ha aperto l'app (porta alla Formazione, sotto `toccoSugliAvvisi`)
        DelegatoAvvisi.installa()
        OpzioniTolte.pulisci()   // colore, densità e sezione iniziale non si scelgono più: si torna ai valori normali
        // I giocatori seguiti non ci sono più (#634): via dalla ricerca di iOS (Spotlight) le voci messe da una versione di prima.
        // Una volta sola: quando riesce resta un segno sul telefono e agli avvii dopo non si rifà.
        let segno = OpzioniTolte.chiaveSpotlightSvuotato
        if !Demo.attivo, !Ambiente.ospiteDeiTest, !UserDefaults.standard.bool(forKey: segno) {
            CSSearchableIndex.default().deleteAllSearchableItems { errore in
                if errore == nil { UserDefaults.standard.set(true, forKey: segno) }
            }
        }
        Suggerimenti.configura()
        // senza rete si vede la copia salvata: quando il telefono ritrova la rete si riprova da soli, come la web
        if !Demo.attivo, !Ambiente.ospiteDeiTest { RitornoRete.condiviso.avvia() }
    }

    var body: some Scene {
        WindowGroup {
            if Ambiente.ospiteDeiTest {
                // L'app fa solo da contenitore dei test automatici (workflow Test): nessuna schermata, quindi nessuna richiesta
                // al server vero. Prima l'app partiva davvero e, a ogni «Aggiorna» dei test, interrogava il server di produzione.
                Color.clear
            } else {
            // Colori chiari o scuri come il sistema: lo sfondo e il verde si adattano da soli.
            PortaDiAccesso()
                .environmentObject(nav)
                .environmentObject(sessione)
                .onOpenURL { url in
                    // schieraxi://formazione, schieraxi://giocatore/12, ... (per esempio dal tocco su una notifica di ntfy)
                    if url.isFileURL {
                        nav.apriFile(url)   // un file delle rose da un'altra app
                    } else if let destinazione = Collegamenti.interpreta(url) {
                        nav.vai(a: destinazione)
                    }
                }
                // il tocco su un promemoria della scadenza: la Formazione, come schieraxi://formazione (`DelegatoAvvisi`)
                .toccoSugliAvvisi(nav)
                .onChange(of: fase) { _, nuova in
                    // Uscendo dall'app si chiede a iOS il prossimo aggiornamento in background.
                    if nuova == .background { Aggiornamento.programma() }
                }
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
                // chiesto a mano, come «Riprova»: se una lettura resta senza rete, al ritorno della rete si riprova da soli (#980)
                Button("Aggiorna") {
                    RitornoRete.condiviso.riprovaAMano()
                    NotificationCenter.default.post(name: .aggiornaTutto, object: nil)
                }
                .keyboardShortcut("r", modifiers: .command)
            }
        }
    }
}
