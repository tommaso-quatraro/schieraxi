import SwiftUI

/// I fogli dell'account («Il tuo account» e «Accessi»).
///
/// Si aprono tutti da UN solo punto, fuori dalla lista delle Impostazioni (`fogliAccount(_:)` sul suo NavigationStack).
/// Prima ogni sezione aveva il suo `.sheet` attaccato alla `Section`: dentro una `List` un modificatore su una `Section`
/// finisce su OGNI sua riga (tanti fogli legati allo stesso stato), e le righe si ridisegnano appena arrivano i dati
/// dell'account (`/api/account/me`, gli accessi, l'email): la riga che teneva il foglio veniva rifatta e il foglio
/// si chiudeva da solo («Cambia password» si apriva e si chiudeva subito, build 219).
enum FoglioAccount: Identifiable, Equatable {
    case password, codice, elimina, email
    /// La password prima di collegare Google; aggiungi una password (chi entra solo con Google).
    case passwordPerGoogle, passwordDaGoogle
    /// Il foglio Condividi del file «Scarica i tuoi dati».
    case condividi(URL)

    var id: String {
        switch self {
        case .password: return "password"
        case .codice: return "codice"
        case .elimina: return "elimina"
        case .email: return "email"
        case .passwordPerGoogle: return "passwordPerGoogle"
        case .passwordDaGoogle: return "passwordDaGoogle"
        case .condividi(let url): return "condividi-" + url.lastPathComponent
        }
    }
}

/// Quale foglio dell'account è aperto e l'ultimo esito da mostrare nelle righe. Vive nelle Impostazioni (non nelle righe
/// della lista), così niente che si ridisegna lo può azzerare.
@MainActor
final class FogliAccount: ObservableObject {
    @Published var aperto: FoglioAccount?
    /// «Password cambiata.», «Email verificata.»... sotto «Il tuo account».
    @Published var messaggio: String?
    /// Esito di collega/scollega Google sotto «Accessi».
    @Published var messaggioAccessi: String?
    @Published var erroreAccessi: String?

    /// Apre un foglio; se ce n'è già uno aperto non fa niente (un doppio tocco non ne apre due).
    func apri(_ foglio: FoglioAccount) {
        guard aperto == nil else { return }
        aperto = foglio
    }

    func collegaGoogle(password: String, _ sessione: SessioneAccount) async {
        erroreAccessi = nil; messaggioAccessi = nil
        do {
            try await sessione.collegaGoogle(password: password, avvio: AvvioWebSistema())
            messaggioAccessi = "Google è collegato."
        } catch let e as ErroreSocial where e.eSoloUnaChiusura {
            // chiusa la finestra: nessun errore da mostrare
        } catch {
            erroreAccessi = SchermataAccesso.testoErrore(error)
        }
    }

    func scollegaGoogle(_ sessione: SessioneAccount) async {
        erroreAccessi = nil; messaggioAccessi = nil
        do {
            try await sessione.scollegaGoogle()
            messaggioAccessi = "Google è scollegato."
        } catch {
            erroreAccessi = SchermataAccesso.testoErrore(error)
        }
    }
}

extension View {
    /// Il punto da cui si aprono i fogli dell'account: va messo FUORI dalla `List` (sul NavigationStack delle Impostazioni).
    func fogliAccount(_ fogli: FogliAccount) -> some View { modifier(PresentaFogliAccount(fogli: fogli)) }
}

private struct PresentaFogliAccount: ViewModifier {
    @ObservedObject var fogli: FogliAccount
    @EnvironmentObject private var sessione: SessioneAccount
    @AppStorage(ServiziSociali.chiave) private var socialTesto = ""

    /// Cambia quando compare «Accessi» (utente noto e Google acceso): solo allora si chiede di nuovo come si entra.
    private var chiaveAccessi: String {
        guard sessione.multiutente, let u = sessione.utente, ServiziSociali.googleAcceso(socialTesto) else { return "" }
        return String(u.id)
    }

    func body(content: Content) -> some View {
        content
            // come si entra (password, Google): una volta, quando «Accessi» compare (prima partiva da ogni riga di «Accessi»)
            .task(id: chiaveAccessi) {
                if !chiaveAccessi.isEmpty { await sessione.aggiornaAccessi() }
            }
            .sheet(item: $fogli.aperto) { foglio in
                vista(foglio)
            }
    }

