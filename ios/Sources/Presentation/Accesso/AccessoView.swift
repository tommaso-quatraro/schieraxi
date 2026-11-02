import SwiftUI

/// La schermata di accesso (solo se il server ha gli account), uguale alla web: due schede (Accedi, Registrati) e il collegamento
/// «Password dimenticata» sotto il modulo (con l'email o con il codice di recupero). Passi, testi e controlli stanno in
/// `ModuloAccesso` (logica pura, provata dai test). Il marchio si muove mentre si aspetta il server.
struct SchermataAccesso: View {
    /// `recupera` non è una scheda in vista: si apre da «Password dimenticata».
    enum Scheda: String, CaseIterable, Identifiable {
        case accedi = "Accedi", registrati = "Registrati", recupera = "Password dimenticata"
        var id: String { rawValue }
    }

    @EnvironmentObject private var sessione: SessioneAccount
    @Environment(\.scenePhase) private var fase
    @Environment(\.dynamicTypeSize) private var testo
    /// Un solo invio alla volta, anche con due tocchi ravvicinati (prima che la sessione faccia in tempo a dire «in corso»).
    @State private var inInvio = false
    /// Dopo un «troppi tentativi» (429): fino a quando aspettare. Il pulsante si riaccende da solo a zero.
    @State private var attesaFinoA: Date?
    @State private var modulo: ModuloAccesso
    @State private var errore: String?
    @State private var messaggio: String?
    /// Il nuovo codice di recupero dopo aver rimesso la password: va salvato prima di proseguire.
    @State private var codiceNuovo: CodiceDaSalvare?
    @State private var avanzate = false
    /// Google è acceso sul server? (lo dice il server nel 401; senza, i pulsanti non compaiono)
    @AppStorage(ServiziSociali.chiave) private var socialTesto = ""
    /// Dopo Google, account nuovo: manca la scelta del nome utente.
    @State private var nuovoGoogle: NuovoAccountSocial?
    private var googleAcceso: Bool { ServiziSociali.googleAcceso(socialTesto) }
    @AppStorage(ModalitaRegistrazione.chiave) private var modoTesto = ModalitaRegistrazione.invito.rawValue
    private var modo: ModalitaRegistrazione { ModalitaRegistrazione(rawValue: modoTesto) ?? .invito }
    /// La posta è accesa sul server? (lo dice il server nel 401; spenta: niente email con l'invito né recupero con l'email)
    @AppStorage(PostaServer.chiave) private var postaAccesa = true
    @FocusState private var focus: ModuloAccesso.Campo?
    @Namespace private var pillole
    @Namespace private var pilloleMetodo

    init(iniziale: Scheda = .accedi) {
        var m = ModuloAccesso(scheda: iniziale)
        if iniziale == .recupera {
            m.metodo = MetodoRecupero.iniziale(ModalitaRegistrazione.salvato, postaAccesa: PostaServer.accesa())
        }
        _modulo = State(initialValue: m)
    }

    // MARK: corpo

