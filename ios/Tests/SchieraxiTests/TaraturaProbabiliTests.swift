import Foundation
import Testing
@testable import Schieraxi

/// Stato dei dati: la riga della taratura di «gioca N%» con le probabili (#379, PR C del piano 2026-11-06-gioca-probabili-server),
/// con le parole della web (`rigaTaratura` di `fanta/web/app.js`, testi `sd.tar_*` del catalogo comune; `sd.f_taratura` si
/// confronta ancora con `fanta/web/testi.js`).
/// La fixture `stato-dati-taratura.json` è la risposta vera del server (`taratura_probabili.riepilogo`): la versione 1 attiva dal
/// 15/1, con la prova sulle ultime 4 giornate e un cambio rimandato perché la prima partita è vicina. La controlla
/// `tests/test_stato_dati_taratura_web.py`, che prova la web sugli stessi numeri.
/// Dal #821 la prova si dice in parole semplici: l'errore medio delle percentuali in punti (due decimali, calcolato dal server)
/// contro quello senza questa taratura; niente «versione N» né «Brier» per l'utente.
@Suite("Taratura di «gioca N%» in Stato dei dati")
struct TaraturaProbabiliTests {
    private static let titolo = "Taratura con le probabili"

    /// Il campo `calibrazione.taratura` scritto a mano (per i casi che la fixture non ha), letto come fa l'app.
    private func taratura(_ json: String) throws -> StatoDati.Taratura? {
        let risposta = "{\"stagione\":\"2026-27\",\"calibrazione\":{\"giornate\":3,\"gruppi\":[],\"taratura\":\(json)}}"
        let s: StatoDati = try Decodifica.decodifica(Data(risposta.utf8))
        return s.calibrazione?.taratura
    }

    private func frase(_ json: String) throws -> String? {
        ParoleRegistro.taratura(try taratura(json))
    }

    /// La riga intera della web: «Taratura con le probabili: {s}» (`sd.tar_riga`).
    private func riga(_ parti: String) -> String {
        Catalogo.Sd.tarRiga(s: parti)
    }

    @Test("Si legge la risposta vera del server")
    func decodifica() throws {
        let s: StatoDati = try Fixture.decodifica("stato-dati-taratura")
        let t = try #require(s.calibrazione?.taratura)
        #expect(t.stato == "attiva")
        #expect(t.giornate == 10)
        #expect(t.minimo == 4)
        #expect(t.versione == "1")
        #expect(t.dal == "2027-01-15T10:00:00")
        #expect(t.motivo == "scadenza_vicina")
        let p = try #require(t.prova)
        #expect(p.giornate == 4)
        #expect(p.brier == 0.0912)
        #expect(p.brierPrima == 0.0968)
        #expect(p.brierMostrati == 0.0975)
        #expect(p.calibrazione == 0.0213)
        #expect(p.erroreMedio == 30.2)
        #expect(p.erroreMedioPrima == 31.11)
    }

