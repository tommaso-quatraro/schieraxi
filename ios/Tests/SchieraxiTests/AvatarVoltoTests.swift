import XCTest
import SwiftUI
@testable import Schieraxi

/// Gli avatar illustrati devono dare GLI STESSI indici di web e Android (vettori di docs/AVATAR.md).
final class GeneratoreVoltoTests: XCTestCase {
    /// Le dieci parti della versione 1 (le nove della versione 3 si provano a parte, con `VETTORE3`).
    private func indici(_ v: [Int]) -> [Int] { v }

    func testIVettoriDellaSpecifica() {
        let vettori: [Int: [Int]] = [
            1: [2, 0, 10, 0, 3, 1, 0, 1, 0, 1],
            2: [2, 0, 0, 1, 4, 0, 0, 1, 0, 0],
            3: [2, 2, 7, 7, 0, 0, 0, 0, 0, 0],
            100: [2, 2, 2, 7, 3, 0, 1, 0, 1, 1],
            4567: [2, 0, 0, 7, 0, 2, 2, 0, 0, 0],
            7627: [2, 0, 4, 1, 2, 1, 2, 0, 0, 0],
        ]
        for (id, atteso) in vettori {
            XCTAssertEqual(GeneratoreVolto.estrai(id: id).elenco, indici(atteso), "id \(id)")
        }
    }

    func testLeRegoleDiCoerenza() {
        // 140: orecchino (2) con acconciatura lunga (4) -> nessun accessorio; 170: fascia (1) con cresta (7) -> nessuno
        XCTAssertEqual(GeneratoreVolto.estraiGrezzo(id: 140).elenco, indici([2, 2, 4, 3, 1, 2, 0, 1, 2, 1]))
        XCTAssertEqual(GeneratoreVolto.estrai(id: 140).elenco, indici([2, 2, 4, 3, 1, 2, 0, 1, 0, 1]))
        XCTAssertEqual(GeneratoreVolto.estraiGrezzo(id: 170).elenco, indici([2, 2, 7, 7, 1, 1, 0, 1, 1, 0]))
        XCTAssertEqual(GeneratoreVolto.estrai(id: 170).elenco, indici([2, 2, 7, 7, 1, 1, 0, 1, 0, 0]))
    }

    func testMulberry32() {
        var a = GeneratoreVolto.Mulberry32(seme: 12345)
        for atteso in [0.9797282678, 0.3067522645, 0.4842054215] {
            XCTAssertEqual(a.prossimo(), atteso, accuracy: 1e-9)
        }
        var b = GeneratoreVolto.Mulberry32(seme: 0)
        for atteso in [0.2664292087, 0.0003297457] {
            XCTAssertEqual(b.prossimo(), atteso, accuracy: 1e-9)
        }
    }

    func testUnIdNonValidoVaLettoComeZero() {
        XCTAssertEqual(GeneratoreVolto.estrai(id: -5), GeneratoreVolto.estrai(id: 0))
        XCTAssertEqual(GeneratoreVolto.estrai(id: 5_000_000_000), GeneratoreVolto.estrai(id: 0))
        XCTAssertEqual(GeneratoreVolto.estrai(id: 4_294_967_295), GeneratoreVolto.estrai(id: 4_294_967_295), "il massimo è valido")
    }

    func testIVettoriDellaVersione3() {
        // docs/AVATAR.md, sezione 9: espressione, ritocco capelli, guance, rughe, naso, sfondo, maglia, colletto, spalle
        let vettori: [Int: [Int]] = [
            1: [2, 1, 0, 0, 1, 2, 3, 2, 0],
            2: [2, 2, 0, 0, 2, 3, 0, 0, 0],
            3: [0, 1, 1, 0, 1, 2, 1, 1, 0],
            100: [0, 1, 0, 0, 1, 2, 0, 0, 1],
            4567: [0, 0, 0, 0, 2, 3, 0, 0, 0],
            7627: [1, 2, 0, 0, 0, 0, 3, 0, 1],
        ]
        for (id, atteso) in vettori {
            XCTAssertEqual(GeneratoreVolto.estrai(id: id).elenco3, atteso, "id \(id)")
        }
    }