    @ViewBuilder
    private func vista(_ foglio: FoglioAccount) -> some View {
        switch foglio {
        case .condividi(let url):
            FoglioCondividi(url: url) { fogli.aperto = nil }
                .presentationDetents([.medium, .large])
                .ignoresSafeArea()
        case .passwordPerGoogle:
            NavigationStack {
                FoglioPasswordPerCollegare { password in
                    fogli.aperto = nil
                    Task { await fogli.collegaGoogle(password: password, sessione) }
                }
            }
            .presentationDetents([.medium, .large])
            .presentationDragIndicator(.visible)
        default:
            NavigationStack { contenuto(foglio) }
                .presentationDragIndicator(.visible)
        }
    }

    @ViewBuilder
    private func contenuto(_ foglio: FoglioAccount) -> some View {
        switch foglio {
        case .password:
            FoglioCambiaPassword(nome: sessione.utente?.nomeUtente ?? "") { fogli.messaggio = TestiAccount.passwordCambiataOk }
        case .codice:
            FoglioNuovoCodice()
        case .elimina:
            FoglioElimina()
        case .email:
            FoglioEmail { fogli.messaggio = $0 }
        case .passwordDaGoogle:
            FoglioPasswordDaGoogle()
        case .passwordPerGoogle, .condividi:
            EmptyView()   // aperti da `vista`
        }
    }
}

/// «Il tuo account» nelle Impostazioni, con i testi della web: il nome con «Utente · dal …», l'email (quella di Google se è
/// collegato), cambia la password, codice di recupero, scarica i tuoi dati, elimina l'account ed «Esci» (l'ultima riga, come sulla web).
/// Si vede solo se il server ha gli account (multiutente); con il server di sempre non compare.
/// I fogli si aprono da `fogli` (vedi `FoglioAccount`): qui niente `.sheet`.
struct AccountSezione: View {
    @ObservedObject var fogli: FogliAccount
    @EnvironmentObject private var sessione: SessioneAccount
    @AppStorage(ServiziSociali.chiave) private var socialTesto = ""

    /// La voce dell'email: solo per chi non ha Google collegato. Finché non si sa come entra (Google acceso, accessi non ancora letti) non si mostra.
    private var mostraVoceEmail: Bool {
        let noto = !ServiziSociali.googleAcceso(socialTesto) || sessione.accessi != nil
        return noto && ProfiloAccount.mostraVoceEmail(googleCollegato: sessione.googleCollegato)
    }

    /// «Email confermata: …», «Email da Google: …», «In attesa di conferma: …» o «Nessuna email collegata.», come la web.
    private var rigaEmail: String {
        let daGoogle = sessione.emailOrigine == "google"
        return TestiAccount.rigaEmail(account: daGoogle ? nil : sessione.email,
                                      google: daGoogle ? sessione.email : sessione.accessi?.google?.email,
                                      inAttesa: sessione.emailInAttesa)
    }

    var body: some View {
        if sessione.multiutente, let utente = sessione.utente {
            Section(titolo: "Il tuo account") {
                VStack(alignment: .leading, spacing: 2) {
                    Text(utente.nome).font(.headline)
                    Text(TestiAccount.ruoloEData(ruolo: utente.ruolo, creato: utente.creato))
                        .font(.subheadline).foregroundStyle(Color.testoSecondario)
                }
                .frame(minHeight: Tema.areaTocco)
                .accessibilityElement(children: .combine)
                Text(rigaEmail).font(.subheadline)
                if mostraVoceEmail {
                    Button { fogli.apri(.email) } label: {
                        Label(sessione.email == nil ? "Aggiungi un'email" : "Gestisci l'email", systemImage: "envelope").labelStyle(.voce(.teal)).frame(minHeight: Tema.areaTocco)
                    }
                    .accessibilityHint("Serve a recuperare la password se la dimentichi")
                }
                // chi entra solo con Google non ha una password da cambiare: la aggiunge dal riquadro «Accessi»
                if !sessione.senzaPassword {
                    Button { fogli.apri(.password) } label: {
                        Label(TestiAccount.cambiaPassword, systemImage: "key").labelStyle(.voce(.blue)).frame(minHeight: Tema.areaTocco)
                    }
                    .accessibilityIdentifier("account-cambia-password")
                    Button { fogli.apri(.codice) } label: {
                        Label(TestiAccount.recupero, systemImage: "lifepreserver").labelStyle(.voce(.mint)).frame(minHeight: Tema.areaTocco)
                    }
                    .accessibilityIdentifier("account-codice")
                }
                RigaScaricaDati(fogli: fogli)
                Button(role: .destructive) { fogli.apri(.elimina) } label: {
                    Label(TestiAccount.eliminaTitolo, systemImage: "trash").labelStyle(.voce(.red)).frame(minHeight: Tema.areaTocco)
                }
                .accessibilityIdentifier("account-elimina")
                RigaEsci()
                if let messaggio = fogli.messaggio { Text(messaggio).font(.footnote).foregroundStyle(Color.verde) }
            }
            // niente .sheet qui: su una Section dentro una List finirebbe su ogni riga (vedi `FoglioAccount`)
            AccessiSezione(fogli: fogli)
        }
    }
}

