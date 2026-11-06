import SwiftUI
import PhotosUI

/// Squadre della lega e loro rose; da qui si indica quale è la propria. Le parole sono quelle della web (`ParoleSquadre`).
struct SquadreView: View {
    @StateObject private var vm: SquadreViewModel
    private let server: any ServerClient
    @Environment(\.funzioni) private var funzioni
    /// Il foglio «Stemma e maglia» della mia squadra.
    @State private var apriImmagini = false

    init(server: any ServerClient) {
        self.server = server
        _vm = StateObject(wrappedValue: SquadreViewModel(server: server))
    }

    var body: some View {
        ZStack {
            Sfondo()
            List {
                TitoloNellaPagina()
                if let errore = vm.errore {
                    Text(errore).font(.footnote).foregroundStyle(Color.attenzione)
                }
                if let s = vm.caricatore.dato {
                    if s.isEmpty {
                        Text(ParoleSquadre.importaPrima).foregroundStyle(Color.testoSecondario)
                    } else {
                        Section(titolo: ParoleSquadre.miaSquadra) { miaSquadra(s) }
                        // senza le rose degli altri c'è solo la carta «La mia squadra», con «Vedi la rosa» (come la web)
                        if funzioni.acceso(Funzione.squadreAltrui) {
                            Section {
                                ForEach(s) { sq in
                                    NavigationLink(value: PaginaLega.rosa(sq.nome)) {
                                        RigaSquadra(squadra: sq)
                                    }
                                    .swipeActions {
                                        Button("È la mia") { Task { await vm.impostaMia(sq.nome) } }.tint(Color.verde)
                                    }
                                    .accessibilityAction(named: "È la mia squadra") { Task { await vm.impostaMia(sq.nome) } }
                                }
                            } footer: {
                                Text(ParoleSquadre.toccaUnaSquadra).foregroundStyle(Color.testoSecondario)
                            }
                        }
                    }
                } else if let e = vm.caricatore.errore {
                    ErroreVista(messaggio: e) { Task { await vm.carica() } }
                } else {
                    ScheletroRighe(righe: 5).listRowBackground(Color.clear)
                }
            }
            .scrollContentBackground(.hidden)
            .avvisoDatiSalvati(vm.caricatore)
        }
        .titoloPagina(ParoleSquadre.titoloPagina(squadreAltrui: funzioni.acceso(Funzione.squadreAltrui)))
        .ricercaGlobale()
        .task { await vm.carica() }
        .sheet(isPresented: $apriImmagini) {
            NavigationStack {
                RosaView(nome: vm.mia, server: server, soloImmagini: true)
                    .toolbar {
                        ToolbarItem(placement: .confirmationAction) { Button(ParoleSquadre.chiudi) { apriImmagini = false } }
                    }
            }
        }
    }

    /// La carta «La mia squadra» (come la web): stemma e maglia, nome, giocatori e crediti, «Stemma e maglia», «Vedi la rosa»
    /// e, dietro «Non è la tua squadra?», la scelta di un'altra. Senza una squadra scelta solo l'invito a sceglierla.
    @ViewBuilder
    private func miaSquadra(_ squadre: [SquadraLega]) -> some View {
        if let mia = squadre.first(where: { $0.mia == true }) {
            HStack(spacing: 12) {
                StemmaSquadra(nome: mia.nome, dimensione: 44)
                StemmaSquadra(nome: mia.nome, tipo: "maglia", dimensione: 44, nascondiSeMancante: true)
                VStack(alignment: .leading, spacing: 2) {
                    NomeConPillola(nome: mia.nome) { EmptyView() }
                    Text(ParoleSquadre.riepilogo(giocatori: mia.giocatori, crediti: mia.creditiResidui))
                        .font(.caption).foregroundStyle(Color.testoSecondario)
                }
            }
            .frame(minHeight: 44)
            .accessibilityElement(children: .combine)
            Button { apriImmagini = true } label: {
                Label(ParoleSquadre.stemmaEMaglia, systemImage: "photo").frame(minHeight: 44)
            }
            NavigationLink(value: PaginaLega.rosa(mia.nome)) {
                Label(ParoleSquadre.vediLaRosa, systemImage: "person.3").frame(minHeight: 44)
            }
            DisclosureGroup(ParoleSquadre.nonLaTua) { sceltaMia(squadre) }
        } else {
            Text(ParoleSquadre.scegliLaTua).foregroundStyle(Color.testoSecondario)
            sceltaMia(squadre)
        }
    }

