import SwiftUI

/// Il nome di una squadra, con accanto una pillola («tua») se serve.
struct NomeConPillola<Pillola: View>: View {
    let nome: String
    private let pillola: Pillola

    init(nome: String, @ViewBuilder pillola: () -> Pillola) {
        self.nome = nome
        self.pillola = pillola()
    }

    var body: some View {
        HStack {
            Text(nome).font(.headline)
            pillola
        }
    }
}
