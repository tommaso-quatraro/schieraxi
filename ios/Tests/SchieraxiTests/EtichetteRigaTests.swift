import Foundation
import Testing
@testable import Schieraxi

/// Le etichette sotto il nome nelle righe di «Metti in campo» e di «Sostituisci», e sotto il titolo per chi entra, come
/// `etichetteGiocatore` della web con `giocaPoco` (#778): prima lo stato a parole (a partita cominciata senza voto, lo stato della
/// partita), poi «gioca N%» sotto l'80% e le parole in più della riga («Si passa al …»), poi «Diffidato» e per ultima la nota che
/// spiega lo stato. Stesse parole e stesso ordine della web; i colori come le sue pillole (arancio, rosso, grigio).
@Suite("Etichette delle righe dei cambi, come la web")
struct EtichetteRigaTests {

    @Test("In dubbio: lo stato, «gioca N%», «Diffidato» e la nota, in quest'ordine")
    func inDubbio() throws {
        let g = try giocatore(#""p_voto": 0.62, "dubbio": true, "diffidato": true, "nota": " affaticamento, si decide domani ""#)
        let pezzi = EtichetteRiga.pezzi(g)
        #expect(pezzi.map(\.testo) == [Catalogo.Tit.inDubbio, "gioca 62%", Catalogo.Oggi.diffidatoTipo, "affaticamento, si decide domani"])
        #expect(pezzi.map(\.tono) == [.medio, .medio, .medio, .parola])
    }

    @Test("Infortunato: la parola rossa e la nota; «gioca 0%» no, la parola basta")
    func infortunato() throws {
        let g = try giocatore(#""p_voto": 0.0, "stato": "infortunato", "nota": "lesione al flessore, rientro a dicembre""#)
        let pezzi = EtichetteRiga.pezzi(g)
        #expect(pezzi.map(\.testo) == [Catalogo.Oggi.infortunato, "lesione al flessore, rientro a dicembre"])
        #expect(pezzi.map(\.tono) == [.basso, .parola])
    }

    @Test("Le parole in più della riga vanno dopo «gioca N%» e prima di «Diffidato» e della nota")
    func paroleInPiu() throws {
        let g = try giocatore(#""p_voto": 0.45, "dubbio": true, "diffidato": true, "nota": "febbre""#)
        let pezzi = EtichetteRiga.pezzi(g, inPiu: ["Si passa al 4-4-2"])
        #expect(pezzi.map(\.testo) == [Catalogo.Tit.inDubbio, "gioca 45%", "Si passa al 4-4-2", Catalogo.Oggi.diffidatoTipo, "febbre"])
        #expect(pezzi.map(\.tono) == [.medio, .basso, .parola, .medio, .parola])
    }

    @Test("A partita cominciata senza voto: lo stato della partita al posto dello stato, niente «gioca N%» né nota; «Diffidato» sì")
    func partitaCominciata() throws {
        let g = try giocatore(#""p_voto": 0.6, "dubbio": true, "diffidato": true, "nota": "febbre", "stato_partita": "in_corso""#)
        #expect(EtichetteRiga.pezzi(g).map(\.testo) == [Catalogo.Tit.stInCorso, Catalogo.Oggi.diffidatoTipo])
    }

    @Test("Chi gioca quasi di sicuro e non ha uno stato: niente etichette; diffidato, solo «Diffidato»")
    func senzaStato() throws {
        #expect(EtichetteRiga.pezzi(try giocatore(#""p_voto": 0.9"#)).isEmpty)
        #expect(EtichetteRiga.pezzi(try giocatore(#""p_voto": 0.9, "diffidato": true, "nota": "senza stato non si scrive""#))
            .map(\.testo) == [Catalogo.Oggi.diffidatoTipo])
    }

    @Test("Lo stato con le parole del server, senza « · gioca N%»")
    func etichettaDelServer() throws {
        let g = try giocatore(#""p_voto": 0.62, "etichetta": {"codice": "in_dubbio", "testo": "In dubbio · gioca 62%", "tono": "attenzione"}"#)
        #expect(EtichetteRiga.pezzi(g).map(\.testo) == ["In dubbio", "gioca 62%"])
    }

    // MARK: aiuti

    /// Un centrocampista inventato con i campi dati in più.
    private func giocatore(_ campi: String) throws -> Giocatore {
        try Decodifica.decodifica(Data(#"{"id": 7, "nome": "Rossi", "ruolo": "C", "squadra": "inter", "fv_atteso": 6.8, \#(campi)}"#.utf8))
    }
}
