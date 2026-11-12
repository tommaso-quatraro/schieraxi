import Foundation
import Testing
@testable import Schieraxi

/// L'ultimo giro dei testi da una fonte sola (A6, #556, parte di #167): i testi che il catalogo comune con la web ha già
/// (`fanta/testi/`, in Swift `Catalogo.…`, generati per le chiavi di `ios/testi/`) non si scrivono più a mano nei file che li
/// mostrano: lo stato «Non disponibile», «Perché questo numero», le fasi della giornata, le partite rinviate, la riga di stato
/// della scelta, Notifiche, Aspetto, la lega senza rose, i bonus delle regole, «fantavoto» nelle righe.
/// Qui si legge il sorgente (cartella `ios/` del repository): una frase copiata fra virgolette tornerebbe a cambiare su un lato
/// solo. Le frasi con un valore si controllano a pezzi: il valore si scrive «§» e nessun testo del file contiene un pezzo fisso.
@Suite("Resti dei testi: le parole vengono dal catalogo (#556)")
struct RestiDalCatalogoTests {
    /// Un file di `ios/`, i testi del catalogo che non deve scrivere a mano e le costanti che deve usare.
    struct Caso: Sendable, CustomTestStringConvertible {
        let file: String
        /// Testi senza valori: nessun testo fra virgolette del file è uguale a uno di questi.
        var testi: [String] = []
        /// Frasi con un valore («§», o 1 e 7 per i plurali): nessun testo del file contiene un loro pezzo fisso.
        var frasi: [String] = []
        /// Le costanti del catalogo che il file usa davvero.
        var usa: [String] = []
        var testDescription: String { file }
    }

