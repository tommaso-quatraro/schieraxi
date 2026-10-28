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
                        intestazione(s)
                        if let p = s.previsione { previsione(p, ruolo: s.calciatore.ruolo) } else { senzaPrevisione }
                        prossime
                        forma(s)
                        rendimento(s)
                        statistiche(s)
                        azioni(s)
                    } else if let e = vm.caricatore.errore {
                        ErroreVista(messaggio: e) { Task { await vm.carica() } }
                    } else {
                        ProgressView().padding(40)
                    }
                }
                .padding(16)
            }
            .refreshable { await vm.carica() }
        }
        .navigationTitle(vm.caricatore.dato?.calciatore.nome ?? "Giocatore")
        .navigationBarTitleDisplayMode(.inline)
        .task { await vm.carica() }
    }

    // MARK: intestazione e previsione

    private func intestazione(_ s: SchedaGiocatore) -> some View {
        let c = s.calciatore
        let p = s.previsione
        return Carta {
            HStack(spacing: 14) {
                AvatarGiocatore(id: c.id, squadra: c.squadraSlug ?? p?.squadra, indice: p?.indice, dimensione: 76)
                VStack(alignment: .leading, spacing: 4) {
                    Text(c.nome).font(.title2.bold()).accessibilityAddTraits(.isHeader)
                    HStack(spacing: 6) {
                        BadgeRuolo(ruolo: c.ruolo, piccolo: true)
                        Text("\(nomeRuolo(c.ruolo).primaMaiuscola) · \((c.squadra ?? "").capitalized)").font(.subheadline).foregroundStyle(.secondary)
                    }
                    Text("Quotazione \(Formato.intero(c.quotazione))").font(.caption).foregroundStyle(.secondary)
                }
                Spacer(minLength: 0)
            }
            .accessibilityElement(children: .combine)
            HStack(spacing: 6) {
                etichetta(s.proprietario ?? "Svincolato", colore: s.proprietario == nil ? .orange : Color.verde)
                if let p { ForEach(Array(p.etichette.prefix(3).enumerated()), id: \.offset) { _, e in etichetta(e.testo, colore: e.gravita.colore) } }
            }
            .fixedSize(horizontal: false, vertical: true)
        }
    }

    private func etichetta(_ testo: String, colore: Color) -> some View {
        Text(testo).font(.caption.weight(.semibold)).foregroundStyle(colore)
            .padding(.horizontal, 8).padding(.vertical, 3)
            .background(colore.opacity(0.15), in: Capsule())
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
        Carta("Prossima partita") {
            Text(descrizionePartita(p)).font(.subheadline).foregroundStyle(.secondary)
            HStack(alignment: .firstTextBaseline) {
                VStack(alignment: .leading, spacing: 0) {
                    Text(Formato.punti(p.fvAtteso)).font(.system(.largeTitle, design: .rounded).weight(.bold)).monospacedDigit()
                    Text("fantavoto atteso").font(.caption).foregroundStyle(.secondary)
                }
                Spacer()
                VStack(alignment: .trailing, spacing: 0) {
                    Text("\(Formato.percento(p.pVoto))%").font(.title2.bold()).monospacedDigit()
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
            Carta("Prossime partite") {
                ProssimePartite(partite: vm.prossime)
                Text("Verde: partita facile. Rosso: partita dura.").font(.caption).foregroundStyle(.secondary)
            }
        }
    }

    // MARK: forma, rendimento, statistiche

    @ViewBuilder
    private func forma(_ s: SchedaGiocatore) -> some View {
        Carta("Forma") {
            if let forma = Forma.calcola(s.voti ?? []) {
                HStack {
                    HStack(spacing: 6) {
                        ForEach(forma.ultime) { v in pallino(v) }
                    }
                    Spacer()
                    VStack(alignment: .trailing, spacing: 0) {
                        Text("Andamento").font(.caption2).foregroundStyle(.secondary)
                        Text("\(forma.andamento.freccia) \(forma.andamento.rawValue)").font(.subheadline.bold())
                            .foregroundStyle(forma.andamento == .crescita ? Color.verde : forma.andamento == .calo ? Color.red : .primary)
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
            Carta("Rende sopra o sotto le occasioni?") {
                HStack(alignment: .firstTextBaseline, spacing: 6) {
                    Text(Formato.conSegno(sovra, cifre: 2)).font(.title.bold()).monospacedDigit()
                        .foregroundStyle(sovra > 0.3 ? Color.verde : sovra < -0.3 ? Color.red : .primary)
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
                    .frame(maxWidth: .infinity, minHeight: 44)
            }
            .buttonStyle(.borderedProminent)
            .accessibilityHint(vm.osservato == true ? "Toglie il giocatore dagli osservati" : "Aggiunge il giocatore agli osservati")
            Button { percorso.append(.sceltaAltro(s.calciatore.id)) } label: {
                Label("Confronta con un altro", systemImage: "arrow.left.arrow.right").frame(maxWidth: .infinity, minHeight: 44)
            }
            .buttonStyle(.bordered)
            if vm.inFormazione {
                Button { percorso.append(.sceltaDallaRosa(s.calciatore.id)) } label: {
                    Label("Confronta con la mia rosa", systemImage: "person.2").frame(maxWidth: .infinity, minHeight: 44)
                }
                .buttonStyle(.bordered)
            }
            if let m = vm.messaggio { Text(m).font(.footnote).foregroundStyle(.secondary) }
        }
    }
}
