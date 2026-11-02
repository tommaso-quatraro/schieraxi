import XCTest
@testable import Schieraxi

final class NuovaVersioneTests: XCTestCase {
    func testNumeroDalTag() {
        XCTAssertEqual(NuovaVersione.numero(daTag: "build-37"), 37)
        XCTAssertNil(NuovaVersione.numero(daTag: "v1.2"))
    }

    func testSoloUnaBuildPiuNuovaVieneSegnalata() {
        XCTAssertEqual(NuovaVersione.piuNuova(tag: "build-38", installata: 37), 38)
        XCTAssertNil(NuovaVersione.piuNuova(tag: "build-37", installata: 37))   // stessa build: niente
        XCTAssertNil(NuovaVersione.piuNuova(tag: "build-36", installata: 37))   // più vecchia: niente
        XCTAssertNil(NuovaVersione.piuNuova(tag: "strano", installata: 1))      // tag non riconosciuto: niente
    }

    private func elenco(_ json: String) -> Data { Data(json.utf8) }

    func testElencoMisto_PrendeLaBuildPiuAltaEIgnoraLeReleaseDelServer() {
        // La «latest» del repository unico può essere una release del server: qui v1.251 sta in cima, ma conta solo build-N.
        let json = #"[{"tag_name":"v1.251"},{"tag_name":"build-214"},{"tag_name":"v1.250"},{"tag_name":"build-216"},{"tag_name":"build-9"}]"#
        XCTAssertEqual(NuovaVersione.tagPiuAlto(elenco: elenco(json)), "build-216")
    }

    func testElencoConNumeriDiversiDiCifre_ConfrontaNumeriNonTesto() {
        XCTAssertEqual(NuovaVersione.tagPiuAlto(elenco: elenco(#"[{"tag_name":"build-99"},{"tag_name":"build-100"}]"#)), "build-100")
    }

    func testBozzePrereleaseETagStrani_SiIgnorano() {
        let json = #"[{"tag_name":"build-300","draft":true},{"tag_name":"build-301","prerelease":true},{"tag_name":"build-abc"},{"tag_name":"xbuild-400"},{"nome":"senza tag"},{"tag_name":"build-215"}]"#
        XCTAssertEqual(NuovaVersione.tagPiuAlto(elenco: elenco(json)), "build-215")
    }

    func testElencoVuotoIllegibileOSenzaBuild_DaNil() {
        XCTAssertNil(NuovaVersione.tagPiuAlto(elenco: elenco("[]")))
        XCTAssertNil(NuovaVersione.tagPiuAlto(elenco: elenco("non è json")))
        XCTAssertNil(NuovaVersione.tagPiuAlto(elenco: elenco(#"{"message":"Not Found"}"#)))   // risposta d'errore: un oggetto, non un elenco
        XCTAssertNil(NuovaVersione.tagPiuAlto(elenco: elenco(#"[{"tag_name":"v1.250"}]"#)))
    }

    func testIndirizzoPuntaAlRepositoryUnicoEdElencaLeRelease() {
        XCTAssertEqual(NuovaVersione.indirizzo, "https://api.github.com/repos/tommaso-quatraro/schieraxi/releases?per_page=30")
        XCTAssertNotNil(URL(string: NuovaVersione.indirizzo))
    }
}