/// «Esci», l'ultima riga di «Il tuo account», come sulla web. Sta dentro la sezione dell'account (che c'è solo con un account:
/// senza account c'è `SessioneMinimaSezione`).
struct RigaEsci: View {
    @EnvironmentObject private var sessione: SessioneAccount
    @State private var chiediEsci = false

    var body: some View {
        Button { chiediEsci = true } label: {
            Label("Esci", systemImage: "rectangle.portrait.and.arrow.right").labelStyle(.voce(.gray)).frame(minHeight: Tema.areaTocco)
        }
        .accessibilityHint("Esci dal tuo account su questo telefono")
        // sul pulsante, non sulla Section (vedi `FoglioAccount`)
        .confirmationDialog("Esci da SchieraXI su questo telefono?", isPresented: $chiediEsci, titleVisibility: .visible) {
            Button("Esci", role: .destructive) { DatiPersonali.pulisci(); Task { await sessione.esci() } }
        } message: {
            Text("I dati salvati su questo telefono vengono cancellati. Quelli sul server restano tuoi.")
        }
    }
}

/// Cambia la password: quella di adesso e la nuova due volte («Ripeti la nuova password»), come la web.
struct FoglioCambiaPassword: View {
    let nome: String
    let fatto: () -> Void
    @EnvironmentObject private var sessione: SessioneAccount
    @Environment(\.dismiss) private var chiudi
    @State private var attuale = ""
    @State private var nuova = ""
    @State private var ripeti = ""
    @State private var errore: String?
    @FocusState private var focus: Int?

    private var problema: String? {
        if nuova.isEmpty { return nil }
        return RegoleAccount.problemaPassword(nuova, nome: nome)
    }

    private var pronto: Bool {
        !attuale.isEmpty && RegoleAccount.problemaPassword(nuova, nome: nome) == nil && nuova == ripeti
    }

    var body: some View {
        Form {
            Section {
                SecureField(TestiAccount.passwordAttuale, text: $attuale)
                    .textContentType(.password)
                    .focused($focus, equals: 0)
                    .submitLabel(.next)
                    .onSubmit { focus = 1 }
                    .frame(minHeight: Tema.areaTocco)
            }
            Section {
                SecureField(TestiAccount.nuovaPassword, text: $nuova)
                    .textContentType(.newPassword)
                    .focused($focus, equals: 1)
                    .submitLabel(.next)
                    .onSubmit { focus = 2 }
                    .frame(minHeight: Tema.areaTocco)
                SecureField(TestiAccount.ripetiPassword, text: $ripeti)
                    .textContentType(.newPassword)
                    .focused($focus, equals: 2)
                    // niente invio dal tasto Invio: la password forte suggerita da iOS o il portachiavi non devono mandare
                    // il modulo da soli. Si cambia solo con il pulsante.
                    .submitLabel(.done)
                    .onSubmit { focus = nil }
                    .frame(minHeight: Tema.areaTocco)
            } footer: { Group {
                VStack(alignment: .leading, spacing: 4) {
                    if let problema { Text(problema).foregroundStyle(Color.attenzione) }
                    if !ripeti.isEmpty && nuova != ripeti { Text(TestiAccount.passwordDiverse).foregroundStyle(Color.attenzione) }
                    Text(TestiAccount.altriScollegati)
                }
            }.foregroundStyle(Color.testoSecondario) }
            if let errore { Section { Text(errore).foregroundStyle(Color.attenzione) } }
            Section {
                Button { Task { await invia() } } label: {
                    Text(sessione.inCorso ? "Un attimo…" : TestiAccount.cambiaPassword).frame(maxWidth: .infinity, minHeight: Tema.areaTocco)
                }
                .disabled(!pronto || sessione.inCorso)
            }
        }
        .navigationTitle(TestiAccount.cambiaPassword)
        .schermoProtetto()
        .navigationBarTitleDisplayMode(.inline)
        .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Annulla") { chiudi() } } }
    }

