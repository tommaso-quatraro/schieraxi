"""Prove del controllo dei residui (script/controlli/anti_residui.py).

Le stringhe pericolose si costruiscono a pezzi: il file e' esente dal controllo, ma e' meglio non averle in chiaro."""
import importlib.util
import shutil
import subprocess
from pathlib import Path

import pytest

QUI = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("anti_residui", QUI / "anti_residui.py")
ar = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ar)

NOME_VECCHIO = "fanta" + "claude"
PC = "C:" + "\\" + "Users" + "\\" + "mario" + "\\" + "progetto"
RETE = "tail" + "scale"
GIT = shutil.which("git")


def righe(testo: str, rel: str = "fanta/x.py", parole=None) -> list[str]:
    return ar.scansiona_testo(rel, testo.encode("utf-8"), parole or [])


def test_testo_pulito_non_da_problemi():
    assert righe("x = 1\nnome = 'Squadra Esempio'\nurl = 'https://pc.example.ts.net'\n") == []


def test_percorso_nome_vecchio_e_rete_privata_con_numero_di_riga():
    problemi = "\n".join(righe(f"a = '{PC}'\nb = '{NOME_VECCHIO}'\nc = '{RETE} pronto'\n"))
    assert "fanta/x.py:1: percorso di una cartella del PC" in problemi
    assert "fanta/x.py:2: nome vecchio dell'app" in problemi
    assert "fanta/x.py:3: infrastruttura personale" in problemi


def test_indirizzo_ts_net_vero_si_finto_no():
    # l'indirizzo e' spezzato nel sorgente: lo script di esportazione non lo deve riscrivere
    assert any("indirizzo *.ts.net vero" in p for p in righe("h = 'https://" + "pc.reale.ts.net'\n"))
    assert righe("h = 'https://pi.example.ts.net'\n") == []


def test_segreti_e_email_di_fornitori():
    token = "ghp_" + "a" * 36
    mail = "x" + "@" + "gmail.com"
    problemi = "\n".join(righe(f"t = '{token}'\nm = '{mail}'\nf = 'logo@2x.png'\n"))
    assert "token GitHub" in problemi and "email non ammessa" in problemi
    assert ":3:" not in problemi                       # «logo@2x.png» non e' un'email


def test_email_noreply_ammessa_nei_commit():
    assert ar.EMAIL_AMMESSA.search("123+utente@users.noreply.github.com")
    assert not ar.EMAIL_AMMESSA.search("persona@gmail.com")


def test_indirizzi_di_servizio_ammessi_nei_testi_e_nei_commit():
    chiocciola = "@"
    for mail in ("noreply" + chiocciola + "github.com", "support" + chiocciola + "github.com", "noreply" + chiocciola + "anthropic.com"):
        assert righe(f"Co-Authored-By: Qualcuno <{mail}>\n", "docs/x.md") == [], mail
        assert ar.EMAIL_AMMESSA.search(mail), mail
    # solo quegli indirizzi esatti: un altro indirizzo dello stesso dominio resta un problema
    assert any("email non ammessa" in p for p in righe("m = 'persona" + chiocciola + "github.com'\n"))
    assert not ar.EMAIL_AMMESSA.search("persona" + chiocciola + "anthropic.com")


def test_runner_propri_bloccati():
    assert any("runner propri" in p for p in righe("runs-on: [self-hosted, fanta-pi]\n", "x.yml"))


def test_parole_private_lette_da_file_fuori_da_git_ma_non_stampate(tmp_path):
    elenco = tmp_path / "parole.txt"
    elenco.write_text("# commento\n\nParolaSegreta\nab\n", encoding="utf-8")
    parole = ar.parole_private(elenco)
    assert len(parole) == 1                           # «ab» e' troppo corta e il commento si salta
    problemi = righe("x = 'parolasegreta'\n", parole=parole)
    assert problemi == ["fanta/x.py:1: parola dell'elenco privato"]
    assert "ParolaSegreta" not in "\n".join(problemi)


def test_parole_private_anche_negli_indirizzi_e_nei_nomi_di_file(tmp_path):
    elenco = tmp_path / "parole.txt"
    elenco.write_text("Squadra Segreta\n", encoding="utf-8")
    parole = ar.parole_private(elenco)
    for forma in ("con=Squadra%20Segreta", "squadra+segreta", "squadra-segreta.png", "SQUADRA_SEGRETA", "squadrasegreta"):
        assert righe(f"x = '{forma}'\n", parole=parole) == ["fanta/x.py:1: parola dell'elenco privato"], forma
    assert righe("x = 'squadra di segreta'\n", parole=parole) == []


def test_elenco_privato_mancante_non_blocca_le_regole_generiche(tmp_path):
    assert ar.parole_private(tmp_path / "non-c-e.txt") == []


def test_nome_di_file_con_nome_vecchio_e_con_il_numero_di_titolari():
    assert ar.scansiona_nome(f"docs/{NOME_VECCHIO}.md", [])
    assert ar.scansiona_nome("fanta/chiede_undici_titolari.py", []) == []


def test_file_esenti_non_si_controllano_nel_contenuto():
    assert ar.scansiona_testo("script/controlli/anti_residui.py", ("'" + PC + "'").encode(), []) == []


def test_albero_di_una_cartella_non_git(tmp_path):
    (tmp_path / "a.txt").write_text(f"x {PC}\n", encoding="utf-8")
    (tmp_path / "b.txt").write_text("pulito\n", encoding="utf-8")
    assert ar.file_da_cartella(tmp_path) == ["a.txt", "b.txt"]
    assert len(ar.controlla_albero(tmp_path, [])) == 1


@pytest.mark.skipif(GIT is None, reason="git non installato")
def test_storia_e_contenuto_in_preparazione(tmp_path):
    def git(*args, email="noreply@users.noreply.github.com"):
        subprocess.run(["git", "-C", str(tmp_path), "-c", f"user.email={email}", "-c", "user.name=Prova", *args],
                       check=True, capture_output=True)

    subprocess.run(["git", "init", "-q", "-b", "main", str(tmp_path)], check=True, capture_output=True)
    (tmp_path / "a.txt").write_text("ok\n", encoding="utf-8")
    git("add", "a.txt")
    git("commit", "-q", "-m", "primo")
    assert ar.controlla_storia(tmp_path, []) == []

    (tmp_path / "b.txt").write_text(f"riga {PC}\n", encoding="utf-8")
    git("add", "b.txt")
    assert any("percorso di una cartella" in p for p in ar.controlla_staged(tmp_path, []))
    git("commit", "-q", "-m", "secondo", email="persona" + "@gmail.com")
    trovati = ar.controlla_storia(tmp_path, [])
    assert any("email del autore non ammessa" in p for p in trovati)
    assert any("percorso di una cartella" in p for p in trovati)
    # anche il CORPO del messaggio, non solo la prima riga
    elenco = tmp_path.parent / (tmp_path.name + "-parole.txt")
    elenco.write_text("Squadra Segreta\n", encoding="utf-8")
    git("commit", "-q", "--allow-empty", "-m", "terzo\n\nprova con=Squadra%20Segreta nel corpo")
    assert any("parola dell'elenco privato (nome o messaggio)" in p for p in ar.controlla_storia(tmp_path, ar.parole_private(elenco)))
