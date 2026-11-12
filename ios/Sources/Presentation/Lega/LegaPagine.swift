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
            Text(m).font(.footnote).foregroundStyle(vm.errori.isEmpty ? Color.testoSecondario : Color.attenzione)
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
                voce("checkmark.circle", Color.verde, Catalogo.Scambio.nessunaDifferenzaRispetto)
            } else {
                ForEach(differenze.scambi ?? []) { s in
                    let squadre = s.squadre.count == 2 ? "\(s.squadre[0]) → \(s.squadre[1])" : s.squadre.joined(separator: ", ")
                    let contro = s.daB.isEmpty ? "" : " contro " + nomi(s.daB)
                    voce("arrow.left.arrow.right", Color.verde, "\(s.daB.isEmpty ? Catalogo.Scambio.passaggioB : Catalogo.Scambio.scambioB) \(squadre): \(nomi(s.daA))\(contro)")
                }
                ForEach(differenze.svincolatiPresi ?? []) { g in
                    voce("plus.circle.fill", Color.verde, Catalogo.Scambio.prendeSvincolati(nomi: nomi(g.giocatori), squadra: g.squadra))
                }
                ForEach(differenze.tagliati ?? []) { g in
                    voce("minus.circle.fill", .attenzione, Catalogo.Scambio.lasciaLiberi(nomi: nomi(g.giocatori), squadra: g.squadra))
                }
                ForEach(differenze.crediti ?? []) { c in
                    voce(ParoleWidget.simboloCrediti, .testoSecondario,
                         "Crediti \(c.squadra): \(c.prima.map { String(Formato.intero($0)) } ?? "–") → \(c.dopo.map { String(Formato.intero($0)) } ?? "–")")
                }
                if vuoto, let t = differenze.testo { Text(t).font(.subheadline) }
            }
        }
    }
}

// MARK: - Passaggio di stagione

/// Le frasi del passaggio di stagione, come la web (`lega.rose_ancora_quelle` del catalogo): i giocatori seguiti si chiamano «seguiti».
extension StagioneView {
    static func testoRoseAncoraQuelle(_ stagione: String) -> String { Catalogo.Lega.roseAncoraQuelle(s: stagione) }

    static let testoArchivioConferma = "Rose, regole, scelte e seguiti restano salvati nell'archivio del server."
}

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
                TitoloNellaPagina()
                if let s = vm.stato.dato {
                    if vm.archiviata {
                        Section {
                            Label(Catalogo.Lega.stagioneArchiviata(s: s.rose ?? ""), systemImage: "checkmark.seal.fill").font(.headline).foregroundStyle(Color.verde)
                            Text(Catalogo.Lega.tuttoSalvatoNell).font(.footnote).foregroundStyle(Color.testoSecondario)
                        }
                        passi
                    } else if s.nuova == true {
                        Section {
                            Text(Catalogo.Lega.nuovaStagioneN(s: s.corrente ?? "")).font(.headline)
                            Text(Self.testoRoseAncoraQuelle(s.rose ?? ""))
                                .font(.footnote).foregroundStyle(Color.testoSecondario)
                            Button(role: .destructive) { conferma = true } label: {
                                if vm.inCorso { ProgressView().frame(maxWidth: .infinity, minHeight: 44) }
                                else { Label(Catalogo.Lega.archiviaRiparti, systemImage: "archivebox").labelStyle(.distruttiva).frame(maxWidth: .infinity, minHeight: 44) }
                            }
                            .disabled(vm.inCorso)
                            if let e = vm.errore { Text(e).font(.footnote).foregroundStyle(Color.attenzione) }
                        }
                    } else {
                        Section {
                            Label("Le rose sono della stagione in corso (\(s.corrente ?? "")): non c'è niente da fare.", systemImage: "checkmark.circle")
                                .font(.subheadline)
                            Text("Quando la stagione finisce e inizia la successiva, qui compare il passaggio guidato.").font(.footnote).foregroundStyle(Color.testoSecondario)
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
        .titoloPagina(Catalogo.Lega.voceStagione)
        .ricercaGlobale()
        .task { await vm.carica() }
        // Conferma esplicita: archiviare cambia le rose, le regole e le scelte salvate.
        .confirmationDialog(Catalogo.Lega.confermaArchivio(s: vm.stato.dato?.rose ?? ""), isPresented: $conferma, titleVisibility: .visible) {
            Button(Catalogo.Lega.archiviaRiparti, role: .destructive) { Task { await vm.archiviaERiparti() } }
            Button("Annulla", role: .cancel) {}
        } message: {
            Text(Self.testoArchivioConferma)
        }
    }

    private var passi: some View {
        Section(titolo: "Passi per la nuova stagione") {
            ForEach(PassiNuovaStagione.elenco(amministratore: sessione.puoAmministrare)) { passo in
                NavigationLink(value: passo.pagina) { riga(passo) }
            }
        }
    }

    private func riga(_ passo: PassoStagione) -> some View {
        HStack(alignment: .top, spacing: 12) {
            Text(passo.numero, format: .number).font(.headline).frame(width: latoNumero, height: latoNumero).background(Color.verde.opacity(0.25), in: Circle()).accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 2) {
                Text(passo.titolo).font(.subheadline.bold())
                Text(passo.dettaglio).font(.caption).foregroundStyle(Color.testoSecondario)
            }
        }
        .frame(minHeight: 44)
        .accessibilityElement(children: .combine)
    }
}

