import SwiftUI

// Le pagine di Squadra che prima stavano in Mercato (la scelta e il contenitore sono in LegaView).

// MARK: - Consigliati

struct ConsigliatiView: View {
    @ObservedObject var vm: MercatoViewModel
    @Environment(\.spazioZoom) private var zoom
    @Environment(\.funzioni) private var funzioni
    @State private var dettagli = false

    var body: some View {
        ScrollView {
            // il titolo intero con il testo grande sta sopra le colonne, non dentro la prima
            VStack(spacing: 12) {
                TitoloNellaPagina()
                Colonne(spazio: 12) {
                    if let m = vm.consigliati.dato {
                        introduzione(m)
                        ForEach(Array(m.proposte.enumerated()), id: \.element.id) { i, p in
                            Button { vm.apri(p.entra.id) } label: { CartaCambio(proposta: p) }
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
            }
            .padding(.horizontal, 16).padding(.bottom, 24)
            .animation(Tema.morbida, value: vm.consigliati.dato != nil)
        }
        .demoInFondo()
        .refreshable { await vm.consigliati.ricarica() }
        .avvisoDatiSalvati(vm.consigliati)
        .task { await vm.consigliati.ricarica() }
    }

    /// Una riga di riepilogo; i dettagli (come si calcola, rimborso) stanno dietro la «i».
    private func introduzione(_ m: Mercato) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 8) {
                Text("Svincolati che migliorano la squadra").font(.headline).fixedSize(horizontal: false, vertical: true)
                Spacer(minLength: 4)
                Button {
                    withAnimation(Tema.morbida) { dettagli.toggle() }
                } label: {
                    Image(systemName: dettagli ? "xmark.circle.fill" : "info.circle")
                        .font(.title3).foregroundStyle(Color.testoSecondario)
                        .frame(width: 44, height: 44)
                }
                .buttonStyle(.plain)
                .accessibilityLabel(dettagli ? "Nascondi i dettagli" : "Come funziona")
            }
            Text(riassunto(m)).font(.footnote).foregroundStyle(Color.testoSecondario)
            if dettagli {
                Text(spiegazione(m)).font(.caption).foregroundStyle(Color.testoSecondario).transition(.opacity)
            }
        }
        .padding(.horizontal, 14).padding(.vertical, 8)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.sfondoScheda, in: RoundedRectangle(cornerRadius: Tema.raggioScheda, style: .continuous))
    }

    private func spiegazione(_ m: Mercato) -> String {
        let base = "Ogni proposta è un cambio: esce uno dei tuoi, entra uno svincolato dello stesso ruolo. Il guadagno è in punti attesi: le prossime giornate una per una, più il resto della stagione."
        if m.creditiResidui == nil {
            let dove = funzioni.acceso(Funzione.squadreAltrui)
                ? "Inserisci i tuoi crediti in Altro > Crediti delle squadre"
                : "Aggiorna le rose in Squadra: i crediti arrivano con il file"
            return base + " \(dove) per vedere se i cambi sono fattibili."
        }
        return base + " Lo svincolo ti restituisce il \(Formato.percento(m.rimborsoIpotizzato ?? 0.5))% del prezzo pagato."
    }

    private func riassunto(_ m: Mercato) -> String {
        var parti = ["\(m.svincolati ?? 0) svincolati analizzati"]
        if let c = m.creditiResidui { parti.append("crediti \(Formato.intero(c))") }
        return parti.joined(separator: " · ")
    }
}

// MARK: - Classifica

struct ClassificaView: View {
    @ObservedObject var vm: MercatoViewModel
    @Environment(\.spazioZoom) private var zoom
    /// La spiegazione completa dei numeri: chiusa, sopra l'elenco resta una riga sola.
    @State private var legendaAperta = false

