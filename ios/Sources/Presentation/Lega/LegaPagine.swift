import SwiftUI

/// Il tasto «Aggiorna i dati» con il suo stato: da mettere dentro una `Section` di una `List`.
struct AggiornaDatiSezione: View {
    @ObservedObject var vm: AggiornaDatiViewModel

    var body: some View {
        Button { Task { await vm.avvia() } } label: {
            Label(vm.inCorso ? "Aggiornamento in corso…" : "Aggiorna i dati", systemImage: "arrow.triangle.2.circlepath")
                .symbolEffect(.variableColor.iterative, isActive: vm.inCorso)
                .frame(minHeight: 44)
        }
        .disabled(vm.inCorso)
        .sensoryFeedback(trigger: vm.inCorso) { vecchio, nuovo in vecchio && !nuovo ? .success : nil }
        .accessibilityHint("Il server riscarica calendario, voti, probabili formazioni e quotazioni")
        if let m = vm.messaggio {
            Text(m).font(.footnote).foregroundStyle(vm.errori.isEmpty ? Color.secondary : Color.orange)
        }
    }
}

// MARK: - Cosa è cambiato nelle rose

/// Scambi, svincolati presi, giocatori lasciati liberi e crediti cambiati tra due importazioni delle rose.
struct DifferenzeView: View {
    let differenze: Differenze

    private func nomi(_ giocatori: [GiocatoreMovimento]) -> String { giocatori.map(\.nome).joined(separator: ", ") }

    private func voce(_ icona: String, _ colore: Color, _ testo: String) -> some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: icona).foregroundStyle(colore).frame(width: 22).accessibilityHidden(true)
            Text(testo).font(.subheadline)
            Spacer(minLength: 0)
        }
        .accessibilityElement(children: .combine)
    }

    private var vuoto: Bool {
        (differenze.scambi ?? []).isEmpty && (differenze.svincolatiPresi ?? []).isEmpty
            && (differenze.tagliati ?? []).isEmpty && (differenze.crediti ?? []).isEmpty
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            if differenze.primaImportazione == true {
                Text(differenze.testo ?? "Prima importazione.").font(.subheadline)
            } else if differenze.nessunaDifferenza == true || (vuoto && (differenze.testo ?? "").isEmpty) {
                voce("checkmark.circle", Color.verde, "Nessuna differenza rispetto a prima.")
            } else {
                ForEach(differenze.scambi ?? []) { s in
                    let squadre = s.squadre.count == 2 ? "\(s.squadre[0]) → \(s.squadre[1])" : s.squadre.joined(separator: ", ")
                    let contro = s.daB.isEmpty ? "" : " contro " + nomi(s.daB)
                    voce("arrow.left.arrow.right", Color.verde, "\(s.daB.isEmpty ? "Passaggio" : "Scambio") \(squadre): \(nomi(s.daA))\(contro)")
                }
                ForEach(differenze.svincolatiPresi ?? []) { g in
                    voce("plus.circle.fill", Color.verde, "\(g.squadra) prende dagli svincolati: \(nomi(g.giocatori))")
                }
                ForEach(differenze.tagliati ?? []) { g in
                    voce("minus.circle.fill", .orange, "\(g.squadra) lascia liberi: \(nomi(g.giocatori))")
                }
                ForEach(differenze.crediti ?? []) { c in
                    voce("eurosign.circle", .secondary,
                         "Crediti \(c.squadra): \(c.prima.map { String(Formato.intero($0)) } ?? "–") → \(c.dopo.map { String(Formato.intero($0)) } ?? "–")")
                }
                if vuoto, let t = differenze.testo { Text(t).font(.subheadline) }
            }
        }
    }
}

/// Lo storico dei cambiamenti alle rose, dal più recente.
struct MovimentiView: View {
    @StateObject private var vm: MovimentiViewModel

    init(server: any ServerClient) {
        _vm = StateObject(wrappedValue: MovimentiViewModel(server: server))
    }

