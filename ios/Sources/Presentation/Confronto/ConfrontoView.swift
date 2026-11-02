import SwiftUI

/// «Chi schierare?»: due giocatori a confronto, con le cause spiegate in barre (punti attesi in più per l'uno o per l'altro).
struct ConfrontoView: View {
    @StateObject private var vm: ConfrontoViewModel

    init(a: Int, b: Int, contesto: ContestoConfronto?, server: any ServerClient) {
        _vm = StateObject(wrappedValue: ConfrontoViewModel(a: a, b: b, contesto: contesto, server: server))
    }

    var body: some View {
        ZStack {
            Sfondo()
            ScrollView {
                Colonne(spazio: 14) {
                    if let c = vm.confronto, c.giocatori.count == 2 {
                        duello(c).ingresso(0)
                        verdetto(c).ingresso(1)
                        cause(c).ingresso(2)
                        numeri(c).ingresso(3)
                        motivi(c).ingresso(4)
                    } else if let e = vm.errore {
                        ErroreVista(messaggio: e) { Task { await vm.carica() } }
                    } else {
                        Scheletro(schede: 2, righe: 2, testo: "Metto a confronto i due…")
                    }
                }
                .padding(16)
                .animation(Tema.morbida, value: vm.confronto != nil)
            }
            .refreshable { await vm.carica() }
            .bordiMorbidi()
        }
        .navigationTitle("Chi schierare?")
        .navigationBarTitleDisplayMode(.inline)
        .task { await vm.carica() }
    }

    // MARK: pezzi

    private func duello(_ c: Confronto) -> some View {
        Carta(c.giornata.map { "Giornata \($0)" }) {
            ViewThatFits(in: .horizontal) {
                HStack(alignment: .top, spacing: 8) {
                    colonna(c.giocatori[0], scelto: c.giocatori[0].id == c.consigliato)
                    Text("VS").font(.headline).foregroundStyle(.secondary).padding(.top, 24).accessibilityHidden(true)
                    colonna(c.giocatori[1], scelto: c.giocatori[1].id == c.consigliato)
                }
                VStack(spacing: 12) {
                    colonna(c.giocatori[0], scelto: c.giocatori[0].id == c.consigliato)
                    colonna(c.giocatori[1], scelto: c.giocatori[1].id == c.consigliato)
                }
            }
        }
    }

    private func colonna(_ g: Giocatore, scelto: Bool) -> some View {
        VStack(spacing: 6) {
            AvatarGiocatore(id: g.id, squadra: g.squadra, indice: g.indice, dimensione: 64, nome: g.nome, ruolo: g.ruolo)
            Text(g.nome).font(.headline).multilineTextAlignment(.center).lineLimit(2)
            Text("\(ColoriSquadra.sigla(g.squadra)) – \(ColoriSquadra.sigla(g.avversario)) \(g.inCasa == true ? "casa" : "fuori")")
                .font(.caption).foregroundStyle(.secondary)
            if scelto {
                Label("Consigliato", systemImage: "checkmark.seal.fill").font(.caption.bold()).foregroundStyle(Color.verde)
            }
        }
        .frame(maxWidth: .infinity)
        .padding(10)
        .background(scelto ? Color.verde.opacity(0.14) : Color.clear, in: RoundedRectangle(cornerRadius: Tema.raggioPiccolo + 2, style: .continuous))
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(g.nome), \(nomeRuolo(g.ruolo)), indice \(Formato.intero(g.indice)), punti attesi \(Formato.punti(g.puntiAttesi))\(scelto ? ", consigliato" : "")")
    }

    private func verdetto(_ c: Confronto) -> some View {
        let titolo = c.schierato.map { "Schiera \($0.nome)" } ?? c.vincitore?.nome ?? "—"
        let intestazione = c.formazione == nil ? "Il sistema sceglie" : "Nella formazione (\(c.formazione?.modulo ?? "—"))"
        return Carta(intestazione) {
            Text(titolo).font(.system(.title2, design: .rounded).weight(.bold))
            Text(c.formazione?.testo ?? c.perche ?? "").font(.subheadline).foregroundStyle(.secondary)
        }
    }

