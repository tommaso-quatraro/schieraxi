import SwiftUI

/// Squadre della lega e loro rose.
struct SquadreView: View {
    @StateObject private var vm: SquadreViewModel
    private let server: any ServerClient

    init(server: any ServerClient) {
        self.server = server
        _vm = StateObject(wrappedValue: SquadreViewModel(server: server))
    }

    var body: some View {
        ZStack {
            Sfondo()
            List {
                if let errore = vm.errore {
                    Text(errore).font(.footnote).foregroundStyle(.orange)
                }
                if let s = vm.caricatore.dato {
                    ForEach(s) { sq in
                        NavigationLink { RosaView(nome: sq.nome, server: server) } label: {
                            HStack {
                                Text(sq.nome).font(.headline)
                                if sq.mia == true { Text("tua").font(.caption2.bold()).padding(.horizontal, 6).padding(.vertical, 2).background(Color.verde.opacity(0.3), in: Capsule()) }
                                Spacer()
                                Text("\(sq.giocatori ?? 0)").foregroundStyle(.secondary)
                            }
                            .accessibilityElement(children: .combine)
                        }
                        .swipeActions {
                            Button("È la mia") { Task { await vm.impostaMia(sq.nome) } }.tint(Color.verde)
                        }
                        .accessibilityAction(named: "È la mia squadra") { Task { await vm.impostaMia(sq.nome) } }
                    }
                } else if let e = vm.caricatore.errore {
                    ErroreVista(messaggio: e) { Task { await vm.carica() } }
                } else {
                    ProgressView().frame(maxWidth: .infinity)
                }
            }
            .scrollContentBackground(.hidden)
        }
        .navigationTitle("Squadre")
        .task { await vm.carica() }
    }
}

struct RosaView: View {
    let nome: String
    @StateObject private var caricatore: Caricatore<Rosa>

    init(nome: String, server: any ServerClient) {
        self.nome = nome
        _caricatore = StateObject(wrappedValue: Caricatore<Rosa>("/api/rosa?squadra=\(IndirizzoServer.codifica(nome))", server: server))
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
            Text((g.squadra ?? "").capitalized).font(.caption).foregroundStyle(.secondary)
            if let c = g.costo { Text("\(Formato.intero(c))").monospacedDigit().foregroundStyle(.secondary) }
        }
        .accessibilityElement(children: .combine)
    }
}

/// Asta: quanti crediti dedicare a ogni reparto e prezzi consigliati.
struct AstaView: View {
    @StateObject private var caricatore: Caricatore<PianoAsta>

    init(server: any ServerClient) {
        _caricatore = StateObject(wrappedValue: Caricatore<PianoAsta>("/api/asta", server: server))
    }

    var body: some View {
        ZStack {
            Sfondo()
            ScrollView {
                Colonne(spazio: 14) {
                    if let a = caricatore.dato {
                        Carta {
                            Text("Budget di \(Formato.intero(a.crediti)) crediti").font(.headline)
                            Text("Stime del modello: quanto dedicare a ogni reparto e i prezzi consigliati per i migliori.").font(.footnote).foregroundStyle(.secondary)
                        }
                        ForEach(a.ruoli) { r in
                            Carta("\(r.ruolo): \(Formato.intero(r.crediti)) crediti (\(Formato.percento(r.quota))%)") {
                                ForEach(r.giocatori.prefix(12)) { g in
                                    HStack {
                                        Text(g.nome)
                                        Text((g.squadra ?? "").capitalized).font(.caption).foregroundStyle(.secondary)
                                        Spacer()
                                        Text("\(Formato.intero(g.prezzo))").font(.headline).monospacedDigit()
                                    }
                                    .accessibilityElement(children: .combine)
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
            .refreshable { await caricatore.ricarica() }
            .avvisoDatiSalvati(caricatore.datiSalvati)
        }
        .navigationTitle("Asta")
        .task { await caricatore.ricarica() }
    }
}

struct NovitaView: View {
    @StateObject private var caricatore: Caricatore<[VoceNovita]>

    init(server: any ServerClient) {
        _caricatore = StateObject(wrappedValue: Caricatore<[VoceNovita]>("/api/novita", server: server))
    }

    var body: some View {
        ZStack {
            Sfondo()
            ScrollView {
                Colonne(spazio: 14) {
                    if let n = caricatore.dato {
                        ForEach(n) { v in
                            Carta("Versione \(v.versione) · \(v.titolo)") {
                                ForEach(v.voci, id: \.self) { voce in
                                    // il puntino sta a parte: le righe lunghe vanno a capo allineate al testo
                                    HStack(alignment: .firstTextBaseline, spacing: 6) {
                                        Text("•")
                                        Text(voce)
                                    }
                                    .font(.subheadline)
                                    .accessibilityElement(children: .combine)
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
            .refreshable { await caricatore.ricarica() }
        }
        .navigationTitle("Novità")
        .task { await caricatore.ricarica() }
    }
}

struct StatoDatiView: View {
    @StateObject private var caricatore: Caricatore<StatoDati>

    init(server: any ServerClient) {
        _caricatore = StateObject(wrappedValue: Caricatore<StatoDati>("/api/stato-dati", server: server))
    }

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
                                Text(a.cosa.primaMaiuscola)
                                Text(Quando.leggibile((a.quando ?? "").replacingOccurrences(of: "T", with: " "))).font(.caption).foregroundStyle(.secondary)
                                ForEach(a.errori ?? [], id: \.self) { Text($0).font(.caption).foregroundStyle(.orange) }
                            }
                            .accessibilityElement(children: .combine)
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
        RigaValore(titolo: t, valore: v, cifreFisse: true)
    }
}

/// Importazione delle rose da un file Excel di Leghe (scelto con il selettore di file di iOS).
struct ImportaExcelView: View {
    @StateObject private var vm: ImportaExcelViewModel
    @State private var scegli = false

    init(server: any ServerClient) {
        _vm = StateObject(wrappedValue: ImportaExcelViewModel(server: server))
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
                        if vm.inCorso { ProgressView() } else { Label("Scegli il file Excel", systemImage: "doc.badge.plus") }
                    }
                    .disabled(vm.inCorso)
                    .frame(minHeight: 44)
                }
                if let errore = vm.errore { Section { Text(errore).foregroundStyle(.orange) } }
                if let e = vm.esito {
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
        .fileImporter(isPresented: $scegli, allowedContentTypes: vm.tipiAmmessi, allowsMultipleSelection: false) { risultato in
            Task { await vm.importa(risultato) }
        }
    }
}
