import SwiftUI

/// Impostazioni > Informazioni (come `paginaInformazioni` della web, #673 passo 3): privacy, termini, crediti, codice sorgente, la
/// versione e le novità. La versione è quella del server, come la web; sotto, quella dell'app (solo iPhone, #931).
struct InformazioniPagina: View {
    let server: any ServerClient
    /// Lo stato del server (`GET /api/stato`), già letto dalle Impostazioni: da qui la sua versione.
    @ObservedObject var info: Caricatore<InfoServer>

    var body: some View {
        List {
            TitoloNellaPagina()
            Section {
                RigheLegali(server: server)
                ForEach(VersioniInformazioni.righe(server: info.dato?.versione, app: Self.versioneApp), id: \.titolo) { riga in
                    RigaValore(titolo: riga.titolo, valore: riga.valore)
                }
            }
            Section {
                NavigationLink(value: PaginaImpostazioni.novita) {
                    Label(Catalogo.Lega.voceNovita, systemImage: "sparkles").labelStyle(.voce(.yellow)).frame(minHeight: Tema.areaTocco)
                }
            }
        }
        .scrollContentBackground(.hidden)
        .background(Sfondo())
        .titoloPagina(Catalogo.Imp.informazioni)
    }

    /// La versione dell'app installata («1.0.12»).
    private static var versioneApp: String? {
        Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String
    }
}
