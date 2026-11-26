import CoreGraphics
import SwiftUI
import Testing
@testable import Schieraxi

/// Un dispositivo, con le sue classi di dimensione e la larghezza di una pagina, in punti.
struct DispositivoDiProva: Sendable, CustomTestStringConvertible {
    let nome: String
    let orizzontale: UserInterfaceSizeClass?
    let verticale: UserInterfaceSizeClass?
    let larghezza: CGFloat
    /// È l'iPad largo e alto (`SpazioIPad`)?
    let iPad: Bool

    var testDescription: String { nome }

    static let tutti: [DispositivoDiProva] = [
        DispositivoDiProva(nome: "iPhone in verticale", orizzontale: .compact, verticale: .regular, larghezza: 402, iPad: false),
        // più largo della colonna da 720: prima della #919 Impostazioni e Cerca si stringevano di ~15 punti per lato
        DispositivoDiProva(nome: "iPhone 16 Pro in orizzontale", orizzontale: .compact, verticale: .compact, larghezza: 874, iPad: false),
        // larghezza «regular»: prima della #919 Giornate passava all'elenco con il dettaglio
        DispositivoDiProva(nome: "iPhone Pro Max in orizzontale", orizzontale: .regular, verticale: .compact, larghezza: 956, iPad: false),
        DispositivoDiProva(nome: "iPad in Slide Over", orizzontale: .compact, verticale: .regular, larghezza: 375, iPad: false),
        DispositivoDiProva(nome: "misura non ancora nota", orizzontale: nil, verticale: nil, larghezza: 1032, iPad: false),
        DispositivoDiProva(nome: "iPad 11 pollici in verticale", orizzontale: .regular, verticale: .regular, larghezza: 834, iPad: true),
        DispositivoDiProva(nome: "iPad 13 pollici in verticale", orizzontale: .regular, verticale: .regular, larghezza: 1032, iPad: true),
    ]
}

/// L'iPad come la web larga (#896): le pagine a elenco in una colonna di al massimo 720 punti (`.imp-colonna`), Giornate con
/// l'elenco largo al massimo 420 punti e la giornata a destra, con il testo molto grande la barra in basso come sul telefono.
/// Tutto solo sull'iPad largo e alto (#919): un iPhone in orizzontale supera i 720 punti ma resta com'era. Qui i conti; l'aspetto
/// si guarda nelle foto dell'iPad.
@MainActor
@Suite("iPad: colonne larghe come la web, iPhone invariato")
struct IPadLarghezzeTests {

    // MARK: pagine a elenco

    @Test("Fino a 720 punti nessun margine in più", arguments: [CGFloat(320), 390, 440, 719, 720])
    func strettaSenzaMargine(larghezza: CGFloat) {
        #expect(LarghezzaPagina.margine(larghezza: larghezza) == 0)
    }

    @Test("Oltre i 720 punti lo spazio in più va metà per lato: la colonna resta di 720", arguments: [
        (CGFloat(834), CGFloat(57)), (1024, 152), (1376, 328),
    ])
    func largaConMargine(larghezza: CGFloat, margine: CGFloat) {
        let m = LarghezzaPagina.margine(larghezza: larghezza)
        #expect(m == margine)
        #expect(larghezza - 2 * m <= LarghezzaPagina.colonna + 1, "la colonna è larga \(larghezza - 2 * m)")
    }

    @Test("Una misura che non c'è ancora (0) o infinita non dà margini")
    func misureStrane() {
        #expect(LarghezzaPagina.margine(larghezza: 0) == 0)
        #expect(LarghezzaPagina.margine(larghezza: .infinity) == 0)
        #expect(LarghezzaPagina.margine(larghezza: -5) == 0)
    }

    // MARK: solo l'iPad largo e alto (#919)

    @Test("L'iPad largo e alto è solo quello con larghezza e altezza «regular»", arguments: DispositivoDiProva.tutti)
    func ipadLargoEAlto(d: DispositivoDiProva) {
        #expect(SpazioIPad.largoEAlto(orizzontale: d.orizzontale, verticale: d.verticale) == d.iPad)
    }