    private func invia() async {
        guard pronto else { return }
        do {
            try await sessione.cambiaPassword(attuale: attuale, nuova: nuova)
            fatto()
            chiudi()
        } catch {
            errore = SchermataAccesso.testoErrore(error)
        }
    }
}

/// Un nuovo codice di recupero (il vecchio non vale più): serve la password; poi il codice si mostra una volta sola.
struct FoglioNuovoCodice: View {
    @EnvironmentObject private var sessione: SessioneAccount
    @Environment(\.dismiss) private var chiudi
    @State private var password = ""
    @State private var codice: String?
    @State private var errore: String?

    var body: some View {
        Group {
            if let codice {
                CodiceRecuperoView(codice: codice, titolo: "Salva il nuovo codice", testoPulsante: "Fatto") { chiudi() }
            } else {
                Form {
                    Section {
                        SecureField(TestiAccount.laTuaPassword, text: $password)
                            .textContentType(.password)
                            .submitLabel(.go)
                            .onSubmit { Task { await crea() } }
                            .frame(minHeight: Tema.areaTocco)
                    } header: {
                        Text(TestiAccount.recuperoSpiega).foregroundStyle(Color.testoSecondario).textCase(nil)
                    }
                    if let errore { Section { Text(errore).foregroundStyle(Color.attenzione) } }
                    Section {
                        Button { Task { await crea() } } label: {
                            Text(sessione.inCorso ? "Un attimo…" : TestiAccount.nuovoCodice).frame(maxWidth: .infinity, minHeight: Tema.areaTocco)
                        }
                        .disabled(password.isEmpty || sessione.inCorso)
                    }
                }
            }
        }
        .navigationTitle(TestiAccount.recupero)
        .schermoProtetto()
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .cancellationAction) { if codice == nil { Button("Annulla") { chiudi() } } }
        }
        .interactiveDismissDisabled(codice != nil)
    }

    private func crea() async {
        guard !password.isEmpty else { return }
        do {
            codice = try await sessione.nuovoCodiceRecupero(password: password)
            password = ""
        } catch {
            errore = SchermataAccesso.testoErrore(error)
        }
    }
}

/// Elimina l'account e tutti i suoi dati: password e una conferma esplicita (come il `confirm` della web). Non si può annullare.
struct FoglioElimina: View {
    @EnvironmentObject private var sessione: SessioneAccount
    @Environment(\.dismiss) private var chiudi
    @State private var password = ""
    @State private var chiediConferma = false
    @State private var riconfermato = false
    @State private var errore: String?

    var body: some View {
        Form {
            Section {
                Text(LocalizedStringKey(TestiAccount.eliminaAvviso))
                    .font(.subheadline)
                    .foregroundStyle(Color.attenzione)
            }
            if sessione.senzaPassword { RigaRiconferma(confermato: $riconfermato) }
            if !sessione.senzaPassword {
                Section {
                    SecureField(TestiAccount.laTuaPassword, text: $password)
                        .textContentType(.password)
                        .frame(minHeight: Tema.areaTocco)
                }
            }
            if let errore { Section { Text(errore).foregroundStyle(Color.attenzione) } }
            Section {
                Button(role: .destructive) { chiediConferma = true } label: {
                    Text(sessione.inCorso ? "Un attimo…" : TestiAccount.elimina).frame(maxWidth: .infinity, minHeight: Tema.areaTocco)
                }
                .disabled((sessione.senzaPassword ? !riconfermato : password.isEmpty) || sessione.inCorso)
                // sul pulsante, non sulla Section (vedi `FoglioAccount`)
                .confirmationDialog(TestiAccount.eliminaConferma, isPresented: $chiediConferma, titleVisibility: .visible) {
                    Button(TestiAccount.elimina, role: .destructive) { Task { await elimina() } }
                }
            }
        }
        .navigationTitle(TestiAccount.eliminaTitolo)
        .schermoProtetto()
        .navigationBarTitleDisplayMode(.inline)
        .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Annulla") { chiudi() } } }
    }

    private func elimina() async {
        do {
            try await sessione.elimina(password: password)
        } catch {
            if case ErroreApi.codificato("serve_riconferma", _) = error { riconfermato = false }
            errore = SchermataAccesso.testoErrore(error)
        }
    }
}

