import SwiftUI
import Testing
@testable import Schieraxi

/// «Tutti i numeri» del Confronto «Chi schierare?» (issue #272). I nomi in testa alle due colonne stavano su una riga sola
/// (`.lineLimit(1)`, colonne da 80 punti): un nome lungo finiva con «…», con il testo grande quasi tutti.
/// Si misura con `ImageRenderer` come `NomiInteriTests`: con una larghezza proposta l'immagine è alta quanto la vista, e un
/// nome tagliato non fa crescere la tabella quando si allunga. Nomi inventati.
@Suite("Confronto: tutti i numeri interi con il testo grande")
struct ConfrontoNumeriTests {

    /// Il contenuto della scheda su un iPhone largo 390 punti: margini della pagina (16) e della scheda (12) per lato.
    private static let larghezza: CGFloat = 334
    /// Già su più righe nella sua colonna; il secondo ha due parole in più.
    private static let nomeLungo = "Gianmarco Pierantoni Castelvecchi"
    private static let nomeLunghissimo = "Gianmarco Pierantoni Castelvecchi Bartolomei Santangelo"
    /// Testo normale, «testo grande» e «testo massimo» (le taglie delle foto).
    private static let taglie: [DynamicTypeSize] = [.large, .accessibility2, .accessibility5]

    /// L'altezza che la vista si prende quando è larga `larghezza` punti, alla taglia del testo data.
    @MainActor
    private static func altezza<V: View>(_ vista: V, taglia: DynamicTypeSize,
                                         larghezza: CGFloat = ConfrontoNumeriTests.larghezza) -> CGFloat {
        let disegno = ImageRenderer(content: vista.dynamicTypeSize(taglia))
        disegno.proposedSize = ProposedViewSize(width: larghezza, height: nil)
        disegno.scale = 1
        return disegno.uiImage?.size.height ?? 0
    }

    /// L'altezza di una riga sola del carattere più piccolo della tabella (i nomi in testa alle colonne).
    @MainActor
    private static func riga(_ taglia: DynamicTypeSize) -> CGFloat {
        altezza(Text("Riga").font(.caption.bold()), taglia: taglia)
    }

    private static func giocatore(_ id: Int, _ nome: String) throws -> Giocatore {
        let json = #"""
        {"id": \#(id), "nome": "\#(nome)", "ruolo": "C", "squadra": "genoa", "avversario": "como", "in_casa": true,
         "p_voto": 0.8, "fv_atteso": 6.4, "punti_attesi": 5.12, "indice": 72, "difficolta": 3, "quota_titolare": 0.75,
         "p_gol": 0.18, "p_assist": 0.12, "p_giallo": 0.2}
        """#
        return try Decodifica.decodifica(Data(json.utf8))
    }

    @MainActor
    @Test("I nomi dei due giocatori si leggono interi, a capo, con il testo normale, grande e massimo")
    func nomiInteri() throws {
        let altro = try Self.giocatore(32, "Aldo Pinarotti")
        let lungo = try Self.giocatore(31, Self.nomeLungo)
        let lunghissimo = try Self.giocatore(31, Self.nomeLunghissimo)
        for taglia in Self.taglie {
            let primo = Self.altezza(TabellaNumeriConfronto(x: lunghissimo, y: altro), taglia: taglia)
                - Self.altezza(TabellaNumeriConfronto(x: lungo, y: altro), taglia: taglia)
            #expect(primo >= Self.riga(taglia) * 0.9, "\(taglia), primo giocatore: la tabella cresce solo di \(primo) punti, il nome è tagliato")
            let secondo = Self.altezza(TabellaNumeriConfronto(x: altro, y: lunghissimo), taglia: taglia)
                - Self.altezza(TabellaNumeriConfronto(x: altro, y: lungo), taglia: taglia)
            #expect(secondo >= Self.riga(taglia) * 0.9, "\(taglia), secondo giocatore: la tabella cresce solo di \(secondo) punti, il nome è tagliato")
        }
    }

    /// Quale delle due forme c'è: la tabella (come la web) se ogni parola sta intera nella sua colonna, altrimenti l'elenco.
    /// Si riconosce dall'altezza: è quella della tabella da sola o dell'elenco da solo (che sono diverse).
    @MainActor
    @Test("Tabella con il testo normale; elenco con il testo grande e massimo, e quando la scheda è troppo stretta")
    func tabellaOElenco() throws {
        let x = try Self.giocatore(31, "Aldo Pinarotti"), y = try Self.giocatore(32, "Bruno Castelvecchi")
        let voci = VoceNumeriConfronto.voci(x, y)
        let casi: [(DynamicTypeSize, CGFloat, Bool)] = [
            (.large, Self.larghezza, true),
            (.accessibility2, Self.larghezza, false),
            (.accessibility5, Self.larghezza, false),
            // «Avversario» non ci sta in una colonna da 48 punti: niente parola spezzata, si passa all'elenco
            (.large, 150, false),
        ]
        for (taglia, larghezza, inTabella) in casi {
            let vista = Self.altezza(TabellaNumeriConfronto(x: x, y: y), taglia: taglia, larghezza: larghezza)
            let tabella = Self.altezza(NumeriInTabella(x: x, y: y, voci: voci), taglia: taglia, larghezza: larghezza)
            let elenco = Self.altezza(NumeriInElenco(x: x, y: y, voci: voci), taglia: taglia, larghezza: larghezza)
            #expect(abs(tabella - elenco) >= 1, "\(taglia), \(larghezza) punti: tabella ed elenco alti uguali, la prova non vale")
            let attesa = inTabella ? tabella : elenco
            #expect(abs(vista - attesa) < 1,
                    "\(taglia), \(larghezza) punti: attesa \(inTabella ? "la tabella" : "l'elenco") (\(attesa)), disegnata alta \(vista)")
        }
    }

    @MainActor
    @Test("Colonne della tabella in parti 1,2 : 1 : 1 della riga, come la web")
    func colonne() {
        let colonne = RigaTreColonne.colonne(larghezza: 334, spazio: 10)
        #expect(colonne.count == 3)
        #expect(abs(colonne.reduce(0, +) + 20 - 334) < 0.001)
        #expect(abs(colonne[0] - 117.75) < 0.001)
        #expect(abs(colonne[1] - 98.125) < 0.001 && abs(colonne[2] - 98.125) < 0.001)
        #expect(RigaTreColonne.colonne(larghezza: 10, spazio: 10).allSatisfy { $0 == 0 }, "riga più stretta degli spazi: colonne vuote, mai negative")
    }

    @MainActor
    @Test("Larghezza che serve: la colonna più esigente decide, tenendo conto della sua parte")
    func larghezzaNecessaria() {
        // un numero che chiede 98,125 punti nella sua colonna: la riga deve essere larga 334
        #expect(abs(RigaTreColonne.larghezzaNecessaria(minime: [50, 98.125, 60], spazio: 10) - 334) < 0.001)
        // la voce ha una parte più grande (1,2): con 117,75 punti chiede la stessa riga
        #expect(abs(RigaTreColonne.larghezzaNecessaria(minime: [117.75, 0, 0], spazio: 10) - 334) < 0.001)
        #expect(RigaTreColonne.larghezzaNecessaria(minime: [], spazio: 10) == 20)
    }
}
