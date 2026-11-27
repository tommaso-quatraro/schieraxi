import SwiftUI

/// L'iPad a tutto schermo, o quasi (e ogni schermo largo e alto): con le classi di dimensione orizzontale e verticale «regular»
/// (#896, #919). Solo lì le pagine stanno in una colonna come la web larga, Giornate ha elenco e dettaglio affiancati e il campo è
/// spazioso. Un iPhone in orizzontale può essere più largo della colonna, ma è basso, con l'altezza «compact»: il 16 Pro (874
/// punti) ha anche la larghezza «compact», solo i Plus e i Pro Max (932-956 punti) l'hanno «regular» (#930). L'iPad in Slide Over
/// o in Split View stretta ha la larghezza «compact». Tutti restano come il telefono.
enum SpazioIPad {
    static func largoEAlto(orizzontale: UserInterfaceSizeClass?, verticale: UserInterfaceSizeClass?) -> Bool {
        orizzontale == .regular && verticale == .regular
    }
}
