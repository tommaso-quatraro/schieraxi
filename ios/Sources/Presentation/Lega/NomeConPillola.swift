import SwiftUI

/// Il nome di una squadra, con una pillola («tua») se serve. Il nome non va mai a capo a metà parola (issue #432):
/// - se nome e pillola stanno insieme su una riga, la pillola è accanto al nome;
/// - se no, il nome ha tutta la colonna e va a capo solo tra le parole, e la pillola passa sotto. Prima la pillola stava
///   sempre accanto e prendeva il suo posto: con il testo massimo «Schiera FC» diventava «Schier» e «a FC»;
/// - una parola sola un poco più lunga della colonna si rimpicciolisce (fino a 0,8) invece di spezzarsi.
struct NomeConPillola<Pillola: View>: View {
    let nome: String
    private let pillola: Pillola

    init(nome: String, @ViewBuilder pillola: () -> Pillola) {
        self.nome = nome
        self.pillola = pillola()
    }

    /// Un nome di una parola sola non ha dove andare a capo: l'unica via è rimpicciolirlo un poco.
    private var unaParola: Bool {
        nome.split(whereSeparator: \.isWhitespace).count <= 1
    }

    var body: some View {
        ViewThatFits(in: .horizontal) {
            HStack {
                Text(nome).font(.headline)
                pillola
            }
            VStack(alignment: .leading, spacing: 2) {
                Text(nome).font(.headline)
                    .lineLimit(unaParola ? 1 : nil)
                    .minimumScaleFactor(unaParola ? 0.8 : 1)
                    .fixedSize(horizontal: false, vertical: true)
                pillola
            }
        }
    }
}
