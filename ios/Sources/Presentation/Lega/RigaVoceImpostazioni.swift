import SwiftUI

/// Una riga delle Impostazioni che apre una pagina: il nome e sotto la riga piccola della web (`rigaImp`). VoiceOver legge nome e riga
/// insieme, come un'unica voce; il testo grande le manda a capo.
struct RigaVoceImpostazioni: View {
    let voce: VoceImpostazioni

    var body: some View {
        NavigationLink(value: voce.pagina) {
            NomeConAiuto(voce.nome, aiuto: voce.sotto)
                .frame(maxWidth: .infinity, minHeight: Tema.areaTocco, alignment: .leading)
        }
    }
}
