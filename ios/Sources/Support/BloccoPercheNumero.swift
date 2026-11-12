import SwiftUI

/// I motivi del fantavoto atteso, uno per riga: «+1,1 · Segna più della media del ruolo». Sotto, il riferimento
/// (il giocatore medio del ruolo). Sta nella scheda del giocatore, in «Perché questo numero» (come `bloccoPerche` della web).
struct BloccoPercheNumero: View {
    let perche: PercheNumero
    @ScaledMetric(relativeTo: .subheadline) private var larghezzaEffetto: CGFloat = 52

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            ForEach(perche.righe) { r in
                HStack(alignment: .center, spacing: 10) {
                    effetto(r)
                    Text(r.testo)
                        .font(.subheadline)
                        .fixedSize(horizontal: false, vertical: true)
                    Spacer(minLength: 0)
                }
                .accessibilityElement(children: .ignore)
                .accessibilityLabel(r.voce)
            }
            Text(perche.nota)
                .font(.footnote).foregroundStyle(Color.testoSecondario)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    private func colore(_ v: PercheNumero.Verso) -> Color {
        switch v {
        case .su: return .verde
        case .giu: return .malus
        case .avviso: return .attenzione
        case .neutro: return .testoSecondario
        }
    }

    @ViewBuilder
    private func effetto(_ r: PercheNumero.Riga) -> some View {
        let tinta = colore(r.verso)
        Group {
            if let e = r.effetto {
                Text(e).font(.subheadline.weight(.bold)).monospacedDigit().lineLimit(1).minimumScaleFactor(0.8)
            } else {
                Image(systemName: r.verso == .avviso ? "exclamationmark.triangle.fill" : "circle.fill")
                    .font(r.verso == .avviso ? .subheadline : .caption2)
            }
        }
        .foregroundStyle(tinta)
        .frame(minWidth: larghezzaEffetto, minHeight: 28)
        .background(tinta.opacity(0.14), in: RoundedRectangle(cornerRadius: 8, style: .continuous))
        .accessibilityHidden(true)
    }
}

#Preview("Perché questo numero") {
    let json = """
    {"id": 7, "nome": "Brunvalli", "ruolo": "A", "squadra": "torino", "avversario": "genoa", "in_casa": true, "p_voto": 0.72, "fv_atteso": 7.6,
     "fv_atteso_medio_ruolo": 6.9,
     "perche_numero": [{"chiave": "gioca", "testo": "gioca il 72%: dubbio", "effetto": null},
                       {"chiave": "gol", "testo": "segna più della media del ruolo (41% di segnare)", "effetto": 0.9},
                       {"chiave": "partita", "testo": "partita difficile in casa", "effetto": -0.3}]}
    """
    if let g: Giocatore = try? Decodifica.decodifica(Data(json.utf8)), let p = PercheNumero(g) {
        BloccoPercheNumero(perche: p).padding()
    }
}
