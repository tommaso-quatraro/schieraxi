import Foundation
import Testing
@testable import Schieraxi

/// Senza rete una schermata mostra la copia salvata; quando il telefono ritrova la rete l'app riprova da sola, una volta, come la
/// web (`alRitornoDellaRete` in `caricaConCache` di `app.js`, che aspetta l'evento `online` del browser). Qui la regola, senza la
/// rete vera: `RitornoRete` la usa con le notizie di iOS sulla rete e manda «Aggiorna» a tutte le schermate.
@Suite("Senza rete: tornata la rete si riprova da soli, una volta")
struct RitornoReteTests {
    @Test("Una copia aspetta la rete: la rete torna e si riprova, una volta sola")
    func unaVolta() {
        var attesa = AttesaRete()
        #expect(!attesa.cambio(inLinea: true), "la prima notizia sulla rete non è un ritorno")
        attesa.aspetta()
        #expect(!attesa.cambio(inLinea: false))
        #expect(attesa.cambio(inLinea: true), "tornata la rete: si riprova")
        #expect(!attesa.cambio(inLinea: false))
        #expect(!attesa.cambio(inLinea: true), "una volta sola, finché un'altra lettura non resta senza rete")
    }

    @Test("Senza copie che aspettano, la rete che va e viene non fa ricaricare niente")
    func senzaAttesa() {
        var attesa = AttesaRete()
        #expect(!attesa.cambio(inLinea: false))
        #expect(!attesa.cambio(inLinea: true))
    }

    @Test("La copia resta senza rete con la rete accesa (server spento): si riprova al prossimo ritorno della rete, non subito")
    func conLaReteAccesa() {
        var attesa = AttesaRete()
        #expect(!attesa.cambio(inLinea: true))
        attesa.aspetta()
        #expect(!attesa.cambio(inLinea: true), "la rete non è tornata: c'era già")
        #expect(!attesa.cambio(inLinea: false))
        #expect(attesa.cambio(inLinea: true))
    }
}
