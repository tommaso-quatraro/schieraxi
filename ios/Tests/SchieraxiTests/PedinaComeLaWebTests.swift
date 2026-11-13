import Foundation
import Testing
@testable import Schieraxi

/// La pedina sul campo come `pedina` della web (#616, #673; decisione 2 del proprietario: resta il volto): nel disco il fantavoto
/// atteso (a partita finita quello preso), sotto il cognome «gioca N%» solo sotto l'80% (arancio fra 50 e 79, rosso sotto 50, sul
/// numero che si legge), lo stato a parole, a partita cominciata il suo stato, a formazione chiusa quando gioca chi deve ancora
/// giocare. Niente avversario («vs NAP»): sta nella scheda. VoiceOver dice le stesse cose, come `vocePedina`. Dati inventati.
@Suite("Pedina del campo come la web")
struct PedinaComeLaWebTests {
    /// Un giocatore inventato con questo pezzo di JSON in più (l'avversario c'è, ma la pedina non lo dice).
    private func giocatore(_ altro: String) throws -> Giocatore {
        let json = #"{"id": 7, "nome": "Mario Prova", "ruolo": "D", "fv_atteso": 6.5, "avversario": "napoli", "in_casa": false, \#(altro)}"#
        return try Decodifica.decodifica(Data(json.utf8))
    }

    // MARK: «gioca N%»

