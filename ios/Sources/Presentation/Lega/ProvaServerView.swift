import SwiftUI

/// L'indirizzo del server con la prova di connessione: si scrive, si PROVA, e solo se il server giusto risponde si salva
/// (anche quando chiede l'accesso: un 401 è un successo). Se la prova fallisce l'indirizzo vecchio resta, a meno che
/// non si scelga «Salva comunque». Usata in Lega e nella schermata di accesso.
struct ProvaServerView: View {
    @AppStorage("indirizzo") private var salvato = ""
    @State private var bozza = ""
    @State private var iniziato = false
    @State private var inCorso = false
    @State private var esito: EsitoConnessione?
    @State private var versioneEsito = 0
    @Environment(\.accessibilityReduceMotion) private var ridotto
    /// Chi prova: nei test e nelle anteprime si sostituisce con una prova finta.
    var prova: (String) async -> EsitoConnessione = { indirizzo in
        if Demo.attivo { return .raggiunto(versione: nil, squadra: nil) }   // demo: nessuna rete
        return await ProvaConnessione.prova(indirizzo)
    }
    /// Chi è già dentro (nome utente): se la prova trova una sessione valida dice «Connesso come …».
    var utente: String? = nil
    /// Dopo una prova riuscita (e il salvataggio): per ricaricare lo stato del server o chiedere chi siamo.
    var dopoProva: () async -> Void = {}

    private var daProvare: String { bozza.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? Config.indirizzoPredefinito : bozza }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            TextField(Config.esempioIndirizzo, text: $bozza)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
                .keyboardType(.URL)
                .submitLabel(.go)
                .onSubmit { Task { await provaESalva() } }
                .padding(12)
                .frame(minHeight: Tema.areaTocco)
                .background(Color.sfondoIncavo, in: RoundedRectangle(cornerRadius: Tema.raggioPiccolo, style: .continuous))
                .accessibilityLabel("Indirizzo del server")
            if !bozza.trimmingCharacters(in: .whitespaces).isEmpty && ProvaConnessione.pulisci(bozza) == nil {
                Label("L'indirizzo deve iniziare con https://", systemImage: "exclamationmark.triangle")
                    .font(.footnote).foregroundStyle(Color.attenzione)
            }
            Button {
                Task { await provaESalva() }
            } label: {
                Label("Prova la connessione", systemImage: "antenna.radiowaves.left.and.right")
                    .symbolEffect(.variableColor.iterative, isActive: inCorso && !ridotto)
                    .frame(minHeight: Tema.areaTocco)
            }
            .disabled(inCorso)
            if inCorso {
                HStack(spacing: 10) {
                    Marchio(lato: 32, muove: true).accessibilityHidden(true)
                    Text("Provo a raggiungere il server…").font(.subheadline).foregroundStyle(.secondary)
                }
                .transition(.opacity)
                .accessibilityElement(children: .combine)
            } else if let e = esito {
                riga(e)
                if !e.raggiunto, e != .indirizzoNonValido {
                    Button("Salva comunque") { salva() }
                        .font(.subheadline)
                        .frame(minHeight: Tema.areaTocco, alignment: .leading)
                        .accessibilityHint("Salva questo indirizzo anche se la prova non è riuscita")
                }
            }
        }
        .animation(Tema.molla, value: esito)
        .animation(Tema.morbida, value: inCorso)
        .onAppear {
            guard !iniziato else { return }
            iniziato = true
            bozza = salvato
        }
        .sensoryFeedback(trigger: versioneEsito) { _, _ in
            guard let e = esito else { return nil }
            return e.raggiunto ? SensoryFeedback.success : SensoryFeedback.error
        }
    }

    private func riga(_ e: EsitoConnessione) -> some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: e.icona)
                .font(.title2)
                .foregroundStyle(e.raggiunto ? Color.verde : Color.attenzione)
                .symbolEffect(.bounce, value: ridotto ? 0 : versioneEsito)
                .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 2) {
                Text(e.titolo).font(.subheadline.weight(.semibold))
                Text(e.dettaglio).font(.footnote).foregroundStyle(.secondary)
            }
        }
        .transition(.opacity)
        .accessibilityElement(children: .combine)
    }

    private func provaESalva() async {
        if inCorso { return }
        inCorso = true
        esito = nil
        var risultato = await prova(daProvare)
        // Il server risponde e c'è una sessione aperta: si dice chi è connesso (non «accedi»).
        if case .raggiunto = risultato, let utente, !utente.isEmpty { risultato = .connesso(utente: utente) }
        if case .chiedeAccesso = risultato, utente != nil { risultato = .sessioneScaduta }
        inCorso = false
        esito = risultato
        versioneEsito += 1
        AccessibilityNotification.Announcement(risultato.titolo).post()
        // Si salva solo dopo una prova riuscita: un indirizzo sbagliato non sostituisce quello che funzionava.
        if risultato.raggiunto {
            salva()
            await dopoProva()
        }
    }

    private func salva() {
        let nuovo = ProvaConnessione.pulisci(bozza) ?? ""
        if nuovo != salvato { salvato = nuovo }
        if bozza.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty { bozza = "" }
    }
}
