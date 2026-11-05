import Foundation
import Testing
@testable import Schieraxi

/// Le foto dei widget e quelle dell'app raccontano la stessa lega inventata (#192): una sola fonte (`LegaDemo`), quindi gli
/// stessi nomi con gli accenti, la stessa percentuale di chi è in dubbio, la stessa scadenza, le stesse giornate del Diario.
/// E dati possibili (#194): prima della scadenza nessuna partita è in corso. App e widget si costruiscono nello stesso istante.
@Suite("Demo: i widget dicono le stesse cose dell'app")
struct DemoWidgetComeAppTests {
    /// Un istante fisso (fine ottobre 2026): app e widget nello stesso momento, lo stesso risultato a ogni corsa.
    static let adesso = Date(timeIntervalSinceReferenceDate: 815_000_000)
    /// La demo dell'app in quell'istante, costruita una volta sola.
    static let demoApp = FinteServer.demoFissata(adesso: adesso)

    /// Una risposta della demo dell'app (con `schermata` quella di una fase: `oggi-in-corso`, `oggi-finita`).
    private func app(_ percorso: String, schermata: String? = nil) throws -> [String: Any] {
        let server: FinteServer?
        if let schermata { server = FinteServer.demoFase(schermata, adesso: Self.adesso) } else { server = Self.demoApp }
        let s = try #require(server, "nessuna demo per \(schermata ?? "oggi")")
        let testo = try #require(s.risposte[percorso], "la demo dell'app non ha \(percorso)")
        return try #require(try JSONSerialization.jsonObject(with: Data(testo.utf8)) as? [String: Any])
    }

