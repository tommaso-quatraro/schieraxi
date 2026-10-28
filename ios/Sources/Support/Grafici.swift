import SwiftUI
import Charts

// Grafici con Swift Charts (iOS 16). Ogni grafico ha un'alternativa testuale per VoiceOver (etichetta e valore) e, dove serve,
// un elenco dei numeri che si apre con «Mostra i numeri».

/// Un punto di un grafico a linee o a barre con più serie.
struct PuntoGrafico: Identifiable, Equatable {
    let serie: String
    let x: String
    let ordine: Int
    let valore: Double
    var id: String { "\(serie)-\(x)" }
}

// MARK: - Voti di un giocatore

/// Voto e fantavoto giornata per giornata; la linea tratteggiata è il 6.
struct GraficoVoti: View {
    let voti: [VotoGiornata]

    private var punti: [PuntoGrafico] {
        voti.sorted { $0.giornata < $1.giornata }.flatMap { v -> [PuntoGrafico] in
            var lista: [PuntoGrafico] = []
            if let fv = v.fv { lista.append(PuntoGrafico(serie: "Fantavoto", x: "\(v.giornata)", ordine: v.giornata, valore: fv)) }
            if let voto = v.voto { lista.append(PuntoGrafico(serie: "Voto", x: "\(v.giornata)", ordine: v.giornata, valore: voto)) }
            return lista
        }
    }

    private var dominio: ClosedRange<Double> {
        let valori = punti.map(\.valore)
        let basso = floor(min(4, valori.min() ?? 4))
        let alto = ceil(max(8, valori.max() ?? 8))
        return basso...alto
    }

    /// Dalla prima all'ultima giornata (con una sola giornata si allarga un po', altrimenti il grafico non ha larghezza).
    private var dominioGiornate: ClosedRange<Int> {
        let g = voti.map(\.giornata)
        let primo = g.min() ?? 1, ultimo = g.max() ?? 1
        return primo == ultimo ? (primo - 1)...(ultimo + 1) : primo...ultimo
    }

    /// Frase per VoiceOver e per l'elenco dei numeri.
    static func descrizione(_ voti: [VotoGiornata]) -> [String] {
        voti.sorted { $0.giornata < $1.giornata }.map { v in
            if v.voto == nil && v.fv == nil { return "Giornata \(v.giornata): senza voto" }
            let voto = v.voto.map { "voto \(Formato.decimali($0))" } ?? "senza voto"
            let fv = v.fv.map { "fantavoto \(Formato.decimali($0))" } ?? ""
            return "Giornata \(v.giornata): " + [voto, fv].filter { !$0.isEmpty }.joined(separator: ", ")
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Chart {
                RuleMark(y: .value("Sufficienza", 6))
                    .foregroundStyle(Color.secondary.opacity(0.6))
                    .lineStyle(StrokeStyle(lineWidth: 1, dash: [4, 4]))
                ForEach(punti) { p in
                    LineMark(x: .value("Giornata", p.ordine), y: .value("Punti", p.valore), series: .value("Serie", p.serie))
                        .foregroundStyle(by: .value("Serie", p.serie))
                        .interpolationMethod(.monotone)
                    PointMark(x: .value("Giornata", p.ordine), y: .value("Punti", p.valore))
                        .foregroundStyle(by: .value("Serie", p.serie))
                        .symbolSize(28)
                }
            }
            .chartForegroundStyleScale(["Fantavoto": Color.verde, "Voto": Color.blue])
            .chartYScale(domain: dominio)
            .chartXScale(domain: dominioGiornate)
            .chartXAxis { AxisMarks(values: .automatic(desiredCount: 6)) }
            .frame(height: 180)
            .accessibilityElement(children: .ignore)
            .accessibilityLabel("Grafico del voto e del fantavoto giornata per giornata. La linea tratteggiata è il sei.")
            .accessibilityValue(Self.descrizione(voti).joined(separator: ". "))
            Text("La linea tratteggiata è il 6.").font(.caption).foregroundStyle(.secondary)
            ElencoNumeri(righe: Self.descrizione(voti))
        }
    }
}

/// «Mostra i numeri»: la stessa informazione di un grafico, in forma di elenco (anche per chi non vede i colori).
struct ElencoNumeri: View {
    let righe: [String]

    var body: some View {
        DisclosureGroup("Mostra i numeri") {
            VStack(alignment: .leading, spacing: 4) {
                ForEach(Array(righe.enumerated()), id: \.offset) { _, riga in
                    Text(riga).font(.caption).foregroundStyle(.secondary)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.top, 4)
        }
        .font(.subheadline)
        .tint(.secondary)
    }
}

// MARK: - Prova del modello

/// Punti delle formazioni giornata per giornata: modello, scelta da fantamedia e massimo possibile.
struct GraficoAffidabilita: View {
    let righe: [RigaAffidabilita]

