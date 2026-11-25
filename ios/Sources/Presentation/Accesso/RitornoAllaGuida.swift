import Foundation

/// Una pagina aperta da un passo della configurazione guidata (#880). Sulla web tutto succede dentro la guida, che continua con i
/// passi che restano fino a «Tutto pronto»; sull'iPhone «Importa le rose», «Scegli la squadra» e «Scegli stemma e maglia» portano
/// a una pagina delle Impostazioni e «Collega il widget» al suo foglio. Quando la pagina si lascia (anche con «indietro» senza
/// salvare) o il foglio si chiude, la guida si riapre e riparte da quel passo (`PrimoAvvioLogica.inizio`).
/// Vive nel `LegaViewModel` della sessione: uscendo dall'account se ne va con lui.
struct RitornoAllaGuida {
    /// Dove ha portato la guida: una pagina delle Impostazioni (con quelle che le si aprono sopra) o il foglio del widget.
    enum Meta: Equatable { case pagina(PaginaImpostazioni), widget }

    /// Il ritorno dal foglio del widget: il passo da cui riaprire la guida e se è già fatto (il widget si è collegato da solo).
    struct Ritorno: Equatable {
        let passo: PassoGuidato
        let fatto: Bool
    }

    private enum Fase { case nessuna, chiesta, aperta }
    private var fase = Fase.nessuna
    private var meta: Meta?
    private var passo: PassoGuidato?
    /// Il foglio del widget aperto dalla guida l'ha collegato.
    private var collegato = false

    /// La guida ha portato a `meta` dal passo `passo`.
    mutating func chiesta(_ meta: Meta, dalPasso passo: PassoGuidato) {
        fase = .chiesta
        self.meta = meta
        self.passo = passo
        collegato = false
    }

    /// La pila delle Impostazioni è cambiata: il passo da cui riaprire la guida, una volta, quando la pagina chiesta è stata
    /// aperta e poi lasciata (una pagina aperta sopra, come la rosa dall'elenco delle squadre, non conta come lasciata). Se la
    /// pagina non si apre (le Regole con modifiche da salvare la fanno aspettare) e si torna indietro, la richiesta cade: la stessa
    /// pagina aperta più tardi dalle Impostazioni non riapre la guida.
    mutating func pilaCambiata(_ pagine: [PaginaImpostazioni]) -> PassoGuidato? {
        guard case .pagina(let pagina)? = meta else { return nil }
        return segui(aperta: pagine.contains(pagina))
    }

    /// Il foglio «Collega il widget» si è aperto o chiuso: il passo da cui riaprire la guida, una volta, quando si chiude.
    mutating func foglioWidget(aperto: Bool) -> Ritorno? {
        guard meta == .widget else { return nil }
        let fatto = collegato
        return segui(aperta: aperto).map { Ritorno(passo: $0, fatto: fatto) }
    }

    /// Il foglio «Collega il widget» ha collegato il widget da solo («Widget collegato»). Conta solo se il foglio l'ha aperto la
    /// guida: aperto dalle Impostazioni o dal tocco sul widget non segna niente.
    mutating func widgetCollegato() {
        if fase != .nessuna, meta == .widget { collegato = true }
    }

    /// La pagina è stata chiesta dalla guida e non è ancora stata lasciata: la pagina delle rose, salvate le rose, si chiude da sola.
    func attivo(per pagina: PaginaImpostazioni) -> Bool { fase != .nessuna && meta == .pagina(pagina) }

    private mutating func segui(aperta: Bool) -> PassoGuidato? {
        switch (fase, aperta) {
        case (.chiesta, true):
            fase = .aperta
        case (.chiesta, false):
            dimentica()
        case (.aperta, false):
            let daQui = passo
            dimentica()
            return daQui
        default:
            break
        }
        return nil
    }

    private mutating func dimentica() {
        fase = .nessuna
        meta = nil
        passo = nil
        collegato = false
    }
}
