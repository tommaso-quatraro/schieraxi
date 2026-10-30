import SwiftUI

/// «Il tuo account» in Lega: nome, ruolo, esci, esci da tutti, cambia password, nuovo codice di recupero, elimina l'account.
/// Si vede solo se il server ha gli account (multiutente); con il server di sempre non compare.
struct AccountSezione: View {
    @EnvironmentObject private var sessione: SessioneAccount

    private enum Foglio: String, Identifiable {
        case password, codice, elimina
        var id: String { rawValue }
    }

    @State private var foglio: Foglio?
    @State private var chiediEsci = false
    @State private var chiediEsciDaTutti = false
    @State private var errore: String?
    @State private var messaggio: String?

    var body: some View {
        if sessione.multiutente, let utente = sessione.utente {
            Section("Il tuo account") {
                RigaValore(titolo: "Nome utente", valore: utente.nomeUtente)
                RigaValore(titolo: "Ruolo", valore: utente.ruoloLeggibile)
                Button { chiediEsci = true } label: {
                    Label("Esci", systemImage: "rectangle.portrait.and.arrow.right").labelStyle(.voce(.gray)).frame(minHeight: Tema.areaTocco)
                }
                Button { chiediEsciDaTutti = true } label: {
                    Label("Esci da tutti i dispositivi", systemImage: "iphone.slash").labelStyle(.voce(.orange)).frame(minHeight: Tema.areaTocco)
                }
                Button { foglio = .password } label: {
                    Label("Cambia password", systemImage: "key").labelStyle(.voce(.blue)).frame(minHeight: Tema.areaTocco)
                }
                Button { foglio = .codice } label: {
                    Label("Nuovo codice di recupero", systemImage: "lifepreserver").labelStyle(.voce(.mint)).frame(minHeight: Tema.areaTocco)
                }
                Button(role: .destructive) { foglio = .elimina } label: {
                    Label("Elimina l'account", systemImage: "trash").labelStyle(.voce(.red)).frame(minHeight: Tema.areaTocco)
                }
                if let messaggio { Text(messaggio).font(.footnote).foregroundStyle(Color.verde) }
                if let errore { Text(errore).font(.footnote).foregroundStyle(Color.attenzione) }
            }
            .confirmationDialog("Esci da SchieraXI su questo telefono?", isPresented: $chiediEsci, titleVisibility: .visible) {
                Button("Esci", role: .destructive) { Task { await sessione.esci() } }
            } message: {
                Text("I dati salvati su questo telefono vengono cancellati. Quelli sul server restano tuoi.")
            }
            .confirmationDialog("Esci da tutti i dispositivi?", isPresented: $chiediEsciDaTutti, titleVisibility: .visible) {
                Button("Esci da tutti", role: .destructive) {
                    Task {
                        do { try await sessione.esciDaTutti() } catch { errore = SchermataAccesso.testoErrore(error) }
                    }
                }
            } message: {
                Text("Tutti i telefoni e i browser dovranno rifare l'accesso, anche questo.")
            }
            .sheet(item: $foglio) { f in
                NavigationStack {
                    switch f {
                    case .password:
                        FoglioCambiaPassword(nome: utente.nomeUtente) { messaggio = "Password cambiata." ; errore = nil }
                    case .codice:
                        FoglioNuovoCodice()
                    case .elimina:
                        FoglioElimina()
                    }
                }
                .presentationDragIndicator(.visible)
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
                    .submitLabel(.go)
                    .onSubmit { Task { await invia() } }
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
                        Text("Il codice di prima smette di funzionare. Il nuovo compare una volta sola.")
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
    @State private var errore: String?

    var body: some View {
        Form {
            Section {
                Text("Cancella l'account e TUTTI i suoi dati sul server: rose, regole, scelte, immagini, avvisi. Non si può annullare. Se vuoi portarti via i dati, fai prima il backup dalla web app.")
                    .font(.subheadline)
            }
            Section("Conferma con la password") {
                SecureField("Password", text: $password)
                    .textContentType(.password)
                    .frame(minHeight: Tema.areaTocco)
                Toggle("Ho capito: cancella tutto", isOn: $capito)
                    .frame(minHeight: Tema.areaTocco)
            }
            if let errore { Section { Text(errore).foregroundStyle(Color.attenzione) } }
            Section {
                Button(role: .destructive) { Task { await elimina() } } label: {
                    Text(sessione.inCorso ? "Un attimo…" : "Elimina l'account").frame(maxWidth: .infinity, minHeight: Tema.areaTocco)
                }
                .disabled(password.isEmpty || !capito || sessione.inCorso)
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
            errore = SchermataAccesso.testoErrore(error)
        }
    }
}
