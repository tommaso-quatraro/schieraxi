import SwiftUI

/// Logica dell'editor delle regole della lega. Il JSON del server resta intero (`valore`): i campi lo leggono e lo scrivono con
/// percorsi come `bonus.gol.D`, così nessun campo che l'app non conosce va perso. Si può anche incollare il regolamento di Leghe:
/// il server riconosce i valori e l'app li mostra prima di applicarli.
@MainActor
final class RegoleEditorViewModel: ViewModelBase {
    private let server: any ServerClient
    let caricatore: Caricatore<JSONValue>
    @Published var valore: JSONValue = .nullo
    @Published var caricato = false
    @Published var modificato = false
    @Published var esito: String?
    @Published var esitoRiuscito = true
    @Published var inCorso = false
    /// Le fasce del modificatore difesa (si tengono a parte per non far saltare le righe mentre si modificano).
    @Published var fasce: [RegoleLogica.Fascia] = [] {
        didSet { fasceCambiate(fasce) }
    }
    /// Prova del modificatore: voti di portiere e tre difensori.
    @Published var votiProva: [Double] = [6.5, 6, 6.5, 7]
    // Importa dal regolamento di Leghe
    @Published var testoRegolamento = ""
    @Published var riconoscimento: RiconoscimentoRegole?
    @Published var erroreRiconoscimento: String?
    @Published var riconoscimentoInCorso = false

    /// Dopo un 412, quanto si aspetta prima di ricaricare i campi con le regole del server: la frase si legge mentre si vedono ancora
    /// i valori scritti, come la web (che ricarica la pagina dopo 2,5 secondi). I test la mettono a zero.
    private let attesaDopoConflitto: Duration
    /// L'ETag delle regole dopo un 412, finché una lettura riuscita non porta quello vero: con questo ogni scrittura riceve di nuovo
    /// 412 (vedi `ricaricaDopoConflitto`).
    static let etagDaRileggere = "\"da-rileggere\""

    init(server: any ServerClient, attesaDopoConflitto: Duration = .milliseconds(2500)) {
        self.server = server
        self.attesaDopoConflitto = attesaDopoConflitto
        // Dati che si modificano: niente cache (non si deve ripartire da una copia vecchia).
        caricatore = Caricatore<JSONValue>("/api/regole", snake: false, cache: false, server: server)
        super.init()
        osserva(caricatore)
    }

    /// Rilegge le regole. Con modifiche non salvate NON le sovrascrive (prima bastava cambiare scheda e tornare, o il comando
    /// «Aggiorna», per perderle senza avviso): solo `forza` («Annulla le modifiche», o le regole cambiate da un altro dispositivo)
    /// riparte dal server.
    func carica(forza: Bool = false) async {
        await caricatore.ricarica()
        if let d = caricatore.dato, forza || !modificato || !caricato {
            valore = d
            fasce = RegoleLogica.fasce(d)
            caricato = true
            modificato = false
            esito = nil
        }
    }

    // MARK: campi

    func numero(_ percorso: String, _ predefinito: Double = 0) -> Binding<Double> {
        Binding(get: { self.valore.valore(percorso)?.numero ?? predefinito },
                set: { self.valore.imposta(percorso, JSONValue.numero($0)); self.modificato = true })
    }

    func booleano(_ percorso: String, predefinito: Bool = false) -> Binding<Bool> {
        Binding(get: { self.valore.valore(percorso)?.booleano ?? predefinito },
                set: { self.valore.imposta(percorso, .booleano($0)); self.modificato = true })
    }

    func testo(_ percorso: String) -> Binding<String> {
        Binding(get: { self.valore.valore(percorso)?.testo ?? "" },
                set: { self.valore.imposta(percorso, .testo($0)); self.modificato = true })
    }

    /// Tutti i moduli che si possono scegliere: quelli noti più quelli già nelle regole.
    var moduliDisponibili: [String] {
        var tutti = RegoleLogica.tuttiIModuli
        for m in moduliAttivi where !tutti.contains(m) { tutti.append(m) }
        return tutti
    }

    var moduliAttivi: [String] { (valore.valore("moduli")?.elenco ?? []).compactMap(\.testo) }

    func alternaModulo(_ modulo: String) {
        var attivi = moduliAttivi
        if let i = attivi.firstIndex(of: modulo) { attivi.remove(at: i) } else { attivi.append(modulo) }
        valore.imposta("moduli", .lista(attivi.map { JSONValue.testo($0) }))
        modificato = true
    }

