import SwiftUI

/// I colori principali tra cui scegliere in Lega > Aspetto (la scelta è in `@AppStorage("accento")`).
enum Accento: String, CaseIterable, Identifiable {
    case verde, blu, viola, arancio, rosso, argento

    var id: String { rawValue }

    var nome: String { rawValue.primaMaiuscola }

    /// Sul fondo scuro: più chiaro.
    var scuro: UIColor {
        switch self {
        case .verde: return Self.da(0x3ddc97)   // verde di stato di SchieraXI (scuro)
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
        case .verde: return Self.da(0x0a7d4c)   // verde di stato di SchieraXI (chiaro, contrasto 5:1 sul bianco)
        case .blu: return Self.da(0x1d6fd6)
        case .viola: return Self.da(0x7a45d6)
        case .arancio: return Self.da(0xb45f04)
        case .rosso: return Self.da(0xd63a4a)
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
