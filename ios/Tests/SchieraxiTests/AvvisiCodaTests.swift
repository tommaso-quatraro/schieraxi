import XCTest
@testable import Schieraxi

/// Avvisi: i salvataggi vanno uno alla volta e i promemoria locali seguono gli interruttori.
@MainActor
final class AvvisiCodaTests: XCTestCase {
    /// Un server che, come quello vero con If-Match, rifiuta (412) una scrittura che arriva mentre un'altra è ancora in corso.
    private final class Stato: @unchecked Sendable {
        private let blocco = NSLock()
        private var inCorso = 0
        private(set) var massimo = 0
        func entra() { blocco.lock(); inCorso += 1; massimo = max(massimo, inCorso); blocco.unlock() }
        func esce() { blocco.lock(); inCorso -= 1; blocco.unlock() }
        var occupato: Bool { blocco.lock(); defer { blocco.unlock() }; return inCorso > 0 }
    }

    func testDueInterruttoriToccatiInFrettaSiSalvanoTuttiEDue() async throws {
        let stato = Stato()
        let s = ServerDiProva { metodo, percorso, _ in
            if metodo == "PUT" {
                if stato.occupato { throw ErroreApi.conflitto }
                stato.entra()
                defer { stato.esce() }
                try await Task.sleep(nanoseconds: 150_000_000)
            }
            if percorso.hasPrefix("/api/avvisi") { return try Fixture.dati("avvisi") }
            return Data("{}".utf8)
        }
        let vm = AvvisiServerViewModel(server: s)
        await vm.carica()
        let riepilogo = try XCTUnwrap(vm.impostazioni?.riepilogo)
        let cambi = try XCTUnwrap(vm.impostazioni?.cambi)
        // come due tocchi: ognuno lancia il suo salvataggio senza aspettare l'altro
        vm.impostazioni?.riepilogo = !riepilogo
        let primo = Task { await vm.salva() }
        vm.impostazioni?.cambi = !cambi
        let secondo = Task { await vm.salva() }
        await primo.value
        await secondo.value
        XCTAssertEqual(stato.massimo, 1, "mai due salvataggi insieme")
        XCTAssertNil(vm.erroreSalvataggio, "niente falso «cambiato da un altro dispositivo»")
        let ultimo = String(decoding: try XCTUnwrap(s.corpiInviati(a: "PUT /api/avvisi").last), as: UTF8.self)
        XCTAssertTrue(ultimo.contains("\"riepilogo\":\(!riepilogo)"), ultimo)
        XCTAssertTrue(ultimo.contains("\"cambi\":\(!cambi)"), ultimo)
    }

    func testIPromemoriaLocaliSeguonoGliInterruttori() throws {
        let memoria = try XCTUnwrap(UserDefaults(suiteName: "prova-promemoria-\(UUID().uuidString)"))
        XCTAssertEqual(ArchivioPromemoria.minutiAttivi(memoria), [60, 15], "senza scelta: tutti e due, come prima")
        ArchivioPromemoria.salva(sessanta: false, quindici: true, memoria)
        XCTAssertEqual(ArchivioPromemoria.minutiAttivi(memoria), [15])
        ArchivioPromemoria.salva(sessanta: false, quindici: false, memoria)
        XCTAssertEqual(ArchivioPromemoria.minutiAttivi(memoria), [])

        let adesso = Date(timeIntervalSince1970: 1_793_500_000)
        let inizio = adesso.addingTimeInterval(5 * 3600)
        let tutti = Notifiche.promemoriaConsentiti(inizio: inizio, ore: .predefinite, adesso: adesso)
        XCTAssertEqual(tutti.map(\.minuti), [60, 15])
        let soloUnQuarto = Notifiche.promemoriaConsentiti(inizio: inizio, ore: .predefinite, attivi: [15], adesso: adesso)
        XCTAssertEqual(soloUnQuarto.map(\.minuti), [15], "«Promemoria un'ora prima» spento: il telefono non lo manda")
        XCTAssertTrue(Notifiche.promemoriaConsentiti(inizio: inizio, ore: .predefinite, attivi: [], adesso: adesso).isEmpty)
    }

    func testConGliAccountLaNotaStaAccantoAgliInterruttori() {
        XCTAssertTrue(AvvisiServerView.notaAccount.contains("questo telefono"))
        XCTAssertTrue(AvvisiServerView.notaAccount.contains("web app"))
    }
}