    var body: some View {
        ZStack {
            Sfondo()
            List {
                if let elenco = vm.caricatore.dato {
                    if elenco.isEmpty {
                        VistaVuota(titolo: "Nessun movimento", icona: "arrow.left.arrow.right",
                                   descrizione: "Quando importi di nuovo le rose, qui compaiono scambi, svincolati presi, tagli e crediti cambiati.")
                    }
                    ForEach(elenco) { m in
                        Section(Quando.leggibile((m.quando ?? "").replacingOccurrences(of: "T", with: " "))) {
                            DifferenzeView(differenze: m)
                        }
                    }
                } else if let e = vm.caricatore.errore {
                    ErroreVista(messaggio: e) { Task { await vm.carica() } }
                } else {
                    ScheletroRighe(righe: 5).listRowBackground(Color.clear)
                }
            }
            .scrollContentBackground(.hidden)
        }
        .navigationTitle("Movimenti")
        .ricercaGlobale()
        .refreshable { await vm.carica() }
        .task { await vm.carica() }
    }
}

// MARK: - Passaggio di stagione

/// Quando le rose sono di una stagione finita: archivia e riparti da rose vuote, poi i passi per la stagione nuova.
struct StagioneView: View {
    @StateObject private var vm: StagioneViewModel
    @State private var conferma = false

    init(server: any ServerClient) {
        _vm = StateObject(wrappedValue: StagioneViewModel(server: server))
    }

    var body: some View {
        ZStack {
            Sfondo()
            List {
                if let s = vm.stato.dato {
                    if vm.archiviata {
                        Section {
                            Label("Stagione \(s.rose ?? "") archiviata", systemImage: "checkmark.seal.fill").font(.headline).foregroundStyle(Color.verde)
                            Text("Tutto è salvato nell'archivio del server (lega/archivio). Ora prepara la nuova stagione:").font(.footnote).foregroundStyle(.secondary)
                        }
                        passi
                    } else if s.nuova == true {
                        Section {
                            Text("Nuova stagione \(s.corrente ?? "")").font(.headline)
                            Text("Le rose sono ancora quelle del \(s.rose ?? ""). Archivio rose, regole, scelte e osservati e riparto da rose vuote (stessi nomi di squadra): poi importi il nuovo Excel di Leghe. Non si cancella niente.")
                                .font(.footnote).foregroundStyle(.secondary)
                            Button(role: .destructive) { conferma = true } label: {
                                if vm.inCorso { ProgressView().frame(maxWidth: .infinity, minHeight: 44) }
                                else { Label("Archivia e riparti", systemImage: "archivebox").frame(maxWidth: .infinity, minHeight: 44) }
                            }
                            .disabled(vm.inCorso)
                            if let e = vm.errore { Text(e).font(.footnote).foregroundStyle(.orange) }
                        }
                    } else {
                        Section {
                            Label("Le rose sono della stagione in corso (\(s.corrente ?? "")): non c'è niente da fare.", systemImage: "checkmark.circle")
                                .font(.subheadline)
                            Text("Quando la stagione finisce e inizia la successiva, qui compare il passaggio guidato.").font(.footnote).foregroundStyle(.secondary)
                        }
                    }
                } else if let e = vm.stato.errore {
                    ErroreVista(messaggio: e) { Task { await vm.carica() } }
                } else {
                    ScheletroRighe(righe: 5).listRowBackground(Color.clear)
                }
            }
            .scrollContentBackground(.hidden)
        }
        .navigationTitle("Nuova stagione")
        .ricercaGlobale()
        .task { await vm.carica() }
        // Conferma esplicita: archiviare cambia le rose, le regole e le scelte salvate.
        .confirmationDialog("Archivio la stagione \(vm.stato.dato?.rose ?? "") e riparto da rose vuote?", isPresented: $conferma, titleVisibility: .visible) {
            Button("Archivia e riparti", role: .destructive) { Task { await vm.archiviaERiparti() } }
            Button("Annulla", role: .cancel) {}
        } message: {
            Text("Rose, regole, scelte e osservati restano salvati nell'archivio del server.")
        }
    }

