import CoreGraphics
import SwiftUI
import Testing
import UIKit
@testable import Schieraxi

/// Issue #419 (storia: #211, #276, #293 con la #340). Con il testo grande (da `TitoloPagina.soglia`) le pagine con
/// `titoloPagina` avevano nella barra il titolo piccolo di sistema, che sta su una riga e taglia con «…»: nella pagina di una
/// squadra si leggeva «Gli Amici del B…» nella barra e, subito sotto, lo stesso nome intero (`TitoloNellaPagina`).
/// Regola: un nome non compare mai tagliato in un punto e intero in un altro. Da XXL in su la barra mostra il titolo solo se
/// ci sta intero su una riga; se no non mostra niente, perché il nome intero sta già nella pagina. VoiceOver legge il nome una
/// volta sola: sotto la soglia nella barra, da XXL in su nella pagina, come intestazione (la barra è nascosta a VoiceOver).
/// Il conteggio vero di VoiceOver, sull'app, sta in `TitoloUnaVoltaUITests`.
@Suite("Testo grande: nella barra il titolo intero o niente, mai tagliato")
struct TitoloBarraTestoGrandeTests {

    /// Il nome della squadra della demo nella foto «lega-rosa»: 32 lettere, inventato.
    static let nomeLungo = "Gli Amici del Bar Sport Centrale"
    /// Un nome di 50 lettere, spazi compresi, inventato.
    static let nome50 = "Associazione Sportiva Amici del Bar Sport Centrale"
    /// Un titolo corto vero dell'app (Lega › Squadre).
    static let titoloCorto = "Squadre"
    /// Lo spazio del titolo nella barra di un iPhone stretto in verticale (come in `TitoloInBarraTests`).
    private static let larghezzaIPhone: CGFloat = 160
    /// Lo spazio del titolo nella barra della colonna di destra di un iPad.
    private static let larghezzaIPad: CGFloat = 600
    /// Lo spazio del titolo nella barra di un iPhone stretto in orizzontale.
    private static let larghezzaOrizzontale: CGFloat = 400
    /// L'altezza della barra piccola di un iPhone in orizzontale.
    private static let altezzaBarraOrizzontale: CGFloat = 32

    @Test("Con ogni dimensione del testo la barra ha un titolo intero (grande, a capo, o su una riga se ci sta): mai il titolo piccolo di sistema, che taglia")
    func maiIlTitoloCheTaglia() {
        for dimensione in DynamicTypeSize.allCases {
            for piccoloInBarra in [false, true] {
                let modi = [TitoloPagina.grandeInBarra(dimensione, piccoloInBarra: piccoloInBarra),
                            TitoloPagina.interoInBarra(dimensione, piccoloInBarra: piccoloInBarra),
                            TitoloPagina.inBarraSeCiSta(dimensione)]
                #expect(modi.filter { $0 }.count == 1, "\(dimensione), piccoloInBarra \(piccoloInBarra): \(modi)")
            }
            // la barra può lasciare fuori il titolo solo dove il titolo intero c'è nella pagina, e lì non lo taglia mai
            #expect(TitoloPagina.inBarraSeCiSta(dimensione) == TitoloPagina.nellaPagina(dimensione), "\(dimensione)")
        }
    }

    /// Chi legge VoiceOver: la barra (titolo grande di sistema o `TitoloInBarra`, intestazione) se non è nascosta, cioè
    /// quando non mostra il titolo «solo se ci sta»; la pagina (`TitoloNellaPagina`, intestazione) se il titolo c'è e non è
    /// nascosto. Con il testo grande la barra è nascosta a VoiceOver anche quando il titolo ci sta e si vede: se no un nome
    /// corto si sentirebbe due volte, nella barra e nella pagina.
    @Test("VoiceOver legge il titolo una volta sola: nella barra con il testo normale, nella pagina come intestazione con il testo grande",
          arguments: DynamicTypeSize.allCases)
    func voceUnaVolta(dimensione: DynamicTypeSize) {
        let testoGrande: [DynamicTypeSize] = [.xxLarge, .xxxLarge, .accessibility1, .accessibility2, .accessibility3, .accessibility4,
                                              .accessibility5]
        #expect(TitoloPagina.voceNellaPagina(dimensione) == testoGrande.contains(dimensione))
        for piccoloInBarra in [false, true] {
            let barraLetta = !TitoloPagina.inBarraSeCiSta(dimensione)
                && (TitoloPagina.grandeInBarra(dimensione, piccoloInBarra: piccoloInBarra)
                    || TitoloPagina.interoInBarra(dimensione, piccoloInBarra: piccoloInBarra))
            let paginaLetta = TitoloPagina.nellaPagina(dimensione) && TitoloPagina.voceNellaPagina(dimensione)
            #expect(barraLetta != paginaLetta, "\(dimensione), piccoloInBarra \(piccoloInBarra): barra \(barraLetta), pagina \(paginaLetta)")
        }
    }

