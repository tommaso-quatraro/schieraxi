import SwiftUI

/// L'iPad a tutto schermo, o quasi (e ogni schermo largo e alto): con le classi di dimensione orizzontale e verticale «regular»
/// (#896, #919). Solo lì le pagine stanno in una colonna come la web larga, Giornate ha elenco e dettaglio affiancati e il campo è
/// spazioso. Un iPhone in orizzontale può essere più largo della colonna (16 Pro 874 punti, Pro Max 956, con la larghezza
/// «regular») ma è basso, con l'altezza «compact»; l'iPad in Slide Over o in Split View stretta ha la larghezza «compact»: tutti e
/// due restano come il telefono.
enum SpazioIPad {
    static func largoEAlto(orizzontale: UserInterfaceSizeClass?, verticale: UserInterfaceSizeClass?) -> Bool {
        orizzontale == .regular && verticale == .regular
    }
}
