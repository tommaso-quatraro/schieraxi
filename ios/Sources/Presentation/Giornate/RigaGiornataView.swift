import SwiftUI

/// Una riga della pagina Giornate: a sinistra la giornata (e la stagione, se ce n'è più di una) con la frase di chi sono i punti, a
/// destra i punti fatti grandi e sotto «punti (attesi 71,7)». Con il testo molto grande le due parti vanno una sotto l'altra.
struct RigaGiornataView: View {
    let riga: RigaGiornata
    @Environment(\.dynamicTypeSize) private var dimensione

    var body: some View {
        let impilata = dimensione.isAccessibilitySize
        let disposizione = impilata
            ? AnyLayout(VStackLayout(alignment: .leading, spacing: 6))
            : AnyLayout(HStackLayout(alignment: .top, spacing: 12))
        disposizione {
            VStack(alignment: .leading, spacing: 3) {
                Text(riga.nome)
                    .font(.body.weight(.semibold))
                    .fixedSize(horizontal: false, vertical: true)
                if let stagione = riga.stagione {
                    Text(stagione)
                        .font(.caption).foregroundStyle(Color.testoSecondario)
                }
                Text(riga.stato)
                    .font(.footnote).foregroundStyle(Color.testoSecondario)
                    .fixedSize(horizontal: false, vertical: true)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            VStack(alignment: impilata ? .leading : .trailing, spacing: 0) {
                Text(riga.punti)
                    .font(.title2.bold()).monospacedDigit()
                Text(riga.attesi)
                    .font(.caption).foregroundStyle(Color.testoSecondario).monospacedDigit()
                    .multilineTextAlignment(impilata ? .leading : .trailing)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .frame(minHeight: Tema.areaTocco)
        .contentShape(Rectangle())
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(riga.voce)
    }
}

#Preview("Righe") {
    List {
        RigaGiornataView(riga: RigaGiornata(id: "a", nome: NomeGiornata(serieA: 11, lega: 8).intero, stagione: nil,
                                            stato: Catalogo.Giornate.cambi(2, d: Formato.conSegno(-1.5)), punti: "74,5",
                                            attesi: Catalogo.Formazione.puntiEAttesi(n: "71,7"), voce: NomeGiornata(serieA: 11, lega: 8).voce))
        RigaGiornataView(riga: RigaGiornata(id: "b", nome: NomeGiornata(serieA: 38, lega: nil).intero, stagione: "2025-26",
                                            stato: Catalogo.Giornate.nonSalvata, punti: "66,0",
                                            attesi: Catalogo.Formazione.punti, voce: NomeGiornata(serieA: 38, lega: nil).voce))
    }
}