/// Un passo di «Passi per la nuova stagione»: numero, cosa fare, dove farlo.
struct PassoStagione: Identifiable, Equatable {
    let numero: Int
    let titolo: String
    let dettaglio: String
    let pagina: PaginaLega
    var id: PaginaLega { pagina }
}

/// I passi dopo l'archivio della stagione, gli stessi della web (`nuovaStagione` di `app.js`), senza l'asta: la pagina
/// «Asta e riparazione» sull'iPhone non c'è più. Logica pura, provata nei test.
enum PassiNuovaStagione {
    static func elenco(amministratore: Bool) -> [PassoStagione] {
        var passi: [(titolo: String, dettaglio: String, pagina: PaginaLega)] = [
            (Catalogo.Lega.importaNuoveRose, "Con l'Excel di Leghe, da «Aggiorna le rose».", .importa),
            (Catalogo.Lega.controllaRegole, "Bonus, moduli e crediti possono cambiare da un anno all'altro.", .regole),
        ]
        // Aggiornare i dati spetta a chi amministra il server (come sulla web): agli altri il server risponderebbe «Solo per l'amministratore».
        if amministratore {
            passi.append(("Aggiorna i dati", "Calendario, listone e quotazioni nuovi.", .stato))
        }
        return passi.enumerated().map { PassoStagione(numero: $0.offset + 1, titolo: $0.element.titolo, dettaglio: $0.element.dettaglio, pagina: $0.element.pagina) }
    }
}

// MARK: - Aspetto

/// Impostazioni > Aspetto: il tema (automatico, chiaro, scuro) e le animazioni. Le scelte stanno sul telefono (`@AppStorage`).
/// Le parole del tema sono quelle della web (`asp.*` del catalogo comune); lingua e dimensione del testo sono solo della web.
struct AspettoView: View {
    @AppStorage("tema") private var tema = "auto"
    @AppStorage("animazioniRidotte") private var animazioniRidotte = false

    /// Sotto il Tema: la frase della web e dove si cambia la dimensione del testo. «Impostazioni», non «Impostazioni di iPhone»:
    /// la stessa frase vale sull'iPad (#563).
    static let spiegaTema = Catalogo.Asp.autoSpiega
        + " La dimensione del testo si cambia in Impostazioni > Schermo e luminosità > Dimensione del testo: l'app la segue."

    var body: some View {
        ZStack {
            Sfondo()
            List {
                TitoloNellaPagina()
                Section {
                    Picker(Catalogo.Asp.tema, selection: $tema) {
                        Text(Catalogo.Asp.temaAuto).tag("auto")
                        Text(Catalogo.Asp.temaChiaro).tag("chiaro")
                        Text(Catalogo.Asp.temaScuro).tag("scuro")
                    }
                    .pickerStyle(.segmented)
                    .sensoryFeedback(.selection, trigger: tema)
                } header: {
                    Text(Catalogo.Asp.tema).foregroundStyle(Color.testoSecondario)
                } footer: {
                    Text(Self.spiegaTema).foregroundStyle(Color.testoSecondario)
                }
                Section {
                    Toggle("Animazioni ridotte", isOn: $animazioniRidotte).tint(Color.verde).frame(minHeight: 44)
                } header: { Text("Movimento").foregroundStyle(Color.testoSecondario) } footer: { Text("Toglie le animazioni dell'app (oltre a quelle che iOS già riduce se attivi «Riduci movimento»).").foregroundStyle(Color.testoSecondario) }
            }
            .scrollContentBackground(.hidden)
        }
        .titoloPagina(Catalogo.Imp.aspetto)
    }
}

#Preview("Aspetto") {
    NavigationStack { AspettoView() }
}
