import SwiftUI

/// Schermata Scambi: solo presentazione. Dati e logica sono in `ScambiViewModel`.
struct ScambiView: View {
    @ScaledMetric(relativeTo: .caption) private var larghezzaEtichetta: CGFloat = 54
    @ObservedObject var vm: ScambiViewModel
    /// Dentro la scheda Altro la pagina sta già in una pila di navigazione: niente pila propria.
    var incorporata = false
    @Environment(\.funzioni) private var funzioni
    @Environment(\.apriImportazione) private var apriImportazione

    /// «Valuta un'offerta» c'è sempre; «Trova per me» e «Costruisci» dipendono dalle funzioni accese.
    private var modi: [ModoScambi] {
        ModoScambi.allCases.filter { modo in
            switch modo {
            case .trova: return funzioni.acceso(Funzione.scambiTrova)
            case .costruisci: return funzioni.acceso(Funzione.scambiCostruisci)
            case .valuta: return true
            }
        }
    }

    /// Il modo mostrato: quello scelto se è ancora disponibile, altrimenti «Valuta un'offerta».
    private var modoAttivo: ModoScambi { modi.contains(vm.modo) ? vm.modo : .valuta }

    var body: some View {
        if incorporata {
            pagina
        } else {
            NavigationStack(path: $vm.percorso) { pagina }
        }
    }

