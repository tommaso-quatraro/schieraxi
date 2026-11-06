import Foundation
import Testing
@testable import Schieraxi

/// La schermata Scambi dice le stesse parole della web (issue #438, sotto la #167): titoli, pulsanti, frasi di spiegazione e
/// giudizio sono quelli di `fanta/web/testi.js` (chiavi `scambi.*` e `scambio.*`). Prima l'iPhone scriveva «Analizza»,
/// «Rose dopo lo scambio», «Con chi», «Ho ricevuto un'offerta»… Una frase cambiata su un lato solo fa fallire il test.
/// Dati inventati.
@Suite("Scambi: le stesse parole della web")
struct ScambiComeLaWebTests {
    /// La chiave di `testi.js` e il testo che scrive l'app.
    static let voci: [(String, String)] = [
        // i tre modi e «Trova per me»
        ("scambio.cosa_vuoi_fare", TestiScambi.cosaVuoiFare),
        ("scambio.trova_per", TestiScambi.trovaPerMe),
        ("scambio.valuta_offerta", TestiScambi.valutaOfferta),
        ("scambio.scambi_cui_guadagnate", TestiScambi.scambiCuiGuadagnate),
        ("scambio.con_quale_squadra", TestiScambi.conQualeSquadra),
        ("scambio.tutte_squadre", TestiScambi.tutteLeSquadre),
        ("scambio.quanti_giocatori_per", TestiScambi.quantiGiocatoriPerParte),
        ("scambio.uno_contro_uno", TestiScambi.unoControUno),
        ("scambio.fino_a_2", TestiScambi.finoA2),
        ("scambio.fino_a_3", TestiScambi.finoA3),
        ("scambio.fino_a_4", TestiScambi.finoA4),
        ("scambio.per_gli_scambi", TestiScambi.perGliScambi),
        ("scambio.cerca_scambi", TestiScambi.cercaScambi),
        ("scambio.cerco_gli_scambi", TestiScambi.cercoGliScambi),
        ("scambio.nessuno_scambio_che", TestiScambi.nessunoScambio),
        ("scambio.servono_altre", TestiScambi.servonoAltreRose),
        // proposte
        ("scambio.copia_bozza_del", TestiScambi.copiaBozza),
        ("mercato.bozza_copiata", TestiScambi.bozzaCopiata),
        ("scambio.chi_accetta_piu", TestiScambi.chiAccettaPiu),
        ("scambio.squadre_che_guadagnano", TestiScambi.squadreCheGuadagnano),
        ("scambio.gli_ultimi_scambi", TestiScambi.ultimiScambi),
        // «Valuta un'offerta»
        ("scambio.incolla_messaggio_che", TestiScambi.incollaMessaggio),
        ("scambio.messaggio_dell_offerta", TestiScambi.messaggioOfferta),
        ("scambio.valuta_offerta_2", TestiScambi.valutaOffertaPulsante),
        ("scambio.incolla_prima_messaggio", TestiScambi.incollaPrima),
        ("scambio.leggo_messaggio", TestiScambi.leggoMessaggio),
        ("scambio.riga_con", TestiScambi.rigaCon),
        ("scambio.non_trovato_giocatori", TestiScambi.nonTrovatoGiocatori),
        ("scambio.scegli_mano_costruisci", TestiScambi.scegliAMano),
        ("scambio.vedi_giudizio_completo", TestiScambi.vediGiudizioCompleto),
        // «Costruisci uno scambio»
        ("scambi.analizza_titolo", TestiScambi.costruisciTitolo),
        ("scambi.analizza_spiega", TestiScambi.costruisciSpiega),
        ("scambi.con", TestiScambi.scambioCon),
        ("scambi.dai", TestiScambi.dai),
        ("scambi.ricevi", TestiScambi.ricevi),
        ("scambi.conguaglio", TestiScambi.conguaglio),
        ("scambi.conguaglio_aiuto", TestiScambi.conguaglioAiuto),
        ("scambi.ricevo_crediti", TestiScambi.ricevoCrediti),
        ("scambi.pago_crediti", TestiScambi.pagoCrediti),
        ("scambi.crediti_quanti", TestiScambi.creditiQuanti),
        ("scambi.conguaglio_numero", TestiScambi.conguaglioNumero),
        ("scambi.analizza", TestiScambi.valutaScambio),
        ("scambi.calcolo", TestiScambi.calcolo),
        // il giudizio
        ("scambi.chi_non_valido", TestiScambi.cosiNonSiPuoFare),
        ("scambi.rose_dopo", TestiScambi.roseDopo),
        ("scambi.panchina", TestiScambi.panchina),
        ("scambi.in_stagione", TestiScambi.inStagione),
        ("scambi.tu", TestiScambi.tu),
        ("scambi.crediti_titolo", TestiScambi.crediti),
        ("scambio.impatto_sulla_tua", TestiScambi.impatto),
        ("scambio.conta_anche_resto", TestiScambi.contaAncheResto),
    ]

