import SwiftUI

/// Il bordo sotto la barra in alto per le pagine in cima a una scheda (per ora Impostazioni) con il testo grande (#848).
///
/// Da `TitoloPagina.soglia` in su la barra di queste pagine è vuota: il titolo sta nella pagina (`TitoloPagina.barraSenzaTitolo`,
/// #419) e in cima a una scheda non c'è «indietro». Su iOS 26 la barra non ha uno sfondo suo e sfuma i contenuti che le passano
/// sotto solo dietro a quello che contiene: con il testo normale dietro al titolo piccolo che compare scorrendo, con la barra
/// vuota mai. Scorrendo, righe e titoli passavano nitidi sotto l'ora (foto `impostazioni-aspetto` e `impostazioni-fondo` con il
/// testo grande). Qui la pagina copre la zona sopra la parte sicura (l'ora, e la barra se ha un'altezza) con il suo stesso
/// sfondo, pieno, e sotto sfuma fino a trasparente prima del titolo: ferma non si vede (lo sfondo sopra lo stesso sfondo) e non
/// tocca il titolo; scorrendo i contenuti spariscono sotto l'ora come con il testo normale.
/// Su iOS 18 la barra ha ancora il suo sfondo sfocato quando i contenuti le passano sotto: lì non cambia niente.
/// Va solo sulle pagine con `Sfondo()` dietro la lista e il titolo nella pagina in cima, e fuori dalla striscia dei dati salvati
/// (`avvisoDatiSalvati`), così la fascia comincia dall'alto della finestra e la parte che sfuma resta sopra il titolo.
private struct BordoSottoLaBarraVuota: ViewModifier {
    var misurata: ((CGRect, CGFloat) -> Void)?
    @Environment(\.dynamicTypeSize) private var dimensione
    /// L'altezza della zona sopra la parte sicura, dall'alto della finestra: l'ora e la barra. 0 finché non è misurata.
    @State private var fondoBarra: CGFloat = 0

    func body(content: Content) -> some View {
        Group {
            if #available(iOS 26.0, *) {
                content
                    .overlay(alignment: .top) {
                        // La misura, senza conti sul margine: una riga alta 0 in cima alla parte sicura e, dietro di lei, una vista
                        // vuota che ignora il margine in alto e quindi sale fino all'alto della finestra. La sua altezza è il
                        // margine. Le misure fatte a mano sbagliavano: dentro una vista che ignora il margine il margine vale 0
                        // (fascia alta 0, corsa 44826690071); la cima della parte sicura più il margine che le restava lo contava
                        // due volte (fascia fino a 124 punti, sopra il titolo, corsa 44838926206).
                        Color.clear
                            .frame(maxWidth: .infinity)
                            .frame(height: 0)
                            .background(alignment: .bottom) {
                                Color.clear
                                    .onGeometryChange(for: CGFloat.self) { $0.size.height } action: { fondoBarra = $0 }
                                    .ignoresSafeArea(edges: .top)
                            }
                            .allowsHitTesting(false)
                            .accessibilityHidden(true)
                    }
                    .overlay(alignment: .top) {
                        if TitoloPagina.barraSenzaTitolo(dimensione), fondoBarra > 0 {
                            FasciaSottoLaBarra(piena: fondoBarra, misurata: misurata)
                        }
                    }
            } else {
                content
            }
        }
    }
}

/// La fascia: la cima di `Sfondo()`, dall'alto della finestra, piena fino a `piena` (il fondo dell'ora e della barra) e poi
/// sfumata per `sfumata` punti fino a trasparente. Sta in un contenitore che ignora il margine sicuro, così parte dall'alto della
/// finestra come lo `Sfondo()` della pagina e i due disegni coincidono; è sopra le righe, che scorrendo le spariscono sotto. Non
/// riceve tocchi e VoiceOver non la vede.
private struct FasciaSottoLaBarra: View {
    /// Fin dove la fascia è piena, dall'alto della finestra: il fondo della zona sopra la parte sicura. Piena solo per una parte
    /// di quella zona, scorrendo le lettere si vedevano dietro l'ora e accanto all'isola (foto della corsa 45493597395).
    let piena: CGFloat
    var misurata: ((CGRect, CGFloat) -> Void)?

    /// Quanti punti sfuma la fascia sotto la parte piena. Il titolo nella pagina comincia 46-48 punti sotto la zona sopra la
    /// parte sicura (foto della corsa 45493597395: a 108-110 punti sull'iPhone, dove la zona finisce a 62; a 132 sull'iPad):
    /// con 36 la fascia finisce una decina di punti prima e da ferma non lo tocca.
    static let sfumata: CGFloat = 36

    var body: some View {
        let altezza = piena + Self.sfumata
        let finePiena = piena / altezza
        Sfondo()
            .frame(height: altezza, alignment: .top)
            .clipped()
            .mask {
                LinearGradient(stops: [.init(color: .black, location: 0), .init(color: .black, location: finePiena),
                                       .init(color: .clear, location: 1)],
                               startPoint: .top, endPoint: .bottom)
            }
            .onGeometryChange(for: CGRect.self) { $0.frame(in: .global) } action: { riquadro in
                misurata?(riquadro, riquadro.minY + riquadro.height * finePiena)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
            .ignoresSafeArea()
            .allowsHitTesting(false)
            .accessibilityHidden(true)
    }
}

extension View {
    /// Con il testo grande, su iOS 26, i contenuti che scorrono sotto la barra vuota sfumano nello sfondo invece di passare
    /// nitidi sotto l'ora (#848). Per le pagine in cima a una scheda con `Sfondo()` dietro; vedi `BordoSottoLaBarraVuota`.
    /// `misurata`: per i test, quando la fascia c'è riceve il suo riquadro e dove finisce la sua parte piena (nello spazio
    /// `.global`).
    func bordoSottoLaBarraVuota(misurata: ((CGRect, CGFloat) -> Void)? = nil) -> some View {
        modifier(BordoSottoLaBarraVuota(misurata: misurata))
    }
}