    /// Posti fissi per ruolo in panchina: se attivi `panchina.posti` è un oggetto, altrimenti null.
    var postiFissi: Binding<Bool> {
        Binding(get: { if case .oggetto? = self.valore.valore("panchina.posti") { return true }; return false },
                set: { acceso in
                    if acceso {
                        self.valore.imposta("panchina.posti", .oggetto(["P": .intero(2), "D": .intero(3), "C": .intero(3), "A": .intero(3)]))
                    } else {
                        self.valore.imposta("panchina.posti", .nullo)
                    }
                    self.modificato = true
                })
    }

    /// Voto d'ufficio quando manca il sostituto: attivo se `voto_senza_sostituto` non è null.
    var votoUfficioAttivo: Binding<Bool> {
        Binding(get: { self.valore.valore("voto_senza_sostituto")?.numero != nil },
                set: { acceso in
                    self.valore.imposta("voto_senza_sostituto", acceso ? JSONValue.numero(4) : .nullo)
                    self.modificato = true
                })
    }

    // MARK: fasce del modificatore difesa

    /// Scrive nel JSON le fasce modificate (se sono davvero diverse da quelle che ci sono già: così il caricamento non conta come modifica).
    func fasceCambiate(_ nuove: [RegoleLogica.Fascia]) {
        let ordinate = nuove.sorted { $0.media < $1.media }
        guard ordinate != RegoleLogica.fasce(valore) else { return }
        RegoleLogica.scriviFasce(nuove, in: &valore)
        modificato = true
    }

    func aggiungiFascia() {
        let ultima = fasce.sorted { $0.media < $1.media }.last
        fasce.append(RegoleLogica.Fascia(media: min(9, (ultima?.media ?? 6) + 0.5), bonus: (ultima?.bonus ?? 0) + 1))
    }

    func togliFascia(_ id: UUID) {
        fasce.removeAll { $0.id == id }
    }

    /// Il posto della fascia nell'elenco, da 1 (nil se non c'è più): VoiceOver lo legge nel nome dei suoi campi
    /// («Fascia 2, media almeno»). Dopo «Togli» i numeri si rifanno, perché si contano le fasce rimaste.
    func postoFascia(_ id: UUID) -> Int? {
        fasce.firstIndex { $0.id == id }.map { $0 + 1 }
    }

    /// Bonus che darebbero i voti della prova con le fasce attuali.
    var mediaProva: Double { RegoleLogica.mediaDifesa(votiProva) }
    var bonusProva: Double { RegoleLogica.bonusDifesa(media: mediaProva, fasce: fasce) }

    // MARK: importa dal regolamento

    func riconosci() async {
        let testo = testoRegolamento.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !testo.isEmpty else {
            erroreRiconoscimento = Catalogo.Regole.incollaPrimaTesto
            return
        }
        riconoscimentoInCorso = true
        defer { riconoscimentoInCorso = false }
        do {
            riconoscimento = try await server.posta("POST", "/api/regole/riconosci", RichiestaTesto(testo: testo))
            erroreRiconoscimento = nil
        } catch {
            if Task.isCancelled || error is CancellationError { return }
            riconoscimento = nil
            erroreRiconoscimento = error.localizedDescription
        }
    }

    /// Mette nei campi i valori riconosciuti. Non salva: lo fa l'utente con «Salva le regole», dopo aver controllato.
    /// La frase dopo, come la web: `regole.valori_applicati_controlla` (#559).
    func applicaRiconosciute() {
        guard let r = riconoscimento, !r.modifiche.isEmpty else { return }
        valore = RegoleLogica.applica(r.modifiche, a: valore)
        fasce = RegoleLogica.fasce(valore)
        modificato = true
        esito = Catalogo.Regole.valoriApplicatiControlla
        esitoRiuscito = true
        riconoscimento = nil
        Haptics.selezione()
    }

    // MARK: salvataggio

    /// «Salva le regole». Vero se il server le ha salvate: la domanda sulle modifiche non salvate chiude la pagina solo allora.
    /// Un errore (anche il controllo prima di salvare, «Scegli almeno un modulo») va in `esito` con `esitoRiuscito` falso e la
    /// pagina lo mostra sopra la barra «Modifiche non salvate», vicino a «Salva» (#808).
    @discardableResult
    func salva() async -> Bool {
        // un «Salva» mentre un altro è in corso (anche nell'attesa dopo un 412) non parte: la domanda «Salva le regole» arriva qui
        // anche quando la barra ha il pulsante spento
        guard !inCorso else { return false }
        inCorso = true
        defer { inCorso = false }
        do {
            let pronto = try RegoleLogica.preparaPerSalvataggio(valore)
            let nuove: JSONValue = try await server.posta("PUT", "/api/regole", pronto, snake: false)
            valore = nuove
            fasce = RegoleLogica.fasce(nuove)
            modificato = false
            esito = Catalogo.Regole.regoleSalvateConsigli
            esitoRiuscito = true
            Haptics.esito(riuscito: true)
            NotificationCenter.default.post(name: .aggiornaTutto, object: nil)
            return true
        } catch {
            esito = error.localizedDescription
            esitoRiuscito = false
            Haptics.esito(riuscito: false)
            if (error as? ErroreApi)?.eConflitto == true { await ricaricaDopoConflitto(messaggio: error.localizedDescription) }
            return false
        }
    }

