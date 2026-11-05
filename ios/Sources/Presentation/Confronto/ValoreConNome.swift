import SwiftUI

/// Il valore di un giocatore nell'elenco di «Tutti i numeri»: il nome a sinistra e il numero a destra; se non stanno interi
/// sulla stessa riga, il numero va sotto il nome. Il nome va a capo intero.
struct ValoreConNome: View {
    let nome: String
    let valore: String

    var body: some View {
        ViewThatFits(in: .horizontal) {
            HStack(alignment: .firstTextBaseline, spacing: 12) {
                Text(nome)
                Spacer(minLength: 0)
                Text(valore).bold().monospacedDigit()
            }
            VStack(alignment: .leading, spacing: 0) {
                Text(nome).fixedSize(horizontal: false, vertical: true)
                Text(valore).bold().monospacedDigit().fixedSize(horizontal: false, vertical: true)
            }
        }
    }
}
