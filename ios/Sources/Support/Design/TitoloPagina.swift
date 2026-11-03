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
}

extension EnvironmentValues {
    /// Il titolo della pagina, messo da `titoloPagina(_:)` e letto da `TitoloNellaPagina`.
    @Entry var titoloPagina: String? = nil
}

extension View {
    /// Il titolo della pagina: grande nella barra con il testo normale; con il testo grande piccolo nella barra e intero
    /// nella pagina, dove `TitoloNellaPagina` lo mostra a capo.
    func titoloPagina(_ titolo: String) -> some View {
        modifier(ModificatoreTitoloPagina(titolo: titolo))
    }
}
