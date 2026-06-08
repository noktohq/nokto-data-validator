"""Tests for the document validator."""

import textwrap
from pathlib import Path

import pytest

from src.validator import (
    GENERATOR_SCHEMA,
    REFERENCE_SCHEMA,
    Schema,
    validate_file,
)


@pytest.fixture
def tmp_md(tmp_path):
    def _write(content: str, name: str = "doc.md") -> Path:
        p = tmp_path / name
        p.write_text(textwrap.dedent(content), encoding="utf-8")
        return p

    return _write


def test_valid_generator_passes(tmp_md):
    path = tmp_md("""\
        <!-- generators/example.md -->
        ID: EXAMPLE-001
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
    """)
    result = validate_file(path, schema=GENERATOR_SCHEMA)
    assert result.ok


def test_missing_required_field(tmp_md):
    path = tmp_md("""\
        <!-- generators/example.md -->
        NAVN: Eksempel
        STYRKE: 3

        ## BRUK
        ...
        ## REGLER
        ...
        ## HVIS INPUT MANGLER
        ...
        ## INPUT
        {{X}}
    """)
    result = validate_file(path, schema=GENERATOR_SCHEMA)
    assert any("ID:" in e for e in result.errors)


def test_missing_section(tmp_md):
    path = tmp_md("""\
        <!-- generators/example.md -->
        ID: X
        NAVN: Y
        STYRKE: 1

        ## BRUK
        ...
        ## REGLER
        ...
        ## HVIS INPUT MANGLER
        ...
        ## INPUT
        {{X}}
    """)
    result = validate_file(path, schema=GENERATOR_SCHEMA)
    assert result.ok


def test_input_without_placeholders(tmp_md):
    path = tmp_md("""\
        <!-- generators/example.md -->
        ID: X
        NAVN: Y
        STYRKE: 1

        ## BRUK
        ...
        ## REGLER
        ...
        ## HVIS INPUT MANGLER
        ...
        ## INPUT
        No placeholders here.
    """)
    result = validate_file(path, schema=GENERATOR_SCHEMA)
    assert any("placeholder" in e for e in result.errors)


def test_reference_schema_is_lenient(tmp_md):
    path = tmp_md("# Just a reference doc\n\nSome content.\n")
    result = validate_file(path, schema=REFERENCE_SCHEMA)
    assert result.ok


def test_missing_header_comment_is_warning(tmp_md):
    path = tmp_md("""\
        ID: X
        NAVN: Y
        STYRKE: 1

        ## BRUK
        ...
        ## REGLER
        ...
        ## HVIS INPUT MANGLER
        ...
        ## INPUT
        {{X}}
    """)
    result = validate_file(path, schema=GENERATOR_SCHEMA)
    assert any("comment" in w for w in result.warnings)

