import Foundation
import SwiftUI
import Testing
import UIKit
@testable import Schieraxi

// Issue #848 (punto 1) e #857 (punto 2). Con il testo grande la barra di Impostazioni è vuota e su iOS 26 non sfuma i contenuti:
// righe e titoli («Aspetto» con il testo massimo) passavano nitidi sotto l'ora. `bordoSottoLaBarraVuota()` copre la fascia
// dell'ora e della barra con lo sfondo della pagina. La prima versione leggeva l'altezza in un `GeometryReader` che ignorava
// il margine sicuro: lì il margine vale 0, la fascia era alta 0 e le foto della corsa 44819951481 erano uguali a quelle di main.
// Qui la pagina vera (lista con `Sfondo()`, titolo nella pagina) sta in una finestra grande come lo schermo del simulatore e si
// guarda l'altezza con cui la fascia si disegna: almeno l'ora più la barra.

/// Le altezze che la fascia riceve (sul thread principale).
private final class Altezze: @unchecked Sendable {
    var valori: [CGFloat] = []
}

@MainActor
@Suite("Impostazioni con il testo grande: la fascia sotto la barra vuota copre l'ora e la barra (#848, #857)")
struct BordoSottoLaBarraVuotaTests {
    /// La pagina come Impostazioni in una finestra grande come lo schermo, con il testo `dimensione`. Restituisce le altezze
    /// della fascia (nessuna se la fascia non c'è) e il margine sicuro in alto della finestra (l'ora e l'isola).
    private static func misura(_ dimensione: DynamicTypeSize) async throws -> (altezze: [CGFloat], ora: CGFloat) {
        let scena = try #require(UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }.first,
                                 "l'app che ospita i test ha una scena")
        let finestra = UIWindow(windowScene: scena)
        finestra.frame = scena.coordinateSpace.bounds
        let altezze = Altezze()
        let pagina = NavigationStack {
            List {
                TitoloNellaPagina()
                ForEach(0..<30, id: \.self) { Text("Riga \($0)") }
            }
            .scrollContentBackground(.hidden)
            .background(Sfondo())
            .bordoSottoLaBarraVuota { altezze.valori.append($0) }
            .titoloPagina("Impostazioni")
        }
        .dynamicTypeSize(dimensione)
        let ospite = UIHostingController(rootView: pagina)
        finestra.rootViewController = ospite
        finestra.isHidden = false
        defer {
            finestra.isHidden = true
            finestra.rootViewController = nil
        }
        // la misura arriva dopo la prima disposizione: si aspetta al più due secondi una misura più grande di 0
        for _ in 0..<40 where !(altezze.valori.last.map { $0 > 0 } ?? false) {
            ospite.view.setNeedsLayout()
            ospite.view.layoutIfNeeded()
            try await Task.sleep(for: .milliseconds(50))
        }
        return (altezze.valori, finestra.safeAreaInsets.top)
    }

    @available(iOS 26.0, *)
    @Test("Con il testo massimo la fascia c'è ed è alta più dell'ora: copre anche la barra, mai 0")
    func testoMassimo() async throws {
        let (altezze, ora) = try await Self.misura(.accessibility5)
        let altezza = try #require(altezze.last, "con il testo massimo la fascia deve esserci")
        #expect(ora > 0, "la finestra del simulatore ha l'ora in alto")
        #expect(altezza > ora, "la fascia è alta \(altezza) punti: deve coprire l'ora (\(ora)) e la barra sotto")
    }

    @available(iOS 26.0, *)
    @Test("Con il testo normale niente fascia: c'è il titolo piccolo della barra, che sfuma da solo")
    func testoNormale() async throws {
        let (altezze, _) = try await Self.misura(.large)
        #expect(altezze.isEmpty, "testo normale: la fascia non deve esserci (\(altezze))")
    }
}
