import Foundation
import Testing
@testable import Schieraxi

/// Senza rete una schermata mostra la copia salvata; quando il telefono ritrova la rete l'app riprova da sola, una volta, come la
/// web (`alRitornoDellaRete` in `caricaConCache` di `app.js`, che aspetta l'evento `online` del browser). Qui la regola, senza la
/// rete vera: `RitornoRete` la usa con le notizie di iOS sulla rete e manda «Aggiorna» a tutte le schermate.
@Suite("Senza rete: tornata la rete si riprova da soli, una volta")
struct RitornoReteTests {
    /// Le notizie sulla rete una dopo l'altra (true = in linea) e, per ognuna, se si riprova. Fuori da `#expect`, che non può
    /// chiamare funzioni che cambiano il valore.
    private static func notizie(_ inLinea: [Bool], aspettaDopo: Int? = nil, attesa: inout AttesaRete) -> [Bool] {
        var riprove: [Bool] = []
        for (indice, notizia) in inLinea.enumerated() {
            if indice == aspettaDopo { attesa.aspetta() }
            riprove.append(attesa.cambio(inLinea: notizia))
        }
        return riprove
    }

    @Test("Una copia aspetta la rete: la rete torna e si riprova, una volta sola")
    func unaVolta() {
        var attesa = AttesaRete()
        // la prima notizia non è un ritorno; poi la rete cade con una copia che aspetta, torna (si riprova), ricade e ritorna
        let riprove = Self.notizie([true, false, true, false, true], aspettaDopo: 1, attesa: &attesa)
        #expect(riprove == [false, false, true, false, false], "una volta sola, finché un'altra lettura non resta senza rete")
    }

    @Test("Senza copie che aspettano, la rete che va e viene non fa ricaricare niente")
    func senzaAttesa() {
        var attesa = AttesaRete()
        let riprove = Self.notizie([false, true, false, true], attesa: &attesa)
        #expect(riprove == [false, false, false, false])
    }

    @Test("La copia resta senza rete con la rete accesa (server spento): si riprova al prossimo ritorno della rete, non subito")
    func conLaReteAccesa() {
        var attesa = AttesaRete()
        let riprove = Self.notizie([true, true, false, true], aspettaDopo: 1, attesa: &attesa)
        #expect(riprove == [false, false, false, true])
    }
}