    private func cause(_ c: Confronto) -> some View {
        let x = c.giocatori[0], y = c.giocatori[1]
        return Carta(c.formazione != nil ? "Se giocassero da soli" : "Cosa pesa nella scelta") {
            Text("\(c.formazione != nil ? (c.perche ?? "") + " " : "")Punti attesi in più: la barra va verso \(x.nomeCorto) (sinistra) o verso \(y.nomeCorto) (destra). Le cause sommate danno la differenza totale: \(Formato.conSegno(c.differenzaPunti ?? 0, cifre: 2)) per \(x.nomeCorto).")
                .font(.footnote).foregroundStyle(.secondary)
            ForEach(c.fattoriVisibili) { f in fattore(f, c, x, y) }
        }
    }

    private func valore(_ f: FattoreConfronto, _ v: Double?) -> String {
        guard let v else { return "–" }
        return f.percentuale == true ? "\(Formato.percento(v))%" : Formato.decimali(v, cifre: 2)
    }

    private func fattore(_ f: FattoreConfronto, _ c: Confronto, _ x: Giocatore, _ y: Giocatore) -> some View {
        let verso = Confronto.verso(f.effetto)
        let chi = verso > 0 ? x : y
        let testoVerso = verso == 0 ? "pari" : "\(chi.nomeCorto) +\(Formato.decimali(abs(f.effetto), cifre: 2))"
        return VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(f.etichetta).font(.caption).foregroundStyle(.secondary)
                Spacer()
                Text(testoVerso).font(.caption.bold()).foregroundStyle(verso == 0 ? Color.secondary : Color.verde)
            }
            BarraDivergente(effetto: f.effetto, massimo: c.massimoEffetto)
            HStack {
                Text("\(x.nome.split(separator: " ").first.map(String.init) ?? x.nome) \(valore(f, f.a))")
                Spacer()
                Text("\(valore(f, f.b)) \(y.nome.split(separator: " ").first.map(String.init) ?? y.nome)")
            }
            .font(.caption2).foregroundStyle(.secondary)
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(f.etichetta): \(testoVerso). \(x.nomeCorto) \(valore(f, f.a)), \(y.nomeCorto) \(valore(f, f.b))")
    }

    private func numeri(_ c: Confronto) -> some View {
        let x = c.giocatori[0], y = c.giocatori[1]
        func riga(_ titolo: String, _ f: (Giocatore) -> String) -> some View {
            HStack {
                Text(titolo).foregroundStyle(.secondary).frame(maxWidth: .infinity, alignment: .leading)
                Text(f(x)).bold().monospacedDigit().frame(width: 80, alignment: .trailing)
                Text(f(y)).bold().monospacedDigit().frame(width: 80, alignment: .trailing)
            }
            .font(.subheadline)
            .accessibilityElement(children: .ignore)
            .accessibilityLabel("\(titolo): \(x.nomeCorto) \(f(x)), \(y.nomeCorto) \(f(y))")
        }
        return Carta {
            DisclosureGroup("Tutti i numeri") {
                VStack(spacing: 8) {
                    HStack {
                        Spacer()
                        Text(x.nomeCorto).font(.caption.bold()).lineLimit(1).frame(width: 80, alignment: .trailing)
                        Text(y.nomeCorto).font(.caption.bold()).lineLimit(1).frame(width: 80, alignment: .trailing)
                    }
                    .accessibilityHidden(true)
                    riga("Indice") { "\(Formato.intero($0.indice))" }
                    riga("Avversario") { "\(ColoriSquadra.sigla($0.avversario)) \($0.inCasa == true ? "casa" : "fuori")" }
                    riga("Partita") { PillDifficolta.nome($0.difficolta) }
                    riga("Gioca") { "\(Formato.percento($0.pVoto))%" }
                    riga("Fantavoto atteso (se gioca)") { Formato.punti($0.fvAtteso) }
                    riga("Punti attesi") { Formato.decimali($0.puntiAttesi, cifre: 2) }
                    riga("Parte titolare") { "\(Formato.percento($0.quotaTitolare))%" }
                    riga("Segna") { "\(Formato.percento($0.pGol))%" }
                    riga("Assist") { "\(Formato.percento($0.pAssist))%" }
                    riga("Giallo") { "\(Formato.percento($0.pGiallo))%" }
                }
                .padding(.top, 8)
            }
            .tint(.secondary)
        }
    }

    private func motivi(_ c: Confronto) -> some View {
        Carta {
            ForEach(c.giocatori) { g in
                VStack(alignment: .leading, spacing: 2) {
                    Text(g.nome).font(.subheadline.bold())
                    Text((g.motivi ?? []).isEmpty ? "–" : (g.motivi ?? []).joined(separator: " · ")).font(.caption).foregroundStyle(.secondary)
                }
                .accessibilityElement(children: .combine)
            }
        }
    }
}

