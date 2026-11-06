import SwiftUI

/// Un pulsante della riga di stato della scelta (`RigaStatoScelta`): testo con il simbolo, area di tocco da 44 pt, e con il testo
/// grande va a capo invece di uscire dallo schermo.
struct PulsanteRigaStato: View {
    let testo: String
    let simbolo: String
    let colore: Color
    let azione: () -> Void

    var body: some View {
        Button(action: azione) {
            Label(testo, systemImage: simbolo).font(.footnote.weight(.semibold))
                .fixedSize(horizontal: false, vertical: true).frame(minHeight: 44).contentShape(Rectangle())
        }
        .buttonStyle(StilePressione())
        .foregroundStyle(colore)
    }
}
