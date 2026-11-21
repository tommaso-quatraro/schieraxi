import SwiftUI

/// Il bordo sotto la barra in alto per le pagine in cima a una scheda (per ora Impostazioni) con il testo grande (#848, #857).
///
/// Da `TitoloPagina.soglia` in su la barra di queste pagine è vuota: il titolo sta nella pagina (`TitoloPagina.barraSenzaTitolo`,
/// #419) e in cima a una scheda non c'è «indietro». Su iOS 26 la barra non ha uno sfondo suo e sfuma i contenuti che le passano
/// sotto solo dietro a quello che contiene: con il testo normale dietro al titolo piccolo che compare scorrendo, con la barra
/// vuota mai. Scorrendo, righe e titoli passavano nitidi sotto l'ora (foto `impostazioni-aspetto` e `impostazioni-fondo` con il
/// testo grande; con il testo massimo il titolo «Aspetto»). Qui la pagina copre la fascia sopra la parte sicura (l'ora e la
/// barra, se c'è) con il suo stesso sfondo, pieno sotto l'ora e trasparente in fondo: ferma non si vede (lo sfondo sopra lo
/// stesso sfondo) e non tocca il titolo, che comincia sotto; scorrendo i contenuti spariscono sotto l'ora come con il testo
/// normale. Su iOS 18 la barra ha ancora il suo sfondo sfocato quando i contenuti le passano sotto: lì non cambia niente.
///
/// Niente misure: una riga alta 0 in cima alla parte sicura, e dietro di lei la fascia, che ignora il margine sicuro in alto e
/// quindi sale fino all'alto della finestra. È alta esattamente quanto il margine. Le due versioni con le misure sbagliavano:
/// dentro una vista che ignora il margine il margine vale 0 (fascia alta 0, corsa 44819951481), e la cima della parte sicura
/// più il margine rimasto lo contava due volte (fascia fino a 124 punti, sopra il titolo, corsa 44833454399).
/// Va solo sulle pagine con `Sfondo()` dietro la lista, e fuori dalla striscia dei dati salvati (`avvisoDatiSalvati`), così la
/// fascia è alta quanto l'ora e la barra, non di più.
private struct BordoSottoLaBarraVuota: ViewModifier {
    var misurata: ((CGRect) -> Void)?
    @Environment(\.dynamicTypeSize) private var dimensione

    func body(content: Content) -> some View {
        Group {
            if #available(iOS 26.0, *) {
                content.overlay(alignment: .top) {
                    if TitoloPagina.barraSenzaTitolo(dimensione) {
                        Color.clear
                            .frame(maxWidth: .infinity)
                            .frame(height: 0)
                            .background(alignment: .bottom) {
                                FasciaSottoLaBarra(misurata: misurata)
                                    .ignoresSafeArea(edges: .top)
                            }
                            .allowsHitTesting(false)
                            .accessibilityHidden(true)
                    }
                }
            } else {
                content
            }
        }
    }
}

/// La fascia: la cima di `Sfondo()`, alta quanto lo spazio che riceve (dall'alto della finestra alla parte sicura), mascherata
/// da piena a trasparente. Lo `Sfondo()` parte dall'alto come quello della pagina, quindi i due disegni coincidono. Non riceve
/// tocchi e VoiceOver non la vede.
private struct FasciaSottoLaBarra: View {
    var misurata: ((CGRect) -> Void)?

    var body: some View {
        Sfondo()
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
            .clipped()
            .mask {
                // piena fin sotto l'ora anche quando la fascia è solo l'ora (la barra vuota può non avere altezza)
                LinearGradient(stops: [.init(color: .black, location: 0), .init(color: .black, location: 0.7),
                                       .init(color: .clear, location: 1)],
                               startPoint: .top, endPoint: .bottom)
            }
            .onGeometryChange(for: CGRect.self) { $0.frame(in: .global) } action: { misurata?($0) }
            .allowsHitTesting(false)
            .accessibilityHidden(true)
    }
}

extension View {
    /// Con il testo grande, su iOS 26, i contenuti che scorrono sotto la barra vuota sfumano nello sfondo invece di passare
    /// nitidi sotto l'ora (#848). Per le pagine in cima a una scheda con `Sfondo()` dietro; vedi `BordoSottoLaBarraVuota`.
    /// `misurata`: per i test, riceve il riquadro della fascia (nello spazio `.global`) quando la fascia c'è.
    func bordoSottoLaBarraVuota(misurata: ((CGRect) -> Void)? = nil) -> some View {
        modifier(BordoSottoLaBarraVuota(misurata: misurata))
    }
}