    var body: some View {
        ScrollView {
            VStack(spacing: 20) {
                testata
                if sessione.serverSpostato {
                    Label(MigrazioneServer.messaggio, systemImage: "arrow.triangle.2.circlepath")
                        .font(.subheadline.weight(.medium)).foregroundStyle(Color.attenzione)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .accessibilityElement(children: .combine)
                }
                selettore
                sezioneGoogle
                if modulo.mostraMetodi(postaAccesa: postaAccesa) { selettoreMetodo }
                Carta { campi }
                    .animation(Tema.molla, value: modulo.passo)
                if let messaggio {
                    Label(messaggio, systemImage: "checkmark.circle.fill")
                        .font(.subheadline).foregroundStyle(Color.verde)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .accessibilityElement(children: .combine)
                }
                if let errore {
                    Label(errore, systemImage: "exclamationmark.triangle.fill")
                        .font(.subheadline).foregroundStyle(Color.attenzione)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .accessibilityElement(children: .combine)
                        .transition(.opacity)
                }
                pulsante
                linkSecondario
            }
            .frame(maxWidth: 520)
            .padding(Tema.margine)
            .frame(maxWidth: .infinity)
        }
        .scrollDismissesKeyboard(.interactively)
        .background(Sfondo())
        .animation(Tema.morbida, value: errore)
        .schermoProtetto()
        .sheet(isPresented: $avanzate) { areaAvanzata }
        // Con l'app in secondo piano (o al ritorno) password e codici scritti si cancellano: non restano in memoria dei campi.
        .onChange(of: fase) { _, nuova in
            if nuova == .background { modulo.password = ""; modulo.codice = ""; modulo.codiceEmail = "" }
        }
        // Solo per le fotografie (-DEMO_ACCESSO rete | limite | non-valido): prova da sola ad accedere per mostrare l'errore.
        .task {
            guard Demo.accessoAutomatico else { return }
            // Account finto, solo per la prova locale con dati demo (non esiste su nessun server). La password non è scritta nel codice:
            // si compone al momento con caratteri a caso e il finto server della demo risponde comunque allo stesso modo.
            modulo.nome = "mister.rossi"
            modulo.password = String(UUID().uuidString.lowercased().filter { $0 != "-" }.prefix(20))
            try? await Task.sleep(nanoseconds: 600_000_000)
            await invia()
        }
        .sheet(item: $nuovoGoogle) { n in
            NavigationStack { ScegliNomeGoogleView(nuovo: n, invitoIniziale: modulo.invito) }
                .presentationDragIndicator(.visible)
        }
        .sheet(item: $codiceNuovo) { c in
            NavigationStack {
                CodiceRecuperoView(codice: c.codice, titolo: TestiAccesso.passwordCambiata, testoPulsante: TestiAccesso.vaiAllAccesso) {
                    codiceNuovo = nil
                    tornaDopoIlCambio()
                }
            }
            .interactiveDismissDisabled()
        }
    }

    private var testata: some View {
        VStack(spacing: 10) {
            Marchio(lato: 96, muove: sessione.inCorso)
                .onLongPressGesture(minimumDuration: 1.2) { avanzate = true }
                .accessibilityAction(named: "Impostazioni avanzate del server") { avanzate = true }
            NomeSchieraXIGrande()
        }
        .padding(.top, 12)
    }

    private var selettore: some View {
        HStack(spacing: 6) {
            ForEach([Scheda.accedi, .registrati]) { s in
                Button {
                    vai(s)
                } label: {
                    Text(s.rawValue)
                        .font(.subheadline.weight(.semibold))
                        .frame(maxWidth: .infinity, minHeight: Tema.areaTocco)
                        .pillola(attiva: s == modulo.scheda, spazio: pillole)
                }
                .buttonStyle(StilePressione())
                .accessibilityAddTraits(s == modulo.scheda ? .isSelected : [])
                // «Accedi» è anche il pulsante del modulo: i test cercano la scheda per identificativo
                .accessibilityIdentifier(s == .accedi ? "scheda-accedi" : "scheda-registrati")
            }
        }
        .sensoryFeedback(.selection, trigger: modulo.scheda)
    }

    /// «Con l'email» / «Con il codice di recupero»: in colonna con il testo molto grande.
    private var selettoreMetodo: some View {
        let disposizione = testo.isAccessibilitySize ? AnyLayout(VStackLayout(spacing: 6)) : AnyLayout(HStackLayout(spacing: 6))
        return disposizione {
            ForEach(MetodoRecupero.allCases) { m in
                Button {
                    withAnimation(Tema.molla) { modulo.metodo = m }
                    errore = nil
                    messaggio = nil
                } label: {
                    Text(m.titolo)
                        .font(.subheadline.weight(.semibold))
                        .multilineTextAlignment(.center)
                        .padding(.horizontal, 8)
                        .frame(maxWidth: .infinity, minHeight: Tema.areaTocco)
                        .pillola(attiva: m == modulo.metodo, spazio: pilloleMetodo)
                }
                .buttonStyle(StilePressione())
                .accessibilityAddTraits(m == modulo.metodo ? .isSelected : [])
            }
        }
        .sensoryFeedback(.selection, trigger: modulo.metodo)
    }

    // MARK: campi

    private var campi: some View {
        let elenco = modulo.campi(modo, postaAccesa: postaAccesa)
        return VStack(alignment: .leading, spacing: 14) {
            if let spiegazione = modulo.spiegazione(modo) {
                Text(spiegazione).font(.subheadline).foregroundStyle(Color.testoSecondario)
                    .fixedSize(horizontal: false, vertical: true)
            }
            ForEach(elenco, id: \.self) { c in
                campo(c)
                    .submitLabel(c == elenco.last ? .go : .next)
                    .onSubmit { dopoInvioDa(c, elenco) }
            }
            if modulo.passo == .registra { terminiEPrivacy }
        }
    }

