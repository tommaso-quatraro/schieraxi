import Foundation

/// I testi della schermata Scambi, uguali alla web (`fanta/web/testi.js`, chiavi `scambi.*` e `scambio.*`; la web è il riferimento,
/// `docs/COERENZA-WEB-IPHONE.md`). Ogni voce ha accanto la sua chiave. Logica pura: `ScambiComeLaWebTests` li confronta con
/// `testi.js`, così una frase cambiata su un lato solo fa fallire il test.
enum TestiScambi {
    // MARK: i tre modi e «Trova per me»

    /// `scambio.cosa_vuoi_fare`
    static let cosaVuoiFare = "Cosa vuoi fare"
    /// `scambio.trova_per`, titolo del modo e del riquadro.
    static let trovaPerMe = "Trova per me"
    /// `scambio.valuta_offerta`: nome del modo e titolo del riquadro.
    static let valutaOfferta = "Valuta un'offerta"
    /// `scambio.scambi_cui_guadagnate`
    static let scambiCuiGuadagnate = "Scambi in cui guadagnate punti tutti e due: l'altro li può accettare."
    /// `scambio.con_quale_squadra`
    static let conQualeSquadra = "Con quale squadra"
    /// `scambio.tutte_squadre`
    static let tutteLeSquadre = "Tutte le squadre"
    /// `scambio.quanti_giocatori_per`
    static let quantiGiocatoriPerParte = "Quanti giocatori per parte"
    /// `scambio.uno_contro_uno`, `scambio.fino_a_2`, `scambio.fino_a_3`, `scambio.fino_a_4`
    static let unoControUno = "1 contro 1"
    static let finoA2 = "Fino a 2"
    static let finoA3 = "Fino a 3"
    static let finoA4 = "Fino a 4"
    /// `scambio.per_gli_scambi`
    static let perGliScambi = "Per gli scambi più grandi scegli una squadra: si cercano una alla volta e ci vogliono alcuni secondi."
    /// `scambio.cerca_scambi`
    static let cercaScambi = "Cerca scambi"
    /// `scambio.cerco_gli_scambi`
    static let cercoGliScambi = "Cerco gli scambi…"
    /// `scambio.nessuno_scambio_che`
    static let nessunoScambio = "Nessuno scambio che convenga a tutti e due."
    /// `scambio.servono_altre`, in due metà: il titolo e la descrizione dello stato vuoto (insieme sono la frase della web).
    static let servonoAltreRoseTitolo = "Per gli scambi servono le rose delle altre squadre."
    static let servonoAltreRoseCorpo = "Aggiungile quando vuoi: formazione e consigli funzionano già."
    static var servonoAltreRose: String { servonoAltreRoseTitolo + " " + servonoAltreRoseCorpo }

    // MARK: proposte

    /// `scambio.con` («con Gli Amici») seguito, se lo scambio non è 1 contro 1, dal formato `scambi.formato` («2 contro 1»).
    static func conSquadra(_ altra: String, dai: Int, ricevi: Int) -> String {
        let base = "con \(altra)"
        return dai > 1 || ricevi > 1 ? base + " · " + formato(dai, ricevi) : base
    }
    /// `scambi.formato`: «{n} contro {m}»
    static func formato(_ n: Int, _ m: Int) -> String { "\(n) contro \(m)" }
    /// `scambio.copia_bozza_del`
    static let copiaBozza = "Copia bozza del messaggio"
    /// `mercato.bozza_copiata`
    static let bozzaCopiata = "Bozza copiata: incollala nel gruppo o in privato"
    /// `scambio.chi_accetta_piu`
    static let chiAccettaPiu = "Chi accetta più volentieri"
    /// `scambio.squadre_che_guadagnano`
    static let squadreCheGuadagnano = "Le squadre che guadagnano di più dagli scambi qui sotto, e il reparto che ne beneficia di più."
    /// `scambio.n_scambi.one` e `.other`: «{n} scambio», «{n} scambi»
    static func nScambi(_ n: Int) -> String { n == 1 ? "\(n) scambio" : "\(n) scambi" }
    /// `scambio.migliora`: «migliora i {reparto} di {p}%»
    static func migliora(reparto: String, p: String) -> String { "migliora i \(reparto) di \(p)%" }
    /// `scambio.archivio`: «Archivio ({n})»
    static func archivio(_ n: Int) -> String { "Archivio (\(n))" }
    /// `scambio.gli_ultimi_scambi`
    static let ultimiScambi = "Gli ultimi scambi che hai analizzato."

    // MARK: «Valuta un'offerta»