    @Test("Dall'80% in su niente «gioca N%»: il fantavoto basta (79,6% si legge «80%»)", arguments: [0.8, 0.796, 0.92, 1.0])
    func sicuroSenzaGioca(p: Double) throws {
        let c = LetturaPedina.contenuto(try giocatore(#""p_voto": \#(p)"#))
        #expect(c.pezzi.isEmpty)
        #expect(c.valore == 6.5)
        #expect(c.voce == "Mario Prova, fantavoto atteso 6,5")
    }

    @Test("Fra 50 e 79 «gioca N%» arancio, sotto 50 rosso", arguments: [(0.79, "gioca 79%", true), (0.5, "gioca 50%", true),
                                                                    (0.45, "gioca 45%", false), (0.0, "gioca 0%", false)])
    func giocaSotto80(p: Double, testo: String, arancio: Bool) throws {
        let c = LetturaPedina.contenuto(try giocatore(#""p_voto": \#(p)"#))
        #expect(c.pezzi == [LetturaPedina.Pezzo(testo: testo, tono: arancio ? .medio : .basso)])
    }

    @Test("Senza probabilità dal server si mostra «gioca 0%», come la web (`p_voto ?? 0`)")
    func senzaProbabilita() throws {
        let c = LetturaPedina.contenuto(try giocatore(#""titolarita": "titolare""#))
        #expect(c.pezzi.map(\.testo) == ["gioca 0%"])
    }

    // MARK: stato a parole

    @Test("In dubbio: «gioca N%» e la parola; VoiceOver le dice tutte e due, senza ruolo né avversario")
    func inDubbio() throws {
        let c = LetturaPedina.contenuto(try giocatore(#""p_voto": 0.45, "dubbio": true"#))
        #expect(c.pezzi == [LetturaPedina.Pezzo(testo: "gioca 45%", tono: .basso), LetturaPedina.Pezzo(testo: Catalogo.Tit.inDubbio, tono: .parola)])
        #expect(c.voce == "Mario Prova, fantavoto atteso 6,5, gioca al 45 per cento, In dubbio")
        #expect(!c.voce.contains("Napoli") && !c.voce.contains("difensore"))
    }

    @Test("Infortunato o squalificato: la parola in rosso basta, niente «gioca 0%»", arguments: ["infortunato", "squalificato"])
    func nonGioca(stato: String) throws {
        let c = LetturaPedina.contenuto(try giocatore(#""p_voto": 0.0, "stato": "\#(stato)""#))
        #expect(c.pezzi.count == 1)
        #expect(c.pezzi.first?.tono == .basso)
        #expect(c.pezzi.first?.testo == (stato == "infortunato" ? Catalogo.Oggi.infortunato : Catalogo.Oggi.squalificato))
        #expect(!c.voce.contains("per cento"))
    }

    // MARK: la partita

    @Test("A partita cominciata il suo stato al posto di «gioca N%»")
    func partitaInCorso() throws {
        let g = try giocatore(#""p_voto": 0.72, "stato_partita": "in_corso", "etichetta": {"codice": "in_corso", "testo": "Partita in corso", "tono": "positivo"}"#)
        let c = LetturaPedina.contenuto(g)
        #expect(c.pezzi == [LetturaPedina.Pezzo(testo: "Partita in corso", tono: .parola)])
        #expect(c.valore == 6.5, "senza voto nel disco resta il fantavoto atteso")
        #expect(c.voce == "Mario Prova, fantavoto atteso 6,5, Partita in corso")
    }

    @Test("A partita finita nel disco il fantavoto preso, e VoiceOver dice quello")
    func partitaFinita() throws {
        let c = LetturaPedina.contenuto(try giocatore(#""p_voto": 0.72, "stato_partita": "fatto", "fv_preso": 7"#))
        #expect(c.valore == 7)
        #expect(c.pezzi.isEmpty)
        #expect(c.voce == "Mario Prova, fantavoto 7,0")
    }

    @Test("Partita rinviata: «Rinviata» al posto di «gioca N%»")
    func rinviata() throws {
        let c = LetturaPedina.contenuto(try giocatore(#""p_voto": 0.5, "rinvio": "aspetta""#))
        #expect(c.pezzi == [LetturaPedina.Pezzo(testo: Catalogo.Tit.stRinviata, tono: .parola)])
        #expect(c.voce == "Mario Prova, fantavoto atteso 6,5, Rinviata")
    }

    @Test("A formazione chiusa, per chi deve ancora giocare, quando gioca (con l'ora dell'app)")
    func daGiocare() throws {
        let adesso = try #require(Quando.data("2026-10-31T12:00:00"))
        let g = try giocatore(#""p_voto": 0.6, "stato_partita": "da_giocare", "data_partita": "2026-10-31T18:00:00""#)
        let c = LetturaPedina.contenuto(g, adesso: adesso)
        let quando = Quando.relativa(try #require(Quando.data("2026-10-31T18:00:00")), adesso: adesso)
        #expect(c.pezzi == [LetturaPedina.Pezzo(testo: quando, tono: .parola)])
        #expect(c.voce == "Mario Prova, fantavoto atteso 6,5, \(quando)")
    }

    // MARK: parole per VoiceOver

    @Test("«gioca al 45 per cento», con l'apostrofo davanti a 8, 11 e agli ottanta")
    func voceGioca() {
        #expect(LetturaPedina.voceGioca(45) == "gioca al 45 per cento")
        #expect(LetturaPedina.voceGioca(8) == "gioca all'8 per cento")
        #expect(LetturaPedina.voceGioca(11) == "gioca all'11 per cento")
        #expect(LetturaPedina.voceGioca(85) == Catalogo.Formazione.voceGiocaV(p: "85"))
    }

    @Test("La frase della pedina per VoiceOver è quella di `contenuto`")
    func vocePedina() throws {
        let g = try giocatore(#""p_voto": 0.45"#)
        #expect(g.vocePedina == LetturaPedina.contenuto(g).voce)
    }

    // MARK: soglia e nomi (usati anche da scheda e legenda)

    @Test("La soglia della pedina è quella della scheda e della web, sul numero che si legge")
    func soglia() {
        #expect(LetturaPedina.gioca(0.85) == "gioca 85%")
        #expect(LetturaPedina.gioca(nil) == nil)
        #expect(LetturaPedina.incerto(0.45))
        #expect(LetturaPedina.incerto(0.79))
        #expect(!LetturaPedina.incerto(0.80))
        #expect(!LetturaPedina.incerto(0.796), "si legge «80%»")
        #expect(!LetturaPedina.incerto(nil), "senza probabilità niente avviso")
        #expect(LetturaPedina.nomeSquadra("napoli") == "Napoli")
        #expect(LetturaPedina.nomeSquadra("XYZ") == "XYZ")
        #expect(LetturaPedina.nomeSquadra(" ") == nil)
    }

    @Test("Il testo su un fondo colorato va scuro o chiaro secondo il contrasto")
    func testoSulFondo() {
        #expect(LetturaPedina.testoScuro(suEsadecimale: "f3f4f6"), "fondo bianco: testo scuro")
        #expect(!LetturaPedina.testoScuro(suEsadecimale: "0a58a8"), "fondo blu scuro: testo chiaro")
        #expect(!LetturaPedina.testoScuro(suEsadecimale: "111827"))
        #expect(LetturaPedina.testoScuro(suEsadecimale: "f2d200"), "giallo: testo scuro")
    }
}
