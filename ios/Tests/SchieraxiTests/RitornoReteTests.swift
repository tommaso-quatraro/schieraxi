import Foundation
import Testing
@testable import Schieraxi

/// Senza rete una schermata mostra la copia salvata; quando il telefono ritrova la rete l'app riprova da sola, una volta, come la
/// web (`alRitornoDellaRete` in `caricaConCache` di `app.js`, che aspetta l'evento `online` del browser). Qui la regola, senza la
/// rete vera: `RitornoRete` la usa con le notizie di iOS sulla rete e manda «Aggiorna» a tutte le schermate. Con la rete a tratti
/// un tentativo che non riesce non riarma l'attesa (revisione della #972: prima ogni ritorno della rete faceva ripartire 8-10
/// richieste), e fra due tentativi automatici passano almeno 5 minuti.
@Suite("Senza rete: tornata la rete si riprova da soli, una volta")
struct RitornoReteTests {
    /// Quello che succede, in ordine, a tanti secondi dall'inizio: una copia che resta a video senza rete (`aspetta`) o una
    /// notizia sulla rete (true = in linea).
    enum Fatto {
        case aspetta(_ secondi: TimeInterval)
        case rete(_ inLinea: Bool, _ secondi: TimeInterval)
    }

    private static let inizio = Date(timeIntervalSince1970: 1_795_000_000)

    /// Per ogni notizia sulla rete, se si riprova. Fuori da `#expect`, che non può chiamare funzioni che cambiano il valore.
    private static func riprove(_ fatti: [Fatto]) -> [Bool] {
        var attesa = AttesaRete()
        var riprove: [Bool] = []
        for fatto in fatti {
            switch fatto {
            case .aspetta(let secondi):
                attesa.aspetta(adesso: inizio.addingTimeInterval(secondi))
            case .rete(let inLinea, let secondi):
                riprove.append(attesa.cambio(inLinea: inLinea, adesso: inizio.addingTimeInterval(secondi)))
            }
        }
        return riprove
    }

    @Test("Una copia aspetta la rete: la rete torna e si riprova, una volta sola")
    func unaVolta() {
        // la prima notizia non è un ritorno; poi la rete cade con una copia che aspetta, torna (si riprova), ricade e ritorna
        let riprove = Self.riprove([.rete(true, 0), .aspetta(1), .rete(false, 2), .rete(true, 10), .rete(false, 20), .rete(true, 30)])
        #expect(riprove == [false, false, true, false, false])
    }

    @Test("Un tentativo che non riesce non riarma l'attesa: con la rete a tratti non si riprova a ogni ritorno")
    func tentativoFallitoNonRiarma() {
        // tornata la rete si riprova (10 s); le letture di quel tentativo trovano di nuovo la rete giù (12 s) e restano con la copia,
        // e così una lettura di poco dopo (100 s): ai ritorni dopo non si riprova da soli, resta «Riprova»
        let riprove = Self.riprove([.rete(true, 0), .aspetta(1), .rete(false, 2), .rete(true, 10), .aspetta(12), .rete(false, 12),
                                    .rete(true, 40), .aspetta(100), .rete(false, 101), .rete(true, 120)])
        #expect(riprove == [false, false, true, false, false, false, false])
    }

    @Test("Fra due tentativi automatici almeno 5 minuti: dopo, una copia rimasta senza rete riarma l'attesa")
    func intervallo() {
        let dopo = 10 + AttesaRete.intervallo
        let riprove = Self.riprove([.rete(true, 0), .aspetta(1), .rete(false, 2), .rete(true, 10),
                                    .aspetta(dopo), .rete(false, dopo + 1), .rete(true, dopo + 20)])
        #expect(riprove == [false, false, true, false, true])
    }

    @Test("Senza copie che aspettano, la rete che va e viene non fa ricaricare niente")
    func senzaAttesa() {
        #expect(Self.riprove([.rete(false, 0), .rete(true, 1), .rete(false, 2), .rete(true, 3)]) == [false, false, false, false])
    }

    @Test("La copia resta senza rete con la rete accesa (server spento): si riprova al prossimo ritorno della rete, non subito")
    func conLaReteAccesa() {
        let riprove = Self.riprove([.rete(true, 0), .aspetta(1), .rete(true, 2), .rete(false, 3), .rete(true, 4)])
        #expect(riprove == [false, false, false, true])
    }
}
