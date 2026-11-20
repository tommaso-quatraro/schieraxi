import SwiftUI

/// Un testo sotto il volto della pedina (il cognome, lo stato) staccato da quello della pedina accanto nella stessa fila: ogni
/// forma si prova prima con `margine` libero per lato, poi senza; per ultima la forma con i trattini morbidi, che va a capo dove
/// serve. Intero e mai rimpicciolito: carattere, colore e altezza li mette chi lo usa (`CognomePedina`, `RigaGioca`).
/// Con 4 punti per lato sull'iPad due nomi vicini restavano a circa 15 punti l'uno dall'altro e si leggevano come uno solo
/// («Teo Kloosmeijer Cesare Pulinski», #787, #819); con 10 restano almeno 22 punti fra due testi, come fra due colonne.
struct TestoStaccato: View {
    let testo: String
    /// Il testo a capo fra le parole, da provare quando la riga intera non entra (nil con una parola sola).
    let aCapo: String?

    /// Lo spazio libero per lato attorno al testo.
    static let margine: CGFloat = 10

    var body: some View {
        ViewThatFits(in: .horizontal) {
            Text(testo).padding(.horizontal, Self.margine)
            if let aCapo {
                Text(aCapo).padding(.horizontal, Self.margine)
            }
            Text(testo)
            if let aCapo {
                Text(aCapo)
            }
            Text(LetturaPedina.sillabato(testo))
        }
    }
}
