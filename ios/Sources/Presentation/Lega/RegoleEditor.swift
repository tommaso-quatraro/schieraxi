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
    @Published var modificato = false {
        // un campo cambiato dopo un salvataggio non riuscito: l'errore di prima non vale più e se ne va (#808)
        didSet { if modificato, esito != nil, !esitoRiuscito { esito = nil; esitoRiuscito = true } }
    }
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
    /// I limiti dei numeri (#889): quelli del server (`/limiti-regole.json`, lo stesso file della web) appena arrivano; prima, e con
    /// un server di prima che non ha il file, quelli di riserva, uguali al file.
    @Published private(set) var limiti = LimitiRegole.riserva
    /// Il file dei limiti si chiede una volta sola per pagina, dopo le regole.
    private var limitiChiesti = false

    /// Dopo un 412, quanto si aspetta prima di ricaricare i campi con le regole del server: la frase si legge mentre si vedono ancora
    /// i valori scritti, come la web (che ricarica la pagina dopo 2,5 secondi). I test la mettono a zero.
    private let attesaDopoConflitto: Duration
    /// L'attesa dopo un 412 e la rilettura che la segue: si fermano quando la pagina si chiude (`fermaAttese`).
    private var ricaricaDopo412: Task<Void, Never>?
    /// L'ETag (la versione) dell'ultima risposta arrivata a `caricatore`, e quello delle regole da cui vengono i campi. Sono diversi
    /// quando una rilettura arriva mentre ci sono modifiche non salvate: i campi restano quelli vecchi, e con loro la loro versione.
    private var etagLetto: String?
    private var etagDeiCampi: String?

    init(server: any ServerClient, attesaDopoConflitto: Duration = .milliseconds(2500)) {
        self.server = server
        self.attesaDopoConflitto = attesaDopoConflitto
        // Dati che si modificano: niente cache (non si deve ripartire da una copia vecchia). Il comando «Aggiorna» passa da `carica`,
        // non dal caricatore da solo: così una rilettura tiene insieme i campi e la loro versione.
        caricatore = Caricatore<JSONValue>("/api/regole", snake: false, cache: false, ascolta: false, server: server)
        super.init()
        osserva(caricatore)
        alComandoAggiorna { [weak self] in await self?.carica() }
    }

    /// Rilegge le regole. Con modifiche non salvate NON le sovrascrive (prima bastava cambiare scheda e tornare, o il comando
    /// «Aggiorna», per perderle senza avviso): solo `forza` («Annulla le modifiche») riparte dal server. Senza modifiche si
    /// ricaricano i campi e la loro versione insieme; con modifiche i campi tengono la versione vecchia, e il «Salva» che la manda
    /// riceve 412 se nel frattempo le regole sono cambiate altrove (#808: prima passava e la modifica della web spariva).
    func carica(forza: Bool = false) async {
        _ = await rileggi()
        if let d = caricatore.dato, forza || !modificato || !caricato { applica(d) }
        if caricato { await leggiLimiti() }
    }

    /// Chiede i limiti dei numeri al server, una volta e dopo le regole: la pagina non li aspetta e, con gli account, l'accesso è
    /// già provato dalle regole. Se non arrivano (un server di prima, la rete) restano quelli di riserva, uguali al file.
    private func leggiLimiti() async {
        guard !limitiChiesti else { return }
        limitiChiesti = true
        guard let dati = try? await server.grezzo("/limiti-regole.json"), let letti = LimitiRegole(dati: dati) else { return }
        limiti = letti
    }

    /// Chiede le regole al server; vero se è arrivata una risposta nuova, e allora `etagLetto` è la sua versione (il trasporto l'ha
    /// appena ricordata in `VersioniRisorse`).
    private func rileggi() async -> Bool {
        let prima = caricatore.risposte
        await caricatore.ricarica()
        guard caricatore.risposte > prima else { return false }
        etagLetto = VersioniRisorse.condivise.leggi(server: server.indirizzo, risorsa: Self.risorsa)
        return true
    }

    /// I campi ripartono dalle regole lette dal server (l'ultima risposta), con la loro versione. L'esito di prima se ne va solo se
    /// le regole cambiano: la rilettura che segue un salvataggio riuscito (comando «Aggiorna» mandato da `salva`) lascia la frase.
    private func applica(_ d: JSONValue) {
        if d != valore { esito = nil }
        valore = d
        fasce = RegoleLogica.fasce(d)
        caricato = true
        modificato = false
        etagDeiCampi = etagLetto
    }

    /// La risorsa delle regole in `VersioniRisorse` (anche `/api/regole/rinvio` scrive qui).
    private static let risorsa = "regole"

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

    /// Una fascia mezzo punto sopra l'ultima, con un punto di bonus in più, senza andare oltre i limiti del server (come la web).
    func aggiungiFascia() {
        let ultima = fasce.sorted { $0.media < $1.media }.last
        let media = limiti.intervallo(CampiRegole.limiteMediaFascia), bonus = limiti.intervallo(CampiRegole.limiteBonusFascia)
        fasce.append(RegoleLogica.Fascia(media: min(media.upperBound, (ultima?.media ?? 6) + 0.5),
                                         bonus: min(bonus.upperBound, (ultima?.bonus ?? 0) + 1)))
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
            // prima i campi, come la web (#889): senza numero, con i decimali in un campo intero, fuori dai limiti del server
            if let problema = CampiRegole.problema(valore, fasce: fasce, limiti: limiti) { throw ErroreRegole.messaggio(problema) }
            let pronto = try RegoleLogica.preparaPerSalvataggio(valore)
            // Il «Salva» manda la versione da cui vengono i campi, non quella dell'ultima lettura: se intanto le regole sono cambiate
            // altrove (la web, il riquadro dei rinvii) e i campi sono rimasti quelli vecchi, il server risponde 412 invece di
            // scriverci sopra. Anche dopo un 412 il trasporto ricorda la versione nuova, ma i campi non l'hanno ancora vista.
            if let etagDeiCampi {
                VersioniRisorse.condivise.imposta(etagDeiCampi, server: server.indirizzo, risorsa: Self.risorsa)
            }
            let nuove: JSONValue = try await server.posta("PUT", "/api/regole", pronto, snake: false)
            valore = nuove
            fasce = RegoleLogica.fasce(nuove)
            modificato = false
            esito = Catalogo.Regole.regoleSalvateConsigli
            esitoRiuscito = true
            // la versione appena salvata, dalla risposta
            etagLetto = VersioniRisorse.condivise.leggi(server: server.indirizzo, risorsa: Self.risorsa)
            etagDeiCampi = etagLetto
            Haptics.esito(riuscito: true)
            NotificationCenter.default.post(name: .aggiornaTutto, object: nil)
            return true
        } catch {
            esito = error.localizedDescription
            esitoRiuscito = false
            Haptics.esito(riuscito: false)
            if (error as? ErroreApi)?.eConflitto == true {
                let messaggio = error.localizedDescription
                let attesa = Task { await self.ricaricaDopoConflitto(messaggio: messaggio) }
                ricaricaDopo412 = attesa
                await attesa.value
                ricaricaDopo412 = nil
            }
            return false
        }
    }

    /// 412, regole cambiate da un altro dispositivo: come la web, la frase e, dopo un attimo, i campi ricaricati con le regole del
    /// server; le modifiche non salvate si perdono e la pagina resta aperta (#808; prima la domanda la chiudeva come dopo un
    /// salvataggio riuscito). Intanto `inCorso` tiene fermo «Salva». Se la rilettura non riesce, i campi restano come sono e si dice
    /// perché: il prossimo «Salva» manda di nuovo la versione dei campi e riceve di nuovo 412. Chiusa la pagina non si fa niente.
    private func ricaricaDopoConflitto(messaggio: String) async {
        try? await Task.sleep(for: attesaDopoConflitto)
        guard !Task.isCancelled else { return }
        let arrivate = await rileggi()
        guard !Task.isCancelled else { return }
        if arrivate, let d = caricatore.dato {
            applica(d)
            esito = messaggio              // `applica` toglie l'esito: la frase resta da leggere, con i valori nuovi
        } else {
            esito = caricatore.errore ?? messaggio
        }
        esitoRiuscito = false
    }

    func annulla() async { await carica(forza: true) }

    /// La pagina si è chiusa: l'attesa dopo un 412 e la rilettura non servono più.
    func fermaAttese() {
        ricaricaDopo412?.cancel()
    }
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
                // fotografia `lega-regole-anteprima`: l'anteprima del regolamento della demo, da «Riconosci le regole» in giù
                .demoScorriA("riconosci", proxy: proxy, schermate: ["lega-regole-anteprima"], pronto: vm.riconoscimento != nil)
                // fotografia `lega-regole-non-applicato`: «Non applicato» in cima, per vedere come va a capo il perché (testo grande)
                .demoScorriA("non-applicato", proxy: proxy, schermate: ["lega-regole-non-applicato"], pronto: vm.riconoscimento != nil)
            }
        }
        .titoloPagina(Catalogo.Imp.regole)
        .task { await vm.carica() }
        // solo per le fotografie `lega-regole-anteprima` e `lega-regole-non-applicato`: il regolamento della demo incollato e
        // riconosciuto, come dopo il tocco
        .task(id: vm.caricato) {
            guard vm.caricato, Demo.attivo, let foto = Demo.foto, ["lega-regole-anteprima", "lega-regole-non-applicato"].contains(foto),
                  vm.riconoscimento == nil else { return }
            vm.testoRegolamento = LegaDemo.regolamentoIncollato
            await vm.riconosci()
        }
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
        // chiusa la pagina (non un'altra scheda davanti: allora le Regole restano tra le pagine aperte), l'attesa dopo un 412 si ferma
        .onDisappear {
            if !lega.percorso.contains(.regole) { vm.fermaAttese() }
        }
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
            .id("riconosci")
            if let e = vm.erroreRiconoscimento { Text(e).font(.footnote).foregroundStyle(Color.attenzione) }
            if let r = vm.riconoscimento { riconosciute(r) }
        } header: { Text(Catalogo.Regole.importaLeghe).foregroundStyle(Color.testoSecondario) }
    }

    /// L'anteprima dopo «Riconosci le regole», come la web (#889): «Riconosciuto», «Non applicato» con il perché del server, le righe
    /// da controllare a mano e «Applica ai campi» solo se c'è qualcosa da applicare.
    @ViewBuilder
    private func riconosciute(_ r: RiconoscimentoRegole) -> some View {
        let anteprima = AnteprimaRegolamento(r)
        if anteprima.vuota {
            Label(Catalogo.Regole.nonRiconosciutoNessuna,
                  systemImage: "questionmark.circle").font(.footnote).foregroundStyle(Color.testoSecondario)
        } else {
            if !anteprima.riconosciuti.isEmpty {
                Text(Catalogo.Regole.riconosciuto).font(.headline).accessibilityAddTraits(.isHeader)
                ForEach(anteprima.riconosciuti) { v in
                    VStack(alignment: .leading, spacing: 2) {
                        Label(v.testo, systemImage: "checkmark.circle.fill").font(.subheadline)
                        if let riga = v.daRiga { Text(riga).font(.caption).foregroundStyle(Color.testoSecondario) }
                    }
                    .accessibilityElement(children: .combine)
                }
            }
            // i valori letti che con le regole di adesso non si salvano così come sono: il perché è del server
            if !anteprima.nonApplicati.isEmpty {
                Text(Catalogo.Regole.nonApplicato).font(.headline).accessibilityAddTraits(.isHeader)
                    .id("non-applicato")
                ForEach(anteprima.nonApplicati) { v in
                    VStack(alignment: .leading, spacing: 2) {
                        Label {
                            Text(v.testo).font(.subheadline.weight(.semibold))
                        } icon: {
                            Image(systemName: "exclamationmark.triangle.fill").foregroundStyle(Color.attenzione)
                        }
                        if let motivo = v.motivo { Text(motivo).font(.subheadline) }
                        if let riga = v.daRiga { Text(riga).font(.caption).foregroundStyle(Color.testoSecondario) }
                    }
                    .accessibilityElement(children: .combine)
                }
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
            if anteprima.siApplica {
                Button { vm.applicaRiconosciute() } label: { Text(Catalogo.Regole.applicaCampi).frame(maxWidth: .infinity, minHeight: 44) }
                    .pulsanteVetro(prominente: true)
                Text(Catalogo.Regole.controllaValoriQui).font(.caption).foregroundStyle(Color.testoSecondario)
            }
        }
    }

    // MARK: punteggi

    /// Una riga con − e + per un campo delle regole, con i limiti del server (`vm.limiti`, #889).
    private func riga(_ campo: CampiRegole.Campo, predefinito: Double = 0, passo: Double = 0.5, aiuto: String? = nil) -> RigaStepper {
        let limite = vm.limiti.intervallo(campo.percorso)
        return RigaStepper(titolo: campo.nome, valore: vm.numero(campo.percorso, predefinito), passo: passo,
                           minimo: limite.lowerBound, massimo: limite.upperBound, cifre: campo.intero ? 0 : 1, aiuto: aiuto)
    }

    private var punteggi: some View {
        Group {
            Section(titolo: "Gol") {
                ForEach(CampiRegole.gol, id: \.percorso) { riga($0) }
            }
            Section(titolo: Catalogo.Regole.altriBonus) {
                ForEach(CampiRegole.bonus, id: \.percorso) { riga($0) }
            }
            Section(titolo: Catalogo.Regole.malus) {
                ForEach(CampiRegole.malus, id: \.percorso) { m in
                    riga(m, aiuto: m.percorso == "bonus.gol_subito_portiere" ? Catalogo.Regole.perOgniGol : nil)
                }
            }
            Section {
                Picker(Catalogo.Regole.votoPartenza, selection: vm.testo("fonte_voto")) {
                    Text(Catalogo.Regole.vRedazione).tag("redazione")
                    Text(Catalogo.Regole.vStatistico).tag("statistico")
                    Text(Catalogo.Regole.vItalia).tag("italia")
                }
                .pickerStyle(.segmented)
                .segmentiDellaPagina()   // sull'iPad largo al massimo come quelli della web (#896)
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
                riga(CampiRegole.minDifensori, predefinito: 4, passo: 1, aiuto: Catalogo.Regole.mdMinAiuto)
                Text("La media è la somma di portiere + i 3 migliori difensori, divisa per 4. Per ogni fascia raggiunta si prende il bonus più alto raggiunto.")
                    .font(.footnote).foregroundStyle(Color.testoSecondario)
                ForEach($vm.fasce) { $f in
                    // il numero è il posto della riga: dopo «Togli» si rifanno (#460, come la web)
                    let nomi = TestiRegole.nomiFascia(posto: vm.postoFascia(f.id) ?? 1)
                    VStack(alignment: .leading, spacing: 0) {
                        RigaStepper(titolo: Catalogo.Regole.mediaAlmeno, valore: $f.media, passo: 0.25, minimo: limiteMedia.lowerBound,
                                    massimo: limiteMedia.upperBound, cifre: 2, nomeAccessibile: nomi.media)
                        RigaStepper(titolo: Catalogo.Regole.bonus, valore: $f.bonus, passo: 0.5, minimo: limiteBonus.lowerBound,
                                    massimo: limiteBonus.upperBound, nomeAccessibile: nomi.bonus)
                        Button(role: .destructive) { vm.togliFascia(f.id) } label: { Label("Togli la fascia", systemImage: "trash").labelStyle(.distruttiva).frame(minHeight: 44) }
                            .accessibilityLabel(nomi.togli)
                    }
                }
                Button { vm.aggiungiFascia() } label: { Label(TestiRegole.aggiungiFascia, systemImage: "plus.circle").frame(minHeight: 44) }
                prova
            }
        } header: { Text(Catalogo.Regole.modificatoreDifesa).foregroundStyle(Color.testoSecondario) } footer: { Text(Catalogo.Regole.mdAttivoAiuto).foregroundStyle(Color.testoSecondario) }
    }

    /// I limiti della media e del bonus di una fascia del modificatore (`vm.limiti`, #889).
    private var limiteMedia: ClosedRange<Double> { vm.limiti.intervallo(CampiRegole.limiteMediaFascia) }
    private var limiteBonus: ClosedRange<Double> { vm.limiti.intervallo(CampiRegole.limiteBonusFascia) }

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
                ForEach(CampiRegole.posti, id: \.percorso) { riga($0, passo: 1) }
            } else {
                riga(CampiRegole.giocatoriPanchina, predefinito: 7, passo: 1)
            }
            riga(CampiRegole.cambi, predefinito: 5, passo: 1)
            Picker(Catalogo.Regole.comeEntranoRiserve, selection: vm.testo("panchina.tipo")) {
                Text(Catalogo.Regole.perRuolo).tag("per_ruolo")
                Text(Catalogo.Regole.libera).tag("libera")
            }
            .pickerStyle(.segmented)
            .segmentiDellaPagina()
            Text(vm.valore.valore("panchina.tipo")?.testo == "libera"
                 ? Catalogo.Regole.aiutoLibera
                 : Catalogo.Regole.aiutoPerRuolo)
                .font(.footnote).foregroundStyle(Color.testoSecondario)
            RigaInterruttore(titolo: TestiRegole.cambioModulo, aiuto: TestiRegole.cambioModuloAiuto,
                             acceso: vm.booleano("panchina.cambio_modulo"))
            Toggle(Catalogo.Regole.vuSeManca, isOn: vm.votoUfficioAttivo).tint(Color.verde).frame(minHeight: 44)
            if vm.votoUfficioAttivo.wrappedValue {
                riga(CampiRegole.votoSenzaSostituto, predefinito: 4)
            }
        } header: { Text(Catalogo.Regole.panchinaSostituzioni).foregroundStyle(Color.testoSecondario) }
    }

    private var rosa: some View {
        Section(titolo: Catalogo.Regole.rosaCrediti) {
            ForEach(CampiRegole.rosa, id: \.percorso) { riga($0, passo: 1) }
            riga(CampiRegole.crediti, passo: 10)
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
                    riga(CampiRegole.votoRinviate, predefinito: 6)
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
