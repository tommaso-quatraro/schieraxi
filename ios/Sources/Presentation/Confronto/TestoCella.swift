import SwiftUI

/// Il testo di una cella di `RigaTreColonne`: va a capo solo tra una parola e l'altra, allineato a sinistra (la voce) o a
/// destra (i nomi e i numeri). La sua larghezza ideale è quella della parola più lunga: le parole, invisibili, stanno sotto il
/// testo e lo misurano con il suo stesso carattere. Così la riga sa quanto spazio serve perché nessuna parola si spezzi.
struct TestoCella: View {
    let testo: String
    var allineamento: HorizontalAlignment = .trailing

    private var parole: [String] { testo.split(separator: " ").map(String.init) }

    var body: some View {
        ZStack(alignment: Alignment(horizontal: allineamento, vertical: .top)) {
            // solo per la misura: non si vedono e VoiceOver non le legge
            ForEach(Array(parole.enumerated()), id: \.offset) { _, parola in
                Text(parola).fixedSize().hidden().accessibilityHidden(true)
            }
            // larghezza ideale zero: conta solo la parola più lunga; con una larghezza data, va a capo dentro la colonna
            Text(testo)
                .multilineTextAlignment(allineamento == .leading ? .leading : .trailing)
                .fixedSize(horizontal: false, vertical: true)
                .frame(minWidth: 0, idealWidth: 0, maxWidth: .infinity, alignment: Alignment(horizontal: allineamento, vertical: .top))
        }
    }
}
