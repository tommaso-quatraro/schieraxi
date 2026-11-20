import Foundation
import Testing
@testable import Schieraxi

/// La testata del widget «Da controllare» (medio e grande) dopo la scadenza e a giornata finita (#819). Nelle foto del 20/11 a
/// formazione chiusa diceva «Da controllare» senza niente da controllare, e a giornata finita la giornata compariva due volte:
/// «Giornata 8 · 11ª di Serie A» a destra della testata e «Giornata 8 · 11ª di Serie A: finita» sotto. Le parole sono quelle del
/// catalogo comune con la web (`oggi.chiusa`, `oggi.chiusa_dettaglio`, `oggi.giornata_finita`). Dati inventati.
@Suite("Widget «Da controllare»: testata a formazione chiusa e a giornata finita")
struct TestataDaControllareTests {

    /// Il riassunto di un `/api/widget` inventato con la fase data.
    private func riassunto(_ fase: String) throws -> RiassuntoOggi {
        let corpo: String
        switch fase {
        case "in_corso":
            corpo = #"""
            {"giornata": 11, "giornata_lega": 8, "fase": "in_corso", "scadenza": "2026-10-31 14:50",
             "in_corso": {"giornata": 11, "giornata_lega": 8, "punti_fatti": 41.5, "punti_previsti": 72.4, "ancora_da_giocare": 4,
                          "giocatori": [], "sostituzioni": []}}
            """#
        case "finita":
            // a giornata finita giornata e scadenza sono già quelle della prossima (la 9 della lega)
            corpo = #"""
            {"giornata": 12, "giornata_lega": 9, "fase": "finita", "scadenza": "2026-11-07 14:50",
             "riepilogo": {"giornata": 11, "giornata_lega": 8, "nel_diario": true, "punti_fatti": 69.5, "punti_attesi": 73.7}}
            """#
        default:
            corpo = #"""
            {"giornata": 11, "giornata_lega": 8, "scadenza": "2026-10-31 14:50",
             "formazione": {"modulo": "3-4-3", "punti_attesi": 72.7},
             "avvisi": [{"id": 1, "nome": "Leo Verdani", "tipo": "dubbio", "p_voto": 0.6, "in_formazione": true}]}
            """#
        }
        let w = try #require(RiassuntoWidget.leggi(Data(corpo.utf8)))
        return try #require(w.comeRiassuntoOggi())
    }

    @Test("A formazione chiusa la testata dice «Chiusa» con la giornata, non «Da controllare»")
    func chiusa() throws {
        let t = try riassunto("in_corso").testataDubbi
        #expect(t.forme == ["Chiusa"])
        #expect(t.forme == [Catalogo.Oggi.chiusa], "la parola della web (`oggi.chiusa`)")
        #expect(t.voce == "Chiusa")
        #expect(t.giornata?.intero == "Giornata 8 · 11ª di Serie A")
        #expect(t.simbolo == "dot.radiowaves.left.and.right", "lo stesso simbolo della fase del widget Prossima giornata")
    }

    @Test("A formazione chiusa sotto la testata c'è la frase, non di nuovo «Chiusa»")
    func corpoChiusa() throws {
        let r = try riassunto("in_corso")
        let adesso = try #require(Quando.data("2026-10-31 18:00"))
        let corpo = try #require(r.corpoFaseDubbi(adesso: adesso))
        #expect(corpo == CorpoFaseDubbi(frase: "La formazione si è chiusa oggi 14:50.", sotto: "I punti fatti sono nella Formazione."))
        #expect(corpo.frase == Catalogo.Oggi.chiusaDettaglio(quando: "oggi 14:50") + ".")
        #expect(!corpo.frase.contains("Da controllare") && corpo.frase != r.testataDubbi.forme[0], "«Chiusa» si dice una volta")
    }

    @Test("A giornata finita la giornata si dice una volta: «Giornata 8 · 11ª di Serie A: finita» in testata, niente a destra")
    func finita() throws {
        let t = try riassunto("finita").testataDubbi
        #expect(t.forme == ["Giornata 8 · 11ª di Serie A: finita", "Giornata 8: finita"])
        #expect(t.forme.first == Catalogo.Oggi.giornataFinita(g: "Giornata 8 · 11ª di Serie A"), "la frase della web (`oggi.giornata_finita`)")
        #expect(t.voce == "Giornata 8, 11ª di Serie A: finita")
        #expect(t.giornata == nil, "la giornata è già nel titolo: a destra si ripeteva")
        #expect(t.simbolo == "flag.checkered", "lo stesso simbolo della giornata finita del widget Prossima giornata")
    }

    @Test("A giornata finita sotto la testata c'è cosa succede ora, senza ripetere la giornata")
    func corpoFinita() throws {
        let r = try riassunto("finita")
        let corpo = try #require(r.corpoFaseDubbi(adesso: Date()))
        #expect(corpo == CorpoFaseDubbi(frase: "Si ricomincia con la prossima giornata.", sotto: nil))
        #expect(!corpo.frase.contains("Giornata 8"))
    }

    @Test("Prima della scadenza resta «Da controllare» con la giornata a destra, e niente frase di fase")
    func prima() throws {
        let r = try riassunto("prima")
        let t = r.testataDubbi
        #expect(t.forme == ["Da controllare"])
        #expect(t.giornata?.intero == "Giornata 8 · 11ª di Serie A")
        #expect(t.simbolo == "exclamationmark.triangle.fill", "c'è un titolare in dubbio")
        #expect(r.corpoFaseDubbi(adesso: Date()) == nil)
    }

    @Test("A formazione chiusa senza l'ora della scadenza la frase è quella del catalogo per quel caso (`formazione.chiusa`)")
    func chiusaSenzaOra() throws {
        let corpo = #"""
        {"giornata": 11, "giornata_lega": 8, "fase": "in_corso",
         "in_corso": {"giornata": 11, "giornata_lega": 8, "punti_fatti": 41.5, "punti_previsti": 72.4, "ancora_da_giocare": 4,
                      "giocatori": [], "sostituzioni": []}}
        """#
        let w = try #require(RiassuntoWidget.leggi(Data(corpo.utf8)))
        let r = try #require(w.comeRiassuntoOggi())
        #expect(r.inizio == nil, "senza `scadenza` il widget non sa quando si è chiusa")
        let c = try #require(r.corpoFaseDubbi(adesso: Date()))
        #expect(c == CorpoFaseDubbi(frase: Catalogo.Formazione.chiusa, sotto: "I punti fatti sono nella Formazione."))
        #expect(c.frase == "La formazione di questa giornata è chiusa: le partite sono cominciate.")
    }
}
