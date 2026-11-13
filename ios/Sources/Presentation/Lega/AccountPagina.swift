import SwiftUI

/// Impostazioni > Il tuo account (come `paginaAccount` della web, #673 passo 3): le righe dell'account, con «Esci» in fondo.
/// I fogli dell'account si aprono da qui, fuori dalla lista (vedi `FoglioAccount`).
struct AccountPagina: View {
    @EnvironmentObject private var sessione: SessioneAccount
    @StateObject private var fogli = FogliAccount()

    var body: some View {
        ScrollViewReader { proxy in
            List {
                TitoloNellaPagina()
                AccountSezione(fogli: fogli)
            }
            .scrollContentBackground(.hidden)
            .background(Sfondo())
            // fotografia `accesso-account-fondo`: la fine di «Il tuo account», con «Esci»
            .demoScorriA(RigaEsci.idDemo, proxy: proxy, schermate: ["accesso-account"], inFondo: true, ancora: .center,
                         pronto: sessione.utente != nil)
        }
        .titoloPagina(Catalogo.Imp.account)
        .fogliAccount(fogli)   // fuori dalla List: i dati dell'account che arrivano non chiudono più i fogli
        .schermoProtetto()     // l'email e i dati dell'account non devono comparire nell'anteprima del selettore delle app
    }
}
