import Foundation
import Testing
@testable import Schieraxi

/// Sotto la pedina del campo, come la web (`esitoPedina` di app.js, #283 e #284): a partita iniziata non c'è più «gioca N%» ma il
/// fantavoto preso o lo stato della partita; una partita rinviata dice «Rinviata», prima e dopo la scadenza. Le parole sono quelle
/// del server (`etichetta.testo`) o, con un server vecchio, quelle di `testi.js`. VoiceOver dice le stesse. Dati inventati.
@Suite("Pedina del campo: stato della partita come la web")
struct EsitoPedinaTests {
    /// Un giocatore inventato con questo pezzo di JSON in più.
    private func giocatore(_ altro: String) throws -> Giocatore {
        let json = #"{"id": 7, "nome": "Mario Prova", "ruolo": "D", "fv_atteso": 6.5, "avversario": "napoli", "in_casa": false, \#(altro)}"#
        return try Decodifica.decodifica(Data(json.utf8))
    }

    /// Un'etichetta del server.
    private static func etichetta(_ codice: String, _ testo: String, _ tono: String = "neutro") -> String {
        #""etichetta": {"codice": "\#(codice)", "testo": "\#(testo)", "tono": "\#(tono)"}"#
    }

    // MARK: la partita non è cominciata: resta «gioca N%»

    @Test("Prima della scadenza, partita normale: niente esito, resta «gioca N%»", arguments: [
        #""titolarita": "titolare", "p_voto": 0.9, "etichetta": {"codice": "titolare", "testo": "Probabile titolare", "tono": "positivo"}"#,
        #""titolarita": "panchina", "p_voto": 0.3"#,
        #""p_voto": 0.72, "stato_partita": "da_giocare", "etichetta": {"codice": "da_giocare", "testo": "Da giocare", "tono": "neutro"}"#,
        #""p_voto": 0.72, "stato_partita": "da_giocare""#,
    ])
    func partitaNonCominciata(campi: String) throws {
        let g = try giocatore(campi)
        #expect(g.esitoPedina == nil)
    }

    // MARK: partita rinviata (#284)

    @Test("Partita rinviata, prima e dopo la scadenza: «Rinviata» come la web (`tit.st_rinviata`)", arguments: [
        // server nuovo: l'etichetta del server
        #""titolarita": "titolare", "p_voto": 0.5, "rinvio": "aspetta", "etichetta": {"codice": "rinviata", "testo": "Rinviata", "tono": "attenzione"}"#,
        // server vecchio senza etichetta: dal modo del rinvio, o dallo stato della partita dopo la scadenza
        #""titolarita": "titolare", "p_voto": 0.5, "rinvio": "aspetta""#,
        #""p_voto": 0.5, "stato_partita": "rinviata""#,
    ])
    func rinviata(campi: String) throws {
        let web = try TestiWeb().italiano("tit.st_rinviata")
        let g = try giocatore(campi)
        #expect(g.esitoPedina == web)
    }

