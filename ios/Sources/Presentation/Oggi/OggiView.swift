import SwiftUI

/// Schermata Oggi: solo presentazione. Dati e logica sono in `OggiViewModel`.
struct OggiView: View {
    @ObservedObject var vm: OggiViewModel
    @Environment(\.apriGiocatore) private var apri
    @Environment(\.vaiASezione) private var vaiASezione
    @Environment(\.apriNovita) private var apriNovita
    /// L'ultima versione delle novità che l'utente ha guardato (la scrive la pagina Novità).
    @AppStorage("novitaVista") private var novitaVista = ""

    var body: some View {
        NavigationStack {
            ZStack {
                Sfondo()
                ScrollView {
                    Colonne(spazio: 14) {
                        if let oggi = vm.oggi {
                            testata(oggi)
                            novita
                            formazione(oggi)
                            daControllare
                            migliori(oggi)
                            indisponibili
                            diffidati
                            partite
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
            .ricercaGlobale()
            .task { await vm.carica() }
        }
    }

    private func testata(_ oggi: Oggi) -> some View {
        Carta("Giornata \(oggi.giornata)") {
            HStack(alignment: .center, spacing: 12) {
                contoAllaRovescia(oggi)
                Spacer(minLength: 0)
                if let squadra = oggi.formazione?.squadra {
                    StemmaSquadra(nome: squadra, tipo: "maglia", dimensione: 76, nascondiSeMancante: true)
                }
            }
            if oggi.conProbabili == false {
                Label("Mancano le probabili formazioni di questa giornata: i consigli usano le presenze recenti.", systemImage: "clock")
                    .font(.footnote).foregroundStyle(.secondary)
            }
        }
    }

    @ViewBuilder
    private func contoAllaRovescia(_ oggi: Oggi) -> some View {
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

    /// Ore, minuti e secondi se manca meno di un giorno; altrimenti giorni e ore.
    @ViewBuilder
    private func conto(da adesso: Date, a inizio: Date) -> some View {
        if inizio.timeIntervalSince(adesso) < 24 * 3600 {
            Text(timerInterval: adesso...inizio, countsDown: true).monospacedDigit()
        } else {
            Text(inizio, style: .relative)
        }
    }

    // MARK: novità

    @ViewBuilder
    private var novita: some View {
        if let versione = vm.novitaDaVedere(ultimaVista: novitaVista) {
            Button { apriNovita() } label: {
                Label("Novità nell'app (versione \(versione)): tocca per vedere", systemImage: "sparkles")
                    .font(.subheadline.weight(.semibold))
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .frame(minHeight: 44)
                    .padding(.horizontal, 14)
                    .background(Color.verde.opacity(0.18), in: RoundedRectangle(cornerRadius: 16, style: .continuous))
            }
            .buttonStyle(.plain)
            .accessibilityHint("Apre l'elenco delle novità")
        }
    }

    // MARK: formazione e avvisi

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
                Button { vaiASezione(.formazione) } label: { Label("Apri la formazione", systemImage: "sportscourt").frame(maxWidth: .infinity, minHeight: 44) }
                    .buttonStyle(.bordered)
            } else {
                Text("Formazione non disponibile.").foregroundStyle(.secondary)
            }
        }
    }

    @ViewBuilder
    private var daControllare: some View {
        if !vm.daControllare.isEmpty {
            Carta("Da controllare") {
                Text("Giocatori in formazione con qualche dubbio: riguarda le probabili prima della partita.").font(.caption).foregroundStyle(.secondary)
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

    @ViewBuilder
    private var diffidati: some View {
        if !vm.diffidati.isEmpty {
            Carta("Diffidati") {
                ForEach(vm.diffidati, id: \.ident) { riga($0) }
            }
        }
    }

    private func colore(_ tipo: String?) -> Color {
        switch tipo {
        case "infortunato", "squalificato": return .red
        case "dubbio": return .orange
        default: return .yellow
        }
    }

    private func nomeTipo(_ tipo: String?) -> String {
        switch tipo {
        case "infortunato": return "Infortunato"
        case "squalificato": return "Squalificato"
        case "dubbio": return "Dubbio"
        case "diffidato": return "Diffidato"
        default: return (tipo ?? "").primaMaiuscola
        }
    }

    /// Un avviso su un giocatore: un tocco apre la sua scheda. Il pallino colorato dice la gravità (e il testo la ripete).
    private func riga(_ a: Avviso) -> some View {
        Button { apri(a.id) } label: {
            HStack(alignment: .top, spacing: 10) {
                BadgeRuolo(ruolo: a.ruolo ?? "?")
                VStack(alignment: .leading, spacing: 2) {
                    HStack(spacing: 6) {
                        Text(a.nome).font(.headline)
                        Text(ColoriSquadra.sigla(a.squadra)).font(.caption).foregroundStyle(.secondary)
                    }
                    Text([nomeTipo(a.tipo), a.nota].compactMap { $0 }.joined(separator: ": ")).font(.caption).foregroundStyle(.secondary)
                }
                Spacer(minLength: 0)
                Circle().fill(colore(a.tipo)).frame(width: 10, height: 10).padding(.top, 6).accessibilityHidden(true)
            }
            .frame(minHeight: 44)
            .contentShape(Rectangle())
            .accessibilityElement(children: .ignore)
            .accessibilityLabel("\(a.nome), \(nomeRuolo(a.ruolo ?? "")), \(nomeTipo(a.tipo))\(a.nota.map { ": " + $0 } ?? "")")
        }
        .buttonStyle(.plain)
        .accessibilityHint("Apre la scheda del giocatore")
    }

    @ViewBuilder
    private func migliori(_ oggi: Oggi) -> some View {
        if let lista = oggi.migliori, !lista.isEmpty {
            Carta("I tuoi migliori della giornata") {
                ForEach(lista) { RigaGiocatore(g: $0, apribile: true) }
            }
        }
    }

    @ViewBuilder
    private var partite: some View {
        let giorni = vm.partitePerGiorno
        if !giorni.isEmpty {
            Carta("Partite del turno") {
                ForEach(giorni) { giorno in
                    Text(giorno.titolo).font(.subheadline.bold()).foregroundStyle(.secondary).padding(.top, 4)
                        .accessibilityAddTraits(.isHeader)
                    ForEach(giorno.partite) { p in
                        HStack(spacing: 10) {
                            Text(Quando.data(p.data).map { Quando.ora($0) } ?? "–").font(.caption).monospacedDigit().foregroundStyle(.secondary)
                                .frame(minWidth: 44, alignment: .leading)
                            Text("\(p.casa.capitalized) – \(p.trasferta.capitalized)").font(.subheadline.weight(.semibold))
                                .foregroundStyle(p.giocata == true ? Color.secondary : Color.primary)
                            Spacer()
                        }
                        .accessibilityElement(children: .combine)
                    }
                }
            }
        }
    }
}

#Preview("Oggi") {
    OggiView(vm: OggiViewModel(server: FinteServer.esempio))
}
