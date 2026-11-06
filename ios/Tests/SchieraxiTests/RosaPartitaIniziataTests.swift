import Foundation
import Testing
@testable import Schieraxi

/// A destra delle righe della Rosa di una squadra, come `valoreRosa` di app.js (#367) e come le righe della Formazione (#313):
/// a partita iniziata niente più fantavoto atteso e «gioca N%». A partita finita con il voto il fantavoto preso con sotto
/// «fantavoto» (`mercato.fantavoto`), altrimenti «–» da solo: lo stato è già nella pillola dell'etichetta. La partita rinviata
/// resta come prima della partita. VoiceOver dice le stesse cose. Dati inventati.
@Suite("Righe della Rosa a partita iniziata: come la web")
struct RosaPartitaIniziataTests {
    /// Un giocatore della rosa inventato; `altro` è un pezzo di JSON in più dentro la sua previsione.
    private func rosa(_ altro: String) throws -> GiocatoreRosa {
        let json = #"""
        {"id": 31, "nome": "Paolo Esempio", "ruolo": "C", "squadra": "genoa", "squadra_slug": "genoa", "costo": 12, "quotazione": 14,
         "previsione": {"id": 31, "nome": "Paolo Esempio", "ruolo": "C", "squadra": "genoa", "avversario": "como", "in_casa": true,
                        "fv_atteso": 6.4, "p_voto": 0.72, "indice": 58, \#(altro)}}
        """#
        return try Decodifica.decodifica(Data(json.utf8))
    }

    /// Un giocatore della rosa senza previsione (non gioca questa giornata, o il server non l'ha riconosciuto: senza `id`).
    private func senzaPrevisione(conId: Bool) throws -> GiocatoreRosa {
        let id = conId ? "31" : "null"
        let json = #"{"id": \#(id), "nome": "Paolo Esempio", "ruolo": "C", "squadra": "genoa", "costo": 12, "quotazione": 14}"#
        return try Decodifica.decodifica(Data(json.utf8))
    }

    /// «gioca 72%» con le parole della web (`giocatore.gioca`).
    private func gioca72() throws -> String {
        try TestiWeb().italiano("giocatore.gioca").replacingOccurrences(of: "{p}", with: "72%")
    }

    /// Il pezzo fisso della frase di VoiceOver: nome, ruolo, squadra, costo, quotazione e avversario.
    private static let inizioVoce = "Paolo Esempio, centrocampista, GEN · costo 12 · quotazione 14 · vs COM"

    // MARK: prima della partita, e partita rinviata: fantavoto atteso e «gioca N%»

    @Test("Prima della partita e con la partita rinviata: fantavoto atteso e «gioca 72%», come la web", arguments: [
        #""titolarita": "titolare""#,
        #""stato_partita": "da_giocare", "etichetta": {"codice": "da_giocare", "testo": "Da giocare", "tono": "neutro"}"#,
        // la riga della web usa `esitoPartita`: il rinvio cambia solo la pedina del campo
        #""rinvio": "aspetta", "etichetta": {"codice": "rinviata", "testo": "Rinviata", "tono": "attenzione"}"#,
        #""stato_partita": "rinviata""#,
    ])
    func primaDellaPartita(campi: String) throws {
        let g = try rosa(campi)
        let gioca = try gioca72()
        #expect(RigaRosa.numero(g) == "6,4")
        #expect(RigaRosa.sottoNumero(g) == gioca)
        #expect(RigaRosa.voce(g).contains("fantavoto atteso 6,4"))
    }

    // MARK: partita finita con il voto: il fantavoto preso

    @Test("A partita finita con il voto: il fantavoto preso con sotto «fantavoto», mai «gioca 72%»", arguments: [
        #""stato_partita": "fatto", "fv_preso": 3.5, "etichetta": {"codice": "voto", "testo": "Ha giocato", "tono": "positivo"}"#,
        #""stato_partita": "fatto", "fv_preso": 3.5"#,
    ])
    func fantavotoPreso(campi: String) throws {
        let g = try rosa(campi)
        let fantavoto = try TestiWeb().italiano("mercato.fantavoto")
        #expect(RigaRosa.numero(g) == "3,5")
        #expect(RigaRosa.sottoNumero(g) == fantavoto)
    }

    @Test("VoiceOver a partita finita: «fantavoto 3,5» come la pedina, senza fantavoto atteso né «per cento»")
    func voceConVoto() throws {
        let g = try rosa(#""stato_partita": "fatto", "fv_preso": 3.5, "etichetta": {"codice": "voto", "testo": "Ha giocato", "tono": "positivo"}"#)
        let preso = try TestiWeb().italiano("formazione.fv_preso").replacingOccurrences(of: "{fv}", with: "3,5")
        #expect(RigaRosa.voce(g) == "\(Self.inizioVoce), \(preso), ha giocato")
    }

    // MARK: partita iniziata senza voto: «–» da solo

    @Test("Partita in corso, voto in arrivo, senza voto: «–» da solo, lo stato sta nella pillola", arguments: [
        #""stato_partita": "in_corso", "etichetta": {"codice": "in_corso", "testo": "Partita in corso", "tono": "positivo"}"#,
        #""stato_partita": "in_corso""#,
        #""etichetta": {"codice": "voto_in_arrivo", "testo": "Voto in arrivo", "tono": "neutro"}"#,
        #""stato_partita": "attesa_voti""#,
        #""stato_partita": "senza_voto", "etichetta": {"codice": "senza_voto", "testo": "Senza voto", "tono": "attenzione"}"#,
        // server senza `fv_preso`: ha giocato ma il numero non c'è
        #""stato_partita": "fatto""#,
    ])
    func senzaVoto(campi: String) throws {
        let g = try rosa(campi)
        #expect(RigaRosa.numero(g) == "–")
        #expect(RigaRosa.sottoNumero(g) == nil)
        #expect(!RigaRosa.voce(g).contains("per cento"))
        #expect(!RigaRosa.voce(g).contains("fantavoto"))
    }

    @Test("VoiceOver a partita in corso: lo stato dalla pillola, il trattino non si legge")
    func voceInCorso() throws {
        let g = try rosa(#""stato_partita": "in_corso", "etichetta": {"codice": "in_corso", "testo": "Partita in corso", "tono": "positivo"}"#)
        #expect(RigaRosa.voce(g) == "\(Self.inizioVoce), partita in corso")
    }

    // MARK: prima della partita VoiceOver legge anche le etichette che si vedono

    @Test("VoiceOver prima della partita: fantavoto atteso e le etichette che si vedono, come la web")
    func voceConEtichette() throws {
        let g = try rosa(#""titolarita": "titolare", "etichetta": {"codice": "titolare", "testo": "Probabile titolare", "tono": "positivo"}"#)
        #expect(RigaRosa.voce(g) == "\(Self.inizioVoce), fantavoto atteso 6,4, probabile titolare")
    }

    // MARK: senza previsione

    @Test("Senza previsione: nessun numero, «non gioca» (o «?» se il server non ha riconosciuto il giocatore)")
    func senzaPrevisioneComeLaWeb() throws {
        let nonGioca = try TestiWeb().italiano("scambio.non_gioca")
        let riconosciuto = try senzaPrevisione(conId: true)
        #expect(RigaRosa.numero(riconosciuto) == nil)
        #expect(RigaRosa.sottoNumero(riconosciuto) == nonGioca)
        #expect(RigaRosa.voce(riconosciuto) == "Paolo Esempio, centrocampista, GEN · costo 12 · quotazione 14, \(nonGioca)")
        let sconosciuto = try senzaPrevisione(conId: false)
        #expect(RigaRosa.numero(sconosciuto) == nil)
        #expect(RigaRosa.sottoNumero(sconosciuto) == "?")
    }
}
