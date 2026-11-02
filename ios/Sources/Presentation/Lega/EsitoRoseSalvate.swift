import SwiftUI

/// Aggiorna le rose, dopo «Conferma e salva»: l'esito del server con i testi della web (`lega.*` di `fanta/web/testi.js`):
/// «Cosa è cambiato», le squadre importate, poi «Da controllare:» con gli avvisi oppure «Rose controllate: tutto in ordine.».
/// Due scelte dell'iPhone, scritte in `docs/COERENZA-WEB-IPHONE.md` (differenze ammesse): «Rose salvate» resta come prima riga
/// invece di un avviso che passa, e l'esito sta in cima alla lista. Sono due sezioni: va dentro una `List`.
struct EsitoRoseSalvate: View {
    let esito: EsitoImportazione

    private var avvisi: [String] { esito.avvisi ?? [] }

    var body: some View {
        Section {
            Label("Rose salvate", systemImage: "checkmark.circle.fill").foregroundStyle(Color.verde)
            if let d = esito.differenze { DifferenzeView(differenze: d) }
            else if let r = esito.riepilogo, !r.isEmpty { Text(r) }
            if let squadre = esito.squadreImportate, !squadre.isEmpty {
                Text("Importate: \(squadre.joined(separator: ", ")) (\(Formato.plurale(esito.totaleSquadre ?? squadre.count, "squadra", "squadre")) in tutto).")
                    .font(.footnote).foregroundStyle(Color.testoSecondario)
            }
        } header: { Text("Cosa è cambiato").foregroundStyle(Color.testoSecondario) }
        if avvisi.isEmpty {
            Section {
                Label("Rose controllate: tutto in ordine.", systemImage: "checkmark.circle")
                    .font(.footnote).foregroundStyle(Color.testoSecondario)
            }
        } else {
            Section {
                Text("Da controllare:")
                    .font(.footnote.weight(.semibold))
                    .foregroundStyle(Color.attenzione)
                    .accessibilityAddTraits(.isHeader)
                ForEach(avvisi, id: \.self) { Text($0).font(.footnote).foregroundStyle(Color.attenzione) }
            }
        }
    }
}
