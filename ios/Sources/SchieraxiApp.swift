import SwiftUI

/// SchieraXI nativa per iPhone/iPad: SwiftUI puro, parla con il server sul server (rete privata acceso) e usa le funzioni di iOS.
@main
struct SchieraxiApp: App {
    var body: some Scene {
        WindowGroup {
            TabView {
                OggiView().tabItem { Label("Oggi", systemImage: "calendar") }
                FormazioneView().tabItem { Label("Formazione", systemImage: "sportscourt") }
                AltroView(titolo: "Mercato", icona: "bag").tabItem { Label("Mercato", systemImage: "bag") }
                AltroView(titolo: "Scambi", icona: "arrow.left.arrow.right").tabItem { Label("Scambi", systemImage: "arrow.left.arrow.right") }
                LegaView().tabItem { Label("Lega", systemImage: "person.3") }
            }
            .tint(Color.verde)
            .preferredColorScheme(.dark)
        }
    }
}
