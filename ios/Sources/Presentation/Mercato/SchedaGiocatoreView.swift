import SwiftUI

/// Scheda di un giocatore (sheet): previsione, prossime partite, forma e grafico dei voti, statistiche, «Osserva» e confronti.
struct GiocatoreSheet: View {
    let id: Int
    let server: any ServerClient
    let contesto: ContestoConfronto?
    @State private var percorso: [PassoScheda] = []
    @Environment(\.dismiss) private var chiudi

    init(id: Int, server: any ServerClient, contesto: ContestoConfronto? = nil) {
        self.id = id
        self.server = server
        self.contesto = contesto
    }

    var body: some View {
        NavigationStack(path: $percorso) {
            GiocatoreCorpo(id: id, server: server, percorso: $percorso)
                .toolbar { ToolbarItem(placement: .navigationBarTrailing) { Button("Chiudi") { chiudi() } } }
                .destinazioniGiocatore(percorso: $percorso, server: server, contesto: contesto)
        }
    }
}

extension View {
    /// Le pagine che si aprono dentro un `NavigationStack` di giocatori: scheda, confronto, scelta dell'altro giocatore.
    func destinazioniGiocatore(percorso: Binding<[PassoScheda]>, server: any ServerClient, contesto: ContestoConfronto?) -> some View {
        navigationDestination(for: PassoScheda.self) { passo in
            switch passo {
            case .scheda(let id):
                GiocatoreCorpo(id: id, server: server, percorso: percorso)
            case .confronto(let a, let b):
                ConfrontoView(a: a, b: b, contesto: contesto, server: server)
            case .sceltaDallaRosa(let id):
                SceltaDallaRosaView(id: id, server: server) { altro in
                    percorso.wrappedValue.removeLast()
                    percorso.wrappedValue.append(.confronto(a: id, b: altro))
                }
            case .sceltaAltro(let id):
                RicercaGiocatoreView(titolo: "Confronta con…", server: server) { altro in
                    percorso.wrappedValue.removeLast()
                    percorso.wrappedValue.append(.confronto(a: id, b: altro))
                }
            }
        }
    }
}

struct GiocatoreCorpo: View {
    let id: Int
    @StateObject private var vm: SchedaGiocatoreViewModel
    @Binding var percorso: [PassoScheda]
    @Environment(\.dynamicTypeSize) private var tagliaTesto

    init(id: Int, server: any ServerClient, percorso: Binding<[PassoScheda]>) {
        self.id = id
        _vm = StateObject(wrappedValue: SchedaGiocatoreViewModel(id: id, server: server))
        _percorso = percorso
    }

    var body: some View {
        ZStack {
            Sfondo()
            ScrollView {
                Colonne(spazio: 14) {
                    if let s = vm.caricatore.dato {
                        intestazione(s).ingresso(0)
                        if let p = s.previsione { previsione(p, ruolo: s.calciatore.ruolo).ingresso(1) } else { senzaPrevisione }
                        prossime.ingresso(2)
                        forma(s).ingresso(3)
                        rendimento(s)
                        statistiche(s)
                        azioni(s)
                    } else if let e = vm.caricatore.errore {
                        ErroreVista(messaggio: e) { Task { await vm.carica() } }
                    } else {
                        Scheletro(schede: 3, righe: 2, testo: "Apro la scheda…")
                    }
                }
                .padding(16)
                .animation(Tema.morbida, value: vm.caricatore.dato != nil)
            }
            .demoInFondo()
            .refreshable { await vm.carica() }
            .bordiMorbidi()
        }
        .navigationTitle(vm.caricatore.dato?.calciatore.nome ?? "Giocatore")
        .navigationBarTitleDisplayMode(.inline)
        .task { await vm.carica() }
    }

    // MARK: intestazione e previsione

