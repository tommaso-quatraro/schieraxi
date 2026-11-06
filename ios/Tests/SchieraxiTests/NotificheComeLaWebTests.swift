import Foundation
import Testing
@testable import Schieraxi

// Issue #439. «Notifiche» (Impostazioni) e «Avanzate» dell'iPhone dicono le stesse parole della web: nome e riga sotto della voce
// (`imp.avvisi`, `imp.avvisi_sub`), titoli e righe d'aiuto degli interruttori (`avv.*`), la spiegazione di «Mostra tutte le
// funzioni» (`av.mostra_tutte*`). Le righe d'aiuto della web non finiscono con il punto. `fanta/web/testi.js` si legge dal repository.

/// Le coppie (chiave di `testi.js`, testo dell'iPhone) dei titoli degli interruttori e della scelta «Avviso se il consiglio cambia».
private let titoli: [(String, String)] = [
    ("avv.cambi", TestiImpostazioni.cambi),
    ("avv.prima", AvvisoPrima.titolo),
    ("avv.prom_60", TestiImpostazioni.promemoria60),
    ("avv.prom_15", TestiImpostazioni.promemoria15),
    ("avv.riepilogo", TestiImpostazioni.riepilogo),
    ("avv.copertura", TestiImpostazioni.copertura),
    ("avv.nativa", TestiImpostazioni.nativa),
    ("avv.ore_tranq", TestiImpostazioni.oreTranquille),
    ("av.mostra_tutte", TestiImpostazioni.mostraTutte),
]

/// Le coppie (chiave di `testi.js`, testo dell'iPhone) delle righe d'aiuto sotto gli interruttori.
private let aiuti: [(String, String)] = [
    ("avv.cambi_aiuto", TestiImpostazioni.cambiAiuto),
    ("avv.prima_aiuto", AvvisoPrima.aiuto),
    ("avv.prom_60_aiuto", TestiImpostazioni.promemoria60Aiuto),
    ("avv.riepilogo_aiuto", TestiImpostazioni.riepilogoAiuto),
    ("avv.copertura_aiuto", TestiImpostazioni.coperturaAiuto),
    ("avv.ore_tranq_aiuto", TestiImpostazioni.oreTranquilleAiuto),
    ("av.mostra_tutte_spiega", TestiImpostazioni.mostraTutteSpiega),
]

@Suite("Notifiche e Avanzate come la web (#439)")
struct NotificheComeLaWebTests {
    @Test("La voce si chiama «Notifiche», con sotto «Cosa ricevere sul telefono e quando» (`imp.avvisi`, `imp.avvisi_sub`)")
    func voce() throws {
        let web = try TestiWeb()
        let nome = try web.italiano("imp.avvisi")
        let sotto = try web.italiano("imp.avvisi_sub")
        #expect(TestiImpostazioni.notifiche == nome)
        #expect(TestiImpostazioni.notificheSotto == sotto)
        #expect(TestiImpostazioni.notifiche == "Notifiche")
    }

    @Test("Il titolo dell'interruttore è quello della web", arguments: titoli)
    func titolo(chiave: String, ios: String) throws {
        let web = try TestiWeb().italiano(chiave)
        #expect(ios == web, "«\(chiave)» è diverso da testi.js")
    }

    @Test("La riga d'aiuto è quella della web, senza il punto finale", arguments: aiuti)
    func aiuto(chiave: String, ios: String) throws {
        let web = try TestiWeb().italiano(chiave)
        #expect(ios == web, "«\(chiave)» è diverso da testi.js")
        #expect(!ios.isEmpty)
    }

    @Test("Le scelte di «Avviso se il consiglio cambia» hanno i testi della web (`avv.prima_0` … `avv.prima_90`)")
    func sceltePrima() throws {
        let web = try TestiWeb()
        let attese = try ["avv.prima_0", "avv.prima_30", "avv.prima_60", "avv.prima_90"].map { try web.italiano($0) }
        #expect(AvvisoPrima.valori.map(AvvisoPrima.testo) == attese)
    }

    @Test("«Mostra tutte le funzioni» spiega che si vede «il resto», non «tutto il resto»")
    func mostraTutteIlResto() {
        #expect(TestiImpostazioni.mostraTutteSpiega.contains("vedi anche il resto ("))
        #expect(!TestiImpostazioni.mostraTutteSpiega.contains("tutto il resto"))
    }
}
