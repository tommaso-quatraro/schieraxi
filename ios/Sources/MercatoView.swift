import SwiftUI

enum SezioneMercato: String, CaseIterable, Identifiable {
    case consigliati = "Consigliati"
    case classifica = "Classifica"
    case calendario = "Calendario"
    case osservati = "Osservati"
    case cerca = "Cerca"
    var id: String { rawValue }
}

struct MercatoView: View {
    @State private var sezione: SezioneMercato = .consigliati
    @State private var selezionato: Int?
    @EnvironmentObject private var nav: Navigazione

    /// Se l'app è stata aperta da Spotlight su un giocatore, ne mostra la scheda.
    private func apriRichiesto() {
        if let id = nav.giocatoreDaAprire {
            selezionato = id
            nav.giocatoreDaAprire = nil
        }
    }

    var body: some View {
        NavigationStack {
            ZStack {
                Sfondo()
                VStack(spacing: 8) {
                    Picker("Sezione", selection: $sezione) {
                        ForEach(SezioneMercato.allCases) { Text($0.rawValue).tag($0) }
                    }
                    .pickerStyle(.segmented)
                    .padding(.horizontal, 16)
                    contenuto
                }
            }
            .navigationTitle("Mercato")
            .onAppear { apriRichiesto() }
            .onChange(of: nav.giocatoreDaAprire) { _ in apriRichiesto() }
            .sheet(item: Binding(get: { selezionato.map { IdGiocatore(id: $0) } }, set: { selezionato = $0?.id })) { g in
                GiocatoreSheet(id: g.id)
            }
        }
    }

    @ViewBuilder
    private var contenuto: some View {
        switch sezione {
        case .consigliati: ConsigliatiView(apri: { selezionato = $0 })
        case .classifica: ClassificaView(apri: { selezionato = $0 })
        case .calendario: CalendarioView()
        case .osservati: OsservatiView(apri: { selezionato = $0 })
        case .cerca: CercaView(apri: { selezionato = $0 })
        }
    }
}

struct IdGiocatore: Identifiable { let id: Int }

// MARK: - Consigliati

struct ConsigliatiView: View {
    let apri: (Int) -> Void
    @StateObject private var caricatore = Caricatore<Mercato>("/api/mercato")

    var body: some View {
        ScrollView {
            Colonne(spazio: 12) {
                if let m = caricatore.dato {
                    Carta {
                        Text("Svincolati che migliorano la squadra").font(.headline)
                        Text("\(m.svincolati ?? 0) svincolati analizzati. Il guadagno è in punti attesi sulle prossime giornate.")
                            .font(.footnote).foregroundStyle(.secondary)
                    }
                    ForEach(m.proposte) { p in
                        Button { apri(p.entra.id) } label: { carta(p) }.buttonStyle(.plain).puntatore()
                    }
                    if m.proposte.isEmpty {
                        VistaVuota(titolo: "Nessun cambio conviene adesso", icona: "checkmark.circle", descrizione: "La rosa è già la scelta migliore tra gli svincolati.")
                    }
                } else if let e = caricatore.errore {
                    ErroreVista(messaggio: e) { Task { await caricatore.ricarica() } }
                } else {
                    ProgressView("Cerco gli svincolati migliori…").padding(40)
                }
            }
            .padding(.horizontal, 16).padding(.bottom, 24)
        }
        .refreshable { await caricatore.ricarica() }
        .avvisoDatiSalvati(caricatore.datiSalvati)
        .task { await caricatore.ricarica() }
    }

    private func carta(_ p: PropostaMercato) -> some View {
        Carta {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 6) {
                    HStack { BadgeRuolo(ruolo: p.esce.ruolo); Text(p.esce.nome).font(.subheadline); Image(systemName: "arrow.right").font(.caption).foregroundStyle(.secondary) }
                    HStack { BadgeRuolo(ruolo: p.entra.ruolo); Text(p.entra.nome).font(.headline) }
                }
                Spacer()
                VStack(alignment: .trailing) {
                    Text("+" + p.guadagno.formatted(.number.precision(.fractionLength(1)))).font(.title3.bold()).foregroundStyle(Color.verde).monospacedDigit()
                    Text("punti attesi").font(.caption2).foregroundStyle(.secondary)
                }
            }
            if let r = p.rimborso, r > 0 {
                Text("Rimborso svincolo: \(Int(r)) crediti").font(.caption).foregroundStyle(.secondary)
            }
        }
    }
}

