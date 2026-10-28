import SwiftUI

/// Schermata Scambi: solo presentazione. Dati e logica sono in `ScambiViewModel`.
struct ScambiView: View {
    @ObservedObject var vm: ScambiViewModel

    var body: some View {
        NavigationStack(path: $vm.percorso) {
            ZStack {
                Sfondo()
                ScrollView {
                    Colonne(spazio: 12) {
                        Carta {
                            Picker("Con", selection: $vm.con) {
                                Text("Tutte le squadre").tag("Tutte")
                                ForEach(vm.altre) { Text($0.nome).tag($0.nome) }
                            }
                            Toggle("Cerca anche 2 contro 2 (più lento)", isOn: $vm.due).tint(Color.verde)
                            NavigationLink(value: PaginaScambi.analizza) {
                                Label("Analizza uno scambio a mano", systemImage: "slider.horizontal.3").frame(minHeight: 44)
                            }
                        }
                        if let d = vm.proposte.dato {
                            if d.proposte.isEmpty {
                                VistaVuota(titolo: "Nessuno scambio per ora", icona: "arrow.left.arrow.right", descrizione: "Nessuno scambio conviene a tutti e due.")
                            }
                            ForEach(d.proposte) { p in
                                Button { vm.selezionata = p } label: { carta(p) }
                                    .buttonStyle(.plain).puntatore()
                                    .accessibilityHint("Mostra il dettaglio dello scambio")
                            }
                        } else if let e = vm.proposte.errore {
                            ErroreVista(messaggio: e) { Task { await vm.caricaProposte() } }
                        } else {
                            ProgressView("Cerco gli scambi…").padding(40)
                        }
                    }
                    .padding(.horizontal, 16).padding(.bottom, 24)
                }
                .demoInFondo()
                .refreshable { await vm.caricaProposte() }
                .avvisoDatiSalvati(vm.proposte.datiSalvati)
            }
            .navigationTitle("Scambi")
            .navigationDestination(for: PaginaScambi.self) { _ in AnalizzaScambioView(server: vm.server) }
            .task { await vm.caricaSquadre() }
            .task(id: vm.indirizzoProposte) { await vm.caricaProposte() }
            .sheet(item: $vm.selezionata) { p in
                NavigationStack {
                    ZStack { Sfondo(); ScrollView { DettaglioScambio(p: p).padding(16) } }
                        .navigationTitle("Scambio con \(p.altra)")
                        .navigationBarTitleDisplayMode(.inline)
                        .toolbar {
                            ToolbarItem(placement: .navigationBarTrailing) { Button("Chiudi") { vm.selezionata = nil } }
                        }
                }
            }
        }
    }

    private func carta(_ p: PropostaScambio) -> some View {
        Carta {
            Text(p.altra).font(.caption).foregroundStyle(.secondary)
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 4) {
                    ForEach(p.`do`) { g in HStack { BadgeRuolo(ruolo: g.ruolo); Text(g.nome).font(.subheadline) } }
                    Image(systemName: "arrow.down").font(.caption).foregroundStyle(.secondary).accessibilityLabel("in cambio di")
                    ForEach(p.ricevo) { g in HStack { BadgeRuolo(ruolo: g.ruolo); Text(g.nome).font(.headline) } }
                }
                Spacer()
                VStack(alignment: .trailing, spacing: 4) {
                    guadagno("tu", p.guadagnoMio)
                    guadagno("loro", p.guadagnoLoro)
                }
            }
        }
    }

    private func guadagno(_ chi: String, _ v: Double) -> some View {
        HStack(spacing: 4) {
            Text(chi).font(.caption2).foregroundStyle(.secondary)
            Text(Formato.conSegno(v)).font(.headline).monospacedDigit().foregroundStyle(v >= 0 ? Color.verde : .orange)
        }
        .accessibilityElement(children: .combine)
    }
}

/// Dettaglio di uno scambio: cosa dai, cosa ricevi, quanto guadagna ciascuno giornata per giornata.
struct DettaglioScambio: View {
    let p: PropostaScambio

