import Foundation
import Testing
@testable import Schieraxi

/// La giornata in corso e finita ai bordi, come la web dopo la #899 (#895, parte iPhone di #900, riga 98 di
/// `docs/COERENZA-WEB-IPHONE.md`): numeri, stati e frasi li decide il server, l'iPhone li mostra.
/// 1. il voto d'ufficio della partita rinviata (etichetta `voto_ufficio`) si mostra come un voto preso, con la sua parola;
/// 2. un titolare «Senza voto» ha nel disco la lineetta, non il suo atteso;
/// 3. la riga sotto i punti è `in_corso.situazione` del server (testa della Formazione e widget);
/// 4. a giornata finita il riquadro del rinvio sta sotto i punti, con il titolo della giornata, la partita e la nota;
/// 5. l'andamento della scheda è `andamento` di `/api/giocatore`;
/// 6. `voti_in_arrivo` e, a giornata in corso, «atteso» sotto il numero di chi deve ancora giocare.
/// Con un server di prima (senza i campi nuovi) resta quello di sempre. Dati inventati.
@Suite("Giornata in corso e finita ai bordi come la web (#900)")
struct BordiGiornataComeLaWebTests {
    /// Un giocatore della Formazione (inventato) con questa probabilità di giocare e questo pezzo di JSON in più.
    private func giocatore(_ altro: String, pVoto: Double = 0.9) throws -> Giocatore {
        let json = #"{"id": 7, "nome": "Mario Prova", "ruolo": "D", "fv_atteso": 6.5, "p_voto": \#(pVoto), \#(altro)}"#
        return try Decodifica.decodifica(Data(json.utf8))
    }

