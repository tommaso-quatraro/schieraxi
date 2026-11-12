import SwiftUI
import Testing
import UIKit
@testable import Schieraxi

/// Scheda del giocatore quando il server non manda il fantavoto atteso (issue #262):
/// scrivevano «0,0» (`fvAtteso ?? 0`), mentre la web e gli elenchi dei giocatori (#251) scrivono «–». Uno zero vero resta «0,0».
/// Si disegna con `ImageRenderer`: «–» è più stretto di «0,0», e la vista senza numero non deve essere uguale a quella con lo zero.
/// Dati inventati.
@Suite("Fantavoto che manca: «–» e non «0,0»")
struct FantavotoMancanteTests {

    /// Il carattere del numero grande del foglio.
    private static let carattere = Font.system(size: 48, weight: .bold, design: .rounded)

    /// Un giocatore inventato con il fantavoto scritto dal test (`null` = il server non lo manda). Senza `p_voto` («gioca 0%»):
    /// così l'altro numero della vista non si muove e i disegni si possono confrontare.
    private static func giocatore(fantavoto: String) throws -> Giocatore {
        let json = #"{"id": 41, "nome": "Leonel Marténi", "ruolo": "A", "squadra": "genoa", "fv_atteso": \#(fantavoto)}"#
        return try Decodifica.decodifica(Data(json.utf8))
    }

    @MainActor
    private static func immagine<V: View>(_ vista: V, larghezza: CGFloat? = nil) -> UIImage? {
        let disegno = ImageRenderer(content: vista)
        disegno.proposedSize = ProposedViewSize(width: larghezza, height: nil)
        disegno.scale = 1
        return disegno.uiImage
    }

    /// La misura di un testo con il carattere del numero grande, dato come quello della vista (dall'ambiente).
    @MainActor
    private static func misura<V: View>(_ vista: V) -> CGSize {
        immagine(vista.environment(\.font, carattere))?.size ?? .zero
    }

    @MainActor
    @Test("Il numero da solo: «–» se il server non lo manda, «0,0» se è zero")
    func numeroDaSolo() {
        let trattino = Self.misura(Text("–").monospacedDigit())
        let zeroScritto = Self.misura(Text("0,0").monospacedDigit())
        #expect(trattino.width > 0)
        #expect(trattino.width < zeroScritto.width - 4, "la prova ha senso solo se «–» è più stretto di «0,0»")

        let manca = Self.misura(FantavotoCheSale(valore: nil))
        let zero = Self.misura(FantavotoCheSale(valore: 0))
        #expect(manca == trattino, "senza numero è largo \(manca.width): «–» \(trattino.width), «0,0» \(zeroScritto.width)")
        #expect(zero == zeroScritto, "con lo zero è largo \(zero.width): «0,0» \(zeroScritto.width)")
    }

    @MainActor
    @Test("Scheda del giocatore: senza fantavoto non scrive «0,0»")
    func scheda() throws {
        let senza = try Self.giocatore(fantavoto: "null")
        let zero = try Self.giocatore(fantavoto: "0")
        try #require(senza.fvAtteso == nil)
        try #require(zero.fvAtteso == 0)
        let conSenza = try #require(Self.immagine(CifreScheda(cifre: LetturaScheda.cifre(senza)), larghezza: 358)?.pngData())
        let conZero = try #require(Self.immagine(CifreScheda(cifre: LetturaScheda.cifre(zero)), larghezza: 358)?.pngData())
        #expect(conSenza != conZero, "senza numero la scheda è disegnata come con lo zero: scrive «0,0»")
    }
}
