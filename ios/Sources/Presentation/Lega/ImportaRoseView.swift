import SwiftUI

/// Lega > Aggiorna le rose (ci porta anche il passo «rose» del primo avvio). Due passi:
/// 1) si incolla la pagina delle rose o si sceglie il file (Excel, CSV, testo);
/// 2) l'anteprima del server, che non salva niente: squadra per squadra i dubbi da sistemare, la propria squadra, poi «Conferma e salva».
/// Al primo caricamento (nessuna rosa sul server) titolo e frase sono quelli del primo avvio della web e non c'è «Togli le squadre
/// che non sono nel file» (#880). Logica in `ImportaExcelViewModel` e `AnteprimaLogica`.
struct ImportaExcelView: View {
    private let server: any ServerClient
    /// Aperta da «Importa le rose» della configurazione guidata: salvate le rose la pagina si chiude e la guida continua (#880).
    private let dallaGuida: Bool
    @StateObject private var vm: ImportaExcelViewModel
    @StateObject private var dubbi: DubbiRoseViewModel
    @EnvironmentObject private var nav: Navigazione
    @Environment(\.dismiss) private var chiudi
    @State private var scegli = false
    @State private var cerca: DubbioDaCercare?

    /// `squadre`: le squadre già lette dalle Impostazioni, se ci sono. Con loro, o arrivando dalla guida, si sa subito se le rose ci
    /// sono e la pagina non cambia testi dopo la risposta del server (revisione della #887).
    init(server: any ServerClient, dallaGuida: Bool = false, squadre: [SquadraLega]? = nil) {
        self.server = server
        self.dallaGuida = dallaGuida
        let note = ImportaExcelViewModel.roseNote(dallaGuida: dallaGuida, squadre: squadre)
        _vm = StateObject(wrappedValue: ImportaExcelViewModel(server: server, roseSalvate: note))
        _dubbi = StateObject(wrappedValue: DubbiRoseViewModel(server: server))
    }

    var body: some View {
        ZStack {
            Sfondo()
            if let r = vm.anteprima {
                AnteprimaRoseVista(vm: vm, anteprima: r) { cerca = $0 }
                    .transition(.opacity)
            } else {
                inserimento.transition(.opacity)
            }
        }
        .animation(Tema.morbida, value: vm.anteprima == nil)
        .titoloPagina(vm.titolo)
        .task { await dubbi.carica() }
        .task { await vm.leggiRoseSalvate() }
        // dalla guida, salvate le rose si torna alla guida (la riapre `RitornoAllaGuida` quando la pagina sparisce), come la web
        .onChange(of: vm.esito != nil) { _, salvate in if salvate, dallaGuida { chiudi() } }
        // Solo per le fotografie del simulatore (-DEMO_SCHERMATA lega-importa-salvate / lega-importa-salvate-ok): l'esito di un salvataggio, con dati inventati.
        .task { if vm.esito == nil, let esito = DemoEsitoRose.esito(Demo.schermata) { vm.esito = esito } }
        // dopo un salvataggio i «giocatori da sistemare» (rimasti senza codice) si rileggono
        .onChange(of: vm.inCorso) { _, ora in if !ora, vm.esito != nil { Task { await dubbi.carica() } } }
        .onChange(of: vm.errore) { _, nuovo in if let nuovo { AccessibilityNotification.Announcement(nuovo).post() } }
        .sheet(item: $dubbi.scelto) { d in
            NavigationStack { CercaGiocatoreGiustoView(vm: dubbi, dubbio: d) }
        }
        .sheet(item: $cerca) { d in
            NavigationStack {
                CercaPerAnteprimaView(server: server, dubbio: d) { c in vm.scegli(trovato: c, per: d.giocatore, squadra: d.squadra) }
            }
        }
        .fileImporter(isPresented: $scegli, allowedContentTypes: vm.tipiAmmessi, allowsMultipleSelection: false) { risultato in
            Task { await vm.importa(risultato) }
        }
        // Un file arrivato da un'altra app («Apri con SchieraXI»): passa dall'anteprima, con gli stessi controlli del selettore.
        .task(id: nav.fileDaImportare) {
            guard let url = nav.fileDaImportare else { return }
            nav.fileDaImportare = nil
            await vm.importa(.success([url]))
        }
    }

