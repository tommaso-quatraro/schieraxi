import SwiftUI

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
                        Toggle(isOn: Binding(
                            get: { vm.impostazioni?.app_nativa ?? false },
                            set: { nuovo in
                                vm.impostazioni?.app_nativa = nuovo
                                Task { await vm.salva() }
                            })) {
                            VStack(alignment: .leading, spacing: 2) {
                                Text("Avvisi anche per l'app nativa")
                                Text("Arrivano con l'app ntfy e il tocco apre questa app. Se hai attivato anche le notifiche della web app potresti riceverli doppi.")
                                    .font(.caption).foregroundStyle(.secondary)
                            }
                        }
                        .tint(Color.verde)
                        .frame(minHeight: 44)
                    } footer: {
                        Text("Per far aprire l'app dal tocco su una notifica serve l'intestazione Click: la trovi in Lega, «Come aprire l'app da una notifica ntfy».")
                    }
                    Section {
                        Text("Dispositivi con avvisi web attivi: \(s.dispositivi ?? 0). Canale degli avvisi: \(s.canale == true ? "attivo" : "non configurato"). Con l'Apple ID gratuito l'app nativa non può ricevere notifiche push: gli avvisi del server arrivano con ntfy o dalla web app installata dalla Home.")
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
