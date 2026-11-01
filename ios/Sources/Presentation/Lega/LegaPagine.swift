import SwiftUI

/// Il tasto «Aggiorna i dati» con il suo stato: da mettere dentro una `Section` di una `List`.
struct AggiornaDatiSezione: View {
    @ObservedObject var vm: AggiornaDatiViewModel
    @Environment(\.accessibilityReduceMotion) private var ridotto

    var body: some View {
        Button { Task { await vm.avvia() } } label: {
            Label(vm.inCorso ? "Aggiornamento in corso…" : "Aggiorna i dati", systemImage: "arrow.triangle.2.circlepath")
                .symbolEffect(.variableColor.iterative, isActive: vm.inCorso && !ridotto)
                .frame(minHeight: 44)
        }
        .disabled(vm.inCorso)
        .sensoryFeedback(trigger: vm.inCorso) { vecchio, nuovo in vecchio && !nuovo ? .success : nil }
        .accessibilityHint("Il server riscarica calendario, voti, probabili formazioni e quotazioni")
        if let m = vm.messaggio {
            Text(m).font(.footnote).foregroundStyle(vm.errori.isEmpty ? Color.secondary : Color.attenzione)
        }
    }
}

// MARK: - Cosa è cambiato nelle rose

/// Scambi, svincolati presi, giocatori lasciati liberi e crediti cambiati tra due importazioni delle rose.
struct DifferenzeView: View {
    @ScaledMetric(relativeTo: .subheadline) private var latoIcona: CGFloat = 22
    let differenze: Differenze

    private func nomi(_ giocatori: [GiocatoreMovimento]) -> String { giocatori.map(\.nome).joined(separator: ", ") }

    private func voce(_ icona: String, _ colore: Color, _ testo: String) -> some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: icona).foregroundStyle(colore).frame(width: latoIcona).accessibilityHidden(true)
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
                    voce("c.circle", .secondary,
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
    @EnvironmentObject private var sessione: SessioneAccount
    @ScaledMetric(relativeTo: .headline) private var latoNumero: CGFloat = 28
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
                            Text("Tutto è salvato nell'archivio del server. Ora prepara la nuova stagione:").font(.footnote).foregroundStyle(.secondary)
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
                            if let e = vm.errore { Text(e).font(.footnote).foregroundStyle(Color.attenzione) }
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
            // Aggiornare i dati spetta a chi amministra il server (come sulla web): agli altri il server risponderebbe «Solo per l'amministratore».
            if sessione.puoAmministrare {
                NavigationLink(value: PaginaLega.stato) {
                    passo("4", "Aggiorna i dati", "Calendario, listone e quotazioni nuovi.")
                }
            }
            passo(sessione.puoAmministrare ? "5" : "4", "Prima dell'asta guarda Altro > Asta e riparazione", "Budget e prezzi consigliati.")
        }
    }

    private func passo(_ numero: String, _ titolo: String, _ dettaglio: String) -> some View {
        HStack(alignment: .top, spacing: 12) {
            Text(numero).font(.headline).frame(width: latoNumero, height: latoNumero).background(Color.verde.opacity(0.25), in: Circle()).accessibilityHidden(true)
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

/// Impostazioni > Aspetto: il tema (automatico, chiaro, scuro) e le animazioni. Le scelte stanno sul telefono (`@AppStorage`).
struct AspettoView: View {
    @AppStorage("tema") private var tema = "auto"
    @AppStorage("animazioniRidotte") private var animazioniRidotte = false

    var body: some View {
        ZStack {
            Sfondo()
            List {
                Section {
                    Picker("Tema", selection: $tema) {
                        Text("Automatico").tag("auto")
                        Text("Chiaro").tag("chiaro")
                        Text("Scuro").tag("scuro")
                    }
                    .pickerStyle(.segmented)
                    .sensoryFeedback(.selection, trigger: tema)
                } header: {
                    Text("Tema")
                } footer: {
                    Text("Automatico segue il chiaro e lo scuro di iPhone. La dimensione del testo si cambia in Impostazioni di iPhone > Schermo e luminosità > Dimensione del testo: l'app la segue.")
                }
                Section {
                    Toggle("Animazioni ridotte", isOn: $animazioniRidotte).tint(Color.verde).frame(minHeight: 44)
                } header: { Text("Movimento") } footer: { Text("Toglie le animazioni dell'app (oltre a quelle che iOS già riduce se attivi «Riduci movimento»).") }
            }
            .scrollContentBackground(.hidden)
        }
        .navigationTitle("Aspetto")
    }
}

#Preview("Aspetto") {
    NavigationStack { AspettoView() }
}
