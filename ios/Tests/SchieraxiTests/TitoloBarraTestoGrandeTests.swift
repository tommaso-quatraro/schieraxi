import SwiftUI
import Testing
@testable import Schieraxi

/// Issue #419 (storia: #211, #276, #293 con la #340). Con il testo grande (da `TitoloPagina.soglia`) le pagine con
/// `titoloPagina` avevano nella barra il titolo piccolo di sistema, che sta su una riga e taglia con «…»: nella pagina di una
/// squadra si leggeva «Gli Amici del B…» nella barra e, subito sotto, lo stesso nome intero (`TitoloNellaPagina`).
/// Regola: un nome non compare mai tagliato in un punto e intero in un altro. Da XXL in su la barra resta senza titolo e il
/// titolo intero sta nella pagina. VoiceOver legge il nome una volta sola: sotto la soglia nella barra, da XXL in su nella
/// pagina, come intestazione. Il conteggio vero, sull'app con la barra vera, sta in `TitoloUnaVoltaUITests`.
@Suite("Testo grande: nella barra il titolo intero o niente, mai tagliato")
struct TitoloBarraTestoGrandeTests {

    /// Le dimensioni del testo dalla soglia in su.
    private static let testoGrande: [DynamicTypeSize] = [.xxLarge, .xxxLarge, .accessibility1, .accessibility2, .accessibility3,
                                                         .accessibility4, .accessibility5]

    @Test("Con ogni dimensione del testo la barra ha il titolo grande, il titolo intero a capo o niente: mai il titolo piccolo di sistema, che taglia")
    func maiIlTitoloCheTaglia() {
        for dimensione in DynamicTypeSize.allCases {
            for piccoloInBarra in [false, true] {
                let modi = [TitoloPagina.grandeInBarra(dimensione, piccoloInBarra: piccoloInBarra),
                            TitoloPagina.interoInBarra(dimensione, piccoloInBarra: piccoloInBarra),
                            TitoloPagina.barraSenzaTitolo(dimensione)]
                #expect(modi.filter { $0 }.count == 1, "\(dimensione), piccoloInBarra \(piccoloInBarra): \(modi)")
            }
            #expect(TitoloPagina.barraSenzaTitolo(dimensione) == Self.testoGrande.contains(dimensione), "\(dimensione)")
            // la barra resta senza titolo solo dove il titolo intero c'è nella pagina
            #expect(TitoloPagina.barraSenzaTitolo(dimensione) == TitoloPagina.nellaPagina(dimensione), "\(dimensione)")
        }
    }

    /// Chi legge VoiceOver: la barra (titolo grande di sistema o `TitoloInBarra`, intestazione) quando ha un titolo; la
    /// pagina (`TitoloNellaPagina`, intestazione) se il titolo c'è e non è nascosto.
    @Test("VoiceOver legge il titolo una volta sola: nella barra con il testo normale, nella pagina come intestazione con il testo grande",
          arguments: DynamicTypeSize.allCases)
    func voceUnaVolta(dimensione: DynamicTypeSize) {
        #expect(TitoloPagina.voceNellaPagina(dimensione) == Self.testoGrande.contains(dimensione))
        for piccoloInBarra in [false, true] {
            let barraLetta = TitoloPagina.grandeInBarra(dimensione, piccoloInBarra: piccoloInBarra)
                || TitoloPagina.interoInBarra(dimensione, piccoloInBarra: piccoloInBarra)
            let paginaLetta = TitoloPagina.nellaPagina(dimensione) && TitoloPagina.voceNellaPagina(dimensione)
            #expect(barraLetta != paginaLetta, "\(dimensione), piccoloInBarra \(piccoloInBarra): barra \(barraLetta), pagina \(paginaLetta)")
        }
    }
}