    private func intestazione(_ s: SchedaGiocatore) -> some View {
        let c = s.calciatore
        let p = s.previsione
        let squadra = c.squadraSlug ?? p?.squadra
        let tinta = Color(esadecimale: ColoriSquadra.esadecimali(squadra).0)
        return VStack(spacing: 14) {
            HStack(spacing: 16) {
                AvatarGiocatore(id: c.id, squadra: squadra, indice: p?.indice, dimensione: 96, nome: c.nome, ruolo: c.ruolo)
                VStack(alignment: .leading, spacing: 6) {
                    Text(c.nome).font(.title.bold()).accessibilityAddTraits(.isHeader)
                    HStack(spacing: 6) {
                        BadgeRuolo(ruolo: c.ruolo, piccolo: true)
                        Text("\(nomeRuolo(c.ruolo).primaMaiuscola) · \((c.squadra ?? "").capitalized)").font(.subheadline).foregroundStyle(.secondary)
                    }
                    Text("Quotazione \(Formato.intero(c.quotazione))").font(.caption).foregroundStyle(.secondary)
                }
                Spacer(minLength: 0)
            }
            .accessibilityElement(children: .combine)
            ViewThatFits(in: .horizontal) {
                HStack(spacing: 6) { etichette(s, p) }
                VStack(alignment: .leading, spacing: 6) { etichette(s, p) }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding(18)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background {
            RoundedRectangle(cornerRadius: 30, style: .continuous)
                .fill(LinearGradient(colors: [tinta.opacity(0.42), tinta.opacity(0.10)], startPoint: .topLeading, endPoint: .bottomTrailing))
                .background(Color.sfondoScheda, in: RoundedRectangle(cornerRadius: 30, style: .continuous))
        }
    }

    @ViewBuilder
    private func etichette(_ s: SchedaGiocatore, _ p: Giocatore?) -> some View {
        Capsula(testo: s.proprietario ?? "Svincolato", colore: s.proprietario == nil ? .orange : Color.verde)
        if let p {
            ForEach(Array(p.etichette.prefix(3).enumerated()), id: \.offset) { _, e in
                Capsula(testo: e.testo, colore: e.gravita.colore)
            }
        }
    }

    private var senzaPrevisione: some View {
        Carta {
            Label("Nessuna previsione per la prossima giornata.", systemImage: "info.circle").font(.subheadline).foregroundStyle(.secondary)
        }
    }

    private func descrizionePartita(_ p: Giocatore) -> String {
        var testo = ""
        if let g = p.giornata { testo += "Giornata \(g) · " }
        testo += (p.inCasa == true ? "in casa" : "fuori") + " contro " + (p.avversario ?? "").capitalized
        if let data = p.dataPartita { testo += " · " + Quando.leggibile(data) }
        return testo
    }

    private func previsione(_ p: Giocatore, ruolo: String) -> some View {
        Carta("Prossima partita", simbolo: "soccerball") {
            Text(descrizionePartita(p)).font(.subheadline).foregroundStyle(.secondary)
            HStack(alignment: .firstTextBaseline) {
                VStack(alignment: .leading, spacing: 0) {
                    NumeroCheSale(valore: p.fvAtteso ?? 0).font(.system(size: 44, weight: .bold, design: .rounded))
                    Text("fantavoto atteso").font(.caption).foregroundStyle(.secondary)
                }
                Spacer()
                VStack(alignment: .trailing, spacing: 0) {
                    NumeroCheSale(valore: Double(Formato.percento(p.pVoto)), formato: { "\(Formato.intero($0))%" }).font(.title2.bold())
                    Text("gioca").font(.caption).foregroundStyle(.secondary)
                }
            }
            .accessibilityElement(children: .combine)
            BarraPercentuale(valore: p.pVoto ?? 0)
            HStack {
                PillDifficolta(difficolta: p.difficolta)
                Spacer()
                if p.golSquadra != nil || p.golAvversario != nil {
                    Text("gol attesi \(Formato.decimali(p.golSquadra ?? 0))–\(Formato.decimali(p.golAvversario ?? 0))")
                        .font(.caption).foregroundStyle(.secondary)
                }
            }
            FilaTessere {
                if ruolo == "P" {
                    TesseraDato(valore: "\(Formato.percento(p.portaInviolata))%", etichetta: "porta inviolata")
                    TesseraDato(valore: Formato.decimali(p.golAvversario ?? 0), etichetta: "gol subiti attesi")
                    TesseraDato(valore: "\(Formato.percento(p.pGiallo))%", etichetta: "giallo")
                } else {
                    TesseraDato(valore: "\(Formato.percento(p.pGol))%", etichetta: "segna")
                    TesseraDato(valore: "\(Formato.percento(p.pAssist))%", etichetta: "assist")
                    TesseraDato(valore: "\(Formato.percento(p.pGiallo))%", etichetta: "giallo")
                    TesseraDato(valore: "\(Formato.percento(p.pRosso))%", etichetta: "rosso")
                }
            }
        }
    }

    @ViewBuilder
    private var prossime: some View {
        if !vm.prossime.isEmpty {
            Carta("Prossime partite", simbolo: "calendar") {
                ProssimePartite(partite: vm.prossime)
                Text("Verde: partita facile. Rosso: partita dura.").font(.caption).foregroundStyle(.secondary)
            }
        }
    }

    // MARK: forma, rendimento, statistiche

    @ViewBuilder
    private func forma(_ s: SchedaGiocatore) -> some View {
        Carta("Forma", simbolo: "chart.line.uptrend.xyaxis") {
            if let forma = Forma.calcola(s.voti ?? []) {
                HStack {
                    HStack(spacing: 6) {
                        ForEach(Array(forma.ultime.enumerated()), id: \.element.id) { i, v in
                            pallino(v).ingresso(i + 2)
                        }
                    }
                    Spacer()
                    VStack(alignment: .trailing, spacing: 0) {
                        Text("Andamento").font(.caption2).foregroundStyle(.secondary)
                        Text("\(forma.andamento.freccia) \(forma.andamento.rawValue)").font(.subheadline.bold())
                            .foregroundStyle(forma.andamento == .crescita ? Color.verde : forma.andamento == .calo ? Color.malus : .primary)
                    }
                    .accessibilityElement(children: .combine)
                }
                GraficoVoti(voti: s.voti ?? [])
            } else {
                Text("Nessuna presenza in questa stagione.").font(.subheadline).foregroundStyle(.secondary)
            }
        }
    }

    private func pallino(_ v: VotoGiornata) -> some View {
        let colore: Color = v.fv == nil ? .gray : (v.fv ?? 0) >= 7 ? Color.verde : (v.fv ?? 0) >= 6 ? .orange : .red
        let etichetta = v.fv == nil ? "senza voto" : "fantavoto " + Formato.decimali(v.fv ?? 0)
        return Text(v.fv.map { Formato.decimali($0) } ?? "sv")
            .font(.caption2.bold()).monospacedDigit()
            .foregroundStyle(.white)
            .frame(minWidth: 34, minHeight: 28)
            .background(colore.opacity(0.9), in: RoundedRectangle(cornerRadius: 8, style: .continuous))
            .accessibilityLabel("Giornata \(v.giornata): \(etichetta)")
    }

    @ViewBuilder
    private func rendimento(_ s: SchedaGiocatore) -> some View {
        if let r = s.rendimento, let sovra = r.sovraRendimento {
            Carta("Rende sopra o sotto le occasioni?", simbolo: "scope") {
                HStack(alignment: .firstTextBaseline, spacing: 6) {
                    Text(Formato.conSegno(sovra, cifre: 2)).font(.title.bold()).monospacedDigit()
                        .foregroundStyle(sovra > 0.3 ? Color.verde : sovra < -0.3 ? Color.malus : .primary)
                    Text("punti a partita").font(.caption).foregroundStyle(.secondary)
                }
                .accessibilityElement(children: .combine)
                Text("Gol \(Formato.conSegno(r.golMenoXg ?? 0)) rispetto agli xG · assist \(Formato.conSegno(r.assistMenoXa ?? 0)) rispetto agli xA. "
                     + (sovra > 0.3 ? "Sta segnando più di quanto crea: è probabile che cali."
                        : sovra < -0.3 ? "Crea più di quanto segna: è probabile che si sblocchi." : "In linea con le occasioni che ha."))
                    .font(.footnote).foregroundStyle(.secondary)
            }
        }
    }

    private func statistiche(_ s: SchedaGiocatore) -> some View {
        Carta {
            DisclosureGroup("Tutte le statistiche") {
                VStack(alignment: .leading, spacing: 12) {
                    if let st = s.stagione {
                        Text("Stagione").font(.subheadline.bold())
                        LazyVGrid(columns: [GridItem(.adaptive(minimum: 96), spacing: 10)], spacing: 12) {
                            TesseraDato(valore: "\(Formato.intero(st.presenze))/\(Formato.intero(st.giornateGiocateSerieA))", etichetta: "presenze")
                            TesseraDato(valore: Formato.decimali(st.mediaVoto ?? 0, cifre: 2), etichetta: "media voto")
                            TesseraDato(valore: Formato.decimali(st.fantamedia ?? 0, cifre: 2), etichetta: "fantamedia")
                            TesseraDato(valore: "\(Formato.intero(st.gol) + Formato.intero(st.rigSegnati))", etichetta: "gol (\(Formato.intero(st.rigSegnati)) rig.)")
                            TesseraDato(valore: "\(Formato.intero(st.assist))", etichetta: "assist")
                            TesseraDato(valore: "\(Formato.intero(st.ammonizioni))/\(Formato.intero(st.espulsioni))", etichetta: "gialli/rossi")
                            if s.calciatore.ruolo == "P" {
                                TesseraDato(valore: "\(Formato.intero(st.golSubiti))", etichetta: "gol subiti")
                                TesseraDato(valore: "\(Formato.intero(st.rigParati))", etichetta: "rigori parati")
                            }
                        }
                    }
                    if let a = s.avanzate, (a.minuti ?? 0) > 0 {
                        Text("Statistiche avanzate").font(.subheadline.bold())
                        LazyVGrid(columns: [GridItem(.adaptive(minimum: 96), spacing: 10)], spacing: 12) {
                            TesseraDato(valore: Formato.decimali(a.xg ?? 0, cifre: 2), etichetta: "xG")
                            TesseraDato(valore: Formato.decimali(a.xa ?? 0, cifre: 2), etichetta: "xA")
                            TesseraDato(valore: "\(Formato.intero(a.minuti))'", etichetta: "minuti")
                            TesseraDato(valore: Formato.decimali(a.per90?.xg ?? 0, cifre: 2), etichetta: "xG ogni 90'")
                            TesseraDato(valore: Formato.decimali(a.per90?.xa ?? 0, cifre: 2), etichetta: "xA ogni 90'")
                            TesseraDato(valore: Formato.decimali(a.per90?.tiri ?? 0), etichetta: "tiri ogni 90'")
                            TesseraDato(valore: "\(Formato.intero(a.rigoriCalciati))", etichetta: "rigori calciati")
                            TesseraDato(valore: "\(Formato.intero(a.passaggiChiave))", etichetta: "passaggi chiave")
                            TesseraDato(valore: "\(Formato.intero(a.punizioni))", etichetta: "punizioni tirate")
                        }
                        ForEach(a.stagioniPrecedenti ?? []) { p in
                            Text("Stagione \(p.stagione): \(Formato.intero(p.minuti))' · \(Formato.intero(p.gol)) gol (xG \(Formato.decimali(p.xg ?? 0))) · \(Formato.intero(p.assist)) assist (xA \(Formato.decimali(p.xa ?? 0)))")
                                .font(.caption).foregroundStyle(.secondary)
                        }
                    }
                }
                .padding(.top, 8)
            }
            .tint(.secondary)
        }
    }

    // MARK: azioni

    private func azioni(_ s: SchedaGiocatore) -> some View {
        Carta {
            Button { Task { await vm.alternaOsservato() } } label: {
                Label(vm.osservato == true ? "Osservato" : "Osserva", systemImage: vm.osservato == true ? "star.fill" : "star")
                    .contentTransition(.symbolEffect(.replace))
                    .frame(maxWidth: .infinity, minHeight: 44)
            }
            .pulsanteVetro(prominente: true)
            .sensoryFeedback(.success, trigger: vm.osservato)
            .accessibilityHint(vm.osservato == true ? "Toglie il giocatore dagli osservati" : "Aggiunge il giocatore agli osservati")
            Button { percorso.append(.sceltaAltro(s.calciatore.id)) } label: {
                Label("Confronta con un altro", systemImage: "arrow.left.arrow.right").frame(maxWidth: .infinity, minHeight: 44)
            }
            .pulsanteVetro()
            if vm.inFormazione {
                Button { percorso.append(.sceltaDallaRosa(s.calciatore.id)) } label: {
                    Label("Confronta con la mia rosa", systemImage: "person.2").frame(maxWidth: .infinity, minHeight: 44)
                }
                .pulsanteVetro()
            }
            if let m = vm.messaggio { Text(m).font(.footnote).foregroundStyle(.secondary) }
        }
    }
}
