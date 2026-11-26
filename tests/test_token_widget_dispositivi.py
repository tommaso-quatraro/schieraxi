"""Un token del widget per dispositivo (26/11/2026): lo stesso account su iPhone e iPad ha due widget, ognuno con il suo token legato
alla sessione che l'ha chiesto. Entrare o uscire da un dispositivo non tocca il widget dell'altro (prima il server ne teneva uno per
utente: il secondo dispositivo spegneva il widget del primo, che diceva «Tocca per collegare»). Nomi e dati inventati."""
import contextlib
from datetime import datetime, timedelta, timezone

from fanta import account
from test_account_http import cliente
from test_token_widget import _altro_dispositivo, due_utenti, token_di, widget  # noqa: F401  (fixture)


def _vale(token) -> bool:
    c, h = widget(token)
    r = c.get("/api/widget", headers=h)
    assert r.status_code in (200, 401), r.text
    return r.status_code == 200


def _quanti() -> int:
    with contextlib.closing(account.apri()) as db:
        return db.execute("SELECT COUNT(*) FROM token_widget").fetchone()[0]


def test_due_dispositivi_dello_stesso_account_hanno_due_token(due_utenti):  # noqa: F811
    a, _ = due_utenti
    iphone = token_di(a)
    ipad = token_di(_altro_dispositivo())
    assert iphone != ipad
    assert _vale(iphone) and _vale(ipad), "il token nuovo dell'iPad non spegne quello dell'iPhone"
    assert _quanti() == 2


def test_rinnovare_sostituisce_solo_il_token_dello_stesso_dispositivo(due_utenti):  # noqa: F811
    a, _ = due_utenti
    altro = _altro_dispositivo()
    primo, ipad = token_di(a), token_di(altro)
    secondo = token_di(a)
    assert not _vale(primo), "il token di prima dello stesso dispositivo non vale più"
    assert _vale(secondo) and _vale(ipad)
    assert _quanti() == 2


def test_l_uscita_di_un_dispositivo_lascia_il_widget_dell_altro(due_utenti):  # noqa: F811
    a, _ = due_utenti
    altro = _altro_dispositivo()
    iphone, ipad = token_di(a), token_di(altro)
    assert altro.post("/api/account/esci").status_code == 200
    assert not _vale(ipad), "«Esci» dall'iPad chiude il suo widget"
    assert _vale(iphone), "e lascia quello dell'iPhone"
    assert a.get("/api/account/me").status_code == 200


def test_la_revoca_delle_app_gia_installate_tocca_solo_questo_dispositivo(due_utenti):  # noqa: F811
    """Le app di prima, a «Esci», mandano `DELETE /api/account/token-widget` prima di uscire: toglie solo il token di quella
    sessione, non quello dell'altro dispositivo."""
    a, _ = due_utenti
    altro = _altro_dispositivo()
    iphone, ipad = token_di(a), token_di(altro)
    assert altro.delete("/api/account/token-widget").json() == {"revocato": True}
    assert not _vale(ipad)
    assert _vale(iphone)
    assert altro.delete("/api/account/token-widget").json() == {"revocato": False}


def test_lo_stato_e_quello_del_token_di_questo_dispositivo(due_utenti):  # noqa: F811
    a, _ = due_utenti
    token_di(a)
    altro = _altro_dispositivo()
    assert altro.get("/api/account/token-widget").json() == {"presente": False}
    token_di(altro)
    assert altro.get("/api/account/token-widget").json()["presente"] is True
    assert altro.delete("/api/account/token-widget").json() == {"revocato": True}
    assert altro.get("/api/account/token-widget").json() == {"presente": False}
    assert a.get("/api/account/token-widget").json()["presente"] is True


def test_un_token_senza_legame_resta_finche_non_si_esce(due_utenti):  # noqa: F811
    """Le app già installate: un token nato quando il server ne teneva uno per utente (senza legame) vale ancora, anche dopo che un
    altro dispositivo ne ha chiesto uno o ha mandato il DELETE delle app di prima."""
    a, _ = due_utenti
    vecchio = token_di(a)
    with contextlib.closing(account.apri()) as db:
        db.execute("UPDATE token_widget SET sessione_id = NULL")
        db.commit()
    altro = _altro_dispositivo()
    nuovo = token_di(altro)
    assert _vale(vecchio) and _vale(nuovo)
    assert altro.delete("/api/account/token-widget").json() == {"revocato": True}
    assert _vale(vecchio)