    // MARK: passo 1: cosa importare

    private var inserimento: some View {
        List {
            TitoloNellaPagina()
            // l'esito dell'ultimo salvataggio, in cima (differenza ammessa con la web: docs/COERENZA-WEB-IPHONE.md)
            if let e = vm.esito { EsitoRoseSalvate(esito: e) }
            Section {
                // finché non si sa se le rose ci sono, niente frase: potrebbe essere quella sbagliata
                if let spiegazione = vm.spiegazione {
                    Text(spiegazione)
                        .font(.footnote).foregroundStyle(Color.testoSecondario)
                }
                Button { scegli = true } label: {
                    Label(Catalogo.Pav.scegliFile, systemImage: "doc.badge.plus").frame(maxWidth: .infinity, minHeight: Tema.areaTocco, alignment: .leading)
                }
                .disabled(vm.inCorso)
                Text("Puoi anche aprire il file con SchieraXI da File, Mail o dal menu Condividi.")
                    .font(.footnote).foregroundStyle(Color.testoSecondario)
            }
            Section {
                // «… Le squadre che non sono nel file restano com'erano» e l'interruttore servono solo a chi ha già le rose
                if vm.mostraPerChiHaLeRose {
                    Text(Catalogo.Lega.nonHaiFile)
                        .font(.footnote).foregroundStyle(Color.testoSecondario)
                }
                TextEditor(text: $vm.testoRose)
                    .frame(minHeight: 110)
                    .overlay(alignment: .topLeading) {
                        if vm.testoRose.isEmpty {
                            Text(Catalogo.Lega.incollaQuiTesto)
                                .foregroundStyle(Color.testoSecondario)
                                .padding(.top, 8).padding(.leading, 5)
                                .allowsHitTesting(false)
                                .accessibilityHidden(true)
                        }
                    }
                    .accessibilityLabel(Catalogo.Lega.incollaQuiTesto)
                    .disabled(vm.inCorso)
                if vm.mostraPerChiHaLeRose {
                    Toggle(Catalogo.Lega.togliSquadreChe, isOn: $vm.sostituisciTutto).tint(Color.verde).frame(minHeight: Tema.areaTocco)
                }
                Button { Task { await vm.importaTesto() } } label: {
                    Label(Catalogo.Lega.importaTesto, systemImage: "text.magnifyingglass").frame(maxWidth: .infinity, minHeight: Tema.areaTocco)
                }
                .disabled(vm.inCorso)
            } header: { Text(Catalogo.Lega.incollaTestoDelle).foregroundStyle(Color.testoSecondario) }
            if vm.inCorso {
                Section {
                    HStack(spacing: 10) { ProgressView(); Text(Catalogo.Ar.leggo).foregroundStyle(Color.testoSecondario) }
                        .frame(minHeight: Tema.areaTocco)
                        .accessibilityElement(children: .combine)
                }
            }
            if let errore = vm.errore {
                Section { Label(errore, systemImage: "exclamationmark.triangle").foregroundStyle(Color.attenzione) }
            }
            daSistemare
        }
        .scrollContentBackground(.hidden)
    }

