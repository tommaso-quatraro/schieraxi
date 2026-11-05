import SwiftUI

/// La riga di stato della tua scelta in Formazione, come `rigaStatoScelta` di `fanta/web/app.js`: il segno (simbolo e colore),
/// la frase della web e, dove la web li mette nella riga, «Salva questa» e «Torna alla consigliata». Gli altri pulsanti
/// (salva le modifiche, annulla) stanno sotto, con la modifica a mano.
struct RigaStatoScelta: View {
    let stato: StatoScelta
    let salvaQuesta: () -> Void
    let tornaAllaConsigliata: () -> Void

    var body: some View {
        let colore = Self.colore(stato.tono)
        ViewThatFits(in: .horizontal) {
            HStack(alignment: .center, spacing: 8) {
                frase(colore)
                Spacer(minLength: 4)
                pulsanti
            }
            VStack(alignment: .leading, spacing: 4) {
                frase(colore)
                // con il testo grande i pulsanti vanno uno sotto l'altro invece di uscire dallo schermo
                if stato.conSalvaQuesta || stato.conTornaNellaRiga {
                    ViewThatFits(in: .horizontal) {
                        HStack(spacing: 12) { pulsanti }
                        VStack(alignment: .leading, spacing: 0) { pulsanti }
                    }
                }
            }
        }
        .padding(.horizontal, 10).padding(.vertical, 6)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(colore.opacity(0.12), in: RoundedRectangle(cornerRadius: 12))
        .animation(Tema.morbida, value: stato)
    }

    /// Il colore del segno (verde salvata, arancio modifiche, rosso non valida, grigio il resto): sempre con simbolo e frase.
    static func colore(_ tono: StatoScelta.Tono) -> Color {
        switch tono {
        case .bene: return .verde
        case .attenzione: return .attenzione
        case .malus: return .malus
        case .neutro: return .testoSecondario
        }
    }

    private func frase(_ colore: Color) -> some View {
        Label {
            Text(stato.titolo()).font(.footnote.weight(.semibold)).foregroundStyle(.primary)
                .fixedSize(horizontal: false, vertical: true)
        } icon: {
            Image(systemName: stato.simbolo).foregroundStyle(colore).accessibilityHidden(true)
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(stato.voce())
    }

    @ViewBuilder
    private var pulsanti: some View {
        if stato.conSalvaQuesta {
            Button(action: salvaQuesta) {
                Label("Salva questa", systemImage: "tray.and.arrow.down").font(.footnote.weight(.semibold))
                    .fixedSize(horizontal: false, vertical: true).frame(minHeight: 44).contentShape(Rectangle())
            }
            .buttonStyle(StilePressione())
            .foregroundStyle(Color.verde)
            .accessibilityHint("Salva come tua scelta per questa giornata la formazione che stai guardando")
        }
        if stato.conTornaNellaRiga {
            Button(action: tornaAllaConsigliata) {
                Label("Torna alla consigliata", systemImage: "arrow.uturn.backward").font(.footnote.weight(.semibold))
                    .fixedSize(horizontal: false, vertical: true).frame(minHeight: 44).contentShape(Rectangle())
            }
            .buttonStyle(StilePressione())
            .foregroundStyle(.primary)
            .accessibilityHint(stato == .nonValida ? "Toglie la formazione salvata che non vale più e mostra la consigliata"
                                                   : "Rimette lo stile e il modulo consigliati")
        }
    }
}

#Preview("Riga di stato") {
    let stati: [StatoScelta] = [.consigliata, .altra, .salvata(Date()), .modificata(Date()), .bozza, .nonValida, .chiusa(tua: true), .chiusaNonValida]
    VStack(spacing: 12) {
        ForEach(stati.indices, id: \.self) { i in
            RigaStatoScelta(stato: stati[i], salvaQuesta: {}, tornaAllaConsigliata: {})
        }
    }
    .padding()
}
