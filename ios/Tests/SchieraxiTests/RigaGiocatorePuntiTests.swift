import Foundation
import Testing
@testable import Schieraxi

/// Il numero a destra di ogni giocatore negli elenchi (Formazione, Squadra) è lo stesso del campo, della scheda e dei widget:
/// passa da `Formato.punti`, quindi a metà arrotonda lontano dallo zero come la web (6,25 → 6,3, non 6,2) e scrive sempre la
/// virgola, anche con il telefono in inglese (#251). Dati inventati.
@Suite("Elenchi dei giocatori: il fantavoto come il campo e i widget")
struct RigaGiocatorePuntiTests {
    /// Un giocatore inventato con i campi dei punti scelti dal test.
    private func giocatore(_ punti: String) throws -> Giocatore {
        let json = #"{"id": 120, "nome": "Leonel Marténi", "ruolo": "A", "p_voto": 0.62, \#(punti)}"#
        return try Decodifica.decodifica(Data(json.utf8))
    }

    /// Valori esatti in binario (6,25 e 4,75 sono proprio «a metà»), così il test prova l'arrotondamento e non l'errore
    /// dei numeri con la virgola.
    static let fantavoti: [(Double, String)] = [(6.25, "6,3"), (4.75, "4,8"), (7.44, "7,4"), (6.04, "6,0")]

    @Test("Lo stesso numero del campo: a metà si arrotonda come la web, con la virgola", arguments: RigaGiocatorePuntiTests.fantavoti)
    func comeIlCampo(fv: Double, atteso: String) throws {
        let g = try giocatore(#""fv_atteso": \#(fv), "punti_attesi": 4.1"#)
        #expect(RigaGiocatore.testoPunti(g) == atteso)
        // il campo (il disco della pedina e VoiceOver) scrive lo stesso numero
        let campo = LetturaPedina.contenuto(g)
        #expect(Formato.punti(campo.valore) == atteso)
        #expect(campo.voce.contains("fantavoto atteso \(atteso),"))
    }

    @Test("Server senza `fv_atteso`: i punti attesi, arrotondati allo stesso modo")
    func puntiAttesiDaServerVecchio() throws {
        let g = try giocatore(#""punti_attesi": 5.25"#)
        #expect(RigaGiocatore.testoPunti(g) == "5,3")
    }

    @Test("Senza numero: il trattino come la web, non «0,0»")
    func senzaNumero() throws {
        let g = try giocatore(#""fv_atteso": null"#)
        #expect(RigaGiocatore.testoPunti(g) == "–")
    }

    /// Prova il telefono in inglese: gira dove il sistema scrive i decimali con il punto (il simulatore della CI è in inglese).
    @Test("Con il telefono in inglese resta la virgola",
          .enabled(if: Locale.current.decimalSeparator == ".", "serve un telefono in inglese, come il simulatore della CI"))
    func telefonoInInglese() throws {
        let g = try giocatore(#""fv_atteso": 7.44"#)
        #expect(RigaGiocatore.testoPunti(g) == "7,4")
        #expect(!RigaGiocatore.testoPunti(g).contains("."))
    }
}
