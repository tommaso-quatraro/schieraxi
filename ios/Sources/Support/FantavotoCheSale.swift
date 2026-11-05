import SwiftUI

/// Il fantavoto atteso grande della scheda del giocatore e del foglio «Perché questo numero»: le cifre salgono da zero
/// quando compare (`NumeroCheSale`).
struct FantavotoCheSale: View {
    let valore: Double?

    var body: some View {
        NumeroCheSale(valore: valore ?? 0)
    }
}
