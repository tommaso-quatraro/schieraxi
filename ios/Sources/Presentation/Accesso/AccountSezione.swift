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
            FoglioCambiaPassword(nome: sessione.utente?.nomeUtente ?? "") { fogli.messaggio = "Password cambiata." }
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

/// «Il tuo account» nelle Impostazioni: un solo nome, l'email (quella di Google se è collegato), cambia password,
/// codice per recuperare l'accesso, elimina l'account. «Esci» sta in fondo alle Impostazioni (`EsciSezione`).
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

    var body: some View {
        if sessione.multiutente, let utente = sessione.utente {
            Section("Il tuo account") {
                RigaValore(titolo: "Nome", valore: utente.nome)
                RigaValore(titolo: "Email", valore: (sessione.emailMostrata ?? "Nessuna") + (sessione.emailDaGoogle && sessione.emailMostrata != nil ? " (da Google)" : ""))
                if mostraVoceEmail {
                    Button { fogli.apri(.email) } label: {
                        Label(sessione.email == nil ? "Aggiungi un'email" : "Gestisci l'email", systemImage: "envelope").labelStyle(.voce(.teal)).frame(minHeight: Tema.areaTocco)
                    }
                    .accessibilityHint("Serve a recuperare la password se la dimentichi")
                }
                // chi entra solo con Google non ha una password da cambiare: la aggiunge dal riquadro «Accessi»
                if !sessione.senzaPassword {
                    Button { fogli.apri(.password) } label: {
                        Label("Cambia password", systemImage: "key").labelStyle(.voce(.blue)).frame(minHeight: Tema.areaTocco)
                    }
                    Button { fogli.apri(.codice) } label: {
                        Label("Nuovo codice per recuperare l'accesso", systemImage: "lifepreserver").labelStyle(.voce(.mint)).frame(minHeight: Tema.areaTocco)
                    }
                }
                RigaScaricaDati(fogli: fogli)
                Button(role: .destructive) { fogli.apri(.elimina) } label: {
                    Label("Elimina l'account", systemImage: "trash").labelStyle(.voce(.red)).frame(minHeight: Tema.areaTocco)
                }
                if let messaggio = fogli.messaggio { Text(messaggio).font(.footnote).foregroundStyle(Color.verde) }
            }
            // niente .sheet qui: su una Section dentro una List finirebbe su ogni riga (vedi `FoglioAccount`)
            AccessiSezione(fogli: fogli)
        }
    }
}

/// «Esci», l'ultima voce delle Impostazioni: solo con un account (senza account c'è `SessioneMinimaSezione`).
struct EsciSezione: View {
    @EnvironmentObject private var sessione: SessioneAccount
    @State private var chiediEsci = false

    var body: some View {
        if sessione.multiutente, sessione.utente != nil {
            Section {
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
    }
}

/// Cambia la password: quella di adesso, la nuova (due volte).
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
            Section("Password di adesso") {
                SecureField("Password attuale", text: $attuale)
                    .textContentType(.password)
                    .focused($focus, equals: 0)
                    .submitLabel(.next)
                    .onSubmit { focus = 1 }
                    .frame(minHeight: Tema.areaTocco)
            }
            Section {
                SecureField("Nuova password", text: $nuova)
                    .textContentType(.newPassword)
                    .focused($focus, equals: 1)
                    .submitLabel(.next)
                    .onSubmit { focus = 2 }
                    .frame(minHeight: Tema.areaTocco)
                SecureField("Ripeti la nuova password", text: $ripeti)
                    .textContentType(.newPassword)
                    .focused($focus, equals: 2)
                    // niente invio dal tasto Invio: la password forte suggerita da iOS o il portachiavi non devono mandare
                    // il modulo da soli. Si cambia solo con il pulsante.
                    .submitLabel(.done)
                    .onSubmit { focus = nil }
                    .frame(minHeight: Tema.areaTocco)
            } header: {
                Text("Password nuova")
            } footer: {
                VStack(alignment: .leading, spacing: 4) {
                    if let problema { Text(problema).foregroundStyle(Color.attenzione) }
                    if !ripeti.isEmpty && nuova != ripeti { Text("Le due password non coincidono.").foregroundStyle(Color.attenzione) }
                    Text("Almeno \(RegoleAccount.passwordMinima) caratteri, non solo numeri e non troppo facile.")
                }
            }
            if let errore { Section { Text(errore).foregroundStyle(Color.attenzione) } }
            Section {
                Button { Task { await invia() } } label: {
                    Text(sessione.inCorso ? "Un attimo…" : "Cambia la password").frame(maxWidth: .infinity, minHeight: Tema.areaTocco)
                }
                .disabled(!pronto || sessione.inCorso)
            }
        }
        .navigationTitle("Cambia password")
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
                        SecureField("Password", text: $password)
                            .textContentType(.password)
                            .submitLabel(.go)
                            .onSubmit { Task { await crea() } }
                            .frame(minHeight: Tema.areaTocco)
                    } header: {
                        Text("Conferma con la password")
                    } footer: {
                        Text("Il codice di prima non vale più. Quello nuovo lo vedi una volta sola: scrivilo e tienilo al sicuro.")
                    }
                    if let errore { Section { Text(errore).foregroundStyle(Color.attenzione) } }
                    Section {
                        Button { Task { await crea() } } label: {
                            Text(sessione.inCorso ? "Un attimo…" : "Crea un nuovo codice").frame(maxWidth: .infinity, minHeight: Tema.areaTocco)
                        }
                        .disabled(password.isEmpty || sessione.inCorso)
                    }
                }
            }
        }
        .navigationTitle("Codice di recupero")
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

