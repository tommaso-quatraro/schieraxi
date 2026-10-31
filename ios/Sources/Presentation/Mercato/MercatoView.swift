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
        case .giocatori: GiocatoriView(vm: vm, ricerca: vm.ricerca)
        case .calendario: CalendarioView(vm: vm)
        case .osservati: OsservatiView(vm: vm)
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
                // larghezza vera del testo: senza, ViewThatFits crede che ci stia tutto e le etichette si sovrappongono
                .fixedSize(horizontal: true, vertical: false)
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
    @State private var dettagli = false

    var body: some View {
        ScrollView {
            Colonne(spazio: 12) {
                if let m = vm.consigliati.dato {
                    introduzione(m)
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

    /// Una riga di riepilogo; i dettagli (come si calcola, rimborso) stanno dietro la «i».
    private func introduzione(_ m: Mercato) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 8) {
                Text("Svincolati che migliorano la squadra").font(.headline).lineLimit(2)
                Spacer(minLength: 4)
                Button {
                    withAnimation(Tema.morbida) { dettagli.toggle() }
                } label: {
                    Image(systemName: dettagli ? "xmark.circle.fill" : "info.circle")
                        .font(.title3).foregroundStyle(.secondary)
                        .frame(width: 44, height: 44)
                }
                .buttonStyle(.plain)
                .accessibilityLabel(dettagli ? "Nascondi i dettagli" : "Come funziona")
            }
            Text(riassunto(m)).font(.footnote).foregroundStyle(.secondary)
            if dettagli {
                Text(spiegazione(m)).font(.caption).foregroundStyle(.secondary).transition(.opacity)
            }
        }
        .padding(.horizontal, 14).padding(.vertical, 8)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.sfondoScheda, in: RoundedRectangle(cornerRadius: Tema.raggioScheda, style: .continuous))
    }

    private func spiegazione(_ m: Mercato) -> String {
        let base = "Ogni proposta è un cambio: esce uno dei tuoi, entra uno svincolato dello stesso ruolo. Il guadagno è in punti attesi: le prossime giornate una per una, più il resto della stagione."
        if m.creditiResidui == nil { return base + " Inserisci i tuoi crediti in Lega > Crediti per vedere se i cambi sono fattibili." }
        return base + " Lo svincolo ti restituisce il \(Formato.percento(m.rimborsoIpotizzato ?? 0.5))% del prezzo pagato."
    }

    private func riassunto(_ m: Mercato) -> String {
        var parti = ["\(m.svincolati ?? 0) svincolati analizzati"]
        if let c = m.creditiResidui { parti.append("crediti \(Formato.intero(c))") }
        return parti.joined(separator: " · ")
    }

    /// Cambio compatto: l'entrante in primo piano (avatar, nome), l'uscente in piccolo, il guadagno come dato principale a destra,
    /// rimborso e crediti in una riga discreta.
    private func carta(_ p: PropostaMercato) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(alignment: .center, spacing: 10) {
                AvatarGiocatore(id: p.entra.id, squadra: p.entra.squadra, dimensione: 44, conNumero: false, nome: p.entra.nome, ruolo: p.entra.ruolo)
                VStack(alignment: .leading, spacing: 3) {
                    HStack(spacing: 6) {
                        BadgeRuolo(ruolo: p.entra.ruolo, piccolo: true)
                        Text(p.entra.nome).font(.headline).lineLimit(2).minimumScaleFactor(0.8)
                    }
                    HStack(spacing: 5) {
                        Image(systemName: "arrow.uturn.backward").font(.caption2)
                        AvatarGiocatore(id: p.esce.id, squadra: p.esce.squadra, dimensione: 18, conNumero: false, nome: p.esce.nome, ruolo: p.esce.ruolo)
                        Text(p.esce.nome).font(.caption).lineLimit(2)
                    }
                    .foregroundStyle(.secondary)
                }
                Spacer(minLength: 6)
                VStack(alignment: .trailing, spacing: 0) {
                    Text(Formato.conSegno(p.guadagno)).font(.title2.bold()).foregroundStyle(Color.verde).monospacedDigit()
                    Text("punti attesi").font(.caption2).foregroundStyle(.secondary)
                }
                .fixedSize()
            }
            if let riga = dettaglioRiga(p) {
                Text(riga).font(.caption).foregroundStyle(p.fattibile == false ? Color.attenzione : .secondary).lineLimit(2)
            }
        }
        .padding(.horizontal, 14).padding(.vertical, 10)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.sfondoScheda, in: RoundedRectangle(cornerRadius: Tema.raggioScheda, style: .continuous))
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(vocePropostaMercato(p))
    }

    /// «+0,6 nelle prossime 5 · rimborso 8, costo 12, crediti dopo 30»: tutto il secondario in una riga.
    private func dettaglioRiga(_ p: PropostaMercato) -> String? {
        var parti: [String] = []
        if let b = p.breve { parti.append("\(Formato.conSegno(b)) nelle prossime \(p.giornate?.count ?? 0)") }
        if let dopo = p.creditiDopo {
            let nonBastano = p.fattibile == false ? " (non bastano)" : ""
            parti.append("rimborso \(Formato.intero(p.rimborso)), costo \(Formato.intero(p.entra.quotazione)), crediti dopo \(Formato.intero(dopo))" + nonBastano)
        } else if let r = p.rimborso, r > 0 {
            parti.append("rimborso \(Formato.intero(r))")
        }
        return parti.isEmpty ? nil : parti.joined(separator: " · ")
    }

    private func vocePropostaMercato(_ p: PropostaMercato) -> String {
        var testo = "Entra \(p.entra.nome), esce \(p.esce.nome), \(Formato.conSegno(p.guadagno)) punti attesi"
        if let riga = dettaglioRiga(p) { testo += ". " + riga }
        return testo
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
            if let messaggio = vm.messaggioOsservati { Text(messaggio).font(.footnote).foregroundStyle(Color.attenzione) }
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
                        .frame(minHeight: Tema.areaTocco)
                        .contentShape(Rectangle())
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

// MARK: - Giocatori (classifica e ricerca in un elenco)

/// Un solo elenco di giocatori: con il campo di ricerca vuoto è la classifica (con i filtri di ruolo e svincolati), scrivendo almeno
/// due lettere diventano i risultati della ricerca. Ex schede «Classifica» e «Cerca».
struct GiocatoriView: View {
    @ObservedObject var vm: MercatoViewModel
    @ObservedObject var ricerca: RicercaMercatoViewModel

    var body: some View {
        Group {
            if ricerca.abbastanzaLungo {
                CercaView(ricerca: ricerca, apri: { vm.apri($0) })
            } else {
                ClassificaView(vm: vm)
            }
        }
        .searchable(text: $ricerca.testo, placement: .navigationBarDrawer(displayMode: .always), prompt: "Cerca un giocatore")
        .task(id: ricerca.testo) { await ricerca.cerca() }
    }
}

struct CercaView: View {
    @ObservedObject var ricerca: RicercaMercatoViewModel
    let apri: (Int) -> Void

    var body: some View {
        List {
            if let errore = ricerca.errore { Text(errore).foregroundStyle(Color.attenzione) }
            if !ricerca.abbastanzaLungo {
                VistaVuota(titolo: "Cerca un giocatore", icona: "magnifyingglass", descrizione: "Scrivi almeno due lettere del nome.")
                    .listRowBackground(Color.clear)
            } else if ricerca.nessunRisultato {
                ContentUnavailableView.search(text: ricerca.testo).listRowBackground(Color.clear)
            }
            ForEach(ricerca.visibili) { g in
                Button { apri(g.id) } label: {
                    HStack(spacing: 12) {
                        BadgeRuolo(ruolo: g.ruolo)
                        Text(g.nome).font(.headline)
                        Spacer()
                        Text((g.squadra ?? "").capitalized).font(.caption).foregroundStyle(.secondary)
                    }
                    .frame(minHeight: Tema.areaTocco)
                    .accessibilityElement(children: .combine)
                }
                .buttonStyle(.plain)
                .accessibilityHint("Apre la scheda del giocatore")
            }
            if ricerca.ciSonoAltri {
                Button {
                    ricerca.mostraAltri()
                } label: {
                    Text("Mostra altri (\(ricerca.trovati.count - ricerca.visibili.count))").frame(maxWidth: .infinity, minHeight: Tema.areaTocco)
                }
                .accessibilityHint("Mostra altri risultati della ricerca")
            }
        }
        .scrollContentBackground(.hidden)
    }
}

#Preview("Mercato") {
    MercatoView(vm: MercatoViewModel(server: FinteServer.esempio))
        .environmentObject(Navigazione())
}
