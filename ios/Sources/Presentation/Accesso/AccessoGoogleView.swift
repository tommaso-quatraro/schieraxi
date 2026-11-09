import SwiftUI

// Accesso con Google: il pulsante, la scelta del nome utente per i nuovi account e il riquadro «Accessi» nelle Impostazioni.
// Il giro con Google lo fa il server; qui si apre solo la finestra di sistema e si riscatta il codice (vedi `SessioneAccount`).
// Tutto resta spento finché il server non dichiara «google» tra i servizi accesi (`ServiziSociali`).

extension NuovoAccountSocial: Identifiable {
    var id: String { iscrizione }
}

/// «Continua con Google»: sotto il pulsante principale delle schermate Accedi e Registrati.
struct BottoneGoogle: View {
    let titolo: String
    var occupato = false
    let azione: () -> Void

    var body: some View {
        Button(action: azione) {
            Label(titolo, systemImage: "g.circle.fill")
                .font(.headline)
                .frame(maxWidth: .infinity, minHeight: Tema.areaTocco)
        }
        .pulsanteVetro()
        .disabled(occupato)
        .accessibilityHint("Si apre una finestra di Google. Poi torni qui da solo.")
    }
}

/// Dopo Google, per un account nuovo: si sceglie il nome utente (e si mette il codice d'invito, se serve).
struct ScegliNomeGoogleView: View {
    let nuovo: NuovoAccountSocial
    var invitoIniziale = ""
    @EnvironmentObject private var sessione: SessioneAccount
    @Environment(\.dismiss) private var chiudi
    @State private var nome = ""
    @State private var invito = ""
    @State private var accetto = false
    @State private var errore: String?
    @FocusState private var focus: Bool

    private var problemaNome: String? {
        if nome.isEmpty { return nil }
        return RegoleAccount.problemaSpaziNome(nome) ?? RegoleAccount.problemaNome(nome)
    }

    private var pronto: Bool {
        !nome.isEmpty && problemaNome == nil && accetto && (!nuovo.serveInvito || !invito.trimmingCharacters(in: .whitespaces).isEmpty)
    }

    private func pagina(_ p: PaginaServer) -> URL? {
        ProvaEsempio.attiva ? nil : InformazioniLegali.indirizzo(p, server: IndirizzoServer.attuale)
    }

    var body: some View {
        Form {
            Section {
                TextField(Catalogo.Accesso.nomeUtente, text: $nome)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .keyboardType(.asciiCapable)
                    .focused($focus)
                    .submitLabel(.go)
                    .onSubmit { Task { await crea() } }
                    .frame(minHeight: Tema.areaTocco)
            } header: {
                Text(Catalogo.Social.scegliNome).foregroundStyle(Color.testoSecondario)
            } footer: { Group {
                if let problemaNome { Text(problemaNome).foregroundStyle(Color.attenzione) }
                else { Text("È il nome con cui ti vedono gli altri. Da 3 a 32 caratteri: lettere, numeri, punto, trattino.") }
            }.foregroundStyle(Color.testoSecondario) }
            if nuovo.serveInvito {
                Section {
                    TextField(Catalogo.Accesso.codiceInvito, text: $invito)
                        .textInputAutocapitalization(.characters)
                        .autocorrectionDisabled()
                        .frame(minHeight: Tema.areaTocco)
                } header: {
                    Text("Invito").foregroundStyle(Color.testoSecondario)
                } footer: {
                    Text("L'invito te lo dà chi ti ha parlato di SchieraXI.").foregroundStyle(Color.testoSecondario)
                }
            }
            Section {
                // la stessa casella della registrazione (e della web): Privacy, Termini d'uso ed età minima
                Toggle(TestiAccesso.letto, isOn: $accetto)
                    .frame(minHeight: Tema.areaTocco)
                if let url = pagina(.privacy) { Link(TestiAccesso.leggiPrivacy, destination: url).frame(minHeight: Tema.areaTocco) }
                if let url = pagina(.termini) { Link(TestiAccesso.leggiTermini, destination: url).frame(minHeight: Tema.areaTocco) }
            }
            if let errore {
                Section { Label(errore, systemImage: "exclamationmark.triangle.fill").foregroundStyle(Color.attenzione) }
            }
            Section {
                Button { Task { await crea() } } label: {
                    Text(sessione.inCorso ? "Un attimo…" : Catalogo.Social.crea).frame(maxWidth: .infinity, minHeight: Tema.areaTocco)
                }
                .disabled(!pronto || sessione.inCorso)
            }
        }
        .navigationTitle("Quasi fatto")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Annulla") { chiudi() } } }
        .onAppear {
            if nome.isEmpty { nome = NomeSuggerito.pulito(nuovo.nomeSuggerito) }
            if invito.isEmpty { invito = invitoIniziale }
        }
    }

