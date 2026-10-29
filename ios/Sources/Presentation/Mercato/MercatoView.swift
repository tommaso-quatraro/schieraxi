import SwiftUI

/// Schermata Mercato: scelta della sezione e scheda del giocatore. Dati e logica sono in `MercatoViewModel`.
struct MercatoView: View {
    @ObservedObject var vm: MercatoViewModel
    @EnvironmentObject private var nav: Navigazione
    @Environment(\.spazioZoom) private var zoom

    /// Se l'app è stata aperta da Spotlight o da un indirizzo schieraxi://giocatore/<id>, mostra la scheda.
    private func apriRichiesto() {
        if let id = nav.giocatoreDaAprire {
            vm.apri(id)
            nav.giocatoreDaAprire = nil
        }
    }

    var body: some View {
        NavigationStack {
            ZStack {
                Sfondo()
                VStack(spacing: 8) {
                    SelettoreSezioni(selezione: $vm.sezione)
                    contenuto
                }
            }
            .navigationTitle("Mercato")
            .ricercaGlobale()
            .onAppear { apriRichiesto() }
            .onChange(of: nav.giocatoreDaAprire) { _, _ in apriRichiesto() }
            .sheet(item: $vm.schedaAperta) { g in
                GiocatoreSheet(id: g.id, server: vm.server)
                    .arrivoZoom(g.id, zoom)
                    .presentationDragIndicator(.visible)
            }
        }
    }

    @ViewBuilder
    private var contenuto: some View {
        switch vm.sezione {
        case .consigliati: ConsigliatiView(vm: vm)
        case .classifica: ClassificaView(vm: vm)
        case .calendario: CalendarioView(vm: vm)
        case .osservati: OsservatiView(vm: vm)
        case .asta: AstaContenuto(vm: vm.asta)
        case .cerca: CercaView(vm: vm)
        }
    }
}

/// Scelta della sezione del Mercato. Sei pulsanti affiancati se ci stanno; altrimenti (schermo stretto o testo grande) una fila
/// di pulsanti che scorre di lato. Un selettore a segmenti qui tagliava i nomi e non cresce col testo.
struct SelettoreSezioni: View {
    @Binding var selezione: SezioneMercato
    @Namespace private var pillole

    var body: some View {
        ViewThatFits(in: .horizontal) {
            HStack(spacing: 6) {
                ForEach(SezioneMercato.allCases) { s in pulsante(s, .footnote, 8) }
            }
            .padding(.horizontal, 12)
            ScrollViewReader { lettore in
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(SezioneMercato.allCases) { s in pulsante(s, .subheadline, 14).id(s) }
                    }
                    .padding(.horizontal, 16)
                }
                .onAppear { lettore.scrollTo(selezione, anchor: .center) }
                .onChange(of: selezione) { _, nuova in withAnimation { lettore.scrollTo(nuova, anchor: .center) } }
            }
        }
    }

    private func pulsante(_ s: SezioneMercato, _ carattere: Font, _ margine: CGFloat) -> some View {
        let attiva = s == selezione
        return Button {
            withAnimation(Tema.molla) { selezione = s }
        } label: {
            Text(s.rawValue)
                .font(carattere.weight(.semibold))
                .lineLimit(1)
                .padding(.horizontal, margine)
                .frame(minHeight: 44)
                .pillola(attiva: attiva, spazio: pillole)
        }
        .buttonStyle(StilePressione())
        .sensoryFeedback(.selection, trigger: selezione)
        .accessibilityAddTraits(attiva ? .isSelected : [])
    }
}

// MARK: - Consigliati

struct ConsigliatiView: View {
    @ObservedObject var vm: MercatoViewModel
    @Environment(\.spazioZoom) private var zoom

