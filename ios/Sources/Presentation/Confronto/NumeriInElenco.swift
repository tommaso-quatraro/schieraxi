import SwiftUI

/// «Tutti i numeri» quando la tabella non ci sta (testo grande, scheda stretta): una voce dopo l'altra, con sotto il valore
/// di ognuno dei due giocatori accanto al suo nome. Tutto a capo, mai «…» (#272).
struct NumeriInElenco: View {
    let x: Giocatore
    let y: Giocatore
    let voci: [VoceNumeriConfronto]

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            ForEach(voci) { voce in
                VStack(alignment: .leading, spacing: 4) {
                    Text(voce.titolo).foregroundStyle(Color.testoSecondario)
                        .fixedSize(horizontal: false, vertical: true)
                    ValoreConNome(nome: x.nomeCorto, valore: voce.a)
                    ValoreConNome(nome: y.nomeCorto, valore: voce.b)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .accessibilityElement(children: .ignore)
                .accessibilityLabel(voce.frase(x, y))
            }
        }
        .font(.subheadline)
    }
}