    /// 412, regole cambiate da un altro dispositivo: come la web, la frase e, dopo un attimo, i campi ricaricati con le regole del
    /// server; le modifiche non salvate si perdono e la pagina resta aperta (#808; prima la domanda la chiudeva come dopo un
    /// salvataggio riuscito). Intanto `inCorso` tiene fermo «Salva». L'ETag ricordato non deve valere: il trasporto ha già preso
    /// quello della risposta 412, e un nuovo «Salva» passerebbe sopra la versione dell'altro dispositivo senza che si veda. Con
    /// `etagDaRileggere` ogni scrittura riceve di nuovo 412 finché una lettura riuscita non porta l'ETag vero, anche se la rilettura
    /// qui sotto non riesce (come la web, che dopo un 412 tiene l'ETag vecchio).
    private func ricaricaDopoConflitto(messaggio: String) async {
        VersioniRisorse.condivise.imposta(Self.etagDaRileggere, server: server.indirizzo, risorsa: "regole")
        try? await Task.sleep(for: attesaDopoConflitto)
        await carica(forza: true)
        // `carica(forza:)` toglie l'esito: la frase resta da leggere, con i valori nuovi
        esito = messaggio
        esitoRiuscito = false
    }

    func annulla() async { await carica(forza: true) }

    func fermaAttese() {}
}

// MARK: - Vista

/// Un valore numerico con − e + (un Stepper di iOS), con il valore scritto accanto al titolo.
struct RigaStepper: View {
    let titolo: String
    @Binding var valore: Double
    var passo = 0.5
    var minimo = 0.0
    var massimo = 20.0
    var cifre = 1
    var aiuto: String? = nil
    /// Il nome che legge VoiceOver, quando il testo a vista non basta a distinguere la riga (le fasce: «Fascia 2, media almeno»).
    /// Senza, VoiceOver legge il titolo come prima.
    var nomeAccessibile: String? = nil

    var body: some View {
        if let nomeAccessibile {
            campo.accessibilityLabel(nomeAccessibile)
        } else {
            campo
        }
    }

    private var campo: some View {
        Stepper(value: $valore, in: minimo...massimo, step: passo) {
            HStack(alignment: .firstTextBaseline) {
                VStack(alignment: .leading, spacing: 1) {
                    Text(titolo)
                    if let aiuto {
                        Text(aiuto).font(.caption).foregroundStyle(Color.testoSecondario)
                            .fixedSize(horizontal: false, vertical: true)   // le righe d'aiuto lunghe vanno a capo, mai tagliate
                    }
                }
                Spacer(minLength: 8)
                Text(Formato.decimali(valore, cifre: cifre)).monospacedDigit().foregroundStyle(Color.testoSecondario)
            }
        }
        .frame(minHeight: 44)
        .accessibilityValue(Formato.decimali(valore, cifre: cifre))
    }
}

/// Un interruttore con la sua riga d'aiuto sotto, come `interruttore(...)` della web.
struct RigaInterruttore: View {
    let titolo: String
    let aiuto: String
    @Binding var acceso: Bool

    var body: some View {
        Toggle(isOn: $acceso) {
            VStack(alignment: .leading, spacing: 2) {
                Text(titolo)
                Text(aiuto).font(.caption).foregroundStyle(Color.testoSecondario)
            }
        }
        .tint(Color.verde)
        .frame(minHeight: 44)
    }
}

/// Regole della lega: punteggi, modificatore difesa, moduli, panchina, rosa e crediti. Si può anche incollare il regolamento di Leghe.
struct RegoleEditorView: View {
    /// Perché si chiede cosa fare delle modifiche non salvate: «Indietro», o una pagina aperta da fuori (#808).
    private enum Uscita {
        case indietro
        case pagine([PaginaImpostazioni])
    }

    @StateObject private var vm: RegoleEditorViewModel
    /// Le Impostazioni: sanno che le regole hanno modifiche non salvate e quali pagine aspettano la risposta alla domanda.
    private let lega: LegaViewModel
    @Environment(\.dismiss) private var chiudi
    @State private var chiediIndietro = false
    /// Le pagine chieste da fuori («Vedi la rosa» dalla Formazione) che aspettano la risposta (`LegaViewModel.pagineInAttesa`).
    @State private var inAttesa: [PaginaImpostazioni]?