    var body: some View {
        ScrollView {
            Colonne(spazio: 12) {
                if let m = vm.consigliati.dato {
                    Carta(simbolo: "arrow.triangle.swap") {
                        Text("Svincolati che migliorano la squadra").font(.headline)
                        Text("Ogni proposta è un cambio: esce uno dei tuoi, entra uno svincolato dello stesso ruolo. \(m.svincolati ?? 0) svincolati analizzati; il guadagno è in punti attesi (prossime giornate una per una, più il resto della stagione).")
                            .font(.footnote).foregroundStyle(.secondary)
                        if let c = m.creditiResidui {
                            Text("Crediti residui: \(Formato.intero(c)). Lo svincolo ti restituisce il \(Formato.percento(m.rimborsoIpotizzato ?? 0.5))% del prezzo pagato.")
                                .font(.footnote).foregroundStyle(.secondary)
                        } else {
                            Text("Inserisci i tuoi crediti in Lega > Crediti per vedere se i cambi sono fattibili.").font(.footnote).foregroundStyle(.secondary)
                        }
                    }
                    ForEach(Array(m.proposte.enumerated()), id: \.element.id) { i, p in
                        Button { vm.apri(p.entra.id) } label: { carta(p) }
                            .buttonStyle(StilePressione()).puntatore()
                            .origineZoom(p.entra.id, zoom)
                            .entraScorrendo()
                            .ingresso(i + 1)
                            .accessibilityHint("Apre la scheda del giocatore")
                    }
                    if m.proposte.isEmpty {
                        VistaVuota(titolo: "Nessun cambio conviene adesso", icona: "checkmark.circle", descrizione: "Mister, la rosa è già la migliore tra gli svincolati.")
                    }
                } else if let e = vm.consigliati.errore {
                    ErroreVista(messaggio: e) { Task { await vm.consigliati.ricarica() } }
                } else {
                    Scheletro(schede: 3, righe: 2, testo: "Cerco gli svincolati…")
                }
            }
            .padding(.horizontal, 16).padding(.bottom, 24)
            .animation(Tema.morbida, value: vm.consigliati.dato != nil)
        }
        .demoInFondo()
        .refreshable { await vm.consigliati.ricarica() }
        .avvisoDatiSalvati(vm.consigliati.datiSalvati)
        .task { await vm.consigliati.ricarica() }
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
                    Text(Formato.conSegno(p.guadagno)).font(.title3.bold()).foregroundStyle(Color.verde).monospacedDigit()
                    Text("punti attesi").font(.caption2).foregroundStyle(.secondary)
                }
            }
            if let b = p.breve {
                Text("\(Formato.conSegno(b)) nelle prossime \(p.giornate?.count ?? 0) giornate").font(.caption).foregroundStyle(.secondary)
            }
            if let dopo = p.creditiDopo {
                Text("Rimborso \(Formato.intero(p.rimborso)) − costo \(Formato.intero(p.entra.quotazione)) · crediti dopo il cambio \(Formato.intero(dopo))\(p.fattibile == false ? " (non bastano)" : "")")
                    .font(.caption).foregroundStyle(p.fattibile == false ? Color.orange : .secondary)
            } else if let r = p.rimborso, r > 0 {
                Text("Rimborso svincolo: \(Formato.intero(r)) crediti").font(.caption).foregroundStyle(.secondary)
            }
        }
    }
}

// MARK: - Classifica

struct ClassificaView: View {
    @ObservedObject var vm: MercatoViewModel
    @Environment(\.spazioZoom) private var zoom