    private func sceltaMia(_ squadre: [SquadraLega]) -> some View {
        Picker(ParoleSquadre.tuaSquadra, selection: Binding(get: { vm.mia }, set: { nuova in Task { await vm.impostaMia(nuova) } })) {
            ForEach(squadre) { Text($0.nome).tag($0.nome) }
        }
        .frame(minHeight: 44)
    }
}

/// Un corpo `{nome, nuovo}` per `PUT /api/squadre/nome` (lo stesso della web).
private struct CorpoNuovoNome: Encodable {
    let nome: String
    let nuovo: String
}

/// Della risposta di `PUT /api/squadre/nome` serve il nome come l'ha scritto il server (spazi sistemati).
private struct EsitoNuovoNome: Decodable {
    let nome: String
}

/// Logica della rosa di una squadra: i giocatori, il nome e i crediti che si possono cambiare, il caricamento di stemma e maglia.
@MainActor
final class RosaViewModel: ViewModelBase {
    private let server: any ServerClient
    private let immagini: Immagini
    /// Il nome della squadra: cambia quando la si rinomina («Cambia il nome»).
    @Published private(set) var nome: String
    let caricatore: Caricatore<Rosa>
    @Published var messaggio: String?
    @Published var inCorso = false
    /// I due campi che si scrivono: partono dai valori del server (la rosa) e restano come li scrive l'utente finché non salva.
    @Published var nuovoNome: String
    @Published var crediti = ""
    private var nomeDelServer: String
    private var creditiDelServer = ""

    init(nome: String, server: any ServerClient, immagini: Immagini) {
        self.server = server
        self.immagini = immagini
        self.nome = nome
        nuovoNome = nome
        nomeDelServer = nome
        caricatore = Caricatore<Rosa>(Self.percorso(nome), server: server)
        super.init()
        osserva(caricatore)
    }

    private static func percorso(_ nome: String) -> String { "/api/rosa?squadra=\(IndirizzoServer.codifica(nome))" }

    /// Rilegge la rosa. Un nome o dei crediti scritti e non ancora salvati restano; `forza` (cambiati da un altro dispositivo) riparte
    /// da quelli del server.
    func carica(forza: Bool = false) async {
        await caricatore.ricarica()
        if let r = caricatore.dato { allinea(a: r, forza: forza) }
    }

    private func allinea(a r: Rosa, forza: Bool) {
        let creditiServer = r.creditiResidui.map { String(Formato.intero($0)) } ?? ""
        if forza || nuovoNome == nomeDelServer { nuovoNome = nome }
        if forza || crediti == creditiDelServer { crediti = creditiServer }
        nomeDelServer = nome
        creditiDelServer = creditiServer
    }

    /// «Cambia il nome» (`PUT /api/squadre/nome`, come la web): il nome nuovo senza spazi in più, da 1 a 60 caratteri. Il server
    /// sposta con il nome rose, «la mia squadra», stemma e maglia; poi la rosa si rilegge con il nome nuovo.
    func rinomina() async {
        let nuovo = nuovoNome.split(whereSeparator: \.isWhitespace).joined(separator: " ")
        guard !nuovo.isEmpty, nuovo.count <= 60 else {
            messaggio = ParoleSquadre.nomeNonValido
            Haptics.esito(riuscito: false)
            return
        }
        guard nuovo != nome else {
            nuovoNome = nuovo
            return
        }
        inCorso = true
        defer { inCorso = false }
        do {
            let risposta = try await server.corpoJSON("PUT", "/api/squadre/nome", CorpoNuovoNome(nome: nome, nuovo: nuovo))
            let esito: EsitoNuovoNome? = try? Decodifica.decodifica(risposta)
            let scelto = esito?.nome ?? nuovo
            nome = scelto
            nomeDelServer = scelto
            nuovoNome = scelto
            messaggio = ParoleSquadre.nomeSalvato
            Haptics.esito(riuscito: true)
            await immagini.caricaElenchi()          // stemma e maglia hanno seguito il nome
            await caricatore.ricarica(Self.percorso(scelto))
            if let r = caricatore.dato { allinea(a: r, forza: false) }
        } catch {
            let conflitto = (error as? ErroreApi)?.eConflitto == true
            messaggio = error.localizedDescription
            Haptics.esito(riuscito: false)
            if conflitto { await carica(forza: true) }   // cambiata da un altro dispositivo: si rilegge e si mostrano i valori nuovi
        }
    }

