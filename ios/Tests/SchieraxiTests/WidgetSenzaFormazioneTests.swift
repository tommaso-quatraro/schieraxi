import Foundation
import Testing
@testable import Schieraxi

/// Il widget per chi è entrato in SchieraXI a giornata già iniziata senza una formazione per lei (#687, seguito di #651).
/// `GET /api/widget` (e `/api/oggi`) risponde con `fase: "in_corso"`, senza `in_corso` e con `senza_formazione: true` e la `prossima`
/// giornata da preparare; `giornata`, `scadenza` e `formazione` restano quelli della giornata già iniziata. Prima il widget non
/// leggeva i due campi e mostrava la consigliata della giornata già iniziata («Chiusa · 3-4-3 71,5 punti attesi») invece di
/// invitare a preparare la prossima. Lo stesso dato di prova nelle due forme: `widget-senza-formazione` (entrato dopo la
/// scadenza) e `widget-in-corso` (c'era già prima: i punti fatti di sempre). Dati inventati.
@Suite("Widget per chi è entrato a giornata iniziata: la prossima giornata da preparare (#687)")
struct WidgetSenzaFormazioneTests {
    /// La scadenza della prossima giornata nei dati di prova (ora italiana).
    private static let scadenzaProssima = "2026-11-14 14:50"

    private func riassunto(_ fixture: String) throws -> RiassuntoOggi {
        let w = try #require(RiassuntoWidget.leggi(try Fixture.dati(fixture)), "la risposta \(fixture) non si legge")
        return try #require(w.comeRiassuntoOggi(), "senza riassunto il widget dice «Nessun dato»")
    }

    @Test("Con `senza_formazione` il riassunto porta la prossima giornata e il conto alla rovescia va alla sua scadenza")
    func senzaFormazione() throws {
        let r = try riassunto("widget-senza-formazione")
        #expect(r.inCorso)
        #expect(r.senzaFormazioneInCorso, "il widget mostrava la consigliata della giornata già iniziata")
        #expect(!r.mostraFase, "niente punti fatti di una formazione che non ha schierato")
        #expect(r.daControllare == 0)
        let prossima = try #require(r.prossimaDaPreparare, "senza la prossima il widget non può invitare a prepararla")
        #expect(prossima.giornata == 11)
        #expect(prossima.giornataLega == 8)
        #expect(prossima.scadenza == Quando.data(Self.scadenzaProssima))
        #expect(r.scadenzaDelConto == Quando.data(Self.scadenzaProssima), "il conto va alla prossima scadenza, non resta «Chiusa»")
        #expect(r.formeProssimaDaPreparare == ["Giornata 8 · 11ª di Serie A", "Giornata 8"])
        #expect(r.voceProssimaDaPreparare == "Giornata 8, 11ª di Serie A")
        // la giornata già iniziata resta quella del server: i titoli la nominano
        #expect(r.giornata == 10)
        #expect(r.inizio == Quando.data("2026-11-08 14:30"))
    }

    @Test("La stessa giornata per chi c'era già prima della scadenza (`in_corso`, senza `senza_formazione`): come prima")
    func inCorso() throws {
        let r = try riassunto("widget-in-corso")
        #expect(r.inCorso)
        #expect(!r.senzaFormazioneInCorso)
        #expect(r.prossimaDaPreparare == nil)
        #expect(r.mostraFase)
        #expect(r.puntiFatti == 31.5)
        #expect(r.scadenzaDelConto == r.inizio)
        #expect(r.descrizioneSenzaFormazione == nil)
        #expect(r.formeRigaInLineaSenzaFormazione(adesso: Date()).isEmpty)
    }

