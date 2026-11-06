import SwiftUI

/// Schermata Formazione: solo presentazione. Dati e logica sono in `FormazioneViewModel`.
struct FormazioneView: View {
    @ObservedObject var vm: FormazioneViewModel
    @State private var daSostituire: Giocatore?
    /// Dopo «Apri la scheda» nel foglio «Perché questo numero»: la scheda si apre quando il foglio si è chiuso.
    @State private var schedaDopoPerche: Int?
    @Environment(\.apriGiocatore) private var apriGiocatore
    @Namespace private var moduloNS
    @Namespace private var stileNS
    @Environment(\.funzioni) private var funzioni
    /// La legenda del campo si mostra da sola una volta; poi si riapre con «Cosa vuol dire» (come la web app).
    @AppStorage("legendaCampoVista") private var legendaVista = false
    @State private var legendaAperta = false

    /// Dall'alto in basso come sul campo: attacco in alto, portiere in basso.
    private let ruoli = ["A", "C", "D", "P"]
    private let nomiRuolo = ["P": "Portiere", "D": "Difensori", "C": "Centrocampisti", "A": "Attaccanti"]

    /// Cosa fa ogni stile, a parole (come il server e la web app): vedi `StileFormazione`.
    static func descrizioneStile(_ rischio: Int) -> String { StileFormazione.descrizione(rischio) }

    var body: some View {
        NavigationStack {
            ZStack {
                Sfondo()
                ScrollView {
                    Colonne(spazio: Tema.spazioSchede) {
                        if let f = vm.formazione {
                            bannerSquadra
                            let v = vm.vista(f)
                            cardStile(f, v).ingresso(0)
                            if !legendaVista {
                                Carta("Come si legge il campo", simbolo: "info.circle") {
                                    LegendaCampo { withAnimation(Tema.morbida) { legendaVista = true } }
                                }
                                .ingresso(2)
                            }
                            Carta("Campo", simbolo: "sportscourt") {
                                CampoFormazione(titolari: v.titolari, apribile: true)
                                notaScelta(vm.righeScelta(f))
                                if legendaVista { pulsanteLegenda }
                            }
                            .ingresso(3)
                            // Un'unica scheda con i quattro reparti in ordine (Portiere, Difensori, Centrocampisti, Attaccanti):
                            // sull'iPad le colonne si leggono così dall'alto in basso senza saltare da una parte all'altra.
                            Carta("Titolari", simbolo: "person.3.fill") {
                                ForEach(ruoli, id: \.self) { r in
                                    let gruppo = v.titolari.filter { $0.ruolo == r }
                                    if !gruppo.isEmpty {
                                        Text("\(nomiRuolo[r] ?? r) (\(gruppo.count))").titoletto().padding(.top, 4)
                                        ForEach(gruppo) { g in rigaTitolare(g, f, v) }
                                    }
                                }
                            }
                            .ingresso(4)
                            Carta("Panchina", simbolo: "chair.lounge.fill") {
                                Text("In quest'ordine: entra il primo che può sostituire chi resta senza voto.").font(.caption).foregroundStyle(Color.testoSecondario)
                                ForEach(Array(v.panchina.enumerated()), id: \.element.id) { i, g in
                                    RigaConFilo(prima: i == 0) { RigaGiocatore(g: g, apribile: true, perche: apriPerche) }
                                }
                            }
                            .ingresso(5)
                            fuori(f, v)
                            Text(Self.legenda(conPerche: f.titolari.contains { PercheNumero($0) != nil }))
                                .font(.caption).foregroundStyle(Color.testoSecondario).padding(.horizontal, 4)
                        } else if let errore = vm.errore {
                            ErroreVista(messaggio: errore) { Task { await vm.carica() } }
                        } else {
                            Scheletro(schede: 3, righe: 3, testo: "Scelgo gli undici…")
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
                            Button { vm.preparaImmagine(f) } label: { Label("Condividi come immagine", systemImage: "photo") }
                            Button { vm.copiaTesto(f) } label: { Label("Copia il testo", systemImage: "doc.on.doc") }
                        } label: {
                            Image(systemName: "square.and.arrow.up").frame(minWidth: 44, minHeight: 44)
                        }
                        .sensoryFeedback(trigger: vm.anteprimaImmagine?.id) { _, nuovo in nuovo != nil ? .success : nil }
                        .accessibilityLabel("Condividi la formazione")
                    }
                }
            }
            .ricercaGlobale()
            .sheet(item: $daSostituire) { g in
                if let f = vm.formazione {
                    SostituzioneSheet(uscente: g, candidati: vm.sostituti(di: g, f)) { nuovo in
                        vm.sostituisci(g.id, con: nuovo)
                        daSostituire = nil
                    }
                }
            }
            .sheet(item: $vm.confrontoAperto) { inizio in
                ConfrontoSheet(inizio: inizio, contesto: vm.contestoConfronto, server: vm.server)
            }
            .sheet(item: $vm.anteprimaImmagine) { immagine in
                AnteprimaImmagineSheet(elemento: immagine)
            }
            .sheet(item: $vm.percheAperto, onDismiss: {
                if let id = schedaDopoPerche {
                    schedaDopoPerche = nil
                    apriGiocatore(id)
                }
            }) { g in
                PercheNumeroSheet(g: g) {
                    schedaDopoPerche = g.id
                    vm.percheAperto = nil
                }
            }
            .task { await vm.carica() }
        }
    }