def test_l_uscita_toglie_anche_i_token_senza_legame(due_utenti):  # noqa: F811
    """Un token senza legame (nato prima del 20/11/2026) non si sa di quale dispositivo sia: «Esci» da qualsiasi sessione
    dell'account lo toglie, se no resterebbe valido per mesi dopo l'uscita. Il dispositivo che lo usava prende un 401, lascia il
    segnale e la sua app ne chiede uno nuovo; il token legato all'altro dispositivo resta."""
    a, b = due_utenti
    vecchio = token_di(a)
    with contextlib.closing(account.apri()) as db:
        db.execute("UPDATE token_widget SET sessione_id = NULL")
        db.commit()
    altro = _altro_dispositivo()
    ipad, di_bruno = token_di(altro), token_di(b)
    assert a.post("/api/account/esci").status_code == 200
    assert not _vale(vecchio), "dopo «Esci» il token senza legame non vale più"
    assert _vale(ipad), "quello legato all'altro dispositivo resta"
    assert _vale(di_bruno), "e quello di un altro account non si tocca"


def test_un_nuovo_token_toglie_quelli_di_sessioni_chiuse_o_scadute(multiutente, dati_isolati):
    """Al POST del token si tolgono i token dell'utente legati a sessioni revocate (un nuovo accesso sullo stesso dispositivo chiude
    la sessione di prima senza toccare il suo widget) o scadute: nessuno li userà più. Quelli di sessioni aperte restano."""
    adesso = datetime(2026, 11, 26, 10, 0, tzinfo=timezone.utc)
    with contextlib.closing(account.apri()) as db:
        db.execute("INSERT INTO utenti (nome_utente, password_hash, recupero_hash, creato) VALUES ('x', 'h', 'r', '2026-01-01T00:00:00')")
        db.commit()
        chiusa = account._apri_sessione(db, 1, "iphone", adesso)
        t_chiusa, _ = account.crea_token_widget(db, 1, adesso, sessione=chiusa)
        account.esci(db, chiusa)                                   # come il nuovo accesso sullo stesso dispositivo
        scaduta = account._apri_sessione(db, 1, "ipad", adesso - timedelta(days=40))
        t_scaduta, _ = account.crea_token_widget(db, 1, adesso - timedelta(days=40), sessione=scaduta)
        aperta = account._apri_sessione(db, 1, "mac", adesso)
        t_aperta, _ = account.crea_token_widget(db, 1, adesso, sessione=aperta)
        nuova = account._apri_sessione(db, 1, "iphone", adesso)
        t_nuova, _ = account.crea_token_widget(db, 1, adesso, sessione=nuova)
        assert account.utente_da_token_widget(db, t_chiusa, adesso) is None
        assert account.utente_da_token_widget(db, t_scaduta, adesso) is None
        assert account.utente_da_token_widget(db, t_aperta, adesso) is not None
        assert account.utente_da_token_widget(db, t_nuova, adesso) is not None
        assert db.execute("SELECT COUNT(*) FROM token_widget").fetchone()[0] == 2


def test_al_massimo_dieci_token_per_utente(multiutente, dati_isolati):
    """Un tetto di 10 token per utente: oltre, se ne va quello usato meno di recente."""
    adesso = datetime(2026, 11, 26, 10, 0, tzinfo=timezone.utc)
    with contextlib.closing(account.apri()) as db:
        db.execute("INSERT INTO utenti (nome_utente, password_hash, recupero_hash, creato) VALUES ('x', 'h', 'r', '2026-01-01T00:00:00')")
        db.commit()
        token = []
        for i in range(12):
            quando = adesso + timedelta(minutes=i)
            sessione = account._apri_sessione(db, 1, f"dispositivo {i}", quando)
            token.append(account.crea_token_widget(db, 1, quando, sessione=sessione)[0])
        dopo = adesso + timedelta(minutes=30)
        assert db.execute("SELECT COUNT(*) FROM token_widget").fetchone()[0] == account.MAX_TOKEN_WIDGET == 10
        assert [account.utente_da_token_widget(db, t, dopo) is not None for t in token] == [False, False] + [True] * 10


def test_esci_da_tutti_chiude_i_widget_di_tutti_i_dispositivi(due_utenti):  # noqa: F811
    a, b = due_utenti
    altro = _altro_dispositivo()
    iphone, ipad, di_bruno = token_di(a), token_di(altro), token_di(b)
    assert a.post("/api/account/esci-da-tutti").status_code == 200
    assert not _vale(iphone) and not _vale(ipad)
    assert _vale(di_bruno), "il widget di un altro account non si tocca"


def test_il_token_di_un_dispositivo_e_dell_account_giusto(due_utenti):  # noqa: F811
    a, b = due_utenti
    ta, tb = token_di(a), token_di(b)
    with contextlib.closing(account.apri()) as db:
        assert account.utente_da_token_widget(db, ta).nome_utente == "anna"
        assert account.utente_da_token_widget(db, tb).nome_utente == "bruno"


