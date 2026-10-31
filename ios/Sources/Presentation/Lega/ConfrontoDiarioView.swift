import SwiftUI

/// «Cosa consigliava SchieraXI» accanto a «Cosa hai schierato», con i cambi in evidenza.
/// Larghezza ampia (iPad, iPhone in orizzontale) e testo normale: due colonne; altrimenti una sotto l'altra.
/// I cambi si riconoscono dal grassetto, dal simbolo e dallo sfondo (non solo dal colore) e VoiceOver li dice a parole.
struct ConfrontoDiarioView: View {
    let confronto: ConfrontoDiario
    @Environment(\.horizontalSizeClass) private var classe
    @Environment(\.dynamicTypeSize) private var taglia

    private var affiancate: Bool { classe == .regular && !taglia.isAccessibilitySize && confronto.schierata != nil }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            if affiancate {
                HStack(alignment: .top, spacing: 12) {
                    colonnaConsigliata
                    colonnaSchierata
                }
            } else {
                colonnaConsigliata
                colonnaSchierata
            }
            if let frase = confronto.fraseCambi {
                Text(frase).font(.subheadline.weight(.semibold))
                    .fixedSize(horizontal: false, vertical: true)
                    .accessibilityIdentifier("diario-frase-cambi")
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private var colonnaConsigliata: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(confronto.titoloConsigliata).font(.headline).accessibilityAddTraits(.isHeader)
            Text(confronto.sottoConsigliata).font(.footnote).foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
            elenco(confronto.consigliata)
            if let p = confronto.panchina {
                Text(p).font(.footnote).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(confronto.voceConfronto)
    }

    @ViewBuilder private var colonnaSchierata: some View {
        if let titolo = confronto.titoloSchierata, let righe = confronto.schierata {
            VStack(alignment: .leading, spacing: 6) {
                Text(titolo).font(.headline).accessibilityAddTraits(.isHeader)
                elenco(righe)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .accessibilityElement(children: .ignore)
            .accessibilityLabel(titolo + ". " + righe.map(\.voce).joined(separator: ". ") + ".")
        }
    }

    private func elenco(_ righe: [ConfrontoDiario.Riga]) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            ForEach(righe) { r in
                HStack(alignment: .firstTextBaseline, spacing: 8) {
                    Text(r.ruolo).font(.caption.weight(.semibold)).foregroundStyle(.secondary)
                        .frame(minWidth: 18, alignment: .leading)
                    Text(r.nome).font(.body.weight(r.diverso ? .bold : .regular))
                        .fixedSize(horizontal: false, vertical: true)
                    if r.diverso {
                        Spacer(minLength: 0)
                        Image(systemName: "arrow.left.arrow.right").font(.caption).foregroundStyle(Color.attenzione)
                    }
                }
                .padding(.vertical, 3).padding(.horizontal, 6)
                .background(r.diverso ? Color.attenzione.opacity(0.18) : Color.clear, in: RoundedRectangle(cornerRadius: 8, style: .continuous))
            }
        }
    }
}