    /// I giocatori rimasti senza codice nelle rose salvate (lasciati così nell'anteprima, o da importazioni vecchie).
    @ViewBuilder
    private var daSistemare: some View {
        if !dubbi.dubbi.isEmpty {
            Section {
                Text("Non li ho trovati nel listone (magari ceduti o con un altro nome). Tocca un nome e cerca quello giusto; se non c'è, lascia stare.")
                    .font(.footnote).foregroundStyle(Color.testoSecondario)
                ForEach(dubbi.dubbi) { d in
                    Button { dubbi.scelto = d } label: {
                        HStack {
                            VStack(alignment: .leading, spacing: 2) {
                                Text(d.nome).foregroundStyle(.primary)
                                Text(d.squadra).font(.footnote).foregroundStyle(Color.testoSecondario)
                            }
                            Spacer()
                            Image(systemName: "magnifyingglass").foregroundStyle(Color.testoSecondario).accessibilityHidden(true)
                        }
                        .frame(minHeight: Tema.areaTocco)
                    }
                    .accessibilityLabel("\(d.nome), \(d.squadra), non riconosciuto")
                    .accessibilityHint("Cerca il giocatore giusto")
                }
            } header: { Text("Giocatori da sistemare (\(dubbi.dubbi.count))").foregroundStyle(Color.testoSecondario) }
        } else if dubbi.sistemati > 0 {
            Section { Label("Tutti i giocatori sono riconosciuti.", systemImage: "checkmark.circle").font(.footnote).foregroundStyle(Color.testoSecondario) }
        }
    }
}

// MARK: - passo 2: l'anteprima

/// Un dubbio per cui si cerca il giocatore giusto nel listone.
struct DubbioDaCercare: Identifiable, Equatable {
    let squadra: String
    let giocatore: GiocatoreAnteprima
    var testo: String { giocatore.testo }
    var id: String { AnteprimaLogica.chiave(squadra, giocatore) }
}

/// L'anteprima: riassunto, la propria squadra, una scheda per squadra (in colonne sull'iPad), «Conferma e salva».
struct AnteprimaRoseVista: View {
    @ObservedObject var vm: ImportaExcelViewModel
    let anteprima: AnteprimaRose
    let cerca: (DubbioDaCercare) -> Void
    @AccessibilityFocusState private var fuocoTitolo: Bool

    var body: some View {
        ScrollView {
            VStack(spacing: Tema.spazioSchede) {
                TitoloNellaPagina()
                testa
                if !anteprima.squadre.isEmpty { miaSquadra }
                Colonne(spazio: Tema.spazioSchede, larghezzaMinima: 320) {
                    ForEach(anteprima.squadre) { s in
                        CartaSquadraAnteprima(vm: vm, squadra: s, differenze: anteprima.differenze, cerca: cerca)
                    }
                }
                if AnteprimaLogica.mostraDifferenze(anteprima.differenze), let d = anteprima.differenze {
                    Carta {
                        DisclosureGroup {
                            DifferenzeView(differenze: d).padding(.top, 6)
                        } label: {
                            Text(Catalogo.Ar.cosaCambia).font(.subheadline.weight(.semibold)).frame(minHeight: Tema.areaTocco)
                        }
                        .tint(Color.verde)
                    }
                }
                pulsanti
            }
            .padding(.horizontal, 16).padding(.top, 8).padding(.bottom, 24)
            .frame(maxWidth: 1100)
            .frame(maxWidth: .infinity)
        }
        .bordiMorbidi()
        .onAppear { fuocoTitolo = true }
    }

    private var testa: some View {
        Carta {
            Text(Catalogo.Ar.controlla)
                .font(.title3.bold())
                .accessibilityAddTraits(.isHeader)
                .accessibilityFocused($fuocoTitolo)
            // si rifà dopo ogni scelta, come la web (#808): i dubbi già decisi non si contano più
            Text(AnteprimaLogica.riassunto(anteprima, scelte: vm.scelte)).font(.subheadline)
            if let m = vm.messaggioAnteprima {
                Label(m, systemImage: "arrow.triangle.2.circlepath").font(.footnote).foregroundStyle(Color.attenzione)
            }
            ForEach(AnteprimaLogica.avvisiGenerali(anteprima), id: \.self) { a in
                Label(a, systemImage: "info.circle").font(.footnote).foregroundStyle(Color.attenzione)
            }
        }
    }

