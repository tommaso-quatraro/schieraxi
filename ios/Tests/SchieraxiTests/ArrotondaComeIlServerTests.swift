import Foundation
import Testing
@testable import Schieraxi

/// I numeri con i decimali si scrivono come li scrivono il server (`frasi.arrotonda`) e la web (`num`, cioè `toFixed`): sul valore
/// vero del numero in memoria, con il mezzo lontano dallo zero. 6,35 in memoria è 6,3499…: «6,3». Prima l'iPhone moltiplicava per
/// 10 e arrotondava, e 6,35 × 10 fa 63,5 tondo: scriveva «6,4» accanto al «6,3» della web e alla differenza «+1,2» del server.
/// Gli stessi casi sono in tests/test_arrotonda_come_server.py, per il server e la web.
@Suite("Decimali arrotondati come il server e la web")
struct ArrotondaComeIlServerTests {
    /// Il meno di `decimali` può essere «-» o «−» secondo il sistema: si confronta con un solo carattere.
    private static func normalizza(_ testo: String) -> String { testo.replacingOccurrences(of: "\u{2212}", with: "-") }

    @Test("Una cifra: il valore vero del numero, il mezzo lontano dallo zero, mai «-0,0»",
          arguments: zip([6.35, 5.55, 7.05, 8.45, 6.05, 0.15, 9.95, 6.25, 6.75, 1.05, -0.25, -0.35, -6.35, -0.05, -0.04, -0.0, 0.04],
                         ["6,3", "5,5", "7,0", "8,4", "6,0", "0,1", "9,9", "6,3", "6,8", "1,1", "-0,3", "-0,3", "-6,3", "-0,1",
                          "0,0", "0,0", "0,0"]))
    func unaCifra(valore: Double, scritto: String) {
        #expect(Self.normalizza(Formato.decimali(valore)) == scritto, "\(valore)")
        #expect(Self.normalizza(Formato.punti(valore)) == scritto, "\(valore)")
    }

    @Test("Con il segno, come la frase del server: il meno tipografico, lo zero senza segno",
          arguments: zip([1.25, 0.35, 5.55, -0.25, -0.35, -6.35, -0.05, -0.04],
                         ["+1,3", "+0,3", "+5,5", "\u{2212}0,3", "\u{2212}0,3", "\u{2212}6,3", "\u{2212}0,1", "0,0"]))
    func conSegno(valore: Double, scritto: String) {
        #expect(Formato.conSegno(valore) == scritto, "\(valore)")
    }

    @Test("Due cifre, con la stessa regola",
          arguments: zip([2.675, 1.005, 0.125, -0.125, -0.004], ["2,67", "1,00", "0,13", "-0,13", "0,00"]))
    func dueCifre(valore: Double, scritto: String) {
        #expect(Self.normalizza(Formato.decimali(valore, cifre: 2)) == scritto, "\(valore)")
    }

    @Test("Zero cifre, con la stessa regola", arguments: zip([0.5, 2.5, -2.5, -0.4], ["1", "3", "-3", "0"]))
    func zeroCifre(valore: Double, scritto: String) {
        #expect(Self.normalizza(Formato.decimali(valore, cifre: 0)) == scritto, "\(valore)")
    }

    @Test("La differenza scritta dal server torna con i due numeri scritti accanto")
    func differenzaDelServer() {
        // atteso 6,35 (6,3499… in memoria) e preso 7,5: il server scrive «+1,2» (`diario.fatti_e_attesi`), e 7,5 − 6,3 fa 1,2
        #expect(Formato.punti(6.35) == "6,3")
        #expect(Formato.punti(7.5) == "7,5")
        #expect(Formato.conSegno(7.5 - 6.3) == "+1,2")
    }
}