// MARK: - Classifica

struct ClassificaView: View {
    let apri: (Int) -> Void
    @StateObject private var caricatore = Caricatore<ElencoGiocatori>("/api/classifica?limite=60")
    @State private var ruolo = "Tutti"
    @State private var liberi = true

    private var percorso: String {
        var p = "/api/classifica?limite=60&liberi=\(liberi ? "true" : "false")"
        if ruolo != "Tutti" { p += "&ruolo=\(ruolo)" }
        return p
    }

    var body: some View {
        ScrollView {
            VStack(spacing: 12) {
                Picker("Ruolo", selection: $ruolo) {
                    ForEach(["Tutti", "P", "D", "C", "A"], id: \.self) { Text($0).tag($0) }
                }
                .pickerStyle(.segmented)
                Toggle("Solo svincolati", isOn: $liberi).tint(Color.verde)
                if let e = caricatore.errore, caricatore.dato == nil {
                    ErroreVista(messaggio: e) { Task { await caricatore.ricarica(percorso) } }
                } else if let d = caricatore.dato {
                    Carta {
                        ForEach(d.giocatori) { g in
                            Button { apri(g.id) } label: { RigaGiocatore(g: g) }.buttonStyle(.plain)
                        }
                    }
                } else {
                    ProgressView().padding(40)
                }
            }
            .padding(.horizontal, 16).padding(.bottom, 24)
        }
        .refreshable { await caricatore.ricarica(percorso) }
        .avvisoDatiSalvati(caricatore.datiSalvati)
        .task(id: percorso) { await caricatore.ricarica(percorso) }
    }
}

// MARK: - Calendario

struct CalendarioView: View {
    @StateObject private var caricatore = Caricatore<Calendario>("/api/calendario")

    private func colore(_ d: Double?) -> Color {
        switch Int(d ?? 3) {
        case ...1: return Color(red: 0.18, green: 0.82, blue: 0.50)
        case 2: return Color(red: 0.56, green: 0.83, blue: 0.29)
        case 3: return Color(red: 0.95, green: 0.78, blue: 0.27)
        case 4: return Color(red: 1.0, green: 0.60, blue: 0.24)
        default: return Color(red: 1.0, green: 0.36, blue: 0.31)
        }
    }

    private func nomeDifficolta(_ d: Double?) -> String {
        switch Int(d ?? 3) {
        case ...1: return "molto facile"
        case 2: return "facile"
        case 3: return "difficoltà media"
        case 4: return "difficile"
        default: return "molto difficile"
        }
    }

    var body: some View {
        ScrollView {
            VStack(spacing: 12) {
                if let c = caricatore.dato {
                    Carta("Difficoltà delle prossime partite") {
                        Text("Verde = facile, rosso = difficile. In ordine di calendario più morbido.").font(.footnote).foregroundStyle(.secondary)
                        ForEach(c.squadre) { s in
                            HStack(spacing: 6) {
                                Text(s.squadra.prefix(3).uppercased()).font(.caption.bold()).frame(width: 36, alignment: .leading)
                                ForEach(s.partite) { p in
                                    Text(String(p.avversario.prefix(3)).uppercased())
                                        .font(.caption2.bold())
                                        .frame(maxWidth: .infinity, minHeight: 28)
                                        .background(colore(p.difficolta).opacity(0.85), in: RoundedRectangle(cornerRadius: 7, style: .continuous))
                                        .foregroundStyle(.black.opacity(0.8))
                                        // La difficoltà non è solo un colore: VoiceOver la dice a parole.
                                        .accessibilityLabel("Giornata \(p.giornata) contro \(p.avversario), \(p.inCasa == true ? "in casa" : "in trasferta"), \(nomeDifficolta(p.difficolta))")
                                }
                            }
                        }
                    }
                } else if let e = caricatore.errore {
                    ErroreVista(messaggio: e) { Task { await caricatore.ricarica() } }
                } else {
                    ProgressView().padding(40)
                }
            }
            .padding(.horizontal, 16).padding(.bottom, 24)
        }
        .refreshable { await caricatore.ricarica() }
        .avvisoDatiSalvati(caricatore.datiSalvati)
        .task { await caricatore.ricarica() }
    }
}

