import SwiftUI

/// «Sotto il cofano» (Impostazioni > Informazioni): come ragiona SchieraXI, con i testi che manda il server (uguali su web, iPhone e Android).
/// Sezioni ripiegabili con il filtro Base / Nerd / Tutto (ricordato), formule in carattere a spaziatura fissa che scorrono di lato,
/// esempi con l'etichetta «Numeri veri» o «Esempio di calcolo», numeri con la data della misura, glossario cercabile.
/// Su iPad (pagina larga) c'è l'indice a sinistra. Senza rete resta l'ultima copia salvata.
struct SottoIlCofanoView: View {
    @StateObject private var caricatore: Caricatore<SottoIlCofano>
    /// Cosa fare per un rimando a un'altra schermata (lo decide chi ha in mano la navigazione).
    let vai: (DestinazioneCofano) -> Void

    @AppStorage("cofanoLivello") private var livelloRicordato = "base"
    @State private var apertura: [String: Bool] = [:]
    @State private var ricerca = ""
    @State private var larga = false

    init(server: any ServerClient, vai: @escaping (DestinazioneCofano) -> Void) {
        // Senza conversione dei nomi: le chiavi dei numeri («app.errore_modello») sono dati, non campi.
        _caricatore = StateObject(wrappedValue: Caricatore<SottoIlCofano>("/api/sotto-il-cofano", snake: false, server: server))
        self.vai = vai
    }

    private var livello: Binding<LivelloCofano> {
        Binding(get: { LivelloCofano(ricordato: livelloRicordato) }, set: { livelloRicordato = $0.rawValue })
    }

    var body: some View {
        ZStack {
            Sfondo()
            if let c = caricatore.dato {
                contenuto(c)
            } else if let e = caricatore.errore {
                ScrollView { ErroreVista(messaggio: e) { Task { await caricatore.ricarica() } }.padding(Tema.margine) }
            } else {
                ScrollView { Scheletro(schede: 3, righe: 3, testo: "Preparo la pagina…").padding(Tema.margine) }
            }
        }
        .navigationTitle("Sotto il cofano")
        .navigationBarTitleDisplayMode(.inline)
        .onGeometryChange(for: Bool.self) { $0.size.width >= 700 } action: { larga = $0 }
        .task { await caricatore.ricarica() }
    }

    // MARK: impaginazione

    private func contenuto(_ c: SottoIlCofano) -> some View {
        ScrollViewReader { proxy in
            HStack(alignment: .top, spacing: 0) {
                if larga {
                    indice(c, proxy: proxy).frame(width: 250)
                    Divider()
                }
                ScrollView {
                    VStack(alignment: .leading, spacing: Tema.spazioSchede) {
                        testata(c)
                        let visibili = c.sezioniVisibili(LivelloCofano(ricordato: livelloRicordato))
                        if visibili.isEmpty {
                            Carta { Text("Nessuna sezione in questo livello. Prova «Tutto».").font(.subheadline).foregroundStyle(.secondary) }
                        }
                        ForEach(visibili) { sezione in
                            scheda(sezione, in: c).id(sezione.id)
                        }
                        glossario(c).id("glossario")
                    }
                    .padding(.horizontal, Tema.margine)
                    .padding(.bottom, 24)
                    .frame(maxWidth: 820, alignment: .leading)
                    .frame(maxWidth: .infinity)
                }
                .refreshable { await caricatore.ricarica() }
                .avvisoDatiSalvati(caricatore.datiSalvati)
                .bordiMorbidi()
            }
            .toolbar {
                if !larga {
                    ToolbarItem(placement: .navigationBarTrailing) {
                        Menu {
                            ForEach(c.sezioniVisibili(LivelloCofano(ricordato: livelloRicordato))) { s in
                                Button(s.titolo) { vaiA(s.id, proxy: proxy) }
                            }
                            Button("Glossario") { vaiA("glossario", proxy: proxy) }
                        } label: {
                            Label("Indice", systemImage: "list.bullet")
                        }
                        .accessibilityHint("Salta a una sezione")
                    }
                }
            }
        }
    }

    private func vaiA(_ id: String, proxy: ScrollViewProxy) {
        if id != "glossario" { apertura[id] = true }
        withAnimation(Tema.morbida) { proxy.scrollTo(id, anchor: .top) }
    }