    @Test("Con l'etichetta decide il suo codice, come la web: senza «rinviata» resta «gioca N%»")
    func decideLEtichetta() throws {
        let g = try giocatore(#""p_voto": 0.5, "rinvio": "aspetta", \#(Self.etichetta("titolare", "Probabile titolare", "positivo"))"#)
        #expect(g.esitoPedina == nil)
    }

    @Test("Il testo del server si mostra com'è (anche in inglese)")
    func testoDelServer() throws {
        let g = try giocatore(#""p_voto": 0.5, \#(Self.etichetta("rinviata", "Postponed", "attenzione"))"#)
        #expect(g.esitoPedina == "Postponed")
    }

    // MARK: partita cominciata (#283)

    @Test("A partita finita con il voto: il fantavoto preso (`formazione.fv_preso`), mai «gioca 72%»", arguments: [
        #""p_voto": 0.717, "stato_partita": "fatto", "fv_preso": 3.5, "etichetta": {"codice": "voto", "testo": "Ha giocato", "tono": "positivo"}"#,
        #""p_voto": 0.717, "stato_partita": "fatto", "fv_preso": 3.5"#,
    ])
    func fantavotoPreso(campi: String) throws {
        let web = try TestiWeb().italiano("formazione.fv_preso").replacingOccurrences(of: "{fv}", with: "3,5")
        let g = try giocatore(campi)
        #expect(g.esitoPedina == web)
    }

    /// Lo stato della partita senza etichetta (server vecchio) e la chiave di testi.js con la stessa parola.
    static let statiSenzaEtichetta: [(String, String)] = [
        ("in_corso", "tit.st_in_corso"), ("attesa_voti", "tit.st_attesa_voti"), ("senza_voto", "tit.st_senza_voto"), ("fatto", "tit.st_fatto"),
    ]

    @Test("Server senza etichetta: le parole di testi.js dallo stato della partita", arguments: EsitoPedinaTests.statiSenzaEtichetta)
    func statoSenzaEtichetta(stato: String, chiave: String) throws {
        let parola = try TestiWeb().italiano(chiave)
        let g = try giocatore(#""p_voto": 0.72, "stato_partita": "\#(stato)""#)
        #expect(g.esitoPedina == parola)
    }

    /// Il codice dell'etichetta del server e la chiave di testi.js con la stessa parola (`fanta/etichette.py`).
    static let codiciPartita: [(String, String, String)] = [
        ("in_corso", "in_corso", "tit.st_in_corso"), ("voto_in_arrivo", "attesa_voti", "tit.st_attesa_voti"),
        ("senza_voto", "senza_voto", "tit.st_senza_voto"), ("voto", "fatto", "tit.st_fatto"),
    ]

    @Test("Con l'etichetta: il suo testo, che è la parola di testi.js", arguments: EsitoPedinaTests.codiciPartita)
    func statoConEtichetta(codice: String, stato: String, chiave: String) throws {
        let parola = try TestiWeb().italiano(chiave)
        let g = try giocatore(#""p_voto": 0.72, "stato_partita": "\#(stato)", \#(Self.etichetta(codice, parola))"#)
        #expect(g.esitoPedina == parola)
    }

    @Test("Basta il codice dell'etichetta, anche senza `stato_partita`")
    func soloIlCodice() throws {
        let g = try giocatore(#""p_voto": 0.72, \#(Self.etichetta("in_corso", "Partita in corso", "positivo"))"#)
        #expect(g.esitoPedina == "Partita in corso")
    }

    @Test("Un'etichetta vuota o strana non toglie lo stato della partita", arguments: [
        #""etichetta": {"codice": "in_corso", "testo": ""}"#,
        #""etichetta": "Partita in corso""#,
        #""etichetta": null"#,
    ])
    func etichettaStrana(campo: String) throws {
        let g = try giocatore(#""p_voto": 0.72, "stato_partita": "in_corso", \#(campo)"#)
        #expect(g.esitoPedina == "Partita in corso")
    }

    @Test("`rinvio` o `fv_preso` di forma strana non rompono la formazione")
    func campiStrani() throws {
        let g = try giocatore(#""p_voto": 0.72, "rinvio": {"modo": "aspetta"}, "fv_preso": "tanti""#)
        #expect(g.esitoPedina == nil)
        #expect(g.pVoto == 0.72)
    }

    // MARK: VoiceOver

    @Test("VoiceOver: a partita iniziata l'esito al posto di «gioca al N per cento», come `vocePedina` della web")
    func voceConEsito() throws {
        let g = try giocatore(#""p_voto": 0.72, "stato_partita": "in_corso", \#(Self.etichetta("in_corso", "Partita in corso", "positivo"))"#)
        #expect(g.vocePedina == "Mario Prova, difensore, fantavoto atteso 6,5, Partita in corso, avversario Napoli, in trasferta")
    }

    @Test("VoiceOver: partita rinviata e fantavoto preso")
    func voceRinviataEVoto() throws {
        let rinviata = try giocatore(#""p_voto": 0.5, "rinvio": "aspetta""#)
        #expect(rinviata.vocePedina == "Mario Prova, difensore, fantavoto atteso 6,5, Rinviata, avversario Napoli, in trasferta")
        let votato = try giocatore(#""p_voto": 0.72, "stato_partita": "fatto", "fv_preso": 7""#)
        #expect(votato.vocePedina.contains(", fantavoto 7,0, "))
        #expect(!votato.vocePedina.contains("per cento"))
    }

    @Test("VoiceOver prima della partita: la frase di sempre, con «gioca al N per cento»")
    func voceSenzaEsito() throws {
        let g = try giocatore(#""p_voto": 0.45"#)
        #expect(g.vocePedina == "Mario Prova, difensore, fantavoto atteso 6,5, gioca al 45 per cento, non è sicuro di giocare, avversario Napoli, in trasferta")
    }
}
