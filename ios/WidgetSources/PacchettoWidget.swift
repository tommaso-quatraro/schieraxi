import WidgetKit
import SwiftUI

/// I widget di SchieraXI. Questo file e' escluso dall'app di anteprima (la galleria per gli screenshot), che ha il suo `@main`.
@main
struct PacchettoWidget: WidgetBundle {
    var body: some Widget {
        WidgetOggi()
        WidgetFormazione()
        WidgetCruscotto()
        WidgetLive()
        WidgetDubbi()
        WidgetRosa()
        WidgetPunti()
        WidgetScambio()
        WidgetCrediti()
        WidgetStato()
    }
}
