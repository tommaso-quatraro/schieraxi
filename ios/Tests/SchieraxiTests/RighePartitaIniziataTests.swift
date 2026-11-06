import Foundation
import Testing
@testable import Schieraxi

/// A destra delle righe dei giocatori (Formazione, Seguiti, Oggi), come `voceGiocatore` di app.js (#313): a partita iniziata
/// niente più fantavoto atteso e «gioca N%». A partita finita con il voto il fantavoto preso con sotto «fantavoto»
/// (`mercato.fantavoto`), altrimenti «–» da solo: lo stato è già nella pillola dell'etichetta. La partita rinviata resta come
/// prima della partita (la riga usa `esitoPartita`, non `esitoPedina`). VoiceOver dice le stesse cose. Dati inventati.
@Suite("Righe dei giocatori a partita iniziata: come la web")
struct RighePartitaIniziataTests {
    /// Un giocatore inventato con questo pezzo di JSON in più.
    private func giocatore(_ altro: String) throws -> Giocatore {
        let json = #"""
        {"id": 31, "nome": "Paolo Esempio", "ruolo": "C", "squadra": "genoa", "avversario": "como", "in_casa": true,
         "fv_atteso": 6.4, "p_voto": 0.72, "indice": 58, \#(altro)}
        """#
        return try Decodifica.decodifica(Data(json.utf8))
    }

    /// «gioca 72%» con le parole della web (`giocatore.gioca`).
    private func gioca72() throws -> String {
        try TestiWeb().italiano("giocatore.gioca").replacingOccurrences(of: "{p}", with: "72%")
    }

    /// Un motivo di «Perché questo numero», così il numero potrebbe essere un pulsante a sé.
    private static let perche = #""perche_numero": [{"chiave": "partita", "testo": "partita facile in casa", "effetto": 0.3}]"#

    // MARK: prima della partita, e partita rinviata: fantavoto atteso e «gioca N%»

    @Test("Prima della partita e con la partita rinviata: fantavoto atteso e «gioca 72%», come la web", arguments: [
        #""titolarita": "titolare""#,
        #""stato_partita": "da_giocare", "etichetta": {"codice": "da_giocare", "testo": "Da giocare", "tono": "neutro"}"#,
        // la riga della web usa `esitoPartita`: il rinvio cambia solo la pedina del campo
        #""rinvio": "aspetta", "etichetta": {"codice": "rinviata", "testo": "Rinviata", "tono": "attenzione"}"#,
        #""stato_partita": "rinviata""#,
    ])
    func primaDellaPartita(campi: String) throws {
        let g = try giocatore(campi)
        let gioca = try gioca72()
        #expect(RigaGiocatore.numero(g) == "6,4")
        #expect(RigaGiocatore.sottoNumero(g) == gioca)
        #expect(RigaGiocatore.voce(g).contains("fantavoto atteso 6,4, gioca al 72 per cento"))
    }

    // MARK: partita finita con il voto: il fantavoto preso

    @Test("A partita finita con il voto: il fantavoto preso con sotto «fantavoto», mai «gioca 72%»", arguments: [
        #""stato_partita": "fatto", "fv_preso": 3.5, "etichetta": {"codice": "voto", "testo": "Ha giocato", "tono": "positivo"}"#,
        #""stato_partita": "fatto", "fv_preso": 3.5"#,
    ])
    func fantavotoPreso(campi: String) throws {
        let g = try giocatore(campi)
        let fantavoto = try TestiWeb().italiano("mercato.fantavoto")
        #expect(RigaGiocatore.numero(g) == "3,5")
        #expect(RigaGiocatore.sottoNumero(g) == fantavoto)
    }

    @Test("VoiceOver a partita finita: «fantavoto 3,5» come la pedina, senza fantavoto atteso né «per cento»")
    func voceConVoto() throws {
        let g = try giocatore(#""stato_partita": "fatto", "fv_preso": 3.5, "etichetta": {"codice": "voto", "testo": "Ha giocato", "tono": "positivo"}"#)
        let preso = try TestiWeb().italiano("formazione.fv_preso").replacingOccurrences(of: "{fv}", with: "3,5")
        #expect(RigaGiocatore.voce(g) == "Paolo Esempio, centrocampista, Genoa, in casa contro Como, \(preso), indice 58 su 100, ha giocato")
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
        let g = try giocatore(campi)
        #expect(RigaGiocatore.numero(g) == "–")
        #expect(RigaGiocatore.sottoNumero(g) == nil)
        #expect(!RigaGiocatore.voce(g).contains("per cento"))
        #expect(!RigaGiocatore.voce(g).contains("fantavoto"))
    }

    @Test("VoiceOver a partita in corso: lo stato dalla pillola, il trattino non si legge")
    func voceInCorso() throws {
        let g = try giocatore(#""stato_partita": "in_corso", "etichetta": {"codice": "in_corso", "testo": "Partita in corso", "tono": "positivo"}"#)
        #expect(RigaGiocatore.voce(g) == "Paolo Esempio, centrocampista, Genoa, in casa contro Como, indice 58 su 100, partita in corso")
    }

    // MARK: «Perché questo numero»

    @Test("A partita iniziata il numero non apre «Perché questo numero»: spiega il fantavoto atteso, che non si vede più")
    func perche() throws {
        let prima = try giocatore(Self.perche)
        #expect(RigaGiocatore.numeroConPerche(prima))
        let finita = try giocatore(#""stato_partita": "fatto", "fv_preso": 3.5, \#(Self.perche)"#)
        #expect(!RigaGiocatore.numeroConPerche(finita))
        let inCorso = try giocatore(#""stato_partita": "in_corso", \#(Self.perche)"#)
        #expect(!RigaGiocatore.numeroConPerche(inCorso))
    }
}
