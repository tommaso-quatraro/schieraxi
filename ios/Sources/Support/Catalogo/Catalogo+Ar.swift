// Generato da script/testi.py: non modificare a mano.
// Testi da fanta/testi/ar.json, chiavi elencate in ios/testi/ar.txt.

extension Catalogo {
    enum Ar {
        /// `ar.leggo`
        static let leggo = "Leggo le rose…"

        /// `ar.cosa_cambia`
        static let cosaCambia = "Cosa cambia rispetto a ora"

        /// `ar.controlla`
        static let controlla = "Controlla prima di salvare"

        /// `ar.qual_e_tua`
        static let qualETua = "Qual è la tua squadra?"

        /// `ar.conferma`
        static let conferma = "Conferma e salva"

        /// `ar.annulla`
        static let annulla = "Annulla"

        /// `ar.nuova`
        static let nuova = "Nuova"

        /// `ar.rosa_completa`
        static let rosaCompleta = "Rosa completa"

        /// `ar.riconosciuti.one`, `ar.riconosciuti.other`
        static func riconosciuti(_ n: Int) -> String {
            n == 1 ? "\(n) giocatore riconosciuto" : "\(n) giocatori riconosciuti"
        }

        /// `ar.non_trovato`
        static let nonTrovato = "Non trovato"

        /// `ar.da_controllare`
        static let daControllare = "Da controllare"

        /// `ar.chi_e`
        static func chiE(nome: String, squadra: String) -> String {
            "Chi è «\(nome)» (\(squadra))?"
        }

        /// `ar.lascia_cosi`
        static let lasciaCosi = "Lascialo così per ora"

        /// `ar.cerco_io`
        static let cercoIo = "Un altro: lo cerco io"

        /// `ar.togli`
        static let togli = "Toglilo dalla rosa"

        /// `ar.cerca_segnaposto`
        static let cercaSegnaposto = "Scrivi il cognome"

        /// `ar.cerca_per`
        static func cercaPer(nome: String) -> String {
            "Cerca il giocatore giusto per «\(nome)»"
        }

        /// `ar.cambiate`
        static let cambiate = "Nel frattempo le rose sono cambiate, forse da un altro dispositivo: le ho rilette. Ricontrolla e conferma di nuovo."

        /// `ar.salvate`
        static let salvate = "Rose salvate"

        /// `ar.manca`
        static func manca(n: String, ruolo: String) -> String {
            "Manca \(n) \(ruolo)"
        }

        /// `ar.mancano`
        static func mancano(n: String, ruolo: String) -> String {
            "Mancano \(n) \(ruolo)"
        }

        /// `ar.in_piu`
        static func inPiu(n: String, ruolo: String) -> String {
            "\(n) \(ruolo) in più"
        }

        /// `ar.senza_ruolo.one`, `ar.senza_ruolo.other`
        static func senzaRuolo(_ n: Int) -> String {
            n == 1 ? "\(n) giocatore senza ruolo" : "\(n) giocatori senza ruolo"
        }

        /// `ar.c_e_scritto`
        static func cEScritto(nome: String, squadra: String) -> String {
            "Nella rosa di \(squadra) c'è scritto «\(nome)»."
        }

        /// `ar.giocatore_giusto`
        static let giocatoreGiusto = "Giocatore giusto"
    }
}
