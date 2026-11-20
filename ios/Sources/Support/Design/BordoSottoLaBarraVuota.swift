import SwiftUI

/// Il bordo sotto la barra in alto per le pagine in cima a una scheda (per ora Impostazioni) con il testo grande (#848, #857).
///
/// Da `TitoloPagina.soglia` in su la barra di queste pagine è vuota: il titolo sta nella pagina (`TitoloPagina.barraSenzaTitolo`,
/// #419) e in cima a una scheda non c'è «indietro». Su iOS 26 la barra non ha uno sfondo suo e sfuma i contenuti che le passano
/// sotto solo dietro a quello che contiene: con il testo normale dietro al titolo piccolo che compare scorrendo, con la barra
/// vuota mai. Scorrendo, righe e titoli passavano nitidi sotto l'ora (foto `impostazioni-aspetto` e `impostazioni-fondo` con il
/// testo grande; con il testo massimo il titolo «Aspetto»). Qui la pagina copre la fascia dell'ora e della barra con il suo
/// stesso sfondo, pieno sotto l'ora e trasparente sul fondo della barra: ferma non si vede (lo sfondo sopra lo stesso sfondo),
/// scorrendo i contenuti spariscono sotto l'ora come con il testo normale.
/// Su iOS 18 la barra ha ancora il suo sfondo sfocato quando i contenuti le passano sotto: lì non cambia niente.
/// Va solo sulle pagine con `Sfondo()` dietro la lista, e fuori dalla striscia dei dati salvati (`avvisoDatiSalvati`), così la
/// fascia è alta quanto l'ora e la barra, non di più.
private struct BordoSottoLaBarraVuota: ViewModifier {
    var misurata: ((CGFloat) -> Void)?
    @Environment(\.dynamicTypeSize) private var dimensione
    /// Il fondo della barra contato dall'alto della finestra: l'ora più la barra. 0 finché non è misurato.
    @State private var fondoBarra: CGFloat = 0

    func body(content: Content) -> some View {
        Group {
            if #available(iOS 26.0, *) {
                content
                    .overlay(alignment: .top) {
                        // La misura: una vista vuota che rispetta il margine sicuro. La sua cima, contata dall'alto della finestra,
                        // più il margine che le resta in alto (se arriva sotto la barra) è il fondo della barra. Mai dentro una
                        // vista che ignora il margine sicuro: lì il margine vale 0 e la fascia era alta 0 (corsa 44819951481).
                        Color.clear
                            .onGeometryChange(for: CGFloat.self) { spazio in
                                spazio.frame(in: .global).minY + spazio.safeAreaInsets.top
                            } action: { fondo in
                                fondoBarra = fondo
                            }
                            .allowsHitTesting(false)
                            .accessibilityHidden(true)
                    }
                    .overlay(alignment: .top) {
                        if TitoloPagina.barraSenzaTitolo(dimensione), fondoBarra > 0 {
                            FasciaSottoLaBarra(altezza: fondoBarra, misurata: misurata)
                        }
                    }
            } else {
                content
            }
        }
    }
}

/// La fascia: la cima di `Sfondo()`, dall'alto della finestra e alta `altezza` (ora e barra), mascherata da piena a
/// trasparente. Sta in un contenitore che ignora il margine sicuro, così parte dall'alto della finestra come lo `Sfondo()` della
/// pagina e i due disegni coincidono. Non riceve tocchi e VoiceOver non la vede.
private struct FasciaSottoLaBarra: View {
    let altezza: CGFloat
    var misurata: ((CGFloat) -> Void)?

    var body: some View {
        Sfondo()
            .frame(height: altezza, alignment: .top)
            .clipped()
            .mask {
                LinearGradient(stops: [.init(color: .black, location: 0), .init(color: .black, location: 0.55),
                                       .init(color: .clear, location: 1)],
                               startPoint: .top, endPoint: .bottom)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
            .ignoresSafeArea()
            .allowsHitTesting(false)
            .accessibilityHidden(true)
            .onChange(of: altezza, initial: true) { _, nuova in misurata?(nuova) }
    }
}

extension View {
    /// Con il testo grande, su iOS 26, i contenuti che scorrono sotto la barra vuota sfumano nello sfondo invece di passare
    /// nitidi sotto l'ora (#848). Per le pagine in cima a una scheda con `Sfondo()` dietro; vedi `BordoSottoLaBarraVuota`.
    /// `misurata`: per i test, riceve l'altezza della fascia quando la fascia c'è.
    func bordoSottoLaBarraVuota(misurata: ((CGFloat) -> Void)? = nil) -> some View {
        modifier(BordoSottoLaBarraVuota(misurata: misurata))
    }
}
