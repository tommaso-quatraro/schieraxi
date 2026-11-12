import SwiftUI

/// Schermata Formazione: solo presentazione. Dati e logica sono in `FormazioneViewModel`.
struct FormazioneView: View {
    @ObservedObject var vm: FormazioneViewModel
    @Environment(\.apriGiocatore) private var apriGiocatore
    @Namespace private var moduloNS

    /// Dall'alto in basso come sul campo: attacco in alto, portiere in basso.
    private let ruoli = ["A", "C", "D", "P"]
    private let nomiRuolo = ["P": "Portiere", "D": "Difensori", "C": "Centrocampisti", "A": "Attaccanti"]

    // MARK: frasi della web (catalogo comune `fanta/testi/formazione.json` → `Catalogo.Formazione`, #495; le prove sono
    // `FormazioneComeLaWebTests` e `FormazioneDalCatalogoTests`)

    /// Probabili formazioni non ancora uscite (`formazione.mancano_probabili_formazioni`).
    static let testoSenzaProbabili = Catalogo.Formazione.mancanoProbabiliFormazioni
    /// Sotto «Panchina» (`formazione.quest_ordine_entra`).
    static let testoPanchina = Catalogo.Formazione.questOrdineEntra
    /// Davanti alle alternative vicine, solo sul primo titolare che le ha (`formazione.ballottaggio_alternative_vic`).
    static let testoBallottaggio = Catalogo.Formazione.ballottaggioAlternativeVic
    /// ✎ sostituisce un titolare (modifica a mano), come il pulsante della web.
    static let simboloSostituisci = "pencil"
    /// Il pulsante sopra i moduli (`formazione.modifica_mano`).
    static let testoModificaAMano = Catalogo.Formazione.modificaMano
    /// In modifica a mano, per VoiceOver su ogni modulo: un tocco torna alla proposta del server.
    static let suggerimentoChipAMano = Catalogo.Formazione.tornaAllaConsigliata
    /// Mentre la formazione arriva, come la web (`formazione.calcolo`).
    static let testoCaricamento = Catalogo.Formazione.calcolo

    /// La riga sotto «Titolari» in modifica a mano (`formazione.tocca_sostituire`).
    static let istruzioneTitolari = Catalogo.Formazione.toccaSostituire

    /// La formazione di un'altra squadra, come la web: «Stai guardando la formazione di Gli Amici.»
    /// (`formazione.stai_guardando_formazione`, poi il nome e il punto).
    static func testoSquadraVista(_ nome: String) -> String {
        "\(Catalogo.Formazione.staiGuardandoFormazione) \(nome)."
    }

