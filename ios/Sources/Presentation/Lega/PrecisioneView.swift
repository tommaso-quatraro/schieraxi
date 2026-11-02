import SwiftUI
import Charts

/// «Quanto ci abbiamo preso» (Diario, campo `precisione` del server): quattro numeri con una frase, l'errore del fantavoto atteso
/// giornata per giornata e le note. Tutto viene dal server e si mostra anche quando i numeri sono brutti.
struct PrecisioneView: View {
    let testo: TestoPrecisione
    /// Su iPhone una voce sotto l'altra; dove c'è spazio (iPad, orizzontale) due colonne. Cresce con il testo grande.
    @ScaledMetric(relativeTo: .body) private var larghezzaVoce: CGFloat = 280

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("\(TestoPrecisione.intro) \(testo.calcolatoSu)")
                .font(.footnote).foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
            if let pochi = testo.pochi {
                Label(pochi, systemImage: "hourglass")
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(Color.attenzione)
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(10)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color.attenzione.opacity(0.12), in: RoundedRectangle(cornerRadius: Tema.raggioPiccolo, style: .continuous))
                    .accessibilityElement(children: .combine)
            }
            LazyVGrid(columns: [GridItem(.adaptive(minimum: min(larghezzaVoce, 420)), spacing: 10, alignment: .top)], alignment: .leading, spacing: 10) {
                ForEach(Array(testo.voci.enumerated()), id: \.offset) { _, voce in
                    VocePrecisione(voce: voce)
                }
            }
            if testo.barre.count >= 2 {
                GraficoErroreFantavoto(barre: testo.barre)
                Text(TestoPrecisione.legendaGrafico)
                    .font(.caption).foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            if !testo.righe.isEmpty {
                DisclosureGroup(TestoPrecisione.andamento) {
                    VStack(alignment: .leading, spacing: 8) {
                        ForEach(Array(testo.righe.enumerated()), id: \.offset) { _, riga in
                            Text(riga).font(.subheadline).monospacedDigit()
                                .fixedSize(horizontal: false, vertical: true)
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.top, 6)
                }
                .tint(.secondary)
                .frame(minHeight: Tema.areaTocco)
            }
            if let nota = testo.notaRicostruiti {
                Text(nota)
                    .font(.caption).foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .padding(.vertical, 6)
    }
}

/// Un numero grande, la sua etichetta e la frase che lo spiega; per «gioca» anche il giudizio e tutte le fasce.
private struct VocePrecisione: View {
    let voce: TestoPrecisione.Voce

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            VStack(alignment: .leading, spacing: 4) {
                Text(voce.numero)
                    .font(.title.bold()).monospacedDigit()
                    .foregroundStyle(voce.attenzione ? Color.attenzione : Color.primary)
                    .lineLimit(1).minimumScaleFactor(0.6)
                Text(voce.etichetta)
                    .font(.caption).foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
                Text(voce.frase)
                    .font(.subheadline)
                    .fixedSize(horizontal: false, vertical: true)
                if let g = voce.giudizio {
                    Label(g, systemImage: voce.attenzione ? "exclamationmark.triangle.fill" : "info.circle")
                        .font(.subheadline.weight(voce.attenzione ? .semibold : .regular))
                        .foregroundStyle(voce.attenzione ? Color.attenzione : Color.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            .accessibilityElement(children: .ignore)
            .accessibilityLabel(voce.voce)
            if !voce.fasce.isEmpty {
                DisclosureGroup(TestoPrecisione.tutteLeFasce) {
                    VStack(alignment: .leading, spacing: 6) {
                        ForEach(Array(voce.fasce.enumerated()), id: \.offset) { _, f in
                            Text(f).font(.caption)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.top, 4)
                }
                .font(.subheadline)
                .tint(.secondary)
                .frame(minHeight: Tema.areaTocco)
            }
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.sfondoIncavo, in: RoundedRectangle(cornerRadius: Tema.raggioPiccolo, style: .continuous))
    }
}

/// Barre dell'errore medio del fantavoto atteso, una per giornata (più bassa = meglio), con il valore sopra.
struct GraficoErroreFantavoto: View {
    let barre: [TestoPrecisione.Barra]
    @ScaledMetric(relativeTo: .body) private var altezza: CGFloat = 150

    /// Come la web: la scala parte da 0 e arriva almeno a 2,5 punti, così un errore piccolo resta una barra bassa.
    private var massimo: Double { max(2.5, barre.map(\.errore).max() ?? 0) * 1.15 }

    var body: some View {
        Chart(barre) { b in
            BarMark(x: .value("Giornata", b.etichetta), y: .value("Errore medio", b.errore), width: .ratio(0.6))
                .foregroundStyle(Color.verde.gradient)
                .cornerRadius(3)
                .annotation(position: .top, spacing: 2) {
                    Text(b.valore).font(.caption2).monospacedDigit().foregroundStyle(.secondary)
                }
                .accessibilityLabel("Giornata \(b.etichetta)")
                .accessibilityValue("errore medio \(b.valore) punti")
        }
        .chartYScale(domain: 0...massimo)
        .chartYAxis(.hidden)
        .chartXAxis {
            AxisMarks { _ in
                AxisValueLabel()
            }
        }
        .frame(height: min(altezza, 260))
        .accessibilityElement(children: .contain)
        .accessibilityLabel(TestoPrecisione.titoloGrafico)
    }
}

#Preview("Quanto ci abbiamo preso") {
    let p = PrecisioneDiario(
        giornate: 4, pochiDati: true, giornateMinime: 8, fonti: .init(mostrati: 3, ricostruiti: 1),
        fantavoto: .init(erroreMedio: 1.4, scostamento: -0.4, entroUnPunto: 58, voti: 41),
        gioca: .init(giocatori: 52, gruppi: [.init(da: 40, a: 70, giocatori: 9, pochi: true, detto: 55, giocato: 44),
                                             .init(da: 90, a: 100, giocatori: 43, pochi: false, detto: 96, giocato: 83)],
                     principale: 1, fonte: "mostrati", giornate: 3),
        confronto: .init(giornate: 2, meglioConsigliata: 2, meglioTua: 0, pari: 0, punti: 12, mediaConsigliata: 67.5, mediaTua: 61.5),
        squadra: AffidabilitaDiario(giornate: 4, scartoMedio: 3.4, puntiMediAttesi: 67.4, puntiMediFatti: 67.0, dentroFascia: 4, conFascia: 4,
                                    fasciaDichiarata: 80),
        perGiornata: [.init(giornata: 7, erroreFantavoto: 1.6, attesi: 65, fatti: 60.5),
                      .init(giornata: 8, erroreFantavoto: 1.2, attesi: 67, fatti: 64, tua: 59.5, differenza: 4.5),
                      .init(giornata: 9, erroreFantavoto: 1.5, attesi: 68.5, fatti: 71, tua: 63.5, differenza: 7.5),
                      .init(giornata: 10, erroreFantavoto: 1.3, attesi: 69, fatti: 72.5)])
    if let t = TestoPrecisione(p) {
        List { Section(TestoPrecisione.titolo) { PrecisioneView(testo: t) } }
    }
}
