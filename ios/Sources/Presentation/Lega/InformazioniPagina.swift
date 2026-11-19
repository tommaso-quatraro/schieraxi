import SwiftUI

/// Impostazioni > Informazioni (come `paginaInformazioni` della web, #673 passo 3): privacy, termini, crediti, codice sorgente, la
/// versione e le novità.
struct InformazioniPagina: View {
    let server: any ServerClient

    var body: some View {
        List {
            TitoloNellaPagina()
            Section {
                RigheLegali(server: server)
                RigaValore(titolo: "Versione", valore: Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "—")
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
}
