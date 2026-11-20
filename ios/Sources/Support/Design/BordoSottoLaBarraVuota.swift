import SwiftUI

/// Il bordo sotto la barra in alto per le pagine in cima a una scheda (per ora Impostazioni) con il testo grande (#848).
///
/// Da `TitoloPagina.soglia` in su la barra di queste pagine è vuota: il titolo sta nella pagina (`TitoloPagina.barraSenzaTitolo`,
/// #419) e in cima a una scheda non c'è «indietro». Su iOS 26 la barra non ha uno sfondo suo e sfuma i contenuti che le passano
/// sotto solo dietro a quello che contiene: con il testo normale dietro al titolo piccolo che compare scorrendo, con la barra
/// vuota mai. Scorrendo, le righe passavano nitide sotto l'ora (foto `impostazioni-aspetto` con il testo grande). Qui la pagina
/// copre la fascia della barra con il suo stesso sfondo, pieno sotto l'ora e trasparente sul fondo della barra: ferma non si
/// vede (lo sfondo sopra lo stesso sfondo), scorrendo i contenuti spariscono sotto l'ora come con il testo normale.
/// Su iOS 18 la barra ha ancora il suo sfondo sfocato quando i contenuti le passano sotto: lì non cambia niente.
/// Va solo sulle pagine con `Sfondo()` dietro la lista, e fuori dalla striscia dei dati salvati (`avvisoDatiSalvati`), così la
/// fascia è alta quanto l'ora e la barra, non di più.
private struct BordoSottoLaBarraVuota: ViewModifier {
    @Environment(\.dynamicTypeSize) private var dimensione

    func body(content: Content) -> some View {
        Group {
            if #available(iOS 26.0, *) {
                content.overlay(alignment: .top) {
                    if TitoloPagina.barraSenzaTitolo(dimensione) { FasciaSottoLaBarra() }
                }
            } else {
                content
            }
        }
    }
}

/// La fascia: `Sfondo()` dall'alto dello schermo al fondo della barra (il margine sicuro in alto: ora e barra), mascherato da
/// pieno a trasparente. Non riceve tocchi e VoiceOver non la vede.
private struct FasciaSottoLaBarra: View {
    var body: some View {
        GeometryReader { spazio in
            Sfondo()
                .mask(alignment: .top) {
                    LinearGradient(stops: [.init(color: .black, location: 0), .init(color: .black, location: 0.55),
                                           .init(color: .clear, location: 1)],
                                   startPoint: .top, endPoint: .bottom)
                        .frame(height: spazio.safeAreaInsets.top)
                }
        }
        .ignoresSafeArea()
        .allowsHitTesting(false)
        .accessibilityHidden(true)
    }
}

extension View {
    /// Con il testo grande, su iOS 26, i contenuti che scorrono sotto la barra vuota sfumano nello sfondo invece di passare
    /// nitidi sotto l'ora (#848). Per le pagine in cima a una scheda con `Sfondo()` dietro; vedi `BordoSottoLaBarraVuota`.
    func bordoSottoLaBarraVuota() -> some View {
        modifier(BordoSottoLaBarraVuota())
    }
}
