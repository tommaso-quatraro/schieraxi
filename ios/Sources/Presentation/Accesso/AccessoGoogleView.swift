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
                TextField("Nome utente", text: $nome)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .keyboardType(.asciiCapable)
                    .focused($focus)
                    .submitLabel(.go)
                    .onSubmit { Task { await crea() } }
                    .frame(minHeight: Tema.areaTocco)
            } header: {
                Text("Scegli il tuo nome utente")
            } footer: {
                if let problemaNome { Text(problemaNome).foregroundStyle(Color.attenzione) }
                else { Text("È il nome con cui ti vedono gli altri. Da 3 a 32 caratteri: lettere, numeri, punto, trattino.") }
            }
            if nuovo.serveInvito {
                Section {
                    TextField("Codice d'invito", text: $invito)
                        .textInputAutocapitalization(.characters)
                        .autocorrectionDisabled()
                        .frame(minHeight: Tema.areaTocco)
                } header: {
                    Text("Invito")
                } footer: {
                    Text("L'invito te lo dà chi ti ha parlato di SchieraXI.")
                }
            }
            Section {
                Toggle("Accetto i Termini d'uso e l'Informativa sulla privacy", isOn: $accetto)
                    .frame(minHeight: Tema.areaTocco)
                if let url = pagina(.termini) { Link("Leggi i Termini d'uso", destination: url).frame(minHeight: Tema.areaTocco) }
                if let url = pagina(.privacy) { Link("Leggi l'Informativa sulla privacy", destination: url).frame(minHeight: Tema.areaTocco) }
            }
            if let errore {
                Section { Label(errore, systemImage: "exclamationmark.triangle.fill").foregroundStyle(Color.attenzione) }
            }
            Section {
                Button { Task { await crea() } } label: {
                    Text(sessione.inCorso ? "Un attimo…" : "Crea l'account").frame(maxWidth: .infinity, minHeight: Tema.areaTocco)
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
struct AccessiSezione: View {
    @EnvironmentObject private var sessione: SessioneAccount
    @AppStorage(ServiziSociali.chiave) private var socialTesto = ""
    @State private var chiediScollega = false
    @State private var foglioPassword = false
    @State private var errore: String?
    @State private var messaggio: String?

    var body: some View {
        if sessione.multiutente, sessione.utente != nil, ServiziSociali.googleAcceso(socialTesto) {
            Section {
                if let a = sessione.accessi {
                    RigaValore(titolo: "Password", valore: a.password == true ? "Impostata" : (a.password == false ? "Non impostata" : "Non so"))
                    if let g = a.google {
                        RigaValore(titolo: "Google", valore: g.email ?? "Collegato")
                        if a.puoScollegareGoogle {
                            Button(role: .destructive) { chiediScollega = true } label: {
                                Label("Scollega Google", systemImage: "minus.circle").frame(minHeight: Tema.areaTocco)
                            }
                            .disabled(sessione.inCorso)
                        }
                    } else {
                        Button { Task { await collega() } } label: {
                            Label("Collega Google", systemImage: "link.badge.plus").labelStyle(.voce(.blue)).frame(minHeight: Tema.areaTocco)
                        }
                        .disabled(sessione.inCorso)
                        .accessibilityHint("Si apre una finestra di Google")
                    }
                    if a.soloGoogle {
                        Button { foglioPassword = true } label: {
                            Label("Aggiungi una password", systemImage: "key").labelStyle(.voce(.mint)).frame(minHeight: Tema.areaTocco)
                        }
                    }
                } else {
                    Text("Controllo come entri…").foregroundStyle(.secondary)
                }
                if let messaggio { Text(messaggio).font(.footnote).foregroundStyle(Color.verde) }
                if let errore { Text(errore).font(.footnote).foregroundStyle(Color.attenzione) }
            } header: {
                Text("Accessi")
            } footer: {
                Text(piede)
            }
            .task { await sessione.aggiornaAccessi() }
            .confirmationDialog("Scollegare Google?", isPresented: $chiediScollega, titleVisibility: .visible) {
                Button("Scollega Google", role: .destructive) { Task { await scollega() } }
            } message: {
                Text("Potrai entrare solo con nome utente e password. Se vuoi, puoi ricollegare Google quando vuoi.")
            }
            .sheet(isPresented: $foglioPassword) {
                NavigationStack { FoglioPasswordDaGoogle() }.presentationDragIndicator(.visible)
            }
        }
    }

    private var piede: String {
        guard let a = sessione.accessi else { return "" }
        if a.soloGoogle { return "Per ora entri solo con Google. Aggiungi una password per avere un secondo modo di entrare." }
        if a.google != nil && !a.puoScollegareGoogle { return "Google è l'unico modo per entrare: per scollegarlo serve prima un altro accesso." }
        if a.google == nil { return "Collegando Google puoi entrare senza scrivere la password. Il nome utente resta lo stesso." }
        return "Puoi entrare con la password oppure con Google."
    }

    private func collega() async {
        errore = nil; messaggio = nil
        do {
            try await sessione.collegaGoogle(avvio: AvvioWebSistema())
            messaggio = "Google è collegato."
        } catch let e as ErroreSocial where e.eSoloUnaChiusura {
            // chiusa la finestra: nessun errore da mostrare
        } catch {
            errore = SchermataAccesso.testoErrore(error)
        }
    }

    private func scollega() async {
        errore = nil; messaggio = nil
        do {
            try await sessione.scollegaGoogle()
            messaggio = "Google è scollegato."
        } catch {
            errore = SchermataAccesso.testoErrore(error)
        }
    }
}

/// «Conferma con Google»: per chi non ha una password, le azioni delicate chiedono prima questo passaggio (vale 5 minuti).
struct RigaRiconferma: View {
    @Binding var confermato: Bool
    @EnvironmentObject private var sessione: SessioneAccount
    @State private var errore: String?

    var body: some View {
        Section {
            if confermato {
                Label("Confermato con Google", systemImage: "checkmark.circle.fill").foregroundStyle(Color.verde).frame(minHeight: Tema.areaTocco)
            } else {
                Button { Task { await conferma() } } label: {
                    Text(sessione.inCorso ? "Un attimo…" : "Conferma con Google").frame(maxWidth: .infinity, minHeight: Tema.areaTocco)
                }
                .disabled(sessione.inCorso)
                .accessibilityHint("Si apre una finestra di Google")
            }
            if let errore { Text(errore).font(.footnote).foregroundStyle(Color.attenzione) }
        } header: {
            Text("Conferma")
        } footer: {
            Text(confermato ? "Hai cinque minuti per finire." : "Non hai una password: per sicurezza confermi che sei tu con Google.")
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
                    SecureField("Nuova password", text: $nuova).textContentType(.newPassword).frame(minHeight: Tema.areaTocco)
                    SecureField("Ripeti la nuova password", text: $ripeti).textContentType(.newPassword).frame(minHeight: Tema.areaTocco)
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
                    Button { Task { await salva() } } label: {
                        Text(sessione.inCorso ? "Un attimo…" : "Salva la password").frame(maxWidth: .infinity, minHeight: Tema.areaTocco)
                    }
                    .disabled(!pronto || sessione.inCorso)
                }
            }
        }
        .navigationTitle("Aggiungi una password")
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
