import Foundation
import Testing
import UserNotifications
@testable import Schieraxi

/// Gli avvisi dell'app con l'app aperta e il tocco su di loro, come la web (`fanta/web/sw.js`: l'avviso si mostra sempre e il tocco
/// apre `/?vista=formazione`) e come ntfy (`schieraxi://formazione`). Prima nell'app non c'era un delegato delle notifiche di iOS:
/// con l'app aperta il promemoria di un quarto d'ora prima non si vedeva, e il tocco apriva l'app dove l'avevi lasciata.
@MainActor
@Suite("Avvisi con l'app aperta e tocco sull'avviso", .serialized)
struct AvvisiConAppApertaTests {
    @Test("All'avvio l'app fa da delegato delle notifiche di iOS: senza, iOS non chiede all'app cosa fare")
    func delegatoAllAvvio() {
        #expect(UNUserNotificationCenter.current().delegate === DelegatoAvvisi.condiviso)
    }

    @Test("Con l'app aperta un avviso si mostra come ad app chiusa: banner, Centro Notifiche e suono")
    func conAppAperta() {
        #expect(Notifiche.conAppAperta.contains(.banner))
        #expect(Notifiche.conAppAperta.contains(.list))
        #expect(Notifiche.conAppAperta.contains(.sound))
    }

    @Test("Il tocco su un promemoria della scadenza porta dove porta `schieraxi://formazione`", arguments: ["fanta-60", "fanta-15"])
    func promemoriaAllaFormazione(id: String) throws {
        let formazione = try #require(URL(string: "schieraxi://formazione").flatMap { Collegamenti.interpreta($0) })
        #expect(formazione == .sezione(.formazione))
        #expect(Notifiche.destinazione(identificativo: id) == formazione)
    }

    @Test("Il tocco sugli altri avvisi (certificato, versione nuova) apre l'app dov'era",
          arguments: ["fanta-cert-24", "fanta-cert-6", "nuova-versione", "sconosciuto"])
    func altriAvvisi(id: String) {
        #expect(Notifiche.destinazione(identificativo: id) == nil)
    }

    @Test("Il tocco aspetta l'app (anche quando è lui ad aprirla), che va sulla Formazione una volta sola")
    func toccoConsegnato() {
        let prima = UserDefaults.standard.string(forKey: "ultimaSezione")
        defer { UserDefaults.standard.set(prima, forKey: "ultimaSezione") }
        let tocchi = AvvisiToccati()
        let nav = Navigazione()
        nav.sezione = .giornate
        tocchi.tocca(identificativo: "fanta-15")
        #expect(tocchi.destinazione == .sezione(.formazione), "il tocco resta lì finché l'app non lo prende")
        tocchi.consegna(a: nav)
        #expect(nav.sezione == .formazione)
        #expect(tocchi.destinazione == nil)
        nav.sezione = .giornate
        tocchi.consegna(a: nav)
        #expect(nav.sezione == .giornate, "un tocco porta una volta sola")
        tocchi.tocca(identificativo: "fanta-cert-6")
        #expect(tocchi.destinazione == nil, "il promemoria del certificato non porta da nessuna parte")
    }
}
