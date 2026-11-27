import SwiftUI

/// Quanto si muove l'app: tutto, solo dissolvenze brevi («Riduci movimento» di iOS) o niente («Animazioni ridotte» di Impostazioni
/// › Aspetto). Lo leggono le viste che scrivono un'animazione loro (le pedine del campo, i numeri che scorrono, il grafico dei voti):
/// l'interruttore sulla radice dell'app (`RadiceView`) non arriva sempre fin lì, per esempio nei fogli.
enum Movimento: Equatable {
    case pieno
    /// «Riduci movimento» di iOS: niente spostamenti né rimbalzi, solo la dissolvenza breve (`Tema.quieta`).
    case quieto
    /// «Animazioni ridotte» dell'app: nessuna animazione, nemmeno la dissolvenza.
    case fermo

    /// La chiave dell'interruttore «Animazioni ridotte» (`@AppStorage`).
    static let chiave = "animazioniRidotte"

    /// «Animazioni ridotte» vince su tutto; altrimenti «Riduci movimento» cambia il movimento in dissolvenza.
    static func scegli(riduciMovimento: Bool, animazioniRidotte: Bool) -> Movimento {
        if animazioniRidotte { return .fermo }
        return riduciMovimento ? .quieto : .pieno
    }

    /// L'animazione da usare al posto di `normale`: la stessa, la dissolvenza breve o nessuna.
    func animazione(_ normale: Animation) -> Animation? {
        switch self {
        case .pieno: return normale
        case .quieto: return Tema.quieta
        case .fermo: return nil
        }
    }

    /// Le cifre di un numero che cambia scorrono solo con il movimento pieno; altrimenti il numero cambia e basta.
    var cifreCheScorrono: Bool { self == .pieno }
}
