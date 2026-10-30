import SwiftUI

/// Schermata Scambi: solo presentazione. Dati e logica sono in `ScambiViewModel`.
struct ScambiView: View {
    @ObservedObject var vm: ScambiViewModel

    var body: some View {
        NavigationStack(path: $vm.percorso) {
            ZStack {
                Sfondo()
                ScrollView {
                    Colonne(spazio: Tema.spazioSchede) {
                        filtro.ingresso(0)
                        offerta.ingresso(1)
                        if let d = vm.proposte.dato {
                            squadrePropense.ingresso(2)
                            if d.proposte.isEmpty {
                                VistaVuota(titolo: "Nessuno scambio per ora", icona: "arrow.left.arrow.right", descrizione: "Per ora non c'è niente che convenga a tutti e due.")
                            }
                            ForEach(Array(d.proposte.enumerated()), id: \.element.id) { i, p in
                                Button { vm.giudizioSelezionata = nil; vm.selezionata = p } label: { carta(p) }
                                    .buttonStyle(StilePressione()).puntatore()
                                    .entraScorrendo()
                                    .ingresso(i + 3)
                                    .accessibilityHint("Mostra il dettaglio dello scambio")
                            }
                        } else if let e = vm.proposte.errore {
                            ErroreVista(messaggio: e) { Task { await vm.caricaProposte() } }
                        } else {
                            Scheletro(schede: 3, righe: 2, testo: "Guardo gli scambi…")
                        }
                        archivio
                    }
                    .padding(.horizontal, 16).padding(.bottom, 24)
                    .animation(Tema.morbida, value: vm.proposte.dato != nil)
                }
                .demoInFondo()
                .refreshable { await vm.caricaProposte() }
                .avvisoDatiSalvati(vm.proposte.datiSalvati)
                .bordiMorbidi()
            }
            .navigationTitle("Scambi")
            .ricercaGlobale()
            .navigationDestination(for: PaginaScambi.self) { _ in AnalizzaScambioView(server: vm.server) }
            .task { await vm.caricaSquadre() }
            // Niente ricerca automatica: con gli account ogni ricerca conta tra quelle del giorno. Si cerca con il pulsante.
            // In modalità demo (fotografie) sì, per vedere le proposte.
            .task { if Demo.attivo, vm.proposte.dato == nil { await vm.caricaProposte() } }
            .onAppear { vm.caricaArchivio() }
            .sheet(item: $vm.selezionata) { p in
                NavigationStack {
                    ZStack { Sfondo(); ScrollView { DettaglioScambio(p: p, giudizio: vm.giudizioSelezionata).padding(16) } }
                        .navigationTitle("Scambio")   // la squadra è già nella scheda «Punti attesi» (un titolo lungo veniva tagliato)
                        .navigationBarTitleDisplayMode(.inline)
                        .toolbar {
                            ToolbarItem(placement: .navigationBarTrailing) { Button("Chiudi") { vm.selezionata = nil } }
                        }
                }
                .presentationDetents([.medium, .large])
                .presentationDragIndicator(.visible)
            }
        }
    }

    // MARK: filtro e offerta ricevuta

    private var filtro: some View {
        Carta {
            Picker("Con", selection: $vm.con) {
                Text("Tutte le squadre").tag("Tutte")
                ForEach(vm.altre) { Text($0.nome).tag($0.nome) }
            }
            Picker("Dimensione", selection: $vm.fino) {
                Text("1 contro 1").tag(1)
                Text("fino a 2").tag(2)
                Text("fino a 3").tag(3)
                Text("fino a 4").tag(4)
            }
            .pickerStyle(.segmented)
            .disabled(vm.con == "Tutte")
            .onChange(of: vm.con) { _, nuova in if nuova == "Tutte" { vm.fino = 1 } }
            .accessibilityLabel("Quanti giocatori per lato")
            if vm.con == "Tutte" {
                Text("Per gli scambi più grandi (2, 3 o 4 per lato) scegli una squadra. Più giocatori = ricerca più lenta.").font(.caption).foregroundStyle(.secondary)
            } else if vm.fino >= 2 {
                Text("Più giocatori per lato = ricerca più lenta (può volerci qualche secondo).").font(.caption).foregroundStyle(.secondary)
            }
            Button { Task { await vm.caricaProposte() } } label: {
                Label(vm.proposte.inCorso ? "Cerco…" : "Cerca scambi", systemImage: "magnifyingglass")
                    .frame(maxWidth: .infinity, minHeight: 44)
            }
            .pulsanteVetro(prominente: true)
            .disabled(vm.proposte.inCorso)
            NavigationLink(value: PaginaScambi.analizza) {
                Label("Analizza uno scambio a mano", systemImage: "slider.horizontal.3").frame(minHeight: 44)
            }
            if let m = vm.messaggio { Text(m).font(.footnote).foregroundStyle(Color.verde) }
        }
    }

