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

    /// Le frasi del catalogo che mostrano le viste della Formazione unica (#673) e della scheda (con il segno al posto dei valori).
    private static var frasi: [String] {
        [
            Catalogo.Formazione.calcolo, Catalogo.Formazione.puntiAttesi, Catalogo.Formazione.mancanoProbabiliFormazioni,
            Catalogo.Formazione.staiGuardandoFormazione, Catalogo.Formazione.tornaAllaTua,
            Catalogo.Formazione.questOrdineEntra, Catalogo.Formazione.nonSchierati(n: segno), Catalogo.Formazione.indisponibili(n: segno),
            Catalogo.Formazione.senzaDati(nomi: segno),
            Catalogo.Formazione.tornaAllaConsigliata, Catalogo.Formazione.sceltaNonLetta, Catalogo.Formazione.copiaFerma,
            Catalogo.Formazione.stoAncoraRicalcolando, Catalogo.Formazione.comeAndata,
            Catalogo.Formazione.copiaLega, Catalogo.Formazione.copiataLega, Catalogo.Formazione.nonCopio, Catalogo.Formazione.messa,
            Catalogo.Formazione.usaConsigliata, Catalogo.Formazione.decisionePunti(d: segno),
            Catalogo.Formazione.opzioneConsigliato(modulo: segno, punti: segno), Catalogo.Formazione.diSolito(a: segno, b: segno),
            Catalogo.Formazione.nessunAltroGiocatore, Catalogo.Formazione.alPostoDi(nome: segno), Catalogo.Formazione.sostSpiega(nome: segno),
            Catalogo.Formazione.puntiRispetto(nome: segno), Catalogo.Formazione.chiusa, Catalogo.Formazione.bloccati,
            // la scheda del giocatore unica (#616)
            Catalogo.Formazione.partitaCasa(avv: segno, quando: segno), Catalogo.Formazione.partitaFuori(avv: segno, quando: segno),
            Catalogo.Formazione.seGioca, Catalogo.Formazione.percheTitolare, Catalogo.Formazione.incerto(p: segno, riserva: segno),
            Catalogo.Formazione.ultimiVoti, Catalogo.Formazione.sostituisci, Catalogo.Formazione.tuttiNumeri,
            Catalogo.Formazione.questaPartita,
        ]
    }

    // MARK: niente copie a mano

    @Test("Nessun sorgente della Formazione e della scheda riscrive a mano una frase del catalogo")
    func nienteFrasiAMano() throws {
        let file = try Self.sorgenti()
        try #require(file.count >= 6, "non trovo i sorgenti delle schermate: \(file.map(\.lastPathComponent))")
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
        Text("L'ho messa")
        Text("Al posto di \\(nome)")
        messaggio = "Formazione copiata: ora mettila nell'app della lega"
        // Text("Torna alla consigliata") in un commento non conta
        """)
        let trovate = Self.frasi.flatMap(Self.daCercare).filter { codice.contains($0) }
        #expect(Set(trovate) == ["\"L'ho messa\"", "\"Al posto di ", Catalogo.Formazione.copiataLega])
        #expect(trovate.count == 3)
    }

    // MARK: dove l'iPhone diceva un'altra cosa, vince la web

    @Test("«Copia per l'app della lega»: la frase della web, e da copiare il testo della formazione in campo")
    func copiata() async throws {
        let vm = try await Self.caricata()
        let f = try #require(vm.formazione)
        vm.copiaTesto(f)
        #expect(vm.messaggio == Catalogo.Formazione.copiataLega)
        #expect(vm.testo(f).hasPrefix("9ª giornata di Serie A · 4-3-3\n"), "la fixture non ha `giornata_lega`")
    }

    @Test("Mentre carica, la frase della web («Calcolo la formazione migliore…»), non più «Scelgo gli undici…»")
    func caricamento() {
        #expect(FormazioneView.testoCaricamento == Catalogo.Formazione.calcolo)
    }

    @Test("La formazione di un'altra squadra: «Stai guardando la formazione di …» con il punto, come la web")
    func squadraVista() {
        #expect(FormazioneView.testoSquadraVista("Gli Amici") == Catalogo.Formazione.staiGuardandoFormazione + " Gli Amici.")
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

    /// I sorgenti della Formazione (`Formazione/`) e della scheda del giocatore, che sta in `Mercato/`
    /// (`SchedaGiocatoreView.swift`, `SchedaGiocatoreViewModel.swift`): delle altre viste di `Mercato/` nessuna.
    private static func sorgenti() throws -> [URL] {
        let presentazione = ios.appendingPathComponent("Sources/Presentation", isDirectory: true)
        func swift(_ cartella: String, _ tiene: (String) -> Bool = { _ in true }) throws -> [URL] {
            try FileManager.default.contentsOfDirectory(at: presentazione.appendingPathComponent(cartella, isDirectory: true),
                                                        includingPropertiesForKeys: nil)
                .filter { $0.pathExtension == "swift" && tiene($0.lastPathComponent) }
        }
        return try (swift("Formazione") + swift("Mercato") { $0.hasPrefix("SchedaGiocatore") })
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