    /// «Qual è la tua squadra?» come la web (`ar-mia` di `anteprima.js`): le squadre una accanto all'altra, a capo quando la riga è
    /// piena; scelta solo quella suggerita dal server, altrimenti nessuna, finché non la tocchi (#880: prima «Scegli dopo» era
    /// già scelto). Anche la squadra suggerita che non è nel file, per prima (#808).
    private var miaSquadra: some View {
        Carta(Catalogo.Ar.qualETua, simbolo: "star") {
            FilaPillole(spazio: 8) {
                ForEach(AnteprimaLogica.nomiMia(anteprima), id: \.self) { nome in
                    PillolaSquadraMia(nome: nome, scelta: vm.mia == nome) { vm.mia = nome }
                }
            }
            Text("La formazione consigliata è per lei.").font(.caption).foregroundStyle(Color.testoSecondario)
        }
    }

    private var pulsanti: some View {
        VStack(spacing: 10) {
            if let e = vm.errore {
                Label(e, systemImage: "exclamationmark.triangle")
                    .font(.footnote).foregroundStyle(Color.attenzione)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
            Button { Task { await vm.conferma() } } label: {
                HStack(spacing: 8) {
                    if vm.inCorso { ProgressView() }
                    Text(Catalogo.Ar.conferma)
                }
                .frame(maxWidth: .infinity, minHeight: Tema.areaTocco)
            }
            .pulsanteVetro(prominente: true)
            .disabled(vm.inCorso)
            .keyboardShortcut(.return, modifiers: .command)
            .accessibilityHint("Salva le rose con le tue scelte")
            Button { vm.annulla() } label: {
                Text(Catalogo.Ar.annulla).frame(maxWidth: .infinity, minHeight: Tema.areaTocco)
            }
            .buttonStyle(.plain)
            .foregroundStyle(Color.testoSecondario)
            .disabled(vm.inCorso)
            .keyboardShortcut(.cancelAction)
            .accessibilityHint("Torna indietro senza salvare")
        }
        .frame(maxWidth: 520)
    }
}

/// Una squadra dell'anteprima, come `anteprima.js` della web dopo il #873: il nome («Nuova» solo se si aggiunge a rose già salvate);
/// senza dubbi una riga sola da aprire con i conti e dentro i nomi; con dei dubbi la riga dei conti, i dubbi, poi i riconosciuti
/// ripiegati.
struct CartaSquadraAnteprima: View {
    @ObservedObject var vm: ImportaExcelViewModel
    let squadra: SquadraAnteprima
    /// Le differenze dell'anteprima: alla prima importazione niente «Nuova» (#873).
    let differenze: Differenze?
    let cerca: (DubbioDaCercare) -> Void
    @State private var sicuriAperti = false

    var body: some View {
        let nelRipiegato = AnteprimaLogica.contiNelRipiegato(squadra)
        Carta {
            HStack(alignment: .firstTextBaseline, spacing: 8) {
                Text(squadra.nome).font(.headline).accessibilityAddTraits(.isHeader)
                if AnteprimaLogica.mostraNuova(squadra, differenze: differenze) {
                    Capsula(testo: Catalogo.Ar.nuova, colore: Color.informazione, simbolo: "sparkles")
                }
                Spacer(minLength: 0)
            }
            if !nelRipiegato { conti }
            ForEach(AnteprimaLogica.dubbi(squadra), id: \.chiaveInSquadra) { g in
                RigaDubbioAnteprima(
                    squadra: squadra.nome, giocatore: g,
                    scelta: vm.scelta(per: g, squadra: squadra.nome),
                    opzioni: vm.opzioni(per: g, squadra: squadra.nome),
                    scegli: { vm.scegli($0, per: g, squadra: squadra.nome) },
                    cerca: { cerca(DubbioDaCercare(squadra: squadra.nome, giocatore: g)) })
            }
            if squadra.sicuri > 0 {
                DisclosureGroup(isExpanded: $sicuriAperti) {
                    Text(nomiSicuri).font(.caption).foregroundStyle(Color.testoSecondario).frame(maxWidth: .infinity, alignment: .leading)
                } label: {
                    if nelRipiegato {
                        conti.frame(maxWidth: .infinity, minHeight: Tema.areaTocco, alignment: .leading)
                    } else {
                        Text(Catalogo.Ar.riconosciuti(squadra.sicuri))
                            .font(.subheadline).frame(minHeight: Tema.areaTocco)
                    }
                }
                .tint(Color.verde)
            }
        }
    }

