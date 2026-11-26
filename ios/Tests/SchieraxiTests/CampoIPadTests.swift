import CoreGraphics
import Testing
@testable import Schieraxi

/// Il campo della Formazione sull'iPad (#896). Prima la linea di metà campo e il cerchio stavano a metà altezza, qualunque fosse
/// l'altezza delle file: con il testo grande il campo largo e basso metteva il cerchio sopra il volto di un difensore e «Partita
/// in corso» sopra la linea. Ora fra centrocampo e difesa c'è una fascia libera dove passano linea e cerchio, e il campo è alto
/// almeno tre quarti della sua larghezza. Le altezze delle file sono inventate (quelle delle foto dell'iPad, in punti).
@MainActor
@Suite("Campo dell'iPad: la metà campo fra centrocampo e difesa, mai sopra volti e nomi")
struct CampoIPadTests {
    /// Attacco, centrocampo, difesa, portiere: come nella foto dell'iPad col testo grande (il portiere senza la riga dello stato).
    static let file: [CGFloat] = [86, 85, 86, 69]
    /// Il diametro del cerchio di centrocampo.
    static let cerchio: CGFloat = 68

    @Test("Con le file più alte del minimo le file stanno vicine e la fascia ha l'altezza di base")
    func campoStretto() {
        let m = DisposizioneCampo.misure(altezze: Self.file, larghezza: 363)
        #expect(m.cime == [0, 96, 265, 361])
        #expect(m.fasciaCima == 181)
        #expect(m.fasciaAltezza == DisposizioneCampo.fascia)
        #expect(m.altezza == 430)
    }

    @Test("Il cerchio sta tutto nella fascia, con aria sopra e sotto, e la fascia sta fra centrocampo e difesa",
          arguments: [CGFloat(300), 363, 441, 720, 802])
    func cerchioLibero(larghezza: CGFloat) {
        let m = DisposizioneCampo.misure(altezze: Self.file, larghezza: larghezza)
        #expect(m.fasciaAltezza - Self.cerchio >= 16, "\(larghezza): fascia di \(m.fasciaAltezza) punti per un cerchio di \(Self.cerchio)")
        #expect(m.fasciaCima >= m.cime[1] + Self.file[1], "la fascia comincia sopra la fine del centrocampo")
        #expect(m.cime[2] >= m.fasciaCima + m.fasciaAltezza, "la difesa comincia dentro la fascia")
    }

    @Test("Le file non si toccano e il campo finisce con il portiere", arguments: [CGFloat(300), 363, 720, 802])
    func fileInOrdine(larghezza: CGFloat) {
        let m = DisposizioneCampo.misure(altezze: Self.file, larghezza: larghezza)
        for i in 0..<(Self.file.count - 1) {
            #expect(m.cime[i + 1] >= m.cime[i] + Self.file[i] + DisposizioneCampo.spazio,
                    "\(larghezza): la fila \(i + 1) tocca quella sopra")
        }
        #expect(abs(m.altezza - (m.cime[3] + Self.file[3])) < 0.001)
    }

    @Test("Largo (testo grande, una colonna): alto almeno tre quarti della larghezza, lo spazio in più diviso fra le file",
          arguments: [CGFloat(720), 802])
    func campoLargo(larghezza: CGFloat) {
        let m = DisposizioneCampo.misure(altezze: Self.file, larghezza: larghezza)
        #expect(abs(m.altezza - larghezza * DisposizioneCampo.rapporto) < 0.001, "alto \(m.altezza) su \(larghezza)")
        let primoSpazio = m.cime[1] - Self.file[0]
        let ultimoSpazio = m.cime[3] - (m.cime[2] + Self.file[2])
        #expect(primoSpazio > DisposizioneCampo.spazio, "lo spazio in più va anche fra le file")
        #expect(abs(primoSpazio - ultimoSpazio) < 0.001)
        #expect(abs((m.fasciaAltezza - DisposizioneCampo.fascia) - (primoSpazio - DisposizioneCampo.spazio)) < 0.001,
                "la fascia cresce quanto gli altri spazi")
    }

    @Test("Senza file (dati non ancora arrivati) il campo non ha altezza né fascia")
    func senzaFile() {
        let m = DisposizioneCampo.misure(altezze: [], larghezza: 400)
        #expect(m.cime.isEmpty)
        #expect(m.altezza == 0)
        #expect(m.fasciaAltezza == 0)
    }
}
