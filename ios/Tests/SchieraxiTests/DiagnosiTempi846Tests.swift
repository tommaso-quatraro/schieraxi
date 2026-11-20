import Foundation
import SwiftUI
import Testing
import UIKit
@testable import Schieraxi

// DIAGNOSI DELLA #846, DA TOGLIERE: confronta la prima disposizione degli stessi pezzi della Formazione (testa, campo, panchina)
// in due colonne fatte con `HStack` e con `ColonneUguali`, e in una colonna sola. Fallisce sempre, apposta, per scrivere i tempi
// nel registro della corsa (la riga contiene «failed:», che il passo «Righe con errori» raccoglie).

@MainActor
@Suite("Diagnosi #846: due colonne con HStack o con ColonneUguali (da togliere)")
struct DiagnosiTempi846Tests {
    private static func ms(_ d: Duration) -> String {
        let c = d.components
        return String(format: "%.0f ms", Double(c.seconds) * 1000 + Double(c.attoseconds) / 1e15)
    }

    /// Il tempo della prima disposizione di `vista` in una finestra vera di 940 x 834 punti (iPad orizzontale).
    private static func prima<V: View>(_ vista: V) -> String {
        guard let scena = UIApplication.shared.connectedScenes.compactMap({ $0 as? UIWindowScene }).first else { return "senza scena" }
        let finestra = UIWindow(windowScene: scena)
        finestra.frame = CGRect(x: 0, y: 0, width: 940, height: 834)
        let ospite = UIHostingController(rootView: vista.environment(\.horizontalSizeClass, .regular))
        finestra.rootViewController = ospite
        finestra.isHidden = false
        let t = ContinuousClock().measure {
            ospite.view.setNeedsLayout()
            ospite.view.layoutIfNeeded()
        }
        finestra.isHidden = true
        finestra.rootViewController = nil
        return ms(t)
    }

    private static func sinistra(_ f: Formazione, _ v: VistaFormazione, _ oggi: Oggi?) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            TestaFormazioneView(oggi: oggi, formazione: f) { _ in }
            CampoFormazione(titolari: v.titolari, apribile: true)
        }
    }

    private static func destra(_ v: VistaFormazione) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            Carta("Panchina", simbolo: "chair.lounge.fill") {
                ForEach(Array(v.panchina.enumerated()), id: \.element.id) { i, g in
                    RigaConFilo(prima: i == 0) { RigaGiocatore(g: g, apribile: true) }
                }
            }
        }
    }

    @Test("Tempi delle due colonne")
    func tempi() async throws {
        var righe: [String] = []
        let demo = try #require(FinteServer.demoFase("formazione-in-corso"))
        let srv = ServerDiProva(indirizzo: "https://prova-846-tempi-\(UUID().uuidString).invalid") { metodo, percorso, corpo in
            try await demo.richiesta(metodo, percorso, corpo: corpo)
        }
        let oggi = OggiViewModel(server: srv, conPromemoria: false)
        let vm = FormazioneViewModel(server: srv, oggi: oggi, promemoria: {})
        await FormazioneView.ricarica(vm, oggi: oggi)
        let f = try #require(vm.formazione)
        let v = vm.vista(f)
        let g = oggi.oggi

        // una prima volta per caricare caratteri e simboli, poi le misure
        righe.append("riscaldamento " + Self.prima(ScrollView { Self.sinistra(f, v, g).padding(.horizontal, 16) }))
        righe.append("hstack " + Self.prima(ScrollView {
            HStack(alignment: .top, spacing: 14) { Self.sinistra(f, v, g); Self.destra(v) }.padding(.horizontal, 16)
        }))
        righe.append("uguali " + Self.prima(ScrollView {
            ColonneUguali(spazio: 14) { Self.sinistra(f, v, g); Self.destra(v) }.padding(.horizontal, 16)
        }))
        righe.append("una colonna " + Self.prima(ScrollView {
            VStack(alignment: .leading, spacing: 14) { Self.sinistra(f, v, g); Self.destra(v) }.padding(.horizontal, 16)
        }))
        righe.append("hstack di nuovo " + Self.prima(ScrollView {
            HStack(alignment: .top, spacing: 14) { Self.sinistra(f, v, g); Self.destra(v) }.padding(.horizontal, 16)
        }))
        righe.append("solo campo hstack " + Self.prima(ScrollView {
            HStack(alignment: .top, spacing: 14) { CampoFormazione(titolari: v.titolari); Color.clear.frame(height: 10) }
        }))
        righe.append("solo panchina hstack " + Self.prima(ScrollView {
            HStack(alignment: .top, spacing: 14) { Color.clear.frame(height: 10); Self.destra(v) }
        }))

        Issue.record(Comment(rawValue: "tempi 846 failed: " + righe.joined(separator: " | ")))
    }
}