/// Barra che parte dal centro: verso sinistra se la causa favorisce il primo giocatore, verso destra se favorisce il secondo.
struct BarraDivergente: View {
    let effetto: Double
    let massimo: Double
    /// La barra cresce dal centro quando compare.
    @State private var crescita: CGFloat = 0
    @Environment(\.accessibilityReduceMotion) private var ridotto

    var body: some View {
        GeometryReader { g in
            let meta = g.size.width / 2
            let larghezza = meta * CGFloat(min(1, abs(effetto) / max(massimo, 0.001))) * crescita
            let verso = Confronto.verso(effetto)
            ZStack {
                Capsule().fill(Color.primary.opacity(0.1))
                Rectangle().fill(Color.primary.opacity(0.35)).frame(width: 1.5)
                if verso != 0 {
                    Capsule().fill(Color.verde)
                        .frame(width: max(4, larghezza), height: 8)
                        .offset(x: (verso > 0 ? -1 : 1) * (max(4, larghezza) / 2))
                }
            }
        }
        .frame(height: 10)
        .accessibilityHidden(true)
        .onAppear {
            // Con «Riduci movimento» la barra compare già piena, senza crescere.
            if ridotto { crescita = 1 } else { withAnimation(.smooth(duration: 0.8)) { crescita = 1 } }
        }
    }
}

/// Scelta del giocatore della rosa con cui confrontare quello aperto (stesso ruolo per primi).
struct SceltaDallaRosaView: View {
    @StateObject private var vm: SceltaDallaRosaViewModel
    let scelto: (Int) -> Void

    init(id: Int, server: any ServerClient, scelto: @escaping (Int) -> Void) {
        _vm = StateObject(wrappedValue: SceltaDallaRosaViewModel(id: id, server: server))
        self.scelto = scelto
    }

    var body: some View {
        ZStack {
            Sfondo()
            List {
                if vm.formazione.dato != nil {
                    Section(vm.base.map { "Confronta \($0.nome) con…" } ?? "Confronta con…") {
                        ForEach(vm.candidati) { g in
                            Button { scelto(g.id) } label: {
                                HStack {
                                    RigaGiocatore(g: g)
                                    Text(vm.posto(g.id)).font(.caption2).foregroundStyle(.secondary)
                                }
                                .frame(minHeight: 44)
                            }
                            .buttonStyle(.plain)
                            .accessibilityHint("Confronta i due giocatori")
                        }
                    }
                } else if let e = vm.formazione.errore {
                    ErroreVista(messaggio: e) { Task { await vm.carica() } }
                } else {
                    ScheletroRighe(righe: 5).listRowBackground(Color.clear)
                }
            }
            .scrollContentBackground(.hidden)
        }
        .navigationTitle("Confronta")
        .navigationBarTitleDisplayMode(.inline)
        .task { await vm.carica() }
    }
}

/// Ricerca di un giocatore per nome. Con `alScegliere` il tocco sceglie il giocatore; senza, apre la sua scheda.
struct RicercaGiocatoreView: View {
    let titolo: String
    @StateObject private var vm: RicercaViewModel
    let alScegliere: ((Int) -> Void)?

    init(titolo: String, server: any ServerClient, alScegliere: ((Int) -> Void)?) {
        self.titolo = titolo
        self.alScegliere = alScegliere
        _vm = StateObject(wrappedValue: RicercaViewModel(server: server))
    }

    var body: some View {
        ZStack {
            Sfondo()
            List {
                if let e = vm.errore { Text(e).font(.footnote).foregroundStyle(Color.attenzione) }
                if vm.testo.trimmingCharacters(in: .whitespaces).count < 2 {
                    VStack(spacing: 10) {
                        Image(systemName: "magnifyingglass").font(.largeTitle).foregroundStyle(.secondary).accessibilityHidden(true)
                        Text("Scrivi almeno due lettere del nome.").foregroundStyle(.secondary)
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 40)
                    .listRowBackground(Color.clear)
                } else if vm.risultati.isEmpty && vm.errore == nil && !vm.cercando {
                    ContentUnavailableView.search(text: vm.testo).listRowBackground(Color.clear)
                }
                ForEach(vm.risultati) { g in
                    if let alScegliere {
                        Button { alScegliere(g.id) } label: { riga(g) }.buttonStyle(.plain)
                    } else {
                        NavigationLink(value: PassoScheda.scheda(g.id)) { riga(g) }
                    }
                }
            }
            .scrollContentBackground(.hidden)
        }
        .navigationTitle(titolo)
        .navigationBarTitleDisplayMode(.inline)
        .searchable(text: $vm.testo, placement: .navigationBarDrawer(displayMode: .always), prompt: "Nome del giocatore")
        .task(id: vm.testo) { await vm.cerca() }
    }

