import SwiftUI

/// Il cognome sotto il volto della pedina: sempre intero e mai rimpicciolito (issue #274, come la web dal #265).
/// Prova nell'ordine: tutto su una riga; una parola per riga («Hamit» sopra «Çalvaroğlu»); a capo dentro la parola con il
/// trattino, nei punti in cui l'italiano va a capo («Castel-» sopra «vecchi»), solo se una parola da sola non ci sta.
/// Misura: `.caption` semibold, 12 punti alla taglia normale del testo. È anche la misura minima: con il testo di sistema più
/// piccolo resta 12 punti, come le scritte delle pedine sulla web (`--t-eti`) e il minimo dei testi di `docs/DESIGN.md`; sotto
/// si legge male sul prato. Cresce con il testo grande fino a XXL (16 punti): oltre, in una fila da cinque, andrebbe a capo a
/// ogni sillaba e la pedina diventerebbe una colonna di pezzi di parola.
/// Ogni forma si prova prima con un margine ai lati (`TestoStaccato.margine`): due nomi vicini nella stessa fila restano staccati.
/// Sull'iPad un nome che entrava appena su una riga toccava quello accanto, «Teo Kloosmeijer Cesare Pulinski» (#787, #819); ora va
/// a capo come sull'iPhone. Senza il margine si prova solo se con il margine non entra niente.
struct CognomePedina: View {
    let nome: String

    var body: some View {
        TestoStaccato(testo: nome, aCapo: LetturaPedina.parolePerRiga(nome))
            .font(.caption.weight(.semibold))
            .dynamicTypeSize(DynamicTypeSize.large...DynamicTypeSize.xxLarge)
            .foregroundStyle(.white)
            .multilineTextAlignment(.center)
            .fixedSize(horizontal: false, vertical: true)   // tutte le righe che servono: mai «…»
            .shadow(color: .black.opacity(0.5), radius: 1)
    }
}
