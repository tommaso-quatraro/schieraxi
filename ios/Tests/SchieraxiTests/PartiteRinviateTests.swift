import XCTest
@testable import Schieraxi

/// Partite rinviate (campo `rinvio` di Oggi, `riepilogo.recuperi` e `riepilogo.rinvio`, `PUT /api/regole/rinvio`): lettura tollerante,
/// testi uguali alla web app e corpo della richiesta.
final class PartiteRinviateTests: XCTestCase {
    private func oggi(_ json: String) throws -> Oggi { try Decodifica.decodifica(Data(json.utf8)) }

    private let conRinvio = #"""
    {"giornata": 10, "giornata_lega": 7, "fase": "prima",
     "partite": [{"data": "2026-11-25 20:45", "casa": "atalanta", "trasferta": "parma", "giocata": false, "stato": "rinviata"}],
     "rinvio": {"stagione": "2026-27", "giornata": 10, "giornata_lega": 7, "modo": "voto_ufficio", "valore": 5.5, "predefinito": "aspetta",
                "eccezione": true, "modi": ["aspetta", "senza_voto", "voto_ufficio"], "voto_ufficio": 5.5,
                "partite": [{"casa": "atalanta", "trasferta": "parma", "data": "2026-11-25 20:45"}, {"casa": "como", "trasferta": "milan", "data": null}],
                "miei": [{"id": 6844, "nome": "Ruben Tescari", "ruolo": "C", "squadra": "atalanta"}, {"nome": "senza id"}]}}
    """#

    func testIlRinvioDiOggiSiLegge() throws {
        let r = try XCTUnwrap(try oggi(conRinvio).partiteRinviate)
        XCTAssertEqual(r.giornata, 10)
        XCTAssertEqual(r.stagione, "2026-27")
        XCTAssertEqual(r.modo, ModoRinvio.votoUfficio)
        XCTAssertEqual(r.predefinito, ModoRinvio.aspetta)
        XCTAssertTrue(r.eccezione)
        XCTAssertEqual(r.votoUfficio, 5.5)
        XCTAssertEqual(r.partite.map(\.id), ["atalanta-parma", "como-milan"])
        XCTAssertNil(r.partite.last?.data)
        XCTAssertEqual(r.miei.map(\.id), [6844], "l'elemento senza id si salta")
    }

    func testServerVecchioOCampoStranoNonRompeOggi() throws {
        XCTAssertNil(try oggi(#"{"giornata": 9}"#).partiteRinviate)
        XCTAssertNil(try oggi(#"{"giornata": 9, "rinvio": null}"#).partiteRinviate)
        let strano = try oggi(#"{"giornata": 9, "rinvio": "boh"}"#)
        XCTAssertEqual(strano.giornata, 9)
        XCTAssertNil(strano.partiteRinviate)
        let senzaPartite = try oggi(#"{"giornata": 9, "rinvio": {"giornata": 9, "modo": "aspetta"}}"#)
        XCTAssertNil(senzaPartite.partiteRinviate, "senza partite niente riquadro")
        let r = try XCTUnwrap(senzaPartite.rinvio?.valore)
        XCTAssertEqual(r.modi, ModoRinvio.tutti, "senza `modi` valgono le tre scelte")
        XCTAssertFalse(r.eccezione)
    }

    func testRiepilogoConIRecuperiEIlMenu() throws {
        let o = try oggi(#"""
        {"giornata": 11, "fase": "finita",
         "riepilogo": {"giornata": 10, "giornata_lega": 7, "formazione_di": "tua", "nel_diario": false, "punti_fatti": 61,
                       "recuperi": [{"casa": "atalanta", "trasferta": "parma", "data": null}],
                       "rinvio": {"stagione": "2026-27", "giornata": 10, "modo": "aspetta", "predefinito": "aspetta", "eccezione": false, "voto_ufficio": 6}}}
        """#)
        let r = try XCTUnwrap(o.riepilogoGiornata)
        XCTAssertEqual(r.recuperi.map(\.id), ["atalanta-parma"])
        XCTAssertEqual(r.rinvio?.giornata, 10)
        XCTAssertEqual(TestiRinvio.recuperoManca(r.recuperi), "Manca il recupero di ATA–PAR: i punti possono ancora cambiare.")
        let vecchio = try oggi(#"{"giornata": 11, "fase": "finita", "riepilogo": {"giornata": 10, "punti_fatti": 61, "recuperi": 3, "rinvio": []}}"#)
        XCTAssertEqual(vecchio.riepilogoGiornata?.recuperi, [])
        XCTAssertNil(vecchio.riepilogoGiornata?.rinvio)
        XCTAssertEqual(vecchio.riepilogoGiornata?.puntiFatti, 61, "campi sbagliati non rompono il riepilogo")
        XCTAssertNil(TestiRinvio.recuperoManca([]))
    }

    func testTestiUgualiAllaWeb() {
        XCTAssertEqual(TestiRinvio.titolo(1), "Partita rinviata")
        XCTAssertEqual(TestiRinvio.titolo(2), "Partite rinviate")
        XCTAssertEqual(TestiRinvio.nomeModo(ModoRinvio.aspetta, voto: 6), "aspettano il recupero (conta il suo voto)")
        XCTAssertEqual(TestiRinvio.nomeModo(ModoRinvio.senzaVoto, voto: 6), "restano senza voto (entra la riserva)")
        XCTAssertEqual(TestiRinvio.nomeModo(ModoRinvio.votoUfficio, voto: 6), "prendono il voto d'ufficio (6)")
        XCTAssertEqual(TestiRinvio.nomeModo(ModoRinvio.votoUfficio, voto: 5.5), "prendono il voto d'ufficio (5,5)")
        XCTAssertEqual(TestiRinvio.nomeModo("nuovo", voto: nil), "nuovo", "un modo sconosciuto si mostra com'è")
        XCTAssertEqual(TestiRinvio.recupero(PartitaRinviata(casa: "a", trasferta: "b", data: nil)), "recupero da definire")
        XCTAssertTrue(TestiRinvio.recupero(PartitaRinviata(casa: "a", trasferta: "b", data: "2026-11-25 20:45")).hasPrefix("recupero "))
        let s = SceltaRinvio(giornata: 10, modo: ModoRinvio.votoUfficio, predefinito: ModoRinvio.aspetta, eccezione: true,
                             miei: [GiocatoreRinviato(id: 1, nome: "Ruben Tescari"), GiocatoreRinviato(id: 2, nome: "Amos Delvecchio")])
        XCTAssertEqual(TestiRinvio.nota(s), "Scelta solo per questa giornata. Di solito la tua lega: aspettano il recupero (conta il suo voto).")
        XCTAssertEqual(TestiRinvio.miei(s), "I tuoi giocatori coinvolti: Ruben Tescari, Amos Delvecchio")
        XCTAssertTrue(TestiRinvio.nota(SceltaRinvio(giornata: 10, modo: ModoRinvio.aspetta)).hasPrefix("È la regola della tua lega"))
        XCTAssertEqual(TestiRinvio.etichetta(ModoRinvio.votoUfficio), "Voto d'ufficio")
    }

    func testCorpoDellaRichiesta() throws {
        let pieno = try JSONSerialization.jsonObject(with: JSONEncoder().encode(CorpoRinvio(giornata: 10, modo: "senza_voto", stagione: "2026-27"))) as? [String: Any]
        XCTAssertEqual(pieno?["giornata"] as? Int, 10)
        XCTAssertEqual(pieno?["modo"] as? String, "senza_voto")
        XCTAssertEqual(pieno?["stagione"] as? String, "2026-27")
        let torna = try JSONSerialization.jsonObject(with: JSONEncoder().encode(CorpoRinvio(giornata: 10, modo: nil, stagione: nil))) as? [String: Any]
        XCTAssertNil(torna?["modo"], "modo assente = torna alla regola della lega")
    }

    @MainActor
    func testIlMenuMandaLaSceltaEStessaRegolaTogliLEccezione() async throws {
        let server = ServerDiProva { _, _, _ in Data(#"{"stagione": "2026-27", "giornata": 10, "modo": "senza_voto", "eccezione": true}"#.utf8) }
        let vm = OggiViewModel(server: server, conPromemoria: false)
        let s = SceltaRinvio(stagione: "2026-27", giornata: 10, modo: ModoRinvio.votoUfficio, predefinito: ModoRinvio.aspetta, eccezione: true)
        await vm.cambiaRinvio(s, modo: ModoRinvio.senzaVoto)
        await vm.cambiaRinvio(s, modo: ModoRinvio.aspetta)          // = regola della lega: si toglie l'eccezione (modo assente)
        await vm.cambiaRinvio(s, modo: ModoRinvio.votoUfficio)      // già questa: nessuna richiesta
        let corpi = server.corpiInviati(a: "/api/regole/rinvio").compactMap { try? JSONSerialization.jsonObject(with: $0) as? [String: Any] }
        XCTAssertEqual(server.quante("PUT /api/regole/rinvio"), 2)
        XCTAssertEqual(corpi.first?["modo"] as? String, "senza_voto")
        XCTAssertEqual(corpi.first?["giornata"] as? Int, 10)
        XCTAssertNil(corpi.last?["modo"])
        XCTAssertNil(vm.erroreRinvio)
        XCTAssertFalse(vm.rinvioInCorso)
    }

    @MainActor
    func testErroreDelServerSiMostra() async throws {
        let vm = OggiViewModel(server: ServerDiProva.chePrecipita(), conPromemoria: false)
        await vm.cambiaRinvio(SceltaRinvio(giornata: 10, modo: ModoRinvio.aspetta, predefinito: ModoRinvio.aspetta), modo: ModoRinvio.senzaVoto)
        XCTAssertNotNil(vm.erroreRinvio)
    }
}
