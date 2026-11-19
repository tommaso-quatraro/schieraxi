import SwiftUI

/// Il nome di un'impostazione con sotto, in piccolo, la riga d'aiuto della web (se ce l'ha). Va dentro l'etichetta di un
/// interruttore o di una voce: VoiceOver legge il nome e la riga insieme, il testo grande le manda a capo.
struct NomeConAiuto: View {
    let nome: String
    var aiuto: String?

    init(_ nome: String, aiuto: String? = nil) {
        self.nome = nome
        self.aiuto = aiuto
    }

    var body: some View {
        if let aiuto {
            VStack(alignment: .leading, spacing: 2) {
                Text(nome)
                Text(aiuto).font(.caption).foregroundStyle(Color.testoSecondario)
            }
        } else {
            Text(nome)
        }
    }
}

#Preview("Nome con riga d'aiuto") {
    List {
        Toggle(isOn: .constant(true)) {
            NomeConAiuto(Catalogo.Imp.avvisiQui, aiuto: Catalogo.Imp.avvisiQuiAiuto)
        }
        Toggle(isOn: .constant(false)) { NomeConAiuto(Catalogo.Avv.oreTranq) }
    }
    .dynamicTypeSize(.accessibility1)
}
