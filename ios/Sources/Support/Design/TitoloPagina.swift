import SwiftUI

/// Il titolo delle pagine con il testo grande (issue #196).
///
/// Il titolo grande della barra di iOS sta su una riga sola: con il testo grande si tagliava («Avvisi e prome…»,
/// «Nuova stagi…», «Aggiorna le…»). Da `soglia` in su la barra passa al titolo piccolo e il titolo intero va in cima alla
/// pagina, dove va a capo. Una pagina usa `.titoloPagina("…")` al posto di `.navigationTitle("…")` e mette
/// `TitoloNellaPagina()` come primo elemento della sua lista (o della colonna che scorre).
enum TitoloPagina {
    /// Da questa dimensione del testo il titolo va nella pagina. Con «XXL» il titolo grande della barra non ci sta più
    /// sull'iPhone SE («Avvisi e promemoria»), con «XXXL» nemmeno sugli iPhone più larghi.
    static let soglia: DynamicTypeSize = .xxLarge

    /// Tetto della dimensione del titolo nella pagina: più in grande una parola lunga come «Impostazioni» non ci sta in
    /// larghezza sull'iPhone SE e si spezzerebbe a metà.
    static let tetto: DynamicTypeSize = .accessibility3

    /// Con questa dimensione del testo il titolo sta nella pagina (e nella barra solo in piccolo)?
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
    /// ~22 lettere. Da `soglia` in su il titolo intero sta già nella pagina (#276) e la barra resta quella di sistema.
    static func interoInBarra(_ dimensione: DynamicTypeSize, piccoloInBarra: Bool) -> Bool {
        piccoloInBarra && !nellaPagina(dimensione)
    }

    /// Da completare (#419): per ora la barra con il testo grande resta quella di sistema.
    static func inBarraSeCiSta(_ dimensione: DynamicTypeSize) -> Bool {
        false
    }
}

extension EnvironmentValues {
    /// Il titolo della pagina, messo da `titoloPagina(_:)` e letto da `TitoloNellaPagina`.
    @Entry var titoloPagina: String? = nil
}

extension View {
    /// Il titolo della pagina: grande nella barra con il testo normale; con il testo grande piccolo nella barra e intero
    /// nella pagina, dove `TitoloNellaPagina` lo mostra a capo. Con `piccoloInBarra` la barra ha sempre il titolo piccolo
    /// (pagine di dettaglio, titoli presi dai dati come il nome di una squadra, #276): da `soglia` in su il titolo intero va
    /// nella pagina, sotto la soglia la barra lo mostra intero, su due righe se non ci sta in una (`TitoloInBarra`, #293).
    func titoloPagina(_ titolo: String, piccoloInBarra: Bool = false) -> some View {
        modifier(ModificatoreTitoloPagina(titolo: titolo, piccoloInBarra: piccoloInBarra))
    }
}
