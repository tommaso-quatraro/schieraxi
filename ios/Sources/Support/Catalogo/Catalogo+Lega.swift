// Generato da script/testi.py: non modificare a mano.
// Testi da fanta/testi/lega.json, chiavi elencate in ios/testi/lega.txt.

extension Catalogo {
    enum Lega {
        /// `lega.voce_squadre`
        static let voceSquadre = "Squadre e rose"

        /// `lega.voce_squadre_sub`
        static let voceSquadreSub = "La tua squadra, le altre e le loro rose"

        /// `lega.voce_miasquadra`
        static let voceMiasquadra = "La mia squadra e rosa"

        /// `lega.voce_miasquadra_sub`
        static let voceMiasquadraSub = "La tua squadra e i suoi giocatori"

        /// `lega.voce_consigli`
        static let voceConsigli = "Cambi consigliati"

        /// `lega.voce_consigli_sub`
        static let voceConsigliSub = "Svincolati che migliorano la tua squadra"

        /// `lega.voce_osservati`
        static let voceOsservati = "Seguiti"

        /// `lega.voce_osservati_sub`
        static let voceOsservatiSub = "I giocatori che segui e gli avvisi quando si liberano"

        /// `lega.voce_giocatori`
        static let voceGiocatori = "Elenco dei giocatori"

        /// `lega.voce_giocatori_sub`
        static let voceGiocatoriSub = "Tutti i giocatori, con ricerca e filtri"

        /// `lega.voce_calendario`
        static let voceCalendario = "Calendario"

        /// `lega.voce_calendario_sub`
        static let voceCalendarioSub = "Le prossime partite e quanto sono facili"

        /// `lega.voce_importa`
        static let voceImporta = "Aggiorna le rose"

        /// `lega.voce_importa_sub`
        static let voceImportaSub = "Il file Excel o il testo preso da Leghe"

        /// `lega.voce_scambi`
        static let voceScambi = "Scambi"

        /// `lega.voce_scambi_sub`
        static let voceScambiSub = "Valuta un'offerta, trova o costruisci uno scambio"

        /// `lega.voce_diario`
        static let voceDiario = "Diario delle giornate"

        /// `lega.voce_diario_sub`
        static let voceDiarioSub = "La tua formazione contro quella del modello"

        /// `lega.voce_regole`
        static let voceRegole = "Regole"

        /// `lega.voce_regole_sub`
        static let voceRegoleSub = "Punteggi, modificatore difesa, moduli, panchina, rosa"

        /// `lega.voce_movimenti`
        static let voceMovimenti = "Movimenti e storico"

        /// `lega.voce_movimenti_sub`
        static let voceMovimentiSub = "Cosa è cambiato a ogni aggiornamento delle rose"

        /// `lega.voce_crediti`
        static let voceCrediti = "Crediti delle squadre"

        /// `lega.voce_crediti_sub`
        static let voceCreditiSub = "I crediti residui di ogni squadra"

        /// `lega.voce_stagione`
        static let voceStagione = "Nuova stagione"

        /// `lega.voce_stagione_sub`
        static let voceStagioneSub = "Archivia le rose e riparti"

        /// `lega.voce_novita`
        static let voceNovita = "Novità"

        /// `lega.voce_novita_sub`
        static let voceNovitaSub = "Cosa è cambiato negli ultimi aggiornamenti"

        /// `lega.mia_squadra`
        static let miaSquadra = "La mia squadra"

        /// `lega.stemma_maglia`
        static let stemmaMaglia = "Stemma e maglia"

        /// `lega.vedi_rosa`
        static let vediRosa = "Vedi la rosa"

        /// `lega.non_tua_squadra`
        static let nonTuaSquadra = "Non è la tua squadra?"

        /// `lega.scegli_quale_delle`
        static let scegliQualeDelle = "Scegli quale delle squadre è la tua."

        /// `lega.tua_squadra`
        static let tuaSquadra = "La tua squadra"

        /// `lega.tocca_una_squadra`
        static let toccaUnaSquadra = "Tocca una squadra per vedere la rosa."

        /// `lega.importa_prima_rose`
        static let importaPrimaRose = "Importa prima le rose da «Aggiorna le rose»."

