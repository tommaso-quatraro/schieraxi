import SwiftUI
import PhotosUI

/// Squadre della lega e loro rose; da qui si indica quale è la propria.
struct SquadreView: View {
    @StateObject private var vm: SquadreViewModel
    private let server: any ServerClient
    @Environment(\.funzioni) private var funzioni

    init(server: any ServerClient) {
        self.server = server
        _vm = StateObject(wrappedValue: SquadreViewModel(server: server))
    }

    var body: some View {
        ZStack {
            Sfondo()
            List {
                if let errore = vm.errore {
                    Text(errore).font(.footnote).foregroundStyle(Color.attenzione)
                }
                if let s = vm.caricatore.dato {
                    Section("La tua squadra") {
                        Picker("Squadra", selection: Binding(get: { vm.mia }, set: { nuova in Task { await vm.impostaMia(nuova) } })) {
                            ForEach(s) { Text($0.nome).tag($0.nome) }
                        }
                        .frame(minHeight: 44)
                    }
                    Section(funzioni.acceso(Funzione.squadreAltrui) ? "Le squadre" : "La mia squadra e rosa") {
                        ForEach(s.filter { funzioni.acceso(Funzione.squadreAltrui) || $0.mia == true }) { sq in
                            NavigationLink(value: PaginaLega.rosa(sq.nome)) {
                                HStack(spacing: 12) {
                                    StemmaSquadra(nome: sq.nome, dimensione: 44)
                                    VStack(alignment: .leading, spacing: 2) {
                                        HStack {
                                            Text(sq.nome).font(.headline)
                                            if sq.mia == true { Text("tua").font(.caption2.bold()).padding(.horizontal, 6).padding(.vertical, 2).background(Color.verde.opacity(0.3), in: Capsule()) }
                                        }
                                        Text(Formato.giocatori(sq.giocatori ?? 0) + (sq.creditiResidui.map { " · \(Formato.crediti(Formato.intero($0)))" } ?? ""))
                                            .font(.caption).foregroundStyle(.secondary)
                                    }
                                }
                                .frame(minHeight: 44)
                                .accessibilityElement(children: .combine)
                            }
                            .swipeActions {
                                Button("È la mia") { Task { await vm.impostaMia(sq.nome) } }.tint(Color.verde)
                            }
                            .accessibilityAction(named: "È la mia squadra") { Task { await vm.impostaMia(sq.nome) } }
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
        .navigationTitle("Squadre")
        .ricercaGlobale()
        .task { await vm.carica() }
    }
}

/// Logica della rosa di una squadra: i giocatori e il caricamento di stemma e maglia.
@MainActor
final class RosaViewModel: ViewModelBase {
    let nome: String
    let caricatore: Caricatore<Rosa>
    @Published var messaggio: String?
    @Published var inCorso = false

    init(nome: String, server: any ServerClient) {
        self.nome = nome
        caricatore = Caricatore<Rosa>("/api/rosa?squadra=\(IndirizzoServer.codifica(nome))", server: server)
        super.init()
        osserva(caricatore)
    }

    func carica() async { await caricatore.ricarica() }

    /// Lo stemma o la maglia da un indirizzo web: lo scarica il server.
    func inviaDaIndirizzo(_ indirizzo: String, tipo: String) async {
        inCorso = true
        defer { inCorso = false }
        do {
            try await Immagini.condivise.inviaDaIndirizzo(indirizzo, squadra: nome, tipo: tipo)
            messaggio = tipo == "stemma" ? "Stemma aggiornato." : "Maglia aggiornata."
            Haptics.esito(riuscito: true)
        } catch {
            messaggio = error.localizedDescription
            Haptics.esito(riuscito: false)
        }
    }

    /// Manda al server lo stemma («stemma») o la maglia («maglia») scelti dalla libreria foto.
    func inviaImmagine(_ dati: Data, tipo: String) async {
        inCorso = true
        defer { inCorso = false }
        do {
            try await Immagini.condivise.invia(dati, squadra: nome, tipo: tipo)
            messaggio = tipo == "stemma" ? "Stemma aggiornato." : "Maglia aggiornata."
            Haptics.esito(riuscito: true)
        } catch {
            messaggio = error.localizedDescription
            Haptics.esito(riuscito: false)
        }
    }
}

/// Una riga della rosa: avatar con l'indice, nome, costo e quotazione, titolarità e previsione.
struct RigaRosa: View {
    let g: GiocatoreRosa
    @Environment(\.apriGiocatore) private var apri

    private var sottotitolo: String {
        var parti: [String] = []
        let s = ColoriSquadra.sigla(g.squadraSlug ?? g.previsione?.squadra ?? g.squadra)
        if !s.isEmpty { parti.append(s) }
        if let c = g.costo { parti.append("costo \(Formato.intero(c))") }
        if let q = g.quotazione { parti.append("quotazione \(Formato.intero(q))") }
        if let a = g.previsione?.avversario { parti.append("vs \(ColoriSquadra.sigla(a))") }
        return parti.joined(separator: " · ")
    }

    /// La frase letta da VoiceOver per tutta la riga.
    private var voce: String {
        var testo = "\(g.nome), \(nomeRuolo(g.ruolo ?? "")), \(sottotitolo)"
        if let p = g.previsione { testo += ", fantavoto atteso " + Formato.punti(p.fvAtteso) } else { testo += ", non gioca" }
        return testo
    }

    var body: some View {
        let p = g.previsione
        Button { if let id = g.id { apri(id) } } label: {
            HStack(spacing: 12) {
                AvatarGiocatore(id: g.id, squadra: g.squadraSlug ?? p?.squadra, indice: p?.indice, dimensione: 44, nome: g.nome, ruolo: g.ruolo)
                VStack(alignment: .leading, spacing: 2) {
                    HStack(spacing: 6) {
                        BadgeRuolo(ruolo: g.ruolo ?? "?", piccolo: true)
                        Text(g.nome).font(.headline).lineLimit(2)
                    }
                    Text(sottotitolo).font(.caption).foregroundStyle(.secondary)
                    if let etichette = p?.etichette, !etichette.isEmpty {
                        Text(etichette.map(\.testo).joined(separator: " · ")).font(.caption).foregroundStyle(etichette.contains { $0.gravita == .grave } ? Color.malus : .secondary)
                    }
                }
                Spacer(minLength: 8)
                if let p {
                    VStack(alignment: .trailing, spacing: 2) {
                        Text(Formato.punti(p.fvAtteso)).font(.headline).monospacedDigit()
                        Text("gioca \(Formato.percento(p.pVoto))%").font(.caption2).foregroundStyle(.secondary)
                    }
                } else {
                    Text(g.id == nil ? "?" : "non gioca").font(.caption).foregroundStyle(.secondary)
                }
            }
            .frame(minHeight: 44)
            .contentShape(Rectangle())
            .accessibilityElement(children: .ignore)
            .accessibilityLabel(voce)
        }
        .buttonStyle(.plain)
        .disabled(g.id == nil)
    }
}

struct RosaView: View {
    let nome: String
    @StateObject private var vm: RosaViewModel
    @Environment(\.vediFormazioneDi) private var vediFormazione
    @Environment(\.funzioni) private var funzioni
    @ObservedObject private var immagini = Immagini.condivise
    @State private var sceltaStemma: PhotosPickerItem?
    @State private var sceltaMaglia: PhotosPickerItem?
    @State private var sceglieFile = false
    @State private var tipoFile = "stemma"
    @State private var chiediIndirizzo = false
    @State private var indirizzoScritto = ""

    init(nome: String, server: any ServerClient) {
        self.nome = nome
        _vm = StateObject(wrappedValue: RosaViewModel(nome: nome, server: server))
    }

    private let reparti = [("P", "Portieri"), ("D", "Difensori"), ("C", "Centrocampisti"), ("A", "Attaccanti")]

    var body: some View {
        ZStack {
            Sfondo()
            List {
                if let r = vm.caricatore.dato {
                    intestazione(r)
                    ForEach(reparti, id: \.0) { reparto in
                        let giocatori = r.giocatori.filter { $0.ruolo == reparto.0 }
                        Section("\(reparto.1) (\(giocatori.count))") {
                            ForEach(giocatori, id: \.ident) { RigaRosa(g: $0) }
                        }
                    }
                    // Giocatori che il server non ha saputo collegare a un ruolo (non presenti nel listone).
                    let sconosciuti = r.giocatori.filter { !["P", "D", "C", "A"].contains($0.ruolo ?? "") }
                    if !sconosciuti.isEmpty {
                        Section("Non riconosciuti (da controllare)") {
                            ForEach(sconosciuti, id: \.ident) { RigaRosa(g: $0) }
                        }
                    }
                    if let agg = r.aggiornato {
                        Text("Rose aggiornate il \(String(agg.prefix(10)))").font(.caption).foregroundStyle(.secondary)
                    }
                } else if let e = vm.caricatore.errore {
                    ErroreVista(messaggio: e) { Task { await vm.carica() } }
                } else {
                    ScheletroRighe(righe: 5).listRowBackground(Color.clear)
                }
            }
            .scrollContentBackground(.hidden)
        }
        .navigationTitle(nome)
        .navigationBarTitleDisplayMode(.inline)
        .ricercaGlobale()
        .task { await vm.carica() }
        .fileImporter(isPresented: $sceglieFile, allowedContentTypes: [.image], allowsMultipleSelection: false) { risultato in
            Task { await caricaDaFile(risultato, tipo: tipoFile) }
        }
        .alert("Indirizzo dell'immagine", isPresented: $chiediIndirizzo) {
            TextField("https://…", text: $indirizzoScritto)
                .textInputAutocapitalization(.never).autocorrectionDisabled().keyboardType(.URL)
            Button("Usa come stemma") { Task { await vm.inviaDaIndirizzo(indirizzoScritto, tipo: "stemma") } }
            Button("Usa come divisa") { Task { await vm.inviaDaIndirizzo(indirizzoScritto, tipo: "maglia") } }
            Button("Annulla", role: .cancel) {}
        } message: {
            Text("Solo indirizzi https di un'immagine (stemma o divisa della tua squadra).")
        }
        .onChange(of: sceltaStemma) { _, nuovo in
            guard let nuovo else { return }
            Task { await carica(nuovo, tipo: "stemma"); sceltaStemma = nil }
        }
        .onChange(of: sceltaMaglia) { _, nuovo in
            guard let nuovo else { return }
            Task { await carica(nuovo, tipo: "maglia"); sceltaMaglia = nil }
        }
    }

    /// Un'immagine scelta con Files: letta, ridotta e mandata al server.
    private func caricaDaFile(_ risultato: Result<[URL], Error>, tipo: String) async {
        guard case .success(let urls) = risultato, let url = urls.first else {
            if case .failure(let e) = risultato { vm.messaggio = e.localizedDescription }
            return
        }
        guard let dati = try? await LetturaFile.leggi(url, massimo: 20 * 1024 * 1024), let immagine = UIImage(data: dati),
              let pronti = immagine.datiPerServer() else {
            vm.messaggio = "Non riesco a leggere l'immagine. Salvala su questo iPhone (Files > Sul mio iPhone) e riprova."
            return
        }
        await vm.inviaImmagine(pronti, tipo: tipo)
    }

    /// Il giocatore scelto dalla libreria foto, ridotto e mandato al server.
    private func carica(_ voce: PhotosPickerItem, tipo: String) async {
        guard let dati = try? await voce.loadTransferable(type: Data.self), let immagine = UIImage(data: dati),
              let pronti = immagine.datiPerServer() else {
            vm.messaggio = "Non riesco a leggere l'immagine."
            return
        }
        await vm.inviaImmagine(pronti, tipo: tipo)
    }

    @ViewBuilder
    private func intestazione(_ r: Rosa) -> some View {
        Section {
            HStack(spacing: 16) {
                slot("stemma", "Stemma", $sceltaStemma)
                slot("maglia", "Maglia", $sceltaMaglia)
            }
            .frame(maxWidth: .infinity)
            if let c = r.creditiResidui { Text("Crediti residui: \(Formato.intero(c))") }
            if r.mia != true {
                Button { vediFormazione(nome) } label: { Label("Formazione consigliata per loro", systemImage: "sportscourt").frame(minHeight: 44) }
            }
            Menu {
                Button("Stemma da un file") { tipoFile = "stemma"; sceglieFile = true }
                Button("Divisa da un file") { tipoFile = "maglia"; sceglieFile = true }
            } label: {
                Label("Da un file", systemImage: "folder").frame(minHeight: 44)
            }
            .disabled(vm.inCorso)
            // Lo scarica il server: il server la blocca per tutti se l'amministratore la spegne, anche con «Mostra tutte» (qui uguale).
            if funzioni.accesoDavvero(Funzione.immaginiWeb) {
                Button { indirizzoScritto = ""; chiediIndirizzo = true } label: {
                    Label("Da un indirizzo web", systemImage: "link").frame(minHeight: 44)
                }
                .disabled(vm.inCorso)
                Text("Dall'app o dal sito di Leghe tieni premuto sullo stemma o sulla divisa e scegli «Salva immagine» (oppure copia l'indirizzo dell'immagine), poi incollalo qui. Se l'indirizzo non è pubblico, salva l'immagine e caricala dalla libreria foto.")
                    .font(.footnote).foregroundStyle(.secondary)
            } else {
                Text("Per stemma e divisa scegli una foto dalla libreria o un file.").font(.footnote).foregroundStyle(.secondary)
            }
            if let m = vm.messaggio { Text(m).font(.footnote).foregroundStyle(.secondary) }
            ForEach(r.avvisi ?? [], id: \.self) { Label($0, systemImage: "exclamationmark.triangle").font(.footnote).foregroundStyle(Color.attenzione) }
        }
    }

    private func slot(_ tipo: String, _ titolo: String, _ scelta: Binding<PhotosPickerItem?>) -> some View {
        VStack(spacing: 6) {
            StemmaSquadra(nome: nome, tipo: tipo, dimensione: 72)
            PhotosPicker(selection: scelta, matching: .images) {
                Label(immagini.haImmagine(nome, tipo: tipo) ? "Cambia \(titolo.lowercased())" : "Carica \(titolo.lowercased())", systemImage: "photo")
                    .font(.footnote.weight(.semibold))
                    .frame(minHeight: 44)
            }
        }
        .frame(maxWidth: .infinity)
    }
}

struct NovitaView: View {
    @StateObject private var caricatore: Caricatore<[VoceNovita]>
    /// L'ultima versione guardata: Oggi smette di mostrare il banner «Novità nell'app».
    @AppStorage("novitaVista") private var novitaVista = ""

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
                                if let data = v.data { Text(Quando.dataVersione(data)).font(.caption).foregroundStyle(.secondary).monospacedDigit() }
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
                        Scheletro(schede: 2, righe: 3)
                    }
                }
                .padding(16)
            }
            .refreshable { await caricatore.ricarica() }
        }
        .navigationTitle("Novità")
        .task {
            await caricatore.ricarica()
            if let ultima = caricatore.dato?.first?.versione { novitaVista = ultima }
        }
    }
}

