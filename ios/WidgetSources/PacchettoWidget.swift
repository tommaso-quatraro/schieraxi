import WidgetKit
import SwiftUI

/// I widget di SchieraXI. Questo file e' escluso dall'app di anteprima (la galleria per gli screenshot), che ha il suo `@main`.
@main
struct PacchettoWidget: WidgetBundle {
    var body: some Widget {
        // I tre widget di SchieraXI: Prossima giornata, Formazione, Da controllare. Gli altri otto, già fuori dal pacchetto, sono
        // stati tolti il 12/11/2026 (#634).
        WidgetOggi()
        WidgetFormazione()
        WidgetDubbi()
    }
}