        /// `lega.usa_come_stemma`
        static let usaComeStemma = "Usa come stemma"

        /// `lega.usa_come_maglia`
        static let usaComeMaglia = "Usa come maglia"

        /// `lega.indirizzo_web`
        static let indirizzoWeb = "Da indirizzo web"

        /// `lega.https`
        static let https = "https://…"

        /// `lega.esporta_rose_excel`
        static let esportaRoseExcel = "Esporta le rose in Excel da Leghe (come fai di solito) e scegli il file qui: l'app ti dice cosa è cambiato (scambi, svincolati presi, tagli, crediti)."

        /// `lega.scegli_file_excel`
        static let scegliFileExcel = "Scegli il file Excel"

        /// `lega.non_hai_file`
        static let nonHaiFile = "Se non hai il file Excel: copia la pagina delle rose di Leghe e incollala qui. Le squadre che non sono nel file restano com'erano."

        /// `lega.incolla_qui_testo`
        static let incollaQuiTesto = "Incolla qui il testo delle rose"

        /// `lega.togli_squadre_che`
        static let togliSquadreChe = "Togli le squadre che non sono nel file"

        /// `lega.importa_testo`
        static let importaTesto = "Controlla il testo"

        /// `lega.incolla_testo_delle`
        static let incollaTestoDelle = "Incolla il testo delle rose"

        /// `lega.incolla_prima_testo`
        static let incollaPrimaTesto = "Incolla prima il testo delle rose"

        /// `lega.cosa_cambiato`
        static let cosaCambiato = "Cosa è cambiato"

        /// `lega.importate`
        static func importate(n: String, nomi: String) -> String {
            "Importate: \(nomi) (\(n) in tutto)."
        }

        /// `lega.n_squadre.one`, `lega.n_squadre.other`
        static func nSquadre(_ n: Int) -> String {
            n == 1 ? "\(n) squadra" : "\(n) squadre"
        }

        /// `lega.rose_controllate_tutto`
        static let roseControllateTutto = "Rose controllate: tutto in ordine."

        /// `lega.da_controllare`
        static let daControllare = "Da controllare:"

        /// `lega.crediti_residui_ogni`
        static let creditiResiduiOgni = "Crediti residui di ogni squadra"

        /// `lega.crediti_non_salvati`
        static let creditiNonSalvati = "Ci sono crediti scritti e non ancora salvati."

        /// `lega.salva_crediti`
        static let salvaCrediti = "Salva i crediti"

        /// `lega.servono_per_consigli`
        static let servonoPerConsigli = "Servono per i consigli del mercato (rimborso e crediti dopo il cambio). Restano anche se importi di nuovo l'Excel."

        /// `lega.crediti_salvati`
        static let creditiSalvati = "Crediti salvati"

        /// `lega.rose_ancora_quelle`
        static func roseAncoraQuelle(s: String) -> String {
            "Le rose sono ancora quelle del \(s). Archivio rose, regole, scelte e seguiti e riparto da rose vuote (stessi nomi di squadra): poi importi il nuovo Excel di Leghe. Non si cancella niente."
        }

        /// `lega.archivia_riparti`
        static let archiviaRiparti = "Archivia e riparti"

        /// `lega.stagione_archiviata`
        static func stagioneArchiviata(s: String) -> String {
            "Stagione \(s) archiviata"
        }

        /// `lega.tutto_salvato_nell`
        static let tuttoSalvatoNell = "Tutto è salvato nell'archivio. Ora prepara la nuova stagione:"

        /// `lega.nuova_stagione_n`
        static func nuovaStagioneN(s: String) -> String {
            "Nuova stagione \(s)"
        }

        /// `lega.conferma_archivio`
        static func confermaArchivio(s: String) -> String {
            "Archivio la stagione \(s) e riparto da rose vuote?"
        }

        /// `lega.banner_stagione`
        static func bannerStagione(s: String) -> String {
            "Le rose sono ancora quelle del \(s): archivia e riparti."
        }

        /// `lega.importa_nuove_rose`
        static let importaNuoveRose = "Importa le nuove rose"

        /// `lega.controlla_regole`
        static let controllaRegole = "Controlla le regole"
    }
}
