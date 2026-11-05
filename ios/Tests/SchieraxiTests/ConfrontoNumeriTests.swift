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

    @MainActor
    private static func altezza<V: View>(_ vista: V, taglia: DynamicTypeSize) -> CGFloat {
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
}
