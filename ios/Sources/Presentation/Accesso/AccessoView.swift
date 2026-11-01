import SwiftUI

/// La schermata di accesso (solo se il server ha gli account): Accedi, Registrati (con il codice d'invito) e Recupera (password
/// dimenticata, con il codice di recupero). Il marchio si muove mentre si aspetta il server.
struct SchermataAccesso: View {
    enum Scheda: String, CaseIterable, Identifiable {
        case accedi = "Accedi", registrati = "Registrati", recupera = "Recupera"
        var id: String { rawValue }
    }

    private enum Campo: Hashable { case nome, password, invito, codice, email, codiceEmail }

    @EnvironmentObject private var sessione: SessioneAccount
    @Environment(\.scenePhase) private var fase
    /// Un solo invio alla volta, anche con due tocchi ravvicinati (prima che la sessione faccia in tempo a dire «in corso»).
    @State private var inInvio = false
    /// Dopo un «troppi tentativi» (429): fino a quando aspettare. Il pulsante si riaccende da solo a zero.
    @State private var attesaFinoA: Date?
    @State private var scheda: Scheda
    @State private var nome = ""
    @State private var password = ""
    @State private var invito = ""
    @State private var codice = ""
    @State private var errore: String?
    @State private var messaggio: String?
    /// Il nuovo codice di recupero dopo aver rimesso la password: va salvato prima di proseguire.
    @State private var codiceNuovo: String?
    @State private var avanzate = false
    @State private var email = ""
    @State private var codiceEmail = ""
    /// Registrazione con email a metà: manca il codice arrivato per posta.
    @State private var inAttesa: IscrizioneInAttesa?
    /// Google è acceso sul server? (lo dice il server nel 401; senza, i pulsanti non compaiono)
    @AppStorage(ServiziSociali.chiave) private var socialTesto = ""
    /// Dopo Google, account nuovo: manca la scelta del nome utente.
    @State private var nuovoGoogle: NuovoAccountSocial?
    private var googleAcceso: Bool { ServiziSociali.googleAcceso(socialTesto) }
    @AppStorage(ModalitaRegistrazione.chiave) private var modoTesto = ModalitaRegistrazione.invito.rawValue
    private var modo: ModalitaRegistrazione { ModalitaRegistrazione(rawValue: modoTesto) ?? .invito }
    @FocusState private var focus: Campo?
    @Namespace private var pillole

    init(iniziale: Scheda = .accedi) {
        _scheda = State(initialValue: iniziale)
    }

    // MARK: validazione

    private var problemaNome: String? {
        if nome.isEmpty { return nil }
        if scheda != .accedi, let spazi = RegoleAccount.problemaSpaziNome(nome) { return spazi }
        return RegoleAccount.problemaNome(nome)
    }

    private var nomeOk: Bool { !nome.isEmpty && problemaNome == nil }
    private var problemaPassword: String? {
        guard scheda != .accedi, !password.isEmpty else { return nil }
        return RegoleAccount.problemaPassword(password, nome: nome)
    }

    private var pronto: Bool {
        switch scheda {
        case .accedi:
            return !RegoleAccount.pulisciNome(nome).isEmpty && !password.isEmpty
        case .registrati:
            if inAttesa != nil { return !codiceEmail.trimmingCharacters(in: .whitespaces).isEmpty }
            return nomeOk && RegoleAccount.problemaPassword(password, nome: nome) == nil
                && (!modo.chiedeEmail || RegoleAccount.problemaEmail(email) == nil)
                && (!modo.invitoObbligatorio || !invito.trimmingCharacters(in: .whitespaces).isEmpty)
        case .recupera:
            return nomeOk && !codice.trimmingCharacters(in: .whitespaces).isEmpty
                && RegoleAccount.problemaPassword(password, nome: nome) == nil
        }
    }

