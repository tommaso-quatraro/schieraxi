import SwiftUI

struct FormazioneView: View {
    @StateObject private var caricatore = Caricatore<Formazione>("/api/formazione")
    @State private var testo: String?
    @State private var rischio = 0
    @State private var moduloScelto: String?
    // modifica a mano
    @State private var manuale: [Int]?
    @State private var valutazione: ValutazioneManuale?
    @State private var scelta: SceltaSalvata?
    @State private var daSostituire: Giocatore?
    @State private var messaggio: String?

    private let ruoli = ["P", "D", "C", "A"]
    private let nomiRuolo = ["P": "Portiere", "D": "Difensori", "C": "Centrocampisti", "A": "Attaccanti"]

    var body: some View {
        NavigationStack {
            ZStack {
                Sfondo()
                ScrollView {
                    VStack(spacing: 14) {
                        if let f = caricatore.dato {
                            if manuale == nil { sceltaStile(f) }
                            let (titolari, panchina, modulo, punti) = vista(f)
                            riepilogo(f, modulo: modulo, punti: punti)
                            barraManuale(f)
                            ForEach(ruoli, id: \.self) { r in
                                let gruppo = titolari.filter { $0.ruolo == r }
                                if !gruppo.isEmpty {
                                    Carta(nomiRuolo[r]) {
                                        ForEach(gruppo) { g in
                                            if manuale != nil {
                                                Button { daSostituire = g } label: {
                                                    HStack { RigaGiocatore(g: g); Image(systemName: "arrow.left.arrow.right").foregroundStyle(Color.verde) }
                                                }.buttonStyle(.plain)
                                            } else {
                                                RigaGiocatore(g: g)
                                            }
                                        }
                                    }
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
            .sheet(item: $daSostituire) { g in
                if let f = caricatore.dato { SostituzioneSheet(uscente: g, formazione: f, titolari: manuale ?? []) { nuovo in cambia(g.id, con: nuovo) } }
            }
            .task {
                await caricatore.ricarica()
                await caricaTesto()
                if let f = caricatore.dato { await caricaScelta(f) }
            }
        }
    }

    private func caricaTesto() async {
        testo = try? await Api.testo("/api/formazione/testo")
    }

    /// Se avevi salvato una scelta a mano per questa giornata, riparte da lì.
    private func caricaScelta(_ f: Formazione) async {
        let s: SceltaSalvata? = try? await Api.get("/api/scelta?giornata=\(f.giornata)")
        scelta = s
        if let s, manuale == nil, s.titolari.count == 11 {
            manuale = s.titolari
            await valuta(salva: false)
        }
    }

    /// Titolari, panchina, modulo e punteggio secondo la modalità (a mano, o stile e modulo scelti).
    private func vista(_ f: Formazione) -> ([Giocatore], [Giocatore], String, Double) {
        if let manuale, let schede = f.schede {
            let titolari = manuale.compactMap { schede[String($0)] }
            let ids = valutazione?.panchina ?? f.panchina.map(\.id).filter { !manuale.contains($0) }
            return (titolari, ids.compactMap { schede[String($0)] }, valutazione?.modulo ?? f.modulo, valutazione?.punteggioAtteso ?? f.punteggioAtteso)
        }
        guard let livelli = f.livelli, let schede = f.schede,
              let livello = livelli.first(where: { $0.rischio == rischio }) ?? livelli.first,
              let opzione = livello.moduli.first(where: { $0.modulo == (moduloScelto ?? livello.modulo) }) ?? livello.moduli.first
        else { return (f.titolari, f.panchina, f.modulo, f.punteggioAtteso) }
        let titolari = opzione.titolari.compactMap { schede[String($0)] }
        let panchina = opzione.panchina.compactMap { schede[String($0)] }
        if titolari.isEmpty { return (f.titolari, f.panchina, f.modulo, f.punteggioAtteso) }
        return (titolari, panchina, opzione.modulo, opzione.punteggioAtteso)
    }

    private func cambia(_ vecchio: Int, con nuovo: Int) {
        guard var m = manuale, let i = m.firstIndex(of: vecchio) else { return }
        m[i] = nuovo
        manuale = m
        daSostituire = nil
        UISelectionFeedbackGenerator().selectionChanged()
        Task { await valuta(salva: false) }
    }

    private func valuta(salva: Bool) async {
        guard let m = manuale else { return }
        do {
            let v: ValutazioneManuale = try await Api.posta("POST", "/api/formazione/valuta", RichiestaValutazione(titolari: m, salva: salva))
            valutazione = v
            messaggio = nil
            if salva {
                messaggio = "Salvata come la tua scelta per questa giornata."
                UINotificationFeedbackGenerator().notificationOccurred(.success)
            }
        } catch {
            messaggio = error.localizedDescription
            UINotificationFeedbackGenerator().notificationOccurred(.error)
        }
    }

    private func tornaAllaConsigliata(_ f: Formazione) async {
        try? await Api.invia("DELETE", "/api/scelta?giornata=\(f.giornata)")
        manuale = nil
        valutazione = nil
        scelta = nil
        messaggio = nil
    }

    @ViewBuilder
    private func barraManuale(_ f: Formazione) -> some View {
        Carta {
            if manuale == nil {
                Button {
                    let (titolari, _, _, _) = vista(f)
                    manuale = titolari.map(\.id)
                    Task { await valuta(salva: false) }
                } label: { Label("Modifica a mano", systemImage: "hand.tap") }
            } else {
                Text("Tocca un titolare per sostituirlo con un altro della rosa: i punti attesi si ricalcolano.").font(.footnote).foregroundStyle(.secondary)
                if let v = valutazione, let d = v.differenza {
                    Text("Rispetto alla consigliata con lo stesso modulo: " + (d >= 0 ? "+" : "") + d.formatted(.number.precision(.fractionLength(1))))
                        .font(.subheadline).foregroundStyle(d >= 0 ? Color.verde : .orange)
                }
                HStack {
                    Button { Task { await valuta(salva: true) } } label: { Label("Salva come mia scelta", systemImage: "tray.and.arrow.down") }
                    Spacer()
                    Button(role: .destructive) { Task { await tornaAllaConsigliata(f) } } label: { Text("Torna alla consigliata") }
                }
                .font(.subheadline)
            }
            if let messaggio { Text(messaggio).font(.footnote).foregroundStyle(.secondary) }
        }
    }

    /// Stile (da molto sicura a molto rischiosa) e modulo.
    @ViewBuilder
    private func sceltaStile(_ f: Formazione) -> some View {
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

/// Scelta del sostituto: giocatori della stessa categoria che non sono già titolari.
struct SostituzioneSheet: View {
    let uscente: Giocatore
    let formazione: Formazione
    let titolari: [Int]
    let scelto: (Int) -> Void
    @Environment(\.dismiss) private var chiudi

    private var candidati: [Giocatore] {
        (formazione.schede ?? [:]).values
            .filter { $0.ruolo == uscente.ruolo && !titolari.contains($0.id) }
            .sorted { ($0.puntiAttesi ?? 0) > ($1.puntiAttesi ?? 0) }
    }

    var body: some View {
        NavigationStack {
            List {
                Section("Al posto di \(uscente.nome)") {
                    ForEach(candidati) { g in
                        Button { scelto(g.id) } label: { RigaGiocatore(g: g) }.buttonStyle(.plain)
                    }
                    if candidati.isEmpty { Text("Nessun altro giocatore di questo ruolo in rosa.").foregroundStyle(.secondary) }
                }
            }
            .navigationTitle("Sostituisci")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .navigationBarTrailing) { Button("Annulla") { chiudi() } } }
        }
    }
}
