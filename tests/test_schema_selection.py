"""Skjemavalg: eksplisitt kontekst (argument, regler/manifest) — ikke innholdsfelt validering skal kreve.

Reproduksjon (kildegrunnlag 17.10.2026): en generator uten ID, med resten av generatorstrukturen,
ble klassifisert som referanse og passerte uten feil.
"""

import json
import textwrap
from pathlib import Path

import pytest

from src.validator import (
    GENERATOR_SCHEMA,
    REFERENCE_SCHEMA,
    main,
    validate_directory,
    validate_file,
)

GENERATOR_WITHOUT_ID = """\
    <!-- generators/uten-id.md -->
    NAVN: Eksempel
    STYRKE: 3

    ## BRUK
    Brukes til testing.

    ## REGLER
    - Alltid test.

    ## HVIS INPUT MANGLER
    Stopp.

    ## INPUT
    {{FELTNAVN}}
"""


def write(root: Path, rel: str, text: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(text), encoding="utf-8")
    return p


def test_generator_without_id_fails_without_explicit_schema(tmp_path):
    path = write(tmp_path, "uten-id.md", GENERATOR_WITHOUT_ID)
    result = validate_file(path)
    assert not result.ok
    assert any("ID:" in e for e in result.errors)


def test_generator_without_id_fails_through_directory_route(tmp_path):
    write(tmp_path, "generators/uten-id.md", GENERATOR_WITHOUT_ID)
    results = validate_directory(tmp_path)
    assert results and not all(r.ok for r in results)


def test_generator_without_id_fails_through_cli(tmp_path, capsys):
    write(tmp_path, "generators/uten-id.md", GENERATOR_WITHOUT_ID)
    assert main([str(tmp_path)]) == 1
    assert "ID:" in capsys.readouterr().out


def test_explicit_schema_argument_wins(tmp_path):
    path = write(tmp_path, "ref.md", "# Referanse\n\nTekst.\n")
    assert validate_file(path, schema=REFERENCE_SCHEMA).ok
    assert not validate_file(path, schema=GENERATOR_SCHEMA).ok


def test_rules_select_schema_by_path(tmp_path):
    write(tmp_path, "referanse/lov.md", "# Lov\n\nID: 7 er bare tekst.\n")
    write(tmp_path, "generators/uten-id.md", GENERATOR_WITHOUT_ID)
    rules = [("referanse/*", REFERENCE_SCHEMA), ("generators/*", GENERATOR_SCHEMA)]
    by_name = {r.path.name: r for r in validate_directory(tmp_path, rules=rules)}
    assert by_name["lov.md"].ok
    assert not by_name["uten-id.md"].ok


def test_unknown_file_under_rules_is_an_error(tmp_path):
    write(tmp_path, "annet/ukjent.md", "# Ukjent\n")
    results = validate_directory(tmp_path, rules=[("generators/*", GENERATOR_SCHEMA)])
    assert len(results) == 1 and not results[0].ok
    assert "no schema rule" in results[0].errors[0]


def test_manifest_via_cli(tmp_path, capsys):
    write(tmp_path, "referanse/lov.md", "# Lov\n")
    write(tmp_path, "generators/uten-id.md", GENERATOR_WITHOUT_ID)
    manifest = tmp_path / "schemas.json"
    manifest.write_text(json.dumps({"rules": [
        {"pattern": "referanse/*", "schema": "reference"},
        {"pattern": "generators/*", "schema": "generator"},
    ]}), encoding="utf-8")
    assert main([str(tmp_path), "--manifest", str(manifest)]) == 1
    out = capsys.readouterr().out
    assert "uten-id.md" in out and "lov.md: " not in out


def test_cli_schema_argument(tmp_path):
    write(tmp_path, "a.md", "# Bare tekst\n")
    assert main([str(tmp_path), "--schema", "reference"]) == 0
    assert main([str(tmp_path), "--schema", "generator"]) == 1


def test_zero_matches_is_not_green(tmp_path, capsys):
    (tmp_path / "tom").mkdir()
    assert main([str(tmp_path / "tom")]) == 1
    assert "no files matched" in capsys.readouterr().out


def test_inferred_schema_is_flagged_as_warning(tmp_path):
    path = write(tmp_path, "ref.md", "# Referanse\n\nTekst.\n")
    result = validate_file(path)
    assert result.ok
    assert any("inferred" in w for w in result.warnings)


def test_plain_reference_still_passes_legacy_route(tmp_path):
    write(tmp_path, "ref.md", "# Referanse\n\nSe {{IKKE_EN_VARIABEL}} i eksemplet.\n")
    assert all(r.ok for r in validate_directory(tmp_path))