    func testITrattiNonToccanoLeNoveEstrazioniDellaVersione3() {
        let tratti = TrattiVolto(p: 4, c: 5, a: "C", b: 1, f: 1)
        for id in [1, 2, 3, 100, 4567, 7627] {
            XCTAssertEqual(GeneratoreVolto.estrai(id: id, tratti: tratti).elenco3, GeneratoreVolto.estrai(id: id).elenco3, "id \(id)")
        }
    }

    func testIPesiFannoCento() {
        for pesi in [GeneratoreVolto.pesiPelle, GeneratoreVolto.pesiForma, GeneratoreVolto.pesiAcconciatura, GeneratoreVolto.pesiColore,
                     GeneratoreVolto.pesiBarba, GeneratoreVolto.pesiSopracciglia, GeneratoreVolto.pesiOcchi, GeneratoreVolto.pesiBocca,
                     GeneratoreVolto.pesiAccessorio, GeneratoreVolto.pesiOrecchie,
                     GeneratoreVolto.pesiEspressione, GeneratoreVolto.pesiRitocco, GeneratoreVolto.pesiGuance, GeneratoreVolto.pesiRughe,
                     GeneratoreVolto.pesiNaso, GeneratoreVolto.pesiSfondo, GeneratoreVolto.pesiMaglia, GeneratoreVolto.pesiColletto,
                     GeneratoreVolto.pesiSpalle] {
            XCTAssertEqual(pesi.reduce(0, +), 100)
        }
    }

    func testIVoltiSonoQuasiTuttiDiversi() {
        let diversi = Set((1...3000).map { GeneratoreVolto.estrai(id: $0).elenco })
        XCTAssertGreaterThan(diversi.count, 2900, "con la pelle fissa la specifica dichiara 2928 volti diversi su 3000 codici (soglia della web: 2900)")
    }

    func testIColoriDerivatiConLArrotondamentoDellaSpecifica() {
        XCTAssertEqual(RGB8("#f6d5bd").scuri(0.14), RGB8(r: 212, g: 183, b: 163))   // floor(c * .86 + .5)
        XCTAssertEqual(RGB8("#000000").misce(RGB8("#ffffff"), 0.5), RGB8(r: 128, g: 128, b: 128))   // floor(255 * .5 + .5)
        XCTAssertEqual(RGB8("#ffffff").luminanza, 1, accuracy: 1e-9)
        XCTAssertEqual(RGB8("#000000").luminanza, 0, accuracy: 1e-9)
        XCTAssertEqual(RGB8("#1e71b8").esadecimale, "#1e71b8")
        XCTAssertEqual(RGB8("non un colore"), RGB8("#6b7280"), "un colore sbagliato dà il grigio")
    }

    func testLoSfondoSegueLaLuminanzaDellaMaglia() {
        // maglia chiara (juventus #f3f4f6): scura di .55 / .3, poi mescolata col secondo colore
        let chiara = GeneratoreVolto.sfondo(c1: RGB8("#f3f4f6"), c2: RGB8("#111827"))
        XCTAssertEqual(chiara.1, RGB8("#f3f4f6").scuri(0.3))
        XCTAssertEqual(chiara.0, RGB8("#f3f4f6").scuri(0.55).misce(RGB8("#111827"), 0.22))
        // maglia molto scura: si schiarisce
        let scura = GeneratoreVolto.sfondo(c1: RGB8("#0b2a52"), c2: RGB8("#111827"))
        XCTAssertEqual(scura.1, RGB8("#0b2a52").misce(RGB8("#ffffff"), 0.12))
    }
}

