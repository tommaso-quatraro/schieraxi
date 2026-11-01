import SwiftUI

/// «Le tue scelte» in cima al Diario: un numero grande («5 su 9»), tre conti (tu, consiglio, pari) e le ultime giornate.
/// Una sola frase per VoiceOver sul riepilogo; le righe delle giornate si leggono una per una.
struct SchedaScelteTueView: View {
    let testo: ScelteTueTesto
    @Environment(\.dynamicTypeSize) private var tagliaTesto
    @State private var tutte = false

    private static let righeIniziali = 3

    var body: some View {
        Carta("Le tue scelte", simbolo: "person.crop.circle.badge.questionmark") {
            riepilogo
            if !testo.righe.isEmpty { Divider(); giornate }
        }
    }

    private var riepilogo: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(testo.numeroGrande)
                .font(.system(.largeTitle, design: .rounded).weight(.bold))
                .monospacedDigit()
                .minimumScaleFactor(0.6)
            Text(testo.sottotitolo).font(.subheadline).foregroundStyle(.secondary)
            conti
            Text(testo.frasePunti).font(.body)
            if !testo.fraseCommento.isEmpty {
                Text(testo.fraseCommento).font(.subheadline).foregroundStyle(.secondary)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(testo.voceRiepilogo)
    }

    /// Tre conti affiancati; con il testo molto grande (o poco spazio) vanno uno sotto l'altro.
    private var conti: some View {
        let voci: [(String, Int)] = [("Meglio tu", testo.tua), ("Meglio il consiglio", testo.consigliata), ("Pari", testo.pari)]
        return ViewThatFits(in: .horizontal) {
            HStack(alignment: .top, spacing: 8) {
                ForEach(voci, id: \.0) { conto($0.0, $0.1) }
            }
            .fixedSize(horizontal: false, vertical: true)
            VStack(alignment: .leading, spacing: 8) {
                ForEach(voci, id: \.0) { conto($0.0, $0.1) }
            }
        }
    }

    private func conto(_ titolo: String, _ n: Int) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text("\(n)").font(.title2.weight(.semibold)).monospacedDigit()
            Text(titolo).font(.footnote).foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, minHeight: Tema.areaTocco, alignment: .leading)
        .padding(.horizontal, 10)
        .background(Color.sfondoIncavo, in: RoundedRectangle(cornerRadius: Tema.raggioPiccolo, style: .continuous))
    }

    private var giornate: some View {
        let mostrate = tutte ? testo.righe : Array(testo.righe.prefix(Self.righeIniziali))
        return VStack(alignment: .leading, spacing: 0) {
            ForEach(mostrate) { r in
                VStack(alignment: .leading, spacing: 2) {
                    Text(r.titolo).font(.subheadline.weight(.semibold))
                    Text(r.frase).font(.subheadline)
                    Text(r.punti).font(.footnote).foregroundStyle(colore(r.esito)).monospacedDigit()
                }
                .frame(maxWidth: .infinity, minHeight: Tema.areaTocco, alignment: .leading)
                .padding(.vertical, 6)
                .accessibilityElement(children: .ignore)
                .accessibilityLabel("\(r.titolo). \(r.frase) \(r.punti)")
            }
            if testo.righe.count > Self.righeIniziali {
                Button(tutte ? "Mostra meno" : "Mostra tutte le \(testo.righe.count) giornate") {
                    withAnimation(Tema.morbida) { tutte.toggle() }
                }
                .font(.subheadline.weight(.semibold))
                .frame(minHeight: Tema.areaTocco)
            }
        }
    }

    /// Il colore aiuta ma non basta da solo: ogni riga dice anche a parole chi ha fatto meglio.
    private func colore(_ e: ScelteTueTesto.Esito) -> Color {
        switch e {
        case .tua: return Color.verde
        case .consigliata: return Color.attenzione
        case .pari: return Color.secondary
        }
    }
}

#Preview {
    let dati = Data(#"{"giornate": 9, "meglio_tua": 5, "meglio_consigliata": 3, "pari": 1, "punti_differenza": 4.5, "percentuale_tua": 56, "pochi_dati": false, "per_giornata": [{"stagione": "2026-27", "giornata": 9, "hai_scelto": ["Orsetti"], "consigliava": ["Dunfrey"], "punti_tua": 63.5, "punti_consigliata": 71.0, "differenza": -7.5, "esito": "consigliata"}]}"#.utf8)
    let scelte: ScelteTue? = try? Decodifica.decodifica(dati)
    return ScrollView {
        if let testo = ScelteTueTesto(scelte) { SchedaScelteTueView(testo: testo).padding() }
    }
}