struct StatoDatiView: View {
    @StateObject private var caricatore: Caricatore<StatoDati>
    @StateObject private var affidabilita: Caricatore<Affidabilita>
    @ObservedObject var aggiornamento: AggiornaDatiViewModel

    init(server: any ServerClient, aggiornamento: AggiornaDatiViewModel) {
        _caricatore = StateObject(wrappedValue: Caricatore<StatoDati>("/api/stato-dati", server: server))
        _affidabilita = StateObject(wrappedValue: Caricatore<Affidabilita>("/api/affidabilita", server: server))
        self.aggiornamento = aggiornamento
    }

    var body: some View {
        ZStack {
            Sfondo()
            List {
                Section {
                    AggiornaDatiSezione(vm: aggiornamento)
                }
                if let s = caricatore.dato {
                    Section("Dati") {
                        riga("Stagione", s.stagione ?? "—")
                        riga("Calciatori", "\(s.calciatori ?? 0)")
                        riga("Partite giocate", "\(s.partite?.giocate ?? 0) / \(s.partite?.totali ?? 0)")
                        riga("Voti", "\(s.voti ?? 0)")
                        riga("Coppe europee fino al", s.coppeFino ?? "—")
                    }
                    Section("Avanzate") {
                        // i nomi grezzi dei dati («dati-extra») si leggono meglio tradotti; la lista sta ripiegata
                        DisclosureGroup("Ultimi aggiornamenti dei dati") {
                            ForEach((s.aggiornamenti ?? []).filter { !NomiDati.daNascondere($0.cosa) }) { a in
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(NomiDati.leggibile(a.cosa))
                                    Text(Quando.leggibile((a.quando ?? "").replacingOccurrences(of: "T", with: " "))).font(.caption).foregroundStyle(.secondary)
                                    ForEach(a.errori ?? [], id: \.self) { Text($0).font(.caption).foregroundStyle(Color.attenzione) }
                                }
                                .accessibilityElement(children: .combine)
                            }
                        }
                    }
                    if let probabili = s.probabili, !probabili.isEmpty {
                        Section("Probabili formazioni raccolte") {
                            ForEach(probabili) { p in
                                riga("Giornata \(p.giornata)", "\(p.giocatori ?? 0) giocatori")
                            }
                        }
                    }
                    if let c = s.calibrazione, let gruppi = c.gruppi {
                        Section {
                            ForEach(gruppi) { g in
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(g.gruppo)
                                    Text((g.n ?? 0) > 0
                                         ? "\(g.n ?? 0) giocatori · hanno giocato \(Formato.percento(g.osservato))% · previsto \(Formato.percento(g.previsto))%\(g.indicativo == true ? " (pochi dati)" : "")"
                                         : "ancora nessun dato")
                                        .font(.caption).foregroundStyle(.secondary)
                                }
                                .accessibilityElement(children: .combine)
                            }
                        } header: { Text("Quanto sono giuste le previsioni") } footer: {
                            Text((c.giornate ?? 0) > 0 ? "Giornate già giocate con le probabili raccolte: \(c.giornate ?? 0)." : "Appena finisce una giornata, qui si confronta chi era dato titolare con chi ha davvero preso voto.")
                        }
                    }
                } else if let e = caricatore.errore {
                    ErroreVista(messaggio: e) { Task { await caricatore.ricarica() } }
                } else {
                    ScheletroRighe(righe: 5).listRowBackground(Color.clear)
                }
                Section("Quanto sono affidabili le previsioni") {
                    affidabilitaContenuto
                }
            }
            .scrollContentBackground(.hidden)
        }
        .navigationTitle("Stato dei dati")
        .refreshable { await caricatore.ricarica(); await affidabilita.ricarica() }
        .task { await caricatore.ricarica(); await affidabilita.ricarica() }
    }

    @ViewBuilder
    private var affidabilitaContenuto: some View {
        if let a = affidabilita.dato, let s = a.sintesi, (s.giornate ?? 0) > 0 {
            Text("Prova sulle ultime \(s.giornate ?? 0) giornate giocate, usando per ognuna solo i dati che c'erano prima. «Da fantamedia» è la scelta più semplice: chi ha la media più alta.")
                .font(.footnote).foregroundStyle(.secondary)
            FilaTessere {
                TesseraDato(valore: s.erroreModello.map { Formato.decimali($0, cifre: 2) } ?? "–", etichetta: "errore sui fantavoti (SchieraXI)")
                TesseraDato(valore: s.erroreFantamedia.map { Formato.decimali($0, cifre: 2) } ?? "–", etichetta: "errore (da fantamedia)")
                TesseraDato(valore: s.puntiModello.map { Formato.decimali($0) } ?? "–", etichetta: "punti formazione (SchieraXI)")
            }
            Text("Punti medi per giornata: SchieraXI \(s.puntiModello.map { Formato.decimali($0) } ?? "–"), da fantamedia \(s.puntiFantamedia.map { Formato.decimali($0) } ?? "–"), massimo possibile \(s.puntiPerfetta.map { Formato.decimali($0) } ?? "–"). Errore più basso e punti più alti sono meglio. Nelle giornate passate mancano le probabili formazioni, quindi dal vivo il modello va un po' meglio.")
                .font(.footnote).foregroundStyle(.secondary)
            let righe = (a.righe ?? []).filter { $0.puntiModello != nil }
            if righe.count >= 2 { GraficoAffidabilita(righe: righe) }
        } else if affidabilita.errore != nil, affidabilita.dato == nil {
            Text("Non riesco a leggere la prova delle previsioni.").font(.footnote).foregroundStyle(Color.attenzione)
        } else {
            Text("La prova si fa da sola dopo gli aggiornamenti, appena c'è almeno una giornata finita.").font(.footnote).foregroundStyle(.secondary)
        }
    }

    private func riga(_ t: String, _ v: String) -> some View {
        RigaValore(titolo: t, valore: v, cifreFisse: true)
    }
}