    init(server: any ServerClient, lega: LegaViewModel) {
        _vm = StateObject(wrappedValue: RegoleEditorViewModel(server: server))
        self.lega = lega
    }

    private let ruoli = [("P", "portiere"), ("D", "difensore"), ("C", "centrocampista"), ("A", "attaccante")]
        .map { ($0.0, Catalogo.Regole.golDi(ruolo: $0.1)) }
    // bonus e malus come `bonusRighe` e `malusRighe` della web (`bonus.*` del catalogo comune)
    private let bonus = [("assist", Catalogo.Bonus.assist), ("rigore_segnato", Catalogo.Bonus.rigoreSegnato),
                         ("rigore_parato", Catalogo.Regole.rigoreParatoP), ("portiere_imbattuto", Catalogo.Bonus.portiereImbattuto),
                         ("mvp", Catalogo.Bonus.mvp)]
    private let malus = [("ammonizione", Catalogo.Bonus.ammonizione), ("espulsione", Catalogo.Bonus.espulsione),
                         ("autogol", Catalogo.Bonus.autogol), ("rigore_sbagliato", Catalogo.Bonus.rigoreSbagliato),
                         ("gol_subito_portiere", Catalogo.Bonus.golSubitoPortiere)]
    private let nomiRuolo = ["P": "Portieri", "D": "Difensori", "C": "Centrocampisti", "A": "Attaccanti"]

    var body: some View {
        ZStack {
            Sfondo()
            ScrollViewReader { proxy in
                List {
                    // il titolo intero (testo grande) c'è anche durante il caricamento e con un errore, come nelle altre pagine
                    TitoloNellaPagina()
                    if vm.caricato {
                        nome
                        importa
                        punteggi
                        difesa
                        moduli
                        panchina
                        rosa
                        tempiLega
                        partiteRinviate.id("rinviate")
                        salvataggio
                    } else if let e = vm.caricatore.errore {
                        ErroreVista(messaggio: e) { Task { await vm.carica() } }
                    } else {
                        ScheletroRighe(righe: 6).listRowBackground(Color.clear)
                    }
                }
                .scrollContentBackground(.hidden)
                // fotografia `lega-regole-fondo`: la sezione delle partite rinviate (in fondo alla lista)
                .demoScorriA("rinviate", proxy: proxy, schermate: ["lega-regole"], inFondo: true, pronto: vm.caricato)
            }
        }
        .titoloPagina(Catalogo.Imp.regole)
        .task { await vm.carica() }
        // Modifiche non salvate: una barra in basso lo ricorda (il pulsante «Salva» è in fondo a una lista lunga) e, tornando
        // indietro o aprendo un'altra pagina da fuori, si chiede cosa fare invece di perderle in silenzio. Sull'iPhone e sull'iPad
        // (#808: sull'iPad «‹ Impostazioni» le buttava); un avviso, che si vede intero in mezzo allo schermo su tutti e due.
        .safeAreaInset(edge: .bottom, spacing: 0) {
            // anche senza modifiche, se c'è l'errore dell'ultimo salvataggio: dopo il 412 i campi sono ricaricati, la frase resta
            if vm.caricato && (vm.modificato || erroreSalvataggio != nil) { barraNonSalvate }
        }
        .navigationBarBackButtonHidden(vm.modificato)
        .toolbar {
            if vm.modificato {
                ToolbarItem(placement: .topBarLeading) {
                    Button { chiediIndietro = true } label: { Label("Indietro", systemImage: "chevron.backward") }
                        .accessibilityHint("Le modifiche alle regole non sono salvate: ti chiedo cosa fare")
                }
            }
        }
        .alert("Le modifiche alle regole non sono salvate", isPresented: domandaAperta, presenting: uscita) { perche in
            Button(Catalogo.Regole.salvaRegole) {
                Task {
                    // si esce solo se le regole sono salvate: un errore (anche il 412) lascia la pagina aperta, con l'errore
                    if await vm.salva() { esci(perche) }
                }
            }
            Button("Esci senza salvare", role: .destructive) { esci(perche) }
            Button("Continua a modificare", role: .cancel) {}
        }
        // le Impostazioni sanno se le regole hanno modifiche da salvare, e chiedono qui prima di aprire un'altra pagina
        .onChange(of: vm.modificato, initial: true) { _, modificato in
            if lega.regoleNonSalvate != modificato { lega.regoleNonSalvate = modificato }
        }
        .onReceive(lega.$pagineInAttesa) { inAttesa = $0 }
        // un salvataggio non riuscito si sente anche con VoiceOver (la frase compare sopra la barra, lontano dal fuoco)
        .onChange(of: erroreSalvataggio) { _, errore in
            if let errore { AccessibilityNotification.Announcement(errore).post() }
        }
    }

