import Foundation
import Testing
@testable import Schieraxi

/// Stato dei dati, «Quanto è affidabile il modello» (#982): se i punti della formazione del modello battono quelli da fantamedia
/// (il verde della web, classe `positivo`) lo dice il server, `sintesi.modello_batte_fantamedia`. L'app non confronta più i due
/// numeri da sola; con un server di prima, che non manda il campo, sì, come faceva la web.
@Suite("Affidabilità: il verde sui punti del modello lo decide il server (#982)")
struct AffidabilitaVerdeTests {
    private func sintesi(_ json: String) throws -> SintesiAffidabilita {
        let a: Affidabilita = try Decodifica.decodifica(Data(#"{"righe": [], "sintesi": \#(json)}"#.utf8))
        return try #require(a.sintesi)
    }

    @Test("Il server dice di no: niente verde, anche se i due numeri direbbero di sì")
    func ilServerDiceDiNo() throws {
        let s = try sintesi(#"{"punti_modello": 71.7, "punti_fantamedia": 70.6, "modello_batte_fantamedia": false}"#)
        #expect(s.modelloBatteFantamedia == false)
        #expect(!s.batteFantamedia)
    }

    @Test("Il server dice di sì: verde, anche se i due numeri direbbero di no")
    func ilServerDiceDiSi() throws {
        let s = try sintesi(#"{"punti_modello": 69.9, "punti_fantamedia": 70.1, "modello_batte_fantamedia": true}"#)
        #expect(s.modelloBatteFantamedia == true)
        #expect(s.batteFantamedia)
    }

    @Test("Un server di prima, senza il campo: il confronto dei due numeri, come la web", arguments: [
        (#"{"punti_modello": 71.7, "punti_fantamedia": 70.6}"#, true),
        (#"{"punti_modello": 70.0, "punti_fantamedia": 70.0}"#, true),
        (#"{"punti_modello": 66.0, "punti_fantamedia": 68.3}"#, false),
        (#"{"punti_modello": 66.0}"#, false),
        (#"{"punti_modello": 66.0, "punti_fantamedia": 68.3, "modello_batte_fantamedia": null}"#, false),
    ])
    func serverDiPrima(json: String, verde: Bool) throws {
        let s = try sintesi(json)
        #expect(s.modelloBatteFantamedia == nil)
        #expect(s.batteFantamedia == verde)
    }
}