    /// Riapre la legenda del campo (popover sull'iPad, foglio sull'iPhone).
    private var pulsanteLegenda: some View {
        Button { legendaAperta = true } label: {
            Label("Cosa vuol dire", systemImage: "info.circle").font(.footnote.weight(.semibold))
                .frame(minHeight: 44).contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .foregroundStyle(Color.verde)
        .accessibilityHint("Apre la legenda del campo")
        .popover(isPresented: $legendaAperta) {
            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    Text("Come si legge il campo").font(.headline).accessibilityAddTraits(.isHeader)
                    LegendaCampo()
                }
                .padding(20)
            }
            .frame(minWidth: 320, idealWidth: 380)
            .presentationDetents([.medium, .large])
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

    /// Il tocco sul numero di un giocatore: apre «Perché questo numero» con i dati già caricati.
    private var apriPerche: (Giocatore) -> Void {
        { g in vm.percheAperto = g }
    }

    /// La riga in fondo alla Formazione: cosa sono i numeri (e, con un server che manda i motivi, che si possono toccare).
    static func legenda(conPerche: Bool) -> String {
        "Il numero è il fantavoto atteso: quello che SchieraXI si aspetta dal giocatore se gioca, con le regole della tua lega."
            + (conPerche ? " Toccalo per sapere perché." : "")
            + " I punti attesi della squadra pesano ogni fantavoto per la probabilità di giocare. Negli elenchi il numero sul volto è l'indice: 100 = il migliore del suo ruolo questa giornata."
    }

    // MARK: un'altra squadra

    @ViewBuilder
    private var bannerSquadra: some View {
        if let nome = vm.squadraVista {
            Carta {
                Label("Stai guardando la formazione di \(nome)", systemImage: "eye").font(.subheadline)
                Button { vm.tornaAllaMia() } label: { Text("Torna alla tua").frame(minHeight: 44) }
                    .pulsanteVetro()
            }
        }
    }

    // MARK: righe

    /// In modifica a mano ogni titolare è un bottone che apre la scelta del sostituto (tranne chi gioca un anticipo già cominciato:
    /// `vm.fermi`); altrimenti un tocco apre la scheda, «⇄» confronta con un altro della rosa e sotto i titolari incerti ci sono le
    /// alternative vicine (ballottaggio).
    @ViewBuilder
    private func rigaTitolare(_ g: Giocatore, _ f: Formazione, _ v: VistaFormazione) -> some View {
        if vm.chiusa {
            // giornata chiusa: sola lettura (un tocco apre la scheda, niente sostituzioni né confronti per cambiare)
            RigaGiocatore(g: g, apribile: true, perche: apriPerche)
        } else if vm.manuale != nil && !vm.fermi.contains(g.id) {
            Button { daSostituire = g } label: {
                HStack { RigaGiocatore(g: g); Image(systemName: "arrow.left.arrow.right").foregroundStyle(Color.verde).accessibilityHidden(true) }
                    .frame(minHeight: 44)
            }
            .buttonStyle(StilePressione())
            .accessibilityHint("Apre la scelta del giocatore che prende il suo posto")
        } else {
            VStack(alignment: .leading, spacing: 4) {
                HStack(spacing: 4) {
                    RigaGiocatore(g: g, apribile: true, perche: apriPerche)
                    Button { vm.confrontoAperto = .scelta(g.id) } label: {
                        Image(systemName: "arrow.left.arrow.right").frame(minWidth: 44, minHeight: 44).contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                    .foregroundStyle(Color.verde)
                    .accessibilityLabel("Confronta \(g.nome) con un altro della rosa")
                }
                // in modifica a mano qui c'è solo chi è fermo (anticipo già cominciato, #373): come la web, ⇄ e niente ballottaggio
                if vm.manuale == nil { ballottaggio(g, f, v) }
            }
        }
    }

    @ViewBuilder
    private func ballottaggio(_ g: Giocatore, _ f: Formazione, _ v: VistaFormazione) -> some View {
        let alternative = vm.ballottaggio(per: g, f, v)
        if !alternative.isEmpty {
            VStack(alignment: .leading, spacing: 4) {
                Text("Ballottaggio · alternative vicine").font(.caption).foregroundStyle(Color.testoSecondario)
                ViewThatFits(in: .horizontal) {
                    HStack(spacing: 8) { ForEach(alternative) { a in chipAlternativa(a, rispetto: g) } }
                    VStack(alignment: .leading, spacing: 6) { ForEach(alternative) { a in chipAlternativa(a, rispetto: g) } }
                }
            }
            .padding(.leading, 58)
        }
    }

    private func chipAlternativa(_ a: Ballottaggio.Alternativa, rispetto g: Giocatore) -> some View {
        Button { vm.confrontoAperto = .coppia(g.id, a.giocatore.id) } label: {
            HStack(spacing: 5) {
                Text(a.giocatore.nomeCorto).font(.caption.weight(.semibold))
                Text(Formato.conSegno(a.differenza)).font(.caption.bold()).monospacedDigit()
                    .foregroundStyle(a.quasiPari ? Color.testoSecondario : (a.differenza > 0 ? Color.verde : Color.attenzione))
                if a.quasiPari { Text("quasi pari").font(.caption2).foregroundStyle(Color.testoSecondario) }
            }
            .padding(.horizontal, 10)
            .frame(minHeight: 44)
            .background(Color.sfondoIncavo, in: Capsule())
        }
        .buttonStyle(StilePressione())
        .accessibilityLabel("Confronta \(g.nome) con \(a.giocatore.nome), \(Formato.conSegno(a.differenza)) punti attesi\(a.quasiPari ? ", quasi pari" : "")")
    }

    @ViewBuilder
    private func fuori(_ f: Formazione, _ v: VistaFormazione) -> some View {
        let altri = vm.fuori(f, v)
        if !altri.isEmpty || !(f.senzaDati ?? []).isEmpty {
            Carta {
                DisclosureGroup("Fuori dalla formazione (\(altri.count))") {
                    VStack(alignment: .leading, spacing: 8) {
                        ForEach(altri) { RigaGiocatore(g: $0, apribile: true, perche: apriPerche) }
                        if let senza = f.senzaDati, !senza.isEmpty {
                            Text("Senza dati per questa giornata: " + senza.joined(separator: ", ")).font(.caption).foregroundStyle(Color.testoSecondario)
                        }
                    }
                    .padding(.top, 6)
                }
                .tint(Color.testoSecondario)
            }
        }
    }

    // MARK: stile, modulo e punti (una sola card)

    /// Giornata, punti, stile con la sua descrizione, modulo proposto e «Modifica a mano» in una card compatta:
    /// il campo parte subito sotto.
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
                Label("Probabili formazioni non ancora uscite: uso le presenze recenti.", systemImage: "clock").font(.footnote).foregroundStyle(Color.testoSecondario)
            }
            rigaStato(f)
            if vm.chiusa {
                if let r = vm.valutazioneAttuale, let d = r.differenza { rigaDifferenza(r, d) }
            } else if vm.manuale == nil {
                if let livelli = f.livelli, !livelli.isEmpty { sceltaStile(f, livelli) }
            } else {
                testoManuale
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
                                          comeConsigliato: v.modulo == f.modulo && vm.rischio == (f.stileConsigliato ?? 0)))
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
                Text(TestoACapo.soloTraIPezzi("punti attesi" + (vm.fascia(f).map { TestoACapo.separatore + $0 } ?? "")))
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
                            salvaQuesta: { salvaQuesta(f) },
                            tornaAllaConsigliata: { tornaAllaConsigliata(f) })
        }
    }

    private func salvaQuesta(_ f: Formazione) {
        Task { await vm.salvaQuesta(f) }
    }

    private func tornaAllaConsigliata(_ f: Formazione) {
        Task { await vm.tornaAllaConsigliata(f) }
    }

    /// Gli stili come scelte in fila, la loro descrizione, il modulo proposto e i moduli.
    @ViewBuilder
    private func sceltaStile(_ f: Formazione, _ livelli: [LivelloRischio]) -> some View {
        let livello = livelli.first(where: { $0.rischio == vm.rischio }) ?? livelli[0]
        let consigliato = f.stileConsigliato ?? 0
        // «Stili a 3 livelli» spenta (di norma): più sicura, equilibrata, più rischiosa (e lo stile in uso, se è un altro). Accesa: tutti e 5.
        let visibili = funzioni.acceso(Funzione.stiliRidotti) ? livelli : livelli.filter { $0.rischio == livello.rischio || abs($0.rischio) < 2 }
        FilaScorrevole {
            ForEach(visibili) { l in
                let attivo = l.rischio == livello.rischio
                Button { withAnimation(Tema.molla) { vm.scegliStile(l.rischio) } } label: {
                    Text(l.nome + (l.rischio == consigliato ? " ★" : ""))
                        .font(.subheadline.bold())
                        .padding(.horizontal, 14)
                        .frame(minHeight: 44)
                        .pillola(attiva: attivo, spazio: stileNS)
                }
                .buttonStyle(StilePressione())
                .accessibilityLabel("Stile \(l.nome)\(l.rischio == consigliato ? ", consigliato" : "")")
                .accessibilityAddTraits(attivo ? .isSelected : [])
            }
        }
        (Text(livello.nome).bold() + Text(" · " + (livello.descrizione ?? Self.descrizioneStile(livello.rischio))
                                          + (StileFormazione.stellaNonMassimo(livello).map { " " + $0 } ?? "")))
            .font(.footnote).foregroundStyle(Color.testoSecondario)
            .fixedSize(horizontal: false, vertical: true)
        HStack {
            Text("Modulo proposto: \(livello.modulo)").font(.footnote.weight(.semibold))
            Spacer()
            modificaAMano(f)
        }
        FilaScorrevole {
            ForEach(livello.moduli) { m in
                let attivo = vm.moduloAttivo(livello) == m.modulo
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
                .accessibilityLabel("Modulo \(m.modulo), \(Formato.punti(m.punteggioAtteso)) punti attesi\(m.modulo == livello.modulo ? ", proposto dallo stile" : "")")
                .accessibilityAddTraits(attivo ? .isSelected : [])
            }
        }
    }

    /// Pulsante piccolo (l'area di tocco resta da 44 pt).
    private func modificaAMano(_ f: Formazione) -> some View {
        Button { vm.iniziaModificaManuale(f) } label: {
            Label("Modifica a mano", systemImage: "hand.tap").font(.footnote.weight(.semibold))
                .padding(.horizontal, 10).padding(.vertical, 5)
                .background(Color.sfondoIncavo, in: Capsule())
                .frame(minHeight: 44)
                .contentShape(Rectangle())
        }
        .buttonStyle(StilePressione())
        .foregroundStyle(Color.verde)
    }

    @ViewBuilder
    private var testoManuale: some View {
        Text("Tocca un titolare per sostituirlo con un altro della rosa: i punti attesi si ricalcolano.")
            .font(.footnote).foregroundStyle(Color.testoSecondario)
        if let nota = vm.notaFermi {
            Text(nota).font(.footnote).foregroundStyle(Color.testoSecondario)
        }
        if vm.calcoloNonRiuscito {
            Button { Task { await vm.valuta(salva: false) } } label: {
                Label("Non riesco a calcolare i punti: riprova", systemImage: "arrow.clockwise").font(.footnote.weight(.semibold))
                    .frame(minHeight: 44).contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .foregroundStyle(Color.attenzione)
        }
        if let r = vm.valutazioneAttuale, let d = r.differenza { rigaDifferenza(r, d) }
        // Affiancati se ci stanno; con il testo grande uno sotto l'altro (invece di spezzarsi su tre righe).
        if let f = vm.formazione {
            ViewThatFits(in: .horizontal) {
                HStack { salva; annulla; Spacer(); torna(f) }
                VStack(alignment: .leading, spacing: 0) { salva; annulla; torna(f) }
            }
            .font(.subheadline)
        }
    }

    /// Quanto vale la formazione a mano rispetto alla consigliata. La fascia dei punti sta già nell'intestazione: qui non si ripete
    /// (solo se il server non manda né fascia né oscillazione restano brutta giornata ed eccezionale).
    private func rigaDifferenza(_ r: ValutazioneManuale, _ d: Double) -> some View {
        let confronto = "\(Formato.conSegno(d)) rispetto alla consigliata con lo stesso modulo (\(Formato.punti(r.consigliataStessoModulo ?? r.consigliata)))."
        let estremi = IntervalloPunti.frase(r.intervallo, dev: r.dev) == nil
            ? " Brutta giornata \(Formato.intero(r.bruttaGiornata)) · giornata eccezionale \(Formato.intero(r.giornataEccezionale))." : ""
        return Text(confronto + estremi).font(.subheadline)
            // sotto mezzo punto è un pari (grigio, non arancio)
            .foregroundStyle(abs(d) < 0.5 ? Color.testoSecondario : d > 0 ? Color.verde : Color.attenzione)
    }

    /// «Salva come mia scelta» (o «Salva le modifiche»): solo se c'è qualcosa da salvare e per la propria squadra.
    @ViewBuilder
    private var salva: some View {
        let stato = vm.statoScelta
        // non mentre il server prova la scelta salvata appena letta (lo stato non si sa ancora)
        if vm.squadraVista == nil, stato.daSalvare, !vm.provaSalvata {
            Button { Task { await vm.valuta(salva: true) } } label: {
                Label(Self.etichettaSalva(stato), systemImage: "tray.and.arrow.down").fixedSize().frame(minHeight: 44)
            }
            .keyboardShortcut("s", modifiers: .command)
        }
    }

    static func etichettaSalva(_ stato: StatoScelta) -> String {
        if case .modificata = stato { return "Salva le modifiche" }
        return "Salva come mia scelta"
    }

    /// «Annulla modifiche»: si torna agli undici salvati.
    @ViewBuilder
    private var annulla: some View {
        if case .modificata = vm.statoScelta, vm.salvati != nil {
            Button { vm.annullaModifiche() } label: {
                Text("Annulla modifiche").fixedSize().frame(minHeight: 44)
            }
        }
    }

    private func torna(_ f: Formazione) -> some View {
        Button(role: .destructive) { Task { await vm.tornaAllaConsigliata(f) } } label: {
            Text("Torna alla consigliata").fixedSize().frame(minHeight: 44)
        }
    }

}

