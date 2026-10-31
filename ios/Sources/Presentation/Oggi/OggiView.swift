import SwiftUI
import TipKit

/// Schermata Oggi: solo presentazione. Dati e logica sono in `OggiViewModel`.
struct OggiView: View {
    @ObservedObject var vm: OggiViewModel
    @Environment(\.apriGiocatore) private var apri
    @Environment(\.vaiASezione) private var vaiASezione
    @Environment(\.apriNovita) private var apriNovita
    /// L'ultima versione delle novità che l'utente ha guardato (la scrive la pagina Novità).
    @AppStorage("novitaVista") private var novitaVista = ""
    @State private var novitaAnimata = false
    @State private var tutteLeCose = false

    var body: some View {
        NavigationStack {
            ZStack {
                Sfondo()
                ScrollView {
                    Colonne(spazio: Tema.spazioSchede) {
                        if let oggi = vm.oggi {
                            testata(oggi).ingresso(0)
                            daFare(oggi).ingresso(1)
                            novita.ingresso(1)
                            formazione(oggi).ingresso(2)
                            daControllare.ingresso(3)
                            suggerimento
                            migliori(oggi).ingresso(4)
                            indisponibili.ingresso(5)
                            diffidati.ingresso(6)
                            partite.ingresso(7)
                        } else if let errore = vm.errore {
                            ErroreVista(messaggio: errore) { Task { await vm.carica() } }
                        } else {
                            Scheletro(schede: 3, righe: 2, testo: "Preparo la giornata…")
                        }
                    }
                    .padding(.horizontal, Tema.margine)
                    .padding(.bottom, 24)
                    .animation(Tema.morbida, value: vm.oggi != nil)
                }
                .demoInFondo()
                .refreshable { await vm.carica() }
                .avvisoDatiSalvati(vm.datiSalvati)
                .bordiMorbidi()
            }
            .navigationTitle("Oggi")
            .ricercaGlobale()
            .task { await vm.carica() }
        }
    }

    /// Il suggerimento (TipKit) «tocca un giocatore»: compare una volta sola, finché non si apre una scheda.
    @ViewBuilder
    private var suggerimento: some View {
        if !Demo.attivo {
            TipView(Suggerimenti.scheda)
                .tipBackground(Color.sfondoScheda)
        }
    }

    // MARK: riquadro principale

    /// Il riquadro in alto: sfondo vivo, giornata, conto alla rovescia grande e maglia della squadra.
    private func testata(_ oggi: Oggi) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Label("Giornata \(oggi.giornata)", systemImage: "calendar")
                .font(.subheadline.weight(.semibold))
                .padding(.horizontal, 12).padding(.vertical, 6)
                .vetro(in: Capsule())
            // Conto alla rovescia e maglia sulla stessa riga: il riquadro è più basso e il resto di Oggi sale.
            HStack(alignment: .center, spacing: 8) {
                contoAllaRovescia(oggi)
                if let squadra = oggi.formazione?.squadra {
                    StemmaSquadra(nome: squadra, tipo: "maglia", dimensione: 56, nascondiSeMancante: true)
                        .shadow(color: .black.opacity(0.35), radius: 6, y: 3)
                }
            }
            if oggi.conProbabili == false {
                Label("Mancano le probabili formazioni di questa giornata: i consigli usano le presenze recenti.", systemImage: "clock")
                    .font(.footnote)
                    .foregroundStyle(.white.opacity(0.85))
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background { MagiaColori() }
        .clipShape(RoundedRectangle(cornerRadius: 30, style: .continuous))
        .environment(\.colorScheme, .dark)
        .accessibilityElement(children: .contain)
        .accessibilityLabel("Giornata \(oggi.giornata)")
    }

