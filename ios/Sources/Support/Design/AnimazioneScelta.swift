import SwiftUI

/// `.animation(_:value:)` che rispetta «Animazioni ridotte» dell'app e «Riduci movimento» di iOS (`Movimento`): l'animazione
/// scritta, la dissolvenza breve o nessuna. Legge i due interruttori nella vista stessa, così vale anche nei fogli.
struct AnimazioneScelta<Valore: Equatable>: ViewModifier {
    let normale: Animation
    let valore: Valore
    @Environment(\.accessibilityReduceMotion) private var riduciMovimento
    @AppStorage(Movimento.chiave) private var animazioniRidotte = false

    func body(content: Content) -> some View {
        content.animation(Movimento.scegli(riduciMovimento: riduciMovimento, animazioniRidotte: animazioniRidotte).animazione(normale),
                          value: valore)
    }
}

extension View {
    /// Anima i cambi di `value` con `normale`, se gli interruttori dell'accessibilità lo lasciano fare (`AnimazioneScelta`).
    func animazione<Valore: Equatable>(_ normale: Animation, value: Valore) -> some View {
        modifier(AnimazioneScelta(normale: normale, valore: value))
    }
}