    private func crea() async {
        guard pronto, !sessione.inCorso else { return }
        errore = nil
        do {
            try await sessione.completaConGoogle(nuovo, nomeUtente: nome, invito: invito, accettoTermini: accetto)
        } catch {
            errore = SchermataAccesso.testoErrore(error)
        }
    }
}

/// «Accessi» nelle Impostazioni, sotto «Il tuo account»: come si entra (password, Google), collega e scollega Google.
/// Non compare se il server non ha Google acceso.
/// I fogli (password per collegare, aggiungi una password) si aprono da `FogliAccount`, fuori dalla lista: vedi `FoglioAccount`.
struct AccessiSezione: View {
    @ObservedObject var fogli: FogliAccount
    @EnvironmentObject private var sessione: SessioneAccount
    @AppStorage(ServiziSociali.chiave) private var socialTesto = ""
    @State private var chiediScollega = false

    var body: some View {
        if sessione.multiutente, sessione.utente != nil, ServiziSociali.googleAcceso(socialTesto) {
            Section {
                if let a = sessione.accessi {
                    // le righe della web: «Password: impostata», «Account Google collegato: …» o «Google: non collegato»
                    if let password = TestiAccount.rigaPassword(a) { Text(password) }
                    Text(TestiAccount.rigaGoogle(a))
                    if a.google != nil {
                        if a.puoScollegareGoogle {
                            Button(role: .destructive) { chiediScollega = true } label: {
                                Label(Catalogo.Social.scollega, systemImage: "minus.circle").frame(minHeight: Tema.areaTocco)
                            }
                            .disabled(sessione.inCorso)
                            // sul pulsante (una riga sola), non sulla Section: lì finirebbe su ogni riga. La domanda è quella
                            // della web, intera nel titolo.
                            .confirmationDialog(Catalogo.Social.scollegaConferma, isPresented: $chiediScollega, titleVisibility: .visible) {
                                Button(Catalogo.Social.scollega, role: .destructive) { Task { await fogli.scollegaGoogle(sessione) } }
                            }
                        }
                    } else {
                        Button {
                            if sessione.senzaPassword { Task { await fogli.collegaGoogle(password: "", sessione) } } else { fogli.apri(.passwordPerGoogle) }
                        } label: {
                            Label(Catalogo.Social.collega, systemImage: "link.badge.plus").labelStyle(.voce(.blue)).frame(minHeight: Tema.areaTocco)
                        }
                        .disabled(sessione.inCorso)
                        .accessibilityHint("Si apre una finestra di Google")
                    }
                    if a.soloGoogle {
                        Button { fogli.apri(.passwordDaGoogle) } label: {
                            Label(Catalogo.Social.aggiungiPassword, systemImage: "key").labelStyle(.voce(.mint)).frame(minHeight: Tema.areaTocco)
                        }
                    }
                } else {
                    Text("Controllo come entri…").foregroundStyle(Color.testoSecondario)
                }
                if let messaggio = fogli.messaggioAccessi { Text(messaggio).font(.footnote).foregroundStyle(Color.verde) }
                if let errore = fogli.erroreAccessi { Text(errore).font(.footnote).foregroundStyle(Color.attenzione) }
            } header: {
                Text(Catalogo.Social.accessi).foregroundStyle(Color.testoSecondario)
            } footer: {
                Text(piede).foregroundStyle(Color.testoSecondario)
            }
            // niente .task, .sheet o .confirmationDialog qui: su una Section dentro una List finiscono su OGNI riga.
            // Il controllo degli accessi lo fa una volta sola `fogliAccount(_:)` sulle Impostazioni.
        }
    }

    private var piede: String {
        guard let a = sessione.accessi else { return "" }
        if a.soloGoogle { return "Per ora entri solo con Google. Aggiungi una password per avere un secondo modo di entrare." }
        if a.google != nil && !a.puoScollegareGoogle { return "Google è l'unico modo per entrare: per scollegarlo serve prima un altro accesso." }
        if a.google == nil { return "Collegando Google puoi entrare senza scrivere la password. Il nome utente resta lo stesso." }
        return "Puoi entrare con la password oppure con Google."
    }
}

/// Chiede la password attuale prima di aprire Google per collegarlo: il server la vuole per le modifiche agli accessi.
struct FoglioPasswordPerCollegare: View {
    @Environment(\.dismiss) private var chiudi
    @State private var password = ""
    let procedi: (String) -> Void

