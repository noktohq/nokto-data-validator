"""
Generic structured-document validator.

Validates that Markdown files in a library conform to a declared schema.
Each schema defines required fields, required sections, and variable placeholders.

Schema selection (explicit context first):
  1. ``schema=`` argument (``validate_file``/``validate_directory``) or ``--schema`` on the CLI.
  2. Path rules: ``rules=[(pattern, schema), ...]`` or a JSON manifest (``--manifest``). First match
     wins; a file that matches no rule is an error ("no schema rule"), never silently a reference.
  3. Legacy fallback when no context is given: the schema is inferred from content and the result
     carries a warning. Inference is conservative — any generator marker (``ID:``/``NAVN:``/``STYRKE:``
     at line start or a ``BRUK``/``REGLER``/``HVIS INPUT MANGLER`` heading) selects GENERATOR_SCHEMA,
     so a generator missing a required field fails instead of passing as a reference.

Changed in 2026-10: before, inference required ``ID:``, ``NAVN:`` and ``{{`` together, so a
generator without ``ID:`` was validated as a reference and passed. The CLI now exits 1 when no
files match.
"""

import fnmatch
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Schema:
    required_fields: list[str] = field(default_factory=list)
    required_sections: list[str] = field(default_factory=list)
    requires_placeholders: bool = False
    requires_header_comment: bool = True


@dataclass
class ValidationResult:
    path: Path
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0


GENERATOR_SCHEMA = Schema(
    required_fields=["ID:", "NAVN:", "STYRKE:"],
    required_sections=["BRUK", "REGLER", "HVIS INPUT MANGLER", "INPUT"],
    requires_placeholders=True,
    requires_header_comment=True,
)

REFERENCE_SCHEMA = Schema(
    required_fields=[],
    required_sections=[],
    requires_placeholders=False,
    requires_header_comment=False,
)


SCHEMAS = {"generator": GENERATOR_SCHEMA, "reference": REFERENCE_SCHEMA}
SKIP = None  # rule target: do not validate matching files

Rule = tuple[str, "Schema | None"]

_GENERATOR_FIELD = re.compile(r"^(ID|NAVN|STYRKE):", re.MULTILINE)
_GENERATOR_HEADING = re.compile(r"^#{0,3}\s*(BRUK|REGLER|HVIS INPUT MANGLER)\s*$", re.MULTILINE | re.IGNORECASE)


def _is_generator(text: str) -> bool:
    """Legacy inference. Any generator marker counts, so missing required fields are reported."""
    return bool(_GENERATOR_FIELD.search(text) or _GENERATOR_HEADING.search(text))


def infer_schema(text: str) -> Schema:
    return GENERATOR_SCHEMA if _is_generator(text) else REFERENCE_SCHEMA


def load_rules(manifest: Path) -> list[Rule]:
    """Read a JSON manifest: {"rules": [{"pattern": "referanse/*", "schema": "reference"}, ...]}.

    ``schema`` is "generator", "reference" or "skip". Patterns use fnmatch against the path
    relative to the validated directory (posix separators; ``*`` also matches ``/``).
    """
    data = json.loads(Path(manifest).read_text(encoding="utf-8"))
    rules: list[Rule] = []
    for i, rule in enumerate(data.get("rules") or []):
        name = rule.get("schema")
        if name == "skip":
            rules.append((str(rule["pattern"]), SKIP))
        elif name in SCHEMAS:
            rules.append((str(rule["pattern"]), SCHEMAS[name]))
        else:
            raise ValueError(f"manifest rule {i}: unknown schema {name!r}")
    if not rules:
        raise ValueError("manifest has no rules")
    return rules


def select_schema(rel_path: str, rules: list[Rule]) -> tuple[bool, Schema | None]:
    """(matched, schema) for the first matching rule. schema None = skip."""
    for pattern, schema in rules:
        if fnmatch.fnmatchcase(rel_path, pattern):
            return True, schema
    return False, None