// MARK: - Osservati

struct OsservatiView: View {
    let apri: (Int) -> Void
    @StateObject private var caricatore = Caricatore<ElencoGiocatori>("/api/osservati")
    @State private var messaggio: String?

    var body: some View {
        List {
            if let messaggio { Text(messaggio).font(.footnote).foregroundStyle(.orange) }
            if let d = caricatore.dato {
                if d.giocatori.isEmpty {
                    VistaVuota(titolo: "Nessun giocatore osservato", icona: "star", descrizione: "Apri la scheda di un giocatore e tocca «Osserva».")
                }
                ForEach(d.giocatori) { g in
                    Button { apri(g.id) } label: {
                        VStack(alignment: .leading, spacing: 4) {
                            RigaGiocatore(g: g)
                            if let p = g.proprietario { Text("Di: \(p)").font(.caption).foregroundStyle(.secondary) }
                            else { Text("Svincolato").font(.caption).foregroundStyle(Color.verde) }
                        }
                        .frame(minHeight: 44)
                    }
                    .buttonStyle(.plain)
                    .accessibilityHint("Apre la scheda del giocatore. Azioni disponibili: togli dagli osservati")
                    .accessibilityAction(named: "Togli dagli osservati") { Task { await togli(g.id) } }
                    .swipeActions {
                        Button("Togli", role: .destructive) { Task { await togli(g.id) } }
                    }
                }
            } else if let e = caricatore.errore {
                ErroreVista(messaggio: e) { Task { await caricatore.ricarica() } }
            } else {
                ProgressView().frame(maxWidth: .infinity).padding(40)
            }
        }
        .scrollContentBackground(.hidden)
        .refreshable { await caricatore.ricarica() }
        .avvisoDatiSalvati(caricatore.datiSalvati)
        .task { await carica() }
    }

    private func carica() async {
        await caricatore.ricarica()
        // Gli osservati compaiono anche nella ricerca di iOS (Spotlight).
        if let d = caricatore.dato, caricatore.datiSalvati == nil, !caricatore.dallaCache {
            Spotlight.indicizza(d.giocatori)
        }
    }

    private func togli(_ id: Int) async {
        do {
            try await Api.invia("DELETE", "/api/osservati/\(id)")
            messaggio = nil
            UISelectionFeedbackGenerator().selectionChanged()
        } catch {
            messaggio = error.localizedDescription
            UINotificationFeedbackGenerator().notificationOccurred(.error)
        }
        await carica()
    }
}

// MARK: - Cerca

struct CercaView: View {
    let apri: (Int) -> Void
    @State private var testo = ""
    @State private var risultati: [GiocatoreBreve] = []
    @State private var errore: String?

    var body: some View {
        List {
            if let errore { Text(errore).foregroundStyle(.orange) }
            if testo.count < 2 {
                Text("Scrivi almeno due lettere del nome.").foregroundStyle(.secondary)
            } else if risultati.isEmpty && errore == nil {
                Text("Nessun giocatore trovato.").foregroundStyle(.secondary)
            }
            ForEach(risultati) { g in
                Button { apri(g.id) } label: {
                    HStack(spacing: 12) {
                        BadgeRuolo(ruolo: g.ruolo)
                        Text(g.nome).font(.headline)
                        Spacer()
                        Text(g.squadra ?? "").font(.caption).foregroundStyle(.secondary)
                    }
                    .frame(minHeight: 44)
                    .accessibilityElement(children: .combine)
                }
                .buttonStyle(.plain)
                .accessibilityHint("Apre la scheda del giocatore")
            }
        }
        .scrollContentBackground(.hidden)
        .searchable(text: $testo, placement: .navigationBarDrawer(displayMode: .always), prompt: "Nome del giocatore")
        .task(id: testo) {
            guard testo.count >= 2 else { risultati = []; errore = nil; return }
            try? await Task.sleep(nanoseconds: 300_000_000)
            if Task.isCancelled { return }
            do {
                risultati = try await Api.get("/api/giocatori?limite=25&q=\(Api.codifica(testo))")
                errore = nil
            } catch {
                if Task.isCancelled || error is CancellationError { return }   // si è continuato a scrivere: vale la ricerca nuova
                errore = error.localizedDescription
            }
        }
    }
}

