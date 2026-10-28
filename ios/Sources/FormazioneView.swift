import SwiftUI

struct FormazioneView: View {
    @StateObject private var caricatore = Caricatore<Formazione>("/api/formazione")
    @State private var testo: String?

    private let ruoli = ["P", "D", "C", "A"]
    private let nomiRuolo = ["P": "Portiere", "D": "Difensori", "C": "Centrocampisti", "A": "Attaccanti"]

    var body: some View {
        NavigationStack {
            ZStack {
                Sfondo()
                ScrollView {
                    VStack(spacing: 14) {
                        if let f = caricatore.dato {
                            riepilogo(f)
                            ForEach(ruoli, id: \.self) { r in
                                let gruppo = f.titolari.filter { $0.ruolo == r }
                                if !gruppo.isEmpty {
                                    Carta(nomiRuolo[r]) { ForEach(gruppo) { RigaGiocatore(g: $0) } }
                                }
                            }
                            Carta("Panchina") { ForEach(f.panchina) { RigaGiocatore(g: $0) } }
                        } else if let errore = caricatore.errore {
                            ErroreVista(messaggio: errore) { Task { await caricatore.ricarica() } }
                        } else {
                            ProgressView("Calcolo la formazione…").padding(40)
                        }
                    }
                    .padding(.horizontal, 16)
                    .padding(.bottom, 24)
                }
                .refreshable {
                    await caricatore.ricarica()
                    await caricaTesto()
                    UINotificationFeedbackGenerator().notificationOccurred(caricatore.errore == nil ? .success : .error)
                }
            }
            .navigationTitle("Formazione")
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    if let testo {
                        ShareLink(item: testo) { Image(systemName: "square.and.arrow.up") }
                    }
                }
            }
            .task {
                await caricatore.ricarica()
                await caricaTesto()
            }
        }
    }

    private func caricaTesto() async {
        testo = try? await Api.testo("/api/formazione/testo")
    }

    private func riepilogo(_ f: Formazione) -> some View {
        Carta("Giornata \(f.giornata)") {
            HStack(alignment: .firstTextBaseline) {
                Text(f.modulo).font(.system(size: 34, weight: .bold, design: .rounded))
                Spacer()
                VStack(alignment: .trailing) {
                    Text(f.punteggioAtteso.formatted(.number.precision(.fractionLength(1)))).font(.title2.bold()).monospacedDigit()
                    Text("punti attesi").font(.caption).foregroundStyle(.secondary)
                }
            }
            if f.conProbabili == false {
                Label("Probabili formazioni non ancora uscite", systemImage: "clock").font(.footnote).foregroundStyle(.secondary)
            }
        }
    }
}