    var body: some View {
        NavigationStack {
            ZStack {
                Sfondo()
                ScrollView {
                    Colonne(spazio: Tema.spazioSchede) {
                        if let f = vm.formazione {
                            bannerSquadra
                            let v = vm.vista(f)
                            let primoBallottaggio = primoConBallottaggio(f, v)
                            cardStile(f, v).ingresso(0)
                            Carta("Campo", simbolo: "sportscourt") {
                                CampoFormazione(titolari: v.titolari, apribile: true)
                                notaScelta(vm.righeScelta(f))
                            }
                            .ingresso(3)
                            // Un'unica scheda con i quattro reparti in ordine (Portiere, Difensori, Centrocampisti, Attaccanti):
                            // sull'iPad le colonne si leggono così dall'alto in basso senza saltare da una parte all'altra.
                            Carta(Catalogo.Formazione.titolari, simbolo: "person.3.fill") {
                                // come la web: in modifica a mano ✎ sostituisce un titolare; altrimenti (e a giornata chiusa) niente riga
                                if vm.manuale != nil, !vm.chiusa {
                                    Text(Self.istruzioneTitolari)
                                        .font(.caption).foregroundStyle(Color.testoSecondario)
                                }
                                if let nota = vm.notaFermi {
                                    Text(nota).font(.caption).foregroundStyle(Color.testoSecondario)
                                }
                                ForEach(ruoli, id: \.self) { r in
                                    let gruppo = v.titolari.filter { $0.ruolo == r }
                                    if !gruppo.isEmpty {
                                        Text("\(nomiRuolo[r] ?? r) (\(gruppo.count))").titoletto().padding(.top, 4)
                                        ForEach(gruppo) { g in rigaTitolare(g, f, v, etichettaBallottaggio: g.id == primoBallottaggio) }
                                    }
                                }
                            }
                            .ingresso(4)
                            Carta("Panchina", simbolo: "chair.lounge.fill") {
                                Text(Self.testoPanchina).font(.caption).foregroundStyle(Color.testoSecondario)
                                ForEach(Array(v.panchina.enumerated()), id: \.element.id) { i, g in
                                    RigaConFilo(prima: i == 0) { RigaGiocatore(g: g, apribile: true) }
                                }
                            }
                            .ingresso(5)
                            fuori(f, v)
                            Text(Self.legenda(conPerche: f.titolari.contains { PercheNumero($0) != nil }))
                                .font(.caption).foregroundStyle(Color.testoSecondario).padding(.horizontal, 4)
                        } else if let errore = vm.errore {
                            ErroreVista(messaggio: errore) { Task { await vm.carica() } }
                        } else {
                            Scheletro(schede: 3, righe: 3, testo: Self.testoCaricamento)
                        }
                    }
                    .padding(.horizontal, Tema.margine)
                    .padding(.bottom, 24)
                    .animation(Tema.morbida, value: vm.formazione != nil)
                }
                .demoInFondo()
                .refreshable { await vm.carica() }
                .avvisoDatiSalvati(vm.caricatore)
                .bordiMorbidi()
            }
            .navigationTitle("Formazione")
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    if let f = vm.formazione {
                        Menu {
                            ShareLink(item: vm.testo(f)) { Label("Condividi come testo", systemImage: "text.alignleft") }
                            Button { vm.copiaTesto(f) } label: { Label(Catalogo.Formazione.copiaFormazione, systemImage: "doc.on.doc") }
                        } label: {
                            Image(systemName: "square.and.arrow.up").frame(minWidth: 44, minHeight: 44)
                        }
                        .accessibilityLabel("Condividi la formazione")
                    }
                }
            }
            .ricercaGlobale()
            // la scelta del sostituto: da «Sostituisci» nella scheda del giocatore o, in modifica a mano, dal tocco sulla riga
            .sheet(item: $vm.daSostituire) { g in
                if let f = vm.formazione {
                    SostituzioneSheet(uscente: g, candidati: vm.sostituti(di: g, f)) { nuovo in
                        vm.sostituisciTitolare(g.id, con: nuovo)
                        vm.daSostituire = nil
                    }
                }
            }
            .task { await vm.carica() }
        }
    }

    /// Sotto il campo, come la nota della web: per i titolari che sembrano una scelta storta, il nome e il perché (righe del server).
    @ViewBuilder
    private func notaScelta(_ righe: [RigaScelta]) -> some View {
        if !righe.isEmpty {
            VStack(alignment: .leading, spacing: 6) {
                ForEach(righe) { r in
                    (Text(r.nome).bold() + Text(" · " + r.testo))
                        .font(.footnote).foregroundStyle(Color.testoSecondario)
                        .fixedSize(horizontal: false, vertical: true)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .accessibilityLabel(r.voce)
                }
            }
            .padding(.top, 2)
        }
    }

    /// La riga in fondo alla Formazione: cosa sono i numeri (e, con un server che manda i motivi, che si possono toccare).
    static func legenda(conPerche: Bool) -> String {
        "Il numero è il fantavoto atteso: quello che SchieraXI si aspetta dal giocatore se gioca, con le regole della tua lega."
            + (conPerche ? " Toccalo per sapere perché." : "")
            + " I punti attesi della squadra pesano ogni fantavoto per la probabilità di giocare."
    }

    // MARK: un'altra squadra

    @ViewBuilder
    private var bannerSquadra: some View {
        if let nome = vm.squadraVista {
            Carta {
                Label(Self.testoSquadraVista(nome), systemImage: "eye").font(.subheadline)
                Button { vm.tornaAllaMia() } label: { Text(Catalogo.Formazione.tornaAllaTua).frame(minHeight: 44) }
                    .pulsanteVetro()
            }
        }
    }

    // MARK: righe

    /// In modifica a mano ogni titolare è un bottone con ✎ che apre la scelta del sostituto (tranne chi gioca un anticipo già
    /// cominciato: `vm.fermi`); altrimenti un tocco apre la scheda e sotto i titolari incerti ci sono le alternative vicine
    /// (ballottaggio). `etichettaBallottaggio`: solo sul primo che le ha si legge «In ballottaggio con».
    @ViewBuilder
    private func rigaTitolare(_ g: Giocatore, _ f: Formazione, _ v: VistaFormazione, etichettaBallottaggio: Bool) -> some View {
        if vm.chiusa {
            // giornata chiusa: sola lettura (un tocco apre la scheda, niente sostituzioni)
            RigaGiocatore(g: g, apribile: true)
        } else if vm.manuale != nil && !vm.fermi.contains(g.id) {
            Button { vm.daSostituire = g } label: {
                HStack { RigaGiocatore(g: g); Image(systemName: Self.simboloSostituisci).foregroundStyle(Color.verde).accessibilityHidden(true) }
                    .frame(minHeight: 44)
            }
            .buttonStyle(StilePressione())
            .accessibilityHint("Apre la scelta del giocatore che prende il suo posto")
        } else {
            VStack(alignment: .leading, spacing: 4) {
                RigaGiocatore(g: g, apribile: true)
                // in modifica a mano qui c'è solo chi è fermo (anticipo già cominciato, #373): come la web, niente ballottaggio
                if vm.manuale == nil { ballottaggio(g, f, v, conEtichetta: etichettaBallottaggio) }
            }
        }
    }

    /// Il primo titolare, nell'ordine dello schermo (attacco in alto), con alternative vicine: come la web, «In ballottaggio con» si
    /// legge una volta sola, lì (prima si ripeteva per ogni titolare). Ogni alternativa ha comunque la sua frase per VoiceOver.
    private func primoConBallottaggio(_ f: Formazione, _ v: VistaFormazione) -> Int? {
        guard vm.manuale == nil, !vm.chiusa else { return nil }
        for r in ruoli {
            if let g = v.titolari.first(where: { $0.ruolo == r && !vm.ballottaggio(per: $0, f, v).isEmpty }) { return g.id }
        }
        return nil
    }

    @ViewBuilder
    private func ballottaggio(_ g: Giocatore, _ f: Formazione, _ v: VistaFormazione, conEtichetta: Bool) -> some View {
        let alternative = vm.ballottaggio(per: g, f, v)
        if !alternative.isEmpty {
            VStack(alignment: .leading, spacing: 4) {
                if conEtichetta {
                    Text(Self.testoBallottaggio).font(.caption).foregroundStyle(Color.testoSecondario)
                }
                ViewThatFits(in: .horizontal) {
                    HStack(spacing: 8) { ForEach(alternative) { a in chipAlternativa(a, rispetto: g) } }
                    VStack(alignment: .leading, spacing: 6) { ForEach(alternative) { a in chipAlternativa(a, rispetto: g) } }
                }
            }
            .padding(.leading, 58)
        }
    }

    /// Un'alternativa vicina: un tocco apre la sua scheda, come la web.
    private func chipAlternativa(_ a: Ballottaggio.Alternativa, rispetto g: Giocatore) -> some View {
        Button { apriGiocatore(a.giocatore.id) } label: {
            HStack(spacing: 5) {
                Text(a.giocatore.nomeCorto).font(.caption.weight(.semibold))
                Text(Formato.conSegno(a.differenza)).font(.caption.bold()).monospacedDigit()
                    .foregroundStyle(a.quasiPari ? Color.testoSecondario : (a.differenza > 0 ? Color.verde : Color.attenzione))
                if a.quasiPari { Text(Catalogo.Formazione.quasiPari).font(.caption2).foregroundStyle(Color.testoSecondario) }
            }
            .padding(.horizontal, 10)
            .frame(minHeight: 44)
            .background(Color.sfondoIncavo, in: Capsule())
        }
        .buttonStyle(StilePressione())
        .accessibilityLabel("\(a.giocatore.nome), \(Formato.conSegno(a.differenza)) punti attesi rispetto a \(g.nome)\(a.quasiPari ? ", \(Catalogo.Formazione.quasiPari)" : "")")
        .accessibilityHint("Apre la scheda del giocatore")
    }

    @ViewBuilder
    private func fuori(_ f: Formazione, _ v: VistaFormazione) -> some View {
        let altri = vm.fuori(f, v)
        if !altri.isEmpty || !(f.senzaDati ?? []).isEmpty {
            Carta {
                DisclosureGroup(Catalogo.Formazione.fuoriDalla(n: "\(altri.count)")) {
                    VStack(alignment: .leading, spacing: 8) {
                        ForEach(altri) { RigaGiocatore(g: $0, apribile: true) }
                        if let senza = f.senzaDati, !senza.isEmpty {
                            Text(Catalogo.Formazione.senzaDati(nomi: senza.joined(separator: ", "))).font(.caption).foregroundStyle(Color.testoSecondario)
                        }
                    }
                    .padding(.top, 6)
                }
                .tint(Color.testoSecondario)
            }
        }
    }

    // MARK: modulo e punti (una sola card)

    /// Giornata, punti, stato della scelta, «Modifica a mano» e i moduli in una card compatta: il campo parte subito sotto.
    /// Come la web, i moduli restano anche in modifica a mano (#463).
    private func cardStile(_ f: Formazione, _ v: VistaFormazione) -> some View {
        Carta {
            intestazione(f, v)
            if let fascia = vm.fasciaChiusa {
                // come la web: la fascia della giornata chiusa solo per un'altra squadra (per la tua lo dice la riga di stato),
                // e la formazione in sola lettura
                Label(fascia, systemImage: "lock.fill")
                    .font(.footnote.weight(.semibold))
                    .padding(.horizontal, 10).padding(.vertical, 6)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color.attenzione.opacity(0.14), in: RoundedRectangle(cornerRadius: 12, style: .continuous))
                    .accessibilityElement(children: .combine)
            } else if !vm.chiusa, f.conProbabili == false {
                Label(Self.testoSenzaProbabili, systemImage: "clock").font(.footnote).foregroundStyle(Color.testoSecondario)
                    .fixedSize(horizontal: false, vertical: true)
            }
            // come la web: il confronto con la consigliata sotto i punti, poi la riga dello stato con i suoi pulsanti
            if vm.manuale != nil { calcoloManuale }
            rigaStato(f)
            if !vm.chiusa {
                if let livello = vm.livello(f) { sceltaModulo(f, livello) }
                pulsantiSenzaRiga(f)
            }
            if let messaggio = vm.messaggio { Text(messaggio).font(.footnote).foregroundStyle(Color.testoSecondario) }
        }
    }

    private func intestazione(_ f: Formazione, _ v: VistaFormazione) -> some View {
        FilaAdattiva(allineamento: .firstTextBaseline) {
            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: 8) {
                    if let nome = f.squadra { StemmaSquadra(nome: nome, dimensione: 28, nascondiSeMancante: true) }
                    Text(v.modulo).font(.system(.title2, design: .rounded).weight(.bold))
                        .lineLimit(1).fixedSize()   // «3-4-3» non va mai a capo
                }
                Text(TempiLega.didascalia(giornata: f.etichettaGiornata, scelta: vm.manuale != nil,
                                          comeConsigliato: !vm.altraDallaConsigliata))
                    .font(.caption).foregroundStyle(Color.testoSecondario)
            }
            Spacer()
            puntiIntestazione(f, v)
        }
        .accessibilityElement(children: .combine)
    }

    /// I punti attesi; in modifica a mano, finché il server non li ha calcolati, «Calcolo…» (mai quelli della consigliata).
    @ViewBuilder
    private func puntiIntestazione(_ f: Formazione, _ v: VistaFormazione) -> some View {
        VStack(alignment: .trailing, spacing: 0) {
            if let punti = v.punti {
                Text(Formato.punti(punti)).font(.title2.bold()).monospacedDigit().numerico(punti)
                // «tra 66 e 82 · 8 volte su 10» va a capo solo tra un pezzo e l'altro, mai a metà
                Text(TestoACapo.soloTraIPezzi(Catalogo.Formazione.puntiAttesi + (vm.fascia(f).map { TestoACapo.separatore + $0 } ?? "")))
                    .font(.caption).foregroundStyle(Color.testoSecondario).multilineTextAlignment(.trailing)
            } else if vm.calcoloNonRiuscito {
                Text("–").font(.title2.bold()).accessibilityHidden(true)
                Text("punti non calcolati").font(.caption).foregroundStyle(Color.testoSecondario)
            } else {
                ProgressView().controlSize(.small).accessibilityHidden(true)
                Text("Calcolo…").font(.caption).foregroundStyle(Color.testoSecondario)
            }
        }
    }

    // MARK: riga di stato della scelta

    /// Sempre visibile per la propria squadra (`RigaStatoScelta`), con gli stati, le frasi e i pulsanti della web.
    @ViewBuilder
    private func rigaStato(_ f: Formazione) -> some View {
        let stato = vm.statoScelta
        if stato != .sconosciuto {
            RigaStatoScelta(stato: stato,
                            salvando: vm.salvataggioInCorso,
                            salva: { salvaQuesta(f) },
                            annulla: { vm.annullaModifiche() },
                            tornaAllaConsigliata: { tornaAllaConsigliata(f) })
        }
    }

    private func salvaQuesta(_ f: Formazione) {
        Task { await vm.salvaQuesta(f) }
    }

    private func tornaAllaConsigliata(_ f: Formazione) {
        Task { await vm.tornaAllaConsigliata(f) }
    }

    /// «Modifica a mano» (solo dove la web la offre: `StatoScelta.conModificaAMano`) e i moduli dello stile equilibrato, l'unico
    /// rimasto (#634, come la web). In modifica a mano nessun modulo è acceso: un tocco torna alla proposta del server (la scelta
    /// salvata resta).
    @ViewBuilder
    private func sceltaModulo(_ f: Formazione, _ livello: LivelloRischio) -> some View {
        let aMano = vm.manuale != nil
        if !aMano, vm.statoScelta.conModificaAMano { modificaAMano(f) }
        FilaScorrevole {
            ForEach(livello.moduli) { m in
                let attivo = !aMano && vm.moduloAttivo(livello) == m.modulo
                Button { withAnimation(Tema.molla) { vm.scegliModulo(m.modulo) } } label: {
                    VStack(spacing: 0) {
                        Text(m.modulo + (m.modulo == livello.modulo ? " ★" : "")).font(.subheadline.bold())
                        Text(Formato.punti(m.punteggioAtteso)).font(.caption2).monospacedDigit()
                    }
                    .padding(.horizontal, 14)
                    .frame(minHeight: 44)
                    .pillola(attiva: attivo, spazio: moduloNS)
                }
                .buttonStyle(StilePressione())
                .accessibilityLabel("Modulo \(m.modulo), \(Formato.punti(m.punteggioAtteso)) punti attesi\(m.modulo == livello.modulo ? ", consigliato" : "")")
                .accessibilityHint(aMano ? Self.suggerimentoChipAMano : "")
                .accessibilityAddTraits(attivo ? .isSelected : [])
            }
        }
    }

    /// Pulsante piccolo (l'area di tocco resta da 44 pt).
    private func modificaAMano(_ f: Formazione) -> some View {
        Button { vm.iniziaModificaManuale(f) } label: {
            Label(Self.testoModificaAMano, systemImage: "hand.tap").font(.footnote.weight(.semibold))
                .padding(.horizontal, 10).padding(.vertical, 5)
                .background(Color.sfondoIncavo, in: Capsule())
                .frame(minHeight: 44)
                .contentShape(Rectangle())
        }
        .buttonStyle(StilePressione())
        .foregroundStyle(Color.verde)
    }

    /// In modifica a mano, sotto i punti: «Non riesco a calcolare i punti: riprova» e il confronto con la consigliata. I pulsanti
    /// stanno nella riga dello stato; le frasi su ✎ e sui giocatori fermi sotto «Titolari», come la web.
    @ViewBuilder
    private var calcoloManuale: some View {
        if vm.calcoloNonRiuscito, !vm.chiusa {
            Button { Task { await vm.valuta(salva: false) } } label: {
                Label("Non riesco a calcolare i punti: riprova", systemImage: "arrow.clockwise").font(.footnote.weight(.semibold))
                    .frame(minHeight: 44).contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .foregroundStyle(Color.attenzione)
        }
        if let r = vm.valutazioneAttuale, let d = r.differenza { rigaDifferenza(r, d) }
    }

    /// Quanto vale la formazione a mano rispetto alla consigliata. La fascia dei punti sta già nell'intestazione: qui non si ripete
    /// (solo se il server non manda né fascia né oscillazione restano brutta giornata ed eccezionale).
    private func rigaDifferenza(_ r: ValutazioneManuale, _ d: Double) -> some View {
        let confronto = Catalogo.Formazione.rispetto(d: Formato.conSegno(d), n: Formato.punti(r.consigliataStessoModulo ?? r.consigliata))
        let estremi = IntervalloPunti.frase(r.intervallo, dev: r.dev) == nil
            ? " Brutta giornata \(Formato.intero(r.bruttaGiornata)) · giornata eccezionale \(Formato.intero(r.giornataEccezionale))." : ""
        return Text(confronto + estremi).font(.subheadline)
            // sotto mezzo punto è un pari (grigio, non arancio)
            .foregroundStyle(abs(d) < 0.5 ? Color.testoSecondario : d > 0 ? Color.verde : Color.attenzione)
    }

    /// In modifica a mano senza la riga dello stato (la formazione di un'altra squadra, o la tua scelta non ancora letta): i
    /// pulsanti stanno qui, come quelli della web fuori dalla riga. «Salva come mia scelta» solo per la tua squadra, e non mentre
    /// il server prova la scelta salvata appena letta.
    @ViewBuilder
    private func pulsantiSenzaRiga(_ f: Formazione) -> some View {
        if vm.manuale != nil, vm.statoScelta == .sconosciuto {
            let conSalva = vm.squadraVista == nil && !vm.provaSalvata
            ViewThatFits(in: .horizontal) {
                HStack(spacing: 12) {
                    if conSalva { salva(f) }
                    torna(f)
                }
                VStack(alignment: .leading, spacing: 0) {
                    if conSalva { salva(f) }
                    torna(f)
                }
            }
        }
    }

    private func salva(_ f: Formazione) -> some View {
        PulsanteRigaStato(testo: Self.etichettaSalva(vm.statoScelta), simbolo: "tray.and.arrow.down", colore: .verde) { salvaQuesta(f) }
            .keyboardShortcut("s", modifiers: .command)
            .disabled(vm.salvataggioInCorso)
    }

    private func torna(_ f: Formazione) -> some View {
        PulsanteRigaStato(testo: RigaStatoScelta.testoTorna, simbolo: "arrow.uturn.backward", colore: .primary) { tornaAllaConsigliata(f) }
    }

    /// «Salva le modifiche» con una scelta salvata e modifiche (`formazione.salva_modifiche`), altrimenti «Salva come mia scelta»
    /// (`formazione.salva_come_mia`).
    static func etichettaSalva(_ stato: StatoScelta) -> String {
        if case .modificata = stato { return Catalogo.Formazione.salvaModifiche }
        return Catalogo.Formazione.salvaComeMia
    }
}