    var body: some View {
        ScrollView {
            VStack(spacing: 12) {
                Picker("Ruolo", selection: $vm.ruolo) {
                    ForEach(["Tutti", "P", "D", "C", "A"], id: \.self) { Text($0).tag($0) }
                }
                .pickerStyle(.segmented)
                Toggle("Solo svincolati", isOn: $vm.soloLiberi).tint(Color.verde)
                if let e = vm.classifica.errore, vm.classifica.dato == nil {
                    ErroreVista(messaggio: e) { Task { await vm.caricaClassifica() } }
                } else if let d = vm.classifica.dato {
                    if d.giocatori.isEmpty {
                        VistaVuota(titolo: "Nessun giocatore", icona: "person.slash", descrizione: "Prova a cambiare ruolo o a togliere il filtro sugli svincolati.")
                    } else {
                        Carta {
                            ForEach(Array(d.giocatori.enumerated()), id: \.element.id) { i, g in
                                RigaConFilo(prima: i == 0) {
                                    Button { vm.apri(g.id) } label: {
                                        VStack(alignment: .leading, spacing: 2) {
                                            RigaGiocatore(g: g)
                                            Text("quot. \(g.quotazione.map { String(Formato.intero($0)) } ?? "–") · \(g.proprietario ?? "svincolato")")
                                                .font(.caption).foregroundStyle(g.proprietario == nil ? Color.verde : .secondary).padding(.leading, 58)
                                        }
                                        .frame(minHeight: 44)
                                    }
                                    .buttonStyle(StilePressione())
                                    .origineZoom(g.id, zoom)
                                    .accessibilityHint("Apre la scheda del giocatore")
                                }
                            }
                        }
                    }
                } else {
                    Scheletro(schede: 1, righe: 6, testo: "Preparo la classifica…")
                }
            }
            .padding(.horizontal, 16).padding(.bottom, 24)
            .animation(Tema.morbida, value: vm.classifica.dato != nil)
        }
        .demoInFondo()
        .refreshable { await vm.caricaClassifica() }
        .avvisoDatiSalvati(vm.classifica.datiSalvati)
        .task(id: vm.percorsoClassifica) { await vm.caricaClassifica() }
    }
}

// MARK: - Calendario

struct CalendarioView: View {
    @ObservedObject var vm: MercatoViewModel

    private func colore(_ d: Double?) -> Color {
        switch Formato.intero(d ?? 3) {
        case ...1: return Color(red: 0.18, green: 0.82, blue: 0.50)
        case 2: return Color(red: 0.56, green: 0.83, blue: 0.29)
        case 3: return Color(red: 0.95, green: 0.78, blue: 0.27)
        case 4: return Color(red: 1.0, green: 0.60, blue: 0.24)
        default: return Color(red: 1.0, green: 0.36, blue: 0.31)
        }
    }

    var body: some View {
        ScrollView {
            VStack(spacing: 12) {
                if let c = vm.calendario.dato {
                    Carta("Difficoltà delle prossime partite", simbolo: "calendar") {
                        Text("Verde = facile, rosso = difficile. In ordine di calendario più morbido.").font(.footnote).foregroundStyle(.secondary)
                        // La griglia è una tabella di sigle di tre lettere: con il testo molto grande smette di crescere
                        // (altrimenti le sigle andavano a capo lettera per lettera).
                        VStack(spacing: 6) {
                            HStack(spacing: 6) {
                                Color.clear.frame(width: 44, height: 1)
                                ForEach(c.giornate, id: \.self) { g in
                                    Text("G\(g)").font(.caption2).foregroundStyle(.secondary).frame(maxWidth: .infinity)
                                }
                            }
                            .accessibilityHidden(true)
                            ForEach(c.squadre) { s in
                                HStack(spacing: 6) {
                                    Text(s.squadra.prefix(3).uppercased())
                                        .font(.caption.bold()).lineLimit(1)
                                        .frame(width: 44, alignment: .leading)
                                    ForEach(s.partite) { p in
                                        Text(String(p.avversario.prefix(3)).uppercased())
                                            .font(.caption2.bold())
                                            .lineLimit(1)
                                            .minimumScaleFactor(0.6)
                                            .frame(maxWidth: .infinity, minHeight: 28)
                                            .background(colore(p.difficolta).opacity(0.85), in: RoundedRectangle(cornerRadius: 7, style: .continuous))
                                            .foregroundStyle(.black.opacity(0.8))
                                            // La difficoltà non è solo un colore: VoiceOver la dice a parole.
                                            .accessibilityLabel("Giornata \(p.giornata) contro \(p.avversario), \(p.inCasa == true ? "in casa" : "in trasferta"), \(Formato.difficolta(p.difficolta))")
                                    }
                                }
                            }
                        }
                        .dynamicTypeSize(...DynamicTypeSize.xLarge)
                    }
                } else if let e = vm.calendario.errore {
                    ErroreVista(messaggio: e) { Task { await vm.calendario.ricarica() } }
                } else {
                    Scheletro(schede: 1, righe: 5, testo: "Guardo il calendario…")
                }
            }
            .padding(.horizontal, 16).padding(.bottom, 24)
            .animation(Tema.morbida, value: vm.calendario.dato != nil)
        }
        .refreshable { await vm.calendario.ricarica() }
        .avvisoDatiSalvati(vm.calendario.datiSalvati)
        .task { await vm.calendario.ricarica() }
    }
}

