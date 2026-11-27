import SwiftUI

/// Una riga delle Impostazioni che apre una pagina: il nome e sotto la riga piccola della web (`rigaImp`). VoiceOver legge nome e riga
/// insieme, come un'unica voce; il testo grande le manda a capo. Senza pagina la riga è spenta, senza freccia, come `rigaImpSpenta`
/// della web: un pulsante disattivato, grigio, che VoiceOver legge «non disponibile».
struct RigaVoceImpostazioni: View {
    let voce: VoceImpostazioni

    var body: some View {
        if let pagina = voce.pagina {
            NavigationLink(value: pagina) { contenuto }
        } else {
            Button {} label: { contenuto }
                .disabled(true)
        }
    }

    private var contenuto: some View {
        NomeConAiuto(voce.nome, aiuto: voce.sotto)
            .frame(maxWidth: .infinity, minHeight: Tema.areaTocco, alignment: .leading)
    }
}