    /// I conti in una riga, come `ar-conti` della web: «25 giocatori · 12 crediti · Rosa completa», oppure i problemi della rosa
    /// («Manca 1 portiere») nel colore d'attenzione. Le parole dicono già tutto: simbolo e colore aiutano solo a vederlo.
    private var conti: some View {
        let problemi = AnteprimaLogica.problemi(squadra)
        let completa = problemi.isEmpty
        let testoStato = completa ? Catalogo.Ar.rosaCompleta : problemi.joined(separator: " · ")
        let simbolo = completa ? "checkmark.circle" : "exclamationmark.triangle"
        let stato: Text = Text("\(Image(systemName: simbolo)) \(testoStato)")
            .foregroundStyle(completa ? Color.verde : Color.attenzione)
        let conteggio = AnteprimaLogica.conteggio(squadra)
        return Text("\(Text(conteggio + " · ").foregroundStyle(Color.testoSecondario))\(stato)")
            .font(.footnote)
            .fixedSize(horizontal: false, vertical: true)
            .accessibilityLabel("\(conteggio), \(testoStato)")
    }

    private var nomiSicuri: String {
        squadra.giocatori.filter { $0.stato == .sicuro }.map { $0.nome ?? $0.testo }.joined(separator: ", ")
    }
}

/// Un dubbio: il nome com'era scritto, perché è un dubbio, e il menu per scegliere chi è (o toglierlo).
struct RigaDubbioAnteprima: View {
    let squadra: String
    let giocatore: GiocatoreAnteprima
    let scelta: SceltaDubbio
    let opzioni: [CandidatoAnteprima]
    let scegli: (SceltaDubbio) -> Void
    let cerca: () -> Void

    private var nonTrovato: Bool { giocatore.stato == .nonTrovato }
    private var testoScelta: String { AnteprimaLogica.testoScelta(scelta, giocatore, opzioni: opzioni) }

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Divider()
            HStack(alignment: .firstTextBaseline, spacing: 8) {
                Text("«\(giocatore.testo)»")
                    .font(.subheadline.weight(.semibold))
                    .strikethrough(scelta == .togli)
                Spacer(minLength: 4)
                Capsula(testo: nonTrovato ? Catalogo.Ar.nonTrovato : Catalogo.Ar.daControllare,
                        colore: nonTrovato ? Color.malus : Color.attenzione,
                        simbolo: nonTrovato ? "questionmark.circle" : "exclamationmark.circle")
            }
            .accessibilityElement(children: .combine)
            if let avviso = giocatore.avviso, !avviso.isEmpty {
                Text(avviso).font(.caption).foregroundStyle(Color.testoSecondario)
            }
            Menu {
                Section {
                    ForEach(opzioni) { c in
                        Button { scegli(.giocatore(c.id)) } label: {
                            if scelta == .giocatore(c.id) {
                                Label(AnteprimaLogica.descrivi(c), systemImage: "checkmark")
                            } else {
                                Text(AnteprimaLogica.descrivi(c))
                            }
                        }
                    }
                }
                if nonTrovato || giocatore.id == nil {
                    Button { scegli(.lascia) } label: {
                        if scelta == .lascia { Label(Catalogo.Ar.lasciaCosi, systemImage: "checkmark") } else { Text(Catalogo.Ar.lasciaCosi) }
                    }
                }
                Button(action: cerca) { Label(Catalogo.Ar.cercoIo, systemImage: "magnifyingglass") }
                Button(role: .destructive) { scegli(.togli) } label: { Label(Catalogo.Ar.togli, systemImage: "trash") }
            } label: {
                HStack(spacing: 8) {
                    Text(testoScelta)
                        .font(.subheadline)
                        .foregroundStyle(scelta == .togli ? Color.malus : Color.primary)
                        .multilineTextAlignment(.leading)
                    Spacer(minLength: 4)
                    Image(systemName: "chevron.up.chevron.down").font(.caption).foregroundStyle(Color.testoSecondario).accessibilityHidden(true)
                }
                .padding(.horizontal, 12)
                .frame(minHeight: Tema.areaTocco)
                .background(Color.sfondoIncavo, in: RoundedRectangle(cornerRadius: Tema.raggioPiccolo, style: .continuous))
                .contentShape(Rectangle())
            }
            .accessibilityLabel(Catalogo.Ar.chiE(nome: giocatore.testo, squadra: squadra))
            .accessibilityValue(testoScelta)
            .accessibilityHint("Apre le scelte per questo giocatore")
            if nonTrovato && scelta == .lascia {
                Button(action: cerca) {
                    Label("Cerca il giocatore giusto", systemImage: "magnifyingglass").font(.subheadline).frame(minHeight: Tema.areaTocco)
                }
                .buttonStyle(.borderless)
                .tint(Color.verde)
            }
        }
    }
}

