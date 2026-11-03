import SwiftUI

/// Icona e testo di un pulsante distruttivo dello stesso rosso (`Color.malus`, contrasto 4,5:1 sul chiaro e sullo scuro).
/// In una lista il ruolo `.destructive` colora solo il testo: l'icona restava del colore dell'app, verde accanto a un testo
/// rosso («Archivia e riparti» in Nuova stagione, issue #196).
struct StileDistruttivo: LabelStyle {
    func makeBody(configuration: Configuration) -> some View {
        Label(configuration)
            .foregroundStyle(Color.malus)
    }
}

extension LabelStyle where Self == StileDistruttivo {
    /// Icona e testo nello stesso rosso: per i pulsanti con `role: .destructive` dentro una lista.
    static var distruttiva: StileDistruttivo { StileDistruttivo() }
}