final class DisegnoVoltoTests: XCTestCase {
    func testIPercorsiSVG() {
        XCTAssertEqual(PercorsoSVG.path("M0 0H10V10H0Z").boundingRect, CGRect(x: 0, y: 0, width: 10, height: 10))
        // S riflette il secondo controllo precedente; numeri negativi
        let curva = PercorsoSVG.path("M0 0C0 10 10 10 10 0S20 -10 20 0")
        XCTAssertEqual(curva.boundingRect.maxX, 20, accuracy: 0.01)
        XCTAssertLessThan(curva.boundingRect.minY, 0)
        XCTAssertFalse(PercorsoSVG.path("M10 100C12 84 28 77 50 77S88 84 90 100Z").isEmpty)
        // più sottopercorsi
        let due = PercorsoSVG.path("M40 29Q42 22 46 19.5M50 28V19.5M60 29Q58 22 54 19.5")
        XCTAssertEqual(due.boundingRect.minX, 40, accuracy: 0.01)
        XCTAssertEqual(due.boundingRect.maxX, 60, accuracy: 0.01)
        XCTAssertTrue(PercorsoSVG.path("").isEmpty)
        _ = PercorsoSVG.path("M1")   // numeri mancanti: niente crash
    }

    func testOgniVoltoHaIlSuoDisegnoEIPortieriIGuanti() {
        let c1 = RGB8("#0a58a8"), c2 = RGB8("#111827")
        for id in 0..<400 {
            let campo = DisegnoVolto.elementi(id: id, portiere: false, c1: c1, c2: c2)
            let portiere = DisegnoVolto.elementi(id: id, portiere: true, c1: c1, c2: c2)
            XCTAssertGreaterThan(campo.count, 8, "id \(id)")
            // il portiere ha sempre la maglia grigia senza disegno: i due guanti (4 forme) sostituiscono il disegno della maglia
            let disegnoMaglia: Int = [0, 5, 1, 1][GeneratoreVolto.estrai(id: id).maglia]
            XCTAssertEqual(portiere.count, campo.count + 4 - disegnoMaglia, "due guanti con due linee ciascuno (id \(id))")
        }
    }

    func testIlNumeroDiMagliaSiDisegnaSoloTra1E99() {
        let c1 = RGB8("#0a58a8"), c2 = RGB8("#111827")
        let base = DisegnoVolto.elementi(id: 5, portiere: false, c1: c1, c2: c2).count
        XCTAssertEqual(DisegnoVolto.elementi(id: 5, portiere: false, c1: c1, c2: c2, numero: 10).count, base + 1)
        for fuori in [0, 100, -3] {
            XCTAssertEqual(DisegnoVolto.elementi(id: 5, portiere: false, c1: c1, c2: c2, numero: fuori).count, base)
        }
    }

    func testIlColoreDellaSquadraEQuelloDellaWeb() {
        let (a, b) = DisegnoVolto.coloriSquadra("inter")
        XCTAssertEqual(a, RGB8("#0a58a8"))
        XCTAssertEqual(b, RGB8("#111827"))
        let (g1, g2) = DisegnoVolto.coloriSquadra(nil)
        XCTAssertEqual(g1, RGB8("#6b7280"))
        XCTAssertEqual(g2, RGB8("#e5e7eb"))
    }

    @MainActor
    func testIlVoltoSiDisegnaAdOgniDimensione() {
        for lato in [24.0, 40.0, 92.0] {
            let r = ImageRenderer(content: AvatarVolto(id: 4567, squadra: "milan", portiere: false).frame(width: lato, height: lato))
            r.scale = 1
            XCTAssertNotNil(r.uiImage, "lato \(lato)")
        }
    }
}

/// Avatar versione 2: tratti grossolani (docs/AVATAR.md, sezione 8, VETTORE2).
@MainActor
final class AvatarVersione2Tests: XCTestCase {
    private func tratti(_ json: String) -> TrattiVolto? { try? JSONDecoder().decode(TrattiVolto.self, from: Data(json.utf8)) }

    private func elenco(_ id: Int, _ json: String?) -> [Int] {
        GeneratoreVolto.estrai(id: id, tratti: json.flatMap { tratti($0) }).elenco
    }

