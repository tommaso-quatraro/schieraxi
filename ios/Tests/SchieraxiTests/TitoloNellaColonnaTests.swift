import SwiftUI
import Testing
import UIKit
@testable import Schieraxi

/// Sull'iPad le pagine a colonna (Impostazioni e le sue pagine, #896) avevano il titolo grande della barra al bordo dello schermo,
/// lontano dalla colonna da 720 punti (#930, punto 3): la barra di iOS non riceve i margini della colonna, e la colonna sulla
/// `NavigationStack` faceva sparire le liste in orizzontale (#919). Qui il titolo va nella pagina, in cima alla colonna, come già
/// con il testo grande (`TitoloNellaPagina`), e la barra resta senza titolo. Solo sull'iPad largo e alto e solo per le pagine con il
/// titolo grande; sull'iPhone e nelle pagine con il titolo piccolo nella barra non cambia niente.
@Suite("iPad: il titolo delle pagine a colonna sta nella colonna")
struct TitoloNellaColonnaTests {

    @Test("Nella colonna dell'iPad il titolo è nella pagina con ogni dimensione del testo, e la barra resta senza titolo")
    func nellaColonnaSempreNellaPagina() {
        for d in DynamicTypeSize.allCases {
            #expect(TitoloPagina.nellaPagina(d, inColonna: true), "\(d)")
            #expect(!TitoloPagina.grandeInBarra(d, inColonna: true), "\(d)")
            #expect(TitoloPagina.barraSenzaTitolo(d, inColonna: true), "\(d)")
            #expect(TitoloPagina.voceNellaPagina(d, inColonna: true), "\(d): VoiceOver lo legge una volta, nella pagina")
            // fuori dalla colonna come prima
            #expect(TitoloPagina.nellaPagina(d, inColonna: false) == TitoloPagina.nellaPagina(d), "\(d)")
            #expect(TitoloPagina.grandeInBarra(d, inColonna: false) == TitoloPagina.grandeInBarra(d), "\(d)")
            #expect(TitoloPagina.barraSenzaTitolo(d, inColonna: false) == TitoloPagina.barraSenzaTitolo(d), "\(d)")
        }
    }

    @Test("Solo le pagine con il titolo grande: quelle con il titolo piccolo nella barra restano come prima")
    func soloIlTitoloGrande() {
        #expect(TitoloPagina.inColonna(iPadLargo: true, piccoloInBarra: false))
        #expect(!TitoloPagina.inColonna(iPadLargo: true, piccoloInBarra: true))
        #expect(!TitoloPagina.inColonna(iPadLargo: false, piccoloInBarra: false))
        #expect(!TitoloPagina.inColonna(iPadLargo: false, piccoloInBarra: true))
    }

    @Test("Il titolo nella colonna solo sull'iPad largo e alto, non sugli iPhone in orizzontale", arguments: DispositivoDiProva.tutti)
    func soloSullIPadLargoEAlto(d: DispositivoDiProva) {
        #expect(TitoloPagina.titoloNellaColonna(orizzontale: d.orizzontale, verticale: d.verticale) == d.iPad)
    }

    /// Comportamento vero: `.titoloPagina` legge dall'ambiente se la pagina è nella colonna dell'iPad e `TitoloNellaPagina` si
    /// disegna. `ImageRenderer` non disegna le `List`: qui una `VStack`, che come la lista non dà spazio a un elemento vuoto.
    @MainActor
    @Test("Con il testo normale il titolo si vede nella colonna dell'iPad; sull'iPhone e con il titolo piccolo no")
    func siVedeNellaColonna() {
        func altezza(colonna: Bool, piccolo: Bool = false) -> CGFloat {
            let vista = VStack(spacing: 0) { TitoloNellaPagina() }
                .titoloPagina("Impostazioni", piccoloInBarra: piccolo)
                .environment(\.titoloNellaColonna, colonna)
                .frame(width: 720)
                .dynamicTypeSize(.large)
            let disegno = ImageRenderer(content: vista)
            disegno.scale = 1
            return disegno.uiImage?.size.height ?? 0
        }
        #expect(altezza(colonna: true) > 0, "iPad: il titolo è nella pagina")
        #expect(altezza(colonna: false) == 0, "iPhone: resta il titolo grande della barra")
        #expect(altezza(colonna: true, piccolo: true) == 0, "titolo piccolo nella barra: come prima")
    }
}