    private static let massimo = "Massimo possibile"

    private var punti: [PuntoGrafico] {
        righe.sorted { $0.giornata < $1.giornata }.flatMap { r -> [PuntoGrafico] in
            var lista: [PuntoGrafico] = []
            if let v = r.puntiModello { lista.append(PuntoGrafico(serie: "Modello", x: "\(r.giornata)", ordine: r.giornata, valore: v)) }
            if let v = r.puntiFantamedia { lista.append(PuntoGrafico(serie: "Da fantamedia", x: "\(r.giornata)", ordine: r.giornata, valore: v)) }
            if let v = r.puntiPerfetta { lista.append(PuntoGrafico(serie: Self.massimo, x: "\(r.giornata)", ordine: r.giornata, valore: v)) }
            return lista
        }
    }

    static func descrizione(_ righe: [RigaAffidabilita]) -> [String] {
        righe.sorted { $0.giornata < $1.giornata }.map { r in
            "Giornata \(r.giornata): modello \(r.puntiModello.map { Formato.decimali($0) } ?? "–"), "
                + "da fantamedia \(r.puntiFantamedia.map { Formato.decimali($0) } ?? "–"), "
                + "massimo possibile \(r.puntiPerfetta.map { Formato.decimali($0) } ?? "–")"
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Chart(punti) { p in
                LineMark(x: .value("Giornata", p.ordine), y: .value("Punti", p.valore), series: .value("Serie", p.serie))
                    .foregroundStyle(by: .value("Serie", p.serie))
                    .lineStyle(StrokeStyle(lineWidth: 2.2, lineCap: .round, dash: p.serie == Self.massimo ? [4, 4] : []))
                    .interpolationMethod(.monotone)
                PointMark(x: .value("Giornata", p.ordine), y: .value("Punti", p.valore))
                    .foregroundStyle(by: .value("Serie", p.serie))
                    .symbolSize(p.serie == Self.massimo ? 0 : 24)
            }
            .chartForegroundStyleScale(["Modello": Color.verde, "Da fantamedia": Color.orange, Self.massimo: Color.gray])
            .chartYScale(domain: .automatic(includesZero: false))
            .chartXScale(domain: (righe.map(\.giornata).min() ?? 1)...max((righe.map(\.giornata).max() ?? 1), (righe.map(\.giornata).min() ?? 1) + 1))
            .chartXAxis { AxisMarks(values: .automatic(desiredCount: 6)) }
            .frame(height: 190)
            .accessibilityElement(children: .ignore)
            .accessibilityLabel("Grafico dei punti delle formazioni, giornata per giornata: modello, scelta da fantamedia e massimo possibile")
            .accessibilityValue(Self.descrizione(righe).joined(separator: ". "))
            ElencoNumeri(righe: Self.descrizione(righe))
        }
    }
}

// MARK: - Scambio giornata per giornata

/// Guadagno di punti attesi di ogni squadra in ogni giornata di uno scambio (barre affiancate).
struct GraficoScambio: View {
    let giornate: [Int]
    let mio: [Double]
    let loro: [Double]
    var nomeLoro = "Loro"

    private var punti: [PuntoGrafico] {
        var lista: [PuntoGrafico] = []
        for (i, g) in giornate.enumerated() {
            if i < mio.count { lista.append(PuntoGrafico(serie: "Tu", x: "G\(g)", ordine: g, valore: mio[i])) }
            if i < loro.count { lista.append(PuntoGrafico(serie: nomeLoro, x: "G\(g)", ordine: g, valore: loro[i])) }
        }
        return lista
    }

    static func descrizione(giornate: [Int], mio: [Double], loro: [Double]) -> [String] {
        giornate.enumerated().compactMap { i, g in
            guard i < mio.count, i < loro.count else { return nil }
            return "Giornata \(g): tu \(Formato.conSegno(mio[i], cifre: 2)), loro \(Formato.conSegno(loro[i], cifre: 2))"
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Chart(punti) { p in
                BarMark(x: .value("Giornata", p.x), y: .value("Punti attesi", p.valore))
                    .foregroundStyle(by: .value("Chi", p.serie))
                    .position(by: .value("Chi", p.serie))
            }
            .chartForegroundStyleScale(["Tu": Color.verde, nomeLoro: Color.gray])
            .frame(height: 170)
            .accessibilityElement(children: .ignore)
            .accessibilityLabel("Grafico del guadagno di punti attesi giornata per giornata, per te e per l'altra squadra")
            .accessibilityValue(Self.descrizione(giornate: giornate, mio: mio, loro: loro).joined(separator: ". "))
            ElencoNumeri(righe: Self.descrizione(giornate: giornate, mio: mio, loro: loro))
        }
    }
}