    /// Comportamento vero del disegno: `ImageRenderer` dentro una colonna larga quanto il posto del titolo nella barra.
    /// (La barra stessa `ImageRenderer` non la disegna: lì il controllo sono le foto.)
    @MainActor
    @Test("Nome lungo con il testo grande su un iPhone: nella barra niente, nemmeno un riquadro vuoto (il nome intero è nella pagina)",
          arguments: [DynamicTypeSize.xxLarge, .accessibility1, .accessibility5])
    func nomeLungoNienteNellaBarra(dimensione: DynamicTypeSize) throws {
        let intero = try Self.disegna(Text(Self.nomeLungo).font(.headline), larghezza: nil, min(dimensione, .xxxLarge))
        try #require(CGFloat(intero.width) > Self.larghezzaIPhone, "il nome della prova deve essere più largo della barra")

        let titolo = Self.disegnaSeCe(TitoloInBarra(titolo: Self.nomeLungo, soloSeCiSta: true), larghezza: Self.larghezzaIPhone, dimensione)
        // alto zero: nessun testo trasparente che tiene il posto (VoiceOver ci metterebbe il riquadro su una zona vuota)
        #expect((titolo?.height ?? 0) == 0, "nella barra resta un riquadro alto \(titolo?.height ?? 0)")
        #expect((titolo.map(Self.pixelVisibili) ?? 0) == 0, "un nome che non ci sta non si mostra tagliato con «…»")
    }

    @MainActor
    @Test("Nome che ci sta con il testo grande: una riga intera, alta come il titolo piccolo di sistema (cresce fino a XXXL)",
          arguments: [DynamicTypeSize.xxLarge, .xxxLarge, .accessibility1, .accessibility3, .accessibility5])
    func nomeCheCiStaSuUnaRiga(dimensione: DynamicTypeSize) throws {
        // iPhone con un titolo corto, iPad con il nome lungo
        for (nome, larghezza) in [(Self.titoloCorto, Self.larghezzaIPhone), (Self.nomeLungo, Self.larghezzaIPad)] {
            let riga = try Self.disegna(Text(nome).font(.headline), larghezza: nil, min(dimensione, .xxxLarge))
            try #require(CGFloat(riga.width) < larghezza, "«\(nome)» deve starci in \(larghezza) punti")

            let titolo = try Self.disegna(TitoloInBarra(titolo: nome, soloSeCiSta: true), larghezza: larghezza, dimensione)
            #expect(Self.pixelVisibili(titolo) > 0, "«\(nome)» ci sta: si vede")
            #expect(abs(CGFloat(titolo.height) - CGFloat(riga.height)) <= 1,
                    "«\(nome)»: titolo alto \(titolo.height), una riga del titolo di sistema \(riga.height)")
        }
    }

    /// iPhone in orizzontale: la barra piccola è alta ~32 punti. Con il testo grande `TitoloInBarra` non guarda
    /// l'orientamento: il tetto basta perché una riga ci stia anche lì.
    @MainActor
    @Test("iPhone in orizzontale con il testo massimo: una riga che sta nella barra bassa, o niente se il nome non ci sta")
    func orizzontale() throws {
        let corto = try Self.disegna(TitoloInBarra(titolo: Self.titoloCorto, soloSeCiSta: true),
                                     larghezza: Self.larghezzaOrizzontale, .accessibility5)
        #expect(Self.pixelVisibili(corto) > 0)
        #expect(CGFloat(corto.height) <= Self.altezzaBarraOrizzontale + 0.5, "una riga dentro la barra bassa: alta \(corto.height)")

        let intero = try Self.disegna(Text(Self.nome50).font(.headline), larghezza: nil, .xxxLarge)
        try #require(CGFloat(intero.width) > Self.larghezzaOrizzontale, "il nome della prova deve essere più largo della barra")
        let lungo = Self.disegnaSeCe(TitoloInBarra(titolo: Self.nome50, soloSeCiSta: true), larghezza: Self.larghezzaOrizzontale, .accessibility5)
        #expect((lungo?.height ?? 0) == 0, "nella barra resta un riquadro alto \(lungo?.height ?? 0)")
        #expect((lungo.map(Self.pixelVisibili) ?? 0) == 0, "un nome che non ci sta non si mostra tagliato con «…»")
    }

    // MARK: disegno e misure

    /// La vista disegnata (in punti), larga `larghezza` (nil = quanto le serve): deve esserci qualcosa da disegnare.
    @MainActor
    private static func disegna(_ vista: some View, larghezza: CGFloat?, _ dimensione: DynamicTypeSize) throws -> CGImage {
        try #require(disegnaSeCe(vista, larghezza: larghezza, dimensione), "niente da disegnare")
    }

    /// Come `disegna`, ma una vista alta zero non si disegna: nil.
    @MainActor
    private static func disegnaSeCe(_ vista: some View, larghezza: CGFloat?, _ dimensione: DynamicTypeSize) -> CGImage? {
        let disegno = ImageRenderer(content: vista.frame(width: larghezza).dynamicTypeSize(dimensione))
        disegno.scale = 1
        return disegno.cgImage
    }

    /// Quanti punti dell'immagine non sono trasparenti (il fondo di `ImageRenderer` è trasparente). -1 se non si legge.
    private static func pixelVisibili(_ immagine: CGImage) -> Int {
        let larghezza = immagine.width
        let altezza = immagine.height
        var byte = [UInt8](repeating: 0, count: larghezza * altezza * 4)
        let letta = byte.withUnsafeMutableBytes { memoria -> Bool in
            guard let contesto = CGContext(data: memoria.baseAddress, width: larghezza, height: altezza, bitsPerComponent: 8,
                                           bytesPerRow: larghezza * 4, space: CGColorSpaceCreateDeviceRGB(),
                                           bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else { return false }
            contesto.draw(immagine, in: CGRect(x: 0, y: 0, width: larghezza, height: altezza))
            return true
        }
        guard letta else { return -1 }
        return stride(from: 3, to: byte.count, by: 4).reduce(0) { $0 + (byte[$1] > 0 ? 1 : 0) }
    }
}
