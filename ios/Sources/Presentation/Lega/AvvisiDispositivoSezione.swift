import SwiftUI

/// La sezione Avvisi delle Impostazioni, come `avvisiTelefono` della web (#673 passo 3): «Avvisi su questo dispositivo» con la sua
/// riga d'aiuto (i due avvisi che arrivano) e «Ore tranquille» con la fascia scelta. Gli altri interruttori di prima non ci sono più:
/// restano sul server come sono. Logica in `AvvisiDispositivoViewModel`.
struct AvvisiDispositivoSezione: View {
    @ObservedObject var vm: AvvisiDispositivoViewModel

    /// Il server ha spento le ore tranquille (inizio e fine alla stessa ora): la frase della web (`avv.avevi_scelto_ore`).
    static let testoOreTranquilleSpente = Catalogo.Avv.aveviSceltoOre

    var body: some View {
        Section(titolo: Catalogo.Imp.sezAvvisi) {
            if vm.oreTranquilleSpente {
                avviso(Self.testoOreTranquilleSpente)
            }
            Toggle(isOn: Binding(get: { vm.qui }, set: { nuovo in Task { await vm.cambiaQui(nuovo) } })) {
                NomeConAiuto(Catalogo.Imp.avvisiQui, aiuto: Catalogo.Imp.avvisiQuiAiuto)
            }
            .tint(Color.verde)
            .frame(minHeight: Tema.areaTocco)
            .disabled(vm.inCorso)
            .id(ParteImpostazioni.avvisi.ancora)
            if let messaggio = vm.messaggio {
                Text(messaggio)
                    .font(.footnote)
                    .foregroundStyle(Color.testoSecondario)
                    .fixedSize(horizontal: false, vertical: true)
                    .onAppear { AccessibilityNotification.Announcement(messaggio).post() }
            }
            if vm.caricatore.dato != nil {
                Toggle(isOn: Binding(get: { vm.oreTranquille.attive }, set: { nuovo in Task { await vm.cambiaOreTranquille(nuovo) } })) {
                    NomeConAiuto(Catalogo.Avv.oreTranq, aiuto: AvvisiDispositivoViewModel.aiutoOreTranquille(vm.oreTranquille))
                }
                .tint(Color.verde)
                .frame(minHeight: Tema.areaTocco)
                .disabled(vm.inCorso)
            } else if let errore = vm.caricatore.errore {
                avviso(errore)
            } else {
                ProgressView().frame(maxWidth: .infinity, minHeight: Tema.areaTocco)
            }
            if let errore = vm.erroreSalvataggio {
                avviso(errore)
                    .onAppear { AccessibilityNotification.Announcement(errore).post() }
            }
        }
        // la lettura la lancia la pagina (`ImpostazioniView`): un modificatore su una Section finirebbe su ogni sua riga
    }

    /// Un avviso con il triangolo e il colore d'attenzione, che va a capo.
    private func avviso(_ testo: String) -> some View {
        Label(testo, systemImage: "exclamationmark.triangle.fill")
            .font(.footnote)
            .foregroundStyle(Color.attenzione)
            .fixedSize(horizontal: false, vertical: true)
    }
}