    /// `scambio.incolla_messaggio_che`
    static let incollaMessaggio = "Incolla il messaggio che hai ricevuto (basta che ci siano i cognomi): trovo chi dai e chi ricevi e ti dico se conviene."
    /// `scambio.messaggio_dell_offerta`
    static let messaggioOfferta = "Messaggio dell'offerta"
    /// `scambio.valuta_offerta_2`: il pulsante
    static let valutaOffertaPulsante = "Valuta l'offerta"
    /// `scambio.incolla_prima_messaggio`
    static let incollaPrima = "Incolla prima il messaggio"
    /// `scambio.leggo_messaggio`
    static let leggoMessaggio = "Leggo il messaggio…"
    /// `scambio.riga_con`
    static let rigaCon = "Con"
    /// `scambio.ambigui`: «Più giocatori con lo stesso cognome: {nomi}. Scegli a mano in Costruisci.» (i nomi separati da «; »)
    static func ambigui(_ nomi: [String]) -> String {
        "Più giocatori con lo stesso cognome: \(nomi.joined(separator: "; ")). Scegli a mano in Costruisci."
    }
    /// `scambio.non_trovato_giocatori`
    static let nonTrovatoGiocatori = "Non ho trovato giocatori di tutte e due le squadre nel messaggio: controlla i cognomi, oppure scegli a mano in Costruisci."
    /// `scambio.scegli_mano_costruisci`: il pulsante che porta in «Costruisci».
    static let scegliAMano = "Scegli a mano in Costruisci"
    /// `scambio.vedi_giudizio_completo`
    static let vediGiudizioCompleto = "Vedi il giudizio completo"

    // MARK: «Costruisci uno scambio»

    /// `scambi.analizza_titolo`
    static let costruisciTitolo = "Costruisci uno scambio"
    /// `scambi.analizza_spiega`
    static let costruisciSpiega = "Scegli da 1 a 4 giocatori per parte, anche in numero diverso (2 contro 1, 3 contro 2…). Se vuoi, aggiungi un conguaglio in crediti."
    /// `scambi.con`
    static let scambioCon = "Scambio con"
    /// `scambi.dai` e `scambi.ricevi`
    static let dai = "Dai"
    static let ricevi = "Ricevi"
    /// `scambi.scelti`: «{n} su {max}»
    static func scelti(_ n: Int, massimo: Int) -> String { "\(n) su \(massimo)" }
    /// `scambi.massimo`: «Al massimo {max} giocatori per parte»
    static func alMassimo(_ max: Int) -> String { "Al massimo \(max) giocatori per parte" }
    /// `scambi.conguaglio` (il segno meno è quello tipografico, U+2212)
    static let conguaglio = "Conguaglio in crediti (+/−)"
    /// `scambi.conguaglio_aiuto`
    static let conguaglioAiuto = "Facoltativo. «Ricevo» = ti danno i crediti, «Pago» = li dai tu."
    /// `scambi.ricevo_crediti` e `scambi.pago_crediti`
    static let ricevoCrediti = "Ricevo"
    static let pagoCrediti = "Pago"
    /// `scambi.crediti_quanti`
    static let creditiQuanti = "Quanti crediti"
    /// `scambi.conguaglio_numero`
    static let conguaglioNumero = "Scrivi i crediti con un numero intero, per esempio 30"
    /// `scambi.analizza`: il pulsante
    static let valutaScambio = "Valuta lo scambio"
    /// `scambi.calcolo`
    static let calcolo = "Calcolo…"

    // MARK: il giudizio

    /// `scambi.chi_non_valido`
    static let cosiNonSiPuoFare = "Così non si può fare"
    /// `scambi.rose_dopo`
    static let roseDopo = "Giocatori in rosa dopo lo scambio"
    /// `scambi.formazione_migliore_una` con una giornata sola, `scambi.formazione_migliore` («… (prossime {n} giornate)») con più.
    /// Senza il numero delle giornate (server vecchio) resta la parte che sta in tutte e due.
    static func formazioneMigliore(giornate: Int) -> String {
        switch giornate {
        case 1: return "Formazione migliore (prossima giornata)"
        case 2...: return "Formazione migliore (prossime \(giornate) giornate)"
        default: return "Formazione migliore"
        }
    }
    /// `scambi.panchina`
    static let panchina = "Panchina"
    /// `scambi.in_stagione`
    static let inStagione = "Punti attesi in stagione"
    /// `scambi.tu`
    static let tu = "Tu"
    /// `scambi.crediti_titolo`
    static let crediti = "Crediti"
    /// `scambio.impatto_sulla_tua`
    static let impatto = "Impatto sulla tua rosa"
    /// `scambio.conta_anche_resto`
    static let contaAncheResto = "Conta anche il resto della squadra: se il reparto è già forte, un nuovo arrivato fa meno differenza."
    /// `scambio.in_totale.one` («In totale (prossima giornata)») e `.other` («In totale (prossime {n} giornate)»)
    static func inTotale(giornate: Int) -> String {
        giornate == 1 ? "In totale (prossima giornata)" : "In totale (prossime \(giornate) giornate)"
    }
}
