import XCTest
@testable import Schieraxi

// La schermata di accesso e «Il tuo account» uguali alla web: passi, campi, controlli, testi. Recupero con l'email, posta spenta
// e passi del modulo: `AccessoComeLaWebTests` (Swift Testing).
// Solo nomi e indirizzi finti (example.invalid); le password sono di prova.

final class ModuloAccessoTests: XCTestCase {
    private let passwordBuona = "Prova-Finta-Zero"

    private func registrazione(_ modo: ModalitaRegistrazione = .invito) -> ModuloAccesso {
        var m = ModuloAccesso(scheda: .registrati)
        m.nome = "mister.rossi"
        m.password = passwordBuona
        if modo.invitoObbligatorio { m.invito = "INV-123" }
        if modo.chiedeEmail { m.email = "nome@example.invalid" }
        return m
    }

    // MARK: età minima e casella

    func testLaCasellaChiedeLEtaMinimaComeLaWeb() {
        XCTAssertEqual(TestiAccesso.etaMinima, 14)
        XCTAssertEqual(TestiAccesso.letto, "Ho letto Privacy e Termini d'uso e ho almeno 14 anni")
    }

    func testSenzaCasellaSiPremeMaSiSpiegaCosaManca() {
        var m = registrazione()
        XCTAssertTrue(m.pronto(.invito), "il resto è a posto: il pulsante è acceso, come sulla web")
        XCTAssertEqual(m.problemaPrimaDellInvio, TestiAccesso.spuntaLetto)
        m.accetto = true
        XCTAssertNil(m.problemaPrimaDellInvio)
        // la casella conta solo per registrarsi
        var accesso = ModuloAccesso(scheda: .accedi)
        accesso.nome = "mister.rossi"
        accesso.password = "x"
        XCTAssertNil(accesso.problemaPrimaDellInvio)
    }

    // MARK: campi e testi della registrazione

    func testCampiNellOrdineDellaWeb() {
        let m = ModuloAccesso(scheda: .registrati)
        XCTAssertEqual(m.campi(.invito), [.invito, .nome, .email, .password])
        XCTAssertEqual(m.campi(.email), [.invito, .nome, .email, .password])
        XCTAssertEqual(m.campi(.aperta), [.nome, .email, .password], "registrazione aperta: niente invito")
        XCTAssertEqual(ModuloAccesso(scheda: .accedi).campi(.invito), [.nome, .password])
    }

    // L'email facoltativa (etichetta breve, spiegazione sotto, controllo se c'è): `EtichetteCampiTests` (Swift Testing).

    func testConEmailOApertaLEmailServe() {
        for modo in [ModalitaRegistrazione.email, .aperta] {
            var m = registrazione(modo)
            XCTAssertTrue(m.pronto(modo), "\(modo)")
            m.email = ""
            XCTAssertFalse(m.pronto(modo), "\(modo): l'email è obbligatoria")
        }
        var conInvito = registrazione(.email)
        conInvito.invito = "  "
        XCTAssertFalse(conInvito.pronto(.email), "con il modo email serve anche l'invito")
    }

    func testPasswordENomeSiControllanoSoloQuandoSiSceglie() {
        var m = registrazione()
        m.password = "corta"
        XCTAssertNotNil(m.problemaPassword)
        XCTAssertFalse(m.pronto(.invito))
        m.nome = " mister "
        XCTAssertNotNil(m.problemaNome, "spazi ai lati: si chiede di toglierli quando si crea l'account")
        var accesso = ModuloAccesso(scheda: .accedi)
        accesso.nome = " Mister "
        accesso.password = "corta"
        XCTAssertNil(accesso.problemaNome, "per accedere il nome si sistema da solo")
        XCTAssertNil(accesso.problemaPassword, "per accedere la password non si giudica")
        XCTAssertTrue(accesso.pronto(.invito))
        XCTAssertEqual(accesso.etichettaPassword, "Password")
        XCTAssertEqual(m.etichettaPassword, "Password (almeno 10 caratteri)")
    }

    func testFrasiEPulsantiComeLaWeb() {
        XCTAssertEqual(ModuloAccesso(scheda: .accedi).titoloPulsante, "Accedi")
        XCTAssertNil(ModuloAccesso(scheda: .accedi).spiegazione(.invito), "niente frasi in più sull'accesso")
        let r = ModuloAccesso(scheda: .registrati)
        XCTAssertEqual(r.titoloPulsante, "Crea l'account")
        XCTAssertEqual(r.spiegazione(.invito), "Ti serve un codice d'invito: chiedilo a chi ti ha invitato.")
        XCTAssertEqual(r.spiegazione(.aperta), "Scrivi la tua email: ti mandiamo un codice per confermarla e creare l'account.")
        var v = r
        v.iscrizione = IscrizioneInAttesa(email: "nome@example.invalid", iscrizione: "finta")
        XCTAssertEqual(v.passo, .verificaIscrizione)
        XCTAssertEqual(v.titoloPulsante, "Conferma e crea l'account")
        XCTAssertEqual(v.campi(.email), [.codiceEmail])
        XCTAssertTrue(v.spiegazione(.email)?.contains("nome@example.invalid") ?? false)
        XCTAssertFalse(v.pronto(.email))
        v.codiceEmail = "123456"
        XCTAssertTrue(v.pronto(.email))
    }

    // MARK: password dimenticata