    @ViewBuilder
    private func contoAllaRovescia(_ oggi: Oggi) -> some View {
        if let inizio = Quando.data(oggi.inizio) {
            // Ogni secondo ricontrolla: a zero il conto alla rovescia lascia il posto a «In corso».
            TimelineView(.periodic(from: Date(), by: 1)) { contesto in
                VStack(alignment: .leading, spacing: 4) {
                    if inizio > contesto.date {
                        TestoConto(inizio: inizio, adesso: contesto.date)
                            .font(.system(size: 46, weight: .bold, design: .rounded))
                            .foregroundStyle(.white)
                            .minimumScaleFactor(0.5)
                            .lineLimit(1)
                        Text("alla prima partita, \(Quando.leggibile(oggi.inizio))").font(.subheadline).foregroundStyle(.white.opacity(0.8))
                    } else {
                        Label("In corso", systemImage: "dot.radiowaves.left.and.right")
                            .symbolEffect(.variableColor.iterative, options: .repeating)
                            .font(.system(size: 40, weight: .bold, design: .rounded))
                            .foregroundStyle(.white)
                        Text("iniziata \(Quando.leggibile(oggi.inizio))").font(.subheadline).foregroundStyle(.white.opacity(0.8))
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .accessibilityElement(children: .combine)
            }
        } else {
            Text(oggi.iniziata == true ? "In corso" : "—")
                .font(.system(size: 40, weight: .bold, design: .rounded)).foregroundStyle(.white)
        }
    }

    // MARK: novità

    @ViewBuilder
    private var novita: some View {
        if let versione = vm.novitaDaVedere(ultimaVista: novitaVista) {
            Button { apriNovita() } label: {
                HStack(spacing: 10) {
                    Image(systemName: "sparkles")
                        .symbolRenderingMode(.hierarchical)
                        .symbolEffect(.bounce, value: novitaAnimata)
                        .accessibilityHidden(true)
                    Text("Novità nell'app (versione \(versione)): tocca per vedere")
                        .font(.subheadline.weight(.semibold))
                        .multilineTextAlignment(.leading)
                    Spacer(minLength: 0)
                    Image(systemName: "chevron.right").font(.footnote.weight(.semibold)).foregroundStyle(.secondary).accessibilityHidden(true)
                }
                .foregroundStyle(Color.verde)
                .frame(maxWidth: .infinity, alignment: .leading)
                .frame(minHeight: Tema.areaTocco)
                .padding(.horizontal, 14)
                .background(Color.verde.opacity(0.14), in: RoundedRectangle(cornerRadius: Tema.raggioScheda, style: .continuous))
            }
            .buttonStyle(.plain)
            .accessibilityElement(children: .combine)
            .accessibilityHint("Apre l'elenco delle novità")
            .onAppear { novitaAnimata.toggle() }
        }
    }

    // MARK: formazione e avvisi

    private func formazione(_ oggi: Oggi) -> some View {
        Carta("La tua formazione", simbolo: "sportscourt") {
            if let f = oggi.formazione, f.disponibile {
                HStack(alignment: .firstTextBaseline) {
                    Text(f.modulo ?? "—").font(.system(.largeTitle, design: .rounded).weight(.bold))
                    Spacer()
                    VStack(alignment: .trailing, spacing: 0) {
                        NumeroCheSale(valore: f.punteggioAtteso ?? 0).font(.title2.bold())
                        Text("punti attesi").font(.caption).foregroundStyle(.secondary)
                    }
                }
                .accessibilityElement(children: .combine)
                Button { vaiASezione(.formazione) } label: { Label("Apri la formazione", systemImage: "sportscourt").frame(maxWidth: .infinity, minHeight: Tema.areaTocco) }
                    .pulsanteVetro(prominente: true)
            } else {
                Text("Formazione non disponibile.").foregroundStyle(.secondary)
            }
        }
    }

    /// «Da fare»: le cose che aspettano te, una per riga con il suo pulsante (4 righe, poi «Altre N cose»). Solo se ce n'è almeno una.
    @ViewBuilder
    private func daFare(_ oggi: Oggi) -> some View {
        let cose = oggi.cosePerOrdine
        if !cose.isEmpty {
            let visibili = tutteLeCose ? cose : Array(cose.prefix(4))
            Carta("Da fare", simbolo: "checklist") {
                ForEach(Array(visibili.enumerated()), id: \.element.id) { i, c in
                    RigaConFilo(prima: i == 0) { rigaDaFare(c) }
                }
                if cose.count > 4 {
                    Button {
                        withAnimation(Tema.morbida) { tutteLeCose.toggle() }
                    } label: {
                        Text(tutteLeCose ? "Meno cose" : "Altre \(cose.count - 4) \(cose.count - 4 == 1 ? "cosa" : "cose")")
                            .font(.subheadline.weight(.semibold)).frame(maxWidth: .infinity, minHeight: 44)
                    }
                    .buttonStyle(.plain)
                    .foregroundStyle(Color.verde)
                }
            }
        }
    }

    private func rigaDaFare(_ c: DaFareVoce) -> some View {
        HStack(alignment: .center, spacing: 10) {
            Image(systemName: Self.iconaDaFare(c.tipo))
                .font(.body).foregroundStyle((c.priorita ?? 3) == 1 ? Color.attenzione : .secondary)
                .frame(width: 24)
                .accessibilityHidden(true)
            Text(c.testo).font(.subheadline).fixedSize(horizontal: false, vertical: true)
            Spacer(minLength: 6)
            if let d = c.destinazione?.destinazione {
                Button(c.azione ?? "Apri") { vaiA(d) }
                    .font(.subheadline.weight(.semibold))
                    .buttonStyle(.bordered)
                    .tint(Color.verde)
                    .frame(minHeight: 44)
            }
        }
        .frame(minHeight: 44)
        .accessibilityElement(children: .combine)
    }

    /// Apre la destinazione di una cosa da fare.
    private func vaiA(_ d: Destinazione) {
        if case .sezione(let s) = d { vaiASezione(s) }
        else if case .giocatore(let id) = d { apri(id) }
    }

    static func iconaDaFare(_ tipo: String?) -> String {
        switch tipo {
        case "dubbio": return "exclamationmark.triangle"
        case "formazione": return "sportscourt"
        case "svincolato": return "arrow.triangle.swap"
        case "scambio": return "arrow.left.arrow.right"
        case "rose": return "doc.badge.plus"
        case "certificato": return "clock.badge.exclamationmark"
        case "diario": return "book"
        case "backup": return "externaldrive"
        case "server": return "server.rack"
        case "primo_avvio": return "sparkles"
        default: return "checkmark.circle"
        }
    }

    @ViewBuilder
    private var daControllare: some View {
        if !vm.daControllare.isEmpty {
            Carta("Da controllare", simbolo: "exclamationmark.triangle") {
                Text("Mister, c'è qualche dubbio in formazione. Riguarda le probabili prima del fischio.").font(.caption).foregroundStyle(.secondary)
                ForEach(Array(vm.daControllare.enumerated()), id: \.element.ident) { i, a in
                    RigaConFilo(prima: i == 0) { riga(a) }
                }
            }
        }
    }

    @ViewBuilder
    private var indisponibili: some View {
        if !vm.indisponibili.isEmpty {
            Carta {
                DisclosureGroup("Indisponibili in rosa (\(vm.indisponibili.count))") {
                    VStack(alignment: .leading, spacing: 8) {
                        ForEach(Array(vm.indisponibili.enumerated()), id: \.element.ident) { i, a in
                            RigaConFilo(prima: i == 0) { riga(a) }
                        }
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
            Carta("Diffidati", simbolo: "rectangle.portrait.fill") {
                ForEach(Array(vm.diffidati.enumerated()), id: \.element.ident) { i, a in
                    RigaConFilo(prima: i == 0) { riga(a) }
                }
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

    /// «Dubbio (55%)» come nella web app: per i dubbi, la probabilità di giocare.
    private func etichettaTipo(_ a: Avviso) -> String {
        let nome = nomeTipo(a.tipo)
        if a.tipo == "dubbio", let p = a.pVoto { return "\(nome) (\(Formato.percento(p))%)" }
        return nome
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
                    Text([etichettaTipo(a), a.nota].compactMap { $0 }.joined(separator: ": ")).font(.caption).foregroundStyle(.secondary)
                }
                Spacer(minLength: 0)
                Capsula(testo: etichettaTipo(a), colore: colore(a.tipo)).accessibilityHidden(true)
            }
            .frame(minHeight: 44)
            .contentShape(Rectangle())
            .accessibilityElement(children: .ignore)
            .accessibilityLabel("\(a.nome), \(nomeRuolo(a.ruolo ?? "")), \(etichettaTipo(a))\(a.nota.map { ": " + $0 } ?? "")")
        }
        .buttonStyle(.plain)
        .accessibilityHint("Apre la scheda del giocatore")
    }

    @ViewBuilder
    private func migliori(_ oggi: Oggi) -> some View {
        if let lista = oggi.migliori, !lista.isEmpty {
            Carta("I tuoi migliori della giornata", simbolo: "star.fill") {
                ForEach(Array(lista.enumerated()), id: \.element.id) { i, g in
                    RigaConFilo(prima: i == 0) { RigaGiocatore(g: g, apribile: true) }
                }
            }
        }
    }

    @ViewBuilder
    private var partite: some View {
        let giorni = vm.partitePerGiorno
        if !giorni.isEmpty {
            Carta("Partite del turno", simbolo: "soccerball") {
                ForEach(giorni) { giorno in
                    Text(giorno.titolo).titoletto().padding(.top, 4)
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