    private var offerta: some View {
        Carta("Ho ricevuto un'offerta", simbolo: "envelope.open") {
            Text("Incolla il messaggio (basta che ci siano i cognomi): trovo chi dai e chi ricevi e ti dico se conviene.")
                .font(.footnote).foregroundStyle(.secondary)
            TextEditor(text: $vm.testoOfferta)
                .scrollContentBackground(.hidden)
                .frame(minHeight: 96)
                .padding(8)
                .background(Color.sfondoIncavo, in: RoundedRectangle(cornerRadius: Tema.raggioPiccolo, style: .continuous))
                .overlay(alignment: .topLeading) {
                    if vm.testoOfferta.isEmpty {
                        Text("Es. Ti do Rowe e Giocatore 077, mi dai Giocatore 014?").foregroundStyle(.secondary).padding(.horizontal, 13).padding(.vertical, 16)
                            .allowsHitTesting(false).accessibilityHidden(true)
                    }
                }
                .accessibilityLabel("Messaggio dell'offerta")
            Button { Task { await vm.valutaOfferta() } } label: {
                if vm.offertaInCorso { ProgressView().frame(maxWidth: .infinity, minHeight: 44) }
                else { Text("Valuta l'offerta").frame(maxWidth: .infinity, minHeight: 44) }
            }
            .pulsanteVetro(prominente: true)
            .disabled(vm.offertaInCorso)
            .sensoryFeedback(trigger: vm.esitoOfferta?.analisi?.id) { _, nuovo in nuovo != nil ? .success : nil }
            if let e = vm.erroreOfferta { Text(e).font(.footnote).foregroundStyle(Color.attenzione) }
            if let o = vm.esitoOfferta { esitoOfferta(o) }
        }
    }

