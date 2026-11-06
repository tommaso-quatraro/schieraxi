import SwiftUI

/// La giornata in cima a Oggi (#299): «Giornata 8 · 11ª di Serie A» in una capsula di vetro. Se non entra (testo grande, finestra
/// stretta, Split View) va su due righe, «Giornata 8» e sotto «11ª di Serie A». VoiceOver legge sempre i due numeri.
struct CapsulaGiornata: View {
    /// Nil se il server non manda la giornata: resta «Giornata».
    let nome: NomeGiornata?

    var body: some View {
        ViewThatFits(in: .horizontal) {
            Label(nome?.intero ?? "Giornata", systemImage: "calendar")
                .padding(.horizontal, 12).padding(.vertical, 6)
                .vetro(in: Capsule())
                .fixedSize()
            Label {
                VStack(alignment: .leading, spacing: 0) {
                    Text(nome?.corto ?? "Giornata")
                    if let sotto = nome?.sotto { Text(sotto).font(.footnote) }
                }
            } icon: {
                Image(systemName: "calendar")
            }
            .padding(.horizontal, 12).padding(.vertical, 6)
            .vetro(in: RoundedRectangle(cornerRadius: 16, style: .continuous))
            .fixedSize(horizontal: false, vertical: true)
        }
        .font(.subheadline.weight(.semibold))
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(nome?.voce ?? "Giornata")
    }
}

#Preview("Giornata con i due numeri") {
    VStack(alignment: .leading, spacing: 12) {
        CapsulaGiornata(nome: NomeGiornata(serieA: 11, lega: 8))
        CapsulaGiornata(nome: NomeGiornata(serieA: 11, lega: nil))
        CapsulaGiornata(nome: NomeGiornata(serieA: 11, lega: 8)).frame(width: 150)
    }
    .padding()
    .background(Color.black)
    .environment(\.colorScheme, .dark)
}
