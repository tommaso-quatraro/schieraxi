"""Revisione IA (.github/workflows/revisione.yml): cosa legge Claude e cosa esce nella sintesi pubblicata.

- Claude legge il codice della PR (diff preparato dal job e file del checkout), non la conversazione della PR.
- Le letture restano nella cartella del checkout.
- La sintesi pubblicata passa da un filtro che toglie ciò che somiglia a un token o a un segreto.
Decisione: docs/decisioni/0007-revisione-ia-in-ci.md. I token qui sotto sono inventati e composti a pezzi."""
import re

from test_workflow_revisione import SKILL, _cancello, _testo


def _strumenti(opzione: str) -> list[str]:
    m = re.search(rf'--{opzione} "([^"]+)"', _testo())
    assert m, f"manca --{opzione}"
    return m.group(1).split(",")


def _passi() -> list[str]:
    return _testo().split("      - ")[1:]


def test_claude_non_ha_comandi_gh_ne_bash():
    testo = _testo()
    assert "gh pr view" not in testo and "--comments" not in testo
    assert not [s for s in _strumenti("allowedTools") if s.startswith("Bash")]
    for vietato in ("Bash", "Write", "Edit", "NotebookEdit", "WebFetch", "WebSearch", "Task"):
        assert vietato in _strumenti("disallowedTools"), vietato


def test_le_letture_restano_nel_checkout():
    permessi = _strumenti("allowedTools")
    for libero in ("Read", "Grep", "Glob"):
        assert libero not in permessi, f"{libero} senza percorso legge anche fuori dal checkout"
    assert "Read(./**)" in permessi
    negati = _strumenti("disallowedTools")
    for fuori in ("Read(//proc/**)", "Read(//etc/**)", "Read(//tmp/**)", "Read(//home/runner/work/_temp/**)",
                  "Read(~/.claude/**)"):
        assert fuori in negati, fuori


def test_il_diff_lo_prepara_il_job_prima_di_claude():
    passi = _passi()
    indice = next(i for i, p in enumerate(passi) if "name: Diff della PR" in p)
    claude = next(i for i, p in enumerate(passi) if "anthropics/claude-code-action@" in p)
    assert indice < claude
    passo = passi[indice]
    assert "steps.segreto.outputs.presente == 'true'" in passo
    assert "rm -rf .revisione-ia" in passo, "una cartella con lo stesso nome portata dalla PR si butta"
    assert "git diff" in passo and ".revisione-ia/diff.patch" in passo and ".revisione-ia/file.txt" in passo
    assert "gh " not in passo, "il diff viene dal checkout, non dalla conversazione della PR"
    checkout = next(p for p in passi if "actions/checkout@" in p)
    assert "fetch-depth: 2" in checkout, "serve il genitore del commit di unione per il diff"
    prompt = passi[claude][passi[claude].index("prompt:"):passi[claude].index("claude_args:")]
    assert ".revisione-ia/diff.patch" in prompt


def test_la_skill_lavora_sul_diff_preparato():
    testo = SKILL.read_text(encoding="utf-8")
    assert ".revisione-ia/diff.patch" in testo and ".revisione-ia/file.txt" in testo
    assert "gh pr view" not in testo and "gh pr diff" not in testo


def _sintesi(tmp_path, sintesi: str, bloccanti: int = 0) -> str:
    import json
    _cancello(json.dumps({"bloccanti": bloccanti, "sintesi": sintesi}), tmp_path)
    return (tmp_path / "sintesi.md").read_text(encoding="utf-8")


FINTI = {
    "anthropic": "sk-" + "ant-oat01-" + "Ab3dE5gH7jK9mN1pQ3sT5vW7yZ9bC1dF",
    "github": "gh" + "p_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8",
    "github_pat": "github" + "_pat_" + "11ABCDEFG0123456789_abcdefghijklmnopqrstuvwxyz",
    "widget": "fw" + "_" + "Zx9Yw8Vu7Ts6Rq5Po4Nm3",
    "jwt": "ey" + "JhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0In0.c2lnbmF0dXJhLWZpbnRh",
    "aws": "AK" + "IA" + "ABCDEFGHIJ012345",
    "lungo": "Q2xhdWRl" + "VG9rZW5GaW50bzEyMzQ1Njc4OTA",
}


def test_la_sintesi_pubblicata_non_porta_token(tmp_path):
    for nome, finto in FINTI.items():
        uscita = _sintesi(tmp_path, f"Vedi `fanta/server.py:12`, valore {finto} trovato.")
        assert finto not in uscita, nome
        assert finto[:12] not in uscita, nome
        assert "fanta/server.py:12" in uscita and "[tolto]" in uscita, nome
    riepilogo = (tmp_path / "riepilogo.md").read_text(encoding="utf-8")
    assert not [n for n, f in FINTI.items() if f in riepilogo], "anche il riepilogo del job è filtrato"


def test_il_filtro_toglie_valori_di_variabili_segrete_e_chiavi(tmp_path):
    chiave = "-----BEGIN " + "PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASC\n-----END " + "PRIVATE KEY-----"
    uscita = _sintesi(tmp_path, f"CLAUDE_CODE_OAUTH_TOKEN=valoreSegreto99 e GITHUB_TOKEN: altroValore77\n{chiave}\nfine")
    assert "valoreSegreto99" not in uscita and "altroValore77" not in uscita
    assert "MIIEvQIBADANBgkqhkiG9w0BAQEFAASC" not in uscita and "fine" in uscita
    assert "CLAUDE_CODE_OAUTH_TOKEN" in uscita, "il nome della variabile resta, sparisce il valore"


def test_il_filtro_lascia_il_testo_normale(tmp_path):
    normale = ("**Bloccante:** `tests/test_workflow_revisione_letture.py:40`, `script/squadra/brief.py:77`; "
               "commit 0123abc; giornata 12 del 2026-11-06; ramo sicurezza-ci-brief-479; "
               "funzione test_il_filtro_lascia_il_testo_normale_anche_con_nomi_lunghi_123.")
    uscita = _sintesi(tmp_path, normale)
    assert normale in uscita and "[tolto]" not in uscita


def test_il_filtro_non_cambia_il_cancello(tmp_path):
    codice, _ = _cancello('{"bloccanti": 1, "sintesi": "' + FINTI["github"] + '"}', tmp_path)
    assert codice != 0
    codice, _ = _cancello('{"bloccanti": 0, "sintesi": "' + FINTI["github"] + '"}', tmp_path)
    assert codice == 0