    static let casi: [Caso] = [
        Caso(file: "Sources/Support/Design/Stati.swift",
             testi: [Catalogo.Dieta.nonDisponibile, Catalogo.Dieta.tornaOggi],
             usa: ["Catalogo.Dieta.nonDisponibile", "Catalogo.Dieta.tornaOggi"]),
        // la scheda del giocatore unica (#616): «Perché questo numero» sta dentro, «Apri la scheda» nel menu delle righe
        Caso(file: "Sources/Presentation/Mercato/SchedaGiocatoreView.swift",
             testi: [Catalogo.Formazione.percheTitolare, Catalogo.Formazione.ultimiVoti, Catalogo.Formazione.sostituisci,
                     Catalogo.Formazione.tuttiNumeri, Catalogo.Formazione.bloccati, Catalogo.Mercato.caricoScheda, Catalogo.Comune.carico,
                     Catalogo.Mercato.nessunaPresenzaQuesta, Catalogo.Oggi.diffidatoTipo, Catalogo.Perche.titolo],
             usa: ["Catalogo.Formazione.percheTitolare", "Catalogo.Formazione.ultimiVoti", "Catalogo.Formazione.sostituisci",
                   "Catalogo.Formazione.tuttiNumeri", "Catalogo.Formazione.bloccati", "Catalogo.Mercato.caricoScheda",
                   "Catalogo.Comune.carico", "Catalogo.Oggi.diffidatoTipo"]),
        Caso(file: "Sources/Presentation/Mercato/CifreScheda.swift",
             testi: [Catalogo.Mercato.nessunaPrevisionePer, Catalogo.Mercato.fantavotoAtteso, Catalogo.Formazione.seGioca,
                     Catalogo.Mercato.gioca, Catalogo.Mercato.fantavoto],
             frasi: [Catalogo.Formazione.voceGioca(p: "§"), Catalogo.Formazione.voceGiocaV(p: "§")],
             usa: ["Catalogo.Mercato.nessunaPrevisionePer", "Catalogo.Mercato.fantavotoAtteso", "Catalogo.Formazione.seGioca",
                   "Catalogo.Formazione.voceGioca(", "Catalogo.Formazione.voceGiocaV("]),
        Caso(file: "Sources/Presentation/Mercato/TuttiINumeri.swift",
             testi: [Catalogo.Mercato.svincolato, Catalogo.Formazione.questaPartita, Catalogo.Mercato.portaInviolata,
                     Catalogo.Mercato.golSubitiAttesi, Catalogo.Mercato.prossimePartite, Catalogo.Mercato.coloriVerdePartita,
                     Catalogo.Mercato.forma, Catalogo.Mercato.andamento, Catalogo.Mercato.pochiDati, Catalogo.Mercato.inCrescita,
                     Catalogo.Mercato.inCalo, Catalogo.Mercato.votoFantavotoPer, Catalogo.Mercato.rendeSopraSotto,
                     Catalogo.Mercato.puntiPartita, Catalogo.Mercato.rendCala, Catalogo.Mercato.rendSblocca, Catalogo.Mercato.rendLinea,
                     Catalogo.Mercato.presenze, Catalogo.Mercato.mediaVoto, Catalogo.Mercato.fantamedia, Catalogo.Mercato.gialliRossi,
                     Catalogo.Mercato.golSubiti, Catalogo.Mercato.rigoriParati, Catalogo.Mercato.statisticheAvanzate,
                     Catalogo.Mercato.golAttesiTot, Catalogo.Mercato.assistAttesiTot, Catalogo.Mercato.xg90, Catalogo.Mercato.xa90,
                     Catalogo.Mercato.tiri90, Catalogo.Mercato.rigoriCalciati, Catalogo.Mercato.passaggiChiave, Catalogo.Mercato.punizioni],
             frasi: [Catalogo.Mercato.quot(n: "§"), Catalogo.Mercato.golRig(n: "§"), Catalogo.Mercato.rendimentoRiga(a: "§", g: "§"),
                     Catalogo.Mercato.stagionePrec(a: "§", g: "§", m: "§", s: "§", xa: "§", xg: "§")],
             usa: ["Catalogo.Mercato.svincolato", "Catalogo.Mercato.quot(", "Catalogo.Formazione.questaPartita",
                   "Catalogo.Mercato.rendimentoRiga(", "Catalogo.Mercato.stagionePrec(", "Catalogo.Mercato.golRig("]),
        Caso(file: "Sources/Domain/LetturaScheda.swift",
             frasi: [Catalogo.Formazione.partitaCasa(avv: "§", quando: "§"), Catalogo.Formazione.partitaFuori(avv: "§", quando: "§"),
                     Catalogo.Mercato.golAttesi(a: "§", b: "§")],
             usa: ["Catalogo.Formazione.partitaCasa(", "Catalogo.Formazione.partitaFuori(", "Catalogo.Mercato.golAttesi(",
                   "Catalogo.Ruolo.a1", "Catalogo.Ruolo.p1"]),
        Caso(file: "Sources/Domain/ParolaStato.swift",
             testi: [Catalogo.Tit.inDubbio, Catalogo.Tit.fuori, Catalogo.Tit.stRinviata, Catalogo.Oggi.infortunato,
                     Catalogo.Oggi.squalificato],
             usa: ["Catalogo.Tit.inDubbio", "Catalogo.Tit.fuori", "Catalogo.Oggi.infortunato", "Catalogo.Oggi.squalificato"]),
        Caso(file: "Sources/Domain/PercheTitolare.swift",
             frasi: [Catalogo.Formazione.incerto(p: "§", riserva: "§")],
             usa: ["Catalogo.Formazione.incerto("]),
        Caso(file: "Sources/Domain/FantavotoAtteso.swift",
             testi: [Catalogo.Perche.titolo, Catalogo.Perche.definizione],
             frasi: [Catalogo.Perche.rispetto(n: "§"), Catalogo.Perche.nessuno(n: "§")],
             usa: ["Catalogo.Perche.titolo", "Catalogo.Perche.rispetto(", "Catalogo.Perche.nessuno("]),
        Caso(file: "Sources/Domain/FasiGiornata.swift",
             testi: [
                Catalogo.Oggi.puntiFinora, Catalogo.Oggi.aFineGiornata, Catalogo.Oggi.dallaPanchina, Catalogo.Oggi.cambiPanchina,
                Catalogo.Oggi.tuttiGiocato, Catalogo.Oggi.nessunSostituto, Catalogo.Oggi.stDaGiocare, Catalogo.Oggi.stSenzaVoto,
                Catalogo.Oggi.stAttesaVoti, Catalogo.Oggi.stInCorso, Catalogo.Oggi.stRinviata, Catalogo.Oggi.cambioFatto,
                Catalogo.Oggi.cambioProbabile, Catalogo.Oggi.giaIniziata, Catalogo.Oggi.giaIniziataTesto, Catalogo.Oggi.preparaProssima,
                Catalogo.Oggi.laTuaFormazione, Catalogo.Oggi.laConsigliata, Catalogo.Oggi.puntiFatti, Catalogo.Oggi.puntiAttesi,
                Catalogo.Oggi.apriDiario, Catalogo.Oggi.confrontoInArrivo, Catalogo.Oggi.prossimaPronta,
             ],
             frasi: [
                Catalogo.Oggi.attesiPrima(n: "§"), Catalogo.Oggi.ancoraDaGiocare(1), Catalogo.Oggi.ancoraDaGiocare(7),
                Catalogo.Oggi.giornataFinita(g: "§"), Catalogo.Oggi.conConsigliata(attesi: "§", fatti: "§"),
                Catalogo.Oggi.prossimaChiude(g: "§", quando: "§"), Catalogo.Oggi.prossimaDa(quando: "§"),
             ],
             usa: ["Catalogo.Oggi.ancoraDaGiocare(", "Catalogo.Oggi.giornataFinita(", "Catalogo.Oggi.prossimaChiude(",
                   "Catalogo.Oggi.prossimaDa(", "Catalogo.Oggi.prossimaPronta"]),
        Caso(file: "Sources/Domain/PartiteRinviate.swift",
             testi: [
                Catalogo.Oggi.rinvioTitolo1, Catalogo.Oggi.rinvioTitoloN, Catalogo.Oggi.rinvioDomanda, Catalogo.Oggi.rinvioAspetta,
                Catalogo.Oggi.rinvioSenzaVoto, Catalogo.Oggi.rinvioDaDefinire, Catalogo.Oggi.rinvioSalvato, Catalogo.Regole.rinviate,
                Catalogo.Regole.rinviateAiuto, Catalogo.Regole.rvAspetta, Catalogo.Regole.rvSenzaVoto, Catalogo.Regole.rvUfficio,
                Catalogo.Regole.rvAiutoAspetta, Catalogo.Regole.rvAiutoSenzaVoto, Catalogo.Regole.rvAiutoVotoUfficio,
             ],
             frasi: [
                Catalogo.Oggi.rinvioUfficio(v: "§"), Catalogo.Oggi.rinvioRecupero(quando: "§"), Catalogo.Oggi.rinvioMiei(nomi: "§"),
                Catalogo.Oggi.rinvioEccezione(regola: "§"), Catalogo.Oggi.recuperoManca(partite: "§"),
             ],
             usa: ["Catalogo.Oggi.rinvioUfficio(", "Catalogo.Oggi.rinvioEccezione(", "Catalogo.Oggi.recuperoManca(",
                   "Catalogo.Regole.rvAiutoVotoUfficio"]),
        Caso(file: "Sources/Domain/StatoScelta.swift",
             testi: [
                Catalogo.Formazione.statoConsigliata, Catalogo.Formazione.statoAltroModulo, Catalogo.Formazione.statoMano,
                Catalogo.Formazione.statoSalvata, Catalogo.Formazione.statoModificata, Catalogo.Formazione.statoNonValida,
                Catalogo.Formazione.statoChiusa, Catalogo.Formazione.statoChiusaTua, Catalogo.Formazione.statoChiusaNonValida,
                Catalogo.Tempo.giorno0, Catalogo.Tempo.giorno1, Catalogo.Tempo.giorno2, Catalogo.Tempo.giorno3,
                Catalogo.Tempo.giorno4, Catalogo.Tempo.giorno5, Catalogo.Tempo.giorno6,
             ],
             frasi: [Catalogo.Formazione.statoSalvataQuando(quando: "§"), Catalogo.Formazione.statoModificataQuando(quando: "§")],
             usa: ["Catalogo.Formazione.statoSalvataQuando(", "Catalogo.Formazione.statoModificataQuando(",
                   "Catalogo.Formazione.statoChiusaTua", "Catalogo.Formazione.giornoAlle(", "Catalogo.Formazione.alle(",
                   "Catalogo.Tempo.oggi", "Catalogo.Tempo.ieri", "Catalogo.Tempo.giorno6"]),
        Caso(file: "Sources/Domain/Modelli2.swift",
             testi: [Catalogo.Avv.prima, Catalogo.Avv.primaAiuto, Catalogo.Avv.prima0, Catalogo.Avv.prima30, Catalogo.Avv.prima60,
                     Catalogo.Avv.prima90],
             usa: ["Catalogo.Avv.prima", "Catalogo.Avv.primaAiuto", "Catalogo.Avv.prima0", "Catalogo.Avv.prima90"]),
        Caso(file: "Sources/Domain/InformazioniLegali.swift",
             testi: [Catalogo.Legale.privacy, Catalogo.Legale.termini, Catalogo.Legale.crediti],
             usa: ["Catalogo.Legale.privacy", "Catalogo.Legale.termini", "Catalogo.Legale.crediti"]),
        Caso(file: "Sources/Presentation/Lega/Gestione.swift",
             testi: [Catalogo.Avv.aveviSceltoOre, Catalogo.Avv.dalle, Catalogo.Avv.alle, Catalogo.Avv.oreTranq,
                     Catalogo.Avv.mandaAvvisoProva, Catalogo.Asp.avvisiTitolo, Catalogo.Comune.riprova],
             usa: ["Catalogo.Avv.aveviSceltoOre", "Catalogo.Avv.dalle", "Catalogo.Avv.alle", "Catalogo.Avv.mandaAvvisoProva",
                   "Catalogo.Asp.avvisiTitolo"]),
        Caso(file: "Sources/Presentation/Lega/LegaPagine.swift",
             testi: [Catalogo.Asp.tema, Catalogo.Asp.temaAuto, Catalogo.Asp.temaChiaro, Catalogo.Asp.temaScuro, Catalogo.Imp.aspetto],
             frasi: [Catalogo.Asp.autoSpiega],
             usa: ["Catalogo.Asp.tema", "Catalogo.Asp.temaAuto", "Catalogo.Asp.autoSpiega", "Catalogo.Imp.aspetto"]),
        Caso(file: "Sources/Presentation/Accesso/ConfiguraLegaView.swift",
             testi: [Catalogo.Comune.primaRose, Catalogo.Comune.importaSpiega],
             usa: ["Catalogo.Comune.primaRose", "Catalogo.Comune.importaSpiega", "Catalogo.Comune.importaRose"]),
        Caso(file: "Sources/Presentation/Lega/RegoleEditor.swift",
             testi: [
                Catalogo.Bonus.assist, Catalogo.Bonus.rigoreSegnato, Catalogo.Bonus.portiereImbattuto, Catalogo.Bonus.mvp,
                Catalogo.Bonus.ammonizione, Catalogo.Bonus.espulsione, Catalogo.Bonus.autogol, Catalogo.Bonus.rigoreSbagliato,
                Catalogo.Bonus.golSubitoPortiere, Catalogo.Regole.legheApriRegolamento,
                Catalogo.Regole.controllaValoriQui, Catalogo.Regole.valoriApplicatiControlla,
             ],
             usa: ["Catalogo.Bonus.assist", "Catalogo.Bonus.golSubitoPortiere", "Catalogo.Regole.legheApriRegolamento",
                   "Catalogo.Regole.controllaValoriQui", "Catalogo.Regole.valoriApplicatiControlla"]),
        // il pulsante del file con le parole del primo avvio della web (#594)
        Caso(file: "Sources/Presentation/Lega/ImportaRoseView.swift",
             testi: [Catalogo.Lega.esportaRoseExcel, Catalogo.Pav.scegliFile],
             usa: ["Catalogo.Lega.esportaRoseExcel", "Catalogo.Pav.scegliFile"]),
        Caso(file: "Sources/Support/RigaGiocatore.swift", testi: [Catalogo.Mercato.fantavoto, Catalogo.Perche.apriScheda],
             usa: ["Catalogo.Mercato.fantavoto", "Catalogo.Perche.apriScheda"]),
        Caso(file: "Sources/Presentation/Lega/RigaRosa.swift", testi: [Catalogo.Mercato.fantavoto], usa: ["Catalogo.Mercato.fantavoto"]),
    ]

