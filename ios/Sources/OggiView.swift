import SwiftUI

struct OggiView: View {
    @StateObject private var caricatore = Caricatore<Oggi>("/api/oggi")
    @AppStorage("permessoChiesto") private var permessoChiesto = false

    var body: some View {
        NavigationStack {
            ZStack {
                Sfondo()
                ScrollView {
                    VStack(spacing: 14) {
                        if let oggi = caricatore.dato {
                            testata(oggi)
                            formazione(oggi)
                            daControllare(oggi)
                            migliori(oggi)
                            partite(oggi)
                        } else if let errore = caricatore.errore {
                            ErroreVista(messaggio: errore) { Task { await caricatore.ricarica() } }
                        } else {
                            ProgressView("Carico la giornata…").padding(40)
                        }
                    }
                    .padding(.horizontal, 16)
                    .padding(.bottom, 24)
                }
                .refreshable {
                    await caricatore.ricarica()
                    UINotificationFeedbackGenerator().notificationOccurred(caricatore.errore == nil ? .success : .error)
                }
            }
            .navigationTitle("Oggi")
            .task { await carica() }
        }
    }

    private func carica() async {
        await caricatore.ricarica()
        guard let oggi = caricatore.dato else { return }
        if !permessoChiesto {
            permessoChiesto = true
            _ = await Notifiche.chiediPermesso()
        }
        if let inizio = Quando.data(oggi.inizio) {
            await Notifiche.programma(giornata: oggi.giornata, inizio: inizio, modulo: oggi.formazione?.modulo)
        }
    }

    private func testata(_ oggi: Oggi) -> some View {
        Carta("Giornata \(oggi.giornata)") {
            let adesso = Date()
            if let inizio = Quando.data(oggi.inizio), inizio > adesso {
                Text(timerInterval: adesso...inizio, countsDown: true)
                    .font(.system(size: 40, weight: .bold, design: .rounded))
                    .monospacedDigit()
                Text("alla prima partita, \(Quando.leggibile(oggi.inizio))").font(.subheadline).foregroundStyle(.secondary)
            } else {
                Text(oggi.iniziata == true ? "In corso" : "—").font(.system(size: 40, weight: .bold, design: .rounded))
                Text("iniziata \(Quando.leggibile(oggi.inizio))").font(.subheadline).foregroundStyle(.secondary)
            }
        }
    }

    private func formazione(_ oggi: Oggi) -> some View {
        Carta("La tua formazione") {
            if let f = oggi.formazione {
                HStack(alignment: .firstTextBaseline) {
                    Text(f.modulo ?? "—").font(.system(size: 34, weight: .bold, design: .rounded))
                    Spacer()
                    VStack(alignment: .trailing) {
                        Text((f.punteggioAtteso ?? 0).formatted(.number.precision(.fractionLength(1)))).font(.title2.bold()).monospacedDigit()
                        Text("punti attesi").font(.caption).foregroundStyle(.secondary)
                    }
                }
                if oggi.conProbabili == false {
                    Label("Probabili formazioni non ancora uscite", systemImage: "clock").font(.footnote).foregroundStyle(.secondary)
                }
            } else {
                Text("Formazione non disponibile.").foregroundStyle(.secondary)
            }
        }
    }

    @ViewBuilder
    private func daControllare(_ oggi: Oggi) -> some View {
        let tutti = oggi.avvisi ?? []
        let miei = tutti.filter { $0.inFormazione == true }
        let altri = tutti.filter { $0.inFormazione != true }
        if !miei.isEmpty {
            Carta("Da controllare") {
                ForEach(miei) { riga($0) }
            }
        }
        if !altri.isEmpty {
            Carta {
                DisclosureGroup("Indisponibili in rosa (\(altri.count))") {
                    VStack(alignment: .leading, spacing: 8) {
                        ForEach(altri) { riga($0) }
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
                        Text(Quando.leggibile(p.data)).font(.caption).foregroundStyle(.secondary).frame(width: 110, alignment: .leading)
                        Text("\(p.casa.uppercased()) – \(p.trasferta.uppercased())").font(.subheadline.weight(.semibold))
                        Spacer()
                    }
                }
            }
        }
    }
}
