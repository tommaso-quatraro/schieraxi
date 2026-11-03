import SwiftUI

/// Le etichette di un giocatore sotto il nome, come la web: ogni etichetta in una pillola del suo colore; le pillole vanno a
/// capo quando la riga è piena, e una pillola più larga della riga va a capo dentro di sé (mai tagliata, issue #227).
struct PilloleEtichette: View {
    let etichette: [Etichetta]

    var body: some View {
        FilaPillole(spazio: 4) {
            ForEach(Array(etichette.enumerated()), id: \.offset) { voce in
                PillolaEtichetta(etichetta: voce.element)
            }
        }
    }
}