    private var passi: some View {
        Section("Passi per la nuova stagione") {
            NavigationLink(value: PaginaLega.importa) {
                passo("1", "Importa le nuove rose", "Con l'Excel di Leghe, da «Aggiorna le rose».")
            }
            NavigationLink(value: PaginaLega.regole) {
                passo("2", "Controlla le regole", "Bonus, moduli e crediti possono cambiare da un anno all'altro.")
            }
            NavigationLink(value: PaginaLega.crediti) {
                passo("3", "Inserisci i crediti delle squadre", "Servono al mercato per dirti se un cambio è fattibile.")
            }
            NavigationLink(value: PaginaLega.stato) {
                passo("4", "Aggiorna i dati", "Calendario, listone e quotazioni nuovi.")
            }
            passo("5", "Prima dell'asta guarda Mercato > Asta", "Budget e prezzi consigliati.")
        }
    }

    private func passo(_ numero: String, _ titolo: String, _ dettaglio: String) -> some View {
        HStack(alignment: .top, spacing: 12) {
            Text(numero).font(.headline).frame(width: 28, height: 28).background(Color.verde.opacity(0.25), in: Circle()).accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 2) {
                Text(titolo).font(.subheadline.bold())
                Text(dettaglio).font(.caption).foregroundStyle(.secondary)
            }
        }
        .frame(minHeight: 44)
        .accessibilityElement(children: .combine)
    }
}

// MARK: - Aspetto

/// Colore principale, tema, densità, animazioni e sezione di avvio. Le scelte stanno sul telefono (`@AppStorage`).
struct AspettoView: View {
    @AppStorage("accento") private var accento = "verde"
    @AppStorage("tema") private var tema = "auto"
    @AppStorage("densita") private var densita = "comoda"
    @AppStorage("animazioniRidotte") private var animazioniRidotte = false
    @AppStorage("fotoGiocatori") private var fotoGiocatori = true
    @AppStorage("sezioneAvvio") private var sezioneAvvio = "ultima"

    var body: some View {
        ZStack {
            Sfondo()
            List {
                Section("Tema") {
                    Picker("Tema", selection: $tema) {
                        Text("Automatico").tag("auto")
                        Text("Chiaro").tag("chiaro")
                        Text("Scuro").tag("scuro")
                    }
                    .pickerStyle(.segmented)
                    .sensoryFeedback(.selection, trigger: tema)
                    Text("Automatico segue il chiaro e lo scuro di iPhone. La dimensione del testo si cambia in Impostazioni > Schermo e luminosità > Dimensione del testo: l'app la segue.")
                        .font(.footnote).foregroundStyle(.secondary)
                }
                Section("Colore principale") {
                    ViewThatFits(in: .horizontal) {
                        HStack(spacing: 12) { colori }
                        LazyVGrid(columns: [GridItem(.adaptive(minimum: 52), spacing: 10)], spacing: 10) { colori }
                    }
                }
                Section("Densità") {
                    Picker("Densità", selection: $densita) {
                        Text("Comoda").tag("comoda")
                        Text("Compatta").tag("compatta")
                    }
                    .pickerStyle(.segmented)
                    Text("Compatta stringe i margini delle schede: ci sta più roba sullo schermo. Le aree di tocco restano grandi.")
                        .font(.footnote).foregroundStyle(.secondary)
                }
                Section {
                    Toggle("Foto dei giocatori", isOn: $fotoGiocatori).tint(Color.verde).frame(minHeight: 44)
                } footer: {
                    Text("Accese: il volto ritagliato di chi ce l'ha, sullo stesso cerchio con i colori della squadra; chi non ha la foto ha la stessa sagoma con le iniziali. Spente: tutti con la sagoma, e l'app non scarica foto.")
                }
                Section {
                    Toggle("Animazioni ridotte", isOn: $animazioniRidotte).tint(Color.verde).frame(minHeight: 44)
                } footer: { Text("Toglie le animazioni dell'app (oltre a quelle che iOS già riduce se attivi «Riduci movimento»).") }
                Section("All'apertura mostra") {
                    Picker("All'apertura mostra", selection: $sezioneAvvio) {
                        Text("L'ultima sezione").tag("ultima")
                        ForEach(Sezione.allCases) { Text($0.titolo).tag($0.rawValue) }
                    }
                    .frame(minHeight: 44)
                }
            }
            .scrollContentBackground(.hidden)
        }
        .navigationTitle("Aspetto")
    }