    var body: some View {
        ScrollView {
            VStack(spacing: 12) {
                TitoloNellaPagina()
                Picker("Ruolo", selection: $vm.ruolo) {
                    ForEach(["Tutti", "P", "D", "C", "A"], id: \.self) { Text($0).tag($0) }
                }
                .pickerStyle(.segmented)
                Toggle("Solo svincolati", isOn: $vm.soloLiberi).tint(Color.verde)
                LegendaElenco(aperta: $legendaAperta)
                if let e = vm.classifica.errore, vm.classifica.dato == nil {
                    ErroreVista(messaggio: e) { Task { await vm.caricaClassifica() } }
                } else if let d = vm.classifica.dato {
                    if d.giocatori.isEmpty {
                        VistaVuota(titolo: "Nessun giocatore", icona: "person.slash", descrizione: "Prova a cambiare ruolo o a togliere il filtro sugli svincolati.")
                    } else {
                        Carta {
                            ForEach(Array(d.giocatori.enumerated()), id: \.element.id) { i, g in
                                RigaConFilo(prima: i == 0) {
                                    Button { vm.apri(g.id) } label: { RigaElencoGiocatore(g: g) }
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
            // Su iPad la tabella non si allarga a tutto lo schermo: colonna centrale leggibile.
            .frame(maxWidth: 760)
            .frame(maxWidth: .infinity)
            .animation(Tema.morbida, value: vm.classifica.dato != nil)
        }
        .demoInFondo()
        .refreshable { await vm.caricaClassifica() }
        .avvisoDatiSalvati(vm.classifica)
        .task(id: vm.percorsoClassifica) { await vm.caricaClassifica() }
    }
}

extension ClassificaView {
    /// Sopra l'elenco: una riga sola, il resto dietro la «i» (prima erano quattro righe che spingevano giù i giocatori).
    static let legendaBreve = "Numero grande: fantavoto atteso se gioca."
    /// Cosa sono gli altri numeri della lista (percentuale, anello, ordine): si apre con la «i».
    static let legenda = "«gioca» è la probabilità che prenda il voto. Il numero sulla foto è l'indice (100 = il migliore del ruolo). In ordine di punti attesi: il fantavoto atteso pesato per la probabilità di giocare."
}

/// La riga di spiegazione sopra l'elenco dei giocatori, con la «i» (44 pt) che apre il resto.
struct LegendaElenco: View {
    @Binding var aperta: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(spacing: 4) {
                Text(ClassificaView.legendaBreve)
                    .font(.caption).foregroundStyle(Color.testoSecondario)
                    // con il testo grande va a capo intera, mai «…» (#247)
                    .fixedSize(horizontal: false, vertical: true)
                    .frame(maxWidth: .infinity, alignment: .leading)
                Button {
                    withAnimation(Tema.morbida) { aperta.toggle() }
                } label: {
                    Image(systemName: aperta ? "xmark.circle.fill" : "info.circle")
                        .font(.title3).foregroundStyle(Color.testoSecondario)
                        .frame(width: Tema.areaTocco, height: Tema.areaTocco)
                        .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .hoverEffect(.highlight)
                .accessibilityLabel(aperta ? "Nascondi la spiegazione" : "Come si leggono i numeri")
            }
            if aperta {
                Text(ClassificaView.legenda)
                    .font(.caption).foregroundStyle(Color.testoSecondario)
                    .fixedSize(horizontal: false, vertical: true)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .transition(.opacity)
            }
        }
    }
}

/// Cosa mostra una riga dell'elenco dei giocatori, come la riga compatta della web (`rigaGiocatoreCompatta`):
/// nome con il ruolo, «GEN · quotazione 19 · svincolato» e a destra il fantavoto atteso (neutro) con «gioca N%».
/// Viene da una riga della giornata (`Giocatore`) o, per chi non c'è, da un risultato della ricerca (`GiocatoreBreve`).
struct DatiRigaElenco: Equatable {
    let id: Int
    let nome: String
    let ruolo: String
    let squadra: String?
    let indice: Double?
    /// «GEN · quotazione 19 · svincolato» (il proprietario solo se lo si conosce).
    let dettaglio: String
    /// Il fantavoto atteso («6,9») o «–».
    let numero: String
    /// «gioca 90%», «non gioca» o niente.
    let sotto: String?
    let voce: String

    static func testoDettaglio(squadra: String?, quotazione: Double?, proprietario: String??) -> String {
        var parti: [String] = []
        let sigla = ColoriSquadra.sigla(squadra)
        if !sigla.isEmpty { parti.append(sigla) }
        parti.append("quotazione \(quotazione.map { String(Formato.intero($0)) } ?? "–")")
        if let proprietario { parti.append(proprietario ?? "svincolato") }
        return parti.joined(separator: " · ")
    }

    init(_ g: Giocatore) {
        id = g.id; nome = g.nome; ruolo = g.ruolo; squadra = g.squadra
        indice = g.assente == true ? nil : g.indice
        dettaglio = Self.testoDettaglio(squadra: g.squadra, quotazione: g.quotazione, proprietario: .some(g.proprietario))
        if g.assente == true {
            numero = "–"
            sotto = "assente"
        } else {
            numero = Formato.punti(g.fvAtteso ?? g.puntiAttesi)
            sotto = "gioca \(Formato.percento(g.pVoto))%"
        }
        var parti = [g.nome, nomeRuolo(g.ruolo), (g.squadra ?? "").capitalized, dettaglio.components(separatedBy: " · ").dropFirst().joined(separator: ", ")]
        if g.assente == true {
            parti.append("assente")
        } else {
            parti.append("\(FantavotoAtteso.nome) \(numero)")
            parti.append("gioca al \(Formato.percento(g.pVoto)) per cento")
            if let i = indice { parti.append("indice \(Formato.intero(i)) su 100") }
        }
        voce = parti.filter { !$0.isEmpty }.joined(separator: ", ")
    }

    /// Chi non è nell'elenco della giornata: «non gioca» solo se l'elenco è arrivato (`nonGioca`).
    init(_ b: GiocatoreBreve, nonGioca: Bool) {
        id = b.id; nome = b.nome; ruolo = b.ruolo; squadra = b.squadra
        indice = nil
        dettaglio = Self.testoDettaglio(squadra: b.squadra, quotazione: b.quotazione, proprietario: nil)
        numero = "–"
        sotto = nonGioca ? "non gioca" : nil
        voce = [b.nome, nomeRuolo(b.ruolo), (b.squadra ?? "").capitalized, "quotazione \(b.quotazione.map { String(Formato.intero($0)) } ?? "–")",
                nonGioca ? "non gioca" : ""].filter { !$0.isEmpty }.joined(separator: ", ")
    }
}

/// Una riga dell'elenco dei giocatori: volto con l'indice, nome, «GEN · quotazione 19 · svincolato», fantavoto atteso e «gioca N%».
/// La usano l'elenco e le due ricerche, così lo stesso giocatore si vede uguale nei tre posti (e come sulla web).
struct RigaElencoGiocatore: View {
    let dati: DatiRigaElenco
    @Environment(\.dynamicTypeSize) private var tagliaTesto
    @ScaledMetric(relativeTo: .body) private var lato: CGFloat = 46

    init(g: Giocatore) { dati = DatiRigaElenco(g) }
    init(breve: GiocatoreBreve, nonGioca: Bool) { dati = DatiRigaElenco(breve, nonGioca: nonGioca) }

    @ViewBuilder
    private var numeri: some View {
        if tagliaTesto.isAccessibilitySize {
            // testo molto grande: i numeri sotto il nome, su una riga, e il nome ha tutta la larghezza
            HStack(spacing: 8) {
                Text(dati.numero).font(.headline).monospacedDigit()
                if let sotto = dati.sotto { Text(sotto).font(.caption).foregroundStyle(Color.testoSecondario) }
            }
        } else {
            VStack(alignment: .trailing, spacing: 2) {
                Text(dati.numero).font(.title3.weight(.bold)).monospacedDigit()
                if let sotto = dati.sotto { Text(sotto).font(.caption2).foregroundStyle(Color.testoSecondario) }
            }
        }
    }

    var body: some View {
        HStack(alignment: tagliaTesto.isAccessibilitySize ? .top : .center, spacing: 12) {
            AvatarGiocatore(id: dati.id, squadra: dati.squadra, indice: dati.indice, dimensione: min(lato, 64), nome: dati.nome, ruolo: dati.ruolo)
            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: 6) {
                    BadgeRuolo(ruolo: dati.ruolo, piccolo: true)
                    // il nome intero: con il testo grande va a capo, mai «…» (#247)
                    Text(dati.nome).font(.headline).fixedSize(horizontal: false, vertical: true)
                }
                Text(dati.dettaglio).font(.caption).foregroundStyle(Color.testoSecondario)
                if tagliaTesto.isAccessibilitySize { numeri }
            }
            Spacer(minLength: 8)
            if !tagliaTesto.isAccessibilitySize { numeri }
        }
        .frame(maxWidth: .infinity, minHeight: Tema.areaTocco, alignment: .leading)
        .contentShape(Rectangle())
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(dati.voce)
    }
}

// MARK: - Calendario

struct CalendarioView: View {
    @ObservedObject var vm: MercatoViewModel

    static let titolo = "Difficoltà delle prossime partite"
    static func spiegazione(giornate: Int) -> String { "Verde = facile, rosso = difficile. In ordine di calendario più morbido." }
    static let legenda = (facile: "", difficile: "")
    static func squadreMie(_ rosa: Rosa?) -> Set<String> { [] }

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
                TitoloNellaPagina()
                if let c = vm.calendario.dato {
                    Carta(Self.titolo, simbolo: "calendar") {
                        Text(Self.spiegazione(giornate: c.giornate.count)).font(.footnote).foregroundStyle(Color.testoSecondario)
                        // La griglia è una tabella di sigle di tre lettere: con il testo molto grande smette di crescere
                        // (altrimenti le sigle andavano a capo lettera per lettera).
                        VStack(spacing: 6) {
                            HStack(spacing: 6) {
                                Color.clear.frame(width: 44, height: 1)
                                ForEach(c.giornate, id: \.self) { g in
                                    Text("G\(g)").font(.caption2).foregroundStyle(Color.testoSecondario).frame(maxWidth: .infinity)
                                }
                            }
                            .accessibilityHidden(true)
                            ForEach(c.squadre) { s in
                                HStack(spacing: 6) {
                                    Text(ColoriSquadra.sigla(s.squadra))
                                        .font(.caption.bold()).lineLimit(1)
                                        .frame(width: 44, alignment: .leading)
                                    ForEach(s.partite) { p in
                                        Text(ProssimePartite.cella(p))
                                            .font(.caption2.bold())
                                            .lineLimit(1)
                                            .minimumScaleFactor(0.6)
                                            .frame(maxWidth: .infinity, minHeight: 28)
                                            .background(colore(p.difficolta).opacity(0.85), in: RoundedRectangle(cornerRadius: 7, style: .continuous))
                                            .foregroundStyle(Color.black)
                                            // La difficoltà non è solo un colore: VoiceOver la dice a parole.
                                            .accessibilityLabel("Serie A, giornata \(p.giornata): contro \(p.avversario), \(p.inCasa == true ? "in casa" : "in trasferta"), \(Formato.difficolta(p.difficolta))")
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
            // Su iPad la tabella non si allarga a tutto lo schermo: colonna centrale leggibile.
            .frame(maxWidth: 760)
            .frame(maxWidth: .infinity)
            .animation(Tema.morbida, value: vm.calendario.dato != nil)
        }
        .refreshable { await vm.calendario.ricarica() }
        .avvisoDatiSalvati(vm.calendario)
        .task { await vm.calendario.ricarica() }
    }
}

// MARK: - Osservati

struct OsservatiView: View {
    @ObservedObject var vm: MercatoViewModel

    var body: some View {
        List {
            TitoloNellaPagina()
            if let messaggio = vm.messaggioOsservati { Text(messaggio).font(.footnote).foregroundStyle(Color.attenzione) }
            if let d = vm.osservati.dato {
                if d.giocatori.isEmpty {
                    VistaVuota(titolo: "Nessun giocatore seguito", icona: "star", descrizione: "Apri la scheda di un giocatore e tocca «Segui».")
                }
                ForEach(d.giocatori) { g in
                    Button { vm.apri(g.id) } label: {
                        VStack(alignment: .leading, spacing: 4) {
                            RigaGiocatore(g: g)
                            if let p = g.proprietario { Text("Di: \(p)").font(.caption).foregroundStyle(Color.testoSecondario) }
                            else { Text("Svincolato").font(.caption).foregroundStyle(Color.verde) }
                        }
                        .frame(minHeight: Tema.areaTocco)
                        .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                    .accessibilityHint("Apre la scheda del giocatore")
                    .accessibilityAction(named: "Non seguire più") { Task { await vm.togliOsservato(g.id) } }
                    .swipeActions {
                        Button(role: .destructive) { Task { await vm.togliOsservato(g.id) } } label: { Label("Togli", systemImage: "star.slash") }
                    }
                    .contextMenu {
                        Button { vm.apri(g.id) } label: { Label("Apri la scheda", systemImage: "person.text.rectangle") }
                        Button(role: .destructive) { Task { await vm.togliOsservato(g.id) } } label: { Label("Non seguire più", systemImage: "star.slash") }
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
        .avvisoDatiSalvati(vm.osservati)
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
    @Environment(\.spazioZoom) private var zoom

    var body: some View {
        ScrollView {
            VStack(spacing: 12) {
                if let errore = ricerca.errore {
                    Text(errore).font(.footnote).foregroundStyle(Color.attenzione)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
                if ricerca.cercando {
                    // prima, mentre cercava, la lista restava vuota (o con i risultati vecchi) senza nessun segno
                    HStack(spacing: 10) { ProgressView(); Text("Cerco…").foregroundStyle(Color.testoSecondario) }
                        .frame(maxWidth: .infinity, minHeight: Tema.areaTocco, alignment: .leading)
                        .accessibilityElement(children: .combine)
                }
                if !ricerca.abbastanzaLungo {
                    VistaVuota(titolo: "Cerca un giocatore", icona: "magnifyingglass", descrizione: "Scrivi almeno due lettere del nome.")
                } else if ricerca.nessunRisultato {
                    ContentUnavailableView.search(text: ricerca.testo)
                }
                if !ricerca.visibili.isEmpty {
                    Carta {
                        ForEach(Array(ricerca.visibili.enumerated()), id: \.element.id) { i, b in
                            RigaConFilo(prima: i == 0) {
                                Button { apri(b.id) } label: { riga(b) }
                                    .buttonStyle(StilePressione())
                                    .origineZoom(b.id, zoom)
                                    .accessibilityHint("Apre la scheda del giocatore")
                            }
                        }
                    }
                }
                if ricerca.ciSonoAltri {
                    Button {
                        ricerca.mostraAltri()
                    } label: {
                        Text("Mostra altri (\(ricerca.trovati.count - ricerca.visibili.count))").frame(maxWidth: .infinity, minHeight: Tema.areaTocco)
                    }
                    .pulsanteVetro()
                    .accessibilityHint("Mostra altri risultati della ricerca")
                }
            }
            .padding(.horizontal, 16).padding(.bottom, 24)
            // Come l'elenco: su iPad una colonna centrale leggibile.
            .frame(maxWidth: 760)
            .frame(maxWidth: .infinity)
        }
        .scrollDismissesKeyboard(.immediately)
    }

    /// Con la previsione della giornata la riga è identica a quella dell'elenco; senza, la stessa forma con «–».
    @ViewBuilder
    private func riga(_ b: GiocatoreBreve) -> some View {
        if let g = ricerca.previsioni.di(b.id) {
            RigaElencoGiocatore(g: g)
        } else {
            RigaElencoGiocatore(breve: b, nonGioca: ricerca.previsioni.arrivate)
        }
    }
}
