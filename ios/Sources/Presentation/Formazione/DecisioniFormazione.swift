import SwiftUI

/// Le decisioni in cima alla Formazione, come `dfRiga` della web (#616): al massimo due righe (le sceglie il server, `Decisioni`),
/// ognuna con il testo del server, «Urgente» davanti a quella urgente (non solo il colore), i punti attesi in più del cambio
/// proposto e la sua azione a destra («Sostituisci», «Usa la consigliata», «Vedi la rosa», …). Le azioni che scrivono restano al loro
/// posto, spente, finché la formazione non si può cambiare. Niente riga se non c'è niente da decidere.
struct DecisioniFormazione: View {
    let voci: [DaFareVoce]
    /// «+0,9 punti attesi.» accanto al cambio proposto.
    let guadagno: (DaFareVoce) -> String?
    /// I comandi che scrivono sono spenti.
    var spento = false
    let azione: (DaFareVoce) -> Void
    @Environment(\.dynamicTypeSize) private var taglia

    var body: some View {
        if !voci.isEmpty {
            Carta {
                ForEach(Array(voci.enumerated()), id: \.element.id) { i, v in
                    RigaConFilo(prima: i == 0) { riga(v) }
                }
            }
            .accessibilityElement(children: .contain)
            .accessibilityLabel(Catalogo.Df.daFare)
        }
    }

    private func riga(_ v: DaFareVoce) -> some View {
        // con il testo molto grande l'azione va sotto la frase: affiancate andavano a capo a metà parola
        let grande = taglia.isAccessibilitySize
        return HStack(alignment: grande ? .top : .center, spacing: 10) {
            VStack(alignment: .leading, spacing: grande ? 8 : 0) {
                frase(v)
                if grande { pulsante(v) }
            }
            if !grande {
                Spacer(minLength: 6)
                pulsante(v)
            }
        }
        .frame(minHeight: Tema.areaTocco)
    }

    private func frase(_ v: DaFareVoce) -> some View {
        let punti = guadagno(v).map { " " + $0 } ?? ""
        return Group {
            if v.urgente {
                Text("\(Text(Catalogo.Df.urgente).bold().foregroundStyle(Color.malus)) \(v.testo)\(Text(punti).bold())")
            } else {
                Text("\(v.testo)\(Text(punti).bold())")
            }
        }
        .font(.subheadline)
        .fixedSize(horizontal: false, vertical: true)
    }

    private func pulsante(_ v: DaFareVoce) -> some View {
        Button(v.testoPulsante) { azione(v) }
            .font(.subheadline.weight(.semibold))
            .buttonStyle(.borderless)
            .foregroundStyle(Color.verde)
            .frame(minHeight: Tema.areaTocco)
            .disabled(spento && v.scrive)
    }
}
