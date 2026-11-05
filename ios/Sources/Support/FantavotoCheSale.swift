import SwiftUI

/// Il fantavoto atteso grande della scheda del giocatore e del foglio «Perché questo numero»: le cifre salgono da zero
/// quando compare (`NumeroCheSale`). Se il server non manda il numero si legge «–», come la web e gli elenchi dei giocatori
/// (#251): mai «0,0», che sembra un voto. Uno zero vero resta «0,0» (issue #262, `FantavotoMancanteTests`).
struct FantavotoCheSale: View {
    let valore: Double?

    var body: some View {
        if let valore {
            NumeroCheSale(valore: valore)
        } else {
            Text(Formato.punti(nil)).monospacedDigit()
        }
    }
}
