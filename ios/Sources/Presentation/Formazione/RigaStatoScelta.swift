import SwiftUI

/// La riga di stato della tua scelta in Formazione, come `rigaStatoScelta` di `fanta/web/app.js`: il segno (simbolo e colore),
/// la frase della web e i pulsanti di quello stato (`StatoScelta.pulsanti`, #463): «Salva questa», «Salva le modifiche» o «Salva
/// come mia scelta», «Annulla modifiche», «Torna alla consigliata». «Modifica a mano» sta accanto alla frase dello stile.
struct RigaStatoScelta: View {
    let stato: StatoScelta
    /// Un salvataggio è in corso: i pulsanti che salvano e «Annulla modifiche» sono spenti (niente doppio salvataggio).
    let salvando: Bool
    /// Salva come tua scelta gli undici sullo schermo («Salva questa», «Salva le modifiche», «Salva come mia scelta»).
    let salva: () -> Void
    let annulla: () -> Void
    let tornaAllaConsigliata: () -> Void

    /// Le parole dei pulsanti, quelle di `testi.js` (`formazione.salva_questa`, `formazione.annulla_modifiche`,
    /// `formazione.torna_alla_consigliata`): la prova è `ModificaAManoModuliTests`.
    static let testoSalvaQuesta = "Salva questa"
    static let testoAnnulla = "Annulla modifiche"
    static let testoTorna = "Torna alla consigliata"

    private static let suggerimentoSalva = "Salva come tua scelta per questa giornata la formazione che stai guardando"

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
                if !stato.pulsanti.isEmpty {
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

    /// I pulsanti dello stato, nell'ordine della web. Il salvataggio è verde; ⌘S salva le modifiche (come Ctrl+S sulla web).
    private var pulsanti: some View {
        ForEach(stato.pulsanti, id: \.self) { pulsante in
            switch pulsante {
            case .salvaQuesta:
                PulsanteRigaStato(testo: Self.testoSalvaQuesta, simbolo: "tray.and.arrow.down", colore: .verde, azione: salva)
                    .disabled(salvando)
                    .accessibilityHint(Self.suggerimentoSalva)
            case .salva:
                PulsanteRigaStato(testo: FormazioneView.etichettaSalva(stato), simbolo: "tray.and.arrow.down", colore: .verde, azione: salva)
                    .keyboardShortcut("s", modifiers: .command)
                    .disabled(salvando)
                    .accessibilityHint(Self.suggerimentoSalva)
            case .annulla:
                PulsanteRigaStato(testo: Self.testoAnnulla, simbolo: "arrow.counterclockwise", colore: .primary, azione: annulla)
                    .disabled(salvando)
                    .accessibilityHint("Rimette la formazione che hai salvato")
            case .torna:
                PulsanteRigaStato(testo: Self.testoTorna, simbolo: "arrow.uturn.backward", colore: .primary, azione: tornaAllaConsigliata)
                    .accessibilityHint(suggerimentoTorna)
            }
        }
    }

    private var suggerimentoTorna: String {
        switch stato {
        case .nonValida: return "Toglie la formazione salvata che non vale più e mostra la consigliata"
        case .salvata, .modificata: return "Toglie la formazione che hai salvato e rimette la consigliata"
        default: return "Rimette lo stile e il modulo consigliati"
        }
    }
}

#Preview("Riga di stato") {
    let stati: [StatoScelta] = [.consigliata, .altra, .salvata(Date()), .modificata(Date()), .bozza, .nonValida, .chiusa(tua: true), .chiusaNonValida]
    VStack(spacing: 12) {
        ForEach(stati.indices, id: \.self) { i in
            RigaStatoScelta(stato: stati[i], salvando: false, salva: {}, annulla: {}, tornaAllaConsigliata: {})
        }
    }
    .padding()
}