    /// Invio dalla tastiera: al campo dopo; dall'ultimo si manda il modulo.
    private func dopoInvioDa(_ c: ModuloAccesso.Campo, _ elenco: [ModuloAccesso.Campo]) {
        if let i = elenco.firstIndex(of: c), i + 1 < elenco.count {
            focus = elenco[i + 1]
        } else {
            Task { await invia() }
        }
    }

    @ViewBuilder
    private func campo(_ c: ModuloAccesso.Campo) -> some View {
        switch c {
        case .nome:
            campoTesto(ModuloAccesso.etichettaNome, text: $modulo.nome, campo: c, problema: modulo.problemaNome)
                .textContentType(.username)
                .textInputAutocapitalization(.never)
                .keyboardType(.asciiCapable)
        case .invito:
            campoTesto(ModuloAccesso.etichettaInvito, text: $modulo.invito, campo: c, problema: nil)
                .textInputAutocapitalization(.characters)
        case .email:
            campoTesto(modulo.etichettaEmail(modo), text: $modulo.email, campo: c, problema: modulo.problemaEmail)
                .textContentType(.emailAddress)
                .textInputAutocapitalization(.never)
                .keyboardType(.emailAddress)
        case .codice:
            campoTesto(ModuloAccesso.etichettaCodice, text: $modulo.codice, campo: c, problema: nil)
                .textInputAutocapitalization(.characters)
        case .codiceEmail:
            campoTesto(ModuloAccesso.etichettaCodiceEmail, text: $modulo.codiceEmail, campo: c, problema: nil)
                .textContentType(.oneTimeCode)
                .keyboardType(.numberPad)
        case .password:
            campoPassword(modulo.etichettaPassword)
        }
    }

    /// Una sola casella per Privacy, Termini d'uso ed età minima (come la web: al server va `accetto_termini`), e le due pagine.
    private var terminiEPrivacy: some View {
        VStack(alignment: .leading, spacing: 4) {
            Toggle(TestiAccesso.letto, isOn: $modulo.accetto)
                .frame(minHeight: Tema.areaTocco)
            if let url = InformazioniLegali.indirizzo(.privacy, server: IndirizzoServer.attuale) {
                Link(destination: url) { Text(TestiAccesso.leggiPrivacy).frame(minHeight: Tema.areaTocco).contentShape(Rectangle()) }
            }
            if let url = InformazioniLegali.indirizzo(.termini, server: IndirizzoServer.attuale) {
                Link(destination: url) { Text(TestiAccesso.leggiTermini).frame(minHeight: Tema.areaTocco).contentShape(Rectangle()) }
            }
        }
        .font(.subheadline)
    }

