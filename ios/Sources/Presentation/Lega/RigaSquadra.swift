import SwiftUI

/// Una riga dell'elenco delle squadre: stemma, nome (con «tua» sulla propria), giocatori e crediti.
struct RigaSquadra: View {
    let squadra: SquadraLega

    var body: some View {
        HStack(spacing: 12) {
            StemmaSquadra(nome: squadra.nome, dimensione: 44)
            VStack(alignment: .leading, spacing: 2) {
                NomeConPillola(nome: squadra.nome) {
                    if squadra.mia == true { PillolaTua() }
                }
                Text(Formato.giocatori(squadra.giocatori ?? 0) + (squadra.creditiResidui.map { " · \(Formato.crediti(Formato.intero($0)))" } ?? ""))
                    .font(.caption).foregroundStyle(Color.testoSecondario)
            }
        }
        .frame(minHeight: 44)
        .accessibilityElement(children: .combine)
    }
}
