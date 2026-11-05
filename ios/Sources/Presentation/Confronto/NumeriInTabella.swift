import SwiftUI

/// «Tutti i numeri» in tabella, come la web: in testa i nomi dei due giocatori, poi una riga per voce con i due valori a
/// destra. I nomi vanno a capo interi nella loro colonna (#272: prima stavano su una riga e finivano con «…»).
struct NumeriInTabella: View {
    let x: Giocatore
    let y: Giocatore
    let voci: [VoceNumeriConfronto]

    /// Lo spazio tra le colonne, uguale in ogni riga perché le colonne stiano una sotto l'altra.
    static let spazio: CGFloat = 10

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            RigaTreColonne(spazio: Self.spazio) {
                Color.clear.frame(width: 0, height: 0)
                TestoCella(testo: x.nomeCorto)
                TestoCella(testo: y.nomeCorto)
            }
            .font(.caption.bold())
            // VoiceOver legge i nomi in ogni riga
            .accessibilityHidden(true)
            ForEach(voci) { voce in
                RigaTreColonne(spazio: Self.spazio) {
                    TestoCella(testo: voce.titolo, allineamento: .leading).foregroundStyle(Color.testoSecondario)
                    TestoCella(testo: voce.a).bold().monospacedDigit()
                    TestoCella(testo: voce.b).bold().monospacedDigit()
                }
                .font(.subheadline)
                .accessibilityElement(children: .ignore)
                .accessibilityLabel(voce.frase(x, y))
            }
        }
    }
}