    /// Lo stesso giocatore a giornata in corso, con lo stato di `in_corso.giocatori` di Oggi (`Giocatore.dalVivo`, come la
    /// Formazione). `altro`: i campi del giocatore di Oggi (`stato`, `fantavoto`, `etichetta`).
    private func dalVivo(_ altro: String) throws -> Giocatore {
        let json = #"{"id": 7, "nome": "Mario Prova", "ruolo": "D", "titolare": true, "a_punteggio": true, \#(altro)}"#
        let inCorso: GiocatoreInCorso = try Decodifica.decodifica(Data(json.utf8))
        return try giocatore(#""squadra": "verona""#).dalVivo(inCorso)
    }

    private static let votoUfficio = #""stato": "rinviata", "fantavoto": 6, "etichetta": {"codice": "voto_ufficio", "testo": "Voto d'ufficio", "tono": "positivo"}"#

    // MARK: 1. voto d'ufficio

    @Test("Voto d'ufficio sul campo: nel disco il 6 (pieno), sotto «Voto d'ufficio», VoiceOver dice tutte e due le cose")
    func votoUfficioPedina() throws {
        let c = LetturaPedina.contenuto(try dalVivo(Self.votoUfficio))
        #expect(c.valore == 6)
        #expect(!c.attesa, "il voto d'ufficio è un voto preso: il disco è pieno")
        #expect(c.pezzi == [LetturaPedina.Pezzo(testo: "Voto d'ufficio", tono: .parola)], "niente «Rinviata» né «gioca 90%»")
        #expect(c.voce == "Mario Prova, fantavoto 6,0, Voto d'ufficio")
    }

    @Test("Voto d'ufficio nella riga e nella scheda: il numero con «fantavoto», la parola del server accanto")
    func votoUfficioRigaEScheda() throws {
        let g = try dalVivo(Self.votoUfficio)
        #expect(RigaGiocatore.numero(g) == "6,0")
        #expect(RigaGiocatore.sottoNumero(g) == Catalogo.Mercato.fantavoto)
        #expect(g.etichette.map(\.testo) == ["Voto d'ufficio"])
        #expect(RigaGiocatore.voce(g).contains("fantavoto 6,0"))
        #expect(LetturaScheda.cifre(g) == .cifre(.preso(6), accanto: .stato("Voto d'ufficio")))
    }

    @Test("Le parole del server si mostrano come sono (anche in inglese)")
    func votoUfficioInInglese() throws {
        let inglese = Self.votoUfficio.replacingOccurrences(of: "Voto d'ufficio", with: "Default grade")
        #expect(LetturaPedina.contenuto(try dalVivo(inglese)).pezzi.map(\.testo) == ["Default grade"])
    }

    @Test("Server di prima (etichetta «Rinviata»): resta l'atteso con «Rinviata», come oggi")
    func votoUfficioServerDiPrima() throws {
        let c = LetturaPedina.contenuto(try dalVivo(
            #""stato": "rinviata", "fantavoto": 6, "etichetta": {"codice": "rinviata", "testo": "Rinviata", "tono": "attenzione"}"#))
        #expect(c.valore == 6.5)
        #expect(c.pezzi.map(\.testo) == ["Rinviata"])
    }

    // MARK: 2. senza voto

    @Test("«Senza voto»: nel disco la lineetta, non l'atteso; VoiceOver non dice l'atteso", arguments: [
        #""stato": "senza_voto", "etichetta": {"codice": "senza_voto", "testo": "Senza voto", "tono": "attenzione"}"#,
        #""stato": "senza_voto""#,
    ])
    func senzaVoto(campi: String) throws {
        let c = LetturaPedina.contenuto(try dalVivo(campi))
        #expect(c.valore == nil, "il disco scrive «–»: l'atteso non conta più")
        #expect(c.attesa)
        #expect(c.pezzi == [LetturaPedina.Pezzo(testo: "Senza voto", tono: .parola)])
        #expect(c.voce == "Mario Prova, Senza voto")
    }

    @Test("Chi deve ancora giocare o ha il voto resta come prima")
    func altriStatiComePrima() throws {
        #expect(LetturaPedina.contenuto(try dalVivo(#""stato": "da_giocare""#)).valore == 6.5)
        #expect(LetturaPedina.contenuto(try dalVivo(#""stato": "fatto", "fantavoto": 7.5"#)).valore == 7.5)
    }

    // MARK: 3. la riga sotto i punti

    /// Oggi a giornata in corso con questa `situazione` (JSON: una stringa, `null`, un numero…) e `ancora` da giocare.
    static func oggiInCorso(situazione: String?, ancora: Int = 0) throws -> Oggi {
        let campo = situazione.map { #", "situazione": \#($0), "situazione_frase": {"chiave": "in_corso.recupero", "param": {"n": 1}}"# } ?? ""
        return try TestaFormazioneTests.oggi(#"""
        {"giornata": 11, "giornata_lega": 8, "iniziata": true, "fase": "in_corso", "scadenza": "2026-10-31 09:00",
         "formazione": {"modulo": "3-4-3", "punteggio_atteso": 73.7},
         "in_corso": {"giornata": 11, "giornata_lega": 8, "punti_fatti": 61.5, "punti_previsti": 66, "ancora_da_giocare": \#(ancora)\#(campo)}}
        """#)
    }

    static let recupero = "Hanno giocato tutti tranne Bapepe, che aspetta il recupero."

    @Test("Sotto i punti la frase del server, anche a zero da giocare", arguments: [
        BordiGiornataComeLaWebTests.recupero, "I voti dei tuoi giocatori sono tutti usciti.", "I tuoi giocatori aspettano tutti il recupero.",
    ])
    func situazioneNellaTesta(frase: String) throws {
        let o = try Self.oggiInCorso(situazione: "\"\(frase)\"")
        let t = TestaFormazione.per(oggi: o, formazione: try TestaFormazioneTests.formazione(#", "iniziata": true"#),
                                    adesso: try TestaFormazioneTests.adesso())
        #expect(t.sotto == frase, "prima: «Hanno giocato tutti: mancano solo i voti ufficiali.» a ogni zero")
    }

    @Test("Server di prima o frase vuota o strana: le parole di sempre", arguments: [nil, "\"  \"", "3", "null"])
    func situazioneAssente(campo: String?) throws {
        let formazione = try TestaFormazioneTests.formazione(#", "iniziata": true"#)
        let zero = TestaFormazione.per(oggi: try Self.oggiInCorso(situazione: campo), formazione: formazione,
                                       adesso: try TestaFormazioneTests.adesso())
        #expect(zero.sotto == Catalogo.Oggi.tuttiGiocato)
        let tre = TestaFormazione.per(oggi: try Self.oggiInCorso(situazione: campo, ancora: 3), formazione: formazione,
                                      adesso: try TestaFormazioneTests.adesso())
        #expect(tre.sotto == Catalogo.Oggi.ancoraDaGiocare(3))
    }

    @Test("Il widget scrive la stessa frase dell'app, da `/api/oggi` e da `/api/widget`, anche dopo la copia salvata")
    func situazioneNelWidget() throws {
        let r = RiassuntoOggi(oggi: try Self.oggiInCorso(situazione: "\"\(Self.recupero)\""))
        #expect(r.ancoraDaGiocareTesto == Self.recupero)
        #expect(r.descrizioneFase?.hasSuffix(Self.recupero) == true, "VoiceOver dice la stessa frase, con il suo punto")
        let salvato = try JSONDecoder().decode(RiassuntoOggi.self, from: JSONEncoder().encode(r))
        #expect(salvato.ancoraDaGiocareTesto == Self.recupero)
        let corpo = #"""
        {"giornata": 11, "giornata_lega": 8, "fase": "in_corso",
         "in_corso": {"giornata": 11, "punti_fatti": 61.5, "ancora_da_giocare": 0, "situazione": "\#(Self.recupero)"}}
        """#
        let w = try #require(RiassuntoWidget.leggi(Data(corpo.utf8)))
        #expect(w.comeRiassuntoOggi()?.ancoraDaGiocareTesto == Self.recupero)
    }

    @Test("Demo: la frase del server va d'accordo con chi deve ancora giocare; più avanti (galleria dei widget) la frase lunga con tre nomi")
    func fraseDellaDemo() throws {
        let blocco = LegaDemo.bloccoInCorso(adesso: Date(timeIntervalSinceReferenceDate: 815_000_000))
        let daGiocare = LegaDemo.righeInCorso.filter { $0.aPunteggio && ["in_corso", "da_giocare"].contains($0.stato) }.count
        #expect(blocco["ancora_da_giocare"] as? Int == daGiocare)
        #expect(blocco["situazione"] as? String == Catalogo.Oggi.ancoraDaGiocare(daGiocare), "la stessa frase del server per quel numero")
        let w = try #require(RiassuntoWidget.leggi(LegaDemo.widget(adesso: Date(timeIntervalSinceReferenceDate: 815_000_000), fase: .inCorso)))
        #expect(w.comeRiassuntoOggi()?.ancoraDaGiocareTesto == LegaDemo.situazioneInCorso, "app e widget della demo dicono la stessa frase")
        let lunga = LegaDemo.situazioneRecupero
        for id in [106, 114, 115] { #expect(lunga.contains(LegaDemo.calciatore(id).nome)) }
        #expect(lunga.count > 120, "la frase più lunga, per vedere che nel widget medio non si taglia")
    }

    @Test("Widget con un server di prima: le parole di sempre")
    func situazioneNelWidgetServerDiPrima() throws {
        #expect(RiassuntoOggi(oggi: try Self.oggiInCorso(situazione: nil)).ancoraDaGiocareTesto == Catalogo.Oggi.tuttiGiocato)
        #expect(RiassuntoOggi(oggi: try Self.oggiInCorso(situazione: nil, ancora: 2)).ancoraDaGiocareTesto == Catalogo.Oggi.ancoraDaGiocare(2))
    }

    // MARK: 4. il rinvio della giornata finita

    /// Oggi a giornata finita (11ª di Serie A, 8ª della lega) con questi `recuperi` e questo `rinvio` nel riepilogo (JSON).
    static func oggiFinita(recuperi: String, rinvio: String) throws -> Oggi {
        try TestaFormazioneTests.oggi(#"""
        {"giornata": 12, "giornata_lega": 9, "fase": "finita",
         "riepilogo": {"giornata": 11, "giornata_lega": 8, "formazione_di": "tua", "nel_diario": false, "punti_fatti": 61, "punti_attesi": 66.1,
                       "recuperi": \#(recuperi), "rinvio": \#(rinvio)},
         "prossima": {"giornata": 12, "giornata_lega": 9, "scadenza": "2026-11-06 14:50", "con_probabili": false}}
        """#)
    }

    static let partita = #"{"casa": "atalanta", "trasferta": "parma", "data": "2026-11-25 20:45"}"#
    static let altra = #"{"casa": "udinese", "trasferta": "milan", "data": null}"#

    static func rinvio(partite: [String], miei: String = #"[{"id": 1, "nome": "Ruben Tescari", "ruolo": "C", "squadra": "atalanta"}]"#) -> String {
        #"""
        {"stagione": "2026-27", "giornata": 11, "giornata_lega": 8, "modo": "aspetta", "predefinito": "aspetta", "eccezione": false,
         "modi": ["aspetta", "senza_voto", "voto_ufficio"], "voto_ufficio": 6, "partite": [\#(partite.joined(separator: ", "))], "miei": \#(miei)}
        """#
    }

    /// La testa per la formazione della prossima (giornata 9 della lega) o, con `formazione` falso, senza (campionato finito).
    private func testa(_ o: Oggi, formazione: Bool = true) throws -> TestaFormazione {
        var f: Formazione?
        if formazione { f = try TestaFormazioneTests.formazione(giornata: 12, lega: 9) }
        return TestaFormazione.per(oggi: o, formazione: f, adesso: try TestaFormazioneTests.adesso())
    }

    @Test("Il riquadro sotto i punti: «Giornata 8 · 11ª di Serie A: partita rinviata», la partita, la nota, i miei giocatori e il menu")
    func rinvioInTesta() throws {
        let t = try testa(try Self.oggiFinita(recuperi: "[\(Self.partita)]", rinvio: Self.rinvio(partite: [Self.partita])))
        let r = try #require(t.rinvio, "prima il menu stava in fondo, sotto la panchina della giornata dopo, senza titolo")
        #expect(r.titolo == "Giornata 8 · 11ª di Serie A: partita rinviata")
        #expect(r.titolo == Catalogo.Oggi.rinvioTitoloGiornata1(g: "Giornata 8 · 11ª di Serie A"))
        #expect(r.nota == Catalogo.Oggi.recuperoPunti)
        #expect(r.scelta.partite.map(\.id) == ["atalanta-parma"])
        #expect(TestiRinvio.miei(r.scelta) == Catalogo.Oggi.rinvioMiei(nomi: "Ruben Tescari"))
        #expect(t.recuperi == nil, "la partita si dice una volta sola: nel riquadro")
        #expect(t.prossima == "Giornata 9 · 12ª di Serie A")
    }

    @Test("Due partite: «…: partite rinviate»; la lega che non aspetta il recupero: niente nota")
    func rinvioDuePartiteSenzaNota() throws {
        let due = try testa(try Self.oggiFinita(recuperi: "[\(Self.partita), \(Self.altra)]",
                                                rinvio: Self.rinvio(partite: [Self.partita, Self.altra])))
        #expect(due.rinvio?.titolo == Catalogo.Oggi.rinvioTitoloGiornataN(g: "Giornata 8 · 11ª di Serie A"))
        let senzaRecuperi = try testa(try Self.oggiFinita(recuperi: "[]", rinvio: Self.rinvio(partite: [Self.partita])))
        #expect(senzaRecuperi.rinvio?.nota == nil)
        #expect(senzaRecuperi.recuperi == nil)
    }

    @Test("Server di prima (rinvio senza partite): il riquadro con il titolo e la riga dei recuperi di sempre")
    func rinvioServerDiPrima() throws {
        let t = try testa(try Self.oggiFinita(recuperi: "[\(Self.partita)]", rinvio: Self.rinvio(partite: [], miei: "[]")))
        #expect(t.recuperi == "Manca il recupero di ATA vs PAR: i punti possono ancora cambiare.")
        #expect(t.rinvio?.titolo == "Giornata 8 · 11ª di Serie A: partita rinviata")
        #expect(t.rinvio?.nota == nil)
        let senzaRinvio = try testa(try Self.oggiFinita(recuperi: "[\(Self.partita)]", rinvio: "null"))
        #expect(senzaRinvio.rinvio == nil)
        #expect(senzaRinvio.recuperi == "Manca il recupero di ATA vs PAR: i punti possono ancora cambiare.")
    }

    @Test("A campionato finito lo stesso riquadro sotto il riepilogo dell'ultima giornata")
    func rinvioACampionatoFinito() throws {
        let json = #"""
        {"giornata": null, "fase": "finita", "prossima": null,
         "campionato_finito": {"testo": "Il campionato è finito: previsioni e consigli ripartono con il calendario della prossima stagione."},
         "riepilogo": {"giornata": 11, "giornata_lega": 8, "punti_fatti": 61, "recuperi": [\#(Self.partita)], "rinvio": \#(Self.rinvio(partite: [Self.partita]))}}
        """#
        let t = try testa(try TestaFormazioneTests.oggi(json), formazione: false)
        #expect(t.campionatoFinito != nil)
        #expect(t.rinvio?.titolo == "Giornata 8 · 11ª di Serie A: partita rinviata")
    }

    // MARK: 5. andamento

    /// La scheda del giocatore con 6 fantavoti uguali (la vecchia regola dell'app direbbe «stabile») e questo campo `andamento`.
    static func scheda(andamento: String?) throws -> SchedaGiocatore {
        let voti = (5...10).map { #"{"giornata": \#($0), "voto": 6, "fv": 6.5}"# }.joined(separator: ", ")
        let campo = andamento.map { #", "andamento": \#($0)"# } ?? ""
        let json = #"{"calciatore": {"id": 7, "nome": "Mario Prova", "ruolo": "D"}, "voti": [\#(voti)]\#(campo)}"#
        return try Decodifica.decodifica(Data(json.utf8))
    }

    /// Il codice del server, l'andamento, la freccia e la parola del catalogo.
    static let andamenti: [(String, Forma.Andamento, String, String)] = [
        ("in_calo", .calo, "↘", Catalogo.Mercato.inCalo),
        ("in_crescita", .crescita, "↗", Catalogo.Mercato.inCrescita),
        ("stabile", .stabile, "→", Catalogo.Mercato.stabile),
        ("pochi_dati", .pochiDati, "→", Catalogo.Mercato.pochiDati),
    ]

    @Test("L'andamento è quello del server, con la freccia e la parola del catalogo", arguments: BordiGiornataComeLaWebTests.andamenti)
    func andamentoDelServer(codice: String, andamento: Forma.Andamento, freccia: String, parola: String) throws {
        let s = try Self.scheda(andamento: "\"\(codice)\"")
        let f = try #require(Forma.di(s.voti ?? [], andamento: s.codiceAndamento))
        #expect(f.andamento == andamento, "l'app non lo ricalcola dai voti")
        #expect(f.andamento?.freccia == freccia)
        #expect(f.andamento?.parola == parola)
        #expect(f.ultime.map(\.giornata) == [6, 7, 8, 9, 10], "gli ultimi 5 voti in pallini restano")
    }

    @Test("Server di prima, valore sconosciuto o strano: niente andamento (come la web), la scheda si legge e i pallini restano",
          arguments: [nil, "\"in_forma\"", "3", "null"])
    func andamentoAssente(campo: String?) throws {
        let s = try Self.scheda(andamento: campo)
        let f = try #require(Forma.di(s.voti ?? [], andamento: s.codiceAndamento))
        #expect(f.andamento == nil)
        #expect(f.ultime.count == 5)
    }

    @Test("Senza presenze niente forma")
    func senzaPresenze() {
        #expect(Forma.di([], andamento: "stabile") == nil)
    }

    // MARK: 6. voti in arrivo e la colonna della panchina

    /// Oggi a giornata finita senza riepilogo, con questo campo `voti_in_arrivo` (JSON; nil = assente).
    static func oggiSenzaVoti(_ campo: String?) throws -> Oggi {
        let voti = campo.map { #""voti_in_arrivo": \#($0),"# } ?? ""
        return try TestaFormazioneTests.oggi(#"""
        {"giornata": 12, "giornata_lega": 9, "fase": "finita", "riepilogo": null, \#(voti)
         "prossima": {"giornata": 12, "giornata_lega": 9, "scadenza": "2026-11-06 14:50", "con_probabili": false}}
        """#)
    }

    static let votiInArrivo = #"""
    {"giornata": 11, "giornata_lega": 8, "testo": "I punti arrivano quando escono i voti.",
     "frase": {"chiave": "riepilogo.voti_in_arrivo", "param": {}}}
    """#

    @Test("Giornata finita senza voti: «Giornata 8 · 11ª di Serie A: finita», la frase del server, poi la prossima")
    func votiInArrivoInTesta() throws {
        let t = try testa(try Self.oggiSenzaVoti(Self.votiInArrivo))
        #expect(t.giornata == "Giornata 8 · 11ª di Serie A: finita")
        #expect(t.giornata == Catalogo.Oggi.giornataFinita(g: "Giornata 8 · 11ª di Serie A"))
        #expect(t.sotto == "I punti arrivano quando escono i voti.")
        #expect(t.punti == nil && t.comeAndata == nil, "niente totale finché non escono i voti")
        #expect(t.prossima == "Giornata 9 · 12ª di Serie A")
        #expect(t.chiude == "Si chiude ven 6 14:50")
    }

    @Test("Senza `voti_in_arrivo` (server di prima o senza formazione), con un testo vuoto o una forma strana: la testa di sempre",
          arguments: [nil, #"{"giornata": 11, "giornata_lega": 8, "testo": " "}"#, #""I punti arrivano quando escono i voti.""#, "null"])
    func votiInArrivoAssente(campo: String?) throws {
        let t = try testa(try Self.oggiSenzaVoti(campo))
        #expect(t.giornata == "Giornata 9 · 12ª di Serie A")
        #expect(t.sotto == nil && t.prossima == nil)
        #expect(t.chiude == "Si chiude ven 6 14:50")
    }

    @Test("A giornata in corso sotto l'atteso di chi deve ancora giocare «atteso», dove non c'è «gioca N%»")
    func attesoInPanchina() throws {
        let sicuro = try dalVivo(#""stato": "da_giocare""#)
        #expect(RigaGiocatore.numero(sicuro) == "6,5")
        #expect(RigaGiocatore.sottoNumero(sicuro, dalVivo: true) == Catalogo.Formazione.attesoBreve)
        let infortunato = try giocatore(#""stato": "infortunato", "stato_partita": "da_giocare""#, pVoto: 0)
        #expect(RigaGiocatore.sottoNumero(infortunato, dalVivo: true) == Catalogo.Formazione.attesoBreve, "lo stato lo dice la parola")
    }

    @Test("A giornata in corso restano «gioca N%» sotto l'80%, «fantavoto» accanto al voto e niente senza voto; prima della scadenza come sempre")
    func restoDellaColonna() throws {
        let incerto = try giocatore(#""stato_partita": "da_giocare""#, pVoto: 0.6)
        #expect(RigaGiocatore.sottoNumero(incerto, dalVivo: true) == "gioca 60%")
        #expect(RigaGiocatore.sottoNumero(try dalVivo(#""stato": "fatto", "fantavoto": 7.5"#), dalVivo: true) == Catalogo.Mercato.fantavoto)
        #expect(RigaGiocatore.sottoNumero(try dalVivo(#""stato": "senza_voto""#), dalVivo: true) == nil)
        #expect(RigaGiocatore.sottoNumero(try giocatore(#""titolarita": "titolare""#)) == "gioca 90%")
    }
}
