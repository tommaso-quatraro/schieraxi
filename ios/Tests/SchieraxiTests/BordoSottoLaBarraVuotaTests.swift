import Foundation
import SwiftUI
import Testing
import UIKit
@testable import Schieraxi

// Issue #848 (punto 1). Con il testo grande la barra di Impostazioni è vuota e su iOS 26 non sfuma i contenuti: righe e titoli
// passavano nitidi sotto l'ora. `bordoSottoLaBarraVuota()` copre la fascia dell'ora e della barra con lo sfondo della pagina.
// La fascia ha due limiti, e ognuno ha già fallito con una versione sbagliata:
// - sotto: piena almeno fino al fondo dell'ora (il margine sicuro in alto della finestra). Con la fascia alta 0 non c'era
//   (corsa 44826690071, foto della corsa 44819951481 uguali a main); alta quanto l'ora ma piena solo fino a 34 punti su 62,
//   scorrendo si vedevano lettere chiare dietro «9:41» e righe nitide accanto all'isola (foto della corsa 45493597395);
// - sopra: finisce almeno `margineTitolo` punti prima della cima del titolo nella pagina. Col margine contato due volte arrivava
//   a 124 punti sull'iPhone (2 × 62), oltre il titolo a 112, e da ferma sbiadiva «Impostazioni» (corse 44838926206 e
//   45486921898, foto della corsa 44833454399).
// Qui la pagina vera (lista con `Sfondo()`, titolo nella pagina, dentro una barra delle schede come l'app) sta in una finestra
// grande come lo schermo del simulatore e si confronta la fascia con l'ora e con il titolo della pagina. Il test misura dove la
// fascia è piena e dove finisce, non il disegno (che stia sopra le righe e abbia gli stessi colori dello sfondo): quello lo
// provano le foto.

/// Il riquadro della fascia, dove finisce la sua parte piena e la cima del titolo nella pagina, nello spazio `.global` (sul
/// thread principale).
private final class Misure: @unchecked Sendable {
    var fascia: [CGRect] = []
    var finePiena: CGFloat?
    var titolo: CGFloat?
}

@MainActor
@Suite("Impostazioni con il testo grande: la fascia sotto la barra vuota copre l'ora e non arriva al titolo (#848)")
struct BordoSottoLaBarraVuotaTests {
    /// Quanti punti almeno tra la fine della fascia e la cima del titolo: da ferma la fascia non deve toccarlo.
    static let margineTitolo: CGFloat = 8

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
                    .bordoSottoLaBarraVuota { fascia, finePiena in
                        misure.fascia.append(fascia)
                        misure.finePiena = finePiena
                    }
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
    @Test("Con il testo massimo la fascia è piena fin sotto l'ora e finisce prima del titolo della pagina, con un margine")
    func testoMassimo() async throws {
        let (misure, ora) = try await Self.misura(.accessibility5)
        let fascia = try #require(misure.fascia.last, "con il testo massimo la fascia deve esserci")
        let finePiena = try #require(misure.finePiena, "la fascia dice dove finisce la sua parte piena")
        let titolo = try #require(misure.titolo, "con il testo massimo il titolo sta nella pagina")
        #expect(ora > 0, "la finestra del simulatore ha l'ora in alto")
        // limite sotto: piena fino al fondo dell'ora, se no scorrendo le lettere si vedono dietro l'ora e accanto all'isola
        #expect(finePiena >= ora - 0.5,
                "la fascia è piena fino a \(finePiena) punti: deve esserlo almeno fino al fondo dell'ora (\(ora))")
        // limite sopra: con il margine contato due volte la fascia finiva a due volte l'ora, oltre la cima del titolo
        #expect(fascia.maxY <= titolo - Self.margineTitolo + 0.5,
                "la fascia finisce a \(fascia.maxY) punti: deve finire \(Self.margineTitolo) punti prima della cima del titolo (\(titolo))")
    }

    @available(iOS 26.0, *)
    @Test("Con il testo normale niente fascia: c'è il titolo piccolo della barra, che sfuma da solo")
    func testoNormale() async throws {
        let (misure, _) = try await Self.misura(.large)
        #expect(misure.fascia.isEmpty, "testo normale: la fascia non deve esserci (\(misure.fascia))")
    }
}
