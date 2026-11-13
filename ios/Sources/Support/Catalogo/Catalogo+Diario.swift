// Generato da script/testi.py: non modificare a mano.
// Testi da fanta/testi/diario.json, chiavi elencate in ios/testi/diario.txt.

extension Catalogo {
    enum Diario {
        /// `diario.salvata_manuale`
        static let salvataManuale = "Salvato: ho segnato i tuoi undici della giornata"

        /// `diario.cosa_hai_schierato_titolo`
        static let cosaHaiSchieratoTitolo = "Cosa hai schierato"

        /// `diario.correggi_spiega`
        static func correggiSpiega(g: String) -> String {
            "\(g): tocca i giocatori che hai schierato. Servono 11 titolari."
        }

        /// `diario.salvata`
        static let salvata = "Salvato: ho segnato che hai schierato la consigliata"

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

        /// `diario.la_consigliata`
        static func laConsigliata(modulo: String) -> String {
            "La consigliata (\(modulo))"
        }

        /// `diario.af_titolo`
        static let afTitolo = "Quanto ci abbiamo preso"

        /// `diario.qp_intro`
        static let qpIntro = "Le giornate finite confrontate con quello che SchieraXI si aspettava. Lo mostriamo anche quando va male."

        /// `diario.qp_su.one`, `diario.qp_su.other`
        static func qpSu(_ n: Int, a: String, da: String) -> String {
            n == 1 ? "Calcolato su 1 giornata (la \(da))." : "Calcolato su \(n) giornate, dalla \(da) alla \(a)."
        }

        /// `diario.qp_pochi`
        static func qpPochi(n: String) -> String {
            "Ancora pochi dati: servono almeno \(n) giornate perché questi numeri siano affidabili. Per ora possono cambiare molto."
        }

        /// `diario.qp_fv_eti`
        static let qpFvEti = "punti di errore medio del fantavoto atteso"

        /// `diario.qp_fv`
        static func qpFv(e: String, k: String) -> String {
            "In media il fantavoto atteso dei tuoi giocatori sbaglia di \(e) punti; \(k) voti su 10 sono entro un punto."
        }

        /// `diario.qp_fv_voti.one`, `diario.qp_fv_voti.other`
        static func qpFvVoti(_ n: Int) -> String {
            n == 1 ? "Su 1 voto." : "Su \(n) voti."
        }

        /// `diario.qp_fv_piu`
        static func qpFvPiu(e: String) -> String {
            "In media hanno fatto \(e) in più del previsto."
        }

        /// `diario.qp_fv_meno`
        static func qpFvMeno(e: String) -> String {
            "In media hanno fatto \(e) in meno del previsto."
        }

        /// `diario.qp_fv_vuoto`
        static let qpFvVuoto = "Ancora niente da confrontare."

        /// `diario.qp_gioca_eti`
        static let qpGiocaEti = "hanno giocato davvero, quando diciamo che giocano"

        /// `diario.qp_su_dieci`
        static func qpSuDieci(k: String) -> String {
            "\(k) su 10"
        }

        /// `diario.qp_gioca`
        static func qpGioca(k: String, p: String) -> String {
            "Quando diciamo «gioca \(p)%», ha giocato \(k) volte su 10."
        }

        /// `diario.qp_gioca_ric`
        static func qpGiocaRic(al: String, k: String) -> String {
            "Con i dati disponibili prima di ogni giornata (senza le probabili formazioni), chi davamo \(al) ha giocato \(k) volte su 10."
        }

        /// `diario.qp_gioca_ottimisti`
        static let qpGiocaOttimisti = "Qui siamo stati troppo ottimisti."

        /// `diario.qp_gioca_prudenti`
        static let qpGiocaPrudenti = "Qui siamo stati troppo prudenti."

        /// `diario.qp_gioca_tutte`
        static let qpGiocaTutte = "Tutte le fasce"

        /// `diario.qp_gioca_fascia`
        static func qpGiocaFascia(a: String, d: String, da: String, g: String) -> String {
            "Gioca \(da)-\(a)%: dicevamo \(d)%, hanno giocato nel \(g)% dei casi"
        }

        /// `diario.qp_giocatori.one`, `diario.qp_giocatori.other`
        static func qpGiocatori(_ n: Int) -> String {
            n == 1 ? "1 caso" : "\(n) casi"
        }

        /// `diario.qp_pochi_casi`
        static let qpPochiCasi = "pochi per dirlo"

        /// `diario.qp_cf_eti`
        static let qpCfEti = "giornate in cui la consigliata ha fatto meglio della tua"

        /// `diario.qp_k_su_n`
        static func qpKSuN(k: String, n: String) -> String {
            "\(k) su \(n)"
        }

        /// `diario.qp_cf`
        static func qpCf(k: String, n: String, pari: String, tua: String) -> String {
            "Giornate in cui la consigliata ha fatto meglio della tua: \(k) su \(n). Meglio la tua: \(tua). Pari: \(pari)."
        }

        /// `diario.qp_cf_piu.one`, `diario.qp_cf_piu.other`
        static func qpCfPiu(_ n: Int, e: String) -> String {
            n == 1 ? "Seguendo sempre la consigliata avresti fatto \(e) punto in più." : "Seguendo sempre la consigliata avresti fatto \(e) punti in più."
        }

        /// `diario.qp_cf_meno.one`, `diario.qp_cf_meno.other`
        static func qpCfMeno(_ n: Int, e: String) -> String {
            n == 1 ? "Con le tue scelte hai fatto \(e) punto in più della consigliata." : "Con le tue scelte hai fatto \(e) punti in più della consigliata."
        }

        /// `diario.qp_cf_pari`
        static let qpCfPari = "In tutto, gli stessi punti."

        /// `diario.qp_sq_eti`
        static let qpSqEti = "punti di scarto medio sulla squadra"

        /// `diario.qp_sq`
        static func qpSq(a: String, d: String, f: String, k: String, n: String) -> String {
            "Punti della consigliata: \(a) previsti e \(f) fatti, in media. Giornate dentro la fascia prevista: \(k) su \(n) (puntiamo a \(d) su 10)."
        }

        /// `diario.qp_grafico_aria`
        static let qpGraficoAria = "Errore medio del fantavoto atteso, giornata per giornata"

        /// `diario.qp_grafico_leg`
        static let qpGraficoLeg = "Di quanto ha sbagliato in media il fantavoto atteso in ogni giornata: più bassa è la barra, meglio è."

        /// `diario.qp_andamento`
        static let qpAndamento = "Giornata per giornata"

        /// `diario.qp_riga_fv`
        static func qpRigaFv(e: String) -> String {
            "fantavoto: errore \(e)"
        }

        /// `diario.qp_riga_sq`
        static func qpRigaSq(a: String, f: String) -> String {
            "squadra: \(a) previsti, \(f) fatti"
        }

        /// `diario.qp_ricostruiti.one`, `diario.qp_ricostruiti.other`
        static func qpRicostruiti(_ n: Int, t: String) -> String {
            n == 1 ? "In 1 giornata su \(t) i numeri dei giocatori sono ricostruiti con i dati che c'erano prima: quelli mostrati allora non erano stati salvati." : "In \(n) giornate su \(t) i numeri dei giocatori sono ricostruiti con i dati che c'erano prima: quelli mostrati allora non erano stati salvati."
        }
    }
}
