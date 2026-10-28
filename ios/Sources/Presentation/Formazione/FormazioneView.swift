import SwiftUI

/// Schermata Formazione: solo presentazione. Dati e logica sono in `FormazioneViewModel`.
struct FormazioneView: View {
    @ObservedObject var vm: FormazioneViewModel
    @State private var daSostituire: Giocatore?

    private let ruoli = ["P", "D", "C", "A"]
    private let nomiRuolo = ["P": "Portiere", "D": "Difensori", "C": "Centrocampisti", "A": "Attaccanti"]

    var body: some View {
        NavigationStack {
            ZStack {
                Sfondo()
                ScrollView {
                    Colonne(spazio: 14) {
                        if let f = vm.formazione {
                            if vm.manuale == nil { sceltaStile(f) }
                            let v = vm.vista(f)
                            riepilogo(f, modulo: v.modulo, punti: v.punti)
                            barraManuale(f)
                            ForEach(ruoli, id: \.self) { r in
                                let gruppo = v.titolari.filter { $0.ruolo == r }
                                if !gruppo.isEmpty {
                                    Carta(nomiRuolo[r]) {
                                        ForEach(gruppo) { g in rigaTitolare(g) }
                                    }
                                }
                            }
                            Carta("Panchina") { ForEach(v.panchina) { RigaGiocatore(g: $0) } }
                        } else if let errore = vm.errore {
                            ErroreVista(messaggio: errore) { Task { await vm.carica() } }
                        } else {
                            ProgressView("Calcolo la formazione…").padding(40)
                        }
                    }
                    .padding(.horizontal, 16)
                    .padding(.bottom, 24)
                }
                .demoInFondo()
                .refreshable { await vm.carica() }
                .avvisoDatiSalvati(vm.datiSalvati)
            }
            .navigationTitle("Formazione")
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    if let testo = vm.testoDaCondividere {
                        ShareLink(item: testo) { Image(systemName: "square.and.arrow.up") }
                            .accessibilityLabel("Condividi la formazione")
                    }
                }
            }
            .sheet(item: $daSostituire) { g in
                if let f = vm.formazione {
                    SostituzioneSheet(uscente: g, formazione: f, titolari: vm.manuale ?? []) { nuovo in
                        vm.sostituisci(g.id, con: nuovo)
                        daSostituire = nil
                    }
                }
            }
            .task { await vm.carica() }
        }
    }

    /// In modifica a mano ogni titolare è un bottone che apre la scelta del sostituto.
    @ViewBuilder
    private func rigaTitolare(_ g: Giocatore) -> some View {
        if vm.manuale != nil {
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

    @ViewBuilder
    private func barraManuale(_ f: Formazione) -> some View {
        Carta {
            if vm.manuale == nil {
                Button { vm.iniziaModificaManuale(f) } label: { Label("Modifica a mano", systemImage: "hand.tap").frame(minHeight: 44) }
            } else {
                Text("Tocca un titolare per sostituirlo con un altro della rosa: i punti attesi si ricalcolano.").font(.footnote).foregroundStyle(.secondary)
                if let d = vm.valutazione?.differenza {
                    Text("Rispetto alla consigliata con lo stesso modulo: " + Formato.conSegno(d))
                        .font(.subheadline).foregroundStyle(d >= 0 ? Color.verde : .orange)
                }
                HStack {
                    Button { Task { await vm.valuta(salva: true) } } label: { Label("Salva come mia scelta", systemImage: "tray.and.arrow.down").frame(minHeight: 44) }
                        .keyboardShortcut("s", modifiers: .command)
                    Spacer()
                    Button(role: .destructive) { Task { await vm.tornaAllaConsigliata(f) } } label: { Text("Torna alla consigliata").frame(minHeight: 44) }
                }
                .font(.subheadline)
            }
            if let messaggio = vm.messaggio { Text(messaggio).font(.footnote).foregroundStyle(.secondary) }
        }
    }

    /// Stile (da molto sicura a molto rischiosa) e modulo.
    @ViewBuilder
    private func sceltaStile(_ f: Formazione) -> some View {
        if let livelli = f.livelli, !livelli.isEmpty {
            let livello = livelli.first(where: { $0.rischio == vm.rischio }) ?? livelli[0]
            Carta("Stile") {
                Picker("Stile", selection: $vm.rischio) {
                    ForEach(livelli) { Text($0.nome).tag($0.rischio) }
                }
                .pickerStyle(.menu)
                .onChange(of: vm.rischio) { _ in vm.cambiaStile() }
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(livello.moduli) { m in
                            let attivo = vm.moduloAttivo(livello) == m.modulo
                            Button { vm.scegliModulo(m.modulo) } label: {
                                VStack(spacing: 2) {
                                    Text(m.modulo).font(.subheadline.bold())
                                    Text(Formato.punti(m.punteggioAtteso)).font(.caption2).monospacedDigit()
                                }
                                .padding(.horizontal, 12).padding(.vertical, 6)
                                .frame(minHeight: 44)
                                .background(attivo ? Color.verde.opacity(0.35) : Color.primary.opacity(0.08), in: Capsule())
                                .overlay(Capsule().strokeBorder(attivo ? Color.verde : .clear, lineWidth: 1))
                            }
                            .buttonStyle(.plain)
                            .accessibilityLabel("Modulo \(m.modulo), \(Formato.punti(m.punteggioAtteso)) punti attesi")
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
                    Text(Formato.punti(punti)).font(.title2.bold()).monospacedDigit()
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
                    if candidati.isEmpty {
                        VistaVuota(titolo: "Nessun altro giocatore", icona: "person.slash", descrizione: "Non ci sono altri giocatori di questo ruolo in rosa.")
                    }
                }
            }
            .navigationTitle("Sostituisci")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .navigationBarTrailing) { Button("Annulla") { chiudi() } } }
        }
    }
}

#Preview("Formazione") {
    FormazioneView(vm: FormazioneViewModel(server: FinteServer.esempio))
}
