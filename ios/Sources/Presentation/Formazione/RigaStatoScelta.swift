import SwiftUI

/// La riga dello stato sotto il campo, come `rigaStato` di `mostraFormazione` della web (#616, #673): il segno (simbolo e colore), la
/// frase dello stato e, quando in campo c'è una tua scelta, «Torna alla consigliata». Con la scelta non letta la frase dell'errore e
/// «Riprova». Mentre una scrittura è in volo, sotto «Sto ancora ricalcolando: un attimo».
struct RigaStatoScelta: View {
    let stato: StatoScelta
    /// I comandi che scrivono sono spenti (copia del telefono, scrittura in volo): «Torna alla consigliata» resta al suo posto, spento.
    var spento = false
    /// Una scrittura è in volo.
    var occupato = false
    let tornaAllaConsigliata: () -> Void
    let riprova: () -> Void

    var body: some View {
        if stato != .nessuno {
            let colore = Self.colore(stato.tono)
            VStack(alignment: .leading, spacing: 6) {
                frase(colore)
                if stato.conTorna {
                    Button(action: tornaAllaConsigliata) {
                        Label(Catalogo.Formazione.tornaAllaConsigliata, systemImage: "arrow.uturn.backward")
                            .font(.subheadline.weight(.semibold))
                            .frame(minHeight: Tema.areaTocco, alignment: .leading)
                            .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                    .foregroundStyle(Color.verde)
                    .disabled(spento)
                    .accessibilityHint(stato == .nonValida ? "Toglie la formazione salvata che non vale più"
                                                           : "Toglie la tua formazione e rimette la consigliata")
                }
                if stato == .nonLetta {
                    Button(Catalogo.Comune.riprova, action: riprova)
                        .font(.subheadline.weight(.semibold))
                        .buttonStyle(.bordered)
                        .frame(minHeight: Tema.areaTocco)
                }
                if occupato {
                    Label {
                        Text(Catalogo.Formazione.stoAncoraRicalcolando).font(.footnote).foregroundStyle(Color.testoSecondario)
                    } icon: {
                        ProgressView().controlSize(.mini)
                    }
                    .accessibilityElement(children: .combine)
                }
            }
            .padding(.horizontal, 10).padding(.vertical, 8)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(colore.opacity(0.12), in: RoundedRectangle(cornerRadius: 12, style: .continuous))
            .animation(Tema.morbida, value: stato)
        }
    }

    /// Il colore del segno: rosso per la scelta che non si legge o non vale più, arancio per la consigliata cambiata, grigio il resto.
    /// Sempre con il simbolo e la frase, mai il colore da solo.
    static func colore(_ tono: StatoScelta.Tono) -> Color {
        switch tono {
        case .attenzione: return .attenzione
        case .malus: return .malus
        case .neutro: return .testoSecondario
        }
    }

    private func frase(_ colore: Color) -> some View {
        Label {
            Text(stato.frase).font(.subheadline).foregroundStyle(.primary)
                .fixedSize(horizontal: false, vertical: true)
        } icon: {
            Image(systemName: stato.simbolo).foregroundStyle(colore).accessibilityHidden(true)
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(stato.voce)
    }
}

#Preview("Riga dello stato") {
    let stati: [StatoScelta] = [.consigliata, .cambiata(diversi: 2, punti: -0.4), .superata(diversi: 1, punti: 0.6), .nonValida,
                                .nonLetta, .chiusa(.tua), .chiusa(.nonValida)]
    ScrollView {
        VStack(spacing: 12) {
            ForEach(stati.indices, id: \.self) { i in
                RigaStatoScelta(stato: stati[i], occupato: i == 1, tornaAllaConsigliata: {}, riprova: {})
            }
        }
        .padding()
    }
}
