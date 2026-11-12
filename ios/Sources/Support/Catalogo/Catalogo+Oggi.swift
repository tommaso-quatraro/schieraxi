// Generato da script/testi.py: non modificare a mano.
// Testi da fanta/testi/oggi.json, chiavi elencate in ios/testi/oggi.txt.

extension Catalogo {
    enum Oggi {
        /// `oggi.benvenuto_schieraxi`
        static let benvenutoSchieraxi = "Benvenuto in SchieraXI"

        /// `oggi.per_cominciare_importa`
        static let perCominciareImporta = "Per cominciare importa le rose della tua lega: poi ti dico ogni giornata chi schierare."

        /// `oggi.chiusa`
        static let chiusa = "Chiusa"

        /// `oggi.chiusa_dettaglio`
        static func chiusaDettaglio(quando: String) -> String {
            "La formazione si è chiusa \(quando)"
        }

        /// `oggi.giorni_ore.one`, `oggi.giorni_ore.other`
        static func giorniOre(_ n: Int, h: String) -> String {
            n == 1 ? "\(n) giorno \(h) h" : "\(n) giorni \(h) h"
        }

        /// `oggi.si_chiude`
        static func siChiude(min: String, quando: String) -> String {
            "La formazione si chiude \(quando) (\(min) min prima della prima partita)"
        }

        /// `oggi.prima_partita`
        static func primaPartita(quando: String) -> String {
            "Prima partita \(quando): la formazione va inserita prima"
        }

        /// `oggi.preparo`
        static let preparo = "Preparo la giornata…"

        /// `oggi.tua_formazione`
        static let tuaFormazione = "La tua formazione"

        /// `oggi.tua_formazione_scelta`
        static let tuaFormazioneScelta = "La tua formazione · la tua scelta"

        /// `oggi.punti_attesi`
        static let puntiAttesi = "punti attesi"

        /// `oggi.apri_formazione`
        static let apriFormazione = "Apri la formazione"

        /// `oggi.mancano_probabili_formazioni`
        static let mancanoProbabiliFormazioni = "Mancano le probabili formazioni di questa giornata: i consigli usano le presenze recenti."

        /// `oggi.tuoi_migliori_della`
        static let tuoiMiglioriDella = "I tuoi migliori della giornata"

        /// `oggi.da_controllare`
        static let daControllare = "Da controllare"

        /// `oggi.giocatori_formazione_con`
        static let giocatoriFormazioneCon = "Giocatori in formazione con qualche dubbio: riguarda le probabili prima della partita."

        /// `oggi.indisponibili`
        static func indisponibili(n: String) -> String {
            "Indisponibili in rosa (\(n))"
        }

        /// `oggi.diffidati`
        static let diffidati = "Diffidati"

        /// `oggi.data_da_definire`
        static let dataDaDefinire = "Data da definire"

        /// `oggi.calendario_no`
        static let calendarioNo = "Calendario non disponibile"

        /// `oggi.punti_finora`
        static let puntiFinora = "Punti fatti finora"

        /// `oggi.a_fine_giornata`
        static let aFineGiornata = "A fine giornata"

        /// `oggi.attesi_prima`
        static func attesiPrima(n: String) -> String {
            "attesi prima: \(n)"
        }

        /// `oggi.ancora_da_giocare.one`, `oggi.ancora_da_giocare.other`
        static func ancoraDaGiocare(_ n: Int) -> String {
            n == 1 ? "\(n) giocatore deve ancora giocare" : "\(n) giocatori devono ancora giocare"
        }

        /// `oggi.tutti_giocato`
        static let tuttiGiocato = "Hanno giocato tutti: mancano solo i voti ufficiali."

        /// `oggi.dalla_panchina`
        static let dallaPanchina = "entrato dalla panchina"

        /// `oggi.st_da_giocare`
        static let stDaGiocare = "Da giocare"

        /// `oggi.st_senza_voto`
        static let stSenzaVoto = "Senza voto"

        /// `oggi.st_attesa_voti`
        static let stAttesaVoti = "Voto in arrivo"