/// Email dell'account (facoltativa): serve per recuperare la password. Si aggiunge con la password, si verifica con un codice
/// ricevuto per email, si toglie con la password.
struct FoglioEmail: View {
    let fatto: (String) -> Void
    @EnvironmentObject private var sessione: SessioneAccount
    @Environment(\.dismiss) private var chiudi
    @State private var indirizzo = ""
    /// Il secondo passo: l'indirizzo è deciso, manca la conferma con la password.
    @State private var indirizzoScelto: String?
    @State private var password = ""
    @State private var codice = ""
    @State private var errore: String?
    @State private var codiceInviato = false
    @State private var riconfermato = false

    /// Manca la conferma: la password (o, per chi entra solo con Google, la riconferma).
    private var senzaConferma: Bool { sessione.senzaPassword ? !riconfermato : password.isEmpty }

    var body: some View {
        Form {
            if sessione.senzaPassword { RigaRiconferma(confermato: $riconfermato) }
            if let email = sessione.email {
                Section {
                    Text(TestiAccount.rigaEmail(account: email, google: nil, inAttesa: nil))
                } footer: {
                    Text(TestiAccount.emailSpiega).foregroundStyle(Color.testoSecondario)
                }
                Section {
                    if !sessione.senzaPassword {
                        SecureField(TestiAccount.laTuaPassword, text: $password)
                            .textContentType(.password)
                            .frame(minHeight: Tema.areaTocco)
                    }
                    Button(role: .destructive) { Task { await togli() } } label: {
                        Text(sessione.inCorso ? "Un attimo…" : TestiAccount.emailTogli).frame(maxWidth: .infinity, minHeight: Tema.areaTocco)
                    }
                    .disabled(senzaConferma || sessione.inCorso)
                }
            } else {
                if codiceInviato || sessione.emailInAttesa != nil {
                    Section {
                        TextField(TestiAccount.emailCodice, text: $codice)
                            .keyboardType(.numberPad)
                            .textContentType(.oneTimeCode)
                            .frame(minHeight: Tema.areaTocco)
                        Button { Task { await conferma() } } label: {
                            Text(sessione.inCorso ? "Un attimo…" : TestiAccount.emailConferma).frame(maxWidth: .infinity, minHeight: Tema.areaTocco)
                        }
                        .disabled(codice.trimmingCharacters(in: .whitespaces).isEmpty || sessione.inCorso)
                    } header: {
                        Text(TestiAccount.emailAttesa(sessione.emailInAttesa ?? indirizzoScelto ?? "")).foregroundStyle(Color.testoSecondario).textCase(nil)
                    } footer: {
                        if codiceInviato { Text(TestiAccount.emailInviato).foregroundStyle(Color.verde) }
                    }
                }
                // Due passi: prima l'indirizzo, poi la password. Un campo email accanto a un campo password è per iOS un modulo
                // di accesso: il riempimento automatico ci scriveva da solo nome utente e password salvati.
                if let scelto = indirizzoScelto {
                    Section {
                        RigaValore(titolo: "Indirizzo", valore: scelto)
                        if !sessione.senzaPassword {
                            SecureField(TestiAccount.laTuaPassword, text: $password)
                                .textContentType(.password)
                                .submitLabel(.send)
                                .onSubmit { Task { await aggiungi() } }
                                .frame(minHeight: Tema.areaTocco)
                        }
                        Button { Task { await aggiungi() } } label: {
                            Text(sessione.inCorso ? "Un attimo…" : TestiAccount.emailInvia).frame(maxWidth: .infinity, minHeight: Tema.areaTocco)
                        }
                        .disabled(senzaConferma || sessione.inCorso)
                        Button("Cambia indirizzo") { indirizzoScelto = nil; password = "" }
                            .frame(maxWidth: .infinity, minHeight: Tema.areaTocco)
                    } footer: {
                        if !sessione.senzaPassword { Text(TestiAccount.emailServePassword).foregroundStyle(Color.testoSecondario) }
                    }
                } else {
                    Section {
                        TextField(TestiAccount.emailNuova, text: $indirizzo)
                            .keyboardType(.emailAddress)
                            .textContentType(.emailAddress)
                            .textInputAutocapitalization(.never)
                            .autocorrectionDisabled()
                            .submitLabel(.next)
                            .onSubmit { avanti() }
                            .frame(minHeight: Tema.areaTocco)
                        Button("Avanti") { avanti() }
                            .frame(maxWidth: .infinity, minHeight: Tema.areaTocco)
                            .disabled(RegoleAccount.problemaEmail(indirizzo) != nil)
                    } footer: {
                        Text(TestiAccount.emailSpiega).foregroundStyle(Color.testoSecondario)
                    }
                }
            }
            if let errore { Section { Text(errore).foregroundStyle(Color.attenzione) } }
        }
        .navigationTitle(TestiAccount.email)
        .schermoProtetto()
        .navigationBarTitleDisplayMode(.inline)
        .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Chiudi") { chiudi() } } }
    }

