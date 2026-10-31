import SwiftUI

/// I colori principali tra cui scegliere in Lega > Aspetto (la scelta è in `@AppStorage("accento")`).
enum Accento: String, CaseIterable, Identifiable {
    case verde, blu, viola, arancio, rosso, argento

    var id: String { rawValue }

    var nome: String { rawValue.primaMaiuscola }

    /// Sul fondo scuro: più chiaro.
    var scuro: UIColor {
        switch self {
        case .verde: return Self.da(0x3ddc97)   // verde acceso di SchieraXI (tema scuro, invariato)
        case .blu: return Self.da(0x5aa9ff)
        case .viola: return Self.da(0xb78bff)
        case .arancio: return Self.da(0xffab52)
        case .rosso: return Self.da(0xff7a85)
        case .argento: return Self.da(0xc9d3de)
        }
    }

    /// Sul fondo chiaro: più scuro, per restare leggibile.
    var chiaro: UIColor {
        switch self {
        case .verde: return Self.da(0x526600)   // oliva scuro di SchieraXI (azioni nel tema chiaro, 6,4:1 sul bianco, 5,7:1 sul grigio dei fondi)
        case .blu: return Self.da(0x1a63c0)     // contrasto 5,2:1 sul grigio dei fondi raggruppati
        case .viola: return Self.da(0x7a45d6)
        case .arancio: return Self.da(0xa25503) // contrasto 4,9:1 sul grigio dei fondi raggruppati
        case .rosso: return Self.da(0xc03442)    // contrasto 4,9:1 sul grigio dei fondi raggruppati
        case .argento: return Self.da(0x4a5a6a)
        }
    }

    private static func da(_ esadecimale: UInt32) -> UIColor {
        UIColor(red: CGFloat((esadecimale >> 16) & 0xff) / 255, green: CGFloat((esadecimale >> 8) & 0xff) / 255,
                blue: CGFloat(esadecimale & 0xff) / 255, alpha: 1)
    }

    /// L'accento scelto (il verde se non si è scelto niente o la scelta non si conosce).
    static var corrente: Accento {
        Accento(rawValue: UserDefaults.standard.string(forKey: "accento") ?? "") ?? .verde
    }
}
