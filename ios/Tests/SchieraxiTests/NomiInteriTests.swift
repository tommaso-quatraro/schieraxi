import SwiftUI
import Testing
@testable import Schieraxi

/// Nomi dei giocatori interi con il testo grande (issue #254). Dopo #247 restava `.lineLimit(2)` sui nomi delle righe dei
/// giocatori (Formazione, Squadra, ricerche), di Oggi durante la giornata, della rosa di una squadra e del Confronto: con il
/// testo grande un nome lungo finiva con «…». Ora va a capo intero, senza testo rimpicciolito.
/// Si misura con `ImageRenderer` come `CambiConsigliatiInteriTests`: con una larghezza proposta l'immagine è alta quanto la vista.
/// Un testo tagliato a due righe non fa crescere la vista quando si allunga: per questo si confrontano due altezze.
/// Nomi e note inventati.
@Suite("Nomi dei giocatori interi con il testo grande")
struct NomiInteriTests {

    /// Una riga su iPhone: 390 punti meno i margini di 16 per lato.
    private static let larghezza: CGFloat = 358
    /// Con il testo grande stanno già su più di una riga; il secondo ha due parole in più.
    private static let nomeLungo = "Gianmarco Pierantoni Castelvecchi"
    private static let nomeLunghissimo = "Gianmarco Pierantoni Castelvecchi Bartolomei Santangelo"
    /// Le due taglie delle foto: «testo grande» e «testo massimo».
    private static let taglie: [DynamicTypeSize] = [.accessibility2, .accessibility5]

    /// L'altezza che la vista si prende quando è larga `larghezza` punti, alla taglia del testo data.
    @MainActor
    private static func altezza<V: View>(_ vista: V, larghezza: CGFloat = NomiInteriTests.larghezza,
                                         taglia: DynamicTypeSize) -> CGFloat {
        let disegno = ImageRenderer(content: vista.dynamicTypeSize(taglia))
        disegno.proposedSize = ProposedViewSize(width: larghezza, height: nil)
        disegno.scale = 1
        return disegno.uiImage?.size.height ?? 0
    }

    /// L'altezza di una riga sola del carattere dato.
    @MainActor
    private static func riga(_ font: Font, taglia: DynamicTypeSize) -> CGFloat {
        altezza(Text("Riga").font(font), taglia: taglia)
    }

    /// Con il testo `lungo` la vista deve crescere di almeno una riga rispetto a `corto`. Se il testo è tagliato a due righe le
    /// due viste sono alte uguali. La prova vale solo se anche `corto` intero, largo quanto tutta la riga, sta su più di una riga:
    /// dentro la vista ha meno spazio, quindi tagliato a due righe non crescerebbe.
    @MainActor
    private static func cresceIntero<V: View>(_ dove: String, font: Font = .headline, corto: String = NomiInteriTests.nomeLungo,
                                              lungo: String = NomiInteriTests.nomeLunghissimo,
                                              _ vista: (String) throws -> V) rethrows {
        for taglia in taglie {
            let interoCorto = altezza(Text(corto).font(font), taglia: taglia)
            #expect(interoCorto >= riga(font, taglia: taglia) * 1.9,
                    "\(dove), \(taglia): il testo corto sta su una riga, la prova non vale")
            let conLungo = try vista(lungo)
            let conCorto = try vista(corto)
            let cresce = altezza(conLungo, taglia: taglia) - altezza(conCorto, taglia: taglia)
            #expect(cresce >= riga(font, taglia: taglia) * 0.9,
                    "\(dove), \(taglia): la vista cresce solo di \(cresce) punti, il testo è tagliato")
        }
    }

    private static func giocatore(_ nome: String) throws -> Giocatore {
        let json = #"{"id": 31, "nome": "\#(nome)", "ruolo": "C", "squadra": "genoa", "avversario": "como", "in_casa": true, "p_voto": 0.8, "fv_atteso": 6.4}"#
        return try Decodifica.decodifica(Data(json.utf8))
    }

    @MainActor
    @Test("Righe dei giocatori (Formazione, Squadra, ricerche): il nome va a capo intero")
    func rigaGiocatore() throws {
        try Self.cresceIntero("RigaGiocatore") { RigaGiocatore(g: try Self.giocatore($0)) }
    }

    @MainActor
    @Test("Rosa di una squadra: il nome va a capo intero")
    func rigaRosa() {
        Self.cresceIntero("RigaRosa") { nome in
            RigaRosa(g: GiocatoreRosa(id: 34, nome: nome, ruolo: "D", squadra: "Prova", squadraSlug: nil, costo: 12,
                                      quotazione: 14, previsione: nil))
        }
    }

}
