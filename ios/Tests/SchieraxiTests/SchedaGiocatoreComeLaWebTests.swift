import Foundation
import Testing
@testable import Schieraxi

/// La scheda del giocatore, una sola come la web (#616, `htmlScheda` e `riempiScheda` di app.js): in alto la partita senza la
/// giornata, il fantavoto atteso «se gioca» con «gioca N%» e lo stato a parole, la nota della fonte, «Perché è titolare» e
/// «Perché questo numero»; il resto dietro «Tutti i numeri». Frasi dal catalogo comune, numeri del server. Dati inventati.
@Suite("La scheda del giocatore come la web")
struct SchedaGiocatoreComeLaWebTests {
    /// Un giocatore inventato; `extra` comincia con «, » e aggiunge campi della risposta del server.
    private func giocatore(id: Int = 7, nome: String = "Mauro Retalli", _ extra: String = "") throws -> Giocatore {
        try Decodifica.decodifica(Data(#"{"id": \#(id), "nome": "\#(nome)", "ruolo": "A", "squadra": "genoa"\#(extra)}"#.utf8))
    }

    // MARK: intestazione

    @Test("Sotto il nome «Attaccante · Genoa», con il ruolo per intero del catalogo")
    func ruoloEClub() {
        #expect(LetturaScheda.ruoloEClub(ruolo: "A", club: "Genoa") == "\(Catalogo.Ruolo.a1) · Genoa")
        #expect(LetturaScheda.ruoloEClub(ruolo: "P", club: "Inter") == "\(Catalogo.Ruolo.p1) · Inter")
        #expect(LetturaScheda.ruoloEClub(ruolo: "C", club: "Como") == "\(Catalogo.Ruolo.c1) · Como")
        #expect(LetturaScheda.ruoloEClub(ruolo: "D", club: nil) == Catalogo.Ruolo.d1, "senza club niente «·» in fondo")
        #expect(LetturaScheda.ruoloEClub(ruolo: "X", club: "Como") == "X · Como", "un ruolo sconosciuto si scrive com'è")
    }

    @Test("La partita senza la giornata: «In casa contro Como · …», «In trasferta contro Hellas Verona · …»")
    func partita() throws {
        let adesso = try #require(Quando.data("2026-10-30T12:00"))
        let quando = Quando.leggibile("2026-10-31T20:45:00", adesso: adesso)
        let casa = try giocatore(#", "avversario": "como", "in_casa": true, "data_partita": "2026-10-31T20:45:00", "giornata": 11, "giornata_lega": 8"#)
        let testo = try #require(LetturaScheda.partita(casa, adesso: adesso))
        #expect(testo == Catalogo.Formazione.partitaCasa(avv: "Como", quando: quando))
        #expect(!testo.contains("Giornata") && !testo.contains("Serie A"), "la scheda si apre dalla Formazione di quella giornata")
        let fuori = try giocatore(#", "avversario": "hellas verona", "in_casa": false, "data_partita": "2026-10-31T20:45:00""#)
        #expect(LetturaScheda.partita(fuori, adesso: adesso) == Catalogo.Formazione.partitaFuori(avv: "Hellas Verona", quando: quando))
        let senzaAvversario = try giocatore()
        #expect(LetturaScheda.partita(senzaAvversario, adesso: adesso) == nil, "senza avversario niente riga")
        let senzaData = try giocatore(#", "avversario": "como", "in_casa": true"#)
        #expect(LetturaScheda.partita(senzaData, adesso: adesso) == Catalogo.Formazione.partitaCasa(avv: "Como", quando: "–"),
                "senza data «–», come `quando` della web")
    }

    @Test("L'intestazione dalla Formazione (la previsione già letta) e dalla scheda del server")
    func testa() throws {
        let previsione = try giocatore()
        let dallaFormazione = TestaScheda(previsione: previsione)
        #expect(dallaFormazione.id == 7 && dallaFormazione.nome == "Mauro Retalli" && dallaFormazione.ruolo == "A")
        #expect(dallaFormazione.club == "Genoa" && dallaFormazione.slug == "genoa")
        #expect(dallaFormazione.previsione?.id == 7)
        let s: SchedaGiocatore = try Decodifica.decodifica(Data(#"""
        {"calciatore": {"id": 7, "nome": "Mauro Retalli", "ruolo": "A", "squadra": "Hellas Verona", "squadra_slug": "verona"}}
        """#.utf8))
        let dalServer = TestaScheda(scheda: s)
        #expect(dalServer.club == "Hellas Verona" && dalServer.slug == "verona")
        #expect(dalServer.previsione == nil)
    }

    // MARK: le cifre

    @Test("Prima della partita: il fantavoto atteso «se gioca» e accanto «gioca N%», senza colore sopra l'80%")
    func cifreSicuro() throws {
        let g = try giocatore(#", "fv_atteso": 6.94, "p_voto": 0.85, "titolarita": "titolare""#)
        #expect(LetturaScheda.cifre(g) == .cifre(.atteso(6.94), accanto: .gioca(percento: 85, livello: .sicuro, parola: nil)),
                "le parole della titolarità («Probabile titolare») non si mostrano più")
    }

    @Test("In dubbio: «gioca 62%» arancio e la parola «In dubbio», senza « · gioca N%» dell'etichetta del server")
    func cifreDubbio() throws {
        let g = try giocatore(#", "fv_atteso": 7.9, "p_voto": 0.62, "dubbio": true, "etichetta": {"codice": "in_dubbio", "testo": "In dubbio · gioca 62%", "tono": "attenzione"}"#)
        let parola = ParolaStato(codice: "in_dubbio", testo: "In dubbio", classe: .arancio)
        #expect(LetturaScheda.cifre(g) == .cifre(.atteso(7.9), accanto: .gioca(percento: 62, livello: .medio, parola: parola)))
    }

    @Test("Infortunato senza etichetta (server vecchio): la parola del catalogo, rossa; il fantavoto che manca resta vuoto")
    func cifreInfortunato() throws {
        let g = try giocatore(#", "stato": "infortunato", "p_voto": 0.0"#)
        let parola = ParolaStato(codice: "infortunato", testo: Catalogo.Oggi.infortunato, classe: .rossa)
        #expect(LetturaScheda.cifre(g) == .cifre(.atteso(nil), accanto: .gioca(percento: 0, livello: .basso, parola: parola)))
        #expect(parola.nonGiocaDiSicuro)
    }

    @Test("Partita in corso: accanto al fantavoto atteso lo stato della partita al posto di «gioca N%»")
    func cifreInCorso() throws {
        let g = try giocatore(#", "fv_atteso": 6.5, "p_voto": 0.9, "stato_partita": "in_corso", "etichetta": {"codice": "in_corso", "testo": "Partita in corso", "tono": "positivo"}"#)
        #expect(LetturaScheda.cifre(g) == .cifre(.atteso(6.5), accanto: .stato("Partita in corso")))
    }

    @Test("Partita finita: il fantavoto preso, oppure lo stato («Senza voto») e niente accanto")
    func cifreFinita() throws {
        let preso = try giocatore(#", "fv_atteso": 6.5, "stato_partita": "fatto", "fv_preso": 7.5"#)
        #expect(LetturaScheda.cifre(preso) == .cifre(.preso(7.5), accanto: nil))
        let senzaVoto = try giocatore(#", "fv_atteso": 6.5, "stato_partita": "senza_voto""#)
        #expect(LetturaScheda.cifre(senzaVoto) == .cifre(.stato(Catalogo.Tit.stSenzaVoto), accanto: nil))
    }

    @Test("Senza previsione: la frase della web")
    func senzaPrevisione() {
        #expect(LetturaScheda.cifre(nil) == .nessunaPrevisione)
    }

    @Test("Le parole di stato: solo quelle che dicono se non gioca", arguments: [
        (#", "titolarita": "fuori""#, "fuori"), (#", "stato": "squalificato""#, "squalificato"),
        (#", "stato_partita": "rinviata""#, "rinviata"), (#", "rinvio": "aspetta""#, "rinviata"), (#", "dubbio": true"#, "in_dubbio"),
    ])
    func paroleDiStato(extra: String, codice: String) throws {
        let g = try giocatore(extra)
        let parola = try #require(ParolaStato(g))
        #expect(parola.codice == codice)
        let attese: [String: (testo: String, classe: ParolaStato.Classe)] = [
            "fuori": (Catalogo.Tit.fuori, .rossa), "squalificato": (Catalogo.Oggi.squalificato, .rossa),
            "rinviata": (Catalogo.Tit.stRinviata, .arancio), "in_dubbio": (Catalogo.Tit.inDubbio, .arancio),
        ]
        let attesa = try #require(attese[codice])
        #expect(parola.testo == attesa.testo)
        #expect(parola.classe == attesa.classe)
    }

    @Test("Nessuna parola per chi gioca, e per un'etichetta di titolarità del server")
    func nessunaParola() throws {
        let titolare = try giocatore(#", "titolarita": "titolare""#)
        #expect(ParolaStato(titolare) == nil)
        let probabile = try giocatore(#", "etichetta": {"codice": "probabile_titolare", "testo": "Probabile titolare", "tono": "positivo"}"#)
        #expect(ParolaStato(probabile) == nil)
    }

    // MARK: nota, perché, questa partita

    @Test("La nota della fonte solo con uno stato da spiegare, e mai a partita cominciata")
    func nota() throws {
        let dubbio = try giocatore(#", "dubbio": true, "nota": "  contusione al ginocchio  ""#)
        #expect(LetturaScheda.nota(dubbio) == "contusione al ginocchio")
        let senzaStato = try giocatore(#", "nota": "titolare fisso""#)
        #expect(LetturaScheda.nota(senzaStato) == nil, "senza stato non spiega niente")
        let vuota = try giocatore(#", "dubbio": true, "nota": "  ""#)
        #expect(LetturaScheda.nota(vuota) == nil)
        let inCorso = try giocatore(#", "dubbio": true, "nota": "x", "stato_partita": "in_corso""#)
        #expect(LetturaScheda.nota(inCorso) == nil)
    }

    @Test("«Perché questo numero» dentro la scheda: a partita cominciata senza «gioca», a partita finita niente")
    func percheNumero() throws {
        let motivi = #", "fv_atteso_medio_ruolo": 6.9, "perche_numero": [{"chiave": "gioca", "testo": "gioca il 62%: dubbio", "effetto": null}, {"chiave": "gol", "testo": "segna più della media del ruolo", "effetto": 0.9}]"#
        let primaDellaPartita = try giocatore(motivi)
        let prima = try #require(LetturaScheda.perche(primaDellaPartita))
        #expect(prima.righe.map(\.chiave) == ["gioca", "gol"])
        let durante = try giocatore(motivi + #", "stato_partita": "in_corso""#)
        let inCorso = try #require(LetturaScheda.perche(durante))
        #expect(inCorso.righe.map(\.chiave) == ["gol"])
        let finita = try giocatore(motivi + #", "stato_partita": "fatto", "fv_preso": 7"#)
        #expect(LetturaScheda.perche(finita) == nil)
        let vecchio = try giocatore()
        #expect(LetturaScheda.perche(vecchio) == nil, "server vecchio: niente riquadro")
    }

    @Test("Questa partita: al massimo due motivi utili, senza titolarità, partita e percentuali (come `motiviUtili`)")
    func motiviPartita() throws {
        let g = try giocatore(#", "motivi": ["titolare", "rigorista", "partita favorevole in casa", "segna il 40%", "calcia le punizioni"]"#)
        #expect(LetturaScheda.motiviPartita(g) == ["rigorista"], "prima i due utili, poi via quelli con la percentuale")
        let senza = try giocatore()
        #expect(LetturaScheda.motiviPartita(senza).isEmpty)
    }

    @Test("«Questa partita» solo prima della partita e per chi può giocare")
    func conQuestaPartita() throws {
        let gioca = try giocatore(#", "p_voto": 0.9"#)
        let infortunato = try giocatore(#", "stato": "infortunato""#)
        let inCorso = try giocatore(#", "stato_partita": "in_corso""#)
        #expect(LetturaScheda.conQuestaPartita(gioca))
        #expect(!LetturaScheda.conQuestaPartita(infortunato))
        #expect(!LetturaScheda.conQuestaPartita(inCorso))
        #expect(!LetturaScheda.conQuestaPartita(nil))
    }

    @Test("Il risultato atteso con le parole della web: «risultato atteso 2,1–1,0»")
    func risultatoAtteso() throws {
        let g = try giocatore(#", "avversario": "como", "gol_squadra": 2.08, "gol_avversario": 1"#)
        #expect(LetturaScheda.risultatoAtteso(g) == Catalogo.Mercato.golAttesi(a: "2,1", b: "1,0"))
        #expect(LetturaScheda.voceRisultatoAtteso(g, squadra: "GENOA") == "Risultato atteso: Genoa 2,1, Como 1,0")
        let unoSolo = try giocatore(#", "gol_squadra": 1.8"#)
        #expect(LetturaScheda.risultatoAtteso(unoSolo) == nil, "con un numero solo non si mostra")
    }

    // MARK: perché è titolare

    @Test("Perché è titolare: la riga del server; senza, la frase degli incerti con la riserva; altrimenti niente")
    func percheTitolare() throws {
        let m: OpzioneModulo = try Decodifica.decodifica(Data(#"""
        {"modulo": "4-3-3", "punteggio_atteso": 70, "titolari": [1, 2, 4], "panchina": [3],
         "perche_scelta": [{"titolare": 1, "altro": 3, "testo": "Preferito a Vasquez: con lui la formazione fa più punti attesi (64,1 contro 63,9)."},
                           {"titolare": 2, "altro": null, "testo": "  "}],
         "incerti": [{"titolare": 2, "riserva": 3}, {"titolare": 4, "riserva": null}]}
        """#.utf8))
        let schede: [String: Giocatore] = try [
            "1": giocatore(id: 1, nome: "Rossi"), "2": giocatore(id: 2, nome: "Bianchi", #", "p_voto": 0.33"#),
            "3": giocatore(id: 3, nome: "Vasquez", #", "p_voto": 0.95"#), "4": giocatore(id: 4, nome: "Neri", #", "p_voto": 0.4"#),
        ]
        #expect(PercheTitolare.testo(m, id: 1, schede: schede)
                == "Preferito a Vasquez: con lui la formazione fa più punti attesi (64,1 contro 63,9).")
        #expect(PercheTitolare.testo(m, id: 2, schede: schede) == Catalogo.Formazione.incerto(p: "33%", riserva: "Vasquez"))
        #expect(PercheTitolare.testo(m, id: 4, schede: schede) == nil, "incerto senza riserva sicura: la frase non si scrive")
        #expect(PercheTitolare.testo(m, id: 3, schede: schede) == nil)
    }
}
