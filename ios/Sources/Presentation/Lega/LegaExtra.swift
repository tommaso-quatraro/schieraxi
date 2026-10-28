import SwiftUI
import UniformTypeIdentifiers

/// Squadre della lega e loro rose.
struct SquadreView: View {
    @StateObject private var caricatore = Caricatore<[SquadraLega]>("/api/squadre")
    @State private var errore: String?

    var body: some View {
        ZStack {
            Sfondo()
            List {
                if let errore {
                    Text(errore).font(.footnote).foregroundStyle(.orange)
                }
                if let s = caricatore.dato {
                    ForEach(s) { sq in
                        NavigationLink { RosaView(nome: sq.nome) } label: {
                            HStack {
                                Text(sq.nome).font(.headline)
                                if sq.mia == true { Text("tua").font(.caption2.bold()).padding(.horizontal, 6).padding(.vertical, 2).background(Color.verde.opacity(0.3), in: Capsule()) }
                                Spacer()
                                Text("\(sq.giocatori ?? 0)").foregroundStyle(.secondary)
                            }
                        }
                        .swipeActions {
                            Button("È la mia") { Task { await imposta(sq.nome) } }.tint(Color.verde)
                        }
                    }
                } else if let e = caricatore.errore {
                    ErroreVista(messaggio: e) { Task { await caricatore.ricarica() } }
                } else {
                    ProgressView().frame(maxWidth: .infinity)
                }
            }
            .scrollContentBackground(.hidden)
        }
        .navigationTitle("Squadre")
        .task { await caricatore.ricarica() }
    }

    private func imposta(_ nome: String) async {
        do {
            _ = try await Api.corpoJSON("PUT", "/api/mia-squadra", NomeSquadra(nome: nome))
            UINotificationFeedbackGenerator().notificationOccurred(.success)
            errore = nil
        } catch {
            UINotificationFeedbackGenerator().notificationOccurred(.error)
            errore = error.localizedDescription
        }
        await caricatore.ricarica()
    }
}

struct RosaView: View {
    let nome: String
    @StateObject private var caricatore: Caricatore<Rosa>

    init(nome: String) {
        self.nome = nome
        _caricatore = StateObject(wrappedValue: Caricatore<Rosa>("/api/rosa?squadra=\(Api.codifica(nome))"))
    }

    var body: some View {
        ZStack {
            Sfondo()
            List {
                if let r = caricatore.dato {
                    ForEach(["P", "D", "C", "A"], id: \.self) { ruolo in
                        Section(ruolo) {
                            ForEach(r.giocatori.filter { $0.ruolo == ruolo }, id: \.ident) { g in rigaRosa(g) }
                        }
                    }
                    // Giocatori che il server non ha saputo collegare a un ruolo (non presenti nel listone).
                    let sconosciuti = r.giocatori.filter { !["P", "D", "C", "A"].contains($0.ruolo ?? "") }
                    if !sconosciuti.isEmpty {
                        Section("Non riconosciuti") {
                            ForEach(sconosciuti, id: \.ident) { g in rigaRosa(g) }
                        }
                    }
                } else if let e = caricatore.errore {
                    ErroreVista(messaggio: e) { Task { await caricatore.ricarica() } }
                } else {
                    ProgressView().frame(maxWidth: .infinity)
                }
            }
            .scrollContentBackground(.hidden)
        }
        .navigationTitle(nome)
        .navigationBarTitleDisplayMode(.inline)
        .task { await caricatore.ricarica() }
    }

    private func rigaRosa(_ g: GiocatoreRosa) -> some View {
        HStack(spacing: 10) {
            BadgeRuolo(ruolo: g.ruolo ?? "?")
            Text(g.nome)
            Spacer()
            Text(g.squadra ?? "").font(.caption).foregroundStyle(.secondary)
            if let c = g.costo { Text("\(Int(c))").monospacedDigit().foregroundStyle(.secondary) }
        }
        .accessibilityElement(children: .combine)
    }
}

/// Asta: quanti crediti dedicare a ogni reparto e prezzi consigliati.
struct AstaView: View {
    @StateObject private var caricatore = Caricatore<PianoAsta>("/api/asta")

    var body: some View {
        ZStack {
            Sfondo()
            ScrollView {
                VStack(spacing: 14) {
                    if let a = caricatore.dato {
                        Carta {
                            Text("Budget di \(Int(a.crediti ?? 0)) crediti").font(.headline)
                            Text("Stime del modello: quanto dedicare a ogni reparto e i prezzi consigliati per i migliori.").font(.footnote).foregroundStyle(.secondary)
                        }
                        ForEach(a.ruoli) { r in
                            Carta("\(r.ruolo): \(Int(r.crediti ?? 0)) crediti (\(Int(((r.quota ?? 0) * 100).rounded()))%)") {
                                ForEach(r.giocatori.prefix(12)) { g in
                                    HStack {
                                        Text(g.nome)
                                        Text(g.squadra ?? "").font(.caption).foregroundStyle(.secondary)
                                        Spacer()
                                        Text("\(Int(g.prezzo ?? 0))").font(.headline).monospacedDigit()
                                    }
                                }
                            }
                        }
                    } else if let e = caricatore.errore {
                        ErroreVista(messaggio: e) { Task { await caricatore.ricarica() } }
                    } else {
                        ProgressView().padding(40)
                    }
                }
                .padding(16)
            }
        }
        .navigationTitle("Asta")
        .task { await caricatore.ricarica() }
    }
}

struct NovitaView: View {
    @StateObject private var caricatore = Caricatore<[VoceNovita]>("/api/novita")

