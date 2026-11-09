import SwiftUI

/// Aggiorna le rose, dopo «Conferma e salva»: l'esito del server con i testi della web (`lega.*` del catalogo comune):
/// «Cosa è cambiato», le squadre importate, poi «Da controllare:» con gli avvisi oppure «Rose controllate: tutto in ordine.».
/// Due scelte dell'iPhone, scritte in `docs/COERENZA-WEB-IPHONE.md` (differenze ammesse): «Rose salvate» resta come prima riga
/// invece di un avviso che passa, e l'esito sta in cima alla lista. Sono due sezioni: va dentro una `List`.
struct EsitoRoseSalvate: View {
    let esito: EsitoImportazione

    private var avvisi: [String] { esito.avvisi ?? [] }

    var body: some View {
        Section {
            Label(Catalogo.Ar.salvate, systemImage: "checkmark.circle.fill").foregroundStyle(Color.verde)
            if let d = esito.differenze { DifferenzeView(differenze: d) }
            else if let r = esito.riepilogo, !r.isEmpty { Text(r) }
            if let squadre = esito.squadreImportate, !squadre.isEmpty {
                Text(Catalogo.Lega.importate(n: Catalogo.Lega.nSquadre(esito.totaleSquadre ?? squadre.count), nomi: squadre.joined(separator: ", ")))
                    .font(.footnote).foregroundStyle(Color.testoSecondario)
            }
        } header: { Text(Catalogo.Lega.cosaCambiato).foregroundStyle(Color.testoSecondario) }
        if avvisi.isEmpty {
            Section {
                Label(Catalogo.Lega.roseControllateTutto, systemImage: "checkmark.circle")
                    .font(.footnote).foregroundStyle(Color.testoSecondario)
            }
        } else {
            Section {
                Text(Catalogo.Lega.daControllare)
                    .font(.footnote.weight(.semibold))
                    .foregroundStyle(Color.attenzione)
                    .accessibilityAddTraits(.isHeader)
                ForEach(avvisi, id: \.self) { Text($0).font(.footnote).foregroundStyle(Color.attenzione) }
            }
        }
    }
}
