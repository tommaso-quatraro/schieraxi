import Foundation

/// I testi della schermata Scambi, uguali alla web: vengono dal catalogo comune (`fanta/testi/scambi.json` e `scambio.json`, chiavi
/// elencate in `ios/testi/`, file generati `Catalogo+Scambi.swift` e `Catalogo+Scambio.swift`). Qui restano i nomi che usano le
/// viste e le frasi composte (numeri, nomi, una frase divisa in due). `SquadraAltroDalCatalogoTests` controlla che nessun testo del
/// catalogo sia riscritto qui, `ScambiComeLaWebTests` le frasi composte.
enum TestiScambi {
    // MARK: i tre modi e «Trova per me»

    static let cosaVuoiFare = Catalogo.Scambio.cosaVuoiFare
    /// Titolo del modo e del riquadro.
    static let trovaPerMe = Catalogo.Scambio.trovaPer
    /// Nome del modo e titolo del riquadro.
    static let valutaOfferta = Catalogo.Scambio.valutaOfferta
    static let scambiCuiGuadagnate = Catalogo.Scambio.scambiCuiGuadagnate
    static let conQualeSquadra = Catalogo.Scambio.conQualeSquadra
    static let tutteLeSquadre = Catalogo.Scambio.tutteSquadre
    static let quantiGiocatoriPerParte = Catalogo.Scambio.quantiGiocatoriPer
    static let unoControUno = Catalogo.Scambio.unoControUno
    static let finoA2 = Catalogo.Scambio.finoA2
    static let finoA3 = Catalogo.Scambio.finoA3
    static let finoA4 = Catalogo.Scambio.finoA4
    static let perGliScambi = Catalogo.Scambio.perGliScambi
    static let cercaScambi = Catalogo.Scambio.cercaScambi
    static let cercoGliScambi = Catalogo.Scambio.cercoGliScambi
    static let nessunoScambio = Catalogo.Scambio.nessunoScambioChe
    /// La frase della web (`scambio.servono_altre`) in due metà: il titolo e la descrizione dello stato vuoto.
    static var servonoAltreRoseTitolo: String { inDue(servonoAltreRose).titolo }
    static var servonoAltreRoseCorpo: String { inDue(servonoAltreRose).corpo }
    static let servonoAltreRose = Catalogo.Scambio.servonoAltre

    /// Una frase divisa dopo il primo punto: «Prima frase.» e il resto; senza punto tutta nel titolo.
    static func inDue(_ frase: String) -> (titolo: String, corpo: String) {
        guard let punto = frase.range(of: ". ") else { return (frase, "") }
        return (String(frase[..<punto.lowerBound]) + ".", String(frase[punto.upperBound...]))
    }

    // MARK: proposte

    /// «con Gli Amici» seguito, se lo scambio non è 1 contro 1, dal formato «2 contro 1».
    static func conSquadra(_ altra: String, dai: Int, ricevi: Int) -> String {
        let base = Catalogo.Scambio.con + " " + altra
        return dai > 1 || ricevi > 1 ? base + " · " + formato(dai, ricevi) : base
    }
    /// «2 contro 1».
    static func formato(_ n: Int, _ m: Int) -> String { Catalogo.Scambi.formato(m: String(m), n: String(n)) }
    static let copiaBozza = Catalogo.Scambio.copiaBozzaDel
    static let bozzaCopiata = Catalogo.Mercato.bozzaCopiata
    static let chiAccettaPiu = Catalogo.Scambio.chiAccettaPiu
    static let squadreCheGuadagnano = Catalogo.Scambio.squadreCheGuadagnano
    /// «1 scambio», «3 scambi».
    static func nScambi(_ n: Int) -> String { Catalogo.Scambio.nScambi(n) }
    /// «migliora i portieri di +2,1%».
    static func migliora(reparto: String, p: String) -> String { Catalogo.Scambio.migliora(p: p, reparto: reparto) }
    /// «Archivio (5)».
    static func archivio(_ n: Int) -> String { Catalogo.Scambio.archivio(n: String(n)) }
    static let ultimiScambi = Catalogo.Scambio.gliUltimiScambi

