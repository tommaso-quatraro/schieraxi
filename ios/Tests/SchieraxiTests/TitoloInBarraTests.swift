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
    static let nomeLungo = "Gli Amici del Bar Sport Centrale"
    /// Lo spazio del titolo nella barra di un iPhone stretto (375 punti), tra la freccia «indietro» e lente e ingranaggio:
    /// il titolo centrato ne ha circa 160. Con 200 il nome della prova, a «Piccolo», poteva stare su una riga sola del
    /// secondo carattere (più piccolo) e la prova delle due righe sarebbe fallita senza un difetto.
    private static let larghezzaBarra: CGFloat = 160
    /// L'altezza della barra piccola di iOS: il titolo deve starci dentro.
    private static let altezzaBarra: CGFloat = 44
    /// Un nome di 50 lettere, spazi compresi, inventato.
    static let nome50 = "Associazione Sportiva Amici del Bar Sport Centrale"
    /// Lo spazio del titolo nella barra di un iPhone stretto in orizzontale (667 punti): circa 400.
    private static let larghezzaOrizzontale: CGFloat = 400

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
        let titolo = Self.misura(Self.verticale(TitoloInBarra(titolo: Self.nomeLungo)), larghezza: Self.larghezzaBarra, dimensione).height
        #expect(rigaDelTitolo > 0)
        #expect(titolo > rigaDelTitolo * 1.5, "due righe, non una")
        // due righe che finiscono con «…» passerebbero il controllo di sopra: lo stesso testo senza limite di righe, alla stessa
        // larghezza, deve essere alto uguale (nessuna riga tolta, nessun «Gli Amici del Bar Sport…»)
        let intero = Self.misura(Self.senzaLimite(Self.nomeLungo), larghezza: Self.larghezzaBarra, dimensione).height
        #expect(abs(titolo - intero) <= 1, "titolo \(titolo), testo intero \(intero): il nome è stato accorciato")
        #expect(titolo <= Self.altezzaBarra + 0.5, "le due righe stanno nella barra piccola")
    }

    /// Un nome di 50 lettere (inventato) può non stare in due righe nemmeno all'80% (stima: oltre ~40-45 lettere): limite dichiarato nella PR
    /// (si accorcia con «…»). Qui si prova che anche allora il titolo resta di due righe dentro la barra, senza uscirne.
    @MainActor
    @Test("Nome di 50 lettere: due righe al massimo, sempre dentro la barra piccola",
          arguments: [DynamicTypeSize.small, .large, .xLarge])
    func nomeDi50Lettere(dimensione: DynamicTypeSize) {
        #expect(Self.nome50.count == 50)
        let rigaDelTitolo = Self.misura(Text("Amici").font(.subheadline.weight(.semibold)), larghezza: nil, dimensione).height
        let titolo = Self.misura(Self.verticale(TitoloInBarra(titolo: Self.nome50)), larghezza: Self.larghezzaBarra, dimensione).height
        // 1,4 e non 1,5: se il nome non ci sta, le due righe sono all'80% del carattere
        #expect(titolo > rigaDelTitolo * 1.4, "due righe")
        #expect(titolo <= Self.altezzaBarra + 0.5, "dentro la barra piccola: titolo \(titolo)")
    }

    /// iPhone in orizzontale (`verticalSizeClass` compatta): la barra piccola è alta ~32 punti, due righe non ci stanno.
    /// Una riga sola, alta come il titolo di sistema, anche con il nome di 50 lettere (si stringe fino all'80%).
    @MainActor
    @Test("iPhone in orizzontale: una riga sola, anche con un nome lungo", arguments: [TitoloInBarraTests.nomeLungo, TitoloInBarraTests.nome50])
    func orizzontaleUnaRiga(nome: String) {
        let sistema = Self.misura(Text("Real Madrink").font(.headline), larghezza: nil, .large).height
        let titolo = Self.misura(TitoloInBarra(titolo: nome).environment(\.verticalSizeClass, .compact),
                                 larghezza: Self.larghezzaOrizzontale, .large).height
        #expect(sistema > 0)
        // una riga: non più alta di quella di sistema; un po' più bassa se il nome si è stretto (fino all'80%)
        #expect(titolo <= sistema + 1 && titolo >= sistema * 0.75, "titolo \(titolo), una riga di sistema \(sistema)")
    }

    @MainActor
    @Test("Nome che ci sta: una riga sola, alta come il titolo di sistema della barra")
    func nomeCortoSuUnaRiga() {
        let titolo = Self.misura(Self.verticale(TitoloInBarra(titolo: "Real Madrink")), larghezza: Self.larghezzaBarra, .large).height
        let sistema = Self.misura(Text("Real Madrink").font(.headline), larghezza: nil, .large).height
        #expect(sistema > 0)
        #expect(abs(titolo - sistema) <= 1, "titolo \(titolo), titolo di sistema \(sistema)")
    }

    // MARK: misure

    /// iPhone in verticale: la barra piccola alta 44 punti, dove il titolo può andare su due righe.
    @MainActor
    private static func verticale(_ vista: some View) -> some View {
        vista.environment(\.verticalSizeClass, .regular)
    }

    /// Il secondo carattere di `TitoloInBarra` senza limite di righe né riduzione: il nome intero, quanto è alto.
    @MainActor
    private static func senzaLimite(_ nome: String) -> some View {
        Text(nome)
            .font(.subheadline.weight(.semibold))
            .lineLimit(nil)
            .multilineTextAlignment(.center)
            .fixedSize(horizontal: false, vertical: true)
    }

    /// La misura di una vista disegnata (in punti), larga `larghezza` (nil = quanto le serve).
    @MainActor
    private static func misura(_ vista: some View, larghezza: CGFloat?, _ dimensione: DynamicTypeSize) -> CGSize {
        let disegno = ImageRenderer(content: vista.frame(width: larghezza).dynamicTypeSize(dimensione))
        disegno.scale = 1
        return disegno.uiImage?.size ?? .zero
    }
}
