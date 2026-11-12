import Foundation

/// «Perché è titolare» nella scheda di un titolare, come `percheTitolare` di app.js (#616): la riga del server (`perche_scelta`
/// del modulo, `fanta/perche_scelta.py`) e, se manca (server vecchio), la frase degli incerti (`incerti`: titolare incerto con la
/// riserva che gioca quasi di sicuro). Chi chiama decide quando si mostra: solo sulla consigliata, a formazione aperta.
enum PercheTitolare {
    /// nil se non c'è niente da dire: nessuna riga del server e nessun incerto con una riserva che la Formazione conosce.
    static func testo(_ modulo: OpzioneModulo, id: Int, schede: [String: Giocatore]) -> String? {
        let riga = (modulo.percheScelta ?? []).first { r in
            r.titolare == id && !(r.testo ?? "").trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        }
        if let testo = riga?.testo { return testo }
        guard let incerto = (modulo.incerti ?? []).first(where: { $0.titolare == id }),
              let titolare = schede[String(id)], let r = incerto.riserva, let riserva = schede[String(r)] else { return nil }
        return Catalogo.Formazione.incerto(p: "\(Formato.percento(titolare.pVoto))%", riserva: riserva.nome)
    }
}