    private var frase: String {
        switch scheda {
        case .accedi: return "Bentornato, mister. Entra e guarda la formazione."
        case .registrati:
            if inAttesa != nil { return "Ti abbiamo scritto: inserisci il codice che trovi nella posta." }
            switch modo {
            case .invito: return "Serve un invito per entrare in squadra."
            case .email: return "Serve un invito e la tua email per entrare in squadra."
            case .aperta: return "Crea il tuo account: ti basta un indirizzo email."
            }
        case .recupera: return "Capita. Con il codice di recupero ti rimetti in campo."
        }
    }

    private var titoloPulsante: String {
        switch scheda {
        case .accedi: return "Entra"
        case .registrati: return inAttesa != nil ? "Conferma il codice" : (modo.chiedeEmail ? "Continua" : "Crea l'account")
        case .recupera: return "Cambia la password"
        }
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
                Carta { campi }
                    .animation(Tema.molla, value: scheda)
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
                sezioneGoogle
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
            if nuova == .background { password = ""; codice = "" }
        }
        // Solo per le fotografie (-DEMO_ACCESSO rete | limite | non-valido): prova da sola ad accedere per mostrare l'errore.
        .task {
            guard Demo.accessoAutomatico else { return }
            // Account e password finti: servono solo alla prova locale con dati demo, non esistono su nessun server.
            nome = "mister.rossi"
            password = "Tre-Quarti-Dieci"
            try? await Task.sleep(nanoseconds: 600_000_000)
            await invia()
        }
        .sheet(item: $nuovoGoogle) { n in
            NavigationStack { ScegliNomeGoogleView(nuovo: n, invitoIniziale: invito) }
                .presentationDragIndicator(.visible)
        }
        .sheet(item: Binding(get: { codiceNuovo.map(CodiceDaSalvare.init) }, set: { if $0 == nil { codiceNuovo = nil } })) { c in
            NavigationStack {
                CodiceRecuperoView(codice: c.codice, titolo: "Salva il nuovo codice", testoPulsante: "Torna all'accesso") {
                    codiceNuovo = nil
                    scheda = .accedi
                    password = ""
                    codice = ""
                    messaggio = "Password cambiata. Ora puoi accedere."
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
            Text("SchieraXI")
                .font(.system(.largeTitle, design: .rounded, weight: .semibold))
                .accessibilityHidden(true)
            Text(frase)
                .font(.subheadline).foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
        }
        .padding(.top, 12)
    }

    private var selettore: some View {
        HStack(spacing: 6) {
            ForEach([Scheda.accedi, .registrati]) { s in
                Button {
                    withAnimation(Tema.molla) { scheda = s }
                    errore = nil
                    messaggio = nil
                    password = ""   // passando da una scheda all'altra la password scritta non resta
                } label: {
                    Text(s.rawValue)
                        .font(.subheadline.weight(.semibold))
                        .frame(maxWidth: .infinity, minHeight: Tema.areaTocco)
                        .pillola(attiva: s == scheda, spazio: pillole)
                }
                .buttonStyle(StilePressione())
                .accessibilityAddTraits(s == scheda ? .isSelected : [])
            }
        }
        .sensoryFeedback(.selection, trigger: scheda)
    }

    // MARK: campi

    @ViewBuilder
    private var campi: some View {
        VStack(alignment: .leading, spacing: 14) {
            if scheda == .registrati, let attesa = inAttesa {
                Text("Codice inviato a \(attesa.email).").font(.subheadline).foregroundStyle(.secondary)
                campoTesto("Codice ricevuto per posta", text: $codiceEmail, campo: .codiceEmail, problema: nil)
                    .keyboardType(.numberPad)
                    .submitLabel(.go)
                    .onSubmit { Task { await invia() } }
            } else {
            campoTesto("Nome utente", text: $nome, campo: .nome, problema: scheda == .accedi ? nil : problemaNome)
                .textContentType(.username)
                .textInputAutocapitalization(.never)
                .keyboardType(.asciiCapable)
                .submitLabel(.next)
                .onSubmit { focus = scheda == .recupera ? .codice : .password }
            if scheda == .recupera {
                campoTesto("Codice di recupero", text: $codice, campo: .codice, problema: nil)
                    .textInputAutocapitalization(.characters)
                    .submitLabel(.next)
                    .onSubmit { focus = .password }
            }
            campoPassword(scheda == .recupera ? "Nuova password" : "Password")
            if scheda == .registrati {
                if modo.chiedeEmail {
                    campoTesto("Indirizzo email", text: $email, campo: .email, problema: email.isEmpty ? nil : RegoleAccount.problemaEmail(email))
                        .textContentType(.emailAddress)
                        .textInputAutocapitalization(.never)
                        .keyboardType(.emailAddress)
                        .submitLabel(.next)
                        .onSubmit { focus = modo.chiedeInvito ? .invito : nil }
                }
                if modo.chiedeInvito {
                    campoTesto(modo.invitoObbligatorio ? "Codice d'invito" : "Codice d'invito (facoltativo)", text: $invito, campo: .invito, problema: nil)
                        .textInputAutocapitalization(.characters)
                        .submitLabel(.go)
                        .onSubmit { Task { await invia() } }
                    if modo.invitoObbligatorio {
                        Text("L'invito te lo dà chi ti ha parlato di SchieraXI.")
                            .font(.caption).foregroundStyle(.secondary)
                    }
                }
            }
            if scheda != .accedi {
                Text("Password di almeno \(RegoleAccount.passwordMinima) caratteri, non solo numeri e non troppo facile.")
                    .font(.caption).foregroundStyle(.secondary)
            }
            }
        }
    }

    private func campoTesto(_ titolo: String, text: Binding<String>, campo: Campo, problema: String?) -> some View {
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
            SecureField(titolo, text: $password)
                .textContentType(scheda == .accedi ? .password : .newPassword)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
                .focused($focus, equals: .password)
                .submitLabel(scheda == .registrati ? .next : .go)
                .onSubmit {
                    if scheda == .registrati { focus = modo.chiedeEmail ? .email : .invito } else { Task { await invia() } }
                }
                .padding(12)
                .frame(minHeight: Tema.areaTocco)
                .background(Color.sfondoIncavo, in: RoundedRectangle(cornerRadius: Tema.raggioPiccolo, style: .continuous))
                .accessibilityLabel(titolo)
            if let problemaPassword {
                Text(problemaPassword).font(.caption).foregroundStyle(Color.attenzione)
                    .accessibilityLabel("\(titolo): \(problemaPassword)")
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
                Text(resto > 0 ? "Riprova tra \(resto) s" : (inInvio || sessione.inCorso ? "Un attimo…" : titoloPulsante))
                    .font(.headline)
                    .monospacedDigit()
                    .frame(maxWidth: .infinity, minHeight: Tema.areaTocco)
            }
            .pulsanteVetro(prominente: true)
            .disabled(!pronto || inInvio || sessione.inCorso || resto > 0)
            .sensoryFeedback(trigger: errore) { _, nuovo in nuovo != nil ? .error : nil }
            .onChange(of: resto) { _, nuovo in
                // a zero il conto alla rovescia si ferma e il messaggio di attesa sparisce
                if nuovo == 0, attesaFinoA != nil { attesaFinoA = nil; errore = nil }
            }
        }
    }

