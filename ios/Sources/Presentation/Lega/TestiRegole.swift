import Foundation

/// I testi della schermata Regole (modificatore difesa, panchina, tempi della lega), uguali alla web (`vistaRegole` in
/// `fanta/web/app.js`): vengono dal catalogo comune (`fanta/testi/regole.json`, file generato `Catalogo+Regole.swift`). Qui restano
/// i nomi che usano le viste e le frasi con un numero. Logica pura: la provano i test.
enum TestiRegole {
    // MARK: modificatore difesa

    /// Le parole di «+ Aggiungi fascia» (`regole.aggiungi_fascia`) senza il «+» della web: sull'iPhone il «+» è l'icona del pulsante.
    static let aggiungiFascia: String = {
        let web = Catalogo.Regole.aggiungiFascia
        return web.hasPrefix("+ ") ? String(web.dropFirst(2)) : web
    }()
    static let prova = Catalogo.Regole.prova
    static let provaVoti = Catalogo.Regole.votiPortiereDifensori

    /// L'esito della prova, come la web (`regole.media_bonus`): «Media 6,50 bonus +1 punto», «Media 6,75 bonus +3 punti».
    /// «punto» solo con un bonus di 1; un bonus intero si scrive senza decimali, uno a metà con uno («+1,5 punti»).
    static func esitoProva(media: Double, bonus: Double) -> String {
        let intero = bonus == bonus.rounded()
        let numero = (bonus > 0 ? "+" : "") + Formato.decimali(bonus, cifre: intero ? 0 : 1)
        return Catalogo.Regole.mediaBonus(abs(bonus) == 1 ? 1 : 2, b: numero, m: Formato.decimali(media, cifre: 2))
    }

    // MARK: nomi per VoiceOver (#460, come la web: #454)

    /// I nomi che VoiceOver legge per i tre controlli di una fascia. Il testo a vista resta «Media almeno», «bonus» e «Togli la
    /// fascia»: senza il numero, con sei fasce VoiceOver leggeva sei volte lo stesso nome.
    struct NomiFascia: Equatable, Sendable {
        /// `regole.fascia_media`: «Fascia 2, media almeno».
        let media: String
        /// `regole.fascia_bonus`: «Fascia 2, bonus».
        let bonus: String
        /// `regole.togli_fascia`: «Togli la fascia 2».
        let togli: String
    }

    /// I nomi dei controlli della fascia al `posto` indicato (da 1: è il posto della riga, quindi dopo «Togli» i numeri si rifanno).
    static func nomiFascia(posto: Int) -> NomiFascia {
        let n = String(posto)
        return NomiFascia(media: Catalogo.Regole.fasciaMedia(n: n),
                          bonus: Catalogo.Regole.fasciaBonus(n: n),
                          togli: Catalogo.Regole.togliFascia(n: n))
    }

    /// Il nome di uno dei quattro voti della prova: 0 è il portiere («regole.voto_portiere»), da 1 i difensori («regole.voto_difensore»).
    static func nomeVotoProva(indice: Int) -> String {
        indice == 0 ? Catalogo.Regole.votoPortiere : Catalogo.Regole.votoDifensore(n: String(indice))
    }

    // MARK: panchina e sostituzioni

    static let postiFissi = Catalogo.Regole.postiFissi
    static let postiFissiAiuto = Catalogo.Regole.postiFissiAiuto
    static let cambioModulo = Catalogo.Regole.cambioModulo
    static let cambioModuloAiuto = Catalogo.Regole.cambioModuloAiuto

    // MARK: tempi della lega

    static let scadenza = Catalogo.Regole.scadenza
    static let scadenzaAiuto = Catalogo.Regole.scadenzaAiuto
    static let primaGiornata = Catalogo.Regole.primaGiornata
    static let primaGiornataAiuto = Catalogo.Regole.primaGiornataAiuto
    /// In fondo alla sezione: un esempio fisso («a 4»), che non cambia con il numero scelto.
    static let conPrimaGiornata = Catalogo.Regole.conPrimaGiornata
}