    /// Un pezzo fisso più corto di così potrebbe stare per caso in un altro testo.
    static let pezzoMinimo = 6
    /// Un pezzo senza la punteggiatura ai lati si guarda solo se resta lungo almeno così.
    static let pezzoNudoMinimo = 12

    @Test("Nei file passati al catalogo nessun suo testo è scritto a mano fra virgolette", arguments: RestiDalCatalogoTests.casi)
    func nienteTestiAMano(caso: Caso) throws {
        let letterali = try Self.letterali(Self.codice(caso.file))
        for testo in caso.testi {
            #expect(!letterali.contains(Self.forma(testo)), "\(caso.file) scrive a mano «\(testo)»: usa Catalogo")
        }
        for frase in caso.frasi {
            for pezzo in Self.pezzi(frase) {
                #expect(!letterali.contains { $0.contains(pezzo) }, "\(caso.file) scrive a mano «\(pezzo)»: usa Catalogo")
            }
        }
    }

    @Test("I file passati al catalogo usano davvero le sue costanti", arguments: RestiDalCatalogoTests.casi)
    func usaIlCatalogo(caso: Caso) throws {
        let codice = try Self.codice(caso.file)
        for costante in caso.usa {
            #expect(Self.usa(codice, costante), "\(caso.file) non usa \(costante)")
        }
    }

