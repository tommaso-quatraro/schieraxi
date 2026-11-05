import SwiftUI

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
                Marchio(lato: 22)
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
        if let oggi = vm.oggi, let nome = oggi.nomeGiornata, let inizio = Quando.data(oggi.chiusura) {
            TimelineView(.periodic(from: Date(), by: 1)) { contesto in
                let ora = Orologio.daSistema(contesto.date)
                HStack(spacing: 6) {
                    // spazio poco: «Giornata 8»; VoiceOver legge anche il numero di Serie A (#299)
                    Text(nome.corto).font(.subheadline.weight(.semibold))
                        .accessibilityLabel(nome.voce)
                    if Quando.contoAllaRovescia(fino: inizio, adesso: ora) != nil {
                        TestoConto(inizio: inizio, adesso: ora)
                            .font(.subheadline).foregroundStyle(Color.testoSecondario)
                    } else {
                        Text("in corso").font(.subheadline).foregroundStyle(Color.testoSecondario)
                    }
                }
                .lineLimit(1)
                .accessibilityElement(children: .combine)
            }
        } else {
            Text("SchieraXI").font(.subheadline.weight(.semibold))
                .accessibilityLabel("Schiera undici")
        }
    }
}
