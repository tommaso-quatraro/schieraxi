import Foundation
import Testing
@testable import Schieraxi

/// #495 (A3 dell'ondata 2): le frasi della Formazione che la web ha nel catalogo comune (`fanta/testi/formazione.json`) arrivano
/// all'iPhone da `Catalogo.Formazione`, generato da `script/testi.py` con le chiavi di `ios/testi/formazione.txt`. Nessun sorgente
/// della Formazione, del Confronto e della scheda del giocatore le riscrive a mano: così una frase cambiata nel catalogo cambia su
/// web e iPhone insieme, e una copia a mano rimasta indietro fa fallire questo test. Dove l'iPhone diceva un'altra cosa vince la web.
@MainActor
@Suite("Le parole della Formazione vengono dal catalogo")
struct FormazioneDalCatalogoTests {
    /// Il segno al posto dei valori nelle frasi con segnaposto: divide la frase nei suoi pezzi fissi.
    private static let segno = "\u{1}"

    /// La prima frase di `formazione.numero_sulla_maglia` («Negli elenchi il numero sul volto è l'indice: …»), con il suo punto:
    /// è quella che la legenda in fondo alla Formazione ha in comune con la web.
    private static var primaFraseIndice: String {
        let testo = Catalogo.Formazione.numeroSullaMaglia
        guard let fine = testo.range(of: ". ") else { return testo }
        return String(testo[..<fine.lowerBound]) + "."
    }

    /// Le frasi del catalogo che mostrano le viste della Formazione (con il segno al posto dei valori). Resta fuori
    /// `formazione.confronta_aria` («Confronta {nome} con un altro»): il suo inizio è anche in frasi del Confronto che non sono sue.
    private static var frasi: [String] {
        [
            Catalogo.Formazione.calcolo, Catalogo.Formazione.puntiAttesi, Catalogo.Formazione.mancanoProbabiliFormazioni,
            Catalogo.Formazione.staiGuardandoFormazione, Catalogo.Formazione.tornaAllaTua, Catalogo.Formazione.titolari,
            Catalogo.Formazione.toccaSostituire, Catalogo.Formazione.toccaConfronto, Catalogo.Formazione.ballottaggioAlternativeVic,
            Catalogo.Formazione.quasiPari, Catalogo.Formazione.questOrdineEntra, Catalogo.Formazione.fuoriDalla(n: segno),
            Catalogo.Formazione.senzaDati(nomi: segno), primaFraseIndice, Catalogo.Formazione.legendaApri,
            Catalogo.Formazione.copiaFormazione, Catalogo.Formazione.condividiImmagine, Catalogo.Formazione.modificaMano,
            Catalogo.Formazione.modificataMano, Catalogo.Formazione.propone(modulo: segno),
            Catalogo.Formazione.moduloFissato(modulo: segno), Catalogo.Formazione.rispetto(d: segno, n: segno),
            Catalogo.Formazione.salvaComeMia, Catalogo.Formazione.salvaModifiche, Catalogo.Formazione.giocatoriDelloStesso,
            Catalogo.Formazione.nessunAltroGiocatore, Catalogo.Formazione.alPostoDi(nome: segno), Catalogo.Formazione.salvaQuesta,
            Catalogo.Formazione.annullaModifiche, Catalogo.Formazione.tornaAllaConsigliata, Catalogo.Formazione.chiusa,
            Catalogo.Formazione.bloccati, Catalogo.Formazione.copiata, Catalogo.Formazione.nonRiescoCreare,
            Catalogo.Formazione.salvataComeTua,
        ]
    }

    // MARK: niente copie a mano