    private func invia() async {
        guard pronto, !inInvio, !sessione.inCorso else { return }
        if let fine = attesaFinoA, AttesaRiprova.secondiRimasti(fino: fine) > 0 { return }
        inInvio = true
        defer { inInvio = false }
        let schedaInvio = scheda
        errore = nil
        messaggio = nil
        focus = nil
        do {
            switch scheda {
            case .accedi:
                try await sessione.accedi(nomeUtente: nome, password: password)
            case .registrati:
                if let attesa = inAttesa {
                    try await sessione.confermaIscrizione(attesa, codice: codiceEmail)
                } else if let nuova = try await sessione.registra(nomeUtente: nome, password: password, invito: invito, email: modo.chiedeEmail ? email : nil) {
                    inAttesa = nuova
                    codiceEmail = ""
                    password = ""
                }
            case .recupera:
                let nuovo = try await sessione.recupera(nomeUtente: nome, codice: codice, nuovaPassword: password)
                if let nuovo, !nuovo.isEmpty {
                    codiceNuovo = nuovo
                } else {
                    scheda = .accedi
                    password = ""
                    messaggio = "Password cambiata. Ora puoi accedere."
                }
            }
        } catch {
            // Se nel frattempo si è cambiata scheda, l'errore non c'entra più con quello che si vede.
            guard schedaInvio == scheda else { return }
            if case ErroreApi.troppiTentativi(_, let attesa) = error, let attesa, attesa > 0 {
                attesaFinoA = Date().addingTimeInterval(TimeInterval(min(attesa, 3600)))
            }
            errore = Self.testoErrore(error)
        }
    }