    @Test("Dal riassunto che l'app passa al widget (`/api/oggi`), anche salvato e riletto; uno di una versione di prima si legge")
    func dallApp() throws {
        let senza = #"""
        {"giornata": 10, "giornata_lega": 7, "scadenza": "2026-11-08 14:30", "iniziata": true, "fase": "in_corso",
         "formazione": {"modulo": "3-4-3", "punteggio_atteso": 71.5}, "in_corso": null, "senza_formazione": true,
         "prossima": {"giornata": 11, "giornata_lega": 8, "scadenza": "2026-11-14 14:50", "prepara_da": "2026-11-11 14:50", "con_probabili": false}}
        """#
        let o: Oggi = try Decodifica.decodifica(Data(senza.utf8))
        let r = RiassuntoOggi(oggi: o)
        #expect(r.senzaFormazioneInCorso)
        #expect(r.prossimaDaPreparare == ProssimaDaPreparare(giornata: 11, giornataLega: 8, scadenza: Quando.data(Self.scadenzaProssima)))
        let riletto = try JSONDecoder().decode(RiassuntoOggi.self, from: try JSONEncoder().encode(r))
        #expect(riletto == r)
        #expect(riletto.senzaFormazioneInCorso)
        // c'era già prima della scadenza: niente prossima, come prima
        let conIn = senza.replacingOccurrences(of: #""senza_formazione": true,"#, with: "")
            .replacingOccurrences(of: #""in_corso": null"#, with: #""in_corso": {"giornata": 10, "punti_fatti": 31.5}"#)
        let c = RiassuntoOggi(oggi: try Decodifica.decodifica(Data(conIn.utf8)))
        #expect(!c.senzaFormazioneInCorso)
        #expect(c.prossimaDaPreparare == nil)
        #expect(c.puntiFatti == 31.5)
        let diPrima = try JSONDecoder().decode(RiassuntoOggi.self, from: Data(#"{"daControllare": 0, "scaricatoIl": 0, "fase": "in_corso"}"#.utf8))
        #expect(diPrima.senzaFormazione == nil)
        #expect(!diPrima.senzaFormazioneInCorso)
    }

    @Test("`senza_formazione` vale solo a giornata in corso e con un sì vero; senza la prossima resta l'invito, senza conto")
    func soloAGiornataInCorso() throws {
        func leggi(_ corpo: String) throws -> RiassuntoOggi {
            let w = try #require(RiassuntoWidget.leggi(Data(corpo.utf8)))
            return try #require(w.comeRiassuntoOggi())
        }
        let prossima = #""prossima": {"giornata": 11, "giornata_lega": 8, "scadenza": "2026-11-14 14:50"}"#
        // a giornata finita la prossima è già `giornata` e `scadenza`: nessun caso a parte
        let finita = try leggi(#"{"giornata": 11, "scadenza": "2026-11-14 14:50", "fase": "finita", "senza_formazione": true, \#(prossima)}"#)
        #expect(!finita.senzaFormazioneInCorso)
        #expect(finita.prossimaDaPreparare == nil)
        let prima = try leggi(#"{"giornata": 10, "scadenza": "2026-11-08 14:30", "senza_formazione": true, \#(prossima)}"#)
        #expect(!prima.senzaFormazioneInCorso)
        let strano = try leggi(#"{"giornata": 10, "scadenza": "2026-11-08 14:30", "fase": "in_corso", "senza_formazione": "sì", \#(prossima)}"#)
        #expect(!strano.senzaFormazioneInCorso, "un valore strano vale «no», come nell'app")
        #expect(strano.giornata == 10, "un campo strano non rompe il resto")
        // ultima giornata della stagione: il server non ha una prossima da mandare
        let ultima = try leggi(#"{"giornata": 38, "scadenza": "2027-05-23 14:30", "fase": "in_corso", "senza_formazione": true}"#)
        #expect(ultima.senzaFormazioneInCorso)
        #expect(ultima.prossimaDaPreparare == nil)
        #expect(ultima.scadenzaDelConto == nil, "niente conto alla rovescia verso una giornata che non c'è")
        #expect(ultima.formeRigaInLineaSenzaFormazione(adesso: Date()) == [ParoleWidget.preparaProssima])
    }

    @Test("Le parole sono quelle della web e della Formazione (`oggi.gia_iniziata`, `oggi.prepara_prossima` del catalogo comune)")
    func paroleComeLaWeb() {
        #expect(ParoleWidget.giaIniziata == Catalogo.Oggi.giaIniziata)
        #expect(ParoleWidget.preparaProssima == Catalogo.Oggi.preparaProssima)
    }

    @Test("Riga in linea e VoiceOver: l'invito con il conto alla rovescia, che si perde prima dell'invito; la frase intera a voce")
    func righe() throws {
        let r = try riassunto("widget-senza-formazione")
        let adesso = try #require(Quando.data("2026-11-10 12:50"))
        #expect(r.formeRigaInLineaSenzaFormazione(adesso: adesso) == ["Prepara la prossima: 4 giorni 2 h", "Prepara la prossima"])
        let scadenza = try #require(Quando.data(Self.scadenzaProssima))
        #expect(r.descrizioneSenzaFormazione
                == "Giornata 7, 10ª di Serie A. Questa giornata è già iniziata. Prepara la prossima: Giornata 8, 11ª di Serie A, scadenza \(Quando.leggibile(scadenza)).")
    }
}
