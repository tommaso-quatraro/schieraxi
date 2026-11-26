import SwiftUI

/// Le pagine a elenco sull'iPad (#896), come la web larga: una colonna di al massimo 720 punti (`.imp-colonna`) e selettori a
/// segmenti di al massimo 520 (`#aspetto .segmenti`). Così interruttori e valori restano vicini al loro nome invece di finire a
/// 1200-1600 punti di distanza. Solo sull'iPad largo e alto (`SpazioIPad`, #919): sugli iPhone, anche in orizzontale e più larghi
/// di 720 punti, non cambia niente.
enum LarghezzaPagina {
    /// La colonna delle pagine a elenco.
    static let colonna: CGFloat = 720
    /// I selettori a segmenti.
    static let segmenti: CGFloat = 520
    /// La riga di stemma e maglia nella rosa di una squadra: a tutta larghezza erano a 370 punti l'uno dall'altra.
    static let immaginiRosa: CGFloat = 400

    /// Il margine da aggiungere a ogni lato perché il contenuto non superi `massima`: 0 se lo spazio è già più stretto (o se la
    /// misura non c'è ancora).
    static func margine(larghezza: CGFloat, massima: CGFloat = colonna) -> CGFloat {
        guard larghezza.isFinite, larghezza > massima else { return 0 }
        return ((larghezza - massima) / 2).rounded(.down)
    }

    /// Il margine per lato della colonna di una pagina con `larghezza` punti liberi: solo sull'iPad largo e alto, 0 altrove.
    static func margineColonna(larghezza: CGFloat, orizzontale: UserInterfaceSizeClass?,
                               verticale: UserInterfaceSizeClass?) -> CGFloat {
        SpazioIPad.largoEAlto(orizzontale: orizzontale, verticale: verticale) ? margine(larghezza: larghezza) : 0
    }

    /// La larghezza libera di una vista larga `larghezza`: quella dentro i suoi margini sicuri ai lati. Una pagina dentro una
    /// `NavigationStack` già stretta alla colonna (Impostazioni, Cerca) ha 720 punti liberi e non aggiunge altro.
    static func libera(larghezza: CGFloat, margini: EdgeInsets) -> CGFloat {
        max(0, larghezza - margini.leading - margini.trailing)
    }

    /// `massima` sull'iPad largo e alto; `nil` (nessun limite) sugli iPhone e sull'iPad stretto.
    static func massimaSuIPad(_ massima: CGFloat, orizzontale: UserInterfaceSizeClass?,
                              verticale: UserInterfaceSizeClass?) -> CGFloat? {
        SpazioIPad.largoEAlto(orizzontale: orizzontale, verticale: verticale) ? massima : nil
    }
}

/// Lo spazio che avanza oltre la colonna va ai due lati come margine sicuro (`safeAreaPadding`): lo sfondo resta pieno, ma righe e
/// schede stanno nella colonna al centro. Su una `NavigationStack` il margine vale anche per la barra (titolo grande, campo di
/// ricerca, pulsanti), se iOS lo passa alla barra: va guardato nelle foto dell'iPad. Con margine 0 (iPhone) è come senza.
private struct ColonnaPagina: ViewModifier {
    @Environment(\.horizontalSizeClass) private var orizzontale
    @Environment(\.verticalSizeClass) private var verticale
    /// I punti liberi che la pagina riceve da fuori, dentro i margini sicuri. 0 finché non sono misurati.
    @State private var libera: CGFloat = 0

    func body(content: Content) -> some View {
        content
            .safeAreaPadding(.horizontal, LarghezzaPagina.margineColonna(larghezza: libera, orizzontale: orizzontale,
                                                                         verticale: verticale))
            // La misura sta fuori dal margine aggiunto qui sopra, che vale solo per la pagina: non lo conta. Se un contenitore
            // sopra ha già stretto la colonna (la `NavigationStack` di Impostazioni e di Cerca) i punti liberi sono già 720 e qui
            // non si aggiunge niente; se il suo margine non arriva fin qui, la colonna la fa questa pagina.
            .background {
                Color.clear
                    .onGeometryChange(for: CGFloat.self) {
                        LarghezzaPagina.libera(larghezza: $0.size.width, margini: $0.safeAreaInsets)
                    } action: { libera = $0 }
                    .accessibilityHidden(true)
            }
    }
}

/// Un elemento largo al massimo `massima` sull'iPad largo e alto; sugli iPhone resta com'è, senza cornici in più.
private struct LarghezzaSuIPad: ViewModifier {
    let massima: CGFloat
    let allineamento: Alignment
    let lineaDalBordo: Bool
    @Environment(\.horizontalSizeClass) private var orizzontale
    @Environment(\.verticalSizeClass) private var verticale

    @ViewBuilder
    func body(content: Content) -> some View {
        if let m = LarghezzaPagina.massimaSuIPad(massima, orizzontale: orizzontale, verticale: verticale) {
            let stretto = content
                .frame(maxWidth: m, alignment: allineamento)
                .frame(maxWidth: .infinity, alignment: allineamento)
            if lineaDalBordo {
                // la linea sotto la riga parte dal bordo, come quella delle altre righe: se no iOS la fa partire dal primo testo,
                // che con l'elemento al centro sta a metà riga
                stretto.alignmentGuide(.listRowSeparatorLeading) { _ in 0 }
            } else {
                stretto
            }
        } else {
            content
        }
    }
}

extension View {
    /// Una pagina a elenco (o la `NavigationStack` che la contiene): sull'iPad largo e alto in una colonna larga al massimo come
    /// quella della web (`LarghezzaPagina.colonna`).
    func colonnaPagina() -> some View {
        modifier(ColonnaPagina())
    }

    /// Un selettore a segmenti largo al massimo come quelli della web (`LarghezzaPagina.segmenti`), allineato a sinistra. Solo
    /// sull'iPad largo e alto.
    func segmentiDellaPagina() -> some View {
        modifier(LarghezzaSuIPad(massima: LarghezzaPagina.segmenti, allineamento: .leading, lineaDalBordo: false))
    }

    /// Un elemento di una riga largo al massimo `massima` sull'iPad largo e alto. Con `lineaDalBordo` la linea sotto la riga parte
    /// dal bordo invece che dal primo testo.
    func larghezzaSuIPad(_ massima: CGFloat, allineamento: Alignment = .leading, lineaDalBordo: Bool = false) -> some View {
        modifier(LarghezzaSuIPad(massima: massima, allineamento: allineamento, lineaDalBordo: lineaDalBordo))
    }
}
