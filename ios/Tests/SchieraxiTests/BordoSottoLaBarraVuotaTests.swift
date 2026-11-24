import Foundation
import SwiftUI
import Testing
import UIKit
@testable import Schieraxi

// Issue #848 (punto 1). Con il testo grande la barra di Impostazioni è vuota e su iOS 26 non sfuma i contenuti: righe e titoli
// passavano nitidi sotto l'ora. `bordoSottoLaBarraVuota()` copre la fascia dell'ora e della barra con lo sfondo della pagina.
// L'altezza della fascia ha due limiti, e ognuno ha già fallito con una versione sbagliata:
// - sotto: almeno il margine dell'ora. Altezza letta in un `GeometryReader` che ignorava il margine sicuro, dove il margine vale
//   0: fascia alta 0 (corsa 44826690071, foto della corsa 44819951481 uguali a main);
// - sopra: mai oltre la cima del titolo nella pagina. Cima della parte sicura più il margine che le restava, cioè il margine
//   contato due volte: fascia fino a 124 punti sull'iPhone (2 × 62), titolo a 112, «Impostazioni» sbiadito da fermo (corsa
//   44838926206, foto della corsa 44833454399).
// Qui la pagina vera (lista con `Sfondo()`, titolo nella pagina, dentro una barra delle schede come l'app) sta in una finestra
// grande come lo schermo del simulatore e si confronta il riquadro della fascia con l'ora e con il titolo della pagina. Il test
// misura l'altezza, non il disegno (che la fascia stia sopra le righe e abbia gli stessi colori dello sfondo): quello lo provano
// le foto.

/// Il riquadro della fascia e la cima del titolo nella pagina, nello spazio `.global` (sul thread principale).
private final class Misure: @unchecked Sendable {
    var fascia: [CGRect] = []
    var titolo: CGFloat?
}

@MainActor
@Suite("Impostazioni con il testo grande: la fascia sotto la barra vuota copre l'ora e non arriva al titolo (#848)")
struct BordoSottoLaBarraVuotaTests {
    /// La pagina come Impostazioni in una finestra grande come lo schermo, con il testo `dimensione`. Restituisce le misure e il
    /// margine sicuro in alto della finestra (l'ora e l'isola).
    private static func misura(_ dimensione: DynamicTypeSize) async throws -> (misure: Misure, ora: CGFloat) {
        let scena = try #require(UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }.first,
                                 "l'app che ospita i test ha una scena")
        let finestra = UIWindow(windowScene: scena)
        finestra.frame = scena.coordinateSpace.bounds
        let misure = Misure()
        let pagina = TabView {
            Tab("Impostazioni", systemImage: "gearshape") {
                NavigationStack {
                    List {
                        TitoloNellaPagina()
                            .onGeometryChange(for: CGFloat.self) { $0.frame(in: .global).minY } action: { misure.titolo = $0 }
                        ForEach(0..<30, id: \.self) { Text("Riga \($0)") }
                    }
                    .scrollContentBackground(.hidden)
                    .background(Sfondo())
                    .bordoSottoLaBarraVuota { misure.fascia.append($0) }
                    .titoloPagina("Impostazioni")
                }
            }
        }
        .tabViewStyle(.sidebarAdaptable)
        .dynamicTypeSize(dimensione)
        let ospite = UIHostingController(rootView: pagina)
        finestra.rootViewController = ospite
        finestra.isHidden = false
        defer {
            finestra.isHidden = true
            finestra.rootViewController = nil
        }
        // le misure arrivano dopo le prime disposizioni: si aspetta al più due secondi una fascia più alta di 0 e il titolo
        for _ in 0..<40 where !((misure.fascia.last.map { $0.height > 0 } ?? false) && misure.titolo != nil) {
            ospite.view.setNeedsLayout()
            ospite.view.layoutIfNeeded()
            try await Task.sleep(for: .milliseconds(50))
        }
        return (misure, finestra.safeAreaInsets.top)
    }

    @available(iOS 26.0, *)
    @Test("Con il testo massimo la fascia copre l'ora e finisce prima del titolo della pagina: mai alta 0, mai sopra il titolo")
    func testoMassimo() async throws {
        let (misure, ora) = try await Self.misura(.accessibility5)
        let fascia = try #require(misure.fascia.last, "con il testo massimo la fascia deve esserci")
        let titolo = try #require(misure.titolo, "con il testo massimo il titolo sta nella pagina")
        #expect(ora > 0, "la finestra del simulatore ha l'ora in alto")
        // limite sotto: con la fascia alta 0 i contenuti passano nitidi sotto l'ora
        #expect(fascia.height >= ora - 0.5, "la fascia è alta \(fascia.height) punti: deve coprire almeno l'ora (\(ora))")
        // limite sopra: con il margine contato due volte la fascia finiva a due volte l'ora, oltre la cima del titolo
        #expect(fascia.maxY <= titolo + 0.5,
                "la fascia finisce a \(fascia.maxY) punti, oltre la cima del titolo (\(titolo)): da ferma lo sbiadisce")
    }

    @available(iOS 26.0, *)
    @Test("Con il testo normale niente fascia: c'è il titolo piccolo della barra, che sfuma da solo")
    func testoNormale() async throws {
        let (misure, _) = try await Self.misura(.large)
        #expect(misure.fascia.isEmpty, "testo normale: la fascia non deve esserci (\(misure.fascia))")
    }
}