// MARK: - Osservati

struct OsservatiView: View {
    @ObservedObject var vm: MercatoViewModel

    var body: some View {
        List {
            if let messaggio = vm.messaggioOsservati { Text(messaggio).font(.footnote).foregroundStyle(.orange) }
            if let d = vm.osservati.dato {
                if d.giocatori.isEmpty {
                    VistaVuota(titolo: "Nessun giocatore osservato", icona: "star", descrizione: "Apri la scheda di un giocatore e tocca «Osserva».")
                }
                ForEach(d.giocatori) { g in
                    Button { vm.apri(g.id) } label: {
                        VStack(alignment: .leading, spacing: 4) {
                            RigaGiocatore(g: g)
                            if let p = g.proprietario { Text("Di: \(p)").font(.caption).foregroundStyle(.secondary) }
                            else { Text("Svincolato").font(.caption).foregroundStyle(Color.verde) }
                        }
                    }
                    .buttonStyle(.plain)
                    .accessibilityHint("Apre la scheda del giocatore")
                    .accessibilityAction(named: "Togli dagli osservati") { Task { await vm.togliOsservato(g.id) } }
                    .swipeActions {
                        Button(role: .destructive) { Task { await vm.togliOsservato(g.id) } } label: { Label("Togli", systemImage: "star.slash") }
                    }
                    .contextMenu {
                        Button { vm.apri(g.id) } label: { Label("Apri la scheda", systemImage: "person.text.rectangle") }
                        Button(role: .destructive) { Task { await vm.togliOsservato(g.id) } } label: { Label("Togli dagli osservati", systemImage: "star.slash") }
                    }
                }
            } else if let e = vm.osservati.errore {
                ErroreVista(messaggio: e) { Task { await vm.caricaOsservati() } }
            } else {
                ScheletroRighe(righe: 4).listRowBackground(Color.clear)
            }
        }
        .scrollContentBackground(.hidden)
        .refreshable { await vm.caricaOsservati() }
        .avvisoDatiSalvati(vm.osservati.datiSalvati)
        .task { await vm.caricaOsservati() }
    }
}

// MARK: - Cerca

struct CercaView: View {
    @ObservedObject var vm: MercatoViewModel

    var body: some View {
        List {
            if let errore = vm.erroreRicerca { Text(errore).foregroundStyle(.orange) }
            if vm.testoRicerca.count < 2 {
                VistaVuota(titolo: "Cerca un giocatore", icona: "magnifyingglass", descrizione: "Scrivi almeno due lettere del nome.")
                    .listRowBackground(Color.clear)
            } else if vm.risultati.isEmpty && vm.erroreRicerca == nil {
                ContentUnavailableView.search(text: vm.testoRicerca).listRowBackground(Color.clear)
            }
            ForEach(vm.risultati) { g in
                Button { vm.apri(g.id) } label: {
                    HStack(spacing: 12) {
                        BadgeRuolo(ruolo: g.ruolo)
                        Text(g.nome).font(.headline)
                        Spacer()
                        Text((g.squadra ?? "").capitalized).font(.caption).foregroundStyle(.secondary)
                    }
                    .accessibilityElement(children: .combine)
                }
                .buttonStyle(.plain)
                .accessibilityHint("Apre la scheda del giocatore")
            }
        }
        .scrollContentBackground(.hidden)
        .searchable(text: $vm.testoRicerca, placement: .navigationBarDrawer(displayMode: .always), prompt: "Nome del giocatore")
        .task(id: vm.testoRicerca) { await vm.cerca() }
    }
}

#Preview("Mercato") {
    MercatoView(vm: MercatoViewModel(server: FinteServer.esempio))
        .environmentObject(Navigazione())
}
