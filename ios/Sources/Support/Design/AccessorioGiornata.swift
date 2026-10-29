import SwiftUI

/// Il conto alla rovescia alla prima partita: ore, minuti e secondi se manca meno di un giorno, altrimenti giorni e ore.
/// Lo usano il riquadro principale di Oggi e l'accessorio sotto la barra delle schede.
struct TestoConto: View {
    let inizio: Date
    let adesso: Date

    var body: some View {
        if inizio.timeIntervalSince(adesso) < 24 * 3600 {
            Text(timerInterval: adesso...inizio, countsDown: true).monospacedDigit()
        } else {
            Text(inizio, style: .relative)
        }
    }
}

extension View {
    /// Su iOS 26: una piccola barra di vetro sopra le schede con la giornata e il conto alla rovescia; un tocco apre la formazione.
    @ViewBuilder
    func accessorioGiornata(_ vm: OggiViewModel, inOggi: Bool, apri: @escaping () -> Void) -> some View {
        if #available(iOS 26.0, *) {
            self.tabViewBottomAccessory {
                AccessorioGiornata(vm: vm, inOggi: inOggi, apri: apri)
            }
        } else {
            self
        }
    }
}

@available(iOS 26.0, *)
struct AccessorioGiornata: View {
    @ObservedObject var vm: OggiViewModel
    let inOggi: Bool
    let apri: () -> Void

    var body: some View {
        Button(action: apri) {
            HStack(spacing: 8) {
                Image(systemName: "timer")
                    .symbolRenderingMode(.hierarchical)
                    .foregroundStyle(Color.verde)
                    .accessibilityHidden(true)
                contenuto
                Spacer(minLength: 0)
            }
            .padding(.horizontal, 12)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityHint("Apre la formazione")
        .task(id: inOggi) {
            // In Oggi i dati li carica la schermata; altrove li chiede l'accessorio, così il conto c'è sempre.
            if !inOggi, vm.oggi == nil, !vm.caricatore.inCorso { await vm.carica() }
        }
    }

    @ViewBuilder
    private var contenuto: some View {
        if let oggi = vm.oggi, let inizio = Quando.data(oggi.inizio) {
            TimelineView(.periodic(from: Date(), by: 1)) { contesto in
                HStack(spacing: 6) {
                    Text("Giornata \(oggi.giornata)").font(.subheadline.weight(.semibold))
                    if inizio > contesto.date {
                        TestoConto(inizio: inizio, adesso: contesto.date)
                            .font(.subheadline).foregroundStyle(.secondary)
                    } else {
                        Text("in corso").font(.subheadline).foregroundStyle(.secondary)
                    }
                }
                .lineLimit(1)
                .accessibilityElement(children: .combine)
            }
        } else {
            Text("SchieraXI").font(.subheadline.weight(.semibold))
        }
    }
}