    var body: some View {
        Form {
            Section {
                SecureField(Catalogo.Account.passwordAttuale, text: $password).textContentType(.password).frame(minHeight: Tema.areaTocco)
            } footer: {
                Text(Catalogo.Social.servePassword).foregroundStyle(Color.testoSecondario)
            }
            Section {
                Button { procedi(password) } label: {
                    Text(Catalogo.Social.continua).frame(maxWidth: .infinity, minHeight: Tema.areaTocco)
                }
                .disabled(password.isEmpty)
            }
        }
        .navigationTitle(Catalogo.Social.collega)
        .navigationBarTitleDisplayMode(.inline)
        .schermoProtetto()
        .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Annulla") { chiudi() } } }
    }
}

/// «Conferma con Google»: per chi non ha una password, le azioni delicate chiedono prima questo passaggio (vale 5 minuti).
/// Le frasi sono quelle della web: la spiegazione sotto il pulsante e, dopo, «Confermato. Per 5 minuti puoi…».
struct RigaRiconferma: View {
    @Binding var confermato: Bool
    @EnvironmentObject private var sessione: SessioneAccount
    @State private var errore: String?

    var body: some View {
        Section {
            if confermato {
                Label(Catalogo.Social.riconfermatoOk, systemImage: "checkmark.circle.fill").foregroundStyle(Color.verde).frame(minHeight: Tema.areaTocco)
            } else {
                Button { Task { await conferma() } } label: {
                    Text(sessione.inCorso ? "Un attimo…" : Catalogo.Social.conferma).frame(maxWidth: .infinity, minHeight: Tema.areaTocco)
                }
                .disabled(sessione.inCorso)
                .accessibilityHint("Si apre una finestra di Google")
            }
            if let errore { Text(errore).font(.footnote).foregroundStyle(Color.attenzione) }
        } header: {
            Text("Conferma").foregroundStyle(Color.testoSecondario)
        } footer: {
            if !confermato { Text(Catalogo.Social.confermaSpiega).foregroundStyle(Color.testoSecondario) }
        }
    }

    private func conferma() async {
        errore = nil
        do {
            try await sessione.riconfermaGoogle(avvio: AvvioWebSistema())
            confermato = true
        } catch let e as ErroreSocial where e.eSoloUnaChiusura {
            // chiusa la finestra
        } catch {
            errore = SchermataAccesso.testoErrore(error)
        }
    }
}

/// Aggiunge una password a chi è entrato solo con Google: prima la conferma con Google, poi la password (due volte).
struct FoglioPasswordDaGoogle: View {
    @EnvironmentObject private var sessione: SessioneAccount
    @Environment(\.dismiss) private var chiudi
    @State private var confermato = false
    @State private var nuova = ""
    @State private var ripeti = ""
    @State private var errore: String?

    private var nome: String { sessione.utente?.nomeUtente ?? "" }
    private var problema: String? { nuova.isEmpty ? nil : RegoleAccount.problemaPassword(nuova, nome: nome) }
    private var pronto: Bool { confermato && RegoleAccount.problemaPassword(nuova, nome: nome) == nil && nuova == ripeti }

    var body: some View {
        Form {
            RigaRiconferma(confermato: $confermato)
            if confermato {
                Section {
                    SecureField(TestiAccount.nuovaPassword, text: $nuova).textContentType(.newPassword).frame(minHeight: Tema.areaTocco)
                    SecureField(TestiAccount.ripetiPassword, text: $ripeti).textContentType(.newPassword).frame(minHeight: Tema.areaTocco)
                } header: {
                    Text("Password nuova").foregroundStyle(Color.testoSecondario)
                } footer: { Group {
                    VStack(alignment: .leading, spacing: 4) {
                        if let problema { Text(problema).foregroundStyle(Color.attenzione) }
                        if !ripeti.isEmpty && nuova != ripeti { Text(TestiAccount.passwordDiverse).foregroundStyle(Color.attenzione) }
                        Text("Almeno \(RegoleAccount.passwordMinima) caratteri, non solo numeri e non troppo facile.")
                    }
                }.foregroundStyle(Color.testoSecondario) }
                if let errore { Section { Text(errore).foregroundStyle(Color.attenzione) } }
                Section {
                    Button { Task { await salva() } } label: {
                        Text(sessione.inCorso ? "Un attimo…" : Catalogo.Social.aggiungiPassword).frame(maxWidth: .infinity, minHeight: Tema.areaTocco)
                    }
                    .disabled(!pronto || sessione.inCorso)
                }
            }
        }
        .navigationTitle(Catalogo.Social.aggiungiPassword)
        .navigationBarTitleDisplayMode(.inline)
        .schermoProtetto()
        .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Annulla") { chiudi() } } }
    }

    private func salva() async {
        guard pronto else { return }
        do {
            try await sessione.impostaPassword(nuova)
            nuova = ""; ripeti = ""
            chiudi()
        } catch {
            if case ErroreApi.codificato("serve_riconferma", _) = error { confermato = false }   // sono passati più di cinque minuti
            errore = SchermataAccesso.testoErrore(error)
        }
    }
}
