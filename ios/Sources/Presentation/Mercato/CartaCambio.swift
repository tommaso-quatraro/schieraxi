import SwiftUI

/// Un cambio di Cambi consigliati, compatto: l'entrante in primo piano (avatar, nome), l'uscente in piccolo, il guadagno come
/// dato principale a destra, rimborso e crediti in una riga discreta.
/// Ogni testo si legge intero: con il testo grande va a capo, mai «…» né testo rimpicciolito (issue #247,
/// `CambiConsigliatiInteriTests`).
struct CartaCambio: View {
    let proposta: PropostaMercato
    @Environment(\.dynamicTypeSize) private var tagliaTesto

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            FilaAdattiva(spazio: 10) {
                AvatarGiocatore(id: proposta.entra.id, squadra: proposta.entra.squadra, dimensione: 44, conNumero: false,
                                nome: proposta.entra.nome, ruolo: proposta.entra.ruolo)
                VStack(alignment: .leading, spacing: 3) {
                    HStack(spacing: 6) {
                        BadgeRuolo(ruolo: proposta.entra.ruolo, piccolo: true)
                        Text(proposta.entra.nome).font(.headline)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    HStack(spacing: 5) {
                        Image(systemName: "arrow.uturn.backward").font(.caption2)
                        AvatarGiocatore(id: proposta.esce.id, squadra: proposta.esce.squadra, dimensione: 18, conNumero: false,
                                        nome: proposta.esce.nome, ruolo: proposta.esce.ruolo)
                        Text(proposta.esce.nome).font(.caption)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    .foregroundStyle(Color.testoSecondario)
                }
                Spacer(minLength: 6)
                // con il testo molto grande la fila diventa una colonna: il guadagno sta a sinistra come il resto
                VStack(alignment: tagliaTesto.isAccessibilitySize ? .leading : .trailing, spacing: 0) {
                    Text(Formato.conSegno(proposta.guadagno)).font(.title2.bold()).foregroundStyle(Color.verde).monospacedDigit()
                    Text("punti attesi").font(.caption2).foregroundStyle(Color.testoSecondario)
                }
                .fixedSize()
            }
            if let riga = Self.dettaglio(proposta) {
                Text(riga).font(.caption)
                    .foregroundStyle(proposta.fattibile == false ? Color.attenzione : Color.testoSecondario)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .padding(.horizontal, 14).padding(.vertical, 10)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.sfondoScheda, in: RoundedRectangle(cornerRadius: Tema.raggioScheda, style: .continuous))
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(Self.voce(proposta))
    }

    /// «+0,6 punti nelle prossime 5 giornate · crediti dopo 30 · rimborso 8 · costo 12»: tutto il secondario in una riga.
    /// Testi, ordine e separatore della web (`mercato.punti_prossime` e `soldiDelCambio` di `app.js`, issue #256):
    /// i soldi del cambio solo se il server manda i crediti dopo, come la web.
    static func dettaglio(_ p: PropostaMercato) -> String? {
        var parti: [String] = []
        if let b = p.breve {
            // «nelle prossime 0» usciva quando il server non manda le giornate: allora si dice solo «nelle prossime giornate»
            let n = p.giornate?.count ?? 0
            let quando = n == 0 ? "nelle prossime giornate" : n == 1 ? "nella prossima giornata" : "nelle prossime \(n) giornate"
            parti.append("\(Formato.conSegno(b)) punti \(quando)")
        }
        if let dopo = p.creditiDopo {
            let nonBastano = p.fattibile == false ? " (non bastano)" : ""
            parti += ["crediti dopo \(Formato.intero(dopo))" + nonBastano,
                      "rimborso \(Formato.intero(p.rimborso))",
                      "costo \(Formato.intero(p.entra.quotazione))"]
        }
        return parti.isEmpty ? nil : parti.joined(separator: " · ")
    }

    /// La frase intera per VoiceOver, con i dettagli nello stesso ordine della riga e le virgole al posto di «·»
    /// (come `FasiGiornata.partiteVoce`): «Entra X, esce Y, +2,4 punti attesi. +0,6 punti nelle prossime 5 giornate,
    /// crediti dopo 30, rimborso 8, costo 12».
    static func voce(_ p: PropostaMercato) -> String {
        var testo = "Entra \(p.entra.nome), esce \(p.esce.nome), \(Formato.conSegno(p.guadagno)) punti attesi"
        if let riga = dettaglio(p) { testo += ". " + riga.replacingOccurrences(of: " · ", with: ", ") }
        return testo
    }
}
