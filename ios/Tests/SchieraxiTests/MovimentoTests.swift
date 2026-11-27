import SwiftUI
import Testing
@testable import Schieraxi

/// «Animazioni ridotte» (Impostazioni › Aspetto) e «Riduci movimento» di iOS valgono anche per le animazioni scritte dentro le viste:
/// le pedine che entrano nel campo, i numeri che scorrono, il grafico dei voti che si disegna. Prima l'interruttore dell'app toglieva
/// solo le animazioni che passavano dalla radice, e quelle scritte in una vista partivano lo stesso (ricerca sull'accessibilità del
/// 27/11). Qui la scelta, che le viste usano con i due interruttori (`Movimento.scegli`).
@Suite("Animazioni: l'interruttore dell'app e «Riduci movimento» di iOS")
struct MovimentoTests {
    @Test("«Animazioni ridotte» ferma tutto, con o senza «Riduci movimento»", arguments: [false, true])
    func animazioniRidotte(riduciMovimento: Bool) {
        let m = Movimento.scegli(riduciMovimento: riduciMovimento, animazioniRidotte: true)
        #expect(m == .fermo)
        #expect(m.animazione(.smooth(duration: 0.4)) == nil)
        #expect(!m.cifreCheScorrono)
    }

    @Test("«Riduci movimento» di iOS: al posto del movimento la dissolvenza breve, e le cifre non scorrono")
    func riduciMovimento() {
        let m = Movimento.scegli(riduciMovimento: true, animazioniRidotte: false)
        #expect(m == .quieto)
        #expect(m.animazione(.spring(duration: 0.45, bounce: 0.22)) == Tema.quieta)
        #expect(!m.cifreCheScorrono)
    }

    @Test("Senza nessuno dei due: l'animazione scritta nella vista, e le cifre scorrono")
    func pieno() {
        let normale = Animation.smooth(duration: 1.0)
        let m = Movimento.scegli(riduciMovimento: false, animazioniRidotte: false)
        #expect(m == .pieno)
        #expect(m.animazione(normale) == normale)
        #expect(m.cifreCheScorrono)
    }

    @Test("L'interruttore si legge con la chiave delle Impostazioni")
    func chiave() {
        #expect(Movimento.chiave == "animazioniRidotte")
    }
}