        /// `oggi.st_in_corso`
        static let stInCorso = "Partita in corso"

        /// `oggi.st_rinviata`
        static let stRinviata = "Rinviata"

        /// `oggi.cambi_panchina`
        static let cambiPanchina = "Cambi dalla panchina"

        /// `oggi.cambio_fatto`
        static let cambioFatto = "già fatto"

        /// `oggi.cambio_probabile`
        static let cambioProbabile = "probabile"

        /// `oggi.nessun_sostituto`
        static let nessunSostituto = "nessun sostituto"

        /// `oggi.giornata_finita`
        static func giornataFinita(g: String) -> String {
            "\(g): finita"
        }

        /// `oggi.la_tua_formazione`
        static let laTuaFormazione = "La tua formazione"

        /// `oggi.la_consigliata`
        static let laConsigliata = "La consigliata"

        /// `oggi.punti_fatti`
        static let puntiFatti = "punti fatti"

        /// `oggi.con_consigliata`
        static func conConsigliata(attesi: String, fatti: String) -> String {
            "Con la consigliata: \(fatti) punti (\(attesi) attesi)."
        }

        /// `oggi.confronto_in_arrivo`
        static let confrontoInArrivo = "Il confronto con la consigliata arriva nel Diario."

        /// `oggi.apri_diario`
        static let apriDiario = "Apri il Diario"

        /// `oggi.prossima_chiude`
        static func prossimaChiude(g: String, quando: String) -> String {
            "\(g): la formazione si chiude \(quando)."
        }

        /// `oggi.prossima_pronta`
        static let prossimaPronta = "Puoi già prepararla."

        /// `oggi.prossima_da`
        static func prossimaDa(quando: String) -> String {
            "Conviene prepararla da \(quando), quando escono le probabili formazioni."
        }

        /// `oggi.gia_iniziata`
        static let giaIniziata = "Questa giornata è già iniziata"

        /// `oggi.gia_iniziata_testo`
        static let giaIniziataTesto = "Sei arrivato a partite cominciate: questa la guardi e basta. Prepara la prossima."

        /// `oggi.prepara_prossima`
        static let preparaProssima = "Prepara la prossima"

        /// `oggi.rinvio_titolo_1`
        static let rinvioTitolo1 = "Partita rinviata"

        /// `oggi.rinvio_titolo_n`
        static let rinvioTitoloN = "Partite rinviate"

        /// `oggi.rinvio_recupero`
        static func rinvioRecupero(quando: String) -> String {
            "recupero \(quando)"
        }

        /// `oggi.rinvio_da_definire`
        static let rinvioDaDefinire = "recupero da definire"

        /// `oggi.rinvio_miei`
        static func rinvioMiei(nomi: String) -> String {
            "I tuoi giocatori coinvolti: \(nomi)"
        }

        /// `oggi.rinvio_domanda`
        static let rinvioDomanda = "Per questa giornata i loro giocatori"

        /// `oggi.rinvio_aspetta`
        static let rinvioAspetta = "aspettano il recupero (conta il suo voto)"

        /// `oggi.rinvio_senza_voto`
        static let rinvioSenzaVoto = "restano senza voto (entra la riserva)"

        /// `oggi.rinvio_ufficio`
        static func rinvioUfficio(v: String) -> String {
            "prendono il voto d'ufficio (\(v))"
        }

        /// `oggi.rinvio_eccezione`
        static func rinvioEccezione(regola: String) -> String {
            "Scelta solo per questa giornata. Di solito la tua lega: \(regola)."
        }

        /// `oggi.rinvio_salvato`
        static let rinvioSalvato = "Fatto: consigli aggiornati per questa giornata"

        /// `oggi.recupero_manca`
        static func recuperoManca(partite: String) -> String {
            "Manca il recupero di \(partite): i punti possono ancora cambiare."
        }

        /// `oggi.infortunato`
        static let infortunato = "Infortunato"

        /// `oggi.squalificato`
        static let squalificato = "Squalificato"

        /// `oggi.diffidato_tipo`
        static let diffidatoTipo = "Diffidato"
    }
}
