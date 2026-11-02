import Foundation

/// Un server finto «lento» a comando: la richiesta che passa dal cancello resta ferma finché il test non chiama `apri()`.
/// Il test sa anche quando la richiesta è arrivata (`richiestaArrivata()`), così controlla lo stato a metà salvataggio senza attese a tempo.
actor Cancello {
    private var arrivata = false
    private var aperto = false
    private var chiAspettaLArrivo: [CheckedContinuation<Void, Never>] = []
    private var chiAspettaLApertura: [CheckedContinuation<Void, Never>] = []

    /// Dal server finto: segna che la richiesta è arrivata e resta fermo finché il cancello non si apre.
    func passa() async {
        arrivata = true
        chiAspettaLArrivo.forEach { $0.resume() }
        chiAspettaLArrivo.removeAll()
        guard !aperto else { return }
        await withCheckedContinuation { chiAspettaLApertura.append($0) }
    }

    /// Dal test: aspetta che la richiesta sia arrivata al server finto.
    func richiestaArrivata() async {
        guard !arrivata else { return }
        await withCheckedContinuation { chiAspettaLArrivo.append($0) }
    }

    /// Dal test: lascia andare la risposta.
    func apri() {
        aperto = true
        chiAspettaLApertura.forEach { $0.resume() }
        chiAspettaLApertura.removeAll()
    }
}