    /// «Salva» accanto ai crediti residui (`PUT /api/crediti`, come la web): un numero intero da 0 a 99999.
    func salvaCrediti() async {
        let testo = crediti.trimmingCharacters(in: .whitespaces)
        guard testo.range(of: "^[0-9]{1,5}$", options: .regularExpression) != nil, let numero = Int(testo) else {
            messaggio = ParoleSquadre.scriviCrediti
            Haptics.esito(riuscito: false)
            return
        }
        inCorso = true
        defer { inCorso = false }
        do {
            _ = try await server.corpoJSON("PUT", "/api/crediti", CreditiSquadre(crediti: [nome: numero]))
            crediti = testo
            creditiDelServer = testo
            messaggio = ParoleSquadre.creditiSalvati
            Haptics.esito(riuscito: true)
        } catch {
            let conflitto = (error as? ErroreApi)?.eConflitto == true
            messaggio = error.localizedDescription
            Haptics.esito(riuscito: false)
            if conflitto { await carica(forza: true) }
        }
    }

    /// Lo stemma o la maglia da un indirizzo web: lo scarica il server.
    func inviaDaIndirizzo(_ indirizzo: String, tipo: String) async {
        inCorso = true
        defer { inCorso = false }
        do {
            try await immagini.inviaDaIndirizzo(indirizzo, squadra: nome, tipo: tipo)
            messaggio = ParoleSquadre.aggiornata(tipo: tipo)
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
            try await immagini.invia(dati, squadra: nome, tipo: tipo)
            messaggio = ParoleSquadre.aggiornata(tipo: tipo)
            Haptics.esito(riuscito: true)
        } catch {
            messaggio = error.localizedDescription
            Haptics.esito(riuscito: false)
        }
    }
}

struct RosaView: View {
    let nome: String
    /// Nel foglio «Stemma e maglia» di Squadre: solo le immagini della squadra, senza i giocatori.
    let soloImmagini: Bool
    @StateObject private var vm: RosaViewModel
    @Environment(\.vediFormazioneDi) private var vediFormazione
    @Environment(\.funzioni) private var funzioni
    @Environment(\.dynamicTypeSize) private var dimensioneTesto
    @ObservedObject private var immagini = Immagini.condivise
    @State private var sceltaStemma: PhotosPickerItem?
    @State private var sceltaMaglia: PhotosPickerItem?
    @State private var sceglieFile = false
    @State private var tipoFile = "stemma"
    @State private var chiediIndirizzo = false
    @State private var indirizzoScritto = ""

    init(nome: String, server: any ServerClient, soloImmagini: Bool = false) {
        self.nome = nome
        self.soloImmagini = soloImmagini
        _vm = StateObject(wrappedValue: RosaViewModel(nome: nome, server: server, immagini: Immagini.condivise))
    }

    private let reparti = [("P", "Portieri"), ("D", "Difensori"), ("C", "Centrocampisti"), ("A", "Attaccanti")]