def test_l_ultimo_uso_si_scrive_sul_token_usato(multiutente, dati_isolati):
    """Con più token per utente l'ultimo uso si segna sul token che ha letto, non sugli altri dello stesso account."""
    adesso = datetime(2026, 11, 26, 10, 0, tzinfo=timezone.utc)
    with contextlib.closing(account.apri()) as db:
        db.execute("INSERT INTO utenti (nome_utente, password_hash, recupero_hash, creato) VALUES ('x', 'h', 'r', '2026-01-01T00:00:00')")
        db.commit()
        uno = account._apri_sessione(db, 1, "iphone", adesso)
        due = account._apri_sessione(db, 1, "ipad", adesso)
        t1, _ = account.crea_token_widget(db, 1, adesso, sessione=uno)
        t2, _ = account.crea_token_widget(db, 1, adesso, sessione=due)
        dopo = adesso + timedelta(hours=3)
        assert account.utente_da_token_widget(db, t1, dopo) is not None
        usi = dict(db.execute("SELECT token_hash, ultimo_uso FROM token_widget").fetchall())
        assert usi[account._hash_token(t1)] == account._testo(dopo)
        assert usi[account._hash_token(t2)] == account._testo(adesso)


def test_i_token_scaduti_dell_utente_se_ne_vanno_con_il_prossimo(multiutente, dati_isolati):
    """Un token scaduto non vale più: quando lo stesso utente ne chiede uno nuovo, la sua riga si toglie (niente righe morte)."""
    adesso = datetime(2026, 11, 26, 10, 0, tzinfo=timezone.utc)
    with contextlib.closing(account.apri()) as db:
        db.execute("INSERT INTO utenti (nome_utente, password_hash, recupero_hash, creato) VALUES ('x', 'h', 'r', '2026-01-01T00:00:00')")
        db.commit()
        vecchia = account._apri_sessione(db, 1, "iphone", adesso - timedelta(days=100))
        account.crea_token_widget(db, 1, adesso - timedelta(days=100), sessione=vecchia)
        nuova = account._apri_sessione(db, 1, "ipad", adesso)
        account.crea_token_widget(db, 1, adesso, sessione=nuova)
        assert db.execute("SELECT COUNT(*) FROM token_widget").fetchone()[0] == 1


def test_bloccare_o_eliminare_toglie_i_token_di_tutti_i_dispositivi(multiutente, dati_isolati):
    """Con la #933: bloccare un account (`esci_da_tutti`) o eliminarlo (cascata) toglie tutti i suoi token del widget, uno per
    sessione e anche quello senza legame, non solo uno. Le righe spariscono davvero: non basta che `_utente_attivo` fermi un
    bloccato. I token di un altro account restano."""
    adesso = datetime(2026, 11, 26, 10, 0, tzinfo=timezone.utc)
    with contextlib.closing(account.apri()) as db:
        for nome in ("luca", "sara", "anna"):
            db.execute("INSERT INTO utenti (nome_utente, password_hash, recupero_hash, creato) VALUES (?, 'h', 'r', '2026-01-01T00:00:00')",
                       (nome,))
        db.commit()
        token = {}
        for uid in (1, 2, 3):
            token[uid] = [account.crea_token_widget(db, uid, adesso, sessione=account._apri_sessione(db, uid, disp, adesso))[0]
                          for disp in ("iphone", "ipad")]
        db.execute("UPDATE token_widget SET sessione_id = NULL WHERE utente_id IN (1, 2) AND id IN "
                   "(SELECT MIN(id) FROM token_widget GROUP BY utente_id)")      # uno senza legame, come quelli di prima del 20/11
        db.commit()

        def righe(uid):
            return db.execute("SELECT COUNT(*) FROM token_widget WHERE utente_id = ?", (uid,)).fetchone()[0]

        assert (righe(1), righe(2), righe(3)) == (2, 2, 2)
        account.blocca(db, 1, adesso=adesso)
        assert righe(1) == 0, "bloccato: via tutti i suoi token"
        account.elimina(db, 2)
        assert righe(2) == 0, "eliminato: via tutti i suoi token"
        assert all(account.utente_da_token_widget(db, t, adesso) is None for t in token[1] + token[2])
        assert righe(3) == 2 and all(account.utente_da_token_widget(db, t, adesso) is not None for t in token[3])


def test_senza_sessione_non_si_crea_ne_si_revoca(due_utenti):  # noqa: F811
    assert cliente().post("/api/account/token-widget").status_code == 401
    assert cliente().delete("/api/account/token-widget").status_code == 401