    @Test("Regole: i testi d'aiuto dell'importazione da Leghe nominano il pulsante «Salva le regole», mai «Salva» da solo (#559)",
          arguments: [Catalogo.Regole.legheApriRegolamento, Catalogo.Regole.controllaValoriQui,
                      Catalogo.Regole.valoriApplicatiControlla])
    func aiutoRegoleNominaIlPulsante(testo: String) {
        #expect(Catalogo.Regole.salvaRegole == "Salva le regole")
        #expect(testo.contains("«\(Catalogo.Regole.salvaRegole)»"))
        #expect(!testo.contains("«Salva»"))
    }

    @Test("Il controllo «usa» vuole il nome intero: «Catalogo.Avv.prima» non vale dentro «Catalogo.Avv.primaAiuto»")
    func usaVuoleIlNomeIntero() {
        #expect(!Self.usa("static let aiuto = Catalogo.Avv.primaAiuto", "Catalogo.Avv.prima"))
        #expect(!Self.usa("case 0: return Catalogo.Avv.prima0", "Catalogo.Avv.prima"), "nemmeno con una cifra dopo")
        #expect(!Self.usa("Catalogo.Avv.prima_vecchia", "Catalogo.Avv.prima"))
        #expect(Self.usa("let a = Catalogo.Avv.primaAiuto\nlet t = Catalogo.Avv.prima", "Catalogo.Avv.prima"), "trovato dopo un falso inizio")
        #expect(Self.usa("Picker(Catalogo.Asp.tema, selection: $tema)", "Catalogo.Asp.tema"))
        #expect(Self.usa("nota = Catalogo.Perche.rispetto(n: Formato.punti(media))", "Catalogo.Perche.rispetto("),
                "un nome che finisce con «(» è una funzione: dopo può venire il nome del parametro")
        #expect(!Self.usa("nota = Catalogo.Perche.rispettoVecchio(n: m)", "Catalogo.Perche.rispetto("))
    }

    /// Il controllo deve trovare davvero un testo del catalogo scritto a mano: qui con un codice finto.
    @Test("Il controllo trova un testo del catalogo scritto a mano, anche dentro una frase con un valore")
    func ilControlloFunziona() throws {
        let codice = Self.soloCodice(#"""
        /// «Non disponibile» nel commento non conta
        Label("Non disponibile", systemImage: "eye.slash")
        let n = "Un giocatore medio del suo ruolo ha \(Formato.punti(media)). Il resto sono differenze piccole." // «Rinviata»
        let t = "la formazione si chiude \(quando)."
        #Preview("Torna a Oggi") { ErroreVista(messaggio: "", riprova: {}) }
        """#)
        let letterali = try Self.letterali(codice)
        #expect(letterali.contains(Self.forma(Catalogo.Dieta.nonDisponibile)))
        let rispetto = Self.pezzi(Catalogo.Perche.rispetto(n: "§"))
        #expect(rispetto.contains { p in letterali.contains { $0.contains(p) } })
        let chiude = Self.pezzi(Catalogo.Oggi.prossimaChiude(g: "§", quando: "§"))
        #expect(chiude.contains { p in letterali.contains { $0.contains(p) } }, "senza i due punti davanti si trova lo stesso")
        #expect(!letterali.contains(Self.forma(Catalogo.Dieta.tornaOggi)), "le anteprime non contano")
        #expect(!letterali.contains(Self.forma(Catalogo.Oggi.stRinviata)), "i commenti in fondo alla riga non contano")
        #expect(Self.pezzi(Catalogo.Oggi.ancoraDaGiocare(7)) == ["giocatori devono ancora giocare"])
        #expect(Self.pezzi(Catalogo.Oggi.giornataFinita(g: "§")) == [": finita"])
    }

    // MARK: lettura del sorgente

    /// Il codice usa la costante: il nome c'è e non continua con una lettera, una cifra o «_» («Catalogo.Avv.prima» non vale
    /// dentro «Catalogo.Avv.primaAiuto»). Un nome che finisce con «(» è una funzione e si cerca così com'è.
    static func usa(_ codice: String, _ costante: String) -> Bool {
        let parteDelNome: (Character) -> Bool = { $0.isLetter || $0.isNumber || $0 == "_" }
        guard let ultimo = costante.last, parteDelNome(ultimo) else { return codice.contains(costante) }
        var resto = codice[...]
        while let trovato = resto.range(of: costante) {
            let dopo = resto[trovato.upperBound...]
            if !(dopo.first.map(parteDelNome) ?? false) { return true }
            resto = dopo
        }
        return false
    }

    /// Un file di `ios/` (percorso dalla cartella `ios/`) senza commenti né anteprime.
    private static func codice(_ percorso: String, file: String = #filePath) throws -> String {
        var cartella = URL(fileURLWithPath: file)
        for _ in 0..<3 { cartella.deleteLastPathComponent() }          // questo file, SchieraxiTests, Tests
        let testo = try #require(try? String(contentsOf: cartella.appendingPathComponent(percorso), encoding: .utf8),
                                 "non riesco a leggere ios/\(percorso)")
        return soloCodice(testo)
    }

    /// Senza le righe di commento (`//`, `///`), i commenti in fondo alla riga e le anteprime (`#Preview("…")`).
    static func soloCodice(_ testo: String) -> String {
        testo.components(separatedBy: .newlines)
            .map { $0.trimmingCharacters(in: .whitespaces) }
            .filter { !$0.hasPrefix("//") && !$0.hasPrefix("#Preview") }
            .map { riga in riga.range(of: " //").map { String(riga[..<$0.lowerBound]) } ?? riga }
            .joined(separator: "\n")
    }

    /// Le forme dei testi fra virgolette di un sorgente Swift: ogni valore `\(…)` scritto «§».
    static func letterali(_ codice: String) throws -> [String] {
        let schema = try NSRegularExpression(pattern: #""((?:[^"\\\n]|\\.)*)""#)
        let tutto = NSRange(codice.startIndex..., in: codice)
        return schema.matches(in: codice, range: tutto)
            .compactMap { m in Range(m.range(at: 1), in: codice).map { forma(String(codice[$0])) } }
    }

    /// Il testo con ogni valore `\(…)` scritto «§»: «ha \(n).» e «ha \(Formato.punti(media)).» hanno la stessa forma.
    static func forma(_ testo: String) -> String {
        testo.replacingOccurrences(of: #"\\\((?:[^()]|\([^()]*\))*\)"#, with: "§", options: .regularExpression)
    }

    /// I pezzi fissi di una frase con un valore («§», o il numero 1 o 7 dei plurali): quelli lunghi almeno `pezzoMinimo` senza gli
    /// spazi ai lati e, se restano lunghi, anche senza la punteggiatura ai lati («: la formazione si chiude» si cerca anche come
    /// «la formazione si chiude»).
    static func pezzi(_ frase: String) -> [String] {
        let separatori = CharacterSet(charactersIn: "§17")
        let punteggiatura = CharacterSet.whitespaces.union(.punctuationCharacters)
        var risultato: [String] = []
        for parte in frase.components(separatedBy: separatori) {
            let pezzo = parte.trimmingCharacters(in: .whitespaces)
            guard pezzo.count >= pezzoMinimo else { continue }
            let nudo = pezzo.trimmingCharacters(in: punteggiatura)
            risultato.append(nudo.count >= pezzoNudoMinimo && nudo != pezzo ? nudo : pezzo)
        }
        return risultato
    }
}
