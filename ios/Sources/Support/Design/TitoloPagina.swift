import SwiftUI

/// Il titolo delle pagine con il testo grande (issue #196).
///
/// Il titolo grande della barra di iOS sta su una riga sola: con il testo grande si tagliava («Avvisi e prome…»,
/// «Nuova stagi…», «Aggiorna le…»). Da `soglia` in su il titolo intero va in cima alla pagina, dove va a capo, e la barra
/// non mostra titoli (#419). Una pagina usa `.titoloPagina("…")` al posto di `.navigationTitle("…")` e mette
/// `TitoloNellaPagina()` come primo elemento della sua lista (o della colonna che scorre). Nella barra il titolo non si
/// taglia mai: grande, intero a capo (`TitoloInBarra`, #293) o niente.
enum TitoloPagina {
    /// Da questa dimensione del testo il titolo va nella pagina. Con «XXL» il titolo grande della barra non ci sta più
    /// sull'iPhone SE («Avvisi e promemoria»), con «XXXL» nemmeno sugli iPhone più larghi.
    static let soglia: DynamicTypeSize = .xxLarge

    /// Tetto della dimensione del titolo nella pagina: più in grande una parola lunga come «Impostazioni» non ci sta in
    /// larghezza sull'iPhone SE e si spezzerebbe a metà.
    static let tetto: DynamicTypeSize = .accessibility3

    /// Con questa dimensione del testo il titolo sta nella pagina (e la barra resta senza titolo)?
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
    /// ~22 lettere. Da `soglia` in su il titolo intero sta già nella pagina (#276): vedi `barraSenzaTitolo`.
    static func interoInBarra(_ dimensione: DynamicTypeSize, piccoloInBarra: Bool) -> Bool {
        piccoloInBarra && !nellaPagina(dimensione)
    }

    /// Con il testo grande la barra resta senza titolo (#419)? Da `soglia` in su, per tutte le pagine: il titolo intero sta
    /// già nella pagina (`TitoloNellaPagina`), e nella barra si tagliava («Gli Amici del B…» sopra lo stesso nome intero).
    /// Niente «solo se ci sta»: un titolo nella barra nascosto a VoiceOver lasciava lo stesso un elemento con il nome (o
    /// vuoto) nella barra, che VoiceOver poteva leggere su una zona vuota (test `TitoloUnaVoltaUITests`).
    static func barraSenzaTitolo(_ dimensione: DynamicTypeSize) -> Bool {
        nellaPagina(dimensione)
    }

    /// VoiceOver legge il titolo nella pagina (`TitoloNellaPagina`, come intestazione) invece che nella barra? (#419) Sì
    /// quando la barra è senza titolo (`barraSenzaTitolo`), così il nome si sente una volta sola, dove si vede intero.
    /// Negli altri casi VoiceOver legge la barra e il titolo nella pagina (se c'è) gli resta nascosto.
    static func voceNellaPagina(_ dimensione: DynamicTypeSize) -> Bool {
        barraSenzaTitolo(dimensione)
    }
}

extension EnvironmentValues {
    /// Il titolo della pagina, messo da `titoloPagina(_:)` e letto da `TitoloNellaPagina`.
    @Entry var titoloPagina: String? = nil
}

extension View {
    /// Il titolo della pagina: grande nella barra con il testo normale; con il testo grande intero nella pagina, dove
    /// `TitoloNellaPagina` lo mostra a capo, e la barra senza titolo (#419). Con `piccoloInBarra` la barra ha il titolo
    /// piccolo (pagine di dettaglio, titoli presi dai dati come il nome di una squadra, #276): sotto la soglia intero, su
    /// due righe se non ci sta in una (`TitoloInBarra`, #293).
    func titoloPagina(_ titolo: String, piccoloInBarra: Bool = false) -> some View {
        modifier(ModificatoreTitoloPagina(titolo: titolo, piccoloInBarra: piccoloInBarra))
    }
}
