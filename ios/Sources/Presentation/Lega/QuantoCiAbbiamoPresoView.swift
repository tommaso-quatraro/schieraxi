import SwiftUI
import Charts

/// «Quanto ci abbiamo preso» (Diario): i punti attesi della formazione consigliata contro quelli fatti, giornata per giornata,
/// e l'affidabilità dichiarata. Si mostra anche quando va male: nessun numero nascosto.
struct QuantoCiAbbiamoPresoView: View {
    let testo: TestoAffidabilita
    let punti: [PuntoAttesoFatto]

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(TestoAffidabilita.intro)
                .font(.footnote).foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
            FilaTessere {
                if let d = testo.dentro { TesseraDato(valore: d, etichetta: "dentro la fascia") }
                if let s = testo.scarto { TesseraDato(valore: s, etichetta: "scarto medio (punti)") }
                if let m = testo.media { TesseraDato(valore: m, etichetta: "fatti / previsti") }
            }
            Text([testo.riga, testo.verso].compactMap { $0 }.joined(separator: " "))
                .font(.subheadline)
                .fixedSize(horizontal: false, vertical: true)
            if let g = testo.giudizio {
                Label(g, systemImage: testo.fuoriLinea ? "exclamationmark.triangle.fill" : testo.pochiDati ? "hourglass" : "checkmark.seal")
                    .font(.subheadline.weight(testo.fuoriLinea ? .semibold : .regular))
                    .foregroundStyle(testo.fuoriLinea ? Color.attenzione : Color.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            if !punti.isEmpty {
                GraficoAttesoFatto(punti: punti)
                Text("Barra: fascia prevista. Trattino: punti attesi. Pallino: punti fatti, arancio se fuori dalla fascia.")
                    .font(.caption).foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
                DisclosureGroup("Giornata per giornata") {
                    VStack(alignment: .leading, spacing: 10) {
                        ForEach(punti.reversed()) { p in rigaGiornata(p) }
                    }
                    .padding(.top, 6)
                }
                .tint(.secondary)
            }
        }
        .padding(.vertical, 6)
    }

    private func rigaGiornata(_ p: PuntoAttesoFatto) -> some View {
        HStack(alignment: .firstTextBaseline, spacing: 10) {
            Text("G\(p.giornata)").font(.subheadline.weight(.semibold)).monospacedDigit()
                .frame(minWidth: 36, alignment: .leading)
            VStack(alignment: .leading, spacing: 2) {
                Text("attesi \(Formato.punti(p.atteso)) · fatti \(Formato.punti(p.fatti))").font(.subheadline).monospacedDigit()
                Text(p.frase).font(.caption)
                    .foregroundStyle(p.dentro == false ? Color.attenzione : Color.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            Spacer(minLength: 0)
            Text(FantavotoAtteso.conSegno(p.scarto)).font(.subheadline.weight(.bold)).monospacedDigit()
                .foregroundStyle(p.scarto >= 0 ? Color.verde : Color.malus)
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(p.voce)
    }
}

/// Il grafico: per ogni giornata la fascia prevista (barra), i punti attesi (trattino) e quelli fatti (pallino).
struct GraficoAttesoFatto: View {
    let punti: [PuntoAttesoFatto]
    @ScaledMetric(relativeTo: .body) private var altezza: CGFloat = 170

    private var dominioX: ClosedRange<Double> {
        let g = punti.map { Double($0.giornata) }
        return ((g.min() ?? 1) - 0.6)...((g.max() ?? 1) + 0.6)
    }

    private var dominioY: ClosedRange<Double> {
        let valori = punti.flatMap { [$0.atteso, $0.fatti, $0.basso ?? $0.atteso, $0.alto ?? $0.atteso] }
        let basso = floor((valori.min() ?? 50) - 3)
        let alto = ceil((valori.max() ?? 80) + 3)
        return basso...max(alto, basso + 1)
    }

    /// Le etichette dell'asse: tutte se sono poche, una sì e una no se sono tante (con l'ultima sempre).
    private var tacche: [Double] {
        let passo = punti.count > 7 ? 2 : 1
        return punti.enumerated()
            .filter { $0.offset % passo == 0 || $0.offset == punti.count - 1 }
            .map { Double($0.element.giornata) }
    }

    var body: some View {
        Chart(punti) { p in
            if let b = p.basso, let a = p.alto {
                RuleMark(x: .value("Giornata", Double(p.giornata)), yStart: .value("Basso", b), yEnd: .value("Alto", a))
                    .lineStyle(StrokeStyle(lineWidth: 12, lineCap: .round))
                    .foregroundStyle(Color.verde.opacity(0.2))
                    .accessibilityHidden(true)
            }
            PointMark(x: .value("Giornata", Double(p.giornata)), y: .value("Attesi", p.atteso))
                .symbol { Capsule().fill(Color.secondary).frame(width: 16, height: 3) }
                .accessibilityHidden(true)
            PointMark(x: .value("Giornata", Double(p.giornata)), y: .value("Fatti", p.fatti))
                .foregroundStyle(p.dentro == false ? Color.attenzione : Color.verde)
                .symbolSize(70)
                .accessibilityLabel("Giornata \(p.giornata)")
                .accessibilityValue(p.voce)
        }
        .chartXScale(domain: dominioX)
        .chartYScale(domain: dominioY)
        .chartXAxis {
            AxisMarks(values: tacche) { valore in
                AxisValueLabel {
                    if let g = valore.as(Double.self) { Text("G\(Formato.intero(g))") }
                }
            }
        }
        .chartYAxis {
            AxisMarks(position: .leading, values: .automatic(desiredCount: 4)) { _ in
                AxisGridLine()
                AxisValueLabel()
            }
        }
        .frame(height: min(altezza, 280))
    }
}

#Preview("Quanto ci abbiamo preso") {
    let a = AffidabilitaDiario(giornate: 10, scartoMedio: 4.2, erroreMedio: -1.5, puntiMediAttesi: 68.4, puntiMediFatti: 66.9,
                               dentroFascia: 7, conFascia: 10, percentualeDentro: 70, fasciaDichiarata: 80, pochiDati: false,
                               giornateMinime: 8, giudizio: "in_linea")
    let punti: [PuntoAttesoFatto] = [
        PuntoAttesoFatto(giornata: 5, atteso: 66.0, fatti: 70.5, basso: 58.0, alto: 74.5, dentro: true),
        PuntoAttesoFatto(giornata: 6, atteso: 67.5, fatti: 55.0, basso: 59.5, alto: 76.0, dentro: false),
        PuntoAttesoFatto(giornata: 7, atteso: 65.0, fatti: 66.0, basso: 57.0, alto: 73.5, dentro: true),
        PuntoAttesoFatto(giornata: 8, atteso: 68.0, fatti: 79.0, basso: 60.0, alto: 76.5, dentro: false),
    ]
    if let t = TestoAffidabilita(a) {
        List { Section(TestoAffidabilita.titolo) { QuantoCiAbbiamoPresoView(testo: t, punti: punti) } }
    }
}