def validate_file(path: Path, schema: Schema | None = None) -> ValidationResult:
    result = ValidationResult(path=path)
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    detected_schema = schema
    if detected_schema is None:
        detected_schema = infer_schema(text)
        name = "GENERATOR_SCHEMA" if detected_schema is GENERATOR_SCHEMA else "REFERENCE_SCHEMA"
        result.warnings.append(f"schema inferred from content ({name}); pass schema= or a manifest")

    if detected_schema.requires_header_comment:
        if not lines or not lines[0].startswith("<!--"):
            result.warnings.append("missing <!-- path --> comment on line 1")

    for field_name in detected_schema.required_fields:
        if field_name not in text:
            result.errors.append(f"missing required field '{field_name}'")

    for section in detected_schema.required_sections:
        pattern = re.compile(
            r"^#{0,3}\s*" + re.escape(section) + r"\s*$",
            re.MULTILINE | re.IGNORECASE,
        )
        if not pattern.search(text):
            result.errors.append(f"missing required section '{section}'")

    if detected_schema.requires_placeholders:
        input_match = re.search(r"## INPUT\n(.*?)(\Z|##)", text, re.DOTALL)
        if input_match and not re.findall(r"\{\{(\w+)\}\}", input_match.group(1)):
            result.errors.append("INPUT section has no {{VARIABLE}} placeholders")

    return result


def validate_directory(
    directory: Path,
    glob: str = "**/*.md",
    skip: set[str] | None = None,
    schema: Schema | None = None,
    rules: list[Rule] | None = None,
) -> list[ValidationResult]:
    """Validate files under ``directory``. ``schema`` applies one schema to all files; ``rules``
    select per path (first match; no match = error). Without either, the legacy inference applies."""
    skip_names = skip or {"README.md", "CLAUDE.md", "KONTEKST.md"}
    results = []
    for path in sorted(directory.glob(glob)):
        if path.name in skip_names or not path.is_file():
            continue
        if rules is not None:
            rel = path.relative_to(directory).as_posix()
            matched, chosen = select_schema(rel, rules)
            if not matched:
                results.append(ValidationResult(path=path, errors=["no schema rule matches this file"]))
                continue
            if chosen is SKIP:
                continue
            results.append(validate_file(path, schema=chosen))
            continue
        results.append(validate_file(path, schema=schema))
    return results


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Nokto document validator")
    parser.add_argument("directory", nargs="?", default=".", help="Directory to validate")
    parser.add_argument("--glob", default="**/*.md", help="Glob pattern (default: **/*.md)")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--schema", choices=sorted(SCHEMAS), help="Validate every file against this schema")
    group.add_argument("--manifest", type=Path, help="JSON manifest with path rules (see load_rules)")
    args = parser.parse_args(argv)

    directory = Path(args.directory)
    if not directory.is_dir():
        print(f"ERROR: '{directory}' is not a directory", file=sys.stderr)
        return 1
    try:
        rules = load_rules(args.manifest) if args.manifest else None
    except (OSError, ValueError, KeyError) as exc:
        print(f"ERROR: manifest: {exc}", file=sys.stderr)
        return 1

    results = validate_directory(directory, glob=args.glob, schema=SCHEMAS.get(args.schema or ""), rules=rules)
    checked = len(results)
    if checked == 0:
        print(f"\nValidated 0 file(s)\n\nRESULT: FAIL — no files matched '{args.glob}' in '{directory}'")
        return 1
    all_errors = [e for r in results for e in r.errors]
    all_warnings = [w for r in results for w in r.warnings]

    print(f"\nValidated {checked} file(s)\n")

    for r in results:
        for e in r.errors:
            print(f"  ERROR   {r.path}: {e}")
        for w in r.warnings:
            print(f"  WARNING {r.path}: {w}")

    print()
    if all_errors:
        print(f"RESULT: FAIL — {len(all_errors)} error(s)")
        return 1

    if all_warnings:
        print(f"RESULT: PASS with {len(all_warnings)} warning(s)")
    else:
        print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())

