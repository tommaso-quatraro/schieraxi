// Generato da script/testi.py: non modificare a mano.
// Testi da fanta/testi/diario.json, chiavi elencate in ios/testi/diario.txt.

extension Catalogo {
    enum Diario {
        /// `diario.salvata`
        static let salvata = "Salvato: ho segnato che hai schierato la consigliata"

        /// `diario.salvata_manuale`
        static let salvataManuale = "Salvato: ho segnato i tuoi undici della giornata"

        /// `diario.non_salvata`
        static let nonSalvata = "Non avevi salvato la tua formazione per questa giornata."

        /// `diario.ho_schierato_questa`
        static let hoSchieratoQuesta = "Ho schierato la consigliata"

        /// `diario.ho_schierato_altra`
        static let hoSchieratoAltra = "Ho schierato un'altra formazione"

        /// `diario.correggi`
        static let correggi = "Correggi a mano"

        /// `diario.tua`
        static func tua(modulo: String) -> String {
            "La tua (\(modulo))"
        }

        /// `diario.tua_consigliata`
        static func tuaConsigliata(modulo: String) -> String {
            "La tua, la consigliata (\(modulo))"
        }

        /// `diario.cosa_hai_schierato_titolo`
        static let cosaHaiSchieratoTitolo = "Cosa hai schierato"

        /// `diario.correggi_spiega`
        static func correggiSpiega(g: String) -> String {
            "\(g): tocca i giocatori che hai schierato. Servono 11 titolari."
        }

        /// `diario.qp_andamento`
        static let qpAndamento = "Giornata per giornata"
    }
}