/// Elimina l'account e tutti i suoi dati: password e una conferma esplicita. Non si può annullare.
struct FoglioElimina: View {
    @EnvironmentObject private var sessione: SessioneAccount
    @Environment(\.dismiss) private var chiudi
    @State private var password = ""
    @State private var capito = false
    @State private var riconfermato = false
    @State private var errore: String?

    var body: some View {
        Form {
            Section {
                Text("Cancella il tuo account e TUTTI i tuoi dati: rose, regole, scelte, immagini, avvisi. Non si può annullare.")
                    .font(.subheadline)
            } footer: {
                Text("Vuoi tenerne una copia? Prima chiudi qui e usa «Scarica i tuoi dati», subito sopra «Elimina l'account».")
            }
            if sessione.senzaPassword { RigaRiconferma(confermato: $riconfermato) }
            Section(sessione.senzaPassword ? "Ultima conferma" : "Conferma con la password") {
                if !sessione.senzaPassword {
                    SecureField("Password", text: $password)
                        .textContentType(.password)
                        .frame(minHeight: Tema.areaTocco)
                }
                Toggle("Ho capito: cancella tutto", isOn: $capito)
                    .frame(minHeight: Tema.areaTocco)
            }
            if let errore { Section { Text(errore).foregroundStyle(Color.attenzione) } }
            Section {
                Button(role: .destructive) { Task { await elimina() } } label: {
                    Text(sessione.inCorso ? "Un attimo…" : "Elimina l'account").frame(maxWidth: .infinity, minHeight: Tema.areaTocco)
                }
                .disabled((sessione.senzaPassword ? !riconfermato : password.isEmpty) || !capito || sessione.inCorso)
            }
        }
        .navigationTitle("Elimina l'account")
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
                    RigaValore(titolo: "Email verificata", valore: email)
                } footer: {
                    Text("Serve per recuperare la password se la dimentichi.")
                }
                Section("Togli l'email") {
                    if !sessione.senzaPassword {
                        SecureField("Password", text: $password)
                            .textContentType(.password)
                            .frame(minHeight: Tema.areaTocco)
                    }
                    Button(role: .destructive) { Task { await togli() } } label: {
                        Text(sessione.inCorso ? "Un attimo…" : "Togli l'email").frame(maxWidth: .infinity, minHeight: Tema.areaTocco)
                    }
                    .disabled(senzaConferma || sessione.inCorso)
                }
            } else {
                if codiceInviato || sessione.emailInAttesa != nil {
                    Section {
                        TextField("Codice ricevuto", text: $codice)
                            .keyboardType(.numberPad)
                            .textContentType(.oneTimeCode)
                            .frame(minHeight: Tema.areaTocco)
                        Button { Task { await conferma() } } label: {
                            Text(sessione.inCorso ? "Un attimo…" : "Conferma il codice").frame(maxWidth: .infinity, minHeight: Tema.areaTocco)
                        }
                        .disabled(codice.trimmingCharacters(in: .whitespaces).isEmpty || sessione.inCorso)
                    } header: {
                        Text("Verifica")
                    } footer: {
                        Text("Ti ho mandato un codice all'indirizzo scelto (controlla anche la posta indesiderata). Se non arriva, riprova qui sotto.")
                    }
                }
                // Due passi: prima l'indirizzo, poi la password. Un campo email accanto a un campo password è per iOS un modulo
                // di accesso: il riempimento automatico ci scriveva da solo nome utente e password salvati.
                if let scelto = indirizzoScelto {
                    Section {
                        RigaValore(titolo: "Indirizzo", valore: scelto)
                        if !sessione.senzaPassword {
                            SecureField("Password", text: $password)
                                .textContentType(.password)
                                .submitLabel(.send)
                                .onSubmit { Task { await aggiungi() } }
                                .frame(minHeight: Tema.areaTocco)
                        }
                        Button { Task { await aggiungi() } } label: {
                            Text(sessione.inCorso ? "Un attimo…" : "Manda il codice").frame(maxWidth: .infinity, minHeight: Tema.areaTocco)
                        }
                        .disabled(senzaConferma || sessione.inCorso)
                        Button("Cambia indirizzo") { indirizzoScelto = nil; password = "" }
                            .frame(maxWidth: .infinity, minHeight: Tema.areaTocco)
                    } header: {
                        Text("Conferma")
                    } footer: {
                        Text(sessione.senzaPassword ? "Ti mando un codice a questo indirizzo." : "Per sicurezza scrivi la tua password, poi ti mando un codice a questo indirizzo.")
                    }
                } else {
                    Section {
                        TextField("Indirizzo email", text: $indirizzo)
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
                    } header: {
                        Text("Aggiungi un'email")
                    } footer: {
                        Text("Facoltativa: ti permette di recuperare la password anche senza il codice di recupero.")
                    }
                }
            }
            if let errore { Section { Text(errore).foregroundStyle(Color.attenzione) } }
        }
        .navigationTitle("Email dell'account")
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
            fatto("Email verificata.")
            chiudi()
        } catch {
            errore = SchermataAccesso.testoErrore(error)
        }
    }

    private func togli() async {
        do {
            try await sessione.togliEmail(password: password)
            fatto("Email tolta.")
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
                Label("Scarica i tuoi dati", systemImage: "square.and.arrow.down").labelStyle(.voce(.indigo))
                Text("Un file con regole, rose, scelte e dati dell'account, da tenere o portare altrove.")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            .accessibilityElement(children: .combine)
            Button { Task { await scarica() } } label: {
                HStack(spacing: 8) {
                    if inCorso { ProgressView().accessibilityHidden(true) }
                    Text(inCorso ? "Preparo il file…" : "Scarica il file")
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
    List { Section("Il tuo account") { RigaScaricaDati(fogli: FogliAccount()) } }
}
