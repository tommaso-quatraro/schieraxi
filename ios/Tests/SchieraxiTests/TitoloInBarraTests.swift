import SwiftUI
import Testing
import UIKit
@testable import Schieraxi

/// Issue #293 (storia: #211, #276). La pagina di una squadra ha il titolo piccolo della barra (`piccoloInBarra`), che iOS
/// tiene su una riga sola: con il testo normale un nome oltre ~22 lettere si tagliava («Gli Amici del Bar Spo…»).
/// Sotto `TitoloPagina.soglia` la barra di queste pagine mostra `TitoloInBarra`: una riga come il titolo di sistema se il
/// nome ci sta, se no due righe. Da XXL in su resta quello di #276 (nome intero a capo nella pagina).
@Suite("Nome lungo della squadra intero nella barra piccola")
struct TitoloInBarraTests {

    /// Il nome della squadra della demo nella foto «lega-rosa»: 32 lettere, inventato.
    private static let nomeLungo = "Gli Amici del Bar Sport Centrale"
    /// Lo spazio del titolo nella barra di un iPhone stretto, tra la freccia «indietro» e lente e ingranaggio.
    private static let larghezzaBarra: CGFloat = 200
    /// L'altezza della barra piccola di iOS: il titolo deve starci dentro.
    private static let altezzaBarra: CGFloat = 44

    @Test("Titolo intero nella barra solo per le pagine con la barra piccola e sotto XXL; da XXL in su resta nella pagina")
    func quandoNellaBarra() {
        let nellaBarra = DynamicTypeSize.allCases.filter { TitoloPagina.interoInBarra($0, piccoloInBarra: true) }
        #expect(nellaBarra == [.xSmall, .small, .medium, .large, .xLarge])
        for dimensione in DynamicTypeSize.allCases {
            // le pagine con il titolo grande della barra non cambiano
            #expect(!TitoloPagina.interoInBarra(dimensione, piccoloInBarra: false), "\(dimensione)")
            // il nome intero sta in un posto solo: nella barra o nella pagina, mai in tutti e due
            let inTuttiEDue = TitoloPagina.interoInBarra(dimensione, piccoloInBarra: true) && TitoloPagina.nellaPagina(dimensione)
            #expect(!inTuttiEDue, "\(dimensione)")
        }
    }

    /// Comportamento vero del disegno: `ImageRenderer` dentro una colonna larga quanto il posto del titolo nella barra.
    /// (La barra stessa `ImageRenderer` non la disegna: lì il controllo sono le foto.)
    @MainActor
    @Test("Nome lungo con il testo normale: va a capo su due righe e sta nella barra, non una riga tagliata",
          arguments: [DynamicTypeSize.small, .large, .xLarge])
    func nomeLungoSuDueRighe(dimensione: DynamicTypeSize) {
        // senza TitoloInBarra il titolo di sistema (una riga) non ci starebbe: si taglierebbe
        let unaRiga = Self.misura(Text(Self.nomeLungo).font(.headline).lineLimit(1), larghezza: nil, dimensione)
        #expect(unaRiga.width > Self.larghezzaBarra, "il nome della prova deve essere più largo della barra")

        let rigaDelTitolo = Self.misura(Text("Amici").font(.subheadline.weight(.semibold)), larghezza: nil, dimensione).height
        let titolo = Self.misura(TitoloInBarra(titolo: Self.nomeLungo), larghezza: Self.larghezzaBarra, dimensione).height
        #expect(rigaDelTitolo > 0)
        #expect(titolo > rigaDelTitolo * 1.5, "due righe: il nome intero, non «Gli Amici del Bar…»")
        #expect(titolo <= Self.altezzaBarra + 0.5, "le due righe stanno nella barra piccola")
    }

    @MainActor
    @Test("Nome che ci sta: una riga sola, alta come il titolo di sistema della barra")
    func nomeCortoSuUnaRiga() {
        let titolo = Self.misura(TitoloInBarra(titolo: "Real Madrink"), larghezza: Self.larghezzaBarra, .large).height
        let sistema = Self.misura(Text("Real Madrink").font(.headline), larghezza: nil, .large).height
        #expect(sistema > 0)
        #expect(abs(titolo - sistema) <= 1, "titolo \(titolo), titolo di sistema \(sistema)")
    }

    // MARK: misure

    /// La misura di una vista disegnata (in punti), larga `larghezza` (nil = quanto le serve).
    @MainActor
    private static func misura(_ vista: some View, larghezza: CGFloat?, _ dimensione: DynamicTypeSize) -> CGSize {
        let disegno = ImageRenderer(content: vista.frame(width: larghezza).dynamicTypeSize(dimensione))
        disegno.scale = 1
        return disegno.uiImage?.size ?? .zero
    }
}
