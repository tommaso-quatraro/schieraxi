import SwiftUI

/// Stato della schermata Formazione (stile, modulo, modifica a mano). Sta fuori dalla vista, nell'app, così
/// cambiando sezione nella barra laterale dell'iPad (la vista viene ricreata) non si perde la modifica a mano.
@MainActor
final class StatoFormazione: ObservableObject {
    @Published var rischio = 0
    @Published var moduloScelto: String?
    @Published var manuale: [Int]?
    @Published var valutazione: ValutazioneManuale?
    @Published var messaggio: String?
    /// Giornata a cui si riferisce la modifica a mano: se cambia, si riparte da zero.
    var giornata: Int?
    /// Numera le valutazioni inviate: una risposta arrivata in ritardo (fuori ordine) viene ignorata.
    var contatore = 0

    func azzeraManuale() {
        manuale = nil
        valutazione = nil
        messaggio = nil
        contatore += 1
    }
}

struct FormazioneView: View {
    @StateObject private var caricatore = Caricatore<Formazione>("/api/formazione")
    @EnvironmentObject private var s: StatoFormazione
    @State private var testo: String?
    @State private var daSostituire: Giocatore?

    private let ruoli = ["P", "D", "C", "A"]
    private let nomiRuolo = ["P": "Portiere", "D": "Difensori", "C": "Centrocampisti", "A": "Attaccanti"]

