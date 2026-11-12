"""Le decisioni in cima alla Formazione (#673, decisione 1 del proprietario): il campo `decisione` delle voci di `da_fare`.

Lo segna il server, come i consigli: i client (web, iPhone) mostrano le prime due voci con il campo che hanno ancora senso con la
formazione in pagina, senza una regola loro. La regola è quella che la web applicava da sola (`dfVera` e `dfDecisioni` di
fanta/web/dafare.js, #616); i casi sono quelli dei test nel browser della Formazione unica (tests/browser/test_formazione_unica.py).
"""
import pytest

from fanta import da_fare

CAMBIO = {"giocatore": {"id": 5, "nome": "Rossi"}, "alternativa": {"id": 12, "nome": "Riserva", "ruolo": "C", "punti_attesi": 6.0}}


def _voce(id: str, tipo: str, priorita: int = 2, **extra) -> dict:
    return {"id": id, "tipo": tipo, "testo": f"Testo di {id}.", "priorita": priorita, "azione": "Fai",
            "destinazione": {"scheda": "formazione", "sezione": None}, **extra}


def scoperto(ruolo: str, priorita: int = 1) -> dict:
    return _voce(f"copertura:{ruolo}", "copertura", priorita, reparto=ruolo, livello="scoperto")


def cambio(priorita: int = 2) -> dict:
    return _voce("dubbio:5", "dubbio", priorita, **CAMBIO)


def rose(priorita: int = 2) -> dict:
    return _voce("rose-vecchie", "rose", priorita)


def dati_fermi() -> dict:
    return _voce("dati-vecchi", "server", 2)


def decisioni(voci: list[dict]) -> list[str]:
    """Gli id delle voci segnate come decisioni, nel loro ordine (`decisione` 1, 2, …)."""
    segnate = [v for v in da_fare.segna_decisioni(voci) if "decisione" in v]
    return [v["id"] for v in sorted(segnate, key=lambda v: v["decisione"])]


def test_solo_le_voci_che_chiedono_di_fare_qualcosa_sono_decisioni():
    voci = [
        _voce("svincolato:7", "svincolato", 3), _voce("scambio:Altri", "scambio", 3), _voce("diario:8", "diario", 3),
        _voce("dubbio:4", "dubbio", 2, giocatore={"id": 4, "nome": "Verdi"}),          # resta titolare: nessun cambio da fare
        _voce("formazione:9", "formazione", 1),                                          # «non l'hai salvata»: il salvataggio è automatico
        _voce("consigliata:9", "formazione", 2), cambio(), _voce("certificato", "certificato", 1),
        _voce("primo-avvio", "primo_avvio", 3), rose(), dati_fermi(),
    ]
    # prima l'urgente, poi le altre nell'ordine della lista (quella vera è già in ordine di priorità)
    assert decisioni(voci) == ["certificato", "consigliata:9", "dubbio:5", "primo-avvio", "rose-vecchie", "dati-vecchi"]
    senza = {v["id"] for v in da_fare.segna_decisioni(voci) if "decisione" not in v}
    assert senza == {"svincolato:7", "scambio:Altri", "diario:8", "dubbio:4", "formazione:9"}


def test_i_posti_partono_da_uno_e_sono_interi():
    segnate = da_fare.segna_decisioni([rose(), cambio()])
    assert sorted(v["decisione"] for v in segnate) == [1, 2]
    assert all(type(v["decisione"]) is int for v in segnate)


# Per ogni caso: le voci del server (in quest'ordine) e le decisioni, dalla prima.
CASI = {
    # il reparto scoperto prende un posto solo, e quello urgente sta in cima
    "due reparti scoperti urgenti e le rose": ([scoperto("P"), scoperto("D"), rose()], ["copertura:P", "rose-vecchie"]),
    # «nessun portiere» è urgente, il cambio e le rose no
    "nessun portiere urgente, un cambio e le rose non urgenti": ([scoperto("P"), cambio(), rose()],
                                                                ["copertura:P", "dubbio:5", "rose-vecchie"]),
    # conta l'urgenza, non il posto nella lista
    "due righe non urgenti e, in fondo, nessun portiere urgente": ([rose(), dati_fermi(), scoperto("P")],
                                                                   ["copertura:P", "rose-vecchie", "dati-vecchi"]),
    # fra le urgenti prima quelle con un'azione: con due di loro il reparto scoperto scende al terzo posto
    "due righe urgenti con un'azione e nessun portiere urgente": ([scoperto("P"), cambio(1), rose(1)],
                                                                  ["dubbio:5", "rose-vecchie", "copertura:P"]),
    # niente di urgente: prima le righe con un'azione, il reparto senza ricambi dopo
    "niente di urgente": ([scoperto("D", 2), cambio(), rose()], ["dubbio:5", "rose-vecchie", "copertura:D"]),
}


@pytest.mark.parametrize("caso", list(CASI))
def test_prima_le_urgenti_e_il_reparto_scoperto_prende_un_posto_solo(caso):
    voci, attese = CASI[caso]
    assert decisioni(voci) == attese


def test_l_ordine_della_lista_non_cambia_e_i_campi_di_prima_restano():
    voci = [scoperto("P"), cambio(), rose()]
    segnate = da_fare.segna_decisioni([dict(v) for v in voci])
    assert [v["id"] for v in segnate] == [v["id"] for v in voci]
    for prima, dopo in zip(voci, segnate):
        assert {k: x for k, x in dopo.items() if k != "decisione"} == prima


def test_una_lista_vuota_resta_vuota():
    assert da_fare.segna_decisioni([]) == []
