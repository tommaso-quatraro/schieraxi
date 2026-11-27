import Foundation
import Testing
@testable import Schieraxi

/// La titolarità a parole della demo è quella che darebbe il server (`titolarita` di fanta/consigli.py): «Probabile titolare» solo
/// dall'80% con le probabili che lo danno titolare (o la quota da titolare dal 60%), «In ballottaggio» dal 50%, «Probabile
/// panchina» dal 20%, sotto «Improbabile». Foto della #955 (corse 45963656523 e 45963638778): in panchina Dimarzi e Lemão avevano
/// «Improbabile» accanto a «gioca 72%» e «gioca 68%», perché la demo diceva improbabile chiunque sotto il 75%.
/// Dati inventati: quelli di `LegaDemo.swift` e `DatiDemo.swift`, nello stesso istante fisso.
struct DemoTitolaritaTests {
    static let adesso = Date(timeIntervalSinceReferenceDate: 815_000_000)
    static let demo = FinteServer.demoFissata(adesso: adesso)

    /// `titolarita` di fanta/consigli.py per chi non è fuori: `p` è `p_voto`, `q` la quota da titolare, `stato` delle probabili.
    static func delServer(p: Double, q: Double, stato: String?) -> String {
        if p >= 0.8 && (q >= 0.6 || stato == "titolare") { return "titolare" }
        return p >= 0.5 ? "ballottaggio" : p >= 0.2 ? "panchina" : "improbabile"
    }

    private func schede() async throws -> [String: Giocatore] {
        let f: Formazione = try await Self.demo.get("/api/formazione")
        return try #require(f.schede, "la Formazione della demo non ha le schede della rosa")
    }

    @Test("Ogni giocatore della rosa ha la titolarità che gli darebbe il server")
    func rosaComeIlServer() async throws {
        let rosa = try await schede()
        var diverse: [String] = []
        for g in rosa.values where g.titolarita != "fuori" {
            let p = g.pVoto ?? 0
            let delServer = Self.delServer(p: p, q: g.quotaTitolare ?? 0, stato: g.stato)
            if g.titolarita != delServer {
                diverse.append("\(g.nome) (gioca \(Int((p * 100).rounded()))%): «\(g.titolarita ?? "nessuna")», il server «\(delServer)»")
            }
        }
        #expect(diverse.isEmpty, "titolarità della demo diversa da quella del server: \(diverse.sorted())")
    }

    @Test("In panchina Dimarzi (72%), Lemão (68%) e Kervan (78%) sono «In ballottaggio», non «Improbabile»")
    func panchinaInBallottaggio() async throws {
        let rosa = try await schede()
        for id in [105, 123, 125] {
            let g = try #require(rosa[String(id)], "nella demo manca il giocatore \(id)")
            #expect(g.titolarita == "ballottaggio", "\(g.nome): «\(g.titolarita ?? "nessuna")»")
            #expect(g.etichette.first?.testo == "In ballottaggio", "\(g.nome): \(g.etichette.map(\.testo))")
        }
    }
}
