import SwiftUI

/// Rose salvate ma la tua squadra non ancora scelta (primo avvio lasciato a metà, collaudo del 26/11), come `caricaGiornata` e
/// `mostraSenzaSquadra` della web: `/api/oggi` e `/api/formazione` risponderebbero 400 («Indica la tua squadra…») e la Formazione
/// sarebbe un errore con «Riprova» che non serve. Lo dice `/api/stato` (`rose_importate` vero e `mia_squadra` vuota): allora la
/// Formazione non chiede la giornata né la formazione e mostra la domanda della guida, «Quale squadra è la tua?» con «Questa è la
/// mia». Solo una risposta appena arrivata decide: senza server (o con la copia del telefono) non si chiede la squadra, e la
/// Formazione resta quella di sempre (la copia con la striscia dei dati salvati, o l'errore con «Riprova»), come la web.
@MainActor
final class SquadraDaScegliere: ViewModelBase {
    /// `GET /api/stato`, senza copia sul telefono: la domanda vale solo per una risposta fresca.
    let info: Caricatore<InfoServer>
    /// Le squadre della lega, per il menu della domanda.
    let squadre: Caricatore<[SquadraLega]>
    private let server: any ServerClient
    /// Fa leggere a VoiceOver il perché di «Questa è la mia» non riuscito: compare sotto il pulsante e prima era solo una vibrazione.
    /// Si sostituisce nei test per contare gli annunci.
    var annuncia: @MainActor (String) -> Void = { Annuncio.leggi($0) }

    init(server: any ServerClient) {
        self.server = server
        info = Caricatore<InfoServer>("/api/stato", cache: false, ascolta: false, server: server)
        squadre = Caricatore<[SquadraLega]>("/api/squadre", cache: false, ascolta: false, server: server)
        super.init()
        osserva(info)
        osserva(squadre)
    }

    /// L'ultima risposta di `/api/stato` dice che le rose ci sono e la tua squadra no.
    var manca: Bool {
        guard info.errore == nil, let i = info.dato, i.roseImportate == true else { return false }
        return (i.miaSquadra ?? "").isEmpty
    }

    /// Rilegge lo stato (e, se la squadra manca, le squadre per il menu). True se la squadra manca: allora la giornata e la
    /// formazione non si chiedono.
    @discardableResult
    func controlla() async -> Bool {
        await info.ricarica()
        if manca { await squadre.ricarica() }
        return manca
    }

    /// «Questa è la mia»: `PUT /api/mia-squadra`, poi lo stato si rilegge (la domanda sparisce) e tutte le schermate rileggono,
    /// come dopo «Non è la tua squadra?» (`LegaViewModel.scegliMiaSquadra`). Nil se è andata bene, altrimenti il motivo da mostrare.
    func scegli(_ nome: String) async -> String? {
        do {
            _ = try await server.corpoJSON("PUT", "/api/mia-squadra", NomeSquadra(nome: nome))
        } catch {
            let testo = error.localizedDescription
            Haptics.esito(riuscito: false)
            annuncia(testo)
            return testo
        }
        Haptics.esito(riuscito: true)
        await info.ricarica()
        NotificationCenter.default.post(name: .aggiornaTutto, object: nil)
        return nil
    }
}

/// La domanda nella Formazione, con le parole del passo «La tua squadra» della guida della web (`pav.quale_squadra_tua`,
/// `pav.questa_mia`): un menu con le squadre, già sulla prima, e il pulsante; un menu che salva al cambio non farebbe scegliere la
/// prima. Senza l'elenco delle squadre, la frase «Indica la tua squadra in «La mia squadra»» (`err.indica_squadra`), come la web.
/// Se la scelta non si salva il perché va sotto il pulsante e VoiceOver lo legge (`SquadraDaScegliere.annuncia`).
@MainActor
struct SceltaSquadraFormazione: View {
    @ObservedObject var squadra: SquadraDaScegliere
    @State private var scelta = ""
    @State private var errore: String?
    @State private var inCorso = false

    var body: some View {
        Carta(Catalogo.Pav.qualeSquadraTua, simbolo: "person.3") {
            if let elenco = squadra.squadre.dato, !elenco.isEmpty {
                // un'etichetta nostra, che va a capo con un nome lungo o il testo grande: quella del menu di sistema lo tagliava
                // con «…» (come `MenuRinvio`)
                Menu {
                    Picker(Catalogo.Lega.tuaSquadra, selection: $scelta) {
                        ForEach(elenco) { Text($0.nome).tag($0.nome) }
                    }
                } label: {
                    HStack(alignment: .firstTextBaseline, spacing: 6) {
                        Text(scelta)
                            .multilineTextAlignment(.leading)
                            .fixedSize(horizontal: false, vertical: true)
                        Image(systemName: "chevron.up.chevron.down").font(.footnote.weight(.semibold))
                        Spacer(minLength: 0)
                    }
                    .frame(maxWidth: .infinity, minHeight: Tema.areaTocco, alignment: .leading)
                    .contentShape(Rectangle())
                }
                .disabled(inCorso)
                .accessibilityLabel(Catalogo.Lega.tuaSquadra)
                .accessibilityValue(scelta)
                Button { Task { await salva() } } label: {
                    Text(Catalogo.Pav.questaMia).frame(maxWidth: .infinity, minHeight: Tema.areaTocco)
                }
                .pulsanteVetro(prominente: true)
                .disabled(inCorso || scelta.isEmpty)
            } else {
                Text(Catalogo.Err.indicaSquadra)
                    .font(.subheadline).foregroundStyle(Color.testoSecondario)
                    .fixedSize(horizontal: false, vertical: true)
            }
            if let errore {
                Text(errore)
                    .font(.footnote).foregroundStyle(Color.attenzione)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .frame(maxWidth: 720, alignment: .leading)
        .frame(maxWidth: .infinity, alignment: .leading)
        .onAppear { scegliPrima() }
        .onChange(of: squadra.squadre.dato?.first?.nome) { _, _ in scegliPrima() }
    }

    /// Il menu parte dalla prima squadra dell'elenco, come il menu della web: «Questa è la mia» la sceglie con un tocco.
    private func scegliPrima() {
        guard let elenco = squadra.squadre.dato, !elenco.contains(where: { $0.nome == scelta }) else { return }
        scelta = elenco.first?.nome ?? ""
    }

    private func salva() async {
        inCorso = true
        defer { inCorso = false }
        errore = await squadra.scegli(scelta)
    }
}
