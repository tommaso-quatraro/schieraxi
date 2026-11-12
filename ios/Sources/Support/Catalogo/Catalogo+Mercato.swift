// Generato da script/testi.py: non modificare a mano.
// Testi da fanta/testi/mercato.json, chiavi elencate in ios/testi/mercato.txt.

extension Catalogo {
    enum Mercato {
        /// `mercato.non_gioca`
        static let nonGioca = "non gioca"

        /// `mercato.come_legge`
        static let comeLegge = "Come si legge"

        /// `mercato.annulla`
        static let annulla = "Annulla"

        /// `mercato.fantavoto`
        static let fantavoto = "fantavoto"

        /// `mercato.carico_scheda`
        static let caricoScheda = "Carico la scheda…"

        /// `mercato.fantavoto_atteso`
        static let fantavotoAtteso = "Fantavoto atteso"

        /// `mercato.gioca`
        static let gioca = "gioca"

        /// `mercato.nessuna_previsione_per`
        static let nessunaPrevisionePer = "Nessuna previsione per la prossima giornata."

        /// `mercato.nessuna_presenza_questa`
        static let nessunaPresenzaQuesta = "Nessuna presenza in questa stagione."

        /// `mercato.sv`
        static let sv = "sv"

        /// `mercato.svincolato`
        static let svincolato = "Svincolato"

        /// `mercato.quot`
        static func quot(n: String) -> String {
            "quotazione \(n)"
        }

        /// `mercato.gol_attesi`
        static func golAttesi(a: String, b: String) -> String {
            "risultato atteso \(a)–\(b)"
        }

        /// `mercato.porta_inviolata`
        static let portaInviolata = "non subisce gol"

        /// `mercato.gol_subiti_attesi`
        static let golSubitiAttesi = "gol che può subire"

        /// `mercato.giallo`
        static let giallo = "giallo"

        /// `mercato.segna`
        static let segna = "segna"

        /// `mercato.assist`
        static let assist = "assist"

        /// `mercato.rosso`
        static let rosso = "rosso"

        /// `mercato.prossime_partite`
        static let prossimePartite = "Prossime partite"

        /// `mercato.colori_verde_partita`
        static let coloriVerdePartita = "Colori: verde partita facile, rosso partita dura."

        /// `mercato.forma`
        static let forma = "Forma"

        /// `mercato.andamento`
        static let andamento = "Andamento"

        /// `mercato.pochi_dati`
        static let pochiDati = "pochi dati"

        /// `mercato.in_crescita`
        static let inCrescita = "in crescita"

        /// `mercato.in_calo`
        static let inCalo = "in calo"

        /// `mercato.stabile`
        static let stabile = "stabile"

        /// `mercato.voto_fantavoto_per`
        static let votoFantavotoPer = "Voto e fantavoto per giornata"

        /// `mercato.rende_sopra_sotto`
        static let rendeSopraSotto = "Gol e assist rispetto alle occasioni"

        /// `mercato.punti_partita`
        static let puntiPartita = "punti a partita"

        /// `mercato.rendimento_riga`
        static func rendimentoRiga(a: String, g: String) -> String {
            "Gol \(g) rispetto ai gol attesi · assist \(a) rispetto agli assist attesi."
        }

        /// `mercato.rend_cala`
        static let rendCala = "Sta segnando più di quanto crea: è probabile che cali."

        /// `mercato.rend_sblocca`
        static let rendSblocca = "Crea più di quanto segna: è probabile che si sblocchi."

        /// `mercato.rend_linea`
        static let rendLinea = "In linea con le occasioni che ha."

        /// `mercato.stagione`
        static let stagione = "Stagione"

        /// `mercato.presenze`
        static let presenze = "presenze"

        /// `mercato.media_voto`
        static let mediaVoto = "media voto"

        /// `mercato.fantamedia`
        static let fantamedia = "fantamedia"

        /// `mercato.gol_rig`
        static func golRig(n: String) -> String {
            "gol (\(n) rig.)"
        }

        /// `mercato.gialli_rossi`
        static let gialliRossi = "gialli/rossi"

        /// `mercato.gol_subiti`
        static let golSubiti = "gol subiti"

        /// `mercato.rigori_parati`
        static let rigoriParati = "rigori parati"

        /// `mercato.statistiche_avanzate`
        static let statisticheAvanzate = "Statistiche avanzate"

        /// `mercato.gol_attesi_tot`
        static let golAttesiTot = "gol attesi"

        /// `mercato.assist_attesi_tot`
        static let assistAttesiTot = "assist attesi"

        /// `mercato.minuti`
        static let minuti = "minuti"

        /// `mercato.xg_90`
        static let xg90 = "gol attesi ogni 90'"

        /// `mercato.xa_90`
        static let xa90 = "assist attesi ogni 90'"

        /// `mercato.tiri_90`
        static let tiri90 = "tiri ogni 90'"

        /// `mercato.rigori_calciati`
        static let rigoriCalciati = "rigori calciati"

        /// `mercato.passaggi_chiave`
        static let passaggiChiave = "passaggi chiave"

        /// `mercato.punizioni`
        static let punizioni = "punizioni tirate"

        /// `mercato.stagione_prec`
        static func stagionePrec(a: String, g: String, m: String, s: String, xa: String, xg: String) -> String {
            "Stagione \(s): \(m)' · \(g) gol (\(xg) attesi) · \(a) assist (\(xa) attesi)"
        }
    }
}
