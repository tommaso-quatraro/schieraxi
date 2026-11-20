import SwiftUI

/// Il chiaro o lo scuro dell'app (#845). Primo passo: solo la firma, il comportamento arriva con il commit dopo i test.
enum TemaScelto {
    static func schema(tema: String, foto: String?) -> ColorScheme? {
        switch tema {
        case "chiaro": return .light
        case "scuro": return .dark
        default: return nil
        }
    }

    static func foto(argomenti: [String]) -> String? { nil }
}
