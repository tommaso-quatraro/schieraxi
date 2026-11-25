import SwiftUI

/// Il chiaro o lo scuro dell'app (#845). Lo applica una volta sola la radice (`PortaDiAccesso`), così la scelta di Impostazioni ›
/// Aspetto vale su ogni schermata: anche su accesso, primo avvio e codice di recupero, che stanno fuori dalle schede (prima
/// seguivano solo il dispositivo).
enum TemaScelto {
    /// `tema`: la scelta salvata (`auto`, `chiaro`, `scuro`); `foto`: l'aspetto del giro delle foto del simulatore (`scuro`,
    /// `chiaro`), che vince. nil = come il dispositivo.
    static func schema(tema: String, foto: String?) -> ColorScheme? {
        switch foto ?? "" {
        case "scuro": return .dark
        case "chiaro": return .light
        default: break
        }
        switch tema {
        case "chiaro": return .light
        case "scuro": return .dark
        default: return nil
        }
    }

    /// Solo per le foto (`-DEMO_ASPETTO scuro|chiaro` di `scripts/screenshot.sh`, con `-DEMO`): l'aspetto del giro, che vale anche
    /// dove il tema resta «Automatico» (la foto `impostazioni-aspetto`). Al primo giro dopo l'accensione il simulatore poteva essere
    /// ancora chiaro, anche se `simctl ui appearance` rileggeva «dark»: le foto «scuro» di accesso e Aspetto uscivano chiare.
    static func foto(argomenti: [String]) -> String? {
        guard argomenti.contains("-DEMO") else { return nil }
        return Demo.argomento("DEMO_ASPETTO", in: argomenti)
    }

    /// `foto(argomenti:)` con gli argomenti di lancio dell'app.
    static let fotoDaLancio: String? = foto(argomenti: ProcessInfo.processInfo.arguments)
}
