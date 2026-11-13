import Foundation
import Testing
@testable import Schieraxi

/// Le parole di Accesso, Il tuo account, Accessi (Google), codice di recupero, Primo avvio e Impostazioni vengono dal catalogo
/// comune con la web (#497, parte di #167): `fanta/testi/` è la fonte, i file Swift di `Support/Catalogo/` li genera
/// `python script/testi.py --scrivi` per le chiavi elencate in `ios/testi/`. Una frase riscritta a mano in Swift non seguirebbe
/// più la web, e qui fallisce. I testi che ha solo l'iPhone («Leggi la Privacy», «Un attimo…», i passi della guida che la web
/// non ha) restano in Swift.
@Suite("Accesso e Impostazioni: le parole vengono dal catalogo (#497)")
struct AccessoImpostazioniDalCatalogoTests {

    // MARK: niente testi a mano

    /// I testi del catalogo che queste schermate mostrano: nessuno deve stare scritto a mano, fra virgolette, nei loro file.
    static let testiFissi: [String] = [
        // accesso.*
        Catalogo.Accesso.schedaAccedi, Catalogo.Accesso.schedaRegistra, Catalogo.Accesso.schedaRecupero,
        Catalogo.Accesso.nomeUtente, Catalogo.Accesso.password, Catalogo.Accesso.password10, Catalogo.Accesso.passwordNuova10,
        Catalogo.Accesso.codiceInvito, Catalogo.Accesso.codice, Catalogo.Accesso.codiceEmail, Catalogo.Accesso.email,
        Catalogo.Accesso.emailFacoltativa, Catalogo.Accesso.emailFacoltativaAiuto, Catalogo.Accesso.invioAccedi,
        Catalogo.Accesso.invioRegistra, Catalogo.Accesso.invioVerifica, Catalogo.Accesso.invioRecupero,
        Catalogo.Accesso.invioRecuperoEmail, Catalogo.Accesso.serveInvito, Catalogo.Accesso.serveInvitoEmail,
        Catalogo.Accesso.serveEmail, Catalogo.Accesso.recuperoSpiega, Catalogo.Accesso.recuperoEmailSpiega,
        Catalogo.Accesso.recuperoConEmail, Catalogo.Accesso.recuperoConCodice, Catalogo.Accesso.torna,
        Catalogo.Accesso.codiceInviato, Catalogo.Accesso.passwordCambiata, Catalogo.Accesso.passwordCambiataAccedi,
        Catalogo.Accesso.vaiAccesso, Catalogo.Accesso.rispostaIncompleta,
        // account.*
        Catalogo.Account.ruoloAdmin, Catalogo.Account.ruoloUtente, Catalogo.Account.esci, Catalogo.Account.cambiaPassword,
        Catalogo.Account.passwordAttuale, Catalogo.Account.ripetiPassword, Catalogo.Account.passwordDiverse,
        Catalogo.Account.altriScollegati, Catalogo.Account.passwordCambiataOk, Catalogo.Account.passwordCambiataCodice,
        Catalogo.Account.laTuaPassword,
        Catalogo.Account.recupero, Catalogo.Account.recuperoSpiega, Catalogo.Account.nuovoCodice, Catalogo.Account.email,
        Catalogo.Account.emailSpiega, Catalogo.Account.emailNessuna, Catalogo.Account.emailNuova, Catalogo.Account.emailInvia,
        Catalogo.Account.emailInviato, Catalogo.Account.emailCodice, Catalogo.Account.emailConferma,
        Catalogo.Account.emailConfermataOk, Catalogo.Account.emailTogli, Catalogo.Account.emailToltaOk,
        Catalogo.Account.emailServePassword, Catalogo.Account.emailSpenta, Catalogo.Account.datiTitolo,
        Catalogo.Account.datiSpiega, Catalogo.Account.datiScarica, Catalogo.Account.eliminaTitolo, Catalogo.Account.elimina,
        Catalogo.Account.eliminaConferma,
        // social.*
        Catalogo.Social.continua, Catalogo.Social.oppure, Catalogo.Social.scegliNome, Catalogo.Social.crea,
        Catalogo.Social.accessi, Catalogo.Social.passwordSi, Catalogo.Social.passwordNo, Catalogo.Social.googleAccount,
        Catalogo.Social.googleNonCollegato, Catalogo.Social.collega, Catalogo.Social.scollega, Catalogo.Social.scollegaConferma,
        Catalogo.Social.scollegatoOk, Catalogo.Social.collegatoOk, Catalogo.Social.servePassword, Catalogo.Social.conferma,
        Catalogo.Social.confermaSpiega, Catalogo.Social.riconfermatoOk, Catalogo.Social.aggiungiPassword,
        // codice.*, legale.*, imp.*
        Catalogo.Codice.titolo, Catalogo.Codice.aCosaServe, Catalogo.Codice.salva, Catalogo.Codice.spiega,
        Catalogo.Codice.copia, Catalogo.Codice.copiato, Catalogo.Codice.salvato,
        Catalogo.Legale.privacy, Catalogo.Legale.termini, Catalogo.Legale.crediti,
        Catalogo.Imp.account, Catalogo.Imp.aspetto, Catalogo.Imp.informazioni, Catalogo.Imp.avanzate, Catalogo.Imp.sezAvvisi,
        Catalogo.Imp.avvisiQui, Catalogo.Imp.avvisiQuiAiuto, Catalogo.Imp.lega, Catalogo.Imp.regole, Catalogo.Imp.regoleSub,
        Catalogo.Imp.miaSquadraNessuna, Catalogo.Imp.altreSquadre, Catalogo.Imp.informazioniSub, Catalogo.Imp.gestione,
        Catalogo.Imp.gestioneSub, Catalogo.Imp.aggiornaSpiega,
        // avv.* (Avvisi), pav.* (Primo avvio)
        Catalogo.Avv.nativa, Catalogo.Avv.nativaAiuto, Catalogo.Avv.oreTranq, Catalogo.Avv.permessoNegatoAbilita,
        Catalogo.Avv.notificheDisattivateQuesto,
        Catalogo.Pav.primoAvvio, Catalogo.Pav.salta, Catalogo.Pav.tuttoProntoMister, Catalogo.Pav.haiFinito,
        Catalogo.Pav.nonSonoRiuscito, Catalogo.Pav.permessoNegatoAbilita,
        // parole comuni già nel catalogo (Oggi, #494)
        Catalogo.Shell.chiudi, Catalogo.Shell.impostazioni, Catalogo.Comune.importaRose,
    ]