    @ViewBuilder
    private var colori: some View {
        ForEach(Accento.allCases) { a in
            Button { accento = a.rawValue } label: {
                Circle()
                    .fill(Color(uiColor: a.scuro))
                    .frame(width: 44, height: 44)
                    .overlay(Circle().strokeBorder(Color.primary.opacity(0.25), lineWidth: 1))
                    .overlay {
                        if accento == a.rawValue {
                            Image(systemName: "checkmark").font(.headline.bold()).foregroundStyle(.black.opacity(0.75))
                                .transizione(.scale.combined(with: .opacity))
                        }
                    }
                    .scaleEffect(accento == a.rawValue ? 1.1 : 1)
                    .animation(Tema.molla, value: accento)
            }
            .buttonStyle(.plain)
            .sensoryFeedback(.selection, trigger: accento)
            .accessibilityLabel(a.nome)
            .accessibilityAddTraits(accento == a.rawValue ? .isSelected : [])
        }
    }
}

// MARK: - Icona dell'app

/// Le icone alternative dell'app: il verde è quella normale, le altre sono «AppIcon-<colore>» nell'asset catalog.
enum IconeApp {
    static let nomi = ["verde", "blu", "viola", "arancio", "rosso", "grafite"]

    /// Il nome da dare a iOS: nil per l'icona normale (verde).
    static func nomePerIOS(_ scelta: String) -> String? { scelta == "verde" ? nil : "AppIcon-\(scelta)" }

    /// Dal nome dell'icona in uso (`UIApplication.alternateIconName`) al colore.
    static func scelta(da nomeIOS: String?) -> String {
        guard let n = nomeIOS, n.hasPrefix("AppIcon-") else { return "verde" }
        let colore = String(n.dropFirst("AppIcon-".count))
        return nomi.contains(colore) ? colore : "verde"
    }

    static func titolo(_ scelta: String) -> String { scelta.primaMaiuscola }
}

struct IconaAppView: View {
    @State private var corrente = IconeApp.scelta(da: UIApplication.shared.alternateIconName)
    @State private var messaggio: String?

    var body: some View {
        ZStack {
            Sfondo()
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    Carta("Icona dell'app") {
                        LazyVGrid(columns: [GridItem(.adaptive(minimum: 92), spacing: 14)], spacing: 16) {
                            ForEach(IconeApp.nomi, id: \.self) { n in
                                Button { Task { await scegli(n) } } label: {
                                    VStack(spacing: 6) {
                                        Image("Icona-\(n)").resizable().scaledToFit().frame(width: 72, height: 72)
                                            .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
                                            .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous).strokeBorder(corrente == n ? Color.verde : Color.primary.opacity(0.15), lineWidth: corrente == n ? 3 : 1))
                                        Text(IconeApp.titolo(n)).font(.footnote.weight(corrente == n ? .bold : .regular))
                                    }
                                    .frame(minHeight: 44)
                                }
                                .buttonStyle(StilePressione())
                                .animation(Tema.molla, value: corrente)
                                .accessibilityLabel("Icona \(IconeApp.titolo(n))")
                                .accessibilityAddTraits(corrente == n ? .isSelected : [])
                            }
                        }
                        if let messaggio { Text(messaggio).font(.footnote).foregroundStyle(.secondary) }
                        Text("L'icona sulla schermata Home cambia subito. Se SideStore rinnova l'app, la scelta resta.")
                            .font(.caption).foregroundStyle(.secondary)
                    }
                }
                .padding(16)
            }
        }
        .navigationTitle("Icona")
    }

    private func scegli(_ nome: String) async {
        if Demo.attivo {
            corrente = nome
            messaggio = "In modalità demo l'icona non cambia davvero."
            return
        }
        guard UIApplication.shared.supportsAlternateIcons else {
            messaggio = "Questo dispositivo non permette di cambiare l'icona."
            return
        }
        do {
            try await UIApplication.shared.setAlternateIconName(IconeApp.nomePerIOS(nome))
            corrente = nome
            messaggio = "Icona \(IconeApp.titolo(nome).lowercased()) scelta."
            Haptics.esito(riuscito: true)
        } catch {
            messaggio = error.localizedDescription
            Haptics.esito(riuscito: false)
        }
    }
}