    var body: some View {
        VStack(spacing: 14) {
            Carta("Dai") { ForEach(p.`do`) { g in elenco(g) } }
            Carta("Ricevi") { ForEach(p.ricevo) { g in elenco(g) } }
            Carta("Punti attesi") {
                riga("Tu", p.guadagnoMio)
                riga("\(p.altra)", p.guadagnoLoro)
                if let g = p.giornate, let a = p.perGiornataMio, let b = p.perGiornataLoro, g.count == a.count, g.count == b.count {
                    Divider()
                    ForEach(Array(g.enumerated()), id: \.offset) { i, n in
                        HStack {
                            Text("Giornata \(n)").foregroundStyle(.secondary)
                            Spacer()
                            Text(Formato.conSegno(a[i], cifre: 2)).monospacedDigit().foregroundStyle(a[i] >= 0 ? Color.verde : .orange)
                            Text(Formato.conSegno(b[i], cifre: 2)).monospacedDigit().foregroundStyle(.secondary).frame(minWidth: 60, alignment: .trailing)
                        }
                        .accessibilityElement(children: .combine)
                    }
                    Text("A destra: il guadagno dell'altra squadra.").font(.caption).foregroundStyle(.secondary)
                }
            }
        }
    }

    private func elenco(_ g: GiocatoreBreve) -> some View {
        HStack { BadgeRuolo(ruolo: g.ruolo); Text(g.nome); Spacer(); Text((g.squadra ?? "").capitalized).foregroundStyle(.secondary) }
            .accessibilityElement(children: .combine)
    }

    private func riga(_ chi: String, _ v: Double) -> some View {
        HStack { Text(chi); Spacer(); Text(Formato.conSegno(v)).font(.headline).monospacedDigit().foregroundStyle(v >= 0 ? Color.verde : .orange) }
            .accessibilityElement(children: .combine)
    }
}

/// Scegli chi dai e chi ricevi dalle due rose e l'app dice se conviene.
struct AnalizzaScambioView: View {
    @StateObject private var vm: AnalizzaScambioViewModel

    init(server: any ServerClient) {
        _vm = StateObject(wrappedValue: AnalizzaScambioViewModel(server: server))
    }

    var body: some View {
        ZStack {
            Sfondo()
            List {
                Section("Con") {
                    Picker("Squadra", selection: $vm.altra) {
                        Text("Scegli…").tag("")
                        ForEach(vm.altre) { Text($0.nome).tag($0.nome) }
                    }
                }
                if let mia = vm.miaRosa.dato {
                    Section("Tu dai") { elenco(mia.giocatori, scelti: $vm.doIds) }
                }
                if let loro = vm.loro {
                    Section("Tu ricevi") { elenco(loro.giocatori, scelti: $vm.ricevoIds) }
                }
                Section {
                    Button {
                        Task { await vm.analizza() }
                    } label: {
                        if vm.inCorso { ProgressView() } else { Text("Analizza").frame(minHeight: 44) }
                    }
                    .disabled(!vm.puoAnalizzare)
                    if let errore = vm.errore { Text(errore).foregroundStyle(.orange) }
                }
                if let esito = vm.esito {
                    Section("Esito") { DettaglioScambio(p: esito).listRowBackground(Color.clear) }
                }
            }
            .scrollContentBackground(.hidden)
        }
        .navigationTitle("Analizza")
        .navigationBarTitleDisplayMode(.inline)
        .task { await vm.carica() }
        .task(id: vm.altra) { await vm.caricaRosaAltra() }
    }

    private func elenco(_ giocatori: [GiocatoreRosa], scelti: Binding<Set<Int>>) -> some View {
        ForEach(giocatori.filter { $0.id != nil }, id: \.ident) { g in
            let id = g.id ?? -1
            let scelto = scelti.wrappedValue.contains(id)
            Button {
                if scelto { scelti.wrappedValue.remove(id) } else { scelti.wrappedValue.insert(id) }
            } label: {
                HStack(spacing: 10) {
                    Image(systemName: scelto ? "checkmark.circle.fill" : "circle")
                        .foregroundStyle(scelto ? Color.verde : .secondary)
                    BadgeRuolo(ruolo: g.ruolo ?? "?")
                    Text(g.nome)
                    Spacer()
                    Text((g.squadra ?? "").capitalized).font(.caption).foregroundStyle(.secondary)
                }
            }
            .buttonStyle(.plain)
            .accessibilityElement(children: .combine)
            .accessibilityAddTraits(scelto ? .isSelected : [])
        }
    }
}

#Preview("Scambi") {
    ScambiView(vm: ScambiViewModel(server: FinteServer.esempio))
}