    @Test("La colonna da 720 punti solo sull'iPad largo e alto, anche se un iPhone in orizzontale è più largo",
          arguments: DispositivoDiProva.tutti)
    func colonnaSoloSullIPad(d: DispositivoDiProva) {
        let m = LarghezzaPagina.margineColonna(larghezza: d.larghezza, orizzontale: d.orizzontale, verticale: d.verticale)
        if d.iPad {
            #expect(m == LarghezzaPagina.margine(larghezza: d.larghezza))
            #expect(m > 0)
        } else {
            #expect(m == 0)
        }
    }

    @Test("Segmenti da 520 punti e riga di stemma e maglia da 400 solo sull'iPad largo e alto", arguments: DispositivoDiProva.tutti)
    func larghezzeMassimeSoloSullIPad(d: DispositivoDiProva) {
        let segmenti = LarghezzaPagina.massimaSuIPad(LarghezzaPagina.segmenti, orizzontale: d.orizzontale, verticale: d.verticale)
        let immagini = LarghezzaPagina.massimaSuIPad(LarghezzaPagina.immaginiRosa, orizzontale: d.orizzontale,
                                                     verticale: d.verticale)
        #expect(segmenti == (d.iPad ? CGFloat(520) : nil))
        #expect(immagini == (d.iPad ? CGFloat(400) : nil))
    }

    @Test("Giornate: elenco e dettaglio affiancati solo sull'iPad largo e alto; sugli iPhone la pagina del telefono",
          arguments: DispositivoDiProva.tutti)
    func giornateSoloSullIPad(d: DispositivoDiProva) {
        #expect(GiornateView.elencoEDettaglio(orizzontale: d.orizzontale, verticale: d.verticale) == d.iPad)
    }

    // MARK: Giornate

    @Test("Giornate: l'elenco prende metà dello spazio, al massimo 420 punti", arguments: [
        (CGFloat(700), CGFloat(350)), (834, 417), (1032, 420), (1376, 420),
    ])
    func elencoGiornate(totale: CGFloat, elenco: CGFloat) {
        #expect(ElencoEDettaglio.larghezzaElenco(totale: totale) == elenco)
    }

    @Test("Giornate: senza misura l'elenco non ha larghezza")
    func elencoSenzaMisura() {
        #expect(ElencoEDettaglio.larghezzaElenco(totale: 0) == 0)
        #expect(ElencoEDettaglio.larghezzaElenco(totale: .infinity) == 0)
    }

    // MARK: barra con il testo molto grande

    @Test("Con il testo molto grande la barra va in basso, come sul telefono, solo sull'iPad largo e alto",
          arguments: DispositivoDiProva.tutti)
    func barraInBassoConTestoMoltoGrande(d: DispositivoDiProva) {
        for testo in [DynamicTypeSize.accessibility1, .accessibility3, .accessibility5] {
            #expect(RadiceView.barraInBasso(orizzontale: d.orizzontale, verticale: d.verticale, testo: testo) == d.iPad)
        }
    }

    @Test("Con il testo normale o grande la barra resta quella di iOS", arguments: DispositivoDiProva.tutti)
    func barraDiSistema(d: DispositivoDiProva) {
        for testo in [DynamicTypeSize.large, .xxxLarge] {
            #expect(!RadiceView.barraInBasso(orizzontale: d.orizzontale, verticale: d.verticale, testo: testo))
            #expect(RadiceView.classeDellaBarra(orizzontale: d.orizzontale, verticale: d.verticale, testo: testo)
                    == d.orizzontale, "la TabView vede la larghezza vera")
        }
    }

    @Test("La barra in basso: la TabView vede la larghezza «compact» solo sull'iPad con il testo molto grande")
    func classeDellaBarra() {
        #expect(RadiceView.classeDellaBarra(orizzontale: .regular, verticale: .regular, testo: .accessibility5) == .compact)
        #expect(RadiceView.classeDellaBarra(orizzontale: .regular, verticale: .regular, testo: .large) == .regular)
        // iPhone Pro Max in orizzontale con il testo molto grande: come prima
        #expect(RadiceView.classeDellaBarra(orizzontale: .regular, verticale: .compact, testo: .accessibility5) == .regular)
        #expect(RadiceView.classeDellaBarra(orizzontale: .compact, verticale: .regular, testo: .accessibility5) == .compact)
        #expect(RadiceView.classeDellaBarra(orizzontale: nil, verticale: nil, testo: .accessibility5) == nil)
    }
}