    func testIVettoriDellaSezione8() {
        // docs/AVATAR.md, sezione 8 (VETTORE2): stessi numeri della web
        XCTAssertEqual(elenco(1, #"{"p":4,"c":3,"a":"L","b":1}"#), [4, 0, 4, 3, 3, 1, 0, 1, 0, 1])
        XCTAssertEqual(elenco(2, #"{"c":0,"a":"R","b":0}"#), [2, 0, 0, 0, 0, 0, 0, 1, 0, 0])
        XCTAssertEqual(elenco(3, #"{"p":1,"c":5,"a":"C","b":1,"f":1}"#), [1, 2, 7, 5, 3, 0, 0, 0, 0, 0], "barba folta: piena")
        XCTAssertEqual(elenco(100, #"{"a":"I","b":1,"f":0}"#), [2, 2, 2, 7, 2, 0, 1, 0, 1, 1], "non folta: la piena diventa corta")
        XCTAssertEqual(elenco(4567, #"{"p":6,"c":6}"#), [6, 0, 0, 6, 0, 2, 2, 0, 0, 0])
        XCTAssertEqual(elenco(7627, #"{"c":9,"a":"X"}"#), [2, 0, 4, 1, 2, 1, 2, 0, 0, 0], "campi non validi: come senza tratti")
        XCTAssertEqual(elenco(1, #"{"b":1,"f":0}"#), [2, 0, 10, 0, 4, 1, 0, 1, 0, 1], "non folta: la piena diventa baffi")
    }

    func testLaPelleSenzaPNonVieneMaiDalSeme() {
        for id in 0..<500 {
            XCTAssertEqual(GeneratoreVolto.estrai(id: id).pelle, 2, "id \(id)")
            XCTAssertEqual(GeneratoreVolto.estrai(id: id, tratti: TrattiVolto(c: 1, b: 1)).pelle, 2, "id \(id)")
        }
        XCTAssertEqual(GeneratoreVolto.estrai(id: 7, tratti: TrattiVolto(p: 0)).pelle, 0)
        XCTAssertEqual(GeneratoreVolto.estrai(id: 7, tratti: TrattiVolto(p: 6)).pelle, 6)
        XCTAssertEqual(GeneratoreVolto.estrai(id: 7, tratti: TrattiVolto(p: 7)).pelle, 2, "fuori scala: la neutra")
        XCTAssertEqual(GeneratoreVolto.estrai(id: 7, tratti: TrattiVolto(p: -1)).pelle, 2)
    }

    func testLaBarbaFoltaSiUsaSoloConBarba() {
        // f senza b non fa niente; f=1 con b=0 neppure
        for id in 1...200 {
            XCTAssertEqual(GeneratoreVolto.estrai(id: id, tratti: TrattiVolto(f: 1)), GeneratoreVolto.estrai(id: id), "id \(id)")
            XCTAssertEqual(GeneratoreVolto.estrai(id: id, tratti: TrattiVolto(b: 0, f: 1)).barba, 0)
            XCTAssertEqual(GeneratoreVolto.estrai(id: id, tratti: TrattiVolto(b: 1, f: 1)).barba, 3)
            XCTAssertTrue([2, 4].contains(GeneratoreVolto.estrai(id: id, tratti: TrattiVolto(b: 1, f: 0)).barba), "id \(id)")
        }
    }

    func testSenzaTrattiEIdenticaAllaVersione1() {
        for id in [0, 1, 2, 3, 100, 4567, 7627, 12345] {
            XCTAssertEqual(GeneratoreVolto.estrai(id: id, tratti: nil), GeneratoreVolto.estrai(id: id), "id \(id)")
            XCTAssertEqual(GeneratoreVolto.estrai(id: id, tratti: TrattiVolto()), GeneratoreVolto.estrai(id: id), "tratti vuoti, id \(id)")
        }
    }

    func testIVettoriDellaVersione1NonCambiano() {
        XCTAssertEqual(GeneratoreVolto.estrai(id: 1).elenco, [2, 0, 10, 0, 3, 1, 0, 1, 0, 1])
        XCTAssertEqual(GeneratoreVolto.estrai(id: 7627).elenco, [2, 0, 4, 1, 2, 1, 2, 0, 0, 0])
    }

    func testITrattiSiLeggonoConTolleranza() {
        XCTAssertEqual(tratti(#"{"c": "ciao", "b": 1}"#), TrattiVolto(c: nil, a: nil, b: 1))
        XCTAssertEqual(tratti(#"{"a": 5, "b": 1}"#), TrattiVolto(c: nil, a: nil, b: 1))
        XCTAssertEqual(tratti(#"{"p": 5, "c": 3, "f": 1}"#), TrattiVolto(p: 5, c: 3, f: 1))
        XCTAssertEqual(tratti(#"{"p": "x", "f": 99999999999999999999}"#), TrattiVolto(), "tipi sbagliati o enormi: come mancanti")
        XCTAssertEqual(tratti("{}"), TrattiVolto())
    }

    func testIlDepositoLeggeLaRispostaDelServer() {
        let corpo = #"{"versione": 3, "tratti": {"1": {"p": 2, "c": 3, "a": "L", "b": 1, "f": 1}, "2": {"c": 6}, "xx": {"c": 1}, "3": "rotto", "-5": {"c": 1}}}"#
        let m = DepositoTratti.leggi(Data(corpo.utf8))
        XCTAssertEqual(m?.count, 2, "le voci rotte si saltano, le altre restano")
        XCTAssertEqual(m?[1], TrattiVolto(p: 2, c: 3, a: "L", b: 1, f: 1))
        XCTAssertEqual(m?[2]?.c, 6)
        XCTAssertNil(DepositoTratti.leggi(Data("[]".utf8)))
        XCTAssertNil(DepositoTratti.leggi(Data()))
        XCTAssertNil(DepositoTratti.leggi(Data(#"{"versione": 3}"#.utf8)))
        // la versione 2 del contratto (senza `f`) si legge uguale
        let v2 = DepositoTratti.leggi(Data(#"{"versione": 2, "tratti": {"9": {"c": 1, "b": 1}}}"#.utf8))
        XCTAssertEqual(v2?[9], TrattiVolto(c: 1, b: 1))
    }

    func testIlDepositoScaricaEUnVoltoCambiaConITratti() async throws {
        let cartella = FileManager.default.temporaryDirectory.appendingPathComponent("tratti-\(UUID().uuidString)", isDirectory: true)
        try FileManager.default.createDirectory(at: cartella, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: cartella) }
        let s = ServerDiProva { _, percorso, _ in
            if percorso == "/api/avatar" { return Data(#"{"versione": 2, "tratti": {"4567": {"c": 5}}}"#.utf8) }
            throw ErroreApi.server("niente")
        }
        let d = DepositoTratti(cartella: cartella)
        XCTAssertNil(d.tratti(per: 4567))
        await d.caricaSeServe(server: s)
        await d.caricaSeServe(server: s)
        XCTAssertEqual(s.quante("/api/avatar"), 1, "una volta sola per apertura")
        XCTAssertEqual(d.tratti(per: 4567)?.c, 5)
        XCTAssertEqual(d.versione, 1)
        // al riavvio i tratti ci sono già (disco)
        let dopo = DepositoTratti(cartella: cartella)
        XCTAssertEqual(dopo.tratti(per: 4567)?.c, 5)
    }

    func testUnErroreDelServerNonRompeEPoiRiprova() async throws {
        let cartella = FileManager.default.temporaryDirectory.appendingPathComponent("tratti-\(UUID().uuidString)", isDirectory: true)
        try FileManager.default.createDirectory(at: cartella, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: cartella) }
        let d = DepositoTratti(cartella: cartella)
        await d.caricaSeServe(server: ServerDiProva.chePrecipita())
        XCTAssertEqual(d.quanti, 0)
        let s = ServerDiProva { _, _, _ in Data(#"{"tratti": {"1": {"b": 1}}}"#.utf8) }
        await d.caricaSeServe(server: s)
        XCTAssertEqual(d.quanti, 1, "dopo un errore ci riprova")
    }
}
