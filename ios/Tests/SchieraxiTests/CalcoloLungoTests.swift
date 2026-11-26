import XCTest
@testable import Schieraxi

/// Una risposta della rete finta, con «riprova subito» per i 202.
private func rispostaFinta(_ r: URLRequest, _ codice: Int) -> HTTPURLResponse {
    HTTPURLResponse(url: r.url ?? URL(fileURLWithPath: "/"), statusCode: codice, httpVersion: nil, headerFields: ["Retry-After": "0"])
        ?? HTTPURLResponse()
}

/// Il calcolo del server che dura (risposta 202, #931 punto 4), come `api()` e `mostraCalcolo` della web: mentre si aspetta c'è la
/// frase «Un attimo, mister: ci sto lavorando.» (`comune.calcolo_attesa`), e quando si smette di aspettare l'errore è
/// `comune.calcolo_lungo`, non una frase scritta a mano. Rete finta (`ProtocolloFinto`), nessun server vero.
final class CalcoloLungoTests: XCTestCase {
    /// Mette l'indirizzo di prova e toglie le risposte di altri test; la funzione restituita rimette com'era.
    private func prepara() -> () -> Void {
        let prima = UserDefaults.standard.string(forKey: "indirizzo")
        UserDefaults.standard.set("https://prova-calcolo.invalid", forKey: "indirizzo")
        ProtocolloFinto.gestore = nil
        return {
            if let prima { UserDefaults.standard.set(prima, forKey: "indirizzo") } else { UserDefaults.standard.removeObject(forKey: "indirizzo") }
            ProtocolloFinto.gestore = nil
        }
    }

    private func server(_ attesa: AttesaCalcolo, tentativi: Int = 3) -> ServerHTTP {
        let configurazione = URLSessionConfiguration.ephemeral
        configurazione.protocolClasses = [ProtocolloFinto.self]
        return ServerHTTP(sessione: URLSession(configuration: configurazione), archivioToken: MemoriaToken(), attesaCalcolo: 0.01,
                          massimoTentativiCalcolo: tentativi, attesa: attesa)
    }

    /// Quante attese sono cominciate e se ce n'è ancora una in corso (il contatore vive sul MainActor).
    private func stato(_ attesa: AttesaCalcolo) async -> (cominciate: Int, inCorso: Bool) {
        await MainActor.run { (attesa.cominciate, attesa.inCorso) }
    }

    func testCalcoloCheNonFinisceDiceLaFraseDellaWeb() async {
        let ripristina = prepara()
        defer { ripristina() }
        let attesa = await MainActor.run { AttesaCalcolo() }
        ProtocolloFinto.gestore = { r in (rispostaFinta(r, 202), Data(#"{"calcolo": "in_corso"}"#.utf8)) }
        do {
            _ = try await server(attesa).grezzo("/api/formazione")
            XCTFail("dopo i tentativi si smette di aspettare")
        } catch {
            XCTAssertEqual(error.localizedDescription, Catalogo.Comune.calcoloLungo)
        }
        let s = await stato(attesa)
        XCTAssertEqual(s.cominciate, 1, "un'attesa sola per richiesta, non una per tentativo")
        XCTAssertFalse(s.inCorso, "smesso di aspettare, la frase d'attesa se ne va")
    }

    func testCalcoloCheFinisceMostraLaFraseSoloMentreAspetta() async throws {
        let ripristina = prepara()
        defer { ripristina() }
        let attesa = await MainActor.run { AttesaCalcolo() }
        let domande = Contatore()
        ProtocolloFinto.gestore = { r in
            domande.passo() == 0 ? (rispostaFinta(r, 202), Data(#"{"calcolo": "in_corso"}"#.utf8)) : (rispostaFinta(r, 200), Data(#"{"ok": true}"#.utf8))
        }
        let dati = try await server(attesa).grezzo("/api/formazione")
        XCTAssertEqual(String(decoding: dati, as: UTF8.self), #"{"ok": true}"#)
        let s = await stato(attesa)
        XCTAssertEqual(s.cominciate, 1)
        XCTAssertFalse(s.inCorso)
    }

    func testRispostaSubitoNessunaAttesa() async throws {
        let ripristina = prepara()
        defer { ripristina() }
        let attesa = await MainActor.run { AttesaCalcolo() }
        ProtocolloFinto.gestore = { r in (rispostaFinta(r, 200), Data("{}".utf8)) }
        _ = try await server(attesa).grezzo("/api/oggi")
        let s = await stato(attesa)
        XCTAssertEqual(s.cominciate, 0)
        XCTAssertFalse(s.inCorso)
    }
}

/// Il contatore dell'attesa, come `inAttesa` della web: la frase resta finché c'è una richiesta che aspetta, e non va mai sotto zero.
@MainActor
final class AttesaCalcoloContaTests: XCTestCase {
    func testDueAtteseInsiemeLaFraseResta() {
        let attesa = AttesaCalcolo()
        attesa.inizia()
        attesa.inizia()
        attesa.finisce()
        XCTAssertTrue(attesa.inCorso, "un'altra richiesta aspetta ancora, come il contatore della web")
        attesa.finisce()
        attesa.finisce()
        XCTAssertFalse(attesa.inCorso)
        XCTAssertEqual(attesa.attese, 0, "mai sotto zero")
        XCTAssertEqual(attesa.cominciate, 2)
    }
}

/// «Aggiorna i dati» che dura più del solito (#931 punto 9): come `aggiornaDati` della web l'iPhone continua a controllare finché
/// il server non ha finito, e alla fine dice com'è andata; prima smetteva dopo 150 domande con una frase scritta a mano.
@MainActor
final class AggiornamentoLungoTests: XCTestCase {
    func testAggiornamentoLungoSiSegueFinoAllaFine() async {
        let domande = Contatore()
        let s = ServerDiProva { metodo, _, _ in
            if metodo == "POST" { return Data(#"{"avviato": true}"#.utf8) }
            if domande.passo() < 200 { return Data(#"{"in_corso": true, "errori": []}"#.utf8) }
            return Data(#"{"in_corso": false, "errori": []}"#.utf8)
        }
        let vm = AggiornaDatiViewModel(server: s)
        vm.pausa = 0
        await vm.avvia()
        XCTAssertEqual(vm.messaggio, Catalogo.Aggiorna.ok)
        XCTAssertEqual(s.quante("GET /api/aggiorna"), 201)
        XCTAssertFalse(vm.pulsanteSpento)
    }
}

/// Informazioni › Versione (#931 punto 3): la versione del server come la web, con la lineetta della web quando manca, e sotto
/// quella dell'app (solo iPhone, differenza ammessa).
final class VersioniInformazioniTests: XCTestCase {
    func testDueRigheConINomiDelCatalogo() {
        let righe = VersioniInformazioni.righe(server: "1.574", app: "1.0.12")
        XCTAssertEqual(righe.map(\.titolo), [Catalogo.Info.versione, Catalogo.Info.versioneApp])
        XCTAssertEqual(righe.map(\.valore), ["1.574", "1.0.12"])
    }

    func testSenzaVersioneLaLineettaDellaWeb() {
        let righe = VersioniInformazioni.righe(server: nil, app: "  ")
        XCTAssertEqual(righe.map(\.valore), ["–", "–"], "la lineetta corta della web («–»), non quella lunga")
    }
}
