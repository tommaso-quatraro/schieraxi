"""«Metti in campo» dalla scheda di un giocatore che non è fra gli 11 (#643): chi può lasciargli il posto lo calcola il server.

Lo stesso ruolo, oppure un altro ruolo se il modulo che ne esce è ammesso dalla lega (la regola unica della scelta,
`scelte.motivo_non_valida`). Per ognuno il modulo dopo il cambio e la differenza di punti attesi (chi entra meno chi esce, la
stessa di «Sostituisci»). Nessuno per chi è già titolare, gioca un anticipo già cominciato, è infortunato o squalificato.
Rosa e regole inventate."""
from fanta import scelte
from fanta.regole import Regole

# id: (ruolo, punti attesi, stato delle probabili)
ROSA = {1: ("P", 4.0, None), 20: ("P", 3.0, None),
        2: ("D", 4.0, None), 3: ("D", 6.5, None), 4: ("D", 5.2, None), 5: ("D", 5.5, None), 21: ("D", 5.0, None),
        25: ("D", 6.0, "squalificato"),
        6: ("C", 6.0, None), 7: ("C", 5.0, None), 8: ("C", 5.5, None), 22: ("C", 5.8, None), 23: ("C", 7.0, "infortunato"),
        9: ("A", 7.0, None), 10: ("A", 4.5, None), 11: ("A", 6.0, None), 24: ("A", 6.2, None)}
TITOLARI = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]                   # 4-3-3


def _schede(rosa=ROSA) -> dict:
    """Come il campo `schede` di GET /api/formazione: chiavi testo."""
    return {str(i): {"id": i, "nome": f"Gioc{i}", "ruolo": r, "punti_attesi": p, "stato": s, "titolarita": "titolare"}
            for i, (r, p, s) in rosa.items()}


def _escono(entra, regole=None, fermi=(), titolari=TITOLARI) -> dict[int, dict]:
    uscite = scelte.chi_lascia_il_posto(entra, titolari, _schede(), regole or Regole(), fermi)
    return {u["esce"]: u for u in uscite}


def test_lo_stesso_ruolo_lascia_il_posto_senza_cambiare_modulo():
    escono = _escono(21)
    for i in (2, 3, 4, 5):
        assert escono[i]["modulo"] == "4-3-3" and escono[i]["cambia_modulo"] is False, escono[i]


def test_un_cambio_di_modulo_ammesso_dalla_lega_c_e_con_il_modulo_nuovo():
    """Un difensore entra al posto di un attaccante: 5-3-2, che la lega ammette."""
    escono = _escono(21)
    for i in (9, 10, 11):
        assert escono[i]["modulo"] == "5-3-2" and escono[i]["cambia_modulo"] is True, escono[i]


def test_un_cambio_di_modulo_non_ammesso_non_c_e():
    """Un difensore al posto di un centrocampista darebbe il 5-2-3, che la lega non ammette; nemmeno il portiere esce per lui."""
    escono = _escono(21)
    assert not {6, 7, 8, 1} & set(escono), escono
    assert set(escono) == {2, 3, 4, 5, 9, 10, 11}


def test_i_moduli_sono_quelli_delle_regole_della_lega():
    """Lo stesso cambio compare o sparisce con i moduli della lega: la regola è nella configurazione, non nel codice."""
    assert not {9, 10, 11} & set(_escono(21, Regole(moduli=["4-3-3", "4-4-2"])))
    assert {6, 7, 8} <= set(_escono(21, Regole(moduli=["4-3-3", "5-2-3"])))


def test_un_centrocampista_puo_entrare_per_un_difensore_o_per_un_attaccante():
    escono = _escono(22)
    assert {i: escono[i]["modulo"] for i in escono} == {2: "3-4-3", 3: "3-4-3", 4: "3-4-3", 5: "3-4-3", 6: "4-3-3",
                                                         7: "4-3-3", 8: "4-3-3", 9: "4-4-2", 10: "4-4-2", 11: "4-4-2"}


def test_il_portiere_entra_solo_al_posto_del_portiere():
    assert set(_escono(20)) == {1}


def test_la_differenza_e_quella_di_sostituisci_e_il_migliore_cambio_e_in_cima():
    """Chi entra meno chi esce, sui punti attesi delle schede: lo stesso numero, con il segno girato, che «Sostituisci» mostra
    dalla scheda del titolare. In cima il cambio che fa guadagnare di più."""
    uscite = scelte.chi_lascia_il_posto(21, TITOLARI, _schede(), Regole())
    assert [u["esce"] for u in uscite] == [2, 10, 4, 5, 11, 3, 9]
    differenze = {u["esce"]: u["differenza"] for u in uscite}
    assert differenze[2] == 1.0 and differenze[3] == -1.5 and differenze[4] == -0.2 and differenze[10] == 0.5


def test_chi_gioca_un_anticipo_gia_cominciato_non_esce_e_non_entra():
    assert 3 not in _escono(21, fermi=[3])
    assert _escono(21, fermi=[21]) == {}


def test_infortunati_e_squalificati_non_entrano():
    assert _escono(23) == {}
    assert _escono(25) == {}


def test_un_titolare_o_uno_che_non_e_della_rosa_non_ha_nessuno_da_far_uscire():
    assert _escono(2) == {}
    assert _escono(999) == {}