    func testPasswordDimenticataPartiteDalMetodoDellaWeb() {
        var m = ModuloAccesso(scheda: .accedi)
        m.password = "scritta"
        m.vai(.recupera, modo: .invito)
        XCTAssertEqual(m.metodo, .codice, "con gli inviti si parte dal codice di recupero")
        XCTAssertEqual(m.password, "", "la password scritta non resta")
        XCTAssertTrue(m.mostraMetodi())
        m.vai(.recupera, modo: .email)
        XCTAssertEqual(m.metodo, .email)
        XCTAssertEqual(MetodoRecupero.iniziale(.aperta), .email)
        XCTAssertEqual(MetodoRecupero.email.titolo, "Con l'email")
        XCTAssertEqual(MetodoRecupero.codice.titolo, "Con il codice di recupero")
        XCTAssertEqual(SchermataAccesso.Scheda.recupera.rawValue, "Password dimenticata")
    }

    func testRecuperoConIlCodice() {
        var m = ModuloAccesso(scheda: .recupera, metodo: .codice)
        XCTAssertEqual(m.passo, .recuperoCodice)
        XCTAssertEqual(m.campi(.invito), [.nome, .codice, .password])
        XCTAssertEqual(m.titoloPulsante, "Scegli la nuova password")
        XCTAssertEqual(m.etichettaPassword, "Nuova password (almeno 10 caratteri)")
        XCTAssertFalse(m.pronto(.invito))
        m.nome = "mister.rossi"
        m.codice = "AAAAA-BBBBB"
        m.password = "corta"
        XCTAssertFalse(m.pronto(.invito), "la nuova password deve andare bene")
        m.password = passwordBuona
        XCTAssertTrue(m.pronto(.invito))
    }

    func testRecuperoConLEmailInDuePassi() {
        var m = ModuloAccesso(scheda: .recupera, metodo: .email)
        XCTAssertEqual(m.passo, .recuperoEmail)
        XCTAssertEqual(m.campi(.email), [.email])
        XCTAssertEqual(m.titoloPulsante, "Mandami il codice")
        XCTAssertFalse(m.pronto(.email))
        m.email = "nome@example"
        XCTAssertFalse(m.pronto(.email))
        m.email = "nome@example.invalid"
        XCTAssertTrue(m.pronto(.email))
        // il codice è partito
        m.emailRecupero = "nome@example.invalid"
        XCTAssertEqual(m.passo, .recuperoEmailCodice)
        XCTAssertFalse(m.mostraMetodi(), "al secondo passo la scelta del metodo sparisce, come sulla web")
        XCTAssertEqual(m.campi(.email), [.codiceEmail, .password])
        XCTAssertEqual(m.titoloPulsante, "Scegli la nuova password")
        XCTAssertEqual(m.spiegazione(.email), "Scrivi il codice arrivato a nome@example.invalid e scegli la nuova password.")
        XCTAssertFalse(m.pronto(.email))
        m.codiceEmail = "123456"
        m.password = "1234567890"
        XCTAssertFalse(m.pronto(.email), "solo numeri non va")
        m.password = passwordBuona
        XCTAssertTrue(m.pronto(.email))
        // tornando all'accesso e poi di nuovo qui si riparte dal primo passo
        m.vai(.accedi, modo: .email)
        m.vai(.recupera, modo: .email)
        XCTAssertEqual(m.passo, .recuperoEmail)
        XCTAssertEqual(m.codiceEmail, "")
    }

    // MARK: Il tuo account

    func testRuoloEDataDiIscrizioneComeLaWeb() {
        XCTAssertEqual(TestiAccount.ruoloEData(ruolo: "utente", creato: "2026-09-01T08:30:00+00:00"), "Utente · dal 1 settembre 2026")
        XCTAssertEqual(TestiAccount.ruoloEData(ruolo: "amministratore", creato: "2026-09-01"), "Amministratore · dal 1 settembre 2026")
        XCTAssertEqual(TestiAccount.ruoloEData(ruolo: "utente", creato: "2026-08-31T23:30:00+00:00"), "Utente · dal 1 settembre 2026",
                       "la data è quella italiana")
        XCTAssertEqual(TestiAccount.ruoloEData(ruolo: "utente", creato: "2026-09-01 10:00"), "Utente · dal 1 settembre 2026")
        XCTAssertEqual(TestiAccount.ruoloEData(ruolo: "utente", creato: nil), "Utente", "senza data resta il ruolo")
        XCTAssertEqual(TestiAccount.ruoloEData(ruolo: "utente", creato: "ieri"), "Utente")
    }

    func testRigaDellEmailConLeFrasiDellaWeb() {
        XCTAssertEqual(TestiAccount.rigaEmail(account: "a@example.invalid", google: "g@example.invalid", inAttesa: nil), "Email confermata: a@example.invalid")
        XCTAssertEqual(TestiAccount.rigaEmail(account: nil, google: "g@example.invalid", inAttesa: nil), "Email da Google: g@example.invalid")
        XCTAssertEqual(TestiAccount.rigaEmail(account: " ", google: nil, inAttesa: "x@example.invalid"), "In attesa di conferma: x@example.invalid")
        XCTAssertEqual(TestiAccount.rigaEmail(account: nil, google: nil, inAttesa: nil), "Nessuna email collegata.")
    }

    func testTestiDellAccountComeLaWeb() {
        XCTAssertEqual(TestiAccount.cambiaPassword, "Cambia la password")
        XCTAssertEqual(TestiAccount.recupero, "Codice di recupero")
        XCTAssertEqual(TestiAccount.nuovoCodice, "Genera un nuovo codice")
        XCTAssertEqual(TestiAccount.ripetiPassword, "Ripeti la nuova password", "come `account.ripeti_password` della web")
        XCTAssertEqual(TestiAccount.elimina, "Elimina il mio account")
    }
}