    private func campoTesto(_ titolo: String, text: Binding<String>, campo: ModuloAccesso.Campo, problema: String?) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            TextField(titolo, text: text)
                .autocorrectionDisabled()
                .focused($focus, equals: campo)
                .padding(12)
                .frame(minHeight: Tema.areaTocco)
                .background(Color.sfondoIncavo, in: RoundedRectangle(cornerRadius: Tema.raggioPiccolo, style: .continuous))
                .accessibilityLabel(titolo)
            if let problema {
                Text(problema).font(.caption).foregroundStyle(Color.attenzione)
                    .accessibilityLabel("\(titolo): \(problema)")
            }
        }
    }

    private func campoPassword(_ titolo: String) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            SecureField(titolo, text: $modulo.password)
                .textContentType(modulo.passwordNuova ? .newPassword : .password)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
                .focused($focus, equals: .password)
                .padding(12)
                .frame(minHeight: Tema.areaTocco)
                .background(Color.sfondoIncavo, in: RoundedRectangle(cornerRadius: Tema.raggioPiccolo, style: .continuous))
                .accessibilityLabel(titolo)
            if let problema = modulo.problemaPassword {
                Text(problema).font(.caption).foregroundStyle(Color.attenzione)
                    .accessibilityLabel("\(titolo): \(problema)")
            }
        }
    }

    // MARK: azione

    private var pulsante: some View {
        TimelineView(.periodic(from: Date(), by: 1)) { contesto in
            let resto = attesaFinoA.map { AttesaRiprova.secondiRimasti(fino: $0, adesso: contesto.date) } ?? 0
            Button {
                Task { await invia() }
            } label: {
                Text(resto > 0 ? "Riprova tra \(resto) s" : (inInvio || sessione.inCorso ? "Un attimo…" : modulo.titoloPulsante))
                    .font(.headline)
                    .monospacedDigit()
                    .frame(maxWidth: .infinity, minHeight: Tema.areaTocco)
            }
            .pulsanteVetro(prominente: true)
            .accessibilityIdentifier("accesso-invia")
            .disabled(!modulo.pronto(modo, postaAccesa: postaAccesa) || inInvio || sessione.inCorso || resto > 0)
            .sensoryFeedback(trigger: errore) { _, nuovo in nuovo != nil ? .error : nil }
            .onChange(of: resto) { _, nuovo in
                // a zero il conto alla rovescia si ferma e il messaggio di attesa sparisce
                if nuovo == 0, attesaFinoA != nil { attesaFinoA = nil; errore = nil }
            }
        }
    }

    private func invia() async {
        guard !inInvio, !sessione.inCorso else { return }
        if let fine = attesaFinoA, AttesaRiprova.secondiRimasti(fino: fine) > 0 { return }
        switch modulo.primaDellInvio(modo, postaAccesa: postaAccesa) {
        case .manda: break
        case .avvisa(let problema):
            // controllo sul telefono, per primo come la web (la casella non spuntata): la password scritta resta
            messaggio = nil
            errore = problema
            return
        case .aspetta:
            return
        }
        inInvio = true
        defer { inInvio = false }
        let passoInvio = modulo.passo
        errore = nil
        messaggio = nil
        focus = nil
        do {
            switch passoInvio {
            case .accedi:
                try await sessione.accedi(nomeUtente: modulo.nome, password: modulo.password)
            case .registra:
                if let nuova = try await sessione.registra(nomeUtente: modulo.nome, password: modulo.password, invito: modulo.invito,
                                                           email: modulo.emailDaMandare(modo, postaAccesa: postaAccesa),
                                                           accettoTermini: modulo.accetto) {
                    modulo.iscrizione = nuova
                    modulo.codiceEmail = ""
                    modulo.password = ""
                }
            case .verificaIscrizione:
                guard let attesa = modulo.iscrizione else { return }
                try await sessione.confermaIscrizione(attesa, codice: modulo.codiceEmail)
            case .recuperoCodice:
                // la password è cambiata: il nuovo codice si mostra anche se nel frattempo si è andati altrove
                let nuovo = try await sessione.recupera(nomeUtente: modulo.nome, codice: modulo.codice, nuovaPassword: modulo.password)
                codiceNuovo = CodiceDaSalvare(codice: nuovo)
            case .recuperoEmail:
                let indirizzo = modulo.email.trimmingCharacters(in: .whitespacesAndNewlines)
                try await sessione.chiediCodiceEmail(indirizzo)
                // se nel frattempo si è cambiato passo (Torna all'accesso), il secondo passo non si apre da solo
                if modulo.codiceInviato(a: indirizzo, daPasso: passoInvio) { messaggio = TestiAccesso.codiceInviato }
            case .recuperoEmailCodice:
                guard let indirizzo = modulo.emailRecupero else { return }
                let nuovo = try await sessione.recuperaConEmail(email: indirizzo, codice: modulo.codiceEmail,
                                                                nuovaPassword: modulo.password)
                codiceNuovo = CodiceDaSalvare(codice: nuovo)
            }
        } catch {
            // Se nel frattempo si è cambiato passo, l'errore non c'entra più con quello che si vede.
            guard passoInvio == modulo.passo else { return }
            if case ErroreApi.troppiTentativi(_, let attesa) = error, let attesa, attesa > 0 {
                attesaFinoA = Date().addingTimeInterval(TimeInterval(min(attesa, 3600)))
            }
            errore = Self.testoErrore(error)
        }
    }

    /// Dopo il recupero, salvato il nuovo codice: di nuovo all'accesso (codici e passi del recupero si dimenticano in `vai`).
    private func tornaDopoIlCambio() {
        vai(.accedi)
        messaggio = TestiAccesso.passwordCambiataAccedi
    }

    /// «Continua con Google» sopra il modulo, come la web: solo se il server lo dichiara, e non nel recupero o mentre si
    /// conferma il codice arrivato per posta.
    @ViewBuilder
    private var sezioneGoogle: some View {
        if googleAcceso, modulo.passo == .accedi || modulo.passo == .registra {
            VStack(spacing: 10) {
                BottoneGoogle(titolo: "Continua con Google", occupato: inInvio || sessione.inCorso || attesaFinoA != nil) {
                    Task { await continuaConGoogle() }
                }
                Text("oppure").font(.footnote).foregroundStyle(Color.testoSecondario).accessibilityHidden(true)
            }
        }
    }

    private func continuaConGoogle() async {
        guard !inInvio, !sessione.inCorso else { return }
        inInvio = true
        defer { inInvio = false }
        errore = nil
        messaggio = nil
        focus = nil
        do {
            if case .nuovoAccount(let nuovo) = try await sessione.accediConGoogle(avvio: AvvioWebSistema()) { nuovoGoogle = nuovo }
        } catch let e as ErroreSocial where e.eSoloUnaChiusura {
            // ha chiuso la finestra di Google: non è un errore
        } catch {
            errore = Self.testoErrore(error)
        }
    }

    /// Un messaggio che dice cosa è successo e come rimediare.
    static func testoErrore(_ errore: Error) -> String {
        if let e = errore as? ErroreApi {
            switch e {
            case .rete: return ErroreApi.testoNonRaggiungibile
            case .timeout: return "SchieraXI ci mette troppo a rispondere. Riprova tra poco."
            case .server(let m): return m
            case .indirizzoNonValido: return "L'indirizzo del server non è valido: deve cominciare con https://"
            case .risposta(let codice): return ErroreApi.testoRisposta(codice)
            default: return e.errorDescription ?? "Qualcosa non va. Riprova."
            }
        }
        return errore.localizedDescription
    }

    // MARK: link e area avanzata

    /// Sotto il pulsante: «Password dimenticata» (e il ritorno all'accesso). Niente di tecnico in vista.
    @ViewBuilder
    private var linkSecondario: some View {
        switch modulo.passo {
        case .accedi:
            Button(TestiAccesso.passwordDimenticata) { vai(.recupera) }.frame(minHeight: Tema.areaTocco)
        case .recuperoCodice, .recuperoEmail, .recuperoEmailCodice:
            Button(TestiAccesso.tornaAllAccesso) { vai(.accedi) }.frame(minHeight: Tema.areaTocco)
        case .verificaIscrizione:
            Button("Ricomincia") { modulo.iscrizione = nil; modulo.codiceEmail = ""; errore = nil }.frame(minHeight: Tema.areaTocco)
        case .registra:
            EmptyView()
        }
    }

    private func vai(_ s: Scheda) {
        withAnimation(Tema.molla) { modulo.vai(s, modo: modo, postaAccesa: postaAccesa) }
        errore = nil
        messaggio = nil
    }

    /// Server e prova con dati di esempio: nascosti, si aprono con un tocco lungo sul marchio (o dall'azione di VoiceOver).
    private var areaAvanzata: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    Text("Solo per chi ha un server proprio. Di norma non serve toccare niente.")
                        .font(.footnote).foregroundStyle(Color.testoSecondario)
                    Carta {
                        VStack(alignment: .leading, spacing: 10) {
                            Label("Indirizzo del server", systemImage: "server.rack").font(.headline)
                            ProvaServerView(dopoProva: {
                                errore = nil
                                await sessione.cambiaServer()
                            })
                        }
                    }
                    Button {
                        avanzate = false
                        ProvaEsempio.avvia()
                    } label: {
                        Label("Prova con dati di esempio", systemImage: "play.circle").frame(maxWidth: .infinity, minHeight: Tema.areaTocco)
                    }
                    .buttonStyle(.bordered)
                    .accessibilityHint("Apre l'app con una lega inventata, senza account e senza rete")
                }
                .padding(Tema.margine)
            }
            .background(Sfondo())
            .navigationTitle("Avanzate")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Fine") { avanzate = false } } }
        }
        .tint(Color.verde)
    }
}

/// Per mostrare il codice in un foglio (`sheet(item:)`).
struct CodiceDaSalvare: Identifiable, Equatable {
    let codice: String
    var id: String { codice }
}

/// La schermata di attesa quando l'app parte e deve ancora sapere se serve l'accesso: il marchio che si muove.
struct SchermataAttesa: View {
    var testo = "Un attimo, mister…"
    var body: some View {
        ZStack {
            Sfondo()
            VStack(spacing: 14) {
                Marchio(lato: 88, muove: true)
                Text(testo).font(.subheadline).foregroundStyle(Color.testoSecondario)
            }
        }
    }
}
