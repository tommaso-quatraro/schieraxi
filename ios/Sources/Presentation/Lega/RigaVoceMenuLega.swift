import SwiftUI

/// Una riga dei menu Squadra e Altro: icona, nome e sotto la riga piccola della web (`sub` di `VOCI_LEGA`).
/// VoiceOver legge nome e riga insieme, come un'unica voce.
struct RigaVoceMenuLega: View {
    let voce: VoceMenuLega

    var body: some View {
        NavigationLink(value: voce.pagina) {
            Label {
                VStack(alignment: .leading, spacing: 2) {
                    Text(voce.nome)
                    Text(voce.dettaglio)
                        .font(.caption)
                        .foregroundStyle(Color.testoSecondario)
                }
            } icon: {
                Image(systemName: voce.simbolo)
            }
            .labelStyle(.voce(voce.colore))
            .frame(minHeight: Tema.areaTocco)
        }
    }
}
