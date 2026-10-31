import WidgetKit
import SwiftUI

/// I widget di SchieraXI. Questo file e' escluso dall'app di anteprima (la galleria per gli screenshot), che ha il suo `@main`.
@main
struct PacchettoWidget: WidgetBundle {
    var body: some Widget {
        // Tre widget per chi usa l'app (Prossima giornata, Formazione, Da controllare). Gli altri restano nel codice ma fuori dal pacchetto:
        // il widget non può leggere le funzioni accese (nessun dato condiviso con l'app, il suo token vale solo per Oggi e per il riassunto),
        // quindi non può nascondere da solo quelli di una funzione spenta (Cruscotto, Partite live, Chi gioca, Giocatore osservato,
        // Punti attesi e fatti, Miglior scambio, Crediti, Stato dei dati).
        WidgetOggi()
        WidgetFormazione()
        WidgetDubbi()
    }
}