    @Test("Nessun sorgente della Formazione, del Confronto e della scheda riscrive a mano una frase del catalogo")
    func nienteFrasiAMano() throws {
        let file = try Self.sorgenti()
        try #require(file.count >= 10, "non trovo i sorgenti delle schermate: \(file.map(\.lastPathComponent))")
        // se la scheda del giocatore cambia cartella il controllo non deve saltarla in silenzio
        try #require(file.filter { $0.lastPathComponent.hasPrefix("SchedaGiocatore") }.count == 2,
                     "non trovo i due sorgenti della scheda del giocatore in Mercato/: \(file.map(\.lastPathComponent))")
        var trovate: [String] = []
        for url in file {
            let codice = try Self.codice(url)
            for frase in Self.frasi {
                for pezzo in Self.daCercare(frase) where codice.contains(pezzo) {
                    trovate.append("\(url.lastPathComponent): \(pezzo)")
                }
            }
        }
        #expect(trovate.isEmpty, "frasi del catalogo scritte a mano (si usa Catalogo.Formazione): \(trovate)")
    }

    @Test("Il controllo trova una frase scritta a mano, intera, dentro un altro testo o con un valore in mezzo")
    func ilControlloVede() {
        let codice = Self.senzaCommenti("""
        Text("Titolari")
        Text("propone il \\(modulo).")
        messaggio = "Formazione copiata: incollala dove vuoi."
        // Text("Annulla modifiche") in un commento non conta
        """)
        let trovate = Self.frasi.flatMap(Self.daCercare).filter { codice.contains($0) }
        #expect(trovate == ["\"Titolari\"", "\"propone il ", Catalogo.Formazione.copiata])
    }

    // MARK: dove l'iPhone diceva un'altra cosa, vince la web

    @Test("Copiata la formazione: la frase della web, senza il punto finale")
    func copiata() async throws {
        let vm = try await Self.caricata()
        let f = try #require(vm.formazione)
        vm.copiaTesto(f)
        #expect(vm.messaggio == Catalogo.Formazione.copiata)
    }

    @Test("Mentre carica, la frase della web («Calcolo la formazione migliore…»), non più «Scelgo gli undici…»")
    func caricamento() {
        #expect(FormazioneView.testoCaricamento == Catalogo.Formazione.calcolo)
    }

    @Test("Salvata la formazione: VoiceOver dice la frase della web («Salvata come tua scelta»)")
    func annuncioSalvata() {
        #expect(FormazioneViewModel.annuncioSalvata == Catalogo.Formazione.salvataComeTua)
    }

    @Test("La formazione di un'altra squadra: «Stai guardando la formazione di …» con il punto, come la web")
    func squadraVista() {
        #expect(FormazioneView.testoSquadraVista("Gli Amici") == Catalogo.Formazione.staiGuardandoFormazione + " Gli Amici.")
    }

    @Test("La legenda in fondo prende dal catalogo la frase sull'indice, una volta sola", arguments: [true, false])
    func legenda(conPerche: Bool) {
        let legenda = FormazioneView.legenda(conPerche: conPerche)
        #expect(legenda.hasSuffix(Self.primaFraseIndice))
        #expect(legenda.components(separatedBy: Self.primaFraseIndice).count == 2)
    }

    // MARK: aiuti

    /// Cosa cercare nel codice per una frase: senza segnaposto il letterale intero fra virgolette e, se è lunga (20 caratteri o
    /// più), la frase anche dentro un altro testo; con i segnaposto il primo pezzo dopo la virgoletta d'apertura e i pezzi lunghi
    /// (15 caratteri o più) che seguono un valore.
    private static func daCercare(_ frase: String) -> [String] {
        let pezzi = frase.components(separatedBy: segno)
        if pezzi.count == 1 { return frase.count >= 20 ? [frase] : ["\"\(frase)\""] }
        var cerca: [String] = []
        if let primo = pezzi.first, primo.count >= 6 { cerca.append("\"" + primo) }
        cerca += pezzi.dropFirst().filter { $0.count >= 15 }
        return cerca
    }

    /// La cartella `ios/` del repository (il test gira nel checkout).
    private static let ios = URL(fileURLWithPath: #filePath)
        .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()

    /// I sorgenti della Formazione (`Formazione/`), del Confronto (`Confronto/`) e della scheda del giocatore, che sta in
    /// `Mercato/` (`SchedaGiocatoreView.swift`, `SchedaGiocatoreViewModel.swift`): delle altre viste di `Mercato/` nessuna.
    private static func sorgenti() throws -> [URL] {
        let presentazione = ios.appendingPathComponent("Sources/Presentation", isDirectory: true)
        func swift(_ cartella: String, _ tiene: (String) -> Bool = { _ in true }) throws -> [URL] {
            try FileManager.default.contentsOfDirectory(at: presentazione.appendingPathComponent(cartella, isDirectory: true),
                                                        includingPropertiesForKeys: nil)
                .filter { $0.pathExtension == "swift" && tiene($0.lastPathComponent) }
        }
        return try (swift("Formazione") + swift("Confronto") + swift("Mercato") { $0.hasPrefix("SchedaGiocatore") })
            .sorted { $0.lastPathComponent < $1.lastPathComponent }
    }

    private static func codice(_ url: URL) throws -> String {
        try senzaCommenti(String(contentsOf: url, encoding: .utf8))
    }

    /// Il sorgente senza commenti: via le righe `//` e la parte di riga dopo un `//` fuori dalle virgolette.
    private static func senzaCommenti(_ sorgente: String) -> String {
        sorgente.components(separatedBy: .newlines).map { (riga: String) -> String in
            var virgolette = 0
            var prima: Character?
            for i in riga.indices {
                let c = riga[i]
                if c == "\"" { virgolette += 1 }
                if c == "/", prima == "/", virgolette.isMultiple(of: 2) { return String(riga[..<riga.index(before: i)]) }
                prima = c
            }
            return riga
        }
        .joined(separator: "\n")
    }

    /// La Formazione della fixture, caricata come sulla schermata (nessuna scelta salvata).
    private static func caricata() async throws -> FormazioneViewModel {
        let srv = ServerDiProva { _, percorso, _ in
            if percorso.hasPrefix("/api/scelta") { return Data("null".utf8) }
            return try Fixture.dati("formazione")
        }
        let vm = FormazioneViewModel(server: srv)
        await vm.carica()
        return vm
    }
}