    @ViewBuilder
    private func esitoOfferta(_ o: OffertaRiconosciuta) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            if let con = o.con { riga("Con", [con]) }
            riga("Dai", o.`do`)
            riga("Ricevi", o.ricevo)
        }
        if let ambigui = o.ambigui, !ambigui.isEmpty {
            Label("Più giocatori con lo stesso cognome: \(ambigui.joined(separator: "; ")). Usa «Analizza uno scambio a mano» per sceglierli.", systemImage: "exclamationmark.triangle")
                .font(.footnote).foregroundStyle(Color.attenzione)
        }
        if let analisi = o.analisi {
            Text(ScambiLogica.giudizioOfferta(analisi)).font(.headline)
            Button {
                vm.giudizioSelezionata = ScambiLogica.giudizioOfferta(analisi)
                vm.selezionata = analisi
            } label: { Label("Vedi il dettaglio", systemImage: "chart.bar").frame(minHeight: 44) }
        } else {
            Label("Non ho trovato giocatori di tutte e due le squadre nel messaggio: controlla i cognomi, oppure usa «Analizza uno scambio a mano».", systemImage: "questionmark.circle")
                .font(.footnote).foregroundStyle(.secondary)
        }
    }

    private func riga(_ titolo: String, _ nomi: [String]) -> some View {
        HStack(alignment: .firstTextBaseline) {
            Text(titolo).font(.caption.bold()).foregroundStyle(.secondary).frame(width: 54, alignment: .leading)
            Text(nomi.isEmpty ? "–" : nomi.joined(separator: ", ")).font(.subheadline)
        }
        .accessibilityElement(children: .combine)
    }

    // MARK: proposte

    @ViewBuilder
    private var squadrePropense: some View {
        let elenco = vm.propense
        if !elenco.isEmpty {
            Carta("Chi accetta più volentieri", simbolo: "person.2.fill") {
                Text("Le squadre che guadagnano di più dagli scambi qui sotto, e il reparto che ne beneficia di più.").font(.footnote).foregroundStyle(.secondary)
                ForEach(elenco) { x in
                    HStack(alignment: .firstTextBaseline) {
                        StemmaSquadra(nome: x.nome, dimensione: 28, nascondiSeMancante: true)
                        VStack(alignment: .leading, spacing: 1) {
                            Text(x.nome).font(.subheadline.bold())
                            Text("\(x.scambi) \(x.scambi == 1 ? "scambio" : "scambi")\(dettaglioReparto(x))").font(.caption).foregroundStyle(.secondary)
                        }
                        Spacer()
                        Text(Formato.conSegno(x.media)).font(.headline).monospacedDigit().foregroundStyle(Color.verde)
                    }
                    .accessibilityElement(children: .combine)
                }
            }
        }
    }

    private func dettaglioReparto(_ x: ScambiLogica.SquadraPropensa) -> String {
        guard let r = x.reparto, let m = x.miglioramento, m > 0 else { return "" }
        return " · migliora i \(nomeRuoloPlurale(r)) di \(Formato.conSegno(m))%"
    }

    private func nomeRuoloPlurale(_ r: String) -> String {
        ["P": "portieri", "D": "difensori", "C": "centrocampisti", "A": "attaccanti"][r] ?? r
    }

    private func carta(_ p: PropostaScambio) -> some View {
        Carta {
            HStack(spacing: 8) {
                StemmaSquadra(nome: p.altra, dimensione: 26, nascondiSeMancante: true)
                Text("con \(p.altra)").font(.caption).foregroundStyle(.secondary)
            }
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 4) {
                    ForEach(p.`do`) { g in HStack { BadgeRuolo(ruolo: g.ruolo); Text(g.nome).font(.subheadline) } }
                    Image(systemName: "arrow.down").font(.caption).foregroundStyle(.secondary).accessibilityLabel("in cambio di")
                    ForEach(p.ricevo) { g in HStack { BadgeRuolo(ruolo: g.ruolo); Text(g.nome).font(.headline) } }
                }
                Spacer()
                VStack(alignment: .trailing, spacing: 4) {
                    guadagno("tu", p.guadagnoMio)
                    guadagno("loro", p.guadagnoLoro)
                }
            }
            Button { vm.copiaBozza(p) } label: { Label("Copia la bozza del messaggio", systemImage: "doc.on.doc").font(.subheadline).frame(maxWidth: .infinity, minHeight: 44) }
                .pulsanteVetro()
        }
    }

    private func guadagno(_ chi: String, _ v: Double) -> some View {
        HStack(spacing: 4) {
            Text(chi).font(.caption2).foregroundStyle(.secondary)
            Text(Formato.conSegno(v)).font(.headline).monospacedDigit().foregroundStyle(v >= 0 ? Color.verde : .orange)
        }
        .accessibilityElement(children: .combine)
    }

    // MARK: archivio

    @ViewBuilder
    private var archivio: some View {
        if !vm.archivio.isEmpty {
            Carta {
                DisclosureGroup("Archivio (\(vm.archivio.count))") {
                    VStack(alignment: .leading, spacing: 10) {
                        Text("Gli ultimi scambi che hai analizzato.").font(.caption).foregroundStyle(.secondary)
                        ForEach(vm.archivio) { v in
                            HStack(alignment: .top) {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text("\(v.dai.joined(separator: ", ")) ⇄ \(v.ricevo.joined(separator: ", "))").font(.subheadline.bold())
                                    Text("con \(v.con) · \(v.quando.formatted(.dateTime.day().month(.abbreviated).locale(Formato.locale)))").font(.caption).foregroundStyle(.secondary)
                                }
                                Spacer()
                                VStack(alignment: .trailing, spacing: 0) {
                                    Text(Formato.conSegno(v.mio)).font(.headline).monospacedDigit().foregroundStyle(v.mio >= 0 ? Color.verde : .orange)
                                    if let pc = v.percentuale { Text("\(Formato.conSegno(pc))%").font(.caption2).foregroundStyle(.secondary) }
                                }
                            }
                            .accessibilityElement(children: .combine)
                        }
                        Button("Svuota l'archivio", role: .destructive) { vm.svuotaArchivio() }.frame(minHeight: 44)
                    }
                    .padding(.top, 6)
                }
                .tint(.secondary)
            }
        }
    }
}