    @Test("La frase della risposta vera: attiva, la prova e il cambio rimandato")
    func fraseDellaFixture() throws {
        let s: StatoDati = try Fixture.decodifica("stato-dati-taratura")
        #expect(ParoleRegistro.taratura(s.calibrazione?.taratura)
                == "\(Self.titolo): attiva dal 15/1 · nelle ultime 4 giornate le percentuali «gioca N%» hanno sbagliato in media di "
                + "30,20 punti, contro 31,11 senza questa taratura · cambio rimandato: la prima partita è tra meno di 24 ore")
    }

    @Test("Senza il campo, con `null` o con un valore che non si legge: la pagina si apre lo stesso, senza la riga")
    func senzaCampo() throws {
        let vecchio: StatoDati = try Fixture.decodifica("stato-dati")
        #expect(vecchio.calibrazione?.gruppi?.isEmpty == false)
        #expect(vecchio.calibrazione?.taratura == nil)
        #expect(try taratura("null") == nil)
        #expect(ParoleRegistro.taratura(nil) == nil)
        #expect(try frase("\"attiva\"") == nil)
        #expect(try frase("{\"stato\":\"sconosciuto\",\"giornate\":1,\"minimo\":4}") == nil)
        #expect(try frase("{\"stato\":3,\"giornate\":\"x\"}") == nil)
    }

    /// Giornate buone per la taratura, quante ne servono per la prima prova e la frase dopo «Taratura con le probabili: ».
    struct CasoAttesa: Sendable, CustomTestStringConvertible {
        let giornate: Int
        let minimo: Int
        let frase: String
        var testDescription: String { "\(giornate) su \(minimo)" }
    }

    static let casiInAttesa: [CasoAttesa] = [
        CasoAttesa(giornate: 2, minimo: 4, frase: "in attesa · 2 giornate su 4"),
        CasoAttesa(giornate: 1, minimo: 4, frase: "in attesa · 1 giornata su 4"),
        CasoAttesa(giornate: 0, minimo: 4, frase: "in attesa · 0 giornate su 4"),
        // riaccesa da poco, o giornate con poche righe: le giornate bastano ma il verdetto non c'è ancora (niente «6 giornate su 4»)
        CasoAttesa(giornate: 6, minimo: 4, frase: "in attesa · 6 giornate"),
        CasoAttesa(giornate: 4, minimo: 4, frase: "in attesa · 4 giornate"),
        CasoAttesa(giornate: 1, minimo: 0, frase: "in attesa · 1 giornata"),
    ]

    @Test("In attesa: quante giornate su quante, o solo quante se bastano già", arguments: TaraturaProbabiliTests.casiInAttesa)
    func inAttesa(caso: CasoAttesa) throws {
        let json = "{\"stato\":\"in_attesa\",\"giornate\":\(caso.giornate),\"minimo\":\(caso.minimo),\"versione\":null,\"dal\":null,"
            + "\"prova\":null,\"motivo\":null}"
        #expect(try frase(json) == "\(Self.titolo): \(caso.frase)")
    }

    /// La frase della prova dopo «· »: l'errore medio con la taratura e senza, come lo scrive la web.
    private static func prova(_ n: Int, _ errore: String, _ prima: String) -> String {
        (n == 1 ? "nell'ultima giornata" : "nelle ultime \(n) giornate") + " le percentuali «gioca N%» hanno sbagliato in media di "
            + "\(errore) punti, contro \(prima) senza questa taratura"
    }

    @Test("Attiva: data dalla stringa del server, numeri della prova, niente versione; «–» se mancano, mai «nan»")
    func attiva() throws {
        let base = "\"stato\":\"attiva\",\"giornate\":8,\"minimo\":4,\"versione\":3"
        let prova = "{\"giornate\":4,\"brier\":0.0912,\"brier_prima\":0.0968,\"brier_mostrati\":0.0975,\"calibrazione\":0.0213,"
            + "\"errore_medio\":30.2,\"errore_medio_prima\":31.11}"
        #expect(try frase("{\(base),\"dal\":\"2027-01-15T10:00:00\",\"prova\":\(prova),\"motivo\":null}")
                == "\(Self.titolo): attiva dal 15/1 · \(Self.prova(4, "30,20", "31,11"))")
        // il giorno è quello scritto dal server, senza fuso orario: le 23:30 del 31/12 restano il 31/12
        #expect(try frase("{\(base),\"dal\":\"2026-12-31T23:30:00\",\"prova\":null,\"motivo\":null}")
                == "\(Self.titolo): attiva dal 31/12")
        #expect(try frase("{\(base),\"dal\":null,\"prova\":null,\"motivo\":null}") == "\(Self.titolo): attiva")
        #expect(try frase("{\(base),\"dal\":\"x\",\"prova\":null}") == "\(Self.titolo): attiva")
        #expect(try frase("{\(base),\"dal\":\"2027-1-5\",\"prova\":null}") == "\(Self.titolo): attiva")
        let mancano = "{\"giornate\":1,\"brier\":null,\"brier_prima\":0.1,\"brier_mostrati\":null,\"calibrazione\":null,"
            + "\"errore_medio\":null,\"errore_medio_prima\":31.62}"
        #expect(try frase("{\(base),\"dal\":\"2027-03-02T06:00:00\",\"prova\":\(mancano)}")
                == "\(Self.titolo): attiva dal 2/3 · \(Self.prova(1, "–", "31,62"))")
        // un motivo che non è il cambio rimandato non si aggiunge alla versione attiva
        #expect(try frase("{\(base),\"motivo\":\"non_migliora\"}") == "\(Self.titolo): attiva")
        // la versione, come testo, come numero o che manca, non si scrive più (#821): resta per chi gestisce il server
        #expect(try frase("{\"stato\":\"attiva\",\"versione\":\"2\"}") == "\(Self.titolo): attiva")
        #expect(try frase("{\"stato\":\"attiva\"}") == "\(Self.titolo): attiva")
    }

    @Test("Attiva dall'8/1 e dall'11/1 con l'apostrofo, come la web (#859); «dal 18/1» e «dal 1/1» restano")
    func attivaConLApostrofo() throws {
        let base = "\"stato\":\"attiva\",\"giornate\":8,\"minimo\":4,\"versione\":3,\"prova\":null,\"motivo\":null"
        #expect(try frase("{\(base),\"dal\":\"2027-01-08T06:00:00\"}") == "\(Self.titolo): attiva dall'8/1")
        #expect(try frase("{\(base),\"dal\":\"2027-01-11T06:00:00\"}") == "\(Self.titolo): attiva dall'11/1")
        #expect(try frase("{\(base),\"dal\":\"2027-01-18T06:00:00\"}") == "\(Self.titolo): attiva dal 18/1")
        #expect(try frase("{\(base),\"dal\":\"2027-01-01T06:00:00\"}") == "\(Self.titolo): attiva dal 1/1")
    }

    @Test("Errore medio con due decimali, scritto dal server; un server vecchio che manda solo i Brier: «–»")
    func erroreMedio() throws {
        // con un decimale una versione accesa per un miglioramento dello 0,5% si leggerebbe «30,9 contro 30,9»
        let vicini = "{\"giornate\":5,\"brier\":0.09553,\"brier_prima\":0.09612,\"calibrazione\":0.03,\"errore_medio\":30.91,"
            + "\"errore_medio_prima\":31.0}"
        #expect(try frase("{\"stato\":\"attiva\",\"versione\":2,\"prova\":\(vicini)}")
                == "\(Self.titolo): attiva · \(Self.prova(5, "30,91", "31,00"))")
        let vecchio = "{\"giornate\":1,\"brier\":0.0955,\"brier_prima\":0.0961,\"calibrazione\":0.01}"
        let testo = try #require(try frase("{\"stato\":\"attiva\",\"versione\":2,\"prova\":\(vecchio)}"))
        #expect(testo == "\(Self.titolo): attiva · \(Self.prova(1, "–", "–"))")
        #expect(!testo.contains("Brier") && !testo.contains("0,09"))
    }

    /// Un codice di `motivo` del server e la sua frase (`sd.tar_m_*` della web), con 7 giornate.
    struct CasoMotivo: Sendable, CustomTestStringConvertible {
        let codice: String
        let frase: String
        var testDescription: String { codice }
    }

    static let motivi: [CasoMotivo] = [
        CasoMotivo(codice: "non_migliora", frase: "non sbaglia meno dei numeri di partenza"),
        CasoMotivo(codice: "poche_giornate", frase: "la prova passa, si accende con 8 giornate (ora 7)"),
        CasoMotivo(codice: "fuori_soglia", frase: "fuori dalle soglie di scarto o di errore medio delle percentuali"),
        CasoMotivo(codice: "incoerente", frase: "i numeri tarati non sono validi"),
        CasoMotivo(codice: "peggiorata", frase: "tornata ai numeri di partenza: sbagliava di più nelle ultime giornate"),
        CasoMotivo(codice: "scadenza_vicina", frase: "cambio rimandato: la prima partita è tra meno di 24 ore"),
        CasoMotivo(codice: "spenta_a_mano", frase: "spenta a mano"),
    ]

    @Test("Non attiva: una frase per ogni motivo del server", arguments: TaraturaProbabiliTests.motivi)
    func nonAttiva(caso: CasoMotivo) throws {
        let json = "{\"stato\":\"non_attiva\",\"giornate\":7,\"minimo\":4,\"versione\":2,\"dal\":null,\"prova\":null,"
            + "\"motivo\":\"\(caso.codice)\"}"
        #expect(try frase(json) == "\(Self.titolo): non attiva · \(caso.frase)")
    }

    @Test("Motivo sconosciuto o assente: solo «non attiva», niente codici")
    func motivoSconosciuto() throws {
        #expect(try frase("{\"stato\":\"non_attiva\",\"giornate\":7,\"motivo\":\"nuovo_motivo\"}") == "\(Self.titolo): non attiva")
        #expect(try frase("{\"stato\":\"non_attiva\",\"giornate\":7,\"motivo\":null}") == "\(Self.titolo): non attiva")
        #expect(try frase("{\"stato\":\"non_attiva\"}") == "\(Self.titolo): non attiva")
    }

    @Test("Spenta a mano")
    func spenta() throws {
        let json = "{\"stato\":\"spenta\",\"giornate\":3,\"minimo\":4,\"versione\":null,\"dal\":null,\"prova\":null,\"motivo\":\"spenta_a_mano\"}"
        #expect(try frase(json) == "\(Self.titolo): spenta a mano")
    }

    // MARK: - stesse parole della web (catalogo)

    @Test("Plurali con i modelli della web", arguments: [1, 3])
    func pluraliComeLaWeb(n: Int) throws {
        let suQuante = riga(Catalogo.Sd.tarInAttesaSu(n, m: "4"))
        #expect(try frase("{\"stato\":\"in_attesa\",\"giornate\":\(n),\"minimo\":4}") == suQuante)
        let soloQuante = riga(Catalogo.Sd.tarInAttesa(n))
        #expect(try frase("{\"stato\":\"in_attesa\",\"giornate\":\(n),\"minimo\":0}") == soloQuante)
        let prova = "{\"giornate\":\(n),\"brier\":0.0912,\"brier_prima\":0.0968,\"calibrazione\":0.0213,\"errore_medio\":30.2,"
            + "\"errore_medio_prima\":31.11}"
        let attiva = Catalogo.Sd.tarAttivaDal(d: "15/1")
        let numeri = Catalogo.Sd.tarProva(n, e: "30,20", p: "31,11")
        #expect(numeri == Self.prova(n, "30,20", "31,11"))
        let conProva = riga(attiva + " · " + numeri)
        #expect(try frase("{\"stato\":\"attiva\",\"versione\":1,\"dal\":\"2027-01-15T10:00:00\",\"prova\":\(prova)}") == conProva)
    }

    @Test("Attiva, non attiva con ogni motivo, spenta e il nome negli aggiornamenti: i testi della web")
    func statiComeLaWeb() throws {
        let web = try TestiWeb()
        let nonAttiva = Catalogo.Sd.tarNonAttiva
        let attiva = riga(Catalogo.Sd.tarAttiva)
        #expect(try frase("{\"stato\":\"attiva\",\"versione\":3}") == attiva)
        let spenta = riga(Catalogo.Sd.tarSpenta)
        #expect(try frase("{\"stato\":\"spenta\"}") == spenta)
        let senzaMotivo = riga(nonAttiva)
        #expect(try frase("{\"stato\":\"non_attiva\"}") == senzaMotivo)
        // ogni codice del server con la sua frase del catalogo (`sd.tar_m_<codice>`), con 7 giornate
        let dalCatalogo = [
            "non_migliora": Catalogo.Sd.tarMNonMigliora, "poche_giornate": Catalogo.Sd.tarMPocheGiornate(n: "7"),
            "fuori_soglia": Catalogo.Sd.tarMFuoriSoglia, "incoerente": Catalogo.Sd.tarMIncoerente,
            "peggiorata": Catalogo.Sd.tarMPeggiorata, "scadenza_vicina": Catalogo.Sd.tarMScadenzaVicina,
            "spenta_a_mano": Catalogo.Sd.tarMSpentaAMano,
        ]
        #expect(Set(dalCatalogo.keys) == Set(Self.motivi.map(\.codice)))
        for caso in Self.motivi {
            let motivo = try #require(dalCatalogo[caso.codice], "\(caso.codice)")
            #expect(motivo == caso.frase, "\(caso.codice)")
            let conMotivo = riga(nonAttiva + " · " + motivo)
            #expect(try frase("{\"stato\":\"non_attiva\",\"giornate\":7,\"motivo\":\"\(caso.codice)\"}") == conMotivo, "\(caso.codice)")
        }
        let rimandato = riga(Catalogo.Sd.tarAttiva + " · " + Catalogo.Sd.tarMScadenzaVicina)
        #expect(try frase("{\"stato\":\"attiva\",\"versione\":1,\"motivo\":\"scadenza_vicina\"}") == rimandato)
        #expect(try web.italiano("sd.f_taratura") == NomiDati.leggibile("taratura-probabili"))
    }

    // MARK: - demo (foto e anteprima)

    @Test("La demo ha la taratura attiva, con i numeri della prova tutti scritti e coerenti con il registro")
    func demo() async throws {
        let demo = FinteServer.demoFissata(adesso: Date(timeIntervalSinceReferenceDate: 815_000_000))
        let s: StatoDati = try Decodifica.decodifica(try await demo.richiesta("GET", "/api/stato-dati", corpo: nil))
        let t = try #require(s.calibrazione?.taratura)
        #expect(t.stato == "attiva")
        let testo = try #require(ParoleRegistro.taratura(t))
        #expect(testo.hasPrefix("\(Self.titolo): attiva dal "))
        #expect(testo.hasSuffix("· \(Self.prova(4, "34,55", "36,15"))"))
        #expect(!testo.contains("–") && !testo.contains("Brier") && !testo.contains("versione"))
        // prima dell'accensione si mostravano i numeri misurati dal registro delle giornate: lo stesso punteggio di Brier
        #expect(t.prova?.brierMostrati == s.registro?.brier)
    }
}
