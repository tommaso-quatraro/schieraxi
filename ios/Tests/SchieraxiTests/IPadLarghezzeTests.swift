import CoreGraphics
import SwiftUI
import Testing
@testable import Schieraxi

/// L'iPad come la web larga (#896): le pagine a elenco in una colonna di al massimo 720 punti (`.imp-colonna`), Giornate con
/// l'elenco largo al massimo 420 punti e la giornata a destra, la barra laterale subito con il testo molto grande. Sull'iPhone,
/// più stretto della colonna, non cambia niente. Qui i conti; l'aspetto si guarda nelle foto dell'iPad.
@MainActor
@Suite("iPad: colonne larghe come la web, iPhone invariato")
struct IPadLarghezzeTests {

    // MARK: pagine a elenco

    @Test("Sull'iPhone e fino a 720 punti nessun margine in più", arguments: [CGFloat(320), 390, 440, 719, 720])
    func strettaSenzaMargine(larghezza: CGFloat) {
        #expect(LarghezzaPagina.margine(larghezza: larghezza) == 0)
    }

    @Test("Oltre i 720 punti lo spazio in più va metà per lato: la colonna resta di 720", arguments: [
        (CGFloat(834), CGFloat(57)), (1024, 152), (1376, 328),
    ])
    func largaConMargine(larghezza: CGFloat, margine: CGFloat) {
        let m = LarghezzaPagina.margine(larghezza: larghezza)
        #expect(m == margine)
        #expect(larghezza - 2 * m <= LarghezzaPagina.colonna + 1, "la colonna è larga \(larghezza - 2 * m)")
    }

    @Test("Una misura che non c'è ancora (0) o infinita non dà margini")
    func misureStrane() {
        #expect(LarghezzaPagina.margine(larghezza: 0) == 0)
        #expect(LarghezzaPagina.margine(larghezza: .infinity) == 0)
        #expect(LarghezzaPagina.margine(larghezza: -5) == 0)
    }

    @Test("Le misure sono quelle della web larga: colonna 720, segmenti 520")
    func misureDellaWeb() {
        #expect(LarghezzaPagina.colonna == 720)
        #expect(LarghezzaPagina.segmenti == 520)
    }

    // MARK: Giornate

    @Test("Giornate: l'elenco prende metà dello spazio, al massimo 420 punti", arguments: [
        (CGFloat(700), CGFloat(350)), (834, 417), (1032, 420), (1376, 420),
    ])
    func elencoGiornate(totale: CGFloat, elenco: CGFloat) {
        #expect(ElencoEDettaglio.larghezzaElenco(totale: totale) == elenco)
    }

    @Test("Giornate: senza misura l'elenco non ha larghezza")
    func elencoSenzaMisura() {
        #expect(ElencoEDettaglio.larghezzaElenco(totale: 0) == 0)
        #expect(ElencoEDettaglio.larghezzaElenco(totale: .infinity) == 0)
    }

    // MARK: barra con il testo grande

    @Test("Sull'iPad con il testo molto grande si parte dalla barra laterale")
    func barraLateraleIPad() {
        #expect(RadiceView.barraLateraleSubito(orizzontale: .regular, verticale: .regular, testo: .accessibility1))
        #expect(RadiceView.barraLateraleSubito(orizzontale: .regular, verticale: .regular, testo: .accessibility5))
    }

    @Test("Con il testo normale, sull'iPhone e sull'iPad stretto la barra resta quella di iOS")
    func barraDiSistema() {
        // iPad con il testo normale o grande ma non molto grande
        #expect(!RadiceView.barraLateraleSubito(orizzontale: .regular, verticale: .regular, testo: .large))
        #expect(!RadiceView.barraLateraleSubito(orizzontale: .regular, verticale: .regular, testo: .xxxLarge))
        // iPhone in verticale, iPad in Split View stretta
        #expect(!RadiceView.barraLateraleSubito(orizzontale: .compact, verticale: .regular, testo: .accessibility3))
        // iPhone grande in orizzontale
        #expect(!RadiceView.barraLateraleSubito(orizzontale: .regular, verticale: .compact, testo: .accessibility3))
        // iPhone piccolo in orizzontale, misura non ancora nota
        #expect(!RadiceView.barraLateraleSubito(orizzontale: .compact, verticale: .compact, testo: .accessibility5))
        #expect(!RadiceView.barraLateraleSubito(orizzontale: nil, verticale: nil, testo: .accessibility5))
    }
}
