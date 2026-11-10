// Generato da script/testi.py: non modificare a mano.
// Testi da fanta/testi/regole.json, chiavi elencate in ios/testi/regole.txt.

extension Catalogo {
    enum Regole {
        /// `regole.prova`
        static let prova = "Prova"

        /// `regole.voti_portiere_difensori`
        static let votiPortiereDifensori = "Voti: portiere e 3 difensori"

        /// `regole.aggiungi_fascia`
        static let aggiungiFascia = "+ Aggiungi fascia"

        /// `regole.media_bonus.one`, `regole.media_bonus.other`
        static func mediaBonus(_ n: Int, b: String, m: String) -> String {
            n == 1 ? "Media \(m) bonus \(b) punto" : "Media \(m) bonus \(b) punti"
        }

        /// `regole.fascia_media`
        static func fasciaMedia(n: String) -> String {
            "Fascia \(n), media almeno"
        }

        /// `regole.fascia_bonus`
        static func fasciaBonus(n: String) -> String {
            "Fascia \(n), bonus"
        }

        /// `regole.togli_fascia`
        static func togliFascia(n: String) -> String {
            "Togli la fascia \(n)"
        }

        /// `regole.voto_portiere`
        static let votoPortiere = "Voto del portiere"

        /// `regole.voto_difensore`
        static func votoDifensore(n: String) -> String {
            "Voto del difensore \(n)"
        }

        /// `regole.posti_fissi`
        static let postiFissi = "Posti fissi per ruolo"

        /// `regole.posti_fissi_aiuto`
        static let postiFissiAiuto = "La panchina ha un numero preciso di posti per ogni ruolo"

        /// `regole.cambio_modulo`
        static let cambioModulo = "Cambio modulo nelle sostituzioni"

        /// `regole.cambio_modulo_aiuto`
        static let cambioModuloAiuto = "Una riserva di un altro ruolo può entrare se il modulo resta valido"

        /// `regole.scadenza`
        static let scadenza = "Scadenza della formazione"

        /// `regole.scadenza_aiuto`
        static let scadenzaAiuto = "minuti prima della prima partita della giornata (0 = all'inizio)"

        /// `regole.prima_giornata`
        static let primaGiornata = "Prima giornata della lega"

        /// `regole.prima_giornata_aiuto`
        static let primaGiornataAiuto = "la giornata di Serie A da cui parte la lega (1 se è partita con il campionato)"

        /// `regole.con_prima_giornata`
        static let conPrimaGiornata = "Con la prima giornata a 4, la giornata 1 della lega è la 4ª di Serie A: calendario, Diario e promemoria contano da lì."

        /// `regole.nome_della_lega`
        static let nomeDellaLega = "Nome della lega"

        /// `regole.mia_lega`
        static let miaLega = "La mia lega"

        /// `regole.importa_leghe`
        static let importaLeghe = "Importa da Leghe"

        /// `regole.leghe_apri_regolamento`
        static let legheApriRegolamento = "Su Leghe apri il regolamento della competizione, copia il testo e incollalo qui: l'app riconosce i valori e te li mostra prima di applicarli. Non cambia nulla finché non tocchi «Salva le regole»."

        /// `regole.riconosci_regole`
        static let riconosciRegole = "Riconosci le regole"

        /// `regole.incolla_prima_testo`
        static let incollaPrimaTesto = "Incolla prima il testo del regolamento"

        /// `regole.non_riconosciuto_nessuna`
        static let nonRiconosciutoNessuna = "Non ho riconosciuto nessuna regola in questo testo. Controlla di aver copiato la pagina del regolamento, oppure imposta i valori a mano qui sotto."

        /// `regole.riconosciuto`
        static let riconosciuto = "Riconosciuto"

        /// `regole.da_riga`
        static func daRiga(r: String) -> String {
            "da: «\(r)»"
        }

        /// `regole.non_riconosciute`
        static func nonRiconosciute(n: String) -> String {
            "Righe con numeri non riconosciute (\(n))"
        }

        /// `regole.applica_campi`
        static let applicaCampi = "Applica ai campi"

        /// `regole.controlla_valori_qui`
        static let controllaValoriQui = "Controlla i valori qui sotto e tocca «Salva le regole» in fondo."

        /// `regole.valori_applicati_controlla`
        static let valoriApplicatiControlla = "Valori applicati: controlla e tocca «Salva le regole»"

        /// `regole.gol_di`
        static func golDi(ruolo: String) -> String {
            "Gol di un \(ruolo)"
        }

        /// `regole.altri_bonus`
        static let altriBonus = "Altri bonus"

        /// `regole.rigore_parato_p`
        static let rigoreParatoP = "Rigore parato (portiere)"

        /// `regole.malus`
        static let malus = "Malus"