    private func riga(_ g: GiocatoreBreve) -> some View {
        FilaAdattiva(spazio: 4) {
            HStack(spacing: 12) {
                BadgeRuolo(ruolo: g.ruolo)
                Text(g.nome).font(.headline)
            }
            Spacer(minLength: 0)
            Text((g.squadra ?? "").capitalized).font(.caption).foregroundStyle(.secondary)
        }
        .frame(minHeight: 44)
        .accessibilityElement(children: .combine)
    }
}

/// La lente accanto al titolo di ogni schermata: cerca un giocatore da qualsiasi sezione.
struct RicercaGlobale: ViewModifier {
    @Environment(\.server) private var server
    @Environment(\.apriImpostazioni) private var apriImpostazioni
    @State private var aperta = false

    func body(content: Content) -> some View {
        content
            .toolbar {
                ToolbarItemGroup(placement: .navigationBarTrailing) {
                    Button { aperta = true } label: { Image(systemName: "magnifyingglass").frame(minWidth: 44, minHeight: 44) }
                        .accessibilityLabel("Cerca un giocatore")
                    // le Impostazioni stanno accanto alla lente in ogni testata (non nei fogli, dove la funzione non c'è)
                    if let apriImpostazioni {
                        Button { apriImpostazioni() } label: { Image(systemName: "gearshape").frame(minWidth: 44, minHeight: 44) }
                            .accessibilityLabel("Impostazioni")
                    }
                }
            }
            .sheet(isPresented: $aperta) { RicercaGlobaleSheet(server: server) }
            .onAppear {
                // Solo per le fotografie del simulatore (argomento -DEMO_SCHERMATA ricerca).
                if Demo.attivo, Demo.schermata == "ricerca", !Demo.ricercaMostrata {
                    Demo.ricercaMostrata = true
                    aperta = true
                }
            }
    }
}

extension View {
    /// Aggiunge la lente della ricerca di un giocatore alla barra della schermata.
    func ricercaGlobale() -> some View { modifier(RicercaGlobale()) }
}

struct RicercaGlobaleSheet: View {
    let server: any ServerClient
    @State private var percorso: [PassoScheda] = []
    @Environment(\.dismiss) private var chiudi

    var body: some View {
        NavigationStack(path: $percorso) {
            RicercaGiocatoreView(titolo: "Cerca un giocatore", server: server, alScegliere: nil)
                .toolbar { ToolbarItem(placement: .navigationBarTrailing) { Button("Chiudi") { chiudi() } } }
                .destinazioniGiocatore(percorso: $percorso, server: server, contesto: nil)
        }
    }
}

/// Sheet di confronto aperto dalla Formazione: due giocatori già scelti (ballottaggio) oppure da scegliere dalla rosa.
struct ConfrontoSheet: View {
    enum Inizio: Identifiable {
        case coppia(Int, Int)
        case scelta(Int)

        var id: String {
            switch self {
            case .coppia(let a, let b): return "coppia-\(a)-\(b)"
            case .scelta(let a): return "scelta-\(a)"
            }
        }
    }

    let inizio: Inizio
    let contesto: ContestoConfronto?
    let server: any ServerClient
    @State private var percorso: [PassoScheda] = []
    @Environment(\.dismiss) private var chiudi

    var body: some View {
        NavigationStack(path: $percorso) {
            radice
                .toolbar { ToolbarItem(placement: .navigationBarTrailing) { Button("Chiudi") { chiudi() } } }
                .destinazioniGiocatore(percorso: $percorso, server: server, contesto: contesto)
        }
    }

    @ViewBuilder
    private var radice: some View {
        switch inizio {
        case .coppia(let a, let b):
            ConfrontoView(a: a, b: b, contesto: contesto, server: server)
        case .scelta(let id):
            SceltaDallaRosaView(id: id, server: server) { altro in percorso.append(.confronto(a: id, b: altro)) }
        }
    }
}
