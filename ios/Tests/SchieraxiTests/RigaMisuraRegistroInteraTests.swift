import SwiftUI
import Testing
@testable import Schieraxi

/// Le righe delle misure di Stato dei dati (`RigaMisuraRegistro`: registro, gol attesi nostri, consiglio di formazione) si leggono
/// intere (issue #430). Nella foto `lega-stato-fondo` «Cambi della consigliata nelle 24 ore prima della scadenza» finiva con
/// «…prima…» su una riga, mentre un'altra riga più lunga andava a capo: il nome stava in una `VStack` dentro `ViewThatFits`, e
/// quando la riga riceveva meno altezza di quella che chiede, `VStack` stringeva il testo a una riga con i puntini.
/// Regola del progetto: le etichette non si tagliano, vanno a capo (#227, #230, #254).
/// Si misura con `ImageRenderer` come `NomiInteriTests`: la vista non deve diventare più bassa quando le si propone poca altezza,
/// e deve essere alta almeno quanto il nome e i dettagli interi messi uno sotto l'altro.
@Suite("Stato dei dati: le righe delle misure restano intere")
struct RigaMisuraRegistroInteraTests {

    /// Una riga su iPhone nella lista (402 punti meno margini e rientri), e una colonna larga dell'iPad.
    private static let larghezze: [CGFloat] = [338, 678]
    /// Testo normale e le due taglie delle foto: «testo grande» e «testo massimo».
    private static let taglie: [DynamicTypeSize] = [.large, .accessibility2, .accessibility5]
    /// Poca altezza: quella di una riga scarsa. Una riga che si piega a questa proposta taglia il testo.
    private static let altezzaScarsa: CGFloat = 24

    /// L'altezza che la vista si prende quando è larga `larghezza` punti e le si propone `altezza` (nil = quanta ne chiede).
    @MainActor
    private static func altezza<V: View>(_ vista: V, larghezza: CGFloat, proposta altezza: CGFloat? = nil,
                                         taglia: DynamicTypeSize) -> CGFloat {
        let disegno = ImageRenderer(content: vista.dynamicTypeSize(taglia))
        disegno.proposedSize = ProposedViewSize(width: larghezza, height: altezza)
        disegno.scale = 1
        return disegno.uiImage?.size.height ?? 0
    }

    /// Le righe vere del consiglio di formazione (le stesse testo per testo della foto): la più lunga è «Cambi della consigliata…».
    private static let righe: [(nome: String, esito: ParoleRegistro.Esito, dettaglio: String)] = [
        (ParoleConsiglio.nome(.stabilita), .nonRegge,
         "1,3 a formazione, in media · per meno di 1 punto atteso, senza un titolare diventato fuori o improbabile: 2 (devono essere 0)"),
        (ParoleConsiglio.nome(.valore), .regge,
         "+2,14 punti a giornata (deve stare a 0 o più) · +0,63 rispetto alla formazione schierata, quando è diversa"),
        (ParoleConsiglio.nome(.perche), .regge,
         "spiegate 9 su 9 (devono essere tutte) · titolari senza un motivo loro in «Perché questo numero»: 6,1% (al massimo 10%)"),
    ]

    @MainActor
    @Test("Con poca altezza proposta la riga non si stringe: il nome e i dettagli non finiscono con «…»")
    func nonSiStringeConPocaAltezza() {
        for riga in Self.righe {
            for larghezza in Self.larghezze {
                for taglia in Self.taglie {
                    let vista = RigaMisuraRegistro(nome: riga.nome, esito: riga.esito, dettaglio: riga.dettaglio)
                    let libera = Self.altezza(vista, larghezza: larghezza, taglia: taglia)
                    let scarsa = Self.altezza(vista, larghezza: larghezza, proposta: Self.altezzaScarsa, taglia: taglia)
                    #expect(libera > 0, "\(riga.nome), \(larghezza) punti, \(taglia): la vista non si disegna")
                    #expect(scarsa >= libera - 1,
                            "\(riga.nome), \(larghezza) punti, \(taglia): con poca altezza la riga scende a \(scarsa) punti invece di \(libera): il testo è tagliato")
                }
            }
        }
    }

    @MainActor
    @Test("La riga è alta almeno quanto il nome e i dettagli interi, uno sotto l'altro")
    func altaQuantoITestiInteri() {
        for riga in Self.righe {
            for larghezza in Self.larghezze {
                for taglia in Self.taglie {
                    let vista = RigaMisuraRegistro(nome: riga.nome, esito: riga.esito, dettaglio: riga.dettaglio)
                    let nomeIntero = Self.altezza(Text(riga.nome), larghezza: larghezza, taglia: taglia)
                    let dettaglioIntero = Self.altezza(Text(riga.dettaglio).font(.footnote).monospacedDigit(), larghezza: larghezza, taglia: taglia)
                    let alta = Self.altezza(vista, larghezza: larghezza, taglia: taglia)
                    #expect(alta >= nomeIntero + dettaglioIntero - 1,
                            "\(riga.nome), \(larghezza) punti, \(taglia): la riga è alta \(alta) punti, nome e dettagli interi ne chiedono \(nomeIntero + dettaglioIntero)")
                }
            }
        }
    }
}