    // MARK: «Valuta un'offerta»

    static let incollaMessaggio = Catalogo.Scambio.incollaMessaggioChe
    static let messaggioOfferta = Catalogo.Scambio.messaggioDellOfferta
    /// Il pulsante.
    static let valutaOffertaPulsante = Catalogo.Scambio.valutaOfferta2
    static let incollaPrima = Catalogo.Scambio.incollaPrimaMessaggio
    static let leggoMessaggio = Catalogo.Scambio.leggoMessaggio
    static let rigaCon = Catalogo.Scambio.rigaCon
    /// «Più giocatori con lo stesso cognome: …. Scegli a mano in Costruisci.», i nomi separati da «; ».
    static func ambigui(_ nomi: [String]) -> String { Catalogo.Scambio.ambigui(nomi: nomi.joined(separator: "; ")) }
    static let nonTrovatoGiocatori = Catalogo.Scambio.nonTrovatoGiocatori
    /// Il pulsante che porta in «Costruisci».
    static let scegliAMano = Catalogo.Scambio.scegliManoCostruisci
    static let vediGiudizioCompleto = Catalogo.Scambio.vediGiudizioCompleto

    // MARK: «Costruisci uno scambio»

    static let costruisciTitolo = Catalogo.Scambi.analizzaTitolo
    static let costruisciSpiega = Catalogo.Scambi.analizzaSpiega
    static let scambioCon = Catalogo.Scambi.con
    static let dai = Catalogo.Scambi.dai
    static let ricevi = Catalogo.Scambi.ricevi
    /// «2 su 4».
    static func scelti(_ n: Int, massimo: Int) -> String { Catalogo.Scambi.scelti(max: String(massimo), n: String(n)) }
    /// «Al massimo 4 giocatori per parte».
    static func alMassimo(_ max: Int) -> String { Catalogo.Scambi.massimo(max: String(max)) }
    /// Il segno meno è quello tipografico (U+2212).
    static let conguaglio = Catalogo.Scambi.conguaglio
    static let conguaglioAiuto = Catalogo.Scambi.conguaglioAiuto
    static let ricevoCrediti = Catalogo.Scambi.ricevoCrediti
    static let pagoCrediti = Catalogo.Scambi.pagoCrediti
    static let creditiQuanti = Catalogo.Scambi.creditiQuanti
    static let conguaglioNumero = Catalogo.Scambi.conguaglioNumero
    /// Il pulsante.
    static let valutaScambio = Catalogo.Scambi.analizza
    static let calcolo = Catalogo.Scambi.calcolo

    // MARK: il giudizio

    static let cosiNonSiPuoFare = Catalogo.Scambi.chiNonValido
    static let roseDopo = Catalogo.Scambi.roseDopo
    /// «Formazione migliore (prossima giornata)» con una giornata sola, «… (prossime N giornate)» con più. Senza il numero delle
    /// giornate (server vecchio) resta la parte che sta in tutte e due, prima della parentesi.
    static func formazioneMigliore(giornate: Int) -> String {
        switch giornate {
        case 1: return Catalogo.Scambi.formazioneMiglioreUna
        case 2...: return Catalogo.Scambi.formazioneMigliore(n: String(giornate))
        default:
            let una = Catalogo.Scambi.formazioneMiglioreUna
            return una.range(of: " (").map { String(una[..<$0.lowerBound]) } ?? una
        }
    }
    static let panchina = Catalogo.Scambi.panchina
    static let inStagione = Catalogo.Scambi.inStagione
    static let tu = Catalogo.Scambi.tu
    static let crediti = Catalogo.Scambi.creditiTitolo
    static let impatto = Catalogo.Scambio.impattoSullaTua
    static let contaAncheResto = Catalogo.Scambio.contaAncheResto
    /// «In totale (prossima giornata)» e «In totale (prossime N giornate)».
    static func inTotale(giornate: Int) -> String { Catalogo.Scambio.inTotale(giornate) }
}