/// Dettaglio di uno scambio: cosa dai, cosa ricevi, quanto guadagna ciascuno giornata per giornata, impatto sui reparti.
struct DettaglioScambio: View {
    let p: PropostaScambio
    /// Un giudizio a parole da mostrare in fondo (per l'analisi a mano e per le offerte).
    var giudizio: String? = nil

    var body: some View {
        VStack(spacing: 14) {
            Carta("Dai") { ForEach(p.`do`) { g in elenco(g) } }
            Carta("Ricevi") { ForEach(p.ricevo) { g in elenco(g) } }
            Carta("Punti attesi") {
                riga("Tu", p.guadagnoMio)
                riga("\(p.altra)", p.guadagnoLoro)
                if let q = p.quotazioneDo, let r = p.quotazioneRicevo {
                    Text("Quotazioni: \(Formato.intero(q)) → \(Formato.intero(r))").font(.caption).foregroundStyle(.secondary)
                }
                if let g = p.giornate, let a = p.perGiornataMio, let b = p.perGiornataLoro, g.count == a.count, g.count == b.count, !g.isEmpty {
                    Divider()
                    Text("Giornata per giornata (prossime \(g.count))").font(.subheadline.bold())
                    GraficoScambio(giornate: g, mio: a, loro: b, nomeLoro: "Loro")
                }
            }
            impatto
            validita
            crediti
            if let giudizio {
                Carta {
                    Label(giudizio, systemImage: "scalemass").font(.headline)
                    if let righe = p.giudizio?.spiegazione, !righe.isEmpty {
                        ForEach(righe, id: \.self) { Text($0).font(.footnote).foregroundStyle(.secondary) }
                    }
                }
            }
        }
    }

    /// Le rose dopo lo scambio: se una non è valida (troppi giocatori di un ruolo, pochi per un modulo) si dice quale e perché.
    @ViewBuilder
    private var validita: some View {
        if p.completo == true {
            Carta("Rose dopo lo scambio") {
                if p.valido == false {
                    Label("Scambio non valido", systemImage: "xmark.octagon.fill").font(.headline).foregroundStyle(.orange)
                } else {
                    Label("Le rose restano valide", systemImage: "checkmark.seal.fill").font(.subheadline).foregroundStyle(Color.verde)
                }
                ForEach(p.problemi ?? [], id: \.self) { Text($0).font(.footnote).foregroundStyle(.orange) }
                if let v = p.valoreRosa?.mio, let variazione = v.variazione {
                    HStack {
                        Text("Tua formazione migliore")
                        Spacer()
                        Text("\(Formato.punti(v.prima)) → \(Formato.punti(v.dopo)) (\(Formato.conSegno(variazione)))").monospacedDigit().font(.subheadline)
                    }
                    .accessibilityElement(children: .combine)
                }
                if let v = p.panchina?.mio, let variazione = v.variazione, abs(variazione) >= 0.05 {
                    HStack {
                        Text("Tua panchina").font(.footnote)
                        Spacer()
                        Text(Formato.conSegno(variazione)).font(.footnote).monospacedDigit()
                    }
                    .foregroundStyle(.secondary)
                    .accessibilityElement(children: .combine)
                }
                if let modulo = p.rose?.mio?.modulo {
                    Text("Modulo dopo lo scambio: \(modulo)").font(.caption).foregroundStyle(.secondary)
                }
            }
        }
    }

