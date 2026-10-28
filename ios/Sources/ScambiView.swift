import SwiftUI

struct ScambiView: View {
    @StateObject private var squadre = Caricatore<[SquadraLega]>("/api/squadre")
    @StateObject private var proposte = Caricatore<ProposteScambi>("/api/scambi/proposte")
    @State private var con = "Tutte"
    @State private var due = false
    @State private var selezionata: PropostaScambio?

    private var altre: [SquadraLega] { (squadre.dato ?? []).filter { $0.mia != true } }

    private var percorso: String {
        var p = "/api/scambi/proposte?due=\(due ? "true" : "false")"
        if con != "Tutte" { p += "&con=\(Api.codifica(con))" }
        return p
    }

    var body: some View {
        NavigationStack {
            ZStack {
                Sfondo()
                ScrollView {
                    VStack(spacing: 12) {
                        Carta {
                            Picker("Con", selection: $con) {
                                Text("Tutte le squadre").tag("Tutte")
                                ForEach(altre) { Text($0.nome).tag($0.nome) }
                            }
                            Toggle("Cerca anche 2 contro 2 (più lento)", isOn: $due).tint(Color.verde)
                            NavigationLink { AnalizzaScambioView() } label: {
                                Label("Analizza uno scambio a mano", systemImage: "slider.horizontal.3")
                            }
                        }
                        if let d = proposte.dato {
                            if d.proposte.isEmpty {
                                Text("Nessuno scambio conviene a tutti e due, per ora.").foregroundStyle(.secondary).padding()
                            }
                            ForEach(d.proposte) { p in
                                Button { selezionata = p } label: { carta(p) }.buttonStyle(.plain)
                            }
                        } else if let e = proposte.errore {
                            ErroreVista(messaggio: e) { Task { await proposte.ricarica(percorso) } }
                        } else {
                            ProgressView("Cerco gli scambi…").padding(40)
                        }
                    }
                    .padding(.horizontal, 16).padding(.bottom, 24)
                }
                .refreshable { await proposte.ricarica(percorso) }
                .avvisoDatiSalvati(proposte.datiSalvati)
            }
            .navigationTitle("Scambi")
            .task { await squadre.ricarica() }
            .task(id: percorso) { await proposte.ricarica(percorso) }
            .sheet(item: $selezionata) { p in
                NavigationStack {
                    ZStack { Sfondo(); ScrollView { DettaglioScambio(p: p).padding(16) } }
                        .navigationTitle("Scambio con \(p.altra)")
                        .navigationBarTitleDisplayMode(.inline)
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
                    Image(systemName: "arrow.down").font(.caption).foregroundStyle(.secondary)
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
            Text((v >= 0 ? "+" : "") + v.formatted(.number.precision(.fractionLength(1))))
                .font(.headline).monospacedDigit().foregroundStyle(v >= 0 ? Color.verde : .orange)
        }
    }
}

/// Dettaglio di uno scambio: cosa dai, cosa ricevi, quanto guadagna ciascuno giornata per giornata.
struct DettaglioScambio: View {
    let p: PropostaScambio

    var body: some View {
        VStack(spacing: 14) {
            Carta("Dai") { ForEach(p.`do`) { g in HStack { BadgeRuolo(ruolo: g.ruolo); Text(g.nome); Spacer(); Text(g.squadra ?? "").foregroundStyle(.secondary) } } }
            Carta("Ricevi") { ForEach(p.ricevo) { g in HStack { BadgeRuolo(ruolo: g.ruolo); Text(g.nome); Spacer(); Text(g.squadra ?? "").foregroundStyle(.secondary) } } }
            Carta("Punti attesi") {
                riga("Tu", p.guadagnoMio)
                riga("\(p.altra)", p.guadagnoLoro)
                if let g = p.giornate, let a = p.perGiornataMio, let b = p.perGiornataLoro, g.count == a.count, g.count == b.count {
                    Divider()
                    ForEach(Array(g.enumerated()), id: \.offset) { i, n in
                        HStack {
                            Text("Giornata \(n)").foregroundStyle(.secondary)
                            Spacer()
                            Text(formato(a[i])).monospacedDigit().foregroundStyle(a[i] >= 0 ? Color.verde : .orange)
                            Text(formato(b[i])).monospacedDigit().foregroundStyle(.secondary).frame(width: 60, alignment: .trailing)
                        }
                    }
                    Text("A destra: il guadagno dell'altra squadra.").font(.caption).foregroundStyle(.secondary)
                }
            }
        }
    }

    private func formato(_ v: Double) -> String { (v >= 0 ? "+" : "") + v.formatted(.number.precision(.fractionLength(2))) }

    private func riga(_ chi: String, _ v: Double) -> some View {
        HStack { Text(chi); Spacer(); Text(formato(v)).font(.headline).monospacedDigit().foregroundStyle(v >= 0 ? Color.verde : .orange) }
    }
}

/// Scegli chi dai e chi ricevi dalle due rose e l'app dice se conviene.
struct AnalizzaScambioView: View {
    @StateObject private var squadre = Caricatore<[SquadraLega]>("/api/squadre")
    @StateObject private var miaRosa = Caricatore<Rosa>("/api/rosa")
    @State private var altra = ""
    @State private var loro: Rosa?
    @State private var doIds: Set<Int> = []
    @State private var ricevoIds: Set<Int> = []
    @State private var esito: PropostaScambio?
    @State private var errore: String?
    @State private var inCorso = false

    private var altre: [SquadraLega] { (squadre.dato ?? []).filter { $0.mia != true } }

    var body: some View {
        ZStack {
            Sfondo()
            List {
                Section("Con") {
                    Picker("Squadra", selection: $altra) {
                        Text("Scegli…").tag("")
                        ForEach(altre) { Text($0.nome).tag($0.nome) }
                    }
                }
                if let mia = miaRosa.dato {
                    Section("Tu dai") { elenco(mia.giocatori, scelti: $doIds) }
                }
                if let loro {
                    Section("Tu ricevi") { elenco(loro.giocatori, scelti: $ricevoIds) }
                }
                Section {
                    Button {
                        Task { await analizza() }
                    } label: {
                        if inCorso { ProgressView() } else { Text("Analizza") }
                    }
                    .disabled(altra.isEmpty || doIds.isEmpty || ricevoIds.isEmpty || inCorso)
                    if let errore { Text(errore).foregroundStyle(.orange) }
                }
                if let esito {
                    Section("Esito") { DettaglioScambio(p: esito).listRowBackground(Color.clear) }
                }
            }
            .scrollContentBackground(.hidden)
        }
        .navigationTitle("Analizza")
        .navigationBarTitleDisplayMode(.inline)
        .task {
            await squadre.ricarica()
            await miaRosa.ricarica()
        }
        .task(id: altra) {
            ricevoIds = []
            esito = nil
            guard !altra.isEmpty else { loro = nil; return }
            loro = try? await Api.get("/api/rosa?squadra=\(Api.codifica(altra))")
        }
    }

    private func elenco(_ giocatori: [GiocatoreRosa], scelti: Binding<Set<Int>>) -> some View {
        ForEach(giocatori.filter { $0.id != nil }, id: \.ident) { g in
            let id = g.id ?? -1
            Button {
                if scelti.wrappedValue.contains(id) { scelti.wrappedValue.remove(id) } else { scelti.wrappedValue.insert(id) }
            } label: {
                HStack(spacing: 10) {
                    Image(systemName: scelti.wrappedValue.contains(id) ? "checkmark.circle.fill" : "circle")
                        .foregroundStyle(scelti.wrappedValue.contains(id) ? Color.verde : .secondary)
                    BadgeRuolo(ruolo: g.ruolo)
                    Text(g.nome)
                    Spacer()
                    Text(g.squadra ?? "").font(.caption).foregroundStyle(.secondary)
                }
            }
            .buttonStyle(.plain)
        }
    }

    private func analizza() async {
        inCorso = true
        defer { inCorso = false }
        let a = doIds.sorted().map(String.init).joined(separator: ",")
        let b = ricevoIds.sorted().map(String.init).joined(separator: ",")
        do {
            esito = try await Api.get("/api/scambi/analizza?con=\(Api.codifica(altra))&do=\(a)&ricevo=\(b)")
            errore = nil
        } catch {
            esito = nil
            errore = error.localizedDescription
        }
    }
}
