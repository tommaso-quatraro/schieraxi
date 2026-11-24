import Foundation
import Testing
@testable import Schieraxi

/// «Tutti i numeri» della scheda del giocatore (#862): con la fonte delle statistiche avanzate ferma (dal 12/11/2026, #756)
/// «Gol e assist rispetto alle occasioni» e «Statistiche avanzate» mostravano i numeri dell'ultima partita letta senza una data.
/// Il server manda il giorno (`avanzate.dati_fino_al`, «2026-11-09») e l'app scrive «Dati fino al 9/11.» come la web (`finoAl` di
/// `riempiScheda`, frase `mercato.dati_fino_al` del catalogo comune). Dati inventati.
@Suite("La scheda dice fino a quando arrivano le statistiche avanzate")
struct SchedaDatiFinoAlTests {
    /// Una scheda con le statistiche avanzate scritte a mano (`avanzate` è il JSON del campo, o nil se manca).
    private func scheda(avanzate: String?) throws -> SchedaGiocatore {
        let campo = avanzate.map { #", "avanzate": \#($0)"# } ?? ""
        return try Decodifica.decodifica(Data(#"""
        {"calciatore": {"id": 7, "nome": "Mauro Retalli", "ruolo": "A", "squadra": "Genoa", "squadra_slug": "genoa"}\#(campo)}
        """#.utf8))
    }

    @Test("Il giorno del server si legge e diventa «Dati fino al 9/11.», la frase della web")
    func conIlGiorno() throws {
        let s = try scheda(avanzate: #"{"minuti": 492, "xg": 6.66, "dati_fino_al": "2026-11-09"}"#)
        #expect(s.avanzate?.datiFinoAl == "2026-11-09")
        #expect(LetturaScheda.datiFinoAl(s.avanzate) == "Dati fino al 9/11.")
        #expect(LetturaScheda.datiFinoAl(s.avanzate) == Catalogo.Mercato.datiFinoAl(data: "9/11"))
    }

    @Test("Senza il giorno (server di prima, stagione senza partite lette) o con un giorno che non si capisce, niente riga",
          arguments: [#"{"minuti": 492}"#, #"{"minuti": 492, "dati_fino_al": null}"#, #"{"minuti": 492, "dati_fino_al": "ieri"}"#,
                      #"{"minuti": 492, "dati_fino_al": ""}"#])
    func senzaIlGiorno(avanzate: String) throws {
        let s = try scheda(avanzate: avanzate)
        #expect(LetturaScheda.datiFinoAl(s.avanzate) == nil)
    }

    @Test("Senza statistiche avanzate niente riga")
    func senzaAvanzate() throws {
        let s = try scheda(avanzate: nil)
        #expect(s.avanzate == nil)
        #expect(LetturaScheda.datiFinoAl(s.avanzate) == nil)
    }

    @Test("Giorno e mese si scrivono senza zeri davanti, come `giornoMese` della web")
    func senzaZeri() throws {
        let primo = try scheda(avanzate: #"{"minuti": 90, "dati_fino_al": "2027-01-03"}"#)
        #expect(LetturaScheda.datiFinoAl(primo.avanzate) == "Dati fino al 3/1.")
        let dicembre = try scheda(avanzate: #"{"minuti": 90, "dati_fino_al": "2026-12-20"}"#)
        #expect(LetturaScheda.datiFinoAl(dicembre.avanzate) == "Dati fino al 20/12.")
    }
}