    /// «Continua con Google»: solo se il server lo dichiara, e non mentre si cambia la password o si conferma il codice per posta.
    @ViewBuilder
    private var sezioneGoogle: some View {
        if googleAcceso, scheda != .recupera, inAttesa == nil {
            VStack(spacing: 10) {
                Text("oppure").font(.footnote).foregroundStyle(.secondary).accessibilityHidden(true)
                BottoneGoogle(titolo: "Continua con Google", occupato: inInvio || sessione.inCorso || attesaFinoA != nil) {
                    Task { await continuaConGoogle() }
                }
                if scheda == .registrati {
                    Text(modo.invitoObbligatorio
                         ? "Con Google scegli il nome utente al passo dopo. Il codice d'invito te lo chiedo lì."
                         : "Con Google scegli il nome utente al passo dopo.")
                        .font(.caption).foregroundStyle(.secondary).multilineTextAlignment(.center)
                }
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
            case .rete: return "Non riesco a raggiungere il server. Controlla la connessione e che il server sia raggiungibile, poi riprova."
            case .timeout: return "Il server ci mette troppo a rispondere. Riprova tra poco."
            case .server(let m): return m
            case .indirizzoNonValido: return "L'indirizzo del server non è valido: deve cominciare con https://"
            case .risposta(let codice): return "Il server ha un problema (codice \(codice)). Riprova tra poco."
            default: return e.errorDescription ?? "Qualcosa non va. Riprova."
            }
        }
        return errore.localizedDescription
    }

    // MARK: link e area avanzata

    /// Sotto il pulsante: «Password dimenticata?» (e il ritorno all'accesso). Niente di tecnico in vista.
    @ViewBuilder
    private var linkSecondario: some View {
        switch scheda {
        case .accedi:
            Button("Password dimenticata?") { vai(.recupera) }.frame(minHeight: Tema.areaTocco)
        case .recupera:
            Button("Torna all'accesso") { vai(.accedi) }.frame(minHeight: Tema.areaTocco)
        case .registrati:
            if inAttesa != nil {
                Button("Ricomincia") { inAttesa = nil; codiceEmail = ""; errore = nil }.frame(minHeight: Tema.areaTocco)
            }
        }
    }

    private func vai(_ s: Scheda) {
        withAnimation(Tema.molla) { scheda = s }
        errore = nil
        messaggio = nil
        password = ""
    }

    /// Server e prova con dati di esempio: nascosti, si aprono con un tocco lungo sul marchio (o dall'azione di VoiceOver).
    private var areaAvanzata: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    Text("Solo per chi ha un server proprio. Di norma non serve toccare niente.")
                        .font(.footnote).foregroundStyle(.secondary)
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
                Text(testo).font(.subheadline).foregroundStyle(.secondary)
            }
        }
    }
}