    /// Il testo italiano della web con ogni segnaposto `{nome}` sostituito.
    private func web(_ chiave: String, _ valori: [String: String] = [:]) throws -> String {
        var testo = try TestiWeb().italiano(chiave)
        for (nome, valore) in valori { testo = testo.replacingOccurrences(of: "{\(nome)}", with: valore) }
        return testo
    }

    @Test("Ogni testo dell'app è quello di testi.js, parola per parola", arguments: ScambiComeLaWebTests.voci)
    func ugualeAllaWeb(chiave: String, app: String) throws {
        let testo = try TestiWeb().italiano(chiave)
        #expect(app == testo, "chiave \(chiave)")
    }

    // MARK: frasi con un numero o un nome

    @Test("«2 su 4» per parte, «Al massimo 4 giocatori per parte», «2 contro 1»")
    func numeriPerParte() throws {
        let scelti = try web("scambi.scelti", ["n": "2", "max": "4"])
        #expect(TestiScambi.scelti(2, massimo: 4) == scelti)
        let massimo = try web("scambi.massimo", ["max": "4"])
        #expect(TestiScambi.alMassimo(4) == massimo)
        let formato = try web("scambi.formato", ["n": "2", "m": "1"])
        #expect(TestiScambi.formato(2, 1) == formato)
    }

    @Test("«con Squadra» e, se non è 1 contro 1, anche il formato come la web")
    func conSquadra() throws {
        let con = try web("scambio.con")
        let formato = try web("scambi.formato", ["n": "2", "m": "1"])
        #expect(TestiScambi.conSquadra("Gli Amici", dai: 1, ricevi: 1) == "\(con) Gli Amici")
        #expect(TestiScambi.conSquadra("Gli Amici", dai: 2, ricevi: 1) == "\(con) Gli Amici · \(formato)")
        let unoTre = try web("scambi.formato", ["n": "1", "m": "3"])
        #expect(TestiScambi.conSquadra("Gli Amici", dai: 1, ricevi: 3) == "\(con) Gli Amici · \(unoTre)")
    }

    @Test("Formazione migliore: «prossima giornata» con una sola, «prossime N giornate» con più")
    func formazioneMigliore() throws {
        let una = try web("scambi.formazione_migliore_una")
        #expect(TestiScambi.formazioneMigliore(giornate: 1) == una)
        let tre = try web("scambi.formazione_migliore", ["n": "3"])
        #expect(TestiScambi.formazioneMigliore(giornate: 3) == tre)
        let due = try web("scambi.formazione_migliore", ["n": "2"])
        #expect(TestiScambi.formazioneMigliore(giornate: 2) == due)
    }

    @Test("Senza il numero delle giornate (server vecchio) resta la parte comune, mai «prossime 0 giornate»")
    func formazioneMiglioreSenzaNumero() throws {
        let una = try web("scambi.formazione_migliore_una")
        #expect(una.hasPrefix(TestiScambi.formazioneMigliore(giornate: 0)))
        #expect(TestiScambi.formazioneMigliore(giornate: 0) == "Formazione migliore")
        #expect(!TestiScambi.formazioneMigliore(giornate: 0).contains("0"))
    }

    @Test("In totale: «prossima giornata» con una sola, «prossime N giornate» con più")
    func inTotale() throws {
        let una = try web("scambio.in_totale.one")
        #expect(TestiScambi.inTotale(giornate: 1) == una)
        let quattro = try web("scambio.in_totale.other", ["n": "4"])
        #expect(TestiScambi.inTotale(giornate: 4) == quattro)
    }

    @Test("Chi accetta più volentieri: «1 scambio», «3 scambi», «migliora i portieri di +2,1%», «Archivio (5)»")
    func propenseEArchivio() throws {
        let uno = try web("scambio.n_scambi.one", ["n": "1"])
        #expect(TestiScambi.nScambi(1) == uno)
        let tre = try web("scambio.n_scambi.other", ["n": "3"])
        #expect(TestiScambi.nScambi(3) == tre)
        let migliora = try web("scambio.migliora", ["reparto": "portieri", "p": "+2,1"])
        #expect(TestiScambi.migliora(reparto: "portieri", p: "+2,1") == migliora)
        let archivio = try web("scambio.archivio", ["n": "5"])
        #expect(TestiScambi.archivio(5) == archivio)
    }

    @Test("Più giocatori con lo stesso cognome: i nomi separati da «; » come la web")
    func ambigui() throws {
        let attesa = try web("scambio.ambigui", ["nomi": "Rossi A.; Rossi B."])
        #expect(TestiScambi.ambigui(["Rossi A.", "Rossi B."]) == attesa)
    }

    // MARK: i modi della schermata

    @Test("I tre modi hanno i nomi dei pulsanti della web, nello stesso ordine")
    func modi() throws {
        let attesi = [try web("scambio.trova_per"), try web("scambio.costruisci"), try web("scambio.valuta_offerta")]
        #expect(ModoScambi.allCases.map(\.rawValue) == attesi)
    }

    // MARK: la bozza del messaggio