    private func widget(_ fase: LegaDemo.Fase = .prima, parziali: Bool = false) throws -> RiassuntoWidget {
        try #require(RiassuntoWidget.leggi(LegaDemo.widget(adesso: Self.adesso, fase: fase, parziali: parziali)),
                     "il riassunto dei widget della demo non si legge")
    }

    private func live(_ dati: [String: Any]) throws -> LiveWidget {
        let d = JSONDecoder()
        d.keyDecodingStrategy = .convertFromSnakeCase
        return try d.decode(LiveWidget.self, from: try JSONSerialization.data(withJSONObject: dati))
    }

    private func elenco(_ d: [String: Any], _ chiave: String) throws -> [[String: Any]] {
        try #require(d[chiave] as? [[String: Any]], "manca «\(chiave)»")
    }

    /// Un numero di un JSON letto con JSONSerialization, scritto come lo scrive l'app («69,0»).
    private func punti(_ valore: Any?) -> String { Formato.punti(valore as? Double) }

    @Test("Marténi in dubbio: stessa percentuale e stesse parole in Oggi e nel widget")
    func dubbioComeOggi() throws {
        let avvisi = try elenco(try app("/api/oggi"), "avvisi")
        let marteni = try #require(avvisi.first { $0["id"] as? Int == 120 })
        let inFormazione = avvisi.filter { $0["in_formazione"] as? Bool == true }.compactMap { $0["id"] as? Int }
        let w = try widget()
        let nelWidget = try #require(w.avvisi?.first { $0.id == 120 }, "nel widget Marténi non è tra gli avvisi")
        let dubbio = w.comeRiassuntoOggi(scaricatoIl: Self.adesso)?.dubbi?.first { $0.id == 120 }
        #expect(nelWidget.nome == marteni["nome"] as? String)
        #expect(nelWidget.pVoto == marteni["p_voto"] as? Double)
        #expect(dubbio?.descrizione == "In dubbio · gioca 62%")
        #expect(w.daControllare.map(\.id) == inFormazione)
    }

    @Test("La rosa nel widget è quella dell'app: stessi nomi con gli accenti, stessa probabilità di giocare, stesso stato")
    func rosaComeLApp() throws {
        let rosa = try elenco(try app("/api/rosa"), "giocatori")
        let w = try widget()
        let nelWidget = Dictionary((w.rosa ?? []).map { ($0.id, $0) }, uniquingKeysWith: { a, _ in a })
        #expect(nelWidget.count == rosa.count)
        for g in rosa {
            let id = try #require(g["id"] as? Int)
            let nome = g["nome"] as? String
            let previsione = g["previsione"] as? [String: Any]
            let suo = try #require(nelWidget[id], "\(nome ?? "?") non è nella rosa del widget")
            #expect(suo.nome == nome)
            #expect(suo.pVoto == previsione?["p_voto"] as? Double, "\(suo.nome)")
            #expect(suo.stato == previsione?["stato"] as? String, "\(suo.nome)")
        }
        for t in w.formazione?.titolari ?? [] { #expect(nelWidget[t.id]?.nome == t.nome) }
    }

    @Test("Giornata, scadenza, prima partita e punti attesi sono quelli di Oggi")
    func scadenzaComeOggi() throws {
        let oggi = try app("/api/oggi")
        let formazione = oggi["formazione"] as? [String: Any]
        let w = try widget()
        #expect(w.giornata == oggi["giornata"] as? Int)
        #expect(w.giornataLega == oggi["giornata_lega"] as? Int)
        #expect(w.scadenza == oggi["scadenza"] as? String)
        #expect(w.primaPartita == oggi["inizio"] as? String)
        #expect(Formato.punti(w.formazione?.puntiAttesi) == punti(formazione?["punteggio_atteso"]))
    }

    @Test("Accanto ai titolari il widget scrive il fantavoto atteso della Formazione dell'app, con lo stesso nome (#240)")
    func titolariComeLaFormazione() throws {
        let titolariApp = try elenco(try app("/api/formazione"), "titolari")
        let f = try #require(try widget().formazione)
        let tit = try #require(f.titolari)
        #expect(tit.map(\.id) == titolariApp.compactMap { $0["id"] as? Int })
        for (g, a) in zip(tit, titolariApp) {
            #expect(f.numeroTitolare(g) == punti(a["fv_atteso"]), "\(g.nome)")
        }
        #expect(f.nomeNumeroTitolari.first == FantavotoAtteso.nome)
    }

    @Test("Prima della scadenza nessuna partita è in corso, né nel widget né nell'app; gli orari sono quelli di Oggi")
    func primaDellaScadenza() throws {
        let liveApp = try live(try app("/api/live"))
        let orari = try elenco(try app("/api/oggi"), "partite").map { "\($0["casa"] as? String ?? "")-\($0["trasferta"] as? String ?? ""): \($0["data"] as? String ?? "")" }
        let w = try widget()
        let inizio = try #require(w.inizio)
        #expect(inizio > Self.adesso)
        #expect(w.partiteInGioco.isEmpty)
        #expect(!w.partiteLive.isEmpty)
        #expect(liveApp.partite?.contains(where: \.inGioco) == false)
        #expect((w.live?.partite ?? []).map { "\($0.id): \($0.data ?? "")" } == orari)
    }

    @Test("Giornata in corso: scadenza passata, le stesse partite e gli stessi punti dell'app")
    func giornataInCorso() throws {
        let partiteApp = try live(try app("/api/live", schermata: "oggi-in-corso")).partite ?? []
        let inCorso = try #require(try app("/api/oggi", schermata: "oggi-in-corso")["in_corso"] as? [String: Any])
        let w = try widget(.inCorso)
        let inizio = try #require(w.inizio)
        #expect(inizio < Self.adesso)
        #expect(!w.partiteInGioco.isEmpty)
        #expect((w.live?.partite ?? []).map { "\($0.id) \($0.stato ?? "") \($0.punteggio)" }
                == partiteApp.map { "\($0.id) \($0.stato ?? "") \($0.punteggio)" })
        #expect(Formato.punti(w.faseGiornata.inCorso?.puntiFatti) == punti(inCorso["punti_fatti"]))
        #expect(Formato.punti(w.faseGiornata.inCorso?.puntiPrevisti) == punti(inCorso["punti_previsti"]))
    }

    @Test("Giornata finita: la prossima giornata e il riepilogo sono quelli dell'app")
    func giornataFinita() throws {
        let oggi = try app("/api/oggi", schermata: "oggi-finita")
        let riepilogo = try #require(oggi["riepilogo"] as? [String: Any])
        let w = try widget(.finita)
        #expect(w.giornata == oggi["giornata"] as? Int)
        #expect(w.scadenza == oggi["scadenza"] as? String)
        #expect(Formato.punti(w.faseGiornata.riepilogo?.puntiFatti) == punti(riepilogo["punti_fatti"]))
        #expect(w.partiteInGioco.isEmpty)
    }

    @Test("«Attesi e fatti» del widget sono le giornate del Diario dell'app (la tua formazione se c'era)")
    func diarioComeLApp() throws {
        let attese = try elenco(try app("/api/diario"), "giornate").map { g -> String in
            let e = (g["schierata"] as? [String: Any]) ?? (g["consigliata"] as? [String: Any]) ?? [:]
            return "G\(g["giornata_lega"] as? Int ?? 0): \(punti(e["atteso"])) → \(punti(e["reale"]))"
        }
        let w = try widget()
        #expect(w.giornateGiocate.map { "G\($0.numero): \(Formato.punti($0.attesi)) → \(Formato.punti($0.fatti))" } == attese)
    }

    @Test("Seguiti, crediti, scambio e svincolo del widget sono quelli dell'app")
    func restoComeLApp() throws {
        let seguiti = try elenco(try app("/api/osservati"), "giocatori").compactMap { $0["id"] as? Int }
        let mercato = try app("/api/mercato")
        let svincolo = try #require(try elenco(mercato, "proposte").first)
        let scambio = try #require(try elenco(try app("/api/scambi/proposte"), "proposte").first)
        let dai = (scambio["do"] as? [[String: Any]])?.compactMap { $0["id"] as? Int }
        let ricevi = (scambio["ricevo"] as? [[String: Any]])?.compactMap { $0["id"] as? Int }
        let w = try widget()
        #expect(w.osservati?.map(\.id) == seguiti)
        #expect(w.creditiResidui == mercato["crediti_residui"] as? Double)
        #expect(w.svincolato?.entra?.id == (svincolo["entra"] as? [String: Any])?["id"] as? Int)
        #expect(w.svincolato?.esce?.id == (svincolo["esce"] as? [String: Any])?["id"] as? Int)
        #expect(Formato.punti(w.svincolato?.guadagno) == punti(svincolo["guadagno"]))
        #expect(w.scambio?.altra == scambio["altra"] as? String)
        #expect(Formato.punti(w.scambio?.guadagnoMio) == punti(scambio["guadagno_mio"]))
        #expect(w.scambio?.`do`?.compactMap(\.id) == dai)
        #expect(w.scambio?.ricevo?.compactMap(\.id) == ricevi)
    }

    @Test("Un server senza scambio e svincolo: lo dice in «mancano», il resto c'è")
    func parziali() throws {
        let w = try widget(parziali: true)
        #expect(w.scambio == nil)
        #expect(w.svincolato == nil)
        #expect(Set(w.mancano ?? []) == ["scambio", "svincolato"])
        #expect(w.formazione?.titolari?.count == 11)
    }
}