    /// Il conguaglio di crediti: chi paga, quanto restano, quanto valgono in punti attesi.
    @ViewBuilder
    private var crediti: some View {
        if let c = p.conguaglio, let n = c.crediti, n != 0 {
            Carta("Conguaglio in crediti") {
                Text(n > 0 ? "Ricevi \(n) crediti da \(p.altra)." : "Paghi \(-n) crediti a \(p.altra).").font(.subheadline)
                if let d = c.dopo?.mio, let r = c.residui?.mio {
                    Text("I tuoi crediti: \(Formato.intero(r)) → \(Formato.intero(d))").font(.footnote).foregroundStyle(.secondary)
                }
                if let m = c.valoreMio {
                    HStack {
                        Text("Valore dei crediti per te")
                        Spacer()
                        Text(Formato.conSegno(m)).monospacedDigit().foregroundStyle(m >= 0 ? Color.verde : .orange)
                    }
                    .font(.subheadline)
                    .accessibilityElement(children: .combine)
                }
                if let netto = p.nettoMio {
                    HStack {
                        Text("Netto per te (con i crediti)").bold()
                        Spacer()
                        Text(Formato.conSegno(netto)).bold().monospacedDigit().foregroundStyle(netto >= 0 ? Color.verde : .orange)
                    }
                    .accessibilityElement(children: .combine)
                }
                if let problema = c.problema, c.valido == false {
                    Text(problema).font(.footnote).foregroundStyle(.orange)
                }
            }
        }
    }

    /// Variazione % dei punti attesi di ogni reparto della mia rosa (prossime giornate).
    @ViewBuilder
    private var impatto: some View {
        if let mio = p.reparti?.mio, !mio.isEmpty {
            Carta("Impatto sulla tua rosa") {
                Text("Conta anche il resto della squadra: se il reparto è già forte, un nuovo arrivato fa meno differenza.").font(.footnote).foregroundStyle(.secondary)
                ForEach(["P", "D", "C", "A"], id: \.self) { r in
                    let x = mio[r] ?? 0
                    HStack {
                        BadgeRuolo(ruolo: r)
                        Text(["P": "Portieri", "D": "Difensori", "C": "Centrocampisti", "A": "Attaccanti"][r] ?? r)
                        Spacer()
                        Text("\(Formato.conSegno(x))%").bold().monospacedDigit()
                            .foregroundStyle(x > 0.05 ? Color.verde : x < -0.05 ? Color.malus : .primary)
                    }
                    .accessibilityElement(children: .combine)
                }
                if let tot = p.percentualeMio {
                    HStack {
                        Text("In totale (prossime \(p.giornate?.count ?? 0) giornate)")
                        Spacer()
                        Text("\(Formato.conSegno(tot))%").bold().monospacedDigit()
                            .foregroundStyle(tot > 0.05 ? Color.verde : tot < -0.05 ? Color.malus : .primary)
                    }
                    .accessibilityElement(children: .combine)
                }
            }
        }
    }

    private func elenco(_ g: GiocatoreBreve) -> some View {
        HStack { BadgeRuolo(ruolo: g.ruolo); Text(g.nome); Spacer(); Text((g.squadra ?? "").capitalized).foregroundStyle(.secondary) }
            .accessibilityElement(children: .combine)
    }

    private func riga(_ chi: String, _ v: Double) -> some View {
        HStack { Text(chi); Spacer(); Text(Formato.conSegno(v)).font(.headline).monospacedDigit().foregroundStyle(v >= 0 ? Color.verde : .orange) }
            .accessibilityElement(children: .combine)
    }
}

/// Scegli chi dai e chi ricevi dalle due rose e l'app dice se conviene.
struct AnalizzaScambioView: View {
    @StateObject private var vm: AnalizzaScambioViewModel