    var body: some View {
        NavigationStack {
            ZStack {
                Sfondo()
                ScrollView {
                    Colonne(spazio: 14) {
                        if let f = caricatore.dato {
                            if s.manuale == nil { sceltaStile(f) }
                            let (titolari, panchina, modulo, punti) = vista(f)
                            riepilogo(f, modulo: modulo, punti: punti)
                            barraManuale(f)
                            ForEach(ruoli, id: \.self) { r in
                                let gruppo = titolari.filter { $0.ruolo == r }
                                if !gruppo.isEmpty {
                                    Carta(nomiRuolo[r]) {
                                        ForEach(gruppo) { g in
                                            if s.manuale != nil {
                                                Button { daSostituire = g } label: {
                                                    HStack { RigaGiocatore(g: g); Image(systemName: "arrow.left.arrow.right").foregroundStyle(Color.verde).accessibilityHidden(true) }
                                                        .frame(minHeight: 44)
                                                }
                                                .buttonStyle(.plain)
                                                .accessibilityHint("Apre la scelta del giocatore che prende il suo posto")
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
                .avvisoDatiSalvati(caricatore.datiSalvati)
            }
            .navigationTitle("Formazione")
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    if let testo {
                        ShareLink(item: testo) { Image(systemName: "square.and.arrow.up") }
                            .accessibilityLabel("Condividi la formazione")
                    }
                }
            }
            .sheet(item: $daSostituire) { g in
                if let f = caricatore.dato { SostituzioneSheet(uscente: g, formazione: f, titolari: s.manuale ?? []) { nuovo in cambia(g.id, con: nuovo) } }
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
        // Un'altra giornata: la modifica a mano della vecchia non vale più.
        if s.giornata != f.giornata {
            s.azzeraManuale()
            s.giornata = f.giornata
        }
        guard s.manuale == nil else { return }   // c'è già una modifica in corso: non si sovrascrive
        let salvata: SceltaSalvata? = try? await Api.get("/api/scelta?giornata=\(f.giornata)")
        if let salvata, s.manuale == nil, salvata.titolari.count == 11 {
            s.manuale = salvata.titolari
            await valuta(salva: false)
        }
    }

    /// Titolari, panchina, modulo e punteggio secondo la modalità (a mano, o stile e modulo scelti).
    private func vista(_ f: Formazione) -> ([Giocatore], [Giocatore], String, Double) {
        if let manuale = s.manuale, let schede = f.schede {
            let titolari = manuale.compactMap { schede[String($0)] }
            let ids = s.valutazione?.panchina ?? f.panchina.map(\.id).filter { !manuale.contains($0) }
            return (titolari, ids.compactMap { schede[String($0)] }, s.valutazione?.modulo ?? f.modulo, s.valutazione?.punteggioAtteso ?? f.punteggioAtteso)
        }
        guard let livelli = f.livelli, let schede = f.schede,
              let livello = livelli.first(where: { $0.rischio == s.rischio }) ?? livelli.first,
              let opzione = livello.moduli.first(where: { $0.modulo == (s.moduloScelto ?? livello.modulo) }) ?? livello.moduli.first
        else { return (f.titolari, f.panchina, f.modulo, f.punteggioAtteso) }
        let titolari = opzione.titolari.compactMap { schede[String($0)] }
        let panchina = opzione.panchina.compactMap { schede[String($0)] }
        if titolari.isEmpty { return (f.titolari, f.panchina, f.modulo, f.punteggioAtteso) }
        return (titolari, panchina, opzione.modulo, opzione.punteggioAtteso)
    }

    private func cambia(_ vecchio: Int, con nuovo: Int) {
        guard var m = s.manuale, let i = m.firstIndex(of: vecchio) else { return }
        m[i] = nuovo
        s.manuale = m
        daSostituire = nil
        UISelectionFeedbackGenerator().selectionChanged()
        Task { await valuta(salva: false) }
    }

    /// Chiede al server i punti della formazione scelta a mano (e, se `salva`, la salva).
    /// Se nel frattempo la scelta è cambiata, la risposta (arrivata in ritardo) viene ignorata.
    private func valuta(salva: Bool) async {
        guard let m = s.manuale else { return }
        s.contatore += 1
        let numero = s.contatore
        do {
            let v: ValutazioneManuale = try await Api.posta("POST", "/api/formazione/valuta", RichiestaValutazione(titolari: m, salva: salva))
            guard numero == s.contatore, s.manuale == m else { return }
            s.valutazione = v
            s.messaggio = nil
            if salva {
                s.messaggio = "Salvata come la tua scelta per questa giornata."
                UINotificationFeedbackGenerator().notificationOccurred(.success)
            }
        } catch {
            if Task.isCancelled || error is CancellationError { return }
            guard numero == s.contatore, s.manuale == m else { return }
            s.messaggio = error.localizedDescription
            UINotificationFeedbackGenerator().notificationOccurred(.error)
        }
    }

    private func tornaAllaConsigliata(_ f: Formazione) async {
        do {
            try await Api.invia("DELETE", "/api/scelta?giornata=\(f.giornata)")
            s.azzeraManuale()
        } catch {
            // Se il server non cancella la scelta salvata, resta com'è e lo si dice.
            s.messaggio = error.localizedDescription
            UINotificationFeedbackGenerator().notificationOccurred(.error)
        }
    }

    @ViewBuilder
    private func barraManuale(_ f: Formazione) -> some View {
        Carta {
            if s.manuale == nil {
                Button {
                    let (titolari, _, _, _) = vista(f)
                    s.manuale = titolari.map(\.id)
                    Task { await valuta(salva: false) }
                } label: { Label("Modifica a mano", systemImage: "hand.tap").frame(minHeight: 44) }
            } else {
                Text("Tocca un titolare per sostituirlo con un altro della rosa: i punti attesi si ricalcolano.").font(.footnote).foregroundStyle(.secondary)
                if let v = s.valutazione, let d = v.differenza {
                    Text("Rispetto alla consigliata con lo stesso modulo: " + (d >= 0 ? "+" : "") + d.formatted(.number.precision(.fractionLength(1))))
                        .font(.subheadline).foregroundStyle(d >= 0 ? Color.verde : .orange)
                }
                HStack {
                    Button { Task { await valuta(salva: true) } } label: { Label("Salva come mia scelta", systemImage: "tray.and.arrow.down").frame(minHeight: 44) }
                        .keyboardShortcut("s", modifiers: .command)
                    Spacer()
                    Button(role: .destructive) { Task { await tornaAllaConsigliata(f) } } label: { Text("Torna alla consigliata").frame(minHeight: 44) }
                }
                .font(.subheadline)
            }
            if let messaggio = s.messaggio { Text(messaggio).font(.footnote).foregroundStyle(.secondary) }
        }
    }

    /// Stile (da molto sicura a molto rischiosa) e modulo.
    @ViewBuilder
    private func sceltaStile(_ f: Formazione) -> some View {
        if let livelli = f.livelli, !livelli.isEmpty {
            let livello = livelli.first(where: { $0.rischio == s.rischio }) ?? livelli[0]
            Carta("Stile") {
                Picker("Stile", selection: $s.rischio) {
                    ForEach(livelli) { Text($0.nome).tag($0.rischio) }
                }
                .pickerStyle(.menu)
                .onChange(of: s.rischio) { _ in
                    s.moduloScelto = nil
                    UISelectionFeedbackGenerator().selectionChanged()
                }
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(livello.moduli) { m in
                            let attivo = (s.moduloScelto ?? livello.modulo) == m.modulo
                            Button {
                                s.moduloScelto = m.modulo
                                UISelectionFeedbackGenerator().selectionChanged()
                            } label: {
                                VStack(spacing: 2) {
                                    Text(m.modulo).font(.subheadline.bold())
                                    Text(m.punteggioAtteso.formatted(.number.precision(.fractionLength(1)))).font(.caption2).monospacedDigit()
                                }
                                .padding(.horizontal, 12).padding(.vertical, 6)
                                .frame(minHeight: 44)
                                .background(attivo ? Color.verde.opacity(0.35) : Color.primary.opacity(0.08), in: Capsule())
                                .overlay(Capsule().strokeBorder(attivo ? Color.verde : .clear, lineWidth: 1))
                            }
                            .buttonStyle(.plain)
                            .accessibilityLabel("Modulo \(m.modulo), \(m.punteggioAtteso.formatted(.number.precision(.fractionLength(1)))) punti attesi")
                            .accessibilityAddTraits(attivo ? .isSelected : [])
                        }
                    }
                }
            }
        }
    }

    private func riepilogo(_ f: Formazione, modulo: String, punti: Double) -> some View {
        Carta("Giornata \(f.giornata)") {
            HStack(alignment: .firstTextBaseline) {
                Text(modulo).font(.system(.title, design: .rounded).weight(.bold))
                Spacer()
                VStack(alignment: .trailing) {
                    Text(punti.formatted(.number.precision(.fractionLength(1)))).font(.title2.bold()).monospacedDigit()
                    Text("punti attesi").font(.caption).foregroundStyle(.secondary)
                }
            }
            .accessibilityElement(children: .combine)
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
                        Button { scelto(g.id) } label: { RigaGiocatore(g: g).frame(minHeight: 44) }.buttonStyle(.plain)
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
