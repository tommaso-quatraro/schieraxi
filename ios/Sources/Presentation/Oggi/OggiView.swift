import SwiftUI

/// Schermata Oggi: solo presentazione. Dati e logica sono in `OggiViewModel`.
struct OggiView: View {
    @ObservedObject var vm: OggiViewModel

    var body: some View {
        NavigationStack {
            ZStack {
                Sfondo()
                ScrollView {
                    Colonne(spazio: 14) {
                        if let oggi = vm.oggi {
                            testata(oggi)
                            formazione(oggi)
                            daControllare
                            indisponibili
                            migliori(oggi)
                            partite(oggi)
                        } else if let errore = vm.errore {
                            ErroreVista(messaggio: errore) { Task { await vm.carica() } }
                        } else {
                            ProgressView("Carico la giornata…").padding(40)
                        }
                    }
                    .padding(.horizontal, 16)
                    .padding(.bottom, 24)
                }
                .demoInFondo()
                .refreshable { await vm.carica() }
                .avvisoDatiSalvati(vm.datiSalvati)
            }
            .navigationTitle("Oggi")
            .task { await vm.carica() }
        }
    }

    private func testata(_ oggi: Oggi) -> some View {
        Carta("Giornata \(oggi.giornata)") {
            if let inizio = Quando.data(oggi.inizio) {
                // Ogni secondo ricontrolla: a zero il conto alla rovescia lascia il posto a «In corso».
                TimelineView(.periodic(from: Date(), by: 1)) { contesto in
                    VStack(alignment: .leading, spacing: 4) {
                        if inizio > contesto.date {
                            conto(da: contesto.date, a: inizio)
                                .font(.system(.largeTitle, design: .rounded).weight(.bold))
                                .minimumScaleFactor(0.6)
                                .lineLimit(1)
                            Text("alla prima partita, \(Quando.leggibile(oggi.inizio))").font(.subheadline).foregroundStyle(.secondary)
                        } else {
                            Text("In corso").font(.system(.largeTitle, design: .rounded).weight(.bold))
                            Text("iniziata \(Quando.leggibile(oggi.inizio))").font(.subheadline).foregroundStyle(.secondary)
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .accessibilityElement(children: .combine)
                }
            } else {
                Text(oggi.iniziata == true ? "In corso" : "—").font(.system(.largeTitle, design: .rounded).weight(.bold))
            }
        }
    }

    /// Ore, minuti e secondi se manca meno di un giorno; altrimenti giorni e ore.
    @ViewBuilder
    private func conto(da adesso: Date, a inizio: Date) -> some View {
        if inizio.timeIntervalSince(adesso) < 24 * 3600 {
            Text(timerInterval: adesso...inizio, countsDown: true).monospacedDigit()
        } else {
            Text(inizio, style: .relative)
        }
    }

    private func formazione(_ oggi: Oggi) -> some View {
        Carta("La tua formazione") {
            if let f = oggi.formazione, f.disponibile {
                HStack(alignment: .firstTextBaseline) {
                    Text(f.modulo ?? "—").font(.system(.title, design: .rounded).weight(.bold))
                    Spacer()
                    VStack(alignment: .trailing) {
                        Text(Formato.punti(f.punteggioAtteso)).font(.title2.bold()).monospacedDigit()
                        Text("punti attesi").font(.caption).foregroundStyle(.secondary)
                    }
                }
                .accessibilityElement(children: .combine)
                if oggi.conProbabili == false {
                    Label("Probabili formazioni non ancora uscite", systemImage: "clock").font(.footnote).foregroundStyle(.secondary)
                }
            } else {
                Text("Formazione non disponibile.").foregroundStyle(.secondary)
            }
        }
    }

    @ViewBuilder
    private var daControllare: some View {
        if !vm.daControllare.isEmpty {
            Carta("Da controllare") {
                ForEach(vm.daControllare, id: \.ident) { riga($0) }
            }
        }
    }

    @ViewBuilder
    private var indisponibili: some View {
        if !vm.indisponibili.isEmpty {
            Carta {
                DisclosureGroup("Indisponibili in rosa (\(vm.indisponibili.count))") {
                    VStack(alignment: .leading, spacing: 8) {
                        ForEach(vm.indisponibili, id: \.ident) { riga($0) }
                    }
                    .padding(.top, 6)
                }
                .tint(.secondary)
            }
        }
    }

    private func riga(_ a: Avviso) -> some View {
        HStack(alignment: .top, spacing: 10) {
            BadgeRuolo(ruolo: a.ruolo ?? "?")
            VStack(alignment: .leading, spacing: 2) {
                Text(a.nome).font(.headline)
                Text([a.tipo, a.nota].compactMap { $0 }.joined(separator: ": ")).font(.caption).foregroundStyle(.secondary)
            }
        }
        .accessibilityElement(children: .combine)
    }

    @ViewBuilder
    private func migliori(_ oggi: Oggi) -> some View {
        if let lista = oggi.migliori, !lista.isEmpty {
            Carta("I tuoi migliori della giornata") {
                ForEach(lista) { RigaGiocatore(g: $0) }
            }
        }
    }

    @ViewBuilder
    private func partite(_ oggi: Oggi) -> some View {
        if let lista = oggi.partite, !lista.isEmpty {
            Carta("Partite del turno") {
                ForEach(lista) { p in
                    HStack {
                        Text(Quando.leggibile(p.data)).font(.caption).foregroundStyle(.secondary).frame(minWidth: 100, alignment: .leading)
                        Text("\(p.casa.uppercased()) – \(p.trasferta.uppercased())").font(.subheadline.weight(.semibold))
                        Spacer()
                    }
                    .accessibilityElement(children: .combine)
                }
            }
        }
    }
}

#Preview("Oggi") {
    OggiView(vm: OggiViewModel(server: FinteServer.esempio))
}