    init(server: any ServerClient) {
        _vm = StateObject(wrappedValue: AnalizzaScambioViewModel(server: server))
    }

    var body: some View {
        ZStack {
            Sfondo()
            List {
                Section("Con") {
                    Picker("Squadra", selection: $vm.altra) {
                        Text("Scegli…").tag("")
                        ForEach(vm.altre) { Text($0.nome).tag($0.nome) }
                    }
                }
                if let mia = vm.miaRosa.dato {
                    Section("Tu dai") { elenco(mia.giocatori, scelti: $vm.doIds) }
                }
                if let loro = vm.loro {
                    Section("Tu ricevi") { elenco(loro.giocatori, scelti: $vm.ricevoIds) }
                }
                Section {
                    HStack {
                        Text("Conguaglio in crediti")
                        Spacer()
                        TextField("0", text: $vm.conguaglio)
                            .keyboardType(.numbersAndPunctuation)
                            .multilineTextAlignment(.trailing)
                            .frame(minWidth: 70, maxWidth: 110, minHeight: 44)
                            .accessibilityLabel("Conguaglio in crediti")
                    }
                    if !vm.conguaglioValido {
                        Label("Scrivi un numero intero di crediti.", systemImage: "exclamationmark.triangle").font(.footnote).foregroundStyle(.orange)
                    }
                } header: {
                    Text("Conguaglio")
                } footer: {
                    Text("Positivo: li ricevi tu (li paga \(vm.altra.isEmpty ? "l'altra squadra" : vm.altra)). Negativo: li paghi tu. Lascia vuoto se non ci sono crediti nello scambio.")
                }
                Section {
                    Text("Dai \(vm.doIds.count) · ricevi \(vm.ricevoIds.count) (da 1 a \(AnalizzaScambioViewModel.massimoPerLato) per lato)")
                        .font(.footnote).foregroundStyle(.secondary)
                    if let t = vm.troppi { Label(t, systemImage: "exclamationmark.triangle").font(.footnote).foregroundStyle(.orange) }
                    Button {
                        Task { await vm.analizza() }
                    } label: {
                        if vm.inCorso { ProgressView() } else { Text("Analizza").frame(maxWidth: .infinity, minHeight: 44) }
                    }
                    .disabled(!vm.puoAnalizzare)
                    if let errore = vm.errore { Text(errore).foregroundStyle(Color.attenzione) }
                }
                if let esito = vm.esito {
                    Section("Esito") { DettaglioScambio(p: esito, giudizio: esito.giudizio?.testo ?? ScambiLogica.giudizioAnalisi(esito)).listRowBackground(Color.clear) }
                }
            }
            .scrollContentBackground(.hidden)
        }
        .navigationTitle("Analizza")
        .navigationBarTitleDisplayMode(.inline)
        .ricercaGlobale()
        .task { await vm.carica() }
        .task(id: vm.altra) { await vm.caricaRosaAltra() }
    }

    private func elenco(_ giocatori: [GiocatoreRosa], scelti: Binding<Set<Int>>) -> some View {
        ForEach(giocatori.filter { $0.id != nil }, id: \.ident) { g in
            let id = g.id ?? -1
            let scelto = scelti.wrappedValue.contains(id)
            Button {
                if scelto { scelti.wrappedValue.remove(id) } else { scelti.wrappedValue.insert(id) }
            } label: {
                HStack(spacing: 10) {
                    Image(systemName: scelto ? "checkmark.circle.fill" : "circle")
                        .foregroundStyle(scelto ? Color.verde : .secondary)
                    BadgeRuolo(ruolo: g.ruolo ?? "?")
                    Text(g.nome)
                    Spacer()
                    Text((g.squadra ?? "").capitalized).font(.caption).foregroundStyle(.secondary)
                }
                .frame(minHeight: 44)
            }
            .buttonStyle(.plain)
            .accessibilityElement(children: .combine)
            .accessibilityAddTraits(scelto ? .isSelected : [])
        }
    }
}

#Preview("Scambi") {
    ScambiView(vm: ScambiViewModel(server: FinteServer.esempio))
}