    private func avanti() {
        let pulito = indirizzo.trimmingCharacters(in: .whitespacesAndNewlines)
        guard RegoleAccount.problemaEmail(pulito) == nil else { return }
        indirizzoScelto = pulito
    }

    private func aggiungi() async {
        guard let scelto = indirizzoScelto, !senzaConferma, !sessione.inCorso else { return }
        do {
            try await sessione.aggiungiEmail(scelto, password: password)
            password = ""
            errore = nil
            codiceInviato = true
        } catch {
            if case ErroreApi.codificato("serve_riconferma", _) = error { riconfermato = false }
            errore = SchermataAccesso.testoErrore(error)
        }
    }

    private func conferma() async {
        do {
            try await sessione.confermaEmail(codice: codice)
            fatto(TestiAccount.emailConfermataOk)
            chiudi()
        } catch {
            errore = SchermataAccesso.testoErrore(error)
        }
    }

    private func togli() async {
        do {
            try await sessione.togliEmail(password: password)
            fatto(TestiAccount.emailToltaOk)
            chiudi()
        } catch {
            if case ErroreApi.codificato("serve_riconferma", _) = error { riconfermato = false }
            errore = SchermataAccesso.testoErrore(error)
        }
    }
}

/// «Scarica i tuoi dati»: una riga discreta subito prima di «Elimina l'account». Scarica il file dal server, lo salva nella
/// cartella temporanea e apre il foglio Condividi (Salva in File, AirDrop, Mail...). Nessun ripristino da qui.
/// Il foglio Condividi si apre da `fogli` (fuori dalla lista), non da questa riga.
struct RigaScaricaDati: View {
    @ObservedObject var fogli: FogliAccount
    @State private var inCorso = false
    @State private var errore: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            VStack(alignment: .leading, spacing: 4) {
                Label(TestiAccount.datiTitolo, systemImage: "square.and.arrow.down").labelStyle(.voce(.indigo))
                Text(TestiAccount.datiSpiega)
                    .font(.footnote)
                    .foregroundStyle(Color.testoSecondario)
                    .fixedSize(horizontal: false, vertical: true)
            }
            .accessibilityElement(children: .combine)
            Button { Task { await scarica() } } label: {
                HStack(spacing: 8) {
                    if inCorso { ProgressView().accessibilityHidden(true) }
                    Text(inCorso ? "Preparo il file…" : TestiAccount.datiScarica)
                }
                .frame(minHeight: Tema.areaTocco)
            }
            .buttonStyle(.bordered)
            .disabled(inCorso)
            .accessibilityHint("Scarica un file con i tuoi dati e apre il menu Condividi per salvarlo")
            if let errore {
                Text(errore)
                    .font(.footnote)
                    .foregroundStyle(Color.attenzione)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .padding(.vertical, 4)
    }

    private func scarica() async {
        guard !inCorso else { return }
        inCorso = true
        errore = nil
        defer { inCorso = false }
        do {
            let url = try await DatiPersonali.scarica(server: ServerCorrente.condiviso)
            fogli.apri(.condividi(url))
        } catch {
            let testo = DatiPersonali.testoErrore(error)
            errore = testo
            AccessibilityNotification.Announcement(testo).post()
        }
    }
}

/// Il foglio Condividi standard di iOS (UIActivityViewController) dentro un foglio di SwiftUI: va bene anche su iPad,
/// dove così non serve un punto d'ancoraggio per il popover.
struct FoglioCondividi: UIViewControllerRepresentable {
    let url: URL
    let fine: () -> Void

    func makeUIViewController(context: Context) -> UIActivityViewController {
        let vc = UIActivityViewController(activityItems: [url], applicationActivities: nil)
        vc.completionWithItemsHandler = { _, _, _, _ in fine() }
        return vc
    }

    func updateUIViewController(_ uiViewController: UIActivityViewController, context: Context) {}
}

#Preview("Scarica i tuoi dati") {
    List { Section(titolo: "Il tuo account") { RigaScaricaDati(fogli: FogliAccount()) } }
}
