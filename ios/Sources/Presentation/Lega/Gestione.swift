import SwiftUI

// MARK: - Avvisi del server

struct AvvisiServerView: View {
    @EnvironmentObject private var sessione: SessioneAccount
    @StateObject private var vm: AvvisiServerViewModel
    /// Lo stato dei promemoria di questo telefono (permesso, aggiornamento in background): una sola pagina per tutti gli avvisi.
    @ObservedObject private var lega: LegaViewModel

    init(server: any ServerClient, lega: LegaViewModel) {
        _vm = StateObject(wrappedValue: AvvisiServerViewModel(server: server))
        self.lega = lega
    }

    var body: some View {
        ZStack {
            Sfondo()
            List {
                Section {
                    RigaValore(titolo: "Notifiche", valore: lega.permesso)
                    Button("Attiva i promemoria sul telefono") { Task { await lega.attivaPromemoria() } }.frame(minHeight: 44)
                    RigaValore(titolo: "Aggiornamento in background", valore: lega.aggiornamentoInBackground)
                } header: {
                    Text("Promemoria sul telefono")
                } footer: {
                    Text("Ti avvisiamo un'ora e un quarto d'ora prima della prima partita, anche con l'app chiusa. Se la formazione consigliata cambia, l'app te lo dice da sola: è iOS a decidere quando controllare, di solito poche volte al giorno.")
                }
                if let s = vm.caricatore.dato {
                    if vm.oreTranquilleSpente {
                        Section {
                            Text("Avevi scelto le ore tranquille con inizio e fine alla stessa ora: non valgono, le ho spente. Riaccendile scegliendo due ore diverse (per esempio dalle 23 alle 7).")
                                .font(.footnote.weight(.semibold))
                                .accessibilityAddTraits(.isStaticText)
                        }
                    }
                    Section("Quali avvisi") {
                        interruttore("Cambi di formazione e probabili", \.cambi)
                        interruttore("Promemoria un'ora prima", \.promemoria_60)
                        interruttore("Promemoria 15 minuti prima", \.promemoria_15)
                        interruttore("Riepilogo a giornata finita", \.riepilogo)
                        Toggle(isOn: Binding(
                            get: { vm.impostazioni?.copertura ?? true },
                            set: { nuovo in
                                vm.impostazioni?.copertura = nuovo
                                Task { await vm.salva() }
                            })) {
                            VStack(alignment: .leading, spacing: 2) {
                                Text("Reparto della rosa scoperto")
                                Text("Ti avvisa se in un reparto hai pochi giocatori disponibili (infortunati, squalificati, diffidati).")
                                    .font(.caption).foregroundStyle(.secondary)
                            }
                        }
                        .tint(Color.verde)
                        .frame(minHeight: 44)
                    }
                    sezioneOreTranquille
                    if sessione.multiutente {
                        Section {
                            Text("Per ricevere anche gli avvisi su cambi di formazione e riepilogo, apri SchieraXI con Safari e aggiungilo alla schermata Home: gli avvisi arrivano da lì.")
                                .font(.footnote).foregroundStyle(.secondary)
                        }
                    } else {
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
                    } header: {
                        Text("Avanzate (per chi gestisce il server)")
                    } footer: {
                        Text("Il server aggiunge da solo il tocco che apre l'app: non devi impostare niente.")
                    }
                    Section {
                        Text("Dispositivi con avvisi web attivi: \(s.dispositivi ?? 0). Canale degli avvisi: \(s.canale == true ? "attivo" : "non configurato"). Con l'Apple ID gratuito l'app nativa non può ricevere notifiche push: gli avvisi del server arrivano con ntfy o dalla web app installata dalla Home.")
                            .font(.footnote).foregroundStyle(.secondary)
                        Button("Manda un avviso di prova") { Task { await vm.provaAvviso() } }.frame(minHeight: 44)
                        if let messaggio = vm.messaggio { Text(messaggio).font(.footnote) }
                    }
                    }
                } else if let e = vm.caricatore.errore {
                    ErroreVista(messaggio: e) { Task { await vm.carica() } }
                } else {
                    ScheletroRighe(righe: 5).listRowBackground(Color.clear)
                }
            }
            .scrollContentBackground(.hidden)
        }
        .navigationTitle("Avvisi e promemoria")
        .task { await vm.carica() }
        .task { await lega.aggiornaPermesso() }
    }

    /// Ore tranquille: niente avvisi in quella fascia (anche i promemoria di questo telefono la rispettano).
    private var sezioneOreTranquille: some View {
        Section {
            Toggle(isOn: Binding(
                get: { vm.impostazioni?.silenzio ?? false },
                set: { nuovo in
                    vm.impostazioni?.silenzio = nuovo
                    if nuovo, vm.impostazioni?.silenzio_da == nil { vm.impostazioni?.silenzio_da = OreTranquille.predefinite.da }
                    if nuovo, vm.impostazioni?.silenzio_a == nil { vm.impostazioni?.silenzio_a = OreTranquille.predefinite.a }
                    Task { await vm.salva() }
                })) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Ore tranquille")
                    Text("Niente avvisi di notte: i promemoria che cadono in quelle ore non partono.")
                        .font(.caption).foregroundStyle(.secondary)
                }
            }
            .tint(Color.verde)
            .frame(minHeight: 44)
            if vm.impostazioni?.silenzio == true {
                selettoreOra("Dalle", \.silenzio_da, predefinita: OreTranquille.predefinite.da)
                selettoreOra("Alle", \.silenzio_a, predefinita: OreTranquille.predefinite.a)
            }
        } header: {
            Text("Ore tranquille")
        } footer: {
            if let ore = vm.impostazioni?.oreTranquille, ore.attive {
                Text(ore.da == ore.a ? "Con la stessa ora di inizio e di fine non c'è nessun silenzio." : "Silenzio \(ore.descrizione) (ora italiana).")
            }
        }
    }

    private func selettoreOra(_ titolo: String, _ chiave: WritableKeyPath<ImpostazioniAvvisi, Int?>, predefinita: Int) -> some View {
        Picker(titolo, selection: Binding(
            get: { vm.impostazioni?[keyPath: chiave] ?? predefinita },
            set: { nuovo in
                vm.impostazioni?[keyPath: chiave] = nuovo
                Task { await vm.salva() }
            })) {
            ForEach(0..<24, id: \.self) { Text(String(format: "%02d:00", $0)).tag($0) }
        }
        .frame(minHeight: 44)
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
                    ScheletroRighe(righe: 5).listRowBackground(Color.clear)
                }
            }
            .scrollContentBackground(.hidden)
        }
        .navigationTitle("Crediti")
        .task { await vm.carica() }
    }
}