/// Importazione delle rose da un file Excel di Leghe (scelto con il selettore di file di iOS) o dal testo incollato.
struct ImportaExcelView: View {
    @StateObject private var vm: ImportaExcelViewModel
    @StateObject private var dubbi: DubbiRoseViewModel
    @EnvironmentObject private var nav: Navigazione
    @State private var scegli = false

    init(server: any ServerClient) {
        _vm = StateObject(wrappedValue: ImportaExcelViewModel(server: server))
        _dubbi = StateObject(wrappedValue: DubbiRoseViewModel(server: server))
    }

    var body: some View {
        ZStack {
            Sfondo()
            List {
                Section {
                    Text("Esporta le rose da Leghe (Excel, CSV o testo), poi scegli qui il file: l'app ti dice cosa è cambiato (scambi, svincolati presi, tagli, crediti). Puoi anche aprire il file con SchieraXI da Files, Mail o dal menu Condividi.")
                        .font(.footnote).foregroundStyle(.secondary)
                    Button {
                        scegli = true
                    } label: {
                        if vm.inCorso { ProgressView() } else { Label("Scegli il file (Excel, CSV, testo)", systemImage: "doc.badge.plus") }
                    }
                    .disabled(vm.inCorso)
                    .frame(minHeight: 44)
                    Toggle("Togli le squadre che non sono nel file", isOn: $vm.sostituisciTutto).tint(Color.verde).frame(minHeight: 44)
                }
                Section {
                    Text("Se non hai il file Excel: copia la pagina delle rose di Leghe e incollala qui. Le squadre che non sono nel testo restano com'erano.")
                        .font(.footnote).foregroundStyle(.secondary)
                    TextEditor(text: $vm.testoRose).frame(minHeight: 110).accessibilityLabel("Testo delle rose")
                    Button { Task { await vm.importaTesto() } } label: { Text("Importa il testo").frame(maxWidth: .infinity, minHeight: 44) }
                        .disabled(vm.inCorso)
                } header: { Text("Incolla il testo delle rose") }
                if let errore = vm.errore { Section { Text(errore).foregroundStyle(Color.attenzione) } }
                if let e = vm.esito {
                    Section("Cosa è cambiato") {
                        if let d = e.differenze { DifferenzeView(differenze: d) }
                        else if let r = e.riepilogo, !r.isEmpty { Text(r) }
                        if let squadre = e.squadreImportate, !squadre.isEmpty {
                            Text("Importate: \(squadre.joined(separator: ", ")) (\(e.totaleSquadre ?? squadre.count) squadre in tutto).")
                                .font(.footnote).foregroundStyle(.secondary)
                        }
                    }
                    Section {
                        if (e.avvisi ?? []).isEmpty {
                            Label("Rose controllate: tutto in ordine.", systemImage: "checkmark.circle").font(.footnote).foregroundStyle(.secondary)
                        } else {
                            ForEach(e.avvisi ?? [], id: \.self) { Text($0).font(.footnote).foregroundStyle(Color.attenzione) }
                        }
                    } header: { Text("Da controllare") }
                }
                if !dubbi.dubbi.isEmpty {
                    Section {
                        Text("Non li ho trovati nel listone (magari ceduti o con un altro nome). Tocca un nome e cerca quello giusto; se non c'è, lascia stare.")
                            .font(.footnote).foregroundStyle(.secondary)
                        ForEach(dubbi.dubbi) { d in
                            Button { dubbi.scelto = d } label: {
                                HStack {
                                    VStack(alignment: .leading, spacing: 2) {
                                        Text(d.nome).foregroundStyle(.primary)
                                        Text(d.squadra).font(.footnote).foregroundStyle(.secondary)
                                    }
                                    Spacer()
                                    Image(systemName: "magnifyingglass").foregroundStyle(.secondary).accessibilityHidden(true)
                                }
                                .frame(minHeight: 44)
                            }
                            .accessibilityLabel("\(d.nome), \(d.squadra), non riconosciuto")
                            .accessibilityHint("Cerca il giocatore giusto")
                        }
                    } header: { Text("Giocatori da sistemare (\(dubbi.dubbi.count))") }
                } else if dubbi.sistemati > 0 {
                    Section { Label("Tutti i giocatori sono riconosciuti.", systemImage: "checkmark.circle").font(.footnote).foregroundStyle(.secondary) }
                }
            }
            .scrollContentBackground(.hidden)
        }
        .navigationTitle("Aggiorna le rose")
        .task { await dubbi.carica() }
        .onChange(of: vm.inCorso) { _, ora in if !ora { Task { await dubbi.carica() } } }
        .sheet(item: $dubbi.scelto) { d in
            NavigationStack { CercaGiocatoreGiustoView(vm: dubbi, dubbio: d) }
        }
        .ricercaGlobale()
        .fileImporter(isPresented: $scegli, allowedContentTypes: vm.tipiAmmessi, allowsMultipleSelection: false) { risultato in
            Task { await vm.importa(risultato) }
        }
        // Un file arrivato da un'altra app («Apri con SchieraXI»): si importa qui, con gli stessi controlli del selettore.
        .task(id: nav.fileDaImportare) {
            guard let url = nav.fileDaImportare else { return }
            nav.fileDaImportare = nil
            await vm.importa(.success([url]))
        }
    }
}