    /// L'errore dell'ultimo salvataggio (nil se è riuscito o non ce n'è stato uno).
    private var erroreSalvataggio: String? { vm.esitoRiuscito ? nil : vm.esito }

    /// Perché la domanda è aperta (nil = chiusa): una pagina chiesta da fuori vince su «Indietro».
    private var uscita: Uscita? {
        if let inAttesa { return .pagine(inAttesa) }
        return chiediIndietro ? .indietro : nil
    }

    /// La domanda è aperta finché c'è un perché; chiusa (con qualsiasi risposta) si dimenticano «Indietro» e le pagine in attesa.
    /// Le risposte che escono usano il perché di quando la domanda si è aperta (`presenting`), non questo.
    private var domandaAperta: Binding<Bool> {
        Binding(get: { uscita != nil }, set: { aperta in
            guard !aperta else { return }
            chiediIndietro = false
            lega.lasciaPagineInAttesa()
        })
    }

    /// Regole salvate o lasciate: si torna indietro, o si aprono le pagine chieste da fuori.
    private func esci(_ uscita: Uscita) {
        switch uscita {
        case .indietro:
            lega.regoleNonSalvate = false
            chiudi()
        case .pagine(let pagine):
            lega.apriDopoLaDomanda(pagine)
        }
    }

