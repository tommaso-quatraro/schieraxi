import SwiftUI
import WidgetKit

// L'app di anteprima dei widget: serve SOLO alla CI (screenshot.yml) per fotografare i widget nelle loro misure sul simulatore di iPhone e di
// iPad, perche' dal simulatore a riga di comando non si puo' aggiungere un widget alla Home. Non entra nell'IPA (non e' tra le dipendenze di
// `Schieraxi`). Argomenti di lancio: `-GALLERIA <widget>[-blocco]` (quale widget; `-blocco` = le misure della schermata di blocco),
// `-DATI pieni|parziali|vuoto` (cosa sa il server), `-RENDER accentato|vivido` (tinted di iOS 18), `-ASPETTO scuro|chiaro` (l'aspetto
// del giro di foto, che vince su quello del simulatore).

@main
struct AnteprimaApp: App {
    var body: some Scene {
        WindowGroup {
            Galleria()
                .preferredColorScheme(Self.aspetto)
        }
    }

    /// `-ASPETTO scuro|chiaro` di `scripts/screenshot_widget.sh`: l'aspetto del giro di foto. Il simulatore cambia aspetto dopo
    /// un po' e le prime foto «scuro» dopo l'accensione dell'iPad uscivano chiare (#890, come le foto dell'app con `-DEMO_ASPETTO`,
    /// #852). Senza l'argomento: come il simulatore.
    private static var aspetto: ColorScheme? {
        switch UserDefaults.standard.string(forKey: "ASPETTO") {
        case "scuro": return .dark
        case "chiaro": return .light
        default: return nil
        }
    }
}
