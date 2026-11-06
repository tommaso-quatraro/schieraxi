import SwiftUI

/// Il titolo delle pagine con il testo grande (issue #196).
///
/// Il titolo grande della barra di iOS sta su una riga sola: con il testo grande si tagliava («Avvisi e prome…»,
/// «Nuova stagi…», «Aggiorna le…»). Da `soglia` in su la barra passa al titolo piccolo e il titolo intero va in cima alla
/// pagina, dove va a capo. Una pagina usa `.titoloPagina("…")` al posto di `.navigationTitle("…")` e mette
/// `TitoloNellaPagina()` come primo elemento della sua lista (o della colonna che scorre). Nella barra il titolo non si
/// taglia mai: intero, a capo se serve, oppure (con il testo grande, se non ci sta) niente (`TitoloInBarra`, #293, #419).
enum TitoloPagina {
    /// Da questa dimensione del testo il titolo va nella pagina. Con «XXL» il titolo grande della barra non ci sta più
    /// sull'iPhone SE («Avvisi e promemoria»), con «XXXL» nemmeno sugli iPhone più larghi.
    static let soglia: DynamicTypeSize = .xxLarge

    /// Tetto della dimensione del titolo nella pagina: più in grande una parola lunga come «Impostazioni» non ci sta in
    /// larghezza sull'iPhone SE e si spezzerebbe a metà.
    static let tetto: DynamicTypeSize = .accessibility3

    /// Tetto della dimensione del titolo piccolo nella barra con il testo grande: fin dove cresce il titolo piccolo di
    /// sistema, così la barra resta alta come nelle altre pagine e una riga ci sta anche nella barra bassa in orizzontale.
    static let tettoBarra: DynamicTypeSize = .xxxLarge

    /// Con questa dimensione del testo il titolo sta nella pagina (e nella barra solo in piccolo, se ci sta)?
    static func nellaPagina(_ dimensione: DynamicTypeSize) -> Bool {
        dimensione >= soglia
    }

    /// La barra mostra il titolo grande? Solo sotto la soglia e se la pagina non lo vuole sempre piccolo
    /// (`piccoloInBarra`: le pagine di dettaglio, come quella di una squadra).
    static func grandeInBarra(_ dimensione: DynamicTypeSize, piccoloInBarra: Bool = false) -> Bool {
        !piccoloInBarra && !nellaPagina(dimensione)
    }

    /// La barra piccola mostra il titolo intero, a capo se serve (`TitoloInBarra`, #293)? Solo per le pagine con
    /// `piccoloInBarra` e sotto la soglia: il titolo piccolo di sistema sta su una riga e taglia un nome di squadra oltre
    /// ~22 lettere. Da `soglia` in su il titolo intero sta già nella pagina (#276): vedi `inBarraSeCiSta`.
    static func interoInBarra(_ dimensione: DynamicTypeSize, piccoloInBarra: Bool) -> Bool {
        piccoloInBarra && !nellaPagina(dimensione)
    }

    /// Con il testo grande la barra mostra il titolo solo se ci sta intero su una riga, se no niente (#419)? Da `soglia` in
    /// su, per tutte le pagine: il titolo intero sta già nella pagina (`TitoloNellaPagina`) e il titolo piccolo di sistema lo
    /// taglierebbe con «…» («Gli Amici del B…» sopra lo stesso nome intero).
    static func inBarraSeCiSta(_ dimensione: DynamicTypeSize) -> Bool {
        nellaPagina(dimensione)
    }
}

extension EnvironmentValues {
    /// Il titolo della pagina, messo da `titoloPagina(_:)` e letto da `TitoloNellaPagina`.
    @Entry var titoloPagina: String? = nil
}

extension View {
    /// Il titolo della pagina: grande nella barra con il testo normale; con il testo grande intero nella pagina, dove
    /// `TitoloNellaPagina` lo mostra a capo, e nella barra piccolo solo se ci sta intero su una riga (#419). Con
    /// `piccoloInBarra` la barra ha sempre il titolo piccolo (pagine di dettaglio, titoli presi dai dati come il nome di una
    /// squadra, #276): sotto la soglia la barra lo mostra intero, su due righe se non ci sta in una (`TitoloInBarra`, #293).
    func titoloPagina(_ titolo: String, piccoloInBarra: Bool = false) -> some View {
        modifier(ModificatoreTitoloPagina(titolo: titolo, piccoloInBarra: piccoloInBarra))
    }
}