// MARK: - Scheda di un giocatore

struct GiocatoreSheet: View {
    let id: Int
    @StateObject private var caricatore: Caricatore<SchedaGiocatore>
    @State private var messaggio: String?
    @Environment(\.dismiss) private var chiudi

    init(id: Int) {
        self.id = id
        _caricatore = StateObject(wrappedValue: Caricatore<SchedaGiocatore>("/api/giocatore/\(id)"))
    }

    var body: some View {
        NavigationStack {
            ZStack {
                Sfondo()
                ScrollView {
                    VStack(spacing: 14) {
                        if let s = caricatore.dato {
                            intestazione(s)
                            if let p = s.previsione { previsione(p) }
                            if let st = s.stagione { stagione(st) }
                            Button {
                                Task {
                                    do {
                                        try await Api.invia("PUT", "/api/osservati/\(id)")
                                        messaggio = "Aggiunto agli osservati."
                                        UINotificationFeedbackGenerator().notificationOccurred(.success)
                                    } catch { messaggio = error.localizedDescription }
                                }
                            } label: { Label("Osserva", systemImage: "star") }
                                .buttonStyle(.borderedProminent)
                            if let m = messaggio { Text(m).font(.footnote).foregroundStyle(.secondary) }
                        } else if let e = caricatore.errore {
                            ErroreVista(messaggio: e) { Task { await caricatore.ricarica() } }
                        } else {
                            ProgressView().padding(40)
                        }
                    }
                    .padding(16)
                }
            }
            .navigationTitle(caricatore.dato?.calciatore.nome ?? "Giocatore")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .navigationBarTrailing) { Button("Chiudi") { chiudi() } } }
            .task { await caricatore.ricarica() }
        }
    }

    private func intestazione(_ s: SchedaGiocatore) -> some View {
        Carta {
            HStack(spacing: 12) {
                BadgeRuolo(ruolo: s.calciatore.ruolo)
                VStack(alignment: .leading) {
                    Text(s.calciatore.nome).font(.title2.bold())
                    Text(s.calciatore.squadra ?? "").foregroundStyle(.secondary)
                }
                Spacer()
                VStack(alignment: .trailing) {
                    Text("\(Int(s.calciatore.quotazione ?? 0))").font(.title2.bold()).monospacedDigit()
                    Text("quotazione").font(.caption2).foregroundStyle(.secondary)
                }
            }
            Text(s.proprietario.map { "Nella squadra: \($0)" } ?? "Svincolato").font(.footnote).foregroundStyle(.secondary)
        }
    }

    private func previsione(_ p: Giocatore) -> some View {
        Carta("Previsione") {
            dato("Punti attesi", (p.puntiAttesi ?? 0).formatted(.number.precision(.fractionLength(1))))
            dato("Probabilità di giocare", "\(Int(((p.pVoto ?? 0) * 100).rounded()))%")
            dato("Gol attesi", (p.golAttesi ?? 0).formatted(.number.precision(.fractionLength(2))))
            dato("Assist attesi", (p.assistAttesi ?? 0).formatted(.number.precision(.fractionLength(2))))
            if let a = p.avversario { dato("Prossima partita", "\(p.inCasa == true ? "vs" : "@") \(a.uppercased())") }
        }
    }

    private func stagione(_ s: StagioneGiocatore) -> some View {
        Carta("Stagione") {
            dato("Presenze", "\(Int(s.presenze ?? 0))")
            dato("Media voto", (s.mediaVoto ?? 0).formatted(.number.precision(.fractionLength(2))))
            dato("Fantamedia", (s.fantamedia ?? 0).formatted(.number.precision(.fractionLength(2))))
            dato("Gol / assist", "\(Int(s.gol ?? 0)) / \(Int(s.assist ?? 0))")
            dato("Ammonizioni / espulsioni", "\(Int(s.ammonizioni ?? 0)) / \(Int(s.espulsioni ?? 0))")
        }
    }

    private func dato(_ titolo: String, _ valore: String) -> some View {
        HStack { Text(titolo).foregroundStyle(.secondary); Spacer(); Text(valore).monospacedDigit() }
    }
}
