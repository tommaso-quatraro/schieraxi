import SwiftUI

/// Formazione, riquadro «Partita rinviata» (campo `rinvio` di `GET /api/oggi`, `cardRinvio` della web): quali partite, la data del
/// recupero, i miei giocatori coinvolti e il menu «Per questa giornata i loro giocatori…», che vale solo per questa giornata.
/// A giornata finita (`riepilogo.rinvio`, #895) lo stesso riquadro sta sotto i punti, con `titolo` («Giornata 7 · 10ª di Serie A:
/// partita rinviata») e `nota` («Manca il recupero: i punti possono ancora cambiare.») sotto le partite.
struct CartaPartitaRinviata: View {
    let scelta: SceltaRinvio
    var inCorso = false
    var errore: String? = nil
    /// Al posto di «Partita rinviata» (la giornata finita, già pronto).
    var titolo: String? = nil
    var nota: String? = nil
    let cambia: @MainActor (String) async -> Void

    var body: some View {
        Carta(titolo ?? TestiRinvio.titolo(scelta.partite.count), simbolo: "calendar.badge.exclamationmark") {
            ForEach(scelta.partite) { p in
                HStack(alignment: .firstTextBaseline, spacing: 8) {
                    Text(TestiRinvio.partita(p)).font(.subheadline.bold())
                    Text(TestiRinvio.recupero(p)).font(.footnote).foregroundStyle(Color.testoSecondario)
                    Spacer(minLength: 0)
                }
                // le sigle si vedono; VoiceOver legge i nomi interi, come le partite del turno
                .accessibilityElement(children: .ignore)
                .accessibilityLabel("\(TestiRinvio.partitaAVoce(p)), \(TestiRinvio.recupero(p))")
            }
            if let nota {
                Text(nota).font(.subheadline).fixedSize(horizontal: false, vertical: true)
            }
            if let m = TestiRinvio.miei(scelta) {
                Text(m).font(.subheadline).fixedSize(horizontal: false, vertical: true)
            }
            MenuRinvio(scelta: scelta, inCorso: inCorso) { _, m in await cambia(m) }
            if let errore { Text(errore).font(.footnote).foregroundStyle(Color.attenzione).fixedSize(horizontal: false, vertical: true) }
        }
    }
}

/// Il menu «Per questa giornata i loro giocatori…» con la riga sotto (regola della lega o scelta solo per questa giornata).
/// Uguale nel riquadro della partita rinviata della giornata e in quello della giornata finita con un recupero che manca (nella testa
/// della Formazione, #895).
struct MenuRinvio: View {
    let scelta: SceltaRinvio
    var inCorso = false
    let cambia: @MainActor (SceltaRinvio, String) async -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(TestiRinvio.domanda).font(.subheadline).foregroundStyle(Color.testoSecondario)
            Menu {
                Picker(TestiRinvio.domanda, selection: Binding(get: { scelta.modo }, set: { m in Task { await cambia(scelta, m) } })) {
                    ForEach(scelta.modi, id: \.self) { m in Text(TestiRinvio.nomeModo(m, voto: scelta.votoUfficio)).tag(m) }
                }
            } label: {
                // l'etichetta va a capo con il testo grande (il selettore di sistema taglierebbe la scelta)
                HStack(alignment: .firstTextBaseline, spacing: 6) {
                    Text(TestiRinvio.nomeModo(scelta.modo, voto: scelta.votoUfficio))
                        .multilineTextAlignment(.leading)
                        .fixedSize(horizontal: false, vertical: true)
                    Image(systemName: "chevron.up.chevron.down").font(.footnote.weight(.semibold))
                    Spacer(minLength: 0)
                }
                .frame(maxWidth: .infinity, minHeight: Tema.areaTocco, alignment: .leading)
                .contentShape(Rectangle())
            }
            .disabled(inCorso)
            .accessibilityLabel(TestiRinvio.domanda)
            .accessibilityValue(TestiRinvio.nomeModo(scelta.modo, voto: scelta.votoUfficio))
            Text(TestiRinvio.nota(scelta)).font(.footnote).foregroundStyle(Color.testoSecondario)
                .fixedSize(horizontal: false, vertical: true)
        }
    }
}

#Preview("Partita rinviata") {
    ScrollView {
        CartaPartitaRinviata(scelta: SceltaRinvio(stagione: "2026-27", giornata: 11, giornataLega: 8, modo: ModoRinvio.aspetta,
                                                  predefinito: ModoRinvio.aspetta,
                                                  partite: [PartitaRinviata(casa: "atalanta", trasferta: "parma", data: "2026-11-25 20:45")],
                                                  miei: [GiocatoreRinviato(id: 1, nome: "Ruben Tescari"), GiocatoreRinviato(id: 2, nome: "Amos Delvecchio")])) { _ in }
            .padding()
    }
}
