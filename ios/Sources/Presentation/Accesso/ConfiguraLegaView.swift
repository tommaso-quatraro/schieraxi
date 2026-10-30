import SwiftUI

private struct ApriImportazioneChiave: EnvironmentKey {
    static let defaultValue: () -> Void = {}
}

extension EnvironmentValues {
    /// Apre Lega > Aggiorna le rose (l'importazione delle rose da Excel o dal testo incollato).
    var apriImportazione: () -> Void {
        get { self[ApriImportazioneChiave.self] }
        set { self[ApriImportazioneChiave.self] = newValue }
    }
}

extension String {
    /// Il server dice che la lega non ha ancora le rose («Nessuna rosa importata», errore 409): serve la configurazione iniziale.
    var dicePerNessunaRosa: Bool { localizedCaseInsensitiveContains("rosa importata") }
}

/// Dopo l'accesso, una lega nuova non ha rose: la schermata spiega cosa fare. L'importazione delle rose c'è anche nell'app
/// (Lega > Aggiorna le rose); per il resto della configurazione (regole, nome della squadra) si usa la web app dal browser.
struct ConfiguraLegaVista: View {
    @Environment(\.apriImportazione) private var apriImportazione
    @Environment(\.openURL) private var apriLink

    var body: some View {
        ContentUnavailableView {
            VStack(spacing: 10) {
                Marchio(lato: 64).accessibilityHidden(true)
                Text("Manca la tua squadra").font(.title2.bold()).multilineTextAlignment(.center)
            }
            .accessibilityElement(children: .combine)
        } description: {
            Text("Mister, qui non ci sono ancora le rose. Importa il file della tua lega: poi SchieraXI sa chi schierare. Regole e nome della squadra si sistemano dalla web app, nel browser.")
        } actions: {
            Button {
                apriImportazione()
            } label: {
                Label("Importa le rose", systemImage: "square.and.arrow.down").frame(minHeight: Tema.areaTocco)
            }
            .pulsanteVetro(prominente: true)
            Button {
                if let url = URL(string: IndirizzoServer.attuale) { apriLink(url) }
            } label: {
                Label("Apri la web app nel browser", systemImage: "safari").frame(minHeight: Tema.areaTocco)
            }
            .pulsanteVetro()
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 24)
    }
}
