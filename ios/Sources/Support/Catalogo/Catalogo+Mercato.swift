// Generato da script/testi.py: non modificare a mano.
// Testi da fanta/testi/mercato.json, chiavi elencate in ios/testi/mercato.txt.

extension Catalogo {
    enum Mercato {
        /// `mercato.osservi_avviso`
        static let osserviAvviso = "Lo segui: ti avviso se cambia qualcosa"

        /// `mercato.non_osservi`
        static let nonOsservi = "Non lo segui più"

        /// `mercato.nessun_giocatore_osservato`
        static let nessunGiocatoreOsservato = "Nessun giocatore seguito."

        /// `mercato.calendario_difficolta`
        static let calendarioDifficolta = "Calendario e difficoltà"

        /// `mercato.cal_spiega.one`, `mercato.cal_spiega.other`
        static func calSpiega(_ n: Int) -> String {
            n == 1 ? "Dalla più facile alla più difficile nella prossima giornata · pallino verde = tue squadre." : "Dalla più facile alla più difficile nelle prossime \(n) giornate · pallino verde = tue squadre."
        }

        /// `mercato.carico_calendario`
        static let caricoCalendario = "Carico il calendario…"

        /// `mercato.cerco_gli_svincolati`
        static let cercoGliSvincolati = "Cerco gli svincolati migliori…"

        /// `mercato.rimborso`
        static func rimborso(p: String) -> String {
            "Lo svincolo ti restituisce il \(p)% del prezzo pagato."
        }

        /// `mercato.crediti_dopo`
        static func creditiDopo(dopo: String, no: String) -> String {
            "crediti dopo \(dopo)\(no)"
        }

        /// `mercato.rimborso_n`
        static func rimborsoN(r: String) -> String {
            "rimborso \(r)"
        }

        /// `mercato.costo_n`
        static func costoN(c: String) -> String {
            "costo \(c)"
        }

        /// `mercato.non_bastano`
        static let nonBastano = " (non bastano)"

        /// `mercato.ruolo`
        static let ruolo = "Ruolo"

        /// `mercato.solo_svincolati`
        static let soloSvincolati = "Solo svincolati"

        /// `mercato.svincolato`
        static let svincolato = "Svincolato"

        /// `mercato.non_gioca`
        static let nonGioca = "non gioca"

        /// `mercato.bozza_copiata`
        static let bozzaCopiata = "Bozza copiata: incollala nel gruppo o in privato"

        /// `mercato.come_legge`
        static let comeLegge = "Come si legge"

        /// `mercato.annulla`
        static let annulla = "Annulla"
    }
}