    /// La barra delle modifiche non salvate, con sopra l'errore dell'ultimo salvataggio: vicino a «Salva» si vede sempre, anche in
    /// cima a una lista lunga (prima stava solo in fondo alla lista, #808). Dopo il 412 i campi si ricaricano e le modifiche non ci
    /// sono più: resta solo la frase, senza la barra.
    private var barraNonSalvate: some View {
        VStack(spacing: 6) {
            if let errore = erroreSalvataggio {
                Label(errore, systemImage: "exclamationmark.triangle")
                    .font(.footnote.weight(.medium))
                    .foregroundStyle(.primary)
                    .fixedSize(horizontal: false, vertical: true)   // la frase del 412 è lunga: va a capo, mai tagliata
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.horizontal, 14).padding(.vertical, 8)
                    .vetro(in: RoundedRectangle(cornerRadius: 18, style: .continuous), tinta: Color.attenzione.opacity(0.35))
                    .accessibilityElement(children: .combine)
            }
            if vm.modificato {
                HStack(spacing: 10) {
                    Label("Modifiche non salvate", systemImage: "pencil.circle").font(.subheadline.weight(.semibold))
                    Spacer(minLength: 8)
                    Button {
                        Task { await vm.salva() }
                    } label: {
                        if vm.inCorso { ProgressView() } else { Text("Salva").frame(minWidth: 60) }
                    }
                    .pulsanteVetro(prominente: true)
                    .frame(minHeight: 44)
                    .disabled(vm.inCorso)
                }
                .padding(.horizontal, 16).padding(.vertical, 6)
                .vetro(in: Capsule(), tinta: Color.attenzione.opacity(0.25))
            }
        }
        .padding(.horizontal, Tema.margine).padding(.bottom, 8)
        .accessibilityElement(children: .contain)
    }

    private var nome: some View {
        Section(titolo: Catalogo.Regole.nomeDellaLega) {
            TextField(Catalogo.Regole.miaLega, text: vm.testo("nome_lega")).frame(minHeight: 44)
        }
    }

    // MARK: importa da Leghe

    private var importa: some View {
        Section {
            Text(Catalogo.Regole.legheApriRegolamento)
                .font(.footnote).foregroundStyle(Color.testoSecondario)
            TextEditor(text: $vm.testoRegolamento)
                .frame(minHeight: 96)
                .accessibilityLabel("Testo del regolamento")
            Button { Task { await vm.riconosci() } } label: {
                if vm.riconoscimentoInCorso { ProgressView().frame(maxWidth: .infinity, minHeight: 44) }
                else { Text(Catalogo.Regole.riconosciRegole).frame(maxWidth: .infinity, minHeight: 44) }
            }
            .disabled(vm.riconoscimentoInCorso)
            if let e = vm.erroreRiconoscimento { Text(e).font(.footnote).foregroundStyle(Color.attenzione) }
            if let r = vm.riconoscimento { riconosciute(r) }
        } header: { Text(Catalogo.Regole.importaLeghe).foregroundStyle(Color.testoSecondario) }
    }

    @ViewBuilder
    private func riconosciute(_ r: RiconoscimentoRegole) -> some View {
        if r.modifiche.isEmpty {
            Label(Catalogo.Regole.nonRiconosciutoNessuna,
                  systemImage: "questionmark.circle").font(.footnote).foregroundStyle(Color.testoSecondario)
        } else {
            Text(Catalogo.Regole.riconosciuto).font(.headline)
            ForEach(r.modifiche) { m in
                VStack(alignment: .leading, spacing: 2) {
                    Label("\(m.etichetta): \(RegoleLogica.descrivi(m.valore))", systemImage: "checkmark.circle.fill").font(.subheadline)
                    if let riga = m.riga { Text(Catalogo.Regole.daRiga(r: riga)).font(.caption).foregroundStyle(Color.testoSecondario) }
                }
                .accessibilityElement(children: .combine)
            }
            // le righe da rileggere, come la web (#733): ognuna con la regola da impostare a mano sotto, se il server ne nomina
            if let gruppo = RegolamentoDaControllare(r) {
                DisclosureGroup(gruppo.titolo) {
                    ForEach(gruppo.righe) { riga in
                        VStack(alignment: .leading, spacing: 2) {
                            Text(riga.testo).foregroundStyle(Color.testoSecondario)
                            if let daImpostare = riga.daImpostare { Text(daImpostare) }
                        }
                        .font(.caption)
                        .accessibilityElement(children: .combine)
                    }
                }
            }
            Button { vm.applicaRiconosciute() } label: { Text(Catalogo.Regole.applicaCampi).frame(maxWidth: .infinity, minHeight: 44) }
                .pulsanteVetro(prominente: true)
            Text(Catalogo.Regole.controllaValoriQui).font(.caption).foregroundStyle(Color.testoSecondario)
        }
    }

    // MARK: punteggi

    private var punteggi: some View {
        Group {
            Section(titolo: "Gol") {
                ForEach(ruoli, id: \.0) { r in
                    RigaStepper(titolo: r.1, valore: vm.numero("bonus.gol.\(r.0)"), minimo: 0, massimo: 20)
                }
            }
            Section(titolo: Catalogo.Regole.altriBonus) {
                ForEach(bonus, id: \.0) { b in
                    RigaStepper(titolo: b.1, valore: vm.numero("bonus.\(b.0)"), minimo: 0, massimo: 20)
                }
            }
            Section(titolo: Catalogo.Regole.malus) {
                ForEach(malus, id: \.0) { m in
                    RigaStepper(titolo: m.1, valore: vm.numero("bonus.\(m.0)"), minimo: -20, massimo: 0,
                                aiuto: m.0 == "gol_subito_portiere" ? Catalogo.Regole.perOgniGol : nil)
                }
            }
            Section {
                Picker(Catalogo.Regole.votoPartenza, selection: vm.testo("fonte_voto")) {
                    Text(Catalogo.Regole.vRedazione).tag("redazione")
                    Text(Catalogo.Regole.vStatistico).tag("statistico")
                    Text(Catalogo.Regole.vItalia).tag("italia")
                }
                .pickerStyle(.segmented)
            } header: { Text(Catalogo.Regole.votoPartenza).foregroundStyle(Color.testoSecondario) } footer: {
                Text(Catalogo.Regole.qualeVotoSomma).foregroundStyle(Color.testoSecondario)
            }
        }
    }

    // MARK: modificatore difesa

    private var difesa: some View {
        Section {
            Toggle(Catalogo.Regole.mdAttivo, isOn: vm.booleano("modificatore_difesa.attivo")).tint(Color.verde).frame(minHeight: 44)
            if vm.valore.valore("modificatore_difesa.attivo")?.booleano == true {
                RigaStepper(titolo: Catalogo.Regole.mdMin, valore: vm.numero("modificatore_difesa.min_difensori", 4), passo: 1,
                            minimo: 3, massimo: 6, cifre: 0, aiuto: Catalogo.Regole.mdMinAiuto)
                Text("La media è la somma di portiere + i 3 migliori difensori, divisa per 4. Per ogni fascia raggiunta si prende il bonus più alto raggiunto.")
                    .font(.footnote).foregroundStyle(Color.testoSecondario)
                ForEach($vm.fasce) { $f in
                    // il numero è il posto della riga: dopo «Togli» si rifanno (#460, come la web)
                    let nomi = TestiRegole.nomiFascia(posto: vm.postoFascia(f.id) ?? 1)
                    VStack(alignment: .leading, spacing: 0) {
                        RigaStepper(titolo: Catalogo.Regole.mediaAlmeno, valore: $f.media, passo: 0.25, minimo: 4, massimo: 9, cifre: 2,
                                    nomeAccessibile: nomi.media)
                        RigaStepper(titolo: Catalogo.Regole.bonus, valore: $f.bonus, passo: 0.5, minimo: 0, massimo: 20,
                                    nomeAccessibile: nomi.bonus)
                        Button(role: .destructive) { vm.togliFascia(f.id) } label: { Label("Togli la fascia", systemImage: "trash").labelStyle(.distruttiva).frame(minHeight: 44) }
                            .accessibilityLabel(nomi.togli)
                    }
                }
                Button { vm.aggiungiFascia() } label: { Label(TestiRegole.aggiungiFascia, systemImage: "plus.circle").frame(minHeight: 44) }
                prova
            }
        } header: { Text(Catalogo.Regole.modificatoreDifesa).foregroundStyle(Color.testoSecondario) } footer: { Text(Catalogo.Regole.mdAttivoAiuto).foregroundStyle(Color.testoSecondario) }
    }

    private var prova: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(TestiRegole.prova).font(.subheadline.bold()).accessibilityAddTraits(.isHeader)
            Text(TestiRegole.provaVoti).font(.footnote).foregroundStyle(Color.testoSecondario)
            ForEach(vm.votiProva.indices, id: \.self) { i in
                RigaStepper(titolo: i == 0 ? "Portiere" : "Difensore \(i)", valore: $vm.votiProva[i], minimo: 3, massimo: 10,
                            nomeAccessibile: TestiRegole.nomeVotoProva(indice: i))
            }
            Text(TestiRegole.esitoProva(media: vm.mediaProva, bonus: vm.bonusProva)).font(.headline)
                .accessibilityElement(children: .combine)
        }
    }

    // MARK: moduli, panchina, rosa

    private var moduli: some View {
        Section {
            LazyVGrid(columns: [GridItem(.adaptive(minimum: 76), spacing: 8)], spacing: 8) {
                ForEach(vm.moduliDisponibili, id: \.self) { m in
                    let attivo = vm.moduliAttivi.contains(m)
                    Button { vm.alternaModulo(m) } label: {
                        Text(m).font(.subheadline.bold()).frame(maxWidth: .infinity, minHeight: 44)
                            .background(attivo ? Color.verde.opacity(0.35) : Color.primary.opacity(0.08), in: Capsule())
                            .overlay(Capsule().strokeBorder(attivo ? Color.verde : .clear, lineWidth: 1))
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel("Modulo \(m)")
                    .accessibilityAddTraits(attivo ? .isSelected : [])
                }
            }
        } header: { Text(Catalogo.Regole.moduliAmmessi).foregroundStyle(Color.testoSecondario) } footer: { Text(Catalogo.Regole.quelliChePuoi).foregroundStyle(Color.testoSecondario) }
    }

    private var panchina: some View {
        Section {
            RigaInterruttore(titolo: TestiRegole.postiFissi, aiuto: TestiRegole.postiFissiAiuto, acceso: vm.postiFissi)
            if case .oggetto? = vm.valore.valore("panchina.posti") {
                ForEach(["P", "D", "C", "A"], id: \.self) { r in
                    RigaStepper(titolo: nomiRuolo[r] ?? r, valore: vm.numero("panchina.posti.\(r)"), passo: 1, minimo: 0, massimo: 8, cifre: 0)
                }
            } else {
                RigaStepper(titolo: Catalogo.Regole.giocatoriPanchina, valore: vm.numero("panchina.numero", 7), passo: 1, minimo: 1, massimo: 14, cifre: 0)
            }
            RigaStepper(titolo: Catalogo.Regole.cambiMassimi, valore: vm.numero("panchina.max_sostituzioni", 5), passo: 1, minimo: 0, massimo: 14, cifre: 0)
            Picker(Catalogo.Regole.comeEntranoRiserve, selection: vm.testo("panchina.tipo")) {
                Text(Catalogo.Regole.perRuolo).tag("per_ruolo")
                Text(Catalogo.Regole.libera).tag("libera")
            }
            .pickerStyle(.segmented)
            Text(vm.valore.valore("panchina.tipo")?.testo == "libera"
                 ? Catalogo.Regole.aiutoLibera
                 : Catalogo.Regole.aiutoPerRuolo)
                .font(.footnote).foregroundStyle(Color.testoSecondario)
            RigaInterruttore(titolo: TestiRegole.cambioModulo, aiuto: TestiRegole.cambioModuloAiuto,
                             acceso: vm.booleano("panchina.cambio_modulo"))
            Toggle(Catalogo.Regole.vuSeManca, isOn: vm.votoUfficioAttivo).tint(Color.verde).frame(minHeight: 44)
            if vm.votoUfficioAttivo.wrappedValue {
                RigaStepper(titolo: Catalogo.Regole.vu, valore: vm.numero("voto_senza_sostituto", 4), minimo: 0, massimo: 10)
            }
        } header: { Text(Catalogo.Regole.panchinaSostituzioni).foregroundStyle(Color.testoSecondario) }
    }

    private var rosa: some View {
        Section(titolo: Catalogo.Regole.rosaCrediti) {
            ForEach(["P", "D", "C", "A"], id: \.self) { r in
                RigaStepper(titolo: nomiRuolo[r] ?? r, valore: vm.numero("rosa.\(r)"), passo: 1, minimo: 0, massimo: 20, cifre: 0)
            }
            RigaStepper(titolo: Catalogo.Regole.creditiIniziali, valore: vm.numero("crediti_iniziali"), passo: 10, minimo: 0, massimo: 5000, cifre: 0)
        }
    }

    /// Scadenza della formazione e prima giornata della lega. Se il server non manda i valori valgono 0 minuti e giornata 1.
    private var tempiLega: some View {
        Section {
            RigaStepper(titolo: TestiRegole.scadenza, valore: vm.numero("scadenza_minuti"), passo: 5, minimo: 0,
                        massimo: TempiLega.minutiMassimi, cifre: 0, aiuto: TestiRegole.scadenzaAiuto)
            RigaStepper(titolo: TestiRegole.primaGiornata, valore: vm.numero("prima_giornata_lega", 1), passo: 1, minimo: 1,
                        massimo: TempiLega.primaGiornataMassima, cifre: 0, aiuto: TestiRegole.primaGiornataAiuto)
            RigaInterruttore(titolo: Catalogo.Regole.aggVicini,
                             aiuto: Catalogo.Regole.aggViciniAiuto,
                             acceso: vm.booleano("aggiornamenti_vicino_scadenza", predefinito: true))
        } header: { Text(Catalogo.Regole.tempiDellaLega).foregroundStyle(Color.testoSecondario) } footer: {
            Text(TestiRegole.conPrimaGiornata).foregroundStyle(Color.testoSecondario)
        }
    }

    /// Partite rinviate: cosa fa di solito la lega (solo se il server conosce la regola: con un server vecchio la sezione non c'è).
    @ViewBuilder
    private var partiteRinviate: some View {
        if let modo = vm.valore.valore("partite_rinviate")?.testo {
            Section {
                // una riga per scelta (il selettore a segmenti tagliava «Aspetta il recupero» sull'iPhone)
                Picker(TestiRinvio.sezioneRegole, selection: vm.testo("partite_rinviate")) {
                    ForEach(ModoRinvio.tutti, id: \.self) { m in Text(TestiRinvio.etichetta(m)).tag(m) }
                }
                .pickerStyle(.inline)
                .labelsHidden()
                Text(TestiRinvio.spiega(modo)).font(.footnote).foregroundStyle(Color.testoSecondario)
                    .fixedSize(horizontal: false, vertical: true)
                if modo == ModoRinvio.votoUfficio {
                    RigaStepper(titolo: Catalogo.Regole.rvVoto, valore: vm.numero("voto_ufficio_rinviate", 6), minimo: 0, massimo: 10)
                }
            } header: { Text(TestiRinvio.sezioneRegole).foregroundStyle(Color.testoSecondario) } footer: {
                Text(TestiRinvio.aiutoRegole).foregroundStyle(Color.testoSecondario)
            }
        }
    }

    private var salvataggio: some View {
        Section {
            Button {
                Task { await vm.salva() }
            } label: {
                if vm.inCorso { ProgressView().frame(maxWidth: .infinity, minHeight: 44) }
                else { Label(Catalogo.Regole.salvaRegole, systemImage: "checkmark.circle").frame(maxWidth: .infinity, minHeight: 44) }
            }
            .pulsanteVetro(prominente: true)
            .disabled(vm.inCorso || !vm.modificato)
            Button { Task { await vm.annulla() } } label: { Text(Catalogo.Regole.annullaModifiche).frame(maxWidth: .infinity, minHeight: 44) }
                .disabled(!vm.modificato)
            // qui solo gli esiti riusciti: un errore sta sopra la barra «Modifiche non salvate», vicino a «Salva»
            if let esito = vm.esito, vm.esitoRiuscito { Text(esito).font(.footnote).foregroundStyle(Color.testoSecondario) }
        }
    }
}