    /// L'indice a sinistra (pagina larga): un tocco porta alla sezione e la apre.
    private func indice(_ c: SottoIlCofano, proxy: ScrollViewProxy) -> some View {
        List {
            Section("In questa pagina") {
                ForEach(c.sezioniVisibili(LivelloCofano(ricordato: livelloRicordato))) { s in
                    Button { vaiA(s.id, proxy: proxy) } label: {
                        Text(s.titolo).font(.subheadline).frame(maxWidth: .infinity, minHeight: Tema.areaTocco, alignment: .leading)
                    }
                    .buttonStyle(.plain)
                }
                Button { vaiA("glossario", proxy: proxy) } label: {
                    Text("Glossario").font(.subheadline.weight(.semibold)).frame(maxWidth: .infinity, minHeight: Tema.areaTocco, alignment: .leading)
                }
                .buttonStyle(.plain)
            }
        }
        .listStyle(.sidebar)
        .scrollContentBackground(.hidden)
    }

    // MARK: pezzi

    private func testata(_ c: SottoIlCofano) -> some View {
        Carta {
            if let s = c.sottotitolo, !s.isEmpty { Text(s).font(.subheadline) }
            ForEach(Array(c.introduzione.enumerated()), id: \.offset) { _, p in
                Text(p).font(.subheadline).foregroundStyle(.secondary)
            }
            if let d = c.rigaDate { Text(d).font(.caption).foregroundStyle(.secondary) }
            if c.piuNuovaDellApp {
                Label("Questa pagina ha una forma più nuova della tua app: aggiorna l'app per vederla tutta.", systemImage: "arrow.down.app")
                    .font(.footnote).foregroundStyle(Color.attenzione)
            }
            Picker("Quanto dettaglio", selection: livello) {
                ForEach(LivelloCofano.allCases) { Text($0.titolo).tag($0) }
            }
            .pickerStyle(.segmented)
            .frame(minHeight: Tema.areaTocco)
            Text(descrizione(LivelloCofano(ricordato: livelloRicordato), c)).font(.caption).foregroundStyle(.secondary)
        }
    }

    private func descrizione(_ l: LivelloCofano, _ c: SottoIlCofano) -> String {
        let testoServer: String?
        switch l {
        case .base: testoServer = c.livelli?["base"]
        case .nerd: testoServer = c.livelli?["nerd"]
        case .tutto: testoServer = nil
        }
        if let t = testoServer, !t.isEmpty { return t }
        switch l {
        case .base: return "Le spiegazioni semplici."
        case .nerd: return "Solo i dettagli tecnici, per chi vuole i conti."
        case .tutto: return "Le spiegazioni semplici e i dettagli tecnici."
        }
    }

    private func aperta(_ s: SezioneCofano) -> Binding<Bool> {
        Binding(get: { apertura[s.id] ?? !s.eNerd }, set: { apertura[s.id] = $0 })
    }

    private func scheda(_ s: SezioneCofano, in c: SottoIlCofano) -> some View {
        Carta {
            DisclosureGroup(isExpanded: aperta(s)) {
                VStack(alignment: .leading, spacing: 10) {
                    ForEach(Array(s.paragrafi.enumerated()), id: \.offset) { _, p in
                        Text(p).font(.subheadline).fixedSize(horizontal: false, vertical: true)
                    }
                    if let f = s.formula, !f.isEmpty { formula(f) }
                    if let e = s.esempio { esempio(e) }
                    numeri(c.numeri(di: s))
                    rimandi(s.rimandi)
                }
                .padding(.top, 8)
            } label: {
                HStack(spacing: 8) {
                    Text(s.titolo).font(.headline).multilineTextAlignment(.leading)
                    if s.eNerd { Capsula(testo: "Nerd", colore: Color.informazione, simbolo: "function") }
                }
                .frame(minHeight: Tema.areaTocco, alignment: .leading)
                .accessibilityAddTraits(.isHeader)
            }
            .tint(Color.verde)
        }
    }

    /// Carattere a spaziatura fissa, scorre di lato, si può selezionare e VoiceOver la legge come testo.
    private func formula(_ f: String) -> some View {
        ScrollView(.horizontal) {
            Text(f)
                .font(.system(.footnote, design: .monospaced))
                .textSelection(.enabled)
                .fixedSize(horizontal: true, vertical: true)
                .padding(10)
        }
        .background(Color.sfondoIncavo, in: RoundedRectangle(cornerRadius: Tema.raggioPiccolo, style: .continuous))
        .accessibilityLabel("Formula")
        .accessibilityValue(f)
    }

