import SwiftUI

/// I giocatori da controllare, uno per riga (volto, nome, stato). Se lo stato intero («In dubbio · gioca 70%») non entra in
/// larghezza, prima spariscono i volti, poi restano il cognome e lo stato corto («gioca 70%»): mai una parola tagliata.
/// Tutte le righe hanno la stessa forma; VoiceOver legge sempre nome e stato interi.
struct RigheDaControllare: View {
    let giocatori: [GiocatoreWidget]
    var lato: CGFloat = 26
    /// false dentro un altro Link (un Link dentro un Link non funziona): le righe sono solo testo.
    var conLink = true
    var spazio: CGFloat = 4

    var body: some View {
        let forme = RigaGiocatoreWidget.Forma.allCases
        PrimaCheEntra(forme.count) { i in
            VStack(alignment: .leading, spacing: spazio) {
                ForEach(giocatori) { g in
                    RigaGiocatoreWidget(g: g, lato: lato, conLink: conLink, forma: forme[i])
                }
            }
        }
    }
}