/// Scelta del sostituto: giocatori della stessa categoria che non sono già titolari né fermi (`FormazioneViewModel.sostituti`).
struct SostituzioneSheet: View {
    let uscente: Giocatore
    let candidati: [Giocatore]
    let scelto: (Int) -> Void
    @Environment(\.dismiss) private var chiudi

    var body: some View {
        NavigationStack {
            List {
                Section("Al posto di \(uscente.nome)") {
                    ForEach(candidati) { g in
                        Button { scelto(g.id) } label: { RigaGiocatore(g: g).frame(minHeight: 44) }.buttonStyle(.plain)
                    }
                    if candidati.isEmpty {
                        VistaVuota(titolo: "Nessun altro giocatore", icona: "person.slash", descrizione: "Non ci sono altri giocatori di questo ruolo in rosa.")
                    }
                }
            }
            .navigationTitle("Sostituisci")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .navigationBarTrailing) { Button("Annulla") { chiudi() } } }
        }
    }
}

/// L'immagine della formazione, con il pulsante per condividerla (menu Condividi di iOS).
struct AnteprimaImmagineSheet: View {
    let elemento: ImmagineCondivisa
    @Environment(\.dismiss) private var chiudi

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 16) {
                    Image(uiImage: elemento.immagine).resizable().scaledToFit()
                        .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
                        .frame(maxWidth: 480)
                        .accessibilityLabel("Immagine della formazione")
                    ShareLink(item: Image(uiImage: elemento.immagine), preview: SharePreview(elemento.titolo, image: Image(uiImage: elemento.immagine))) {
                        Label("Condividi l'immagine", systemImage: "square.and.arrow.up").frame(minHeight: 44)
                    }
                    .pulsanteVetro(prominente: true)
                }
                .padding(16)
                .frame(maxWidth: .infinity)
            }
            .navigationTitle("Formazione")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .navigationBarTrailing) { Button("Chiudi") { chiudi() } } }
        }
    }
}

#Preview("Formazione") {
    FormazioneView(vm: FormazioneViewModel(server: FinteServer.esempio))
}
