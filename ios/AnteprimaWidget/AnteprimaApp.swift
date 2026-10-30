import SwiftUI
import WidgetKit

// L'app di anteprima dei widget: serve SOLO alla CI (screenshot.yml) per fotografare i widget nelle loro misure sul simulatore di iPhone e di
// iPad, perche' dal simulatore a riga di comando non si puo' aggiungere un widget alla Home. Non entra nell'IPA (non e' tra le dipendenze di
// `Schieraxi`). Argomenti di lancio: `-GALLERIA <widget>[-blocco]` (quale widget; `-blocco` = le misure della schermata di blocco),
// `-DATI pieni|parziali|vuoto` (cosa sa il server), `-RENDER accentato|vivido` (tinted di iOS 18).

@main
struct AnteprimaApp: App {
    var body: some Scene {
        WindowGroup { Galleria() }
    }
}