    /// Le frasi con un valore dentro: il valore si scrive «§» (i segni `<b>` della web contano come un valore) e restano le
    /// parti fisse. `account.email_attesa` non c'è: la riga di «Il tuo account» ne usa solo l'inizio (la frase intera, con il
    /// campo del codice, sta nel foglio dell'email), lo prova `righeDellAccount`.
    static let frasiConValori: [String] = [
        Catalogo.Accesso.verificaSpiega(email: "§"), Catalogo.Accesso.recuperoCodiceEmailSpiega(email: "§"),
        Catalogo.Accesso.letto(eta: "§", privacy: "§", termini: "§"), Catalogo.Accesso.spuntaLetto(eta: "§"),
        Catalogo.Account.dal(data: "§", ruolo: "§"), Catalogo.Account.emailVerificata(email: "§"),
        Catalogo.Account.emailGoogle(email: "§"), Catalogo.Account.eliminaAvviso, Catalogo.Social.googleCollegato(email: "§"),
    ]

    /// Le parti fisse di una frase (almeno 6 caratteri senza spazi ai lati: le più corte potrebbero stare in tutt'altro codice).
    static func partiFisse(_ frase: String) -> [String] {
        frase.replacingOccurrences(of: #"<[^>]+>"#, with: "§", options: .regularExpression)
            .components(separatedBy: "§")
            .filter { $0.trimmingCharacters(in: .whitespaces).count >= 6 }
    }

    /// I file controllati: tutti quelli di `Presentation/Accesso`, la pagina delle Impostazioni con le sue voci, gli avvisi e Gestione.
    static func fileControllati(file: String = #filePath) throws -> [String] {
        let accesso = try FileManager.default.contentsOfDirectory(atPath: SorgenteAccesso.radice(file: file).appendingPathComponent(
            "Sources/Presentation/Accesso").path)
            .filter { $0.hasSuffix(".swift") }
            .sorted()
            .map { "Sources/Presentation/Accesso/\($0)" }
        return accesso + ["Sources/Presentation/Lega/ImpostazioniView.swift", "Sources/Presentation/Lega/VociImpostazioni.swift",
                          "Sources/Presentation/Lega/AvvisiDispositivoSezione.swift", "Sources/Presentation/Lega/GestionePagina.swift"]
    }

    @Test("Nei file di Accesso e Impostazioni nessun testo del catalogo è scritto a mano")
    func nienteTestiAMano() throws {
        let file = try Self.fileControllati()
        #expect(file.contains("Sources/Presentation/Accesso/ModuloAccesso.swift"), "la cartella di Accesso non si legge: \(file)")
        for percorso in file {
            let codice = try SorgenteAccesso.codice(percorso)
            for testo in Self.testiFissi {
                #expect(!codice.contains("\"\(testo)\""), "\(percorso) scrive a mano «\(testo)»: usa Catalogo.…")
            }
            for parte in Self.frasiConValori.flatMap(Self.partiFisse) {
                #expect(!codice.contains(parte), "\(percorso) scrive a mano «\(parte)»: usa Catalogo.…")
            }
        }
    }

    /// Il controllo sopra deve trovare davvero un testo scritto a mano: qui con un codice finto.
    @Test("Il controllo trova un testo del catalogo scritto a mano, anche dentro una frase con un valore")
    func ilControlloFunziona() {
        let codice = SorgenteAccesso.soloCodice(#"""
        /// «Esci» nel commento non conta
        Label("Esci", systemImage: "rectangle.portrait.and.arrow.right")
        return "Ti abbiamo scritto a \(a). Inserisci il codice a 6 cifre (vale 15 minuti)."
        #Preview("Accedi") { SchermataAccesso() }
        """#)
        #expect(codice.contains("\"\(Catalogo.Account.esci)\""))
        #expect(Self.partiFisse(Catalogo.Accesso.verificaSpiega(email: "§")).contains { codice.contains($0) })
        #expect(!codice.contains("«Esci»"), "i commenti non contano")
        #expect(!codice.contains("\"\(Catalogo.Accesso.schedaAccedi)\""), "le anteprime non contano")
    }

    // MARK: le viste usano il catalogo

    /// Le viste usano davvero le costanti del catalogo, anche dove prima l'iPhone diceva un'altra cosa e ora vince la web
    /// (Google collegato e scollegato, la conferma con Google, il codice di recupero, il Primo avvio).
    @Test("Le viste di Accesso e Impostazioni prendono le parole dal catalogo", arguments: [
        ("Sources/Presentation/Accesso/AccessoView.swift", [
            "Catalogo.Accesso.schedaAccedi", "Catalogo.Accesso.schedaRegistra", "Catalogo.Accesso.schedaRecupero",
            "Catalogo.Social.continua", "Catalogo.Social.oppure", "Catalogo.Imp.avanzate",
        ]),
        ("Sources/Presentation/Accesso/ModuloAccesso.swift", [
            "Catalogo.Accesso.letto(", "Catalogo.Accesso.spuntaLetto(", "Catalogo.Legale.privacy", "Catalogo.Legale.termini",
            "Catalogo.Accesso.password10", "Catalogo.Accesso.passwordNuova10", "Catalogo.Accesso.verificaSpiega(",
            "Catalogo.Accesso.recuperoCodiceEmailSpiega(", "Catalogo.Accesso.recuperoConEmail", "Catalogo.Accesso.invioVerifica",
        ]),
        ("Sources/Presentation/Accesso/AccessoGoogleView.swift", [
            "Catalogo.Accesso.nomeUtente", "Catalogo.Social.scegliNome", "Catalogo.Accesso.codiceInvito", "Catalogo.Social.crea",
            "Catalogo.Social.accessi", "Catalogo.Social.scollega", "Catalogo.Social.scollegaConferma", "Catalogo.Social.collega",
            "Catalogo.Social.aggiungiPassword", "Catalogo.Social.servePassword", "Catalogo.Social.continua",
            "Catalogo.Social.conferma", "Catalogo.Social.confermaSpiega", "Catalogo.Social.riconfermatoOk",
            "TestiAccount.rigaPassword(", "TestiAccount.rigaGoogle(", "TestiAccount.nuovaPassword", "TestiAccount.ripetiPassword",
            "TestiAccount.passwordDiverse",
        ]),
        ("Sources/Presentation/Accesso/AccountSezione.swift", [
            "Catalogo.Imp.account", "Catalogo.Account.esci", "Catalogo.Social.collegatoOk", "Catalogo.Social.scollegatoOk",
            "Catalogo.Shell.chiudi",
            // dopo il cambio della password: il codice nuovo sotto «Password cambiata» e l'esito dal catalogo (#590)
            "TestiAccesso.passwordCambiata", "TestiAccount.esitoCambioPassword(",
        ]),
        ("Sources/Presentation/Accesso/CodiceRecuperoView.swift", [
            "Catalogo.Codice.titolo", "Catalogo.Codice.aCosaServe", "Catalogo.Codice.salva", "Catalogo.Codice.spiega",
            "Catalogo.Codice.copia", "Catalogo.Codice.copiato", "Catalogo.Codice.salvato", "Catalogo.Account.recupero",
        ]),
        ("Sources/Presentation/Accesso/ConfigurazioneGuidataView.swift", [
            "Catalogo.Pav.primoAvvio", "Catalogo.Pav.salta", "Catalogo.Pav.tuttoProntoMister", "Catalogo.Pav.haiFinito",
            "Catalogo.Shell.chiudi",
        ]),
        ("Sources/Presentation/Accesso/ConfigurazioneGuidataViewModel.swift", [
            "Catalogo.Pav.nonSonoRiuscito", "Catalogo.Pav.permessoNegatoAbilita",
        ]),
        ("Sources/Presentation/Accesso/ConfiguraLegaView.swift", ["Catalogo.Comune.importaRose"]),
        ("Sources/Presentation/Accesso/SessioneMinima.swift", ["Catalogo.Account.esci"]),
        ("Sources/Presentation/Lega/ImpostazioniView.swift", ["Catalogo.Shell.impostazioni", "Catalogo.Imp.lega"]),
        ("Sources/Presentation/Lega/VociImpostazioni.swift", [
            "Catalogo.Lega.voceImporta", "Catalogo.Lega.voceImportaSub", "Catalogo.Lega.miaSquadra", "Catalogo.Imp.miaSquadraNessuna",
            "Catalogo.Imp.regole", "Catalogo.Imp.regoleSub", "Catalogo.Imp.altreSquadre", "Catalogo.Lega.nSquadre(",
            "Catalogo.Imp.account", "Catalogo.Imp.informazioni", "Catalogo.Imp.informazioniSub", "Catalogo.Imp.gestione",
            "Catalogo.Imp.gestioneSub",
        ]),
        ("Sources/Presentation/Lega/AvvisiDispositivoSezione.swift", [
            "Catalogo.Imp.sezAvvisi", "Catalogo.Imp.avvisiQui", "Catalogo.Imp.avvisiQuiAiuto", "Catalogo.Avv.oreTranq",
            "Catalogo.Avv.aveviSceltoOre",
        ]),
        ("Sources/Presentation/Lega/GestionePagina.swift", [
            "Catalogo.Imp.gestione", "Catalogo.Imp.aggiornaSpiega", "Catalogo.Avv.nativa", "Catalogo.Avv.nativaAiuto",
        ]),
    ])
    func vistaUsaIlCatalogo(percorso: String, costanti: [String]) throws {
        let codice = try SorgenteAccesso.codice(percorso)
        for costante in costanti {
            #expect(codice.contains(costante), "\(percorso) non usa \(costante)")
        }
    }

    // MARK: frasi con un valore e testi composti

    @Test("La casella della registrazione: la frase della web con i nomi delle pagine legali e l'età minima")
    func casellaDellaRegistrazione() {
        #expect(TestiAccesso.letto == Catalogo.Accesso.letto(eta: "14", privacy: Catalogo.Legale.privacy,
                                                             termini: Catalogo.Legale.termini))
        #expect(TestiAccesso.spuntaLetto == Catalogo.Accesso.spuntaLetto(eta: "\(TestiAccesso.etaMinima)"))
        #expect(TestiAccesso.letto.contains(Catalogo.Legale.privacy) && TestiAccesso.letto.contains(Catalogo.Legale.termini))
    }

    /// Il catalogo scrive il numero dentro la frase («almeno 10 caratteri»): deve essere il minimo che l'app controlla.
    @Test("Le etichette della password nuova dicono il minimo che l'app controlla")
    func passwordMinima() {
        #expect(Catalogo.Accesso.password10.contains("almeno \(RegoleAccount.passwordMinima) caratteri"))
        #expect(Catalogo.Accesso.passwordNuova10.contains("almeno \(RegoleAccount.passwordMinima) caratteri"))
        #expect(ModuloAccesso(scheda: .registrati).etichettaPassword == Catalogo.Accesso.password10)
        #expect(ModuloAccesso(scheda: .recupera, metodo: .codice).etichettaPassword == Catalogo.Accesso.passwordNuova10)
        #expect(ModuloAccesso(scheda: .accedi).etichettaPassword == Catalogo.Accesso.password)
        #expect(TestiAccount.nuovaPassword == Catalogo.Accesso.passwordNuova10)
    }

    @Test("Le schede e i modi del recupero hanno i nomi della web")
    func schedeEMetodi() {
        #expect(SchermataAccesso.Scheda.allCases.map(\.titolo)
                == [Catalogo.Accesso.schedaAccedi, Catalogo.Accesso.schedaRegistra, Catalogo.Accesso.schedaRecupero])
        #expect(MetodoRecupero.allCases.map(\.titolo) == [Catalogo.Accesso.recuperoConEmail, Catalogo.Accesso.recuperoConCodice])
    }

    @Test("Le frasi con l'indirizzo: il codice per posta della registrazione e del recupero")
    func frasiConLIndirizzo() {
        var verifica = ModuloAccesso(scheda: .registrati)
        verifica.iscrizione = IscrizioneInAttesa(email: "nome@example.invalid", iscrizione: "finta")
        #expect(verifica.spiegazione(.email) == Catalogo.Accesso.verificaSpiega(email: "nome@example.invalid"))
        var recupero = ModuloAccesso(scheda: .recupera, metodo: .email)
        recupero.emailRecupero = "nome@example.invalid"
        #expect(recupero.spiegazione(.email) == Catalogo.Accesso.recuperoCodiceEmailSpiega(email: "nome@example.invalid"))
    }

    @Test("Il tuo account: ruolo e data, e le righe dell'email con le frasi della web")
    func righeDellAccount() {
        #expect(TestiAccount.ruoloEData(ruolo: "utente", creato: "2026-09-01")
                == Catalogo.Account.dal(data: "1 settembre 2026", ruolo: Catalogo.Account.ruoloUtente))
        #expect(TestiAccount.ruoloEData(ruolo: "amministratore", creato: nil) == Catalogo.Account.ruoloAdmin)
        #expect(TestiAccount.rigaEmail(account: "a@example.invalid", google: nil, inAttesa: nil)
                == Catalogo.Account.emailVerificata(email: "a@example.invalid"))
        #expect(TestiAccount.rigaEmail(account: nil, google: "g@example.invalid", inAttesa: nil)
                == Catalogo.Account.emailGoogle(email: "g@example.invalid"))
        #expect(TestiAccount.rigaEmail(account: nil, google: nil, inAttesa: nil) == Catalogo.Account.emailNessuna)
        #expect(TestiAccount.emailAttesa("x@example.invalid") == Catalogo.Account.emailAttesa(email: "x@example.invalid"))
        // la riga corta di «Il tuo account» è l'inizio della frase della web
        let corta = TestiAccount.rigaEmail(account: nil, google: nil, inAttesa: "x@example.invalid")
        #expect(Catalogo.Account.emailAttesa(email: "x@example.invalid").hasPrefix(corta))
    }

    /// La web scrive «tutti» in grassetto con `<b>`; l'iPhone mette il grassetto con il Markdown di `Text`.
    @Test("Elimina l'account: la frase della web, con «tutti» in grassetto senza i segni della web")
    func eliminaAvviso() {
        #expect(TestiAccount.eliminaAvviso.contains("**tutti**"))
        #expect(!TestiAccount.eliminaAvviso.contains("<"))
        let senzaSegni = Catalogo.Account.eliminaAvviso.replacingOccurrences(of: #"</?b>"#, with: "", options: .regularExpression)
        #expect(TestiAccount.eliminaAvviso.replacingOccurrences(of: "**", with: "") == senzaSegni)
    }

    @Test("Accessi: «Password: impostata» o «non impostata» (niente riga se il server non lo dice), Google con l'indirizzo")
    func righeDegliAccessi() {
        #expect(TestiAccount.rigaPassword(AccessiAccount(password: true)) == Catalogo.Social.passwordSi)
        #expect(TestiAccount.rigaPassword(AccessiAccount(password: false)) == Catalogo.Social.passwordNo)
        #expect(TestiAccount.rigaPassword(AccessiAccount(password: nil)) == nil)
        let conEmail = AccessiAccount(password: true, social: [AccessoCollegato(provider: "google", email: "g@example.invalid")])
        #expect(TestiAccount.rigaGoogle(conEmail) == Catalogo.Social.googleCollegato(email: "g@example.invalid"))
        let senzaEmail = AccessiAccount(password: true, social: [AccessoCollegato(provider: "google", email: " ")])
        #expect(TestiAccount.rigaGoogle(senzaEmail) == Catalogo.Social.googleCollegato(email: Catalogo.Social.googleAccount))
        #expect(TestiAccount.rigaGoogle(AccessiAccount(password: true)) == Catalogo.Social.googleNonCollegato)
    }

    @MainActor
    @Test("Primo avvio: il salvataggio non riuscito si dice con la frase della web")
    func primoAvvioSalvataggio() {
        #expect(ConfigurazioneGuidataViewModel.erroreSalvataggio == Catalogo.Pav.nonSonoRiuscito)
    }

    @Test("Codice di recupero: l'invito a salvarlo c'è una volta sola, in «Salva questo codice.» (#557)")
    func codiceUnInvitoSolo() {
        #expect(Catalogo.Codice.aCosaServe == "Ti serve per rientrare se dimentichi la password.")
        #expect(!Catalogo.Codice.aCosaServe.localizedCaseInsensitiveContains("salva"))
        #expect(Catalogo.Codice.salva == "Salva questo codice.")
    }

    @MainActor
    @Test("Aspetto: la dimensione del testo si cambia in «Impostazioni > Schermo e luminosità», giusto anche sull'iPad (#563)")
    func aspettoDimensioneDelTesto() {
        #expect(AspettoSezione.spiegaTema.hasPrefix(Catalogo.Asp.autoSpiega + " "))
        #expect(AspettoSezione.spiegaTema.contains("Impostazioni > Schermo e luminosità > Dimensione del testo"))
        #expect(!AspettoSezione.spiegaTema.contains("iPhone"), "sull'iPad le Impostazioni non sono «di iPhone»")
    }
}

/// Il codice Swift di un file dell'app (percorso dalla cartella `ios/`), senza commenti né anteprime.
private enum SorgenteAccesso {
    struct Errore: Error, CustomStringConvertible {
        let description: String
    }

    /// La cartella `ios/`.
    static func radice(file: String = #filePath) -> URL {
        var url = URL(fileURLWithPath: file)
        for _ in 0..<3 { url.deleteLastPathComponent() }          // AccessoImpostazioniDalCatalogoTests.swift, SchieraxiTests, Tests
        return url
    }

    static func codice(_ percorso: String, file: String = #filePath) throws -> String {
        guard let testo = try? String(contentsOf: radice(file: file).appendingPathComponent(percorso), encoding: .utf8) else {
            throw Errore(description: "non riesco a leggere ios/\(percorso)")
        }
        return soloCodice(testo)
    }

    /// Senza le righe di commento (`//`, `///`), i commenti in fondo alla riga e le anteprime (`#Preview("…")`).
    static func soloCodice(_ testo: String) -> String {
        testo.components(separatedBy: .newlines)
            .map { $0.trimmingCharacters(in: .whitespaces) }
            .filter { !$0.hasPrefix("//") && !$0.hasPrefix("#Preview") }
            .map { riga in riga.range(of: " //").map { String(riga[..<$0.lowerBound]) } ?? riga }
            .joined(separator: "\n")
    }
}
