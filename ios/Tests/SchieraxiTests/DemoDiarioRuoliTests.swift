import Foundation
import Testing
@testable import Schieraxi

/// Le formazioni del Diario della demo (Giornate) hanno i ruoli giusti (foto di `main`, corsa 45951751934): Pulinski era
/// attaccante nel Diario (`DatiDemo.swift`) e centrocampista nella rosa (`LegaDemo.swift`), e Giornate elencava un 3-4-3 con 3
/// centrocampisti e 4 attaccanti. Qui ogni formazione conta i ruoli del suo modulo, e chi è anche nella rosa della demo ha lo
/// stesso ruolo. Dati inventati: quelli di `DatiDemo.swift` e `LegaDemo.swift`.
struct DemoDiarioRuoliTests {

    private func diario() async throws -> DiarioRisposta {
        try Decodifica.decodifica(try await FinteServer.demo.richiesta("GET", "/api/diario", corpo: nil))
    }

    /// Le formazioni di una giornata con il loro nome: consigliata, tua, copia salvata alla scadenza, mostrata prima della scadenza.
    private func formazioni(_ v: VoceDiario) -> [(nome: String, modulo: String?, titolari: [TitolareDiario])] {
        var tutte: [(nome: String, modulo: String?, titolari: [TitolareDiario])] = []
        if let c = v.consigliata { tutte.append(("consigliata", c.modulo, c.titolari ?? [])) }
        if let s = v.schierata { tutte.append(("tua", s.modulo, s.titolari ?? [])) }
        if let a = v.automatica { tutte.append(("salvata alla scadenza", a.modulo, a.titolari ?? [])) }
        if let i = v.istantanea { tutte.append(("mostrata prima della scadenza", i.modulo, i.titolari ?? [])) }
        return tutte
    }

    @Test("Ogni formazione del Diario della demo ha i ruoli del suo modulo: 1 portiere, poi difensori, centrocampisti e attaccanti")
    func ruoliComeIlModulo() async throws {
        let voci = try await diario().giornate ?? []
        try #require(!voci.isEmpty, "nel diario della demo non ci sono giornate")
        var sbagliate: [String] = []
        for v in voci {
            for f in formazioni(v) {
                let ruoli = f.titolari.compactMap(\.ruolo)
                let modulo = ModuloTitolari.modulo(ruoli: ruoli)
                let portieri = ruoli.filter { $0 == "P" }.count
                if ruoli.count != 11 || portieri != 1 || modulo != f.modulo {
                    sbagliate.append("giornata \(v.giornata ?? 0), \(f.nome): \(f.modulo ?? "?") ma \(portieri) portieri e \(modulo)")
                }
            }
        }
        #expect(sbagliate.isEmpty, "formazioni con i ruoli che non tornano: \(sbagliate)")
    }

    @Test("Chi è nel Diario e nella rosa della demo ha lo stesso ruolo nei due posti")
    func stessiRuoliDellaRosa() async throws {
        let voci = try await diario().giornate ?? []
        // il Diario scrive i giocatori per cognome: «Pulinski» è «Cesare Pulinski» della rosa
        func dallaRosa(_ cognome: String) -> CalciatoreDemo? {
            LegaDemo.tutti.first { $0.nome == cognome || $0.nome.hasSuffix(" " + cognome) }
        }
        var visti = Set<String>()
        var diversi: [String] = []
        for v in voci {
            for f in formazioni(v) {
                for t in f.titolari {
                    guard let nome = t.nome, let ruolo = t.ruolo, let r = dallaRosa(nome) else { continue }
                    visti.insert(nome)
                    if r.ruolo != ruolo { diversi.append("\(nome): \(ruolo) nel Diario, \(r.ruolo) nella rosa") }
                }
            }
        }
        #expect(visti.contains("Pulinski") && visti.contains("Marténi"), "il Diario non ha più i giocatori della rosa: il test non prova niente")
        #expect(Set(diversi).isEmpty, "ruoli diversi fra Diario e rosa della demo: \(Set(diversi).sorted())")
    }
}