    private func esempio(_ e: EsempioCofano) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Capsula(testo: e.etichetta, colore: e.origine == "vero" ? Color.verde : Color.informazione,
                    simbolo: e.origine == "vero" ? "checkmark.seal" : "pencil.and.list.clipboard")
            if let t = e.titolo, !t.isEmpty { Text(t).font(.subheadline.weight(.semibold)) }
            if let t = e.testo, !t.isEmpty { Text(t).font(.subheadline).fixedSize(horizontal: false, vertical: true) }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(12)
        .background(Color.sfondoIncavo, in: RoundedRectangle(cornerRadius: Tema.raggioPiccolo, style: .continuous))
        .accessibilityElement(children: .combine)
    }

    @ViewBuilder
    private func numeri(_ lista: [NumeroCofano]) -> some View {
        if !lista.isEmpty {
            VStack(alignment: .leading, spacing: 6) {
                ForEach(lista) { n in
                    VStack(alignment: .leading, spacing: 1) {
                        HStack(alignment: .firstTextBaseline) {
                            Text(n.etichetta).font(.subheadline)
                            Spacer(minLength: 8)
                            Text(n.valore).font(.subheadline.weight(.semibold)).monospacedDigit()
                        }
                        Text(n.nota).font(.caption).foregroundStyle(.secondary)
                    }
                    .accessibilityElement(children: .ignore)
                    .accessibilityLabel("\(n.etichetta): \(n.valore), \(n.nota)")
                }
            }
        }
    }

    @ViewBuilder
    private func rimandi(_ lista: [RimandoCofano]) -> some View {
        if !lista.isEmpty {
            VStack(alignment: .leading, spacing: 4) {
                ForEach(lista) { r in
                    if let destinazione = DestinazioneCofano.da(r.schermata) {
                        Button { vai(destinazione) } label: {
                            Label(r.testo, systemImage: "arrow.up.forward.app")
                                .frame(minHeight: Tema.areaTocco, alignment: .leading)
                        }
                        .accessibilityHint("Apre la schermata")
                    } else if !r.testo.isEmpty {
                        // Schermata che questa versione dell'app non conosce: solo testo, senza collegamento.
                        Text("Vedi anche: \(r.testo)").font(.footnote).foregroundStyle(.secondary)
                    }
                }
            }
        }
    }

    private func glossario(_ c: SottoIlCofano) -> some View {
        let termini = c.glossario(cercando: ricerca)
        return Carta("Glossario", simbolo: "text.book.closed") {
            if !c.glossario.isEmpty {
                HStack(spacing: 8) {
                    Image(systemName: "magnifyingglass").foregroundStyle(.secondary).accessibilityHidden(true)
                    TextField("Cerca un termine", text: $ricerca)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .submitLabel(.search)
                    if !ricerca.isEmpty {
                        Button { ricerca = "" } label: { Image(systemName: "xmark.circle.fill").foregroundStyle(.secondary) }
                            .accessibilityLabel("Cancella la ricerca")
                            .frame(minWidth: Tema.areaTocco, minHeight: Tema.areaTocco)
                    }
                }
                .padding(.horizontal, 12)
                .frame(minHeight: Tema.areaTocco)
                .background(Color.sfondoIncavo, in: RoundedRectangle(cornerRadius: Tema.raggioPiccolo, style: .continuous))
            }
            if termini.isEmpty {
                Text(ricerca.isEmpty ? "Nessun termine." : "Nessun termine trovato per «\(ricerca)».")
                    .font(.subheadline).foregroundStyle(.secondary)
            }
            ForEach(termini) { t in
                VStack(alignment: .leading, spacing: 2) {
                    Text(t.termine).font(.subheadline.weight(.semibold))
                    if !t.spiegazione.isEmpty { Text(t.spiegazione).font(.subheadline).foregroundStyle(.secondary) }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .accessibilityElement(children: .combine)
            }
        }
    }
}

#Preview("Sotto il cofano") {
    NavigationStack {
        SottoIlCofanoView(server: FinteServer.esempio, vai: { _ in })
    }
}