    private func scambio(mio: Double, loro: Double) throws -> PropostaScambio {
        let corpo = """
        {"altra": "Loro", "guadagno_mio": \(mio), "guadagno_loro": \(loro),
         "do": [{"id": 1, "nome": "Aldo", "ruolo": "C", "squadra": "inter", "quotazione": 10},
                {"id": 2, "nome": "Bruno", "ruolo": "D", "squadra": "milan", "quotazione": 8}],
         "ricevo": [{"id": 3, "nome": "Carlo", "ruolo": "A", "squadra": "roma", "quotazione": 12}]}
        """
        return try Decodifica.decodifica(Data(corpo.utf8))
    }

    @Test("La bozza del messaggio ha le parole della web: «più o meno uguale» se i conti sono vicini")
    func bozzaUguale() throws {
        let e = try web("scambio.bozza_e")
        let quanto = try web("scambio.bozza_uguale")
        let attesa = try web("scambio.bozza", ["do": "Aldo\(e)Bruno", "ricevo": "Carlo", "quanto": quanto])
        let proposta = try scambio(mio: 1.0, loro: 0.5)
        #expect(ScambiLogica.bozza(proposta) == attesa)
    }

    @Test("La bozza del messaggio ha le parole della web: i punti attesi di tutti e due se i conti sono lontani")
    func bozzaConIPunti() throws {
        let e = try web("scambio.bozza_e")
        let quanto = try web("scambio.bozza_punti", ["loro": Formato.conSegno(0.1), "mio": Formato.conSegno(2.4)])
        let attesa = try web("scambio.bozza", ["do": "Aldo\(e)Bruno", "ricevo": "Carlo", "quanto": quanto])
        let proposta = try scambio(mio: 2.4, loro: 0.1)
        #expect(ScambiLogica.bozza(proposta) == attesa)
    }

    // MARK: il conguaglio: «Ricevo» e «Pago»

    @MainActor
    private func analisi() -> AnalizzaScambioViewModel {
        let v = AnalizzaScambioViewModel(server: ServerDiProva { _, _, _ in Data("{}".utf8) })
        v.altra = "Loro"
        v.doIds = [1]
        v.ricevoIds = [2]
        return v
    }

    @Test("«Ricevo» manda i crediti positivi, «Pago» negativi: come i due pulsanti della web")
    @MainActor
    func versoDelConguaglio() {
        let v = analisi()
        v.conguaglio = "12"
        #expect(v.verso == .ricevo, "all'inizio «Ricevo», come sulla web")
        #expect(v.creditiConguaglio == 12)
        #expect(v.indirizzoAnalisi.hasSuffix("&completo=true&conguaglio=12"))
        v.verso = .pago
        #expect(v.creditiConguaglio == -12)
        #expect(v.indirizzoAnalisi.hasSuffix("&completo=true&conguaglio=-12"))
        #expect(v.conguaglioValido)
    }

    @Test("Senza crediti, o con zero, nessun conguaglio: né con «Ricevo» né con «Pago»")
    @MainActor
    func nessunConguaglio() {
        let v = analisi()
        for verso in VersoConguaglio.allCases {
            v.verso = verso
            for vuoto in ["", "0", "  "] {
                v.conguaglio = vuoto
                #expect(v.creditiConguaglio == 0, "\(vuoto) con \(verso)")
                #expect(!v.indirizzoAnalisi.contains("conguaglio"))
            }
        }
    }

    @Test("Un numero troppo grande non si manda, qualunque sia il verso")
    @MainActor
    func troppiCrediti() {
        let v = analisi()
        for verso in VersoConguaglio.allCases {
            v.verso = verso
            for cattivo in ["100001", "1000000", "99999999999999999999", "abc", "1,5"] {
                v.conguaglio = cattivo
                #expect(!v.conguaglioValido, "\(cattivo) con \(verso)")
                #expect(!v.puoAnalizzare)
            }
        }
        v.conguaglio = "100000"
        #expect(v.puoAnalizzare)
    }

    @Test("I due pulsanti del conguaglio si chiamano «Ricevo» e «Pago»")
    func nomiDelVerso() throws {
        let nomi = [try web("scambi.ricevo_crediti"), try web("scambi.pago_crediti")]
        #expect(VersoConguaglio.allCases.map(\.nome) == nomi)
    }

    // MARK: i messaggi del ViewModel

    @Test("«Più di 4 giocatori per parte»: la frase della web")
    @MainActor
    func troppiGiocatori() throws {
        let v = analisi()
        v.doIds = [1, 2, 3, 4, 5]
        let frase = try web("scambi.massimo", ["max": "4"])
        #expect(v.troppi == frase)
    }

    @Test("Offerta senza testo: «Incolla prima il messaggio» come la web, e non si chiede niente al server")
    @MainActor
    func offertaSenzaTesto() async throws {
        let vm = ScambiViewModel(server: ServerDiProva.chePrecipita())
        await vm.valutaOfferta()
        let frase = try web("scambio.incolla_prima_messaggio")
        #expect(vm.erroreOfferta == frase)
    }
}