    var body: some View {
        conTitolo(
            ZStack {
                Sfondo()
                if soloImmagini { soloLeImmagini } else { rosaCompleta }
            }
        )
        .task { if !soloImmagini { await vm.carica() } }
        .fileImporter(isPresented: $sceglieFile, allowedContentTypes: [.image], allowsMultipleSelection: false) { risultato in
            Task { await caricaDaFile(risultato, tipo: tipoFile) }
        }
        .alert(ParoleSquadre.indirizzoDellImmagine, isPresented: $chiediIndirizzo) {
            TextField("https://…", text: $indirizzoScritto)
                .textInputAutocapitalization(.never).autocorrectionDisabled().keyboardType(.URL)
            Button(ParoleSquadre.usaCome(tipo: "stemma")) { Task { await vm.inviaDaIndirizzo(indirizzoScritto, tipo: "stemma") } }
            Button(ParoleSquadre.usaCome(tipo: "maglia")) { Task { await vm.inviaDaIndirizzo(indirizzoScritto, tipo: "maglia") } }
            Button(ParoleSquadre.annulla, role: .cancel) {}
        } message: {
            Text(ParoleSquadre.indirizzoImmagine)
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

    /// Il titolo: nella pagina il nome della squadra (intero, a capo: nella barra si taglierebbe, #276); nel foglio «Stemma e maglia».
    @ViewBuilder
    private func conTitolo<Contenuto: View>(_ contenuto: Contenuto) -> some View {
        if soloImmagini {
            contenuto.navigationTitle(ParoleSquadre.stemmaEMaglia).navigationBarTitleDisplayMode(.inline)
        } else {
            contenuto.titoloPagina(vm.nome, piccoloInBarra: true).ricercaGlobale()
        }
    }

    private var soloLeImmagini: some View {
        List {
            Section {
                righeImmagini
                if let m = vm.messaggio { Text(m).font(.footnote).foregroundStyle(Color.testoSecondario) }
            }
        }
        .scrollContentBackground(.hidden)
    }

    private var rosaCompleta: some View {
        ScrollViewReader { proxy in
            List {
                TitoloNellaPagina()
                if let r = vm.caricatore.dato {
                    intestazione(r)
                    ForEach(reparti, id: \.0) { reparto in
                        let giocatori = r.giocatori.filter { $0.ruolo == reparto.0 }
                        Section(titolo: "\(reparto.1) (\(giocatori.count))") {
                            ForEach(giocatori, id: \.ident) { RigaRosa(g: $0) }
                        }
                    }
                    // Giocatori che il server non ha saputo collegare a un ruolo (non presenti nel listone).
                    let sconosciuti = r.giocatori.filter { !["P", "D", "C", "A"].contains($0.ruolo ?? "") }
                    if !sconosciuti.isEmpty {
                        Section(titolo: ParoleSquadre.senzaRuolo) {
                            ForEach(sconosciuti, id: \.ident) { RigaRosa(g: $0) }
                        }
                    }
                    Text(ParoleSquadre.roseAggiornate(r.aggiornato)).font(.caption).foregroundStyle(Color.testoSecondario)
                    RigaFondoDemo()
                } else if let e = vm.caricatore.errore {
                    ErroreVista(messaggio: e) { Task { await vm.carica() } }
                } else {
                    ScheletroRighe(righe: 5).listRowBackground(Color.clear)
                }
            }
            .scrollContentBackground(.hidden)
            .avvisoDatiSalvati(vm.caricatore)
            // fotografia `lega-rosa-fondo` (#425): la lista scorsa fino all'ultima riga, a dati arrivati
            .demoInFondo()
            .demoScorriA(FondoDemo.idRiga, proxy: proxy, schermate: ["lega-rosa"], inFondo: true, ancora: .bottom,
                         pronto: vm.caricatore.dato != nil)
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
            vm.messaggio = ParoleSquadre.immagineDaFileNonLeggibile
            return
        }
        await vm.inviaImmagine(pronti, tipo: tipo)
    }

    /// Il giocatore scelto dalla libreria foto, ridotto e mandato al server.
    private func carica(_ voce: PhotosPickerItem, tipo: String) async {
        guard let dati = try? await voce.loadTransferable(type: Data.self), let immagine = UIImage(data: dati),
              let pronti = immagine.datiPerServer() else {
            vm.messaggio = ParoleSquadre.immagineNonLeggibile
            return
        }
        await vm.inviaImmagine(pronti, tipo: tipo)
    }

    /// In testa alla rosa, nell'ordine della web: «Cambia il nome», i crediti residui, stemma e maglia, la formazione consigliata.
    @ViewBuilder
    private func intestazione(_ r: Rosa) -> some View {
        Section {
            cambiaIlNome
            creditiResidui
            righeImmagini
            if r.mia != true {
                Button { vediFormazione(vm.nome) } label: {
                    Label(ParoleSquadre.formazioneConsigliataPerLoro, systemImage: "sportscourt").frame(minHeight: 44)
                }
            }
            if let m = vm.messaggio { Text(m).font(.footnote).foregroundStyle(Color.testoSecondario) }
            ForEach(r.avvisi ?? [], id: \.self) { Label($0, systemImage: "exclamationmark.triangle").font(.footnote).foregroundStyle(Color.attenzione) }
        }
    }

    /// «Cambia il nome»: il campo con il nome di adesso, «Salva» e la spiegazione (`PUT /api/squadre/nome`).
    private var cambiaIlNome: some View {
        DisclosureGroup(ParoleSquadre.cambiaIlNome) {
            TextField(ParoleSquadre.nuovoNome, text: $vm.nuovoNome)
                .textInputAutocapitalization(.words)
                .autocorrectionDisabled()
                .submitLabel(.done)
                .onSubmit { Task { await vm.rinomina() } }
                .frame(minHeight: 44)
            Button(ParoleSquadre.salva) { Task { await vm.rinomina() } }
                .frame(minHeight: 44)
                .disabled(vm.inCorso)
            Text(ParoleSquadre.aiutoNome).font(.footnote).foregroundStyle(Color.testoSecondario)
        }
    }

    /// «Crediti residui» con il campo e «Salva» (`PUT /api/crediti`). Con il testo grande il campo passa sotto il nome.
    private var creditiResidui: some View {
        ViewThatFits(in: .horizontal) {
            HStack(spacing: 12) {
                Text(ParoleSquadre.creditiResidui)
                Spacer(minLength: 8)
                campoCrediti
                salvaCrediti
            }
            VStack(alignment: .leading, spacing: 8) {
                Text(ParoleSquadre.creditiResidui)
                HStack(spacing: 12) {
                    campoCrediti
                    salvaCrediti
                }
            }
        }
        .frame(minHeight: 44)
    }

    private var campoCrediti: some View {
        TextField("—", text: $vm.crediti)
            .keyboardType(.numberPad)
            .multilineTextAlignment(.trailing)
            .frame(width: 96, minHeight: 44)
            .accessibilityLabel(ParoleSquadre.creditiResidui)
    }

    private var salvaCrediti: some View {
        Button(ParoleSquadre.salva) { Task { await vm.salvaCrediti() } }
            // il campo e il pulsante stanno nella stessa riga di una lista: senza questo un tocco li attiva come uno solo
            .buttonStyle(.borderless)
            .frame(minHeight: 44)
            .disabled(vm.inCorso)
    }

    /// Stemma e maglia: le due immagini con «Carica/Cambia», da un file, da un indirizzo web e le spiegazioni.
    @ViewBuilder
    private var righeImmagini: some View {
        HStack(spacing: 16) {
            slot("stemma", $sceltaStemma)
            slot("maglia", $sceltaMaglia)
        }
        .frame(maxWidth: .infinity)
        Menu {
            Button(ParoleSquadre.daUnFile(tipo: "stemma")) { tipoFile = "stemma"; sceglieFile = true }
            Button(ParoleSquadre.daUnFile(tipo: "maglia")) { tipoFile = "maglia"; sceglieFile = true }
        } label: {
            Label(ParoleSquadre.daUnFileMenu, systemImage: "folder").frame(minHeight: 44)
        }
        .disabled(vm.inCorso)
        // Lo scarica il server: il server la blocca per tutti se l'amministratore la spegne, anche con «Mostra tutte» (qui uguale).
        if funzioni.accesoDavvero(Funzione.immaginiWeb) {
            Button { indirizzoScritto = ""; chiediIndirizzo = true } label: {
                Label(ParoleSquadre.daUnIndirizzoWeb, systemImage: "link").frame(minHeight: 44)
            }
            .disabled(vm.inCorso)
            Text(ParoleSquadre.aiutoIndirizzo)
                .font(.footnote).foregroundStyle(Color.testoSecondario)
        } else {
            Text(ParoleSquadre.senzaIndirizzoWeb).font(.footnote).foregroundStyle(Color.testoSecondario)
        }
    }

    private func slot(_ tipo: String, _ scelta: Binding<PhotosPickerItem?>) -> some View {
        VStack(spacing: 6) {
            StemmaSquadra(nome: vm.nome, tipo: tipo, dimensione: 72)
            PhotosPicker(selection: scelta, matching: .images) {
                // testo molto grande: niente icona e due righe intere («Carica / stemma»), invece di «Cari-ca stem…»
                Label(immagini.haImmagine(vm.nome, tipo: tipo) ? ParoleSquadre.cambia(tipo: tipo) : ParoleSquadre.carica(tipo: tipo),
                      systemImage: "photo")
                    .labelStyle(SoloTestoSeGrande(soloTesto: dimensioneTesto.isAccessibilitySize))
                    .font(.footnote.weight(.semibold))
                    .multilineTextAlignment(.center)
                    .frame(maxWidth: .infinity, minHeight: 44)
                    .contentShape(Rectangle())
            }
            // due pulsanti nella stessa riga di una lista: senza questo un tocco li attiva come uno solo
            .buttonStyle(.borderless)
        }
        .frame(maxWidth: .infinity)
    }
}

/// Con il testo molto grande resta solo il testo (l'icona ruba lo spazio che serve alle parole).
private struct SoloTestoSeGrande: LabelStyle {
    let soloTesto: Bool

    @ViewBuilder
    func makeBody(configuration: Configuration) -> some View {
        if soloTesto { configuration.title } else { Label(configuration) }
    }
}

/// La pillola «Nuovo» accanto al titolo di una versione non ancora vista (come `etichetta` della web).
private struct PillolaNuovo: View {
    var body: some View {
        Text(ParoleNovita.nuovo)
            .font(.caption2.bold())
            .padding(.horizontal, 6).padding(.vertical, 2)
            .background(Color.verde.opacity(0.3), in: Capsule())
    }
}

/// Le novità come la web (`vistaNovita`): ogni carta ha per titolo il titolo della versione e sotto «Versione 1.432 · data»; le
/// versioni non ancora viste hanno «Nuovo»; si vedono le prime 10 (almeno tutte le nuove) e «Mostra le 42 versioni precedenti»
/// apre tutte le altre. Le regole sono in `ParoleNovita`.
struct NovitaView: View {
    @StateObject private var caricatore: Caricatore<[VoceNovita]>
    /// L'ultima versione guardata: Oggi smette di mostrare il banner «Novità nell'app».
    @AppStorage("novitaVista") private var novitaVista = ""
    /// L'ultima versione guardata PRIMA di aprire la pagina: dice quali versioni sono «Nuovo». Si ricorda qui perché `novitaVista`
    /// diventa subito l'ultima versione, e le etichette sparirebbero mentre si legge.
    @State private var vistaPrima: String?
    @State private var tutte = false

    init(server: any ServerClient) {
        _caricatore = StateObject(wrappedValue: Caricatore<[VoceNovita]>("/api/novita", server: server))
    }

    var body: some View {
        ZStack {
            Sfondo()
            ScrollView {
                // Una colonna sola, pigra (si disegna solo quello che si vede) e larga al massimo come un testo leggibile:
                // con le colonne affiancate dell'iPad le versioni si leggevano saltando da una colonna all'altra.
                LazyVStack(spacing: 14) {
                    TitoloNellaPagina()
                    if let n = caricatore.dato {
                        let nuoveDa = ParoleNovita.nuoveDa(versioni: n.map(\.versione), ultimaVista: vistaPrima)
                        let mostrate = tutte ? n.count : ParoleNovita.quanteVisibili(totale: n.count, nuoveDa: nuoveDa)
                        ForEach(Array(n.prefix(mostrate).enumerated()), id: \.element.id) { indice, v in
                            carta(v, nuova: indice < nuoveDa)
                        }
                        if n.count > mostrate {
                            Button {
                                tutte = true
                            } label: {
                                Text(ParoleNovita.precedenti(n.count - mostrate)).frame(maxWidth: .infinity, minHeight: Tema.areaTocco)
                            }
                            .buttonStyle(.bordered)
                        }
                    } else if let e = caricatore.errore {
                        ErroreVista(messaggio: e) { Task { await caricatore.ricarica() } }
                    } else {
                        Scheletro(schede: 2, righe: 3)
                    }
                }
                .padding(16)
                .frame(maxWidth: 720)
                .frame(maxWidth: .infinity)
            }
            .ricercaGlobale()
            .refreshable { await caricatore.ricarica() }
            .avvisoDatiSalvati(caricatore)
        }
        .titoloPagina("Novità")
        .task {
            if vistaPrima == nil { vistaPrima = novitaVista }
            await caricatore.ricarica()
            if let ultima = caricatore.dato?.first?.versione { novitaVista = ultima }
        }
    }

    private func carta(_ v: VoceNovita, nuova: Bool) -> some View {
        Carta {
            HStack(alignment: .firstTextBaseline, spacing: 8) {
                Text(v.titolo).font(.headline).fixedSize(horizontal: false, vertical: true)
                if nuova { PillolaNuovo() }
            }
            .accessibilityElement(children: .combine)
            .accessibilityAddTraits(.isHeader)
            Text(ParoleNovita.sotto(versione: v.versione, data: v.data))
                .font(.caption).foregroundStyle(Color.testoSecondario).monospacedDigit()
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
            ScrollViewReader { proxy in
                List {
                    TitoloNellaPagina()
                    Section {
                        AggiornaDatiSezione(vm: aggiornamento)
                    }
                    if let s = caricatore.dato {
                        Section(titolo: "Dati") {
                            riga("Stagione", s.stagione ?? "—")
                            riga("Calciatori", "\(s.calciatori ?? 0)")
                            riga("Partite giocate", "\(s.partite?.giocate ?? 0) / \(s.partite?.totali ?? 0)")
                            riga("Voti", "\(s.voti ?? 0)")
                            riga("Coppe europee fino al", s.coppeFino.map { Quando.dataVersione($0) } ?? "—")
                        }
                        Section(titolo: "Avanzate") {
                            // i nomi grezzi dei dati («dati-extra») si leggono meglio tradotti; la lista sta ripiegata
                            DisclosureGroup("Ultimi aggiornamenti dei dati") {
                                ForEach((s.aggiornamenti ?? []).filter { !NomiDati.daNascondere($0.cosa) }) { a in
                                    VStack(alignment: .leading, spacing: 2) {
                                        Text(NomiDati.leggibile(a.cosa))
                                        Text(Quando.leggibile((a.quando ?? "").replacingOccurrences(of: "T", with: " "))).font(.caption).foregroundStyle(Color.testoSecondario)
                                        ForEach(a.errori ?? [], id: \.self) { Text($0).font(.caption).foregroundStyle(Color.attenzione) }
                                    }
                                    .accessibilityElement(children: .combine)
                                }
                            }
                        }
                        if let probabili = s.probabili, !probabili.isEmpty {
                            Section(titolo: "Probabili formazioni raccolte") {
                                ForEach(probabili) { p in
                                    riga(TempiLega.serieA(p.giornata), Formato.plurale(p.giocatori ?? 0, "giocatore", "giocatori"))
                                }
                            }
                        }
                        if let c = s.calibrazione, let gruppi = c.gruppi {
                            Section {
                                ForEach(gruppi) { g in
                                    VStack(alignment: .leading, spacing: 2) {
                                        Text(g.gruppo)
                                        Text((g.n ?? 0) > 0
                                             ? "\(Formato.plurale(g.n ?? 0, "giocatore", "giocatori")) · \((g.n ?? 0) == 1 ? "ha" : "hanno") giocato \(Formato.percento(g.osservato))% · previsto \(Formato.percento(g.previsto))%\(g.indicativo == true ? " (pochi dati)" : "")"
                                             : "ancora nessun dato")
                                            .font(.caption).foregroundStyle(Color.testoSecondario)
                                    }
                                    .accessibilityElement(children: .combine)
                                }
                            } header: { Text("Quanto sono giuste le previsioni").foregroundStyle(Color.testoSecondario) } footer: {
                                Text((c.giornate ?? 0) > 0 ? "Giornate già giocate con le probabili raccolte: \(c.giornate ?? 0)." : "Appena finisce una giornata, qui si confronta chi era dato titolare con chi ha davvero preso voto.").foregroundStyle(Color.testoSecondario)
                            }
                        }
                    } else if let e = caricatore.errore {
                        ErroreVista(messaggio: e) { Task { await caricatore.ricarica() } }
                    } else {
                        ScheletroRighe(righe: 5).listRowBackground(Color.clear)
                    }
                    Section(titolo: "Quanto sono affidabili le previsioni") {
                        affidabilitaContenuto
                    }
                    if let registro = caricatore.dato?.registro {
                        RegistroGiornateSezione(registro: registro)
                    }
                    if let nostri = caricatore.dato?.registroNostri {
                        GolAttesiNostriSezione(nostri: nostri)
                    }
                    if let consiglio = caricatore.dato?.consiglio {
                        ConsiglioFormazioneSezione(consiglio: consiglio)
                    }
                    RigaFondoDemo()
                }
                .scrollContentBackground(.hidden)
                // fotografie `lega-stato-fondo` (#425: la lista scorsa fino in fondo, agli indicatori del consiglio) e `lega-stato-nostri`
                // (#430: ferma sul riquadro dei gol attesi nostri, che col consiglio non entra in una foto sola). Lo stato arriva per
                // primo, la prova delle previsioni (a metà pagina) subito dopo: si scorre a entrambi arrivati.
                .demoInFondo()
                .demoScorriA(FondoDemo.arrivoDiStato.id, proxy: proxy, schermate: ["lega-stato"], inFondo: true,
                             ancora: FondoDemo.arrivoDiStato.ancora,
                             pronto: caricatore.dato != nil && (affidabilita.dato != nil || affidabilita.errore != nil))
            }
        }
        .titoloPagina("Stato dei dati")
        .refreshable { await caricatore.ricarica(); await affidabilita.ricarica() }
        .task { await caricatore.ricarica(); await affidabilita.ricarica() }
    }

    @ViewBuilder
    private var affidabilitaContenuto: some View {
        if let a = affidabilita.dato, let s = a.sintesi, (s.giornate ?? 0) > 0 {
            Text("Prova sulle ultime \(s.giornate ?? 0) giornate giocate, usando per ognuna solo i dati che c'erano prima. «Da fantamedia» è la scelta più semplice: chi ha la media più alta.")
                .font(.footnote).foregroundStyle(Color.testoSecondario)
            FilaTessere {
                TesseraDato(valore: s.erroreModello.map { Formato.decimali($0, cifre: 2) } ?? "–", etichetta: "errore sui fantavoti (SchieraXI)")
                TesseraDato(valore: s.erroreFantamedia.map { Formato.decimali($0, cifre: 2) } ?? "–", etichetta: "errore (da fantamedia)")
                TesseraDato(valore: s.puntiModello.map { Formato.decimali($0) } ?? "–", etichetta: "punti formazione (SchieraXI)")
            }
            Text("Punti medi per giornata: SchieraXI \(s.puntiModello.map { Formato.decimali($0) } ?? "–"), da fantamedia \(s.puntiFantamedia.map { Formato.decimali($0) } ?? "–"), massimo possibile \(s.puntiPerfetta.map { Formato.decimali($0) } ?? "–"). Errore più basso e punti più alti sono meglio. Nelle giornate passate mancano le probabili formazioni, quindi dal vivo il modello va un po' meglio.")
                .font(.footnote).foregroundStyle(Color.testoSecondario)
            let righe = (a.righe ?? []).filter { $0.puntiModello != nil }
            if righe.count >= 2 { GraficoAffidabilita(righe: righe) }
        } else if affidabilita.errore != nil, affidabilita.dato == nil {
            Text("Non riesco a leggere la prova delle previsioni.").font(.footnote).foregroundStyle(Color.attenzione)
        } else {
            Text("La prova si fa da sola dopo gli aggiornamenti, appena c'è almeno una giornata finita.").font(.footnote).foregroundStyle(Color.testoSecondario)
        }
    }

    private func riga(_ t: String, _ v: String) -> some View {
        RigaValore(titolo: t, valore: v, cifreFisse: true)
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
            } footer: { Text("Nella rosa di \(dubbio.squadra) c'è scritto «\(dubbio.nome)».").foregroundStyle(Color.testoSecondario) }
            if let errore = vm.errore { Section { Text(errore).foregroundStyle(Color.attenzione) } }
            Section {
                if vm.cercando { ProgressView() }
                ForEach(vm.trovati) { g in
                    Button { Task { await vm.abbina(dubbio, a: g) } } label: {
                        Text("\(g.nome) · \(g.ruolo) · \(g.squadra ?? "–")").frame(maxWidth: .infinity, minHeight: 44, alignment: .leading)
                    }
                }
                if !vm.cercando, vm.trovati.isEmpty, testo.trimmingCharacters(in: .whitespaces).count >= 2 {
                    Text("Nessun risultato").font(.footnote).foregroundStyle(Color.testoSecondario)
                }
            }
        }
        .navigationTitle("Giocatore giusto")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Annulla") { chiudi() } } }
        .task(id: testo) { await vm.cerca(testo) }
    }
}
