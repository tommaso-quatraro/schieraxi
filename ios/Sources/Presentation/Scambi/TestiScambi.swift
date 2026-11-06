import Foundation

/// I testi della schermata Scambi, uguali alla web (`fanta/web/testi.js`, chiavi `scambi.*` e `scambio.*`; la web è il riferimento,
/// `docs/COERENZA-WEB-IPHONE.md`). Ogni voce ha accanto la sua chiave. Logica pura: `ScambiComeLaWebTests` li confronta con
/// `testi.js`, così una frase cambiata su un lato solo fa fallire il test.
enum TestiScambi {
    // MARK: i tre modi e «Trova per me»

    /// `scambio.cosa_vuoi_fare`
    static let cosaVuoiFare = ""
    /// `scambio.trova_per`, titolo del modo e del riquadro.
    static let trovaPerMe = ""
    /// `scambio.costruisci`
    static let costruisci = ""
    /// `scambio.valuta_offerta`: nome del modo e titolo del riquadro.
    static let valutaOfferta = ""
    /// `scambio.scambi_cui_guadagnate`
    static let scambiCuiGuadagnate = ""
    /// `scambio.con_quale_squadra`
    static let conQualeSquadra = ""
    /// `scambio.tutte_squadre`
    static let tutteLeSquadre = ""
    /// `scambio.quanti_giocatori_per`
    static let quantiGiocatoriPerParte = ""
    /// `scambio.uno_contro_uno`, `scambio.fino_a_2`, `scambio.fino_a_3`, `scambio.fino_a_4`
    static let unoControUno = ""
    static let finoA2 = ""
    static let finoA3 = ""
    static let finoA4 = ""
    /// `scambio.per_gli_scambi`
    static let perGliScambi = ""
    /// `scambio.cerca_scambi`
    static let cercaScambi = ""
    /// `scambio.cerco_gli_scambi`
    static let cercoGliScambi = ""
    /// `scambio.nessuno_scambio_che`
    static let nessunoScambio = ""
    /// `scambio.servono_altre`, in due metà: il titolo e la descrizione dello stato vuoto (insieme sono la frase della web).
    static let servonoAltreRoseTitolo = ""
    static let servonoAltreRoseCorpo = ""
    static var servonoAltreRose: String { servonoAltreRoseTitolo + " " + servonoAltreRoseCorpo }

    // MARK: proposte

    /// `scambio.con` («con Gli Amici») seguito, se lo scambio non è 1 contro 1, dal formato `scambi.formato` («2 contro 1»).
    static func conSquadra(_ altra: String, dai: Int, ricevi: Int) -> String { "" }
    /// `scambi.formato`: «{n} contro {m}»
    static func formato(_ n: Int, _ m: Int) -> String { "" }
    /// `scambio.copia_bozza_del`
    static let copiaBozza = ""
    /// `mercato.bozza_copiata`
    static let bozzaCopiata = ""
    /// `scambio.chi_accetta_piu`
    static let chiAccettaPiu = ""
    /// `scambio.squadre_che_guadagnano`
    static let squadreCheGuadagnano = ""
    /// `scambio.n_scambi.one` e `.other`: «{n} scambio», «{n} scambi»
    static func nScambi(_ n: Int) -> String { "" }
    /// `scambio.migliora`: «migliora i {reparto} di {p}%»
    static func migliora(reparto: String, p: String) -> String { "" }
    /// `scambio.archivio`: «Archivio ({n})»
    static func archivio(_ n: Int) -> String { "" }
    /// `scambio.gli_ultimi_scambi`
    static let ultimiScambi = ""

    // MARK: «Valuta un'offerta»

    /// `scambio.incolla_messaggio_che`
    static let incollaMessaggio = ""
    /// `scambio.messaggio_dell_offerta`
    static let messaggioOfferta = ""
    /// `scambio.valuta_offerta_2`: il pulsante
    static let valutaOffertaPulsante = ""
    /// `scambio.incolla_prima_messaggio`
    static let incollaPrima = ""
    /// `scambio.leggo_messaggio`
    static let leggoMessaggio = ""
    /// `scambio.riga_con`
    static let rigaCon = ""
    /// `scambio.ambigui`: «Più giocatori con lo stesso cognome: {nomi}. Scegli a mano in Costruisci.» (i nomi separati da «; »)
    static func ambigui(_ nomi: [String]) -> String { "" }
    /// `scambio.non_trovato_giocatori`
    static let nonTrovatoGiocatori = ""
    /// `scambio.scegli_mano_costruisci`: il pulsante che porta in «Costruisci».
    static let scegliAMano = ""
    /// `scambio.vedi_giudizio_completo`
    static let vediGiudizioCompleto = ""

    // MARK: «Costruisci uno scambio»

    /// `scambi.analizza_titolo`
    static let costruisciTitolo = ""
    /// `scambi.analizza_spiega`
    static let costruisciSpiega = ""
    /// `scambi.con`
    static let scambioCon = ""
    /// `scambi.dai` e `scambi.ricevi`
    static let dai = ""
    static let ricevi = ""
    /// `scambi.scelti`: «{n} su {max}»
    static func scelti(_ n: Int, massimo: Int) -> String { "" }
    /// `scambi.massimo`: «Al massimo {max} giocatori per parte»
    static func alMassimo(_ max: Int) -> String { "" }
    /// `scambi.conguaglio` (il segno meno è quello tipografico, U+2212)
    static let conguaglio = ""
    /// `scambi.conguaglio_aiuto`
    static let conguaglioAiuto = ""
    /// `scambi.ricevo_crediti` e `scambi.pago_crediti`
    static let ricevoCrediti = ""
    static let pagoCrediti = ""
    /// `scambi.crediti_quanti`
    static let creditiQuanti = ""
    /// `scambi.conguaglio_numero`
    static let conguaglioNumero = ""
    /// `scambi.analizza`: il pulsante
    static let valutaScambio = ""
    /// `scambi.calcolo`
    static let calcolo = ""

    // MARK: il giudizio

    /// `scambi.chi_non_valido`
    static let cosiNonSiPuoFare = ""
    /// `scambi.rose_dopo`
    static let roseDopo = ""
    /// `scambi.formazione_migliore_una` con una giornata sola, `scambi.formazione_migliore` («… (prossime {n} giornate)») con più.
    /// Senza il numero delle giornate (server vecchio) resta la parte che sta in tutte e due.
    static func formazioneMigliore(giornate: Int) -> String { "" }
    /// `scambi.panchina`
    static let panchina = ""
    /// `scambi.in_stagione`
    static let inStagione = ""
    /// `scambi.tu`
    static let tu = ""
    /// `scambi.crediti_titolo`
    static let crediti = ""
    /// `scambio.impatto_sulla_tua`
    static let impatto = ""
    /// `scambio.conta_anche_resto`
    static let contaAncheResto = ""
    /// `scambio.in_totale.one` («In totale (prossima giornata)») e `.other` («In totale (prossime {n} giornate)»)
    static func inTotale(giornate: Int) -> String { "" }
}
