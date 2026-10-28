import SwiftUI

struct FormazioneView: View {
    @StateObject private var caricatore = Caricatore<Formazione>("/api/formazione")
    @State private var testo: String?
    @State private var rischio = 0
    @State private var moduloScelto: String?

    private let ruoli = ["P", "D", "C", "A"]
    private let nomiRuolo = ["P": "Portiere", "D": "Difensori", "C": "Centrocampisti", "A": "Attaccanti"]

    var body: some View {
        NavigationStack {
            ZStack {
                Sfondo()
                ScrollView {
                    VStack(spacing: 14) {
                        if let f = caricatore.dato {
                            scelta(f)
                            let (titolari, panchina, modulo, punti) = vista(f)
                            riepilogo(f, modulo: modulo, punti: punti)
                            ForEach(ruoli, id: \.self) { r in
                                let gruppo = titolari.filter { $0.ruolo == r }
                                if !gruppo.isEmpty {
                                    Carta(nomiRuolo[r]) { ForEach(gruppo) { RigaGiocatore(g: $0) } }
                                }
                            }
                            Carta("Panchina") { ForEach(panchina) { RigaGiocatore(g: $0) } }
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

    /// Titolari, panchina, modulo e punteggio secondo lo stile e il modulo scelti (se il server non li manda: la formazione consigliata).
    private func vista(_ f: Formazione) -> ([Giocatore], [Giocatore], String, Double) {
        guard let livelli = f.livelli, let schede = f.schede,
              let livello = livelli.first(where: { $0.rischio == rischio }) ?? livelli.first,
              let opzione = livello.moduli.first(where: { $0.modulo == (moduloScelto ?? livello.modulo) }) ?? livello.moduli.first
        else { return (f.titolari, f.panchina, f.modulo, f.punteggioAtteso) }
        let titolari = opzione.titolari.compactMap { schede[String($0)] }
        let panchina = opzione.panchina.compactMap { schede[String($0)] }
        if titolari.isEmpty { return (f.titolari, f.panchina, f.modulo, f.punteggioAtteso) }
        return (titolari, panchina, opzione.modulo, opzione.punteggioAtteso)
    }

    /// Stile (da molto sicura a molto rischiosa) e modulo.
    @ViewBuilder
    private func scelta(_ f: Formazione) -> some View {
        if let livelli = f.livelli, !livelli.isEmpty {
            let livello = livelli.first(where: { $0.rischio == rischio }) ?? livelli[0]
            Carta("Stile") {
                Picker("Stile", selection: $rischio) {
                    ForEach(livelli) { Text($0.nome).tag($0.rischio) }
                }
                .pickerStyle(.menu)
                .onChange(of: rischio) { _ in
                    moduloScelto = nil
                    UISelectionFeedbackGenerator().selectionChanged()
                }
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(livello.moduli) { m in
                            let attivo = (moduloScelto ?? livello.modulo) == m.modulo
                            Button {
                                moduloScelto = m.modulo
                                UISelectionFeedbackGenerator().selectionChanged()
                            } label: {
                                VStack(spacing: 2) {
                                    Text(m.modulo).font(.subheadline.bold())
                                    Text(m.punteggioAtteso.formatted(.number.precision(.fractionLength(1)))).font(.caption2).monospacedDigit()
                                }
                                .padding(.horizontal, 12).padding(.vertical, 6)
                                .background(attivo ? Color.verde.opacity(0.35) : Color.white.opacity(0.08), in: Capsule())
                                .overlay(Capsule().strokeBorder(attivo ? Color.verde : .clear, lineWidth: 1))
                            }
                            .buttonStyle(.plain)
                        }
                    }
                }
            }
        }
    }

    private func riepilogo(_ f: Formazione, modulo: String, punti: Double) -> some View {
        Carta("Giornata \(f.giornata)") {
            HStack(alignment: .firstTextBaseline) {
                Text(modulo).font(.system(size: 34, weight: .bold, design: .rounded))
                Spacer()
                VStack(alignment: .trailing) {
                    Text(punti.formatted(.number.precision(.fractionLength(1)))).font(.title2.bold()).monospacedDigit()
                    Text("punti attesi").font(.caption).foregroundStyle(.secondary)
                }
            }
            if f.conProbabili == false {
                Label("Probabili formazioni non ancora uscite", systemImage: "clock").font(.footnote).foregroundStyle(.secondary)
            }
        }
    }
}
