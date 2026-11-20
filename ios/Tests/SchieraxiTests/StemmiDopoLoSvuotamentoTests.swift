import Foundation
import Testing
import UIKit
@testable import Schieraxi

// Issue #824. Nella foto `ipad_scuro_orizzontale_lega-squadre` «Squadre e rose» mostrava il cerchio con la lettera al posto di tutti
// gli stemmi e della maglia. In orizzontale quella foto segue `formazione-in-corso`, che nella demo ha un altro indirizzo finto:
// al lancio dopo, 0,7 secondi dall'avvio, la porta (`SessioneAccount.cambiaServer`) vede l'indirizzo cambiato e svuota i dati
// locali, compreso l'elenco di chi ha stemma e maglia (`Immagini.azzera`). Se l'elenco era già arrivato, nessuno lo chiedeva più:
// `caricaSquadra` senza elenco non chiede niente. Gli stessi passi qui, con un server finto e dati inventati.

@MainActor
@Suite("Stemmi e maglie dopo lo svuotamento dei dati locali (#824)")
struct StemmiDopoLoSvuotamentoTests {
    private static let squadra = "Gli Amici"

    private static func png() -> Data {
        UIGraphicsImageRenderer(size: CGSize(width: 20, height: 20)).pngData { c in
            UIColor.red.setFill()
            c.fill(CGRect(x: 0, y: 0, width: 20, height: 20))
        }
    }