        /// `regole.per_ogni_gol`
        static let perOgniGol = "per ogni gol"

        /// `regole.voto_partenza`
        static let votoPartenza = "Voto di partenza"

        /// `regole.v_redazione`
        static let vRedazione = "Redazione"

        /// `regole.v_statistico`
        static let vStatistico = "Statistico"

        /// `regole.v_italia`
        static let vItalia = "Italia"

        /// `regole.quale_voto_somma`
        static let qualeVotoSomma = "Quale voto si somma a bonus e malus: quello che usa la tua lega su Leghe."

        /// `regole.modificatore_difesa`
        static let modificatoreDifesa = "Modificatore difesa"

        /// `regole.md_attivo`
        static let mdAttivo = "Attivo nella mia lega"

        /// `regole.md_attivo_aiuto`
        static let mdAttivoAiuto = "Un bonus se la difesa prende voti alti"

        /// `regole.md_min`
        static let mdMin = "Difensori minimi in campo"

        /// `regole.md_min_aiuto`
        static let mdMinAiuto = "sotto questo numero non si applica"

        /// `regole.media_almeno`
        static let mediaAlmeno = "Media almeno"

        /// `regole.bonus`
        static let bonus = "bonus"

        /// `regole.moduli_ammessi`
        static let moduliAmmessi = "Moduli ammessi"

        /// `regole.quelli_che_puoi`
        static let quelliChePuoi = "Quelli che puoi schierare nella tua lega."

        /// `regole.panchina_sostituzioni`
        static let panchinaSostituzioni = "Panchina e sostituzioni"

        /// `regole.giocatori_panchina`
        static let giocatoriPanchina = "Giocatori in panchina"

        /// `regole.cambi_massimi`
        static let cambiMassimi = "Cambi massimi"

        /// `regole.come_entrano_riserve`
        static let comeEntranoRiserve = "Come entrano le riserve"

        /// `regole.per_ruolo`
        static let perRuolo = "Per ruolo"

        /// `regole.libera`
        static let libera = "Libera"

        /// `regole.aiuto_libera`
        static let aiutoLibera = "Libera: entra il primo della panchina che può sostituirlo, anche di un ruolo diverso se il modulo resta valido."

        /// `regole.aiuto_per_ruolo`
        static let aiutoPerRuolo = "Per ruolo: se un titolare non gioca, entra il primo della panchina dello stesso ruolo."

        /// `regole.vu_se_manca`
        static let vuSeManca = "Voto d'ufficio se manca il sostituto"

        /// `regole.vu`
        static let vu = "Voto d'ufficio"

        /// `regole.rv_voto`
        static let rvVoto = "Voto d'ufficio"

        /// `regole.rosa_crediti`
        static let rosaCrediti = "Rosa e crediti"

        /// `regole.crediti_iniziali`
        static let creditiIniziali = "Crediti iniziali"

        /// `regole.tempi_della_lega`
        static let tempiDellaLega = "Tempi della lega"

        /// `regole.agg_vicini`
        static let aggVicini = "Aggiornamenti più fitti vicino alla scadenza"

        /// `regole.agg_vicini_aiuto`
        static let aggViciniAiuto = "Probabili e infortuni riletti a 60, 30 e 15 minuti dalla scadenza, con avviso se cambia qualcosa"

        /// `regole.salva_regole`
        static let salvaRegole = "Salva le regole"

        /// `regole.annulla_modifiche`
        static let annullaModifiche = "Annulla le modifiche"

        /// `regole.regole_salvate_consigli`
        static let regoleSalvateConsigli = "Regole salvate: i consigli ora le usano"

        /// `regole.nuovo`
        static let nuovo = "Nuovo"

        /// `regole.rinviate`
        static let rinviate = "Partite rinviate"

        /// `regole.rinviate_aiuto`
        static let rinviateAiuto = "Cosa fa la lega con i giocatori di una partita rinviata, anche a settimane dopo. Per una sola giornata puoi cambiarlo da Oggi."

        /// `regole.rv_aspetta`
        static let rvAspetta = "Aspetta il recupero"

        /// `regole.rv_senza_voto`
        static let rvSenzaVoto = "Senza voto"

        /// `regole.rv_ufficio`
        static let rvUfficio = "Voto d'ufficio"

        /// `regole.rv_aiuto_aspetta`
        static let rvAiutoAspetta = "Si aspetta il recupero e conta il voto preso lì: i giocatori restano schierabili."

        /// `regole.rv_aiuto_senza_voto`
        static let rvAiutoSenzaVoto = "I giocatori restano senza voto: entra la riserva."

        /// `regole.rv_aiuto_voto_ufficio`
        static let rvAiutoVotoUfficio = "Tutti prendono lo stesso voto, senza bonus né malus."
    }
}
