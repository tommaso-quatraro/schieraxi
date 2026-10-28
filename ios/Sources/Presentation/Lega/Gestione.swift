import SwiftUI

// MARK: - Regole della lega (editor generico)

struct RegoleEditorView: View {
    @StateObject private var vm: RegoleEditorViewModel

    init(server: any ServerClient) {
        _vm = StateObject(wrappedValue: RegoleEditorViewModel(server: server))
    }

    var body: some View {
        ZStack {
            Sfondo()
            List {
                if vm.caricato {
                    if case .oggetto = vm.valore {
                        EditorJSON(valore: $vm.valore, titolo: "Regole")
                    }
                    Section {
                        Button {
                            Task { await vm.salva() }
                        } label: {
                            if vm.inCorso { ProgressView() } else { Label("Salva le regole", systemImage: "checkmark.circle").frame(minHeight: 44) }
                        }
                        .disabled(vm.inCorso)
                        if let esito = vm.esito { Text(esito).font(.footnote) }
                    }
                } else if let e = vm.caricatore.errore {
                    ErroreVista(messaggio: e) { Task { await vm.carica() } }
                } else {
                    ProgressView().frame(maxWidth: .infinity)
                }
            }
            .scrollContentBackground(.hidden)
        }
        .navigationTitle("Regole")
        .task { await vm.carica() }
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
                    .frame(minHeight: 44)
            }
        case .lista:
            HStack { Text(nome(chiave)); Spacer(); Text(v.descrizione).foregroundStyle(.secondary).lineLimit(1) }
        }
    }

    private func nome(_ chiave: String) -> String {
        chiave.replacingOccurrences(of: "_", with: " ").primaMaiuscola
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
        // virgola decimale, come nel resto dell'app (scrivendo «3,5» o «3.5» il valore è lo stesso)
        case .decimale(let d): return d == d.rounded() && abs(d) < 1e15 ? String(Int(d)) : String(d).replacingOccurrences(of: ".", with: ",")
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
    @StateObject private var vm: AvvisiServerViewModel

    init(server: any ServerClient) {
        _vm = StateObject(wrappedValue: AvvisiServerViewModel(server: server))
    }

    var body: some View {
        ZStack {
            Sfondo()
            List {
                if let s = vm.caricatore.dato {
                    Section("Quali avvisi") {
                        interruttore("Cambi di formazione e probabili", \.cambi)
                        interruttore("Promemoria un'ora prima", \.promemoria_60)
                        interruttore("Promemoria 15 minuti prima", \.promemoria_15)
                        interruttore("Riepilogo a giornata finita", \.riepilogo)
                    }
                    Section {
                        Text("Dispositivi con avvisi web attivi: \(s.dispositivi ?? 0). Gli avvisi del server arrivano dalla web app installata dalla Home (l'app nativa gratuita non può riceverli).")
                            .font(.footnote).foregroundStyle(.secondary)
                        Button("Manda un avviso di prova") { Task { await vm.provaAvviso() } }.frame(minHeight: 44)
                        if let messaggio = vm.messaggio { Text(messaggio).font(.footnote) }
                    }
                } else if let e = vm.caricatore.errore {
                    ErroreVista(messaggio: e) { Task { await vm.carica() } }
                } else {
                    ProgressView().frame(maxWidth: .infinity)
                }
            }
            .scrollContentBackground(.hidden)
        }
        .navigationTitle("Avvisi del server")
        .task { await vm.carica() }
    }

    private func interruttore(_ titolo: String, _ chiave: WritableKeyPath<ImpostazioniAvvisi, Bool>) -> some View {
        Toggle(titolo, isOn: Binding(
            get: { vm.impostazioni?[keyPath: chiave] ?? false },
            set: { nuovo in
                vm.impostazioni?[keyPath: chiave] = nuovo
                Task { await vm.salva() }
            })).tint(Color.verde)
    }
}

// MARK: - Crediti e mia squadra

struct CreditiView: View {
    @StateObject private var vm: CreditiViewModel

    init(server: any ServerClient) {
        _vm = StateObject(wrappedValue: CreditiViewModel(server: server))
    }

    var body: some View {
        ZStack {
            Sfondo()
            List {
                if let s = vm.caricatore.dato {
                    Section("Crediti residui di ogni squadra") {
                        ForEach(s) { sq in
                            HStack {
                                Text(sq.nome)
                                Spacer()
                                TextField("—", text: Binding(get: { vm.valori[sq.nome] ?? "" }, set: { vm.valori[sq.nome] = $0 }))
                                    .keyboardType(.numberPad).multilineTextAlignment(.trailing).frame(minWidth: 80, minHeight: 44)
                            }
                        }
                    }
                    Section {
                        Button("Salva i crediti") { Task { await vm.salva() } }.frame(minHeight: 44)
                        if let messaggio = vm.messaggio { Text(messaggio).font(.footnote) }
                        Text("Servono per i consigli del mercato (rimborso e crediti dopo il cambio). Restano anche se importi di nuovo l'Excel.")
                            .font(.footnote).foregroundStyle(.secondary)
                    }
                } else if let e = vm.caricatore.errore {
                    ErroreVista(messaggio: e) { Task { await vm.carica() } }
                } else {
                    ProgressView().frame(maxWidth: .infinity)
                }
            }
            .scrollContentBackground(.hidden)
        }
        .navigationTitle("Crediti")
        .task { await vm.carica() }
    }
}