/// Scelta del sostituto: giocatori della stessa categoria che non sono già titolari né fermi (`FormazioneViewModel.sostituti`).
struct SostituzioneSheet: View {
    let uscente: Giocatore
    let candidati: [Giocatore]
    let scelto: (Int) -> Void
    @Environment(\.dismiss) private var chiudi

    /// Sotto il titolo, come la web (`formazione.giocatori_dello_stesso`).
    static let testoStessoRuolo = Catalogo.Formazione.giocatoriDelloStesso
    /// Nessun candidato (`formazione.nessun_altro_giocatore`).
    static let testoNessunAltro = Catalogo.Formazione.nessunAltroGiocatore

    var body: some View {
        NavigationStack {
            List {
                Section {
                    ForEach(candidati) { g in
                        Button { scelto(g.id) } label: { RigaGiocatore(g: g).frame(minHeight: 44) }.buttonStyle(.plain)
                    }
                    if candidati.isEmpty {
                        Text(Self.testoNessunAltro).foregroundStyle(Color.testoSecondario)
                    }
                } header: {
                    VStack(alignment: .leading, spacing: 4) {
                        Text(Catalogo.Formazione.alPostoDi(nome: uscente.nome))
                        Text(Self.testoStessoRuolo).font(.footnote).textCase(nil)
                    }
                }
            }
            .navigationTitle(Catalogo.Formazione.sostituisci)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .navigationBarTrailing) { Button("Annulla") { chiudi() } } }
        }
    }
}

#Preview("Formazione") {
    FormazioneView(vm: FormazioneViewModel(server: FinteServer.esempio))
}
