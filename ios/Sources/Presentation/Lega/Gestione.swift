import SwiftUI

// MARK: - Regole della lega (editor generico)

struct RegoleEditorView: View {
    @StateObject private var caricatore = Caricatore<JSONValue>("/api/regole", snake: false, cache: false)
    @State private var valore: JSONValue = .nullo
    @State private var caricato = false
    @State private var esito: String?
    @State private var inCorso = false

    var body: some View {
        ZStack {
            Sfondo()
            List {
                if caricato {
                    if case .oggetto = valore {
                        EditorJSON(valore: $valore, titolo: "Regole")
                    }
                    Section {
                        Button {
                            Task { await salva() }
                        } label: {
                            if inCorso { ProgressView() } else { Label("Salva le regole", systemImage: "checkmark.circle") }
                        }
                        .disabled(inCorso)
                        if let esito { Text(esito).font(.footnote) }
                    }
                } else if let e = caricatore.errore {
                    ErroreVista(messaggio: e) { Task { await carica() } }
                } else {
                    ProgressView().frame(maxWidth: .infinity)
                }
            }
            .scrollContentBackground(.hidden)
        }
        .navigationTitle("Regole")
        .task { await carica() }
    }

    private func carica() async {
        await caricatore.ricarica()
        if let d = caricatore.dato { valore = d; caricato = true }
    }

    private func salva() async {
        inCorso = true
        defer { inCorso = false }
        do {
            let nuove: JSONValue = try await Api.posta("PUT", "/api/regole", valore, snake: false)
            valore = nuove
            esito = "Regole salvate."
            UINotificationFeedbackGenerator().notificationOccurred(.success)
        } catch {
            esito = error.localizedDescription
            UINotificationFeedbackGenerator().notificationOccurred(.error)
        }
    }
}

/// Mostra e modifica un JSON a gruppi: numeri, interruttori e testi; le liste restano in sola lettura.
struct EditorJSON: View {
    @Binding var valore: JSONValue
    let titolo: String

    var body: some View {
        if case .oggetto(let d) = valore {
            ForEach(d.keys.sorted(), id: \.self) { chiave in
                voce(chiave, d[chiave] ?? .nullo)
            }
        }
    }

    private func figlio(_ chiave: String) -> Binding<JSONValue> {
        Binding(
            get: {
                if case .oggetto(let d) = valore { return d[chiave] ?? .nullo }
                return .nullo
            },
            set: { nuovo in
                if case .oggetto(var d) = valore {
                    d[chiave] = nuovo
                    valore = .oggetto(d)
                }
            })
    }

    @ViewBuilder
    private func voce(_ chiave: String, _ v: JSONValue) -> some View {
        switch v {
        case .oggetto:
            Section(nome(chiave)) { EditorJSON(valore: figlio(chiave), titolo: chiave) }
        case .booleano:
            Toggle(nome(chiave), isOn: Binding(
                get: { if case .booleano(let b) = figlio(chiave).wrappedValue { return b }; return false },
                set: { figlio(chiave).wrappedValue = .booleano($0) })).tint(Color.verde)
        case .intero, .decimale, .nullo:
            // Numeri (anche con la virgola) e valori non impostati (null): si scrive un numero, o si lascia vuoto.
            CampoNumero(titolo: nome(chiave), valore: figlio(chiave))
        case .testo:
            HStack {
                Text(nome(chiave))
                Spacer()
                TextField("", text: Binding(
                    get: { if case .testo(let t) = figlio(chiave).wrappedValue { return t }; return "" },
                    set: { figlio(chiave).wrappedValue = .testo($0) }))
                    .multilineTextAlignment(.trailing)
            }
        case .lista:
            HStack { Text(nome(chiave)); Spacer(); Text(v.descrizione).foregroundStyle(.secondary).lineLimit(1) }
        }
    }

    private func nome(_ chiave: String) -> String {
        chiave.replacingOccurrences(of: "_", with: " ").capitalized
    }
}

/// Campo di testo per un numero del JSON: «1.5» e «1,5» valgono uguale; intero se il testo è intero, decimale altrimenti;
/// vuoto = null (non impostato). Un testo che non è un numero lascia il valore com'era.
struct CampoNumero: View {
    let titolo: String
    @Binding var valore: JSONValue
    @State private var testo = ""

    /// Come si scrive il valore attuale (3.0 diventa «3»: così non cambia tipo senza che l'utente tocchi nulla).
    private func formato(_ v: JSONValue) -> String {
        switch v {
        case .intero(let n): return String(n)
        case .decimale(let d): return d == d.rounded() && abs(d) < 1e15 ? String(Int(d)) : String(d)
        default: return ""
        }
    }

    private func aggiorna(_ nuovo: String) {
        if nuovo == formato(valore) { return }
        let t = nuovo.trimmingCharacters(in: .whitespaces).replacingOccurrences(of: ",", with: ".")
        if t.isEmpty {
            valore = .nullo
        } else if let n = Int(t) {
            valore = .intero(n)
        } else if let d = Double(t), d.isFinite {
            valore = .decimale(d)
        }
    }

