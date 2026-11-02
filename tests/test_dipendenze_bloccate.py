"""requirements.txt e requirements-dev.txt: versioni fisse e hash per ogni libreria (li scrive script/blocca_dipendenze.py).

Senza rete: si controlla solo la forma dei file e che corrispondano agli elenchi scritti a mano (requirements*.in)."""
import re
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
RIGA = re.compile(r'^([a-z0-9][a-z0-9._-]*)==([^ ;\\]+)(?: ; (python_version (?:<|>=) "\d+\.\d+"))?$')
HASH = re.compile(r"^--hash=sha256:[0-9a-f]{64}$")


def _canonico(nome: str) -> str:
    return re.sub(r"[-_.]+", "-", nome).lower()


def _bloccati(nome_file: str) -> dict[str, dict[str, str]]:
    """nome -> {marcatore: versione} letti dal file, unendo le righe che finiscono con «\\»."""
    testo = (RADICE / nome_file).read_text(encoding="utf-8").replace("\r\n", "\n").replace("\\\n", " ")
    out: dict[str, dict[str, str]] = {}
    for riga in testo.splitlines():
        riga = riga.split("#", 1)[0].strip()
        if not riga:
            continue
        req, _, resto = riga.partition(" --hash=")
        m = RIGA.match(req.strip())
        assert m, f"{nome_file}: riga senza versione fissa: {riga[:60]}"
        hs = ("--hash=" + resto).split()
        assert all(HASH.match(h) for h in hs), f"{nome_file}: {m.group(1)} senza hash validi"
        marcatore = m.group(3) or ""
        assert marcatore not in out.get(m.group(1), {}), f"{nome_file}: {m.group(1)} due volte"
        out.setdefault(m.group(1), {})[marcatore] = m.group(2)
    return out


def _elenco(nome_file: str) -> dict[str, tuple[str, str]]:
    out = {}
    for riga in (RADICE / nome_file).read_text(encoding="utf-8").splitlines():
        riga = riga.split("#", 1)[0].strip()
        if riga:
            req, _, marcatore = riga.partition(";")
            nome = re.split(r"[<>=!~\[ ]", req.strip(), maxsplit=1)[0]
            out[_canonico(nome)] = (req.split("==", 1)[1].strip() if "==" in req else "", marcatore.strip())
    return out


def test_ogni_libreria_ha_versione_fissa_e_hash():
    app, dev = _bloccati("requirements.txt"), _bloccati("requirements-dev.txt")
    assert len(app) > 20 and dev
    assert not set(app) & set(dev), "le librerie dell'app non si ripetono nel file dei test"


def test_le_versioni_doppie_coprono_ogni_python_una_volta_sola():
    """Con due righe per lo stesso pacchetto i marcatori sono complementari (< X e >= X): pip ne prende sempre una sola."""
    for nome, varianti in {**_bloccati("requirements.txt"), **_bloccati("requirements-dev.txt")}.items():
        if len(varianti) > 1:
            assert len(varianti) == 2 and "" not in varianti, nome
            minore, maggiore = sorted(varianti)
            assert maggiore == minore.replace("<", ">="), nome


def test_gli_elenchi_scritti_a_mano_sono_tutti_bloccati():
    app, dev = _bloccati("requirements.txt"), _bloccati("requirements-dev.txt")
    assert set(_elenco("requirements.in")) <= set(app)
    assert set(_elenco("requirements-dev.in")) <= set(app) | set(dev)
    for nome, (versione, marcatore) in _elenco("requirements-vincoli.in").items():
        assert (app.get(nome) or dev.get(nome))[marcatore] == versione, nome


def test_i_file_dicono_come_si_rigenerano_e_installano():
    for f in ("requirements.txt", "requirements-dev.txt"):
        testo = (RADICE / f).read_text(encoding="utf-8")
        assert testo.startswith("# File generato da script/blocca_dipendenze.py") and "--require-hashes" in testo


def test_il_server_installa_le_librerie_solo_con_gli_hash():
    t = (RADICE / "script" / "server" / "aggiorna-app.sh").read_text(encoding="utf-8")
    assert "-m pip install -q --require-hashes -r" in t
