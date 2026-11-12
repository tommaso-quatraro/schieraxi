import Foundation
import Testing
@testable import Schieraxi

// Issue #439. «Notifiche» (Impostazioni) e «Avanzate» dell'iPhone dicono le stesse parole della web: nome e riga sotto della voce
// (`imp.avvisi`, `imp.avvisi_sub`), titoli e righe d'aiuto degli interruttori (`avv.*`). Le righe d'aiuto della web non
// finiscono con il punto. Dal #497 `imp.*` e `avv.*` vengono dal catalogo comune (`Catalogo.Imp`, `Catalogo.Avv`).
// «Mostra tutte le funzioni» non c'è più (#634).

/// Le coppie (testo del catalogo, testo dell'iPhone) dei titoli degli interruttori e della scelta «Avviso se il consiglio cambia».
private let titoli: [(String, String)] = [
    (Catalogo.Avv.cambi, TestiImpostazioni.cambi),
    (Catalogo.Avv.prima, AvvisoPrima.titolo),
    (Catalogo.Avv.prom60, TestiImpostazioni.promemoria60),
    (Catalogo.Avv.prom15, TestiImpostazioni.promemoria15),
    (Catalogo.Avv.riepilogo, TestiImpostazioni.riepilogo),
    (Catalogo.Avv.copertura, TestiImpostazioni.copertura),
    (Catalogo.Avv.nativa, TestiImpostazioni.nativa),
    (Catalogo.Avv.oreTranq, TestiImpostazioni.oreTranquille),
]

/// Le coppie (testo del catalogo, testo dell'iPhone) delle righe d'aiuto sotto gli interruttori.
private let aiuti: [(String, String)] = [
    (Catalogo.Avv.cambiAiuto, TestiImpostazioni.cambiAiuto),
    (Catalogo.Avv.primaAiuto, AvvisoPrima.aiuto),
    (Catalogo.Avv.prom60Aiuto, TestiImpostazioni.promemoria60Aiuto),
    (Catalogo.Avv.riepilogoAiuto, TestiImpostazioni.riepilogoAiuto),
    (Catalogo.Avv.coperturaAiuto, TestiImpostazioni.coperturaAiuto),
    (Catalogo.Avv.oreTranqAiuto, TestiImpostazioni.oreTranquilleAiuto),
]

@Suite("Notifiche e Avanzate come la web (#439)")
struct NotificheComeLaWebTests {
    @Test("La voce si chiama «Notifiche», con sotto «Cosa ricevere sul telefono e quando» (`imp.avvisi`, `imp.avvisi_sub`)")
    func voce() {
        #expect(TestiImpostazioni.notifiche == Catalogo.Imp.avvisi)
        #expect(TestiImpostazioni.notificheSotto == Catalogo.Imp.avvisiSub)
        #expect(TestiImpostazioni.notifiche == "Notifiche")
    }

    @Test("Il titolo dell'interruttore è quello della web", arguments: titoli)
    func titolo(web: String, ios: String) {
        #expect(ios == web)
    }

    @Test("La riga d'aiuto è quella della web, senza il punto finale", arguments: aiuti)
    func aiuto(web: String, ios: String) {
        #expect(ios == web)
        #expect(!ios.isEmpty)
        #expect(!ios.hasSuffix("."))
    }

    @Test("Le scelte di «Avviso se il consiglio cambia» hanno i testi della web (`avv.prima_0` … `avv.prima_90`)")
    func sceltePrima() {
        let attese = [Catalogo.Avv.prima0, Catalogo.Avv.prima30, Catalogo.Avv.prima60, Catalogo.Avv.prima90]
        #expect(AvvisoPrima.valori.map(AvvisoPrima.testo) == attese)
    }
}