/// Cerca nel listone il giocatore giusto per un dubbio dell'anteprima (niente si salva: diventa la scelta di quel dubbio).
struct CercaPerAnteprimaView: View {
    let server: any ServerClient
    let dubbio: DubbioDaCercare
    let scelto: (CandidatoAnteprima) -> Void
    @Environment(\.dismiss) private var chiudi
    @State private var testo = ""
    @State private var trovati: [GiocatoreBreve] = []
    @State private var cercando = false
    @State private var errore: String?
    @FocusState private var fuoco: Bool

    var body: some View {
        List {
            Section {
                TextField(Catalogo.Ar.cercaSegnaposto, text: $testo)
                    .textInputAutocapitalization(.words)
                    .autocorrectionDisabled()
                    .submitLabel(.search)
                    .focused($fuoco)
                    .frame(minHeight: Tema.areaTocco)
                    .accessibilityLabel(Catalogo.Ar.cercaPer(nome: dubbio.testo))
            } footer: { Text("Nella rosa di \(dubbio.squadra) c'è scritto «\(dubbio.testo)».").foregroundStyle(Color.testoSecondario) }
            if let errore { Section { Text(errore).foregroundStyle(Color.attenzione) } }
            Section {
                if cercando { ProgressView() }
                ForEach(trovati) { g in
                    let c = CandidatoAnteprima(g)
                    Button {
                        scelto(c)
                        chiudi()
                    } label: {
                        Text(AnteprimaLogica.descrivi(c)).frame(maxWidth: .infinity, minHeight: Tema.areaTocco, alignment: .leading)
                    }
                }
                if !cercando, trovati.isEmpty, testo.trimmingCharacters(in: .whitespaces).count >= 2 {
                    Text("Nessun risultato").font(.footnote).foregroundStyle(Color.testoSecondario)
                }
            }
        }
        .navigationTitle("Giocatore giusto")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar { ToolbarItem(placement: .cancellationAction) { Button(Catalogo.Ar.annulla) { chiudi() } } }
        .task(id: testo) { await cercaNelListone() }
        .onAppear { fuoco = true }
    }

    private func cercaNelListone() async {
        let scritto = testo.trimmingCharacters(in: .whitespacesAndNewlines)
        guard scritto.count >= 2 else { trovati = []; return }
        try? await Task.sleep(nanoseconds: 300_000_000)   // si aspetta che finisca di scrivere
        if Task.isCancelled { return }
        cercando = true
        defer { cercando = false }
        do {
            let r: [GiocatoreBreve] = try await server.get("/api/giocatori?limite=6&q=\(IndirizzoServer.codifica(scritto))")
            if Task.isCancelled { return }
            trovati = r
            errore = nil
        } catch {
            if Task.isCancelled || error is CancellationError { return }
            errore = ImportaExcelViewModel.testo(error)
        }
    }
}

#Preview("Aggiorna le rose") {
    NavigationStack { ImportaExcelView(server: FinteServer.esempio) }
        .environmentObject(Navigazione())
}