    var body: some View {
        ZStack {
            Sfondo()
            ScrollView {
                VStack(spacing: 14) {
                    if let n = caricatore.dato {
                        ForEach(n) { v in
                            Carta("Versione \(v.versione) · \(v.titolo)") {
                                ForEach(v.voci, id: \.self) { Text("• " + $0).font(.subheadline) }
                            }
                        }
                    } else if let e = caricatore.errore {
                        ErroreVista(messaggio: e) { Task { await caricatore.ricarica() } }
                    } else {
                        ProgressView().padding(40)
                    }
                }
                .padding(16)
            }
        }
        .navigationTitle("Novità")
        .task { await caricatore.ricarica() }
    }
}

struct StatoDatiView: View {
    @StateObject private var caricatore = Caricatore<StatoDati>("/api/stato-dati")

    var body: some View {
        ZStack {
            Sfondo()
            List {
                if let s = caricatore.dato {
                    Section("Dati") {
                        riga("Stagione", s.stagione ?? "—")
                        riga("Calciatori", "\(s.calciatori ?? 0)")
                        riga("Partite giocate", "\(s.partite?.giocate ?? 0) / \(s.partite?.totali ?? 0)")
                        riga("Voti", "\(s.voti ?? 0)")
                        riga("Coppe europee fino al", s.coppeFino ?? "—")
                    }
                    Section("Ultimi aggiornamenti") {
                        ForEach(s.aggiornamenti ?? []) { a in
                            VStack(alignment: .leading, spacing: 2) {
                                Text(a.cosa.capitalized)
                                Text(Quando.leggibile((a.quando ?? "").replacingOccurrences(of: "T", with: " "))).font(.caption).foregroundStyle(.secondary)
                                ForEach(a.errori ?? [], id: \.self) { Text($0).font(.caption).foregroundStyle(.orange) }
                            }
                        }
                    }
                } else if let e = caricatore.errore {
                    ErroreVista(messaggio: e) { Task { await caricatore.ricarica() } }
                } else {
                    ProgressView().frame(maxWidth: .infinity)
                }
            }
            .scrollContentBackground(.hidden)
        }
        .navigationTitle("Stato dei dati")
        .refreshable { await caricatore.ricarica() }
        .task { await caricatore.ricarica() }
    }

    private func riga(_ t: String, _ v: String) -> some View {
        HStack { Text(t); Spacer(); Text(v).foregroundStyle(.secondary).monospacedDigit() }
    }
}

/// Importazione delle rose da un file Excel di Leghe (scelto con il selettore di file di iOS).
struct ImportaExcelView: View {
    /// Dimensione massima accettata: un Excel delle rose è di poche decine di KB.
    private static let massimoByte = 5 * 1024 * 1024

    @State private var scegli = false
    @State private var inCorso = false
    @State private var esito: EsitoImportazione?
    @State private var errore: String?

    /// Solo fogli di calcolo (.xlsx e simili).
    private var tipiAmmessi: [UTType] {
        var tipi: [UTType] = [.spreadsheet]
        if let xlsx = UTType(filenameExtension: "xlsx") { tipi.append(xlsx) }
        return tipi
    }

    var body: some View {
        ZStack {
            Sfondo()
            List {
                Section {
                    Text("Esporta le rose in Excel da Leghe (come fai di solito), poi scegli qui il file: l'app ti dice cosa è cambiato (scambi, svincolati presi, crediti).")
                        .font(.footnote).foregroundStyle(.secondary)
                    Button {
                        scegli = true
                    } label: {
                        if inCorso { ProgressView() } else { Label("Scegli il file Excel", systemImage: "doc.badge.plus") }
                    }
                    .disabled(inCorso)
                    .frame(minHeight: 44)
                }
                if let errore { Section { Text(errore).foregroundStyle(.orange) } }
                if let e = esito {
                    Section("Esito") {
                        if let r = e.riepilogo, !r.isEmpty { Text(r) }
                        Text("Squadre importate: \(e.totaleSquadre ?? e.squadreImportate?.count ?? 0)")
                        ForEach(e.avvisi ?? [], id: \.self) { Text($0).font(.footnote).foregroundStyle(.orange) }
                    }
                }
            }
            .scrollContentBackground(.hidden)
        }
        .navigationTitle("Aggiorna le rose")
        .fileImporter(isPresented: $scegli, allowedContentTypes: tipiAmmessi, allowsMultipleSelection: false) { risultato in
            Task { await importa(risultato) }
        }
    }

    private func importa(_ risultato: Result<[URL], Error>) async {
        guard case .success(let urls) = risultato, let url = urls.first else {
            if case .failure(let e) = risultato { errore = e.localizedDescription }
            return
        }
        inCorso = true
        defer { inCorso = false }
        let accesso = url.startAccessingSecurityScopedResource()
        defer { if accesso { url.stopAccessingSecurityScopedResource() } }
        let estensione = url.pathExtension.lowercased()
        guard ["xlsx", "xls", "xlsm"].contains(estensione) else {
            esito = nil
            errore = "Il file deve essere un Excel (.xlsx)."
            return
        }
        let grandezza = (try? url.resourceValues(forKeys: [.fileSizeKey]).fileSize) ?? 0
        guard grandezza <= Self.massimoByte else {
            esito = nil
            errore = "Il file è troppo grande (massimo 5 MB): non sembra un Excel delle rose."
            return
        }
        do {
            let dati = try Data(contentsOf: url)
            esito = try await Api.caricaFile("/api/rose/file", nome: url.lastPathComponent, dati: dati)
            errore = nil
            UINotificationFeedbackGenerator().notificationOccurred(.success)
        } catch {
            esito = nil
            errore = error.localizedDescription
            UINotificationFeedbackGenerator().notificationOccurred(.error)
        }
    }
}
