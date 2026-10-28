import SwiftUI

/// Schermata Mercato: scelta della sezione e scheda del giocatore. Dati e logica sono in `MercatoViewModel`.
struct MercatoView: View {
    @ObservedObject var vm: MercatoViewModel
    @EnvironmentObject private var nav: Navigazione

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
            .onAppear { apriRichiesto() }
            .onChange(of: nav.giocatoreDaAprire) { _ in apriRichiesto() }
            .sheet(item: $vm.schedaAperta) { g in
                GiocatoreSheet(id: g.id, server: vm.server)
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
        case .cerca: CercaView(vm: vm)
        }
    }
}

/// Scelta della sezione del Mercato. Con il testo normale sono cinque pulsanti affiancati; se non ci stanno (testo grande)
/// diventa una fila di pulsanti che scorre di lato. Un selettore a segmenti qui tagliava «Calendario» e non cresce col testo.
struct SelettoreSezioni: View {
    @Binding var selezione: SezioneMercato

    var body: some View {
        ViewThatFits(in: .horizontal) {
            HStack(spacing: 4) {
                ForEach(SezioneMercato.allCases) { s in pulsante(s, .footnote, 6).frame(maxWidth: .infinity) }
            }
            .padding(.horizontal, 16)
            ScrollViewReader { lettore in
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(SezioneMercato.allCases) { s in pulsante(s, .subheadline, 14).id(s) }
                    }
                    .padding(.horizontal, 16)
                }
                .onAppear { lettore.scrollTo(selezione, anchor: .center) }
                .onChange(of: selezione) { nuova in withAnimation { lettore.scrollTo(nuova, anchor: .center) } }
            }
        }
    }

    private func pulsante(_ s: SezioneMercato, _ carattere: Font, _ margine: CGFloat) -> some View {
        let attiva = s == selezione
        return Button {
            selezione = s
            Haptics.selezione()
        } label: {
            Text(s.rawValue)
                .font(carattere.weight(.semibold))
                .lineLimit(1)
                .fixedSize()
                .padding(.horizontal, margine)
                .frame(minHeight: 44)
                .frame(maxWidth: .infinity)
                .background(attiva ? Color.verde.opacity(0.35) : Color.primary.opacity(0.08), in: Capsule())
                .overlay(Capsule().strokeBorder(attiva ? Color.verde : .clear, lineWidth: 1))
        }
        .buttonStyle(.plain)
        .accessibilityAddTraits(attiva ? .isSelected : [])
    }
}

// MARK: - Consigliati

struct ConsigliatiView: View {
    @ObservedObject var vm: MercatoViewModel

    var body: some View {
        ScrollView {
            Colonne(spazio: 12) {
                if let m = vm.consigliati.dato {
                    Carta {
                        Text("Svincolati che migliorano la squadra").font(.headline)
                        Text("\(m.svincolati ?? 0) svincolati analizzati. Il guadagno è in punti attesi sulle prossime giornate.")
                            .font(.footnote).foregroundStyle(.secondary)
                    }
                    ForEach(m.proposte) { p in
                        Button { vm.apri(p.entra.id) } label: { carta(p) }
                            .buttonStyle(.plain).puntatore()
                            .accessibilityHint("Apre la scheda del giocatore")
                    }
                    if m.proposte.isEmpty {
                        VistaVuota(titolo: "Nessun cambio conviene adesso", icona: "checkmark.circle", descrizione: "La rosa è già la scelta migliore tra gli svincolati.")
                    }
                } else if let e = vm.consigliati.errore {
                    ErroreVista(messaggio: e) { Task { await vm.consigliati.ricarica() } }
                } else {
                    ProgressView("Cerco gli svincolati migliori…").padding(40)
                }
            }
            .padding(.horizontal, 16).padding(.bottom, 24)
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
            if let r = p.rimborso, r > 0 {
                Text("Rimborso svincolo: \(Formato.intero(r)) crediti").font(.caption).foregroundStyle(.secondary)
            }
        }
    }
}

// MARK: - Classifica

struct ClassificaView: View {
    @ObservedObject var vm: MercatoViewModel

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
                            ForEach(d.giocatori) { g in
                                Button { vm.apri(g.id) } label: { RigaGiocatore(g: g).frame(minHeight: 44) }
                                    .buttonStyle(.plain)
                                    .accessibilityHint("Apre la scheda del giocatore")
                            }
                        }
                    }
                } else {
                    ProgressView().padding(40)
                }
            }
            .padding(.horizontal, 16).padding(.bottom, 24)
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
                    Carta("Difficoltà delle prossime partite") {
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
                    ProgressView().padding(40)
                }
            }
            .padding(.horizontal, 16).padding(.bottom, 24)
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
                        Button("Togli", role: .destructive) { Task { await vm.togliOsservato(g.id) } }
                    }
                }
            } else if let e = vm.osservati.errore {
                ErroreVista(messaggio: e) { Task { await vm.caricaOsservati() } }
            } else {
                ProgressView().frame(maxWidth: .infinity).padding(40)
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
                Text("Scrivi almeno due lettere del nome.").foregroundStyle(.secondary)
            } else if vm.risultati.isEmpty && vm.erroreRicerca == nil {
                Text("Nessun giocatore trovato.").foregroundStyle(.secondary)
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