/// Cerca nel listone il giocatore giusto per un nome delle rose che non è stato riconosciuto.
struct CercaGiocatoreGiustoView: View {
    @ObservedObject var vm: DubbiRoseViewModel
    let dubbio: GiocatoreDaSistemare
    @Environment(\.dismiss) private var chiudi
    @State private var testo = ""

    var body: some View {
        List {
            Section {
                TextField("Cerca il giocatore giusto", text: $testo)
                    .textInputAutocapitalization(.words)
                    .autocorrectionDisabled()
                    .frame(minHeight: 44)
                    .accessibilityLabel("Cerca il giocatore giusto per \(dubbio.nome)")
            } footer: { Text("Nella rosa di \(dubbio.squadra) c'è scritto «\(dubbio.nome)».") }
            if let errore = vm.errore { Section { Text(errore).foregroundStyle(Color.attenzione) } }
            Section {
                if vm.cercando { ProgressView() }
                ForEach(vm.trovati) { g in
                    Button { Task { await vm.abbina(dubbio, a: g) } } label: {
                        Text("\(g.nome) · \(g.ruolo) · \(g.squadra ?? "–")").frame(maxWidth: .infinity, minHeight: 44, alignment: .leading)
                    }
                }
                if !vm.cercando, vm.trovati.isEmpty, testo.trimmingCharacters(in: .whitespaces).count >= 2 {
                    Text("Nessun risultato").font(.footnote).foregroundStyle(.secondary)
                }
            }
        }
        .navigationTitle("Giocatore giusto")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Annulla") { chiudi() } } }
        .task(id: testo) { await vm.cerca(testo) }
    }
}