    private var pagina: some View {
            ZStack {
                Sfondo()
                if vm.servonoAltreRose {
                    soloLaMiaRosa
                } else {
                    VStack(spacing: 8) {
                        if modi.count > 1 { selettoreModo }
                        switch modoAttivo {
                        case .trova: trova
                        case .costruisci: AnalizzaScambioView(server: vm.server, incorporata: true)
                        case .valuta: scorrevole { offerta.ingresso(0) }
                        }
                    }
                }
            }
            .navigationTitle("Scambi")
            .ricercaGlobale()
            .navigationDestination(for: PaginaScambi.self) { _ in
                AnalizzaScambioView(server: vm.server).navigationTitle(TestiScambi.costruisciTitolo).navigationBarTitleDisplayMode(.inline).ricercaGlobale()
            }
            .task { await vm.caricaSquadre() }
            .task { if funzioni.acceso(Funzione.scambiTrova) { await vm.caricaLimite() } }
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

    /// Si è cominciato con la sola propria rosa: per gli scambi servono quelle degli altri.
    private var soloLaMiaRosa: some View {
        ScrollView {
            VStack(spacing: 16) {
                // la frase della web (`scambio.servono_altre`) divisa in titolo e descrizione
                VistaVuota(titolo: TestiScambi.servonoAltreRoseTitolo, icona: "arrow.left.arrow.right",
                           descrizione: TestiScambi.servonoAltreRoseCorpo)
                Button { apriImportazione() } label: {
                    Label("Aggiorna le rose", systemImage: "square.and.arrow.down").frame(maxWidth: .infinity, minHeight: Tema.areaTocco)
                }
                .pulsanteVetro(prominente: true)
                .accessibilityHint("Apre l'importazione delle rose")
            }
            .frame(maxWidth: 520)
            .padding(.horizontal, 16).padding(.bottom, 24)
            .frame(maxWidth: .infinity)
        }
        .refreshable { await vm.caricaSquadre() }
    }

    // MARK: i tre modi

    /// Un solo posto per gli scambi: trovare quelli giusti, costruirne uno, valutare un'offerta ricevuta.
    private var selettoreModo: some View {
        Picker(TestiScambi.cosaVuoiFare, selection: Binding(get: { modoAttivo }, set: { vm.modo = $0 }).animation(Tema.morbida)) {
            ForEach(modi) { Text($0.rawValue).tag($0) }
        }
        .pickerStyle(.segmented)
        .padding(.horizontal, 16)
        .sensoryFeedback(.selection, trigger: vm.modo)
        .accessibilityLabel(TestiScambi.cosaVuoiFare)
    }

    private func scorrevole<C: View>(@ViewBuilder _ contenuto: () -> C) -> some View {
        ScrollView {
            Colonne(spazio: Tema.spazioSchede) { contenuto() }
                .padding(.horizontal, 16).padding(.bottom, 24)
        }
        .demoInFondo()
        .bordiMorbidi()
    }

    /// «Trova per me»: le proposte del modello.
    private var trova: some View {
        ScrollView {
            Colonne(spazio: Tema.spazioSchede) {
                filtro.ingresso(0)
                if let d = vm.proposte.dato {
                    squadrePropense.ingresso(2)
                    if d.proposte.isEmpty {
                        VistaVuota(titolo: TestiScambi.nessunoScambio, icona: "arrow.left.arrow.right")
                    }
                    ForEach(Array(d.proposte.enumerated()), id: \.element.id) { i, p in
                        Button { vm.giudizioSelezionata = nil; vm.selezionata = p } label: { carta(p) }
                            .buttonStyle(StilePressione()).puntatore()
                            .entraScorrendo()
                            .ingresso(i + 3)
                            .accessibilityHint("Mostra il dettaglio dello scambio")
                    }
                } else if let e = vm.proposte.errore {
                    ErroreVista(messaggio: e) { Task { await vm.caricaProposte(forza: true) } }
                } else {
                    Scheletro(schede: 3, righe: 2, testo: TestiScambi.cercoGliScambi)
                }
                archivio
            }
            .padding(.horizontal, 16).padding(.bottom, 24)
            .animation(Tema.morbida, value: vm.proposte.dato != nil)
        }
        .demoInFondo()
        .refreshable { await vm.caricaProposte(forza: true) }
        .avvisoDatiSalvati(vm.proposte)
        .bordiMorbidi()
    }

    // MARK: filtro e offerta ricevuta

    private var filtro: some View {
        Carta(TestiScambi.trovaPerMe, simbolo: "arrow.left.arrow.right") {
            Text(TestiScambi.scambiCuiGuadagnate).font(.footnote).foregroundStyle(Color.testoSecondario)
            FilaAdattiva {
                Label(TestiScambi.conQualeSquadra, systemImage: "person.2").font(.subheadline)
                Spacer(minLength: 8)
                // Un menu con un'etichetta sua: l'etichetta di un Picker a menu non cresce in altezza e con il testo grandissimo
                // «Tutte le squadre» andava sopra le righe sotto (foto del collaudo su iPhone SE).
                Menu {
                    Picker(TestiScambi.conQualeSquadra, selection: $vm.con) {
                        Text(TestiScambi.tutteLeSquadre).tag("Tutte")
                        ForEach(vm.altre) { Text($0.nome).tag($0.nome) }
                    }
                } label: {
                    HStack(spacing: 4) {
                        Text(vm.con == "Tutte" ? TestiScambi.tutteLeSquadre : vm.con).multilineTextAlignment(.leading)
                        Image(systemName: "chevron.up.chevron.down").font(.caption).accessibilityHidden(true)
                    }
                    .foregroundStyle(Color.verde)
                    .frame(minHeight: 44)
                    .contentShape(Rectangle())
                }
                .accessibilityLabel(TestiScambi.conQualeSquadra)
                .accessibilityValue(vm.con == "Tutte" ? TestiScambi.tutteLeSquadre : vm.con)
            }
            .frame(minHeight: 44)
            Text(TestiScambi.quantiGiocatoriPerParte).font(.subheadline).accessibilityHidden(true)
            Picker(TestiScambi.quantiGiocatoriPerParte, selection: $vm.fino) {
                Text(TestiScambi.unoControUno).tag(1)
                Text(TestiScambi.finoA2).tag(2)
                Text(TestiScambi.finoA3).tag(3)
                Text(TestiScambi.finoA4).tag(4)
            }
            .pickerStyle(.segmented)
            .disabled(vm.con == "Tutte")
            .onChange(of: vm.con) { _, nuova in if nuova == "Tutte" { vm.fino = 1 } }
            .accessibilityLabel(TestiScambi.quantiGiocatoriPerParte)
            Text(TestiScambi.perGliScambi).font(.caption).foregroundStyle(Color.testoSecondario)
            Button { Task { await vm.caricaProposte() } } label: {
                Label(vm.proposte.inCorso ? TestiScambi.cercoGliScambi : TestiScambi.cercaScambi, systemImage: "magnifyingglass")
                    .frame(maxWidth: .infinity, minHeight: 44)
            }
            .pulsanteVetro(prominente: true)
            .disabled(vm.proposte.inCorso)
            if let l = vm.limite?.testo {
                Label(l, systemImage: "gauge.with.dots.needle.33percent").font(.footnote).foregroundStyle(Color.testoSecondario)
            }
            if let m = vm.messaggio { Text(m).font(.footnote).foregroundStyle(Color.verde) }
        }
    }

    private var offerta: some View {
        Carta(TestiScambi.valutaOfferta, simbolo: "envelope.open") {
            Text(TestiScambi.incollaMessaggio)
                .font(.footnote).foregroundStyle(Color.testoSecondario)
            TextEditor(text: $vm.testoOfferta)
                .scrollContentBackground(.hidden)
                .frame(minHeight: 96)
                .padding(8)
                .background(Color.sfondoIncavo, in: RoundedRectangle(cornerRadius: Tema.raggioPiccolo, style: .continuous))
                .overlay(alignment: .topLeading) {
                    if vm.testoOfferta.isEmpty {
                        Text("Es. Ti do Rowe e Polinardo, mi dai De Vlaam?").foregroundStyle(Color.testoSecondario).padding(.horizontal, 13).padding(.vertical, 16)
                            .allowsHitTesting(false).accessibilityHidden(true)
                    }
                }
                .accessibilityLabel(TestiScambi.messaggioOfferta)
            Button { Task { await vm.valutaOfferta() } } label: {
                if vm.offertaInCorso { ProgressView().accessibilityLabel(TestiScambi.leggoMessaggio).frame(maxWidth: .infinity, minHeight: 44) }
                else { Text(TestiScambi.valutaOffertaPulsante).frame(maxWidth: .infinity, minHeight: 44) }
            }
            .pulsanteVetro(prominente: true)
            .disabled(vm.offertaInCorso)
            .sensoryFeedback(trigger: vm.esitoOfferta?.analisi?.id) { _, nuovo in nuovo != nil ? .success : nil }
            if let e = vm.erroreOfferta {
                Text(e).font(.footnote).foregroundStyle(Color.attenzione)
                scegliAMano
            }
            if let o = vm.esitoOfferta { esitoOfferta(o) }
        }
    }

    /// Il pulsante della web che porta in «Costruisci» (`scambio.scegli_mano_costruisci`): solo se quel modo c'è.
    @ViewBuilder
    private var scegliAMano: some View {
        if modi.contains(.costruisci) {
            Button { vm.modo = .costruisci } label: {
                Text(TestiScambi.scegliAMano).frame(maxWidth: .infinity, minHeight: 44)
            }
            .pulsanteVetro()
        }
    }

    @ViewBuilder
    private func esitoOfferta(_ o: OffertaRiconosciuta) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            if let con = o.con { riga(TestiScambi.rigaCon, [con]) }
            riga(TestiScambi.dai, o.`do`)
            riga(TestiScambi.ricevi, o.ricevo)
        }
        if let ambigui = o.ambigui, !ambigui.isEmpty {
            Label(TestiScambi.ambigui(ambigui), systemImage: "exclamationmark.triangle")
                .font(.footnote).foregroundStyle(Color.attenzione)
        }
        if let analisi = o.analisi {
            Text(ScambiLogica.giudizioOfferta(analisi)).font(.headline)
            Button {
                vm.giudizioSelezionata = ScambiLogica.giudizioOfferta(analisi)
                vm.selezionata = analisi
            } label: { Label(TestiScambi.vediGiudizioCompleto, systemImage: "chart.bar").frame(minHeight: 44) }
        } else {
            Label(TestiScambi.nonTrovatoGiocatori, systemImage: "questionmark.circle")
                .font(.footnote).foregroundStyle(Color.testoSecondario)
            scegliAMano
        }
    }

    private func riga(_ titolo: String, _ nomi: [String]) -> some View {
        HStack(alignment: .firstTextBaseline) {
            Text(titolo).font(.caption.bold()).foregroundStyle(Color.testoSecondario).frame(width: larghezzaEtichetta, alignment: .leading)
            Text(nomi.isEmpty ? "–" : nomi.joined(separator: ", ")).font(.subheadline)
        }
        .accessibilityElement(children: .combine)
    }

    // MARK: proposte

    @ViewBuilder
    private var squadrePropense: some View {
        let elenco = vm.propense
        if !elenco.isEmpty {
            Carta(TestiScambi.chiAccettaPiu, simbolo: "person.2.fill") {
                Text(TestiScambi.squadreCheGuadagnano).font(.footnote).foregroundStyle(Color.testoSecondario)
                ForEach(elenco) { x in
                    HStack(alignment: .firstTextBaseline) {
                        StemmaSquadra(nome: x.nome, dimensione: 28, nascondiSeMancante: true)
                        VStack(alignment: .leading, spacing: 1) {
                            Text(x.nome).font(.subheadline.bold())
                            Text("\(TestiScambi.nScambi(x.scambi))\(dettaglioReparto(x))").font(.caption).foregroundStyle(Color.testoSecondario)
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
        return " · " + TestiScambi.migliora(reparto: nomeRuoloPlurale(r), p: Formato.conSegno(m))
    }

    private func nomeRuoloPlurale(_ r: String) -> String {
        ["P": "portieri", "D": "difensori", "C": "centrocampisti", "A": "attaccanti"][r] ?? r
    }

    private func carta(_ p: PropostaScambio) -> some View {
        Carta {
            HStack(spacing: 8) {
                StemmaSquadra(nome: p.altra, dimensione: 26, nascondiSeMancante: true)
                Text(TestiScambi.conSquadra(p.altra, dai: p.`do`.count, ricevi: p.ricevo.count)).font(.caption).foregroundStyle(Color.testoSecondario)
            }
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 4) {
                    ForEach(p.`do`) { g in HStack { BadgeRuolo(ruolo: g.ruolo); Text(g.nome).font(.subheadline) } }
                    Image(systemName: "arrow.down").font(.caption).foregroundStyle(Color.testoSecondario).accessibilityLabel("in cambio di")
                    ForEach(p.ricevo) { g in HStack { BadgeRuolo(ruolo: g.ruolo); Text(g.nome).font(.headline) } }
                }
                Spacer()
                VStack(alignment: .trailing, spacing: 4) {
                    guadagno("tu", p.guadagnoMio)
                    guadagno("loro", p.guadagnoLoro)
                }
            }
            Button { vm.copiaBozza(p) } label: { Label(TestiScambi.copiaBozza, systemImage: "doc.on.doc").font(.subheadline).frame(maxWidth: .infinity, minHeight: 44) }
                .pulsanteVetro()
        }
    }

    private func guadagno(_ chi: String, _ v: Double) -> some View {
        HStack(spacing: 4) {
            Text(chi).font(.caption2).foregroundStyle(Color.testoSecondario)
            Text(Formato.conSegno(v)).font(.headline).monospacedDigit().foregroundStyle(v >= 0 ? Color.verde : Color.attenzione)
        }
        .accessibilityElement(children: .combine)
    }

    // MARK: archivio

    @ViewBuilder
    private var archivio: some View {
        if !vm.archivio.isEmpty {
            Carta {
                DisclosureGroup(TestiScambi.archivio(vm.archivio.count)) {
                    VStack(alignment: .leading, spacing: 10) {
                        Text(TestiScambi.ultimiScambi).font(.caption).foregroundStyle(Color.testoSecondario)
                        ForEach(vm.archivio) { v in
                            HStack(alignment: .top) {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text("\(v.dai.joined(separator: ", ")) ⇄ \(v.ricevo.joined(separator: ", "))").font(.subheadline.bold())
                                    Text("con \(v.con) · \(v.quando.formatted(.dateTime.day().month(.abbreviated).locale(Formato.locale)))").font(.caption).foregroundStyle(Color.testoSecondario)
                                }
                                Spacer()
                                VStack(alignment: .trailing, spacing: 0) {
                                    Text(Formato.conSegno(v.mio)).font(.headline).monospacedDigit().foregroundStyle(v.mio >= 0 ? Color.verde : Color.attenzione)
                                    if let pc = v.percentuale { Text("\(Formato.conSegno(pc))%").font(.caption2).foregroundStyle(Color.testoSecondario) }
                                }
                            }
                            .accessibilityElement(children: .combine)
                        }
                        Button("Svuota l'archivio", role: .destructive) { vm.svuotaArchivio() }.frame(minHeight: 44)
                    }
                    .padding(.top, 6)
                }
                .tint(Color.testoSecondario)
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
            Carta(TestiScambi.dai) { ForEach(p.`do`) { g in elenco(g) } }
            Carta(TestiScambi.ricevi) { ForEach(p.ricevo) { g in elenco(g) } }
            Carta(TestiScambi.inStagione) {
                riga(TestiScambi.tu, p.guadagnoMio)
                riga("\(p.altra)", p.guadagnoLoro)
                if let q = p.quotazioneDo, let r = p.quotazioneRicevo {
                    Text("Quotazioni: \(Formato.intero(q)) → \(Formato.intero(r))").font(.caption).foregroundStyle(Color.testoSecondario)
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
                        ForEach(righe, id: \.self) { Text($0).font(.footnote).foregroundStyle(Color.testoSecondario) }
                    }
                }
            }
        }
    }

    /// Le rose dopo lo scambio: se una non è valida (troppi giocatori di un ruolo, pochi per un modulo) si dice quale e perché.
    @ViewBuilder
    private var validita: some View {
        if p.completo == true {
            Carta(TestiScambi.roseDopo) {
                if p.valido == false {
                    Label(TestiScambi.cosiNonSiPuoFare, systemImage: "xmark.octagon.fill").font(.headline).foregroundStyle(Color.attenzione)
                } else {
                    Label("Le rose restano valide", systemImage: "checkmark.seal.fill").font(.subheadline).foregroundStyle(Color.verde)
                }
                ForEach(p.problemi ?? [], id: \.self) { Text($0).font(.footnote).foregroundStyle(Color.attenzione) }
                if let v = p.valoreRosa?.mio, let variazione = v.variazione {
                    // la frase della web è lunga («… (prossime 3 giornate)»): va a capo lei, i numeri restano interi
                    HStack(alignment: .firstTextBaseline, spacing: 8) {
                        Text(TestiScambi.formazioneMigliore(giornate: p.giornate?.count ?? 0))
                        Spacer(minLength: 8)
                        Text("\(Formato.punti(v.prima)) → \(Formato.punti(v.dopo)) (\(Formato.conSegno(variazione)))")
                            .monospacedDigit().font(.subheadline).multilineTextAlignment(.trailing).layoutPriority(1)
                    }
                    .accessibilityElement(children: .combine)
                }
                if let v = p.panchina?.mio, let variazione = v.variazione, abs(variazione) >= 0.05 {
                    HStack {
                        Text(TestiScambi.panchina).font(.footnote)
                        Spacer()
                        Text(Formato.conSegno(variazione)).font(.footnote).monospacedDigit()
                    }
                    .foregroundStyle(Color.testoSecondario)
                    .accessibilityElement(children: .combine)
                }
                if let modulo = p.rose?.mio?.modulo {
                    Text("Modulo dopo lo scambio: \(modulo)").font(.caption).foregroundStyle(Color.testoSecondario)
                }
            }
        }
    }

    /// Il conguaglio di crediti: chi paga, quanto restano, quanto valgono in punti attesi.
    @ViewBuilder
    private var crediti: some View {
        if let c = p.conguaglio, let n = c.crediti, n != 0 {
            Carta(TestiScambi.crediti) {
                Text(n > 0 ? "Ricevi \(Formato.crediti(n)) da \(p.altra)." : "Paghi \(Formato.crediti(-n)) a \(p.altra).").font(.subheadline)
                if let d = c.dopo?.mio, let r = c.residui?.mio {
                    Text("I tuoi crediti: \(Formato.intero(r)) → \(Formato.intero(d))").font(.footnote).foregroundStyle(Color.testoSecondario)
                }
                if let m = c.valoreMio {
                    HStack {
                        Text("Valore dei crediti per te")
                        Spacer()
                        Text(Formato.conSegno(m)).monospacedDigit().foregroundStyle(m >= 0 ? Color.verde : Color.attenzione)
                    }
                    .font(.subheadline)
                    .accessibilityElement(children: .combine)
                }
                if let netto = p.nettoMio {
                    HStack {
                        Text("Netto per te (con i crediti)").bold()
                        Spacer()
                        Text(Formato.conSegno(netto)).bold().monospacedDigit().foregroundStyle(netto >= 0 ? Color.verde : Color.attenzione)
                    }
                    .accessibilityElement(children: .combine)
                }
                if let problema = c.problema, c.valido == false {
                    Text(problema).font(.footnote).foregroundStyle(Color.attenzione)
                }
            }
        }
    }

    /// Variazione % dei punti attesi di ogni reparto della mia rosa (prossime giornate).
    @ViewBuilder
    private var impatto: some View {
        if let mio = p.reparti?.mio, !mio.isEmpty {
            Carta(TestiScambi.impatto) {
                Text(TestiScambi.contaAncheResto).font(.footnote).foregroundStyle(Color.testoSecondario)
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
                        Text(TestiScambi.inTotale(giornate: p.giornate?.count ?? 0))
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
        FilaAdattiva {
            HStack { BadgeRuolo(ruolo: g.ruolo); Text(g.nome) }
            Spacer(minLength: 0)
            Text((g.squadra ?? "").capitalized).foregroundStyle(Color.testoSecondario)
        }
        .accessibilityElement(children: .combine)
    }

    private func riga(_ chi: String, _ v: Double) -> some View {
        HStack { Text(chi); Spacer(); Text(Formato.conSegno(v)).font(.headline).monospacedDigit().foregroundStyle(v >= 0 ? Color.verde : Color.attenzione) }
            .accessibilityElement(children: .combine)
    }
}

/// Scegli chi dai e chi ricevi dalle due rose e l'app dice se conviene.
struct AnalizzaScambioView: View {
    @StateObject private var vm: AnalizzaScambioViewModel
    /// Dentro la schermata Scambi (modo «Costruisci»): niente fondo proprio.
    var incorporata = false

    init(server: any ServerClient, incorporata: Bool = false) {
        _vm = StateObject(wrappedValue: AnalizzaScambioViewModel(server: server))
        self.incorporata = incorporata
    }

    var body: some View {
        ZStack {
            Sfondo()
            List {
                Section {
                    Text(TestiScambi.costruisciSpiega).font(.footnote).foregroundStyle(Color.testoSecondario)
                    Picker(TestiScambi.scambioCon, selection: $vm.altra) {
                        Text("Scegli…").tag("")
                        ForEach(vm.altre) { Text($0.nome).tag($0.nome) }
                    }
                } header: {
                    // dentro Scambi la pagina non ha una barra col titolo: il titolo del riquadro della web sta qui
                    if incorporata {
                        Text(TestiScambi.costruisciTitolo).font(.headline).foregroundStyle(.primary).textCase(nil)
                            .accessibilityAddTraits(.isHeader)
                    }
                }
                if let mia = vm.miaRosa.dato {
                    Section { elenco(mia.giocatori, scelti: $vm.doIds) } header: { testataParte(TestiScambi.dai, scelti: vm.doIds.count) }
                }
                if let loro = vm.loro {
                    Section { elenco(loro.giocatori, scelti: $vm.ricevoIds) } header: { testataParte(TestiScambi.ricevi, scelti: vm.ricevoIds.count) }
                }
                Section {
                    Picker(TestiScambi.conguaglio, selection: $vm.verso) {
                        ForEach(VersoConguaglio.allCases) { Text($0.nome).tag($0) }
                    }
                    .pickerStyle(.segmented)
                    .accessibilityLabel(TestiScambi.conguaglio)
                    HStack {
                        Text(TestiScambi.creditiQuanti)
                        Spacer()
                        TextField("0", text: $vm.conguaglio)
                            .keyboardType(.numberPad)
                            .multilineTextAlignment(.trailing)
                            .frame(minWidth: 70, maxWidth: 110, minHeight: 44)
                            .accessibilityLabel(TestiScambi.creditiQuanti)
                    }
                    // solo cifre, come il campo numerico della web: «Ricevo» e «Pago» dicono il segno (anche se si incolla un meno)
                    .onChange(of: vm.conguaglio) { _, nuovo in
                        let soloCifre = nuovo.filter { ("0"..."9").contains($0) }
                        if soloCifre != nuovo { vm.conguaglio = soloCifre }
                    }
                    if !vm.conguaglioValido {
                        Label(TestiScambi.conguaglioNumero, systemImage: "exclamationmark.triangle").font(.footnote).foregroundStyle(Color.attenzione)
                    }
                } header: {
                    Text(TestiScambi.conguaglio).foregroundStyle(Color.testoSecondario)
                } footer: {
                    Text(TestiScambi.conguaglioAiuto).foregroundStyle(Color.testoSecondario)
                }
                Section {
                    if let t = vm.troppi { Label(t, systemImage: "exclamationmark.triangle").font(.footnote).foregroundStyle(Color.attenzione) }
                    Button {
                        Task { await vm.analizza() }
                    } label: {
                        if vm.inCorso {
                            HStack(spacing: 8) { ProgressView(); Text(TestiScambi.calcolo) }.frame(maxWidth: .infinity, minHeight: 44)
                        } else {
                            Text(TestiScambi.valutaScambio).frame(maxWidth: .infinity, minHeight: 44)
                        }
                    }
                    .disabled(!vm.puoAnalizzare)
                    if let errore = vm.errore { Text(errore).foregroundStyle(Color.attenzione) }
                }
                if let esito = vm.esito {
                    Section(titolo: "Esito") { DettaglioScambio(p: esito, giudizio: esito.giudizio?.testo ?? ScambiLogica.giudizioAnalisi(esito)).listRowBackground(Color.clear) }
                }
            }
            .scrollContentBackground(.hidden)
        }
        .task { await vm.carica() }
        .task(id: vm.altra) { await vm.caricaRosaAltra() }
    }

    /// «Dai   2 su 4»: il titolo della parte e quanti giocatori sono scelti (`scambi.scelti`), letti insieme da VoiceOver.
    private func testataParte(_ titolo: String, scelti: Int) -> some View {
        HStack(alignment: .firstTextBaseline, spacing: 8) {
            Text(titolo)
            Spacer(minLength: 8)
            Text(TestiScambi.scelti(scelti, massimo: AnalizzaScambioViewModel.massimoPerLato)).monospacedDigit()
        }
        .foregroundStyle(Color.testoSecondario)
        .accessibilityElement(children: .combine)
        .accessibilityAddTraits(.isHeader)
    }

    private func elenco(_ giocatori: [GiocatoreRosa], scelti: Binding<Set<Int>>) -> some View {
        ForEach(giocatori.filter { $0.id != nil }, id: \.ident) { g in
            let id = g.id ?? -1
            let scelto = scelti.wrappedValue.contains(id)
            Button {
                if scelto { scelti.wrappedValue.remove(id) } else { scelti.wrappedValue.insert(id) }
            } label: {
                FilaAdattiva(spazio: 4) {
                    HStack(spacing: 10) {
                        Image(systemName: scelto ? "checkmark.circle.fill" : "circle")
                            .foregroundStyle(scelto ? Color.verde : Color.testoSecondario)
                        BadgeRuolo(ruolo: g.ruolo ?? "?")
                        Text(g.nome)
                    }
                    Spacer(minLength: 0)
                    Text((g.squadra ?? "").capitalized).font(.caption).foregroundStyle(Color.testoSecondario)
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