    /// Un server senza account con una squadra che ha stemma e maglia. Ogni server ha un indirizzo suo: niente copie su disco
    /// di altri test. Con `trattieni` l'elenco delle squadre risponde solo quando quel flusso finisce.
    private static func server(trattieni: AsyncStream<Void>? = nil) -> ServerDiProva {
        let immagine = png()
        return ServerDiProva(indirizzo: "https://prova-824-\(UUID().uuidString).invalid") { metodo, percorso, _ in
            if percorso == "/api/account/me" { return Data(#"{"multiutente": false, "utente": null}"#.utf8) }
            if percorso.hasPrefix("/api/foto-disponibili") { return Data(#"{"ids": []}"#.utf8) }
            if percorso.hasPrefix("/api/squadre/immagine") && metodo == "GET" { return immagine }
            if percorso == "/api/squadre" {
                if let trattieni { for await _ in trattieni {} }
                return Data(#"[{"nome": "Gli Amici", "mia": true, "immagini": {"stemma": true, "maglia": true}}]"#.utf8)
            }
            throw ErroreApi.server("niente")
        }
    }

    /// Quante volte è stato chiesto l'elenco delle squadre (non le loro immagini, che cominciano allo stesso modo).
    private static func richiesteElenco(_ s: ServerDiProva) -> Int {
        s.richieste.filter { $0 == "GET /api/squadre" }.count
    }

    @Test("Dopo il cambio di indirizzo all'avvio, come nella foto, stemma e maglia tornano")
    func stemmaEMagliaDopoIlCambioDiIndirizzo() async throws {
        let nome = "stemmi-824-\(UUID().uuidString)"
        let memoria = try #require(UserDefaults(suiteName: nome))
        defer { memoria.removePersistentDomain(forName: nome) }
        // l'avvio di prima era su un altro indirizzo (nella demo: la foto `formazione-in-corso`, poi `lega-squadre`)
        memoria.set("https://prova-824-prima.invalid", forKey: "account.indirizzo")
        let s = Self.server()
        let immagini = Immagini(server: s)
        // widget e portachiavi finti: mai quelli veri del simulatore
        let luoghi = TokenWidget.Luoghi(archivio: MemoriaToken(), memoria: memoria, cartella: { nil }, portachiavi: MemoriaCollegamento(),
                                        sincronizza: {})
        let sessione = SessioneAccount(server: s, archivio: MemoriaToken(), memoria: memoria, pulisci: { immagini.azzera() }, widget: luoghi)

        // all'avvio la radice chiede gli elenchi e la riga della mia squadra carica stemma e maglia
        await immagini.caricaElenchi()
        await immagini.caricaSquadra(Self.squadra, tipo: "stemma")
        await immagini.caricaSquadra(Self.squadra, tipo: "maglia")
        try #require(immagini.memoriaSquadra(Self.squadra, tipo: "stemma") != nil)

        // poco dopo la porta vede l'indirizzo cambiato e svuota i dati locali, elenco compreso
        await sessione.cambiaServer()
        try #require(!immagini.haImmagine(Self.squadra, tipo: "stemma"), "lo svuotamento butta l'elenco delle squadre")
        #expect(immagini.memoriaSquadra(Self.squadra, tipo: "stemma") == nil)

        // le viste `StemmaSquadra` ripartono quando cambia `squadre[nome]` (`.task(id:)`): una volta perché l'elenco si è svuotato,
        // una volta quando arriva quello nuovo
        for _ in 0..<2 {
            await immagini.caricaSquadra(Self.squadra, tipo: "stemma")
            await immagini.caricaSquadra(Self.squadra, tipo: "maglia")
        }
        #expect(immagini.haImmagine(Self.squadra, tipo: "stemma"), "l'elenco si chiede di nuovo")
        #expect(immagini.memoriaSquadra(Self.squadra, tipo: "stemma") != nil, "lo stemma torna, niente lettera")
        #expect(immagini.memoriaSquadra(Self.squadra, tipo: "maglia") != nil, "la maglia torna")
    }

    /// L'altro ordine della stessa gara: lo svuotamento arriva mentre l'elenco chiesto all'avvio è ancora in viaggio.
    @Test("Svuotati i dati mentre l'elenco arriva: arrivato, le righe caricano subito lo stemma")
    func svuotamentoMentreLElencoArriva() async throws {
        let (trattieni, rilascia) = AsyncStream<Void>.makeStream()
        let s = Self.server(trattieni: trattieni)
        let immagini = Immagini(server: s)
        let avvio = Task { await immagini.caricaElenchi() }
        for _ in 0..<300 where Self.richiesteElenco(s) == 0 { try await Task.sleep(for: .milliseconds(10)) }
        try #require(Self.richiesteElenco(s) == 1, "l'elenco è in viaggio")
        immagini.azzera()
        rilascia.finish()
        await avvio.value
        try #require(immagini.haImmagine(Self.squadra, tipo: "stemma"))
        // la riga riparte perché l'elenco è cambiato: lo stemma si carica subito, senza chiedere l'elenco un'altra volta
        await immagini.caricaSquadra(Self.squadra, tipo: "stemma")
        #expect(immagini.memoriaSquadra(Self.squadra, tipo: "stemma") != nil)
        #expect(Self.richiesteElenco(s) == 1)
    }

    @Test("Le righe che ripartono insieme dopo lo svuotamento chiedono l'elenco una volta sola")
    func elencoChiestoUnaVolta() async {
        let s = Self.server()
        let immagini = Immagini(server: s)
        await immagini.caricaElenchi()
        immagini.azzera()
        let righe = (0..<8).map { i in
            Task { await immagini.caricaSquadra(Self.squadra, tipo: i.isMultiple(of: 2) ? "stemma" : "maglia") }
        }
        for riga in righe { await riga.value }
        #expect(Self.richiesteElenco(s) == 2, "una all'avvio e una dopo lo svuotamento, non una per riga")
        #expect(immagini.haImmagine(Self.squadra, tipo: "stemma"))
    }

    @Test("Con il server spento l'elenco mancante si chiede una volta, non a ogni riga")
    func serverSpentoUnaRichiesta() async {
        let s = ServerDiProva(indirizzo: "https://prova-824-spento-\(UUID().uuidString).invalid") { _, _, _ in
            throw ErroreApi.rete("spento")
        }
        let immagini = Immagini(server: s)
        for _ in 0..<3 {
            await immagini.caricaSquadra(Self.squadra, tipo: "stemma")
            await immagini.caricaSquadra("Altri", tipo: "stemma")
        }
        #expect(Self.richiesteElenco(s) == 1)
        #expect(immagini.memoriaSquadra(Self.squadra, tipo: "stemma") == nil)
    }
}