    var body: some View {
        HStack {
            Text(titolo)
            Spacer()
            TextField("non impostato", text: $testo)
                .keyboardType(.numbersAndPunctuation)
                .multilineTextAlignment(.trailing)
                .frame(minWidth: 90, maxWidth: 140, minHeight: 44)
                .onChange(of: testo) { aggiorna($0) }
        }
        .onAppear { testo = formato(valore) }
    }
}

// MARK: - Avvisi del server

struct AvvisiServerView: View {
    @StateObject private var caricatore = Caricatore<StatoAvvisi>("/api/avvisi", snake: false, cache: false)
    @State private var impostazioni: ImpostazioniAvvisi?
    @State private var messaggio: String?

    var body: some View {
        ZStack {
            Sfondo()
            List {
                if let s = caricatore.dato {
                    Section("Quali avvisi") {
                        interruttore("Cambi di formazione e probabili", \.cambi)
                        interruttore("Promemoria un'ora prima", \.promemoria_60)
                        interruttore("Promemoria 15 minuti prima", \.promemoria_15)
                        interruttore("Riepilogo a giornata finita", \.riepilogo)
                    }
                    Section {
                        Text("Dispositivi con avvisi web attivi: \(s.dispositivi ?? 0). Gli avvisi del server arrivano dalla web app installata dalla Home (l'app nativa gratuita non può riceverli).")
                            .font(.footnote).foregroundStyle(.secondary)
                        Button("Manda un avviso di prova") { Task { await prova() } }
                        if let messaggio { Text(messaggio).font(.footnote) }
                    }
                } else if let e = caricatore.errore {
                    ErroreVista(messaggio: e) { Task { await carica() } }
                } else {
                    ProgressView().frame(maxWidth: .infinity)
                }
            }
            .scrollContentBackground(.hidden)
        }
        .navigationTitle("Avvisi del server")
        .task { await carica() }
    }

    private func interruttore(_ titolo: String, _ chiave: WritableKeyPath<ImpostazioniAvvisi, Bool>) -> some View {
        Toggle(titolo, isOn: Binding(
            get: { impostazioni?[keyPath: chiave] ?? false },
            set: { nuovo in
                impostazioni?[keyPath: chiave] = nuovo
                Task { await salva() }
            })).tint(Color.verde)
    }

    private func carica() async {
        await caricatore.ricarica()
        impostazioni = caricatore.dato?.impostazioni
    }

    private func salva() async {
        guard let i = impostazioni else { return }
        do {
            let _: StatoAvvisi = try await Api.posta("PUT", "/api/avvisi", i, snake: false)
            messaggio = nil
        } catch {
            messaggio = error.localizedDescription
        }
    }

    private func prova() async {
        do {
            try await Api.invia("POST", "/api/avvisi/prova")
            messaggio = "Avviso di prova inviato."
        } catch {
            messaggio = error.localizedDescription
        }
    }
}

// MARK: - Crediti e mia squadra

struct CreditiView: View {
    @StateObject private var caricatore = Caricatore<[SquadraCrediti]>("/api/squadre", cache: false)
    @State private var valori: [String: String] = [:]
    @State private var messaggio: String?

    var body: some View {
        ZStack {
            Sfondo()
            List {
                if let s = caricatore.dato {
                    Section("Crediti residui di ogni squadra") {
                        ForEach(s) { sq in
                            HStack {
                                Text(sq.nome)
                                Spacer()
                                TextField("—", text: Binding(get: { valori[sq.nome] ?? "" }, set: { valori[sq.nome] = $0 }))
                                    .keyboardType(.numberPad).multilineTextAlignment(.trailing).frame(minWidth: 80, minHeight: 44)
                            }
                        }
                    }
                    Section {
                        Button("Salva i crediti") { Task { await salva() } }
                        if let messaggio { Text(messaggio).font(.footnote) }
                        Text("Servono per i consigli del mercato (rimborso e crediti dopo il cambio). Restano anche se importi di nuovo l'Excel.")
                            .font(.footnote).foregroundStyle(.secondary)
                    }
                } else if let e = caricatore.errore {
                    ErroreVista(messaggio: e) { Task { await carica() } }
                } else {
                    ProgressView().frame(maxWidth: .infinity)
                }
            }
            .scrollContentBackground(.hidden)
        }
        .navigationTitle("Crediti")
        .task { await carica() }
    }

    private func carica() async {
        await caricatore.ricarica()
        for s in caricatore.dato ?? [] { valori[s.nome] = s.creditiResidui.map { String(Int($0)) } ?? "" }
    }

    private func salva() async {
        var crediti: [String: Int] = [:]
        for (nome, testo) in valori { if let n = Int(testo.trimmingCharacters(in: .whitespaces)) { crediti[nome] = n } }
        do {
            let _: JSONValue = try await Api.posta("PUT", "/api/crediti", CreditiSquadre(crediti: crediti), snake: false)
            messaggio = "Crediti salvati."
            UINotificationFeedbackGenerator().notificationOccurred(.success)
        } catch {
            messaggio = error.localizedDescription
        }
    }
}
