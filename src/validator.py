"""
Generic structured-document validator.

Validates that Markdown files in a library conform to a declared schema.
Each schema defines required fields, required sections, and variable placeholders.
"""

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


def _is_generator(text: str) -> bool:
    return "ID:" in text and "NAVN:" in text and "{{" in text


def validate_file(path: Path, schema: Schema | None = None) -> ValidationResult:
    result = ValidationResult(path=path)
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    detected_schema = schema or (GENERATOR_SCHEMA if _is_generator(text) else REFERENCE_SCHEMA)

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
) -> list[ValidationResult]:
    skip_names = skip or {"README.md", "CLAUDE.md", "KONTEKST.md"}
    results = []
    for path in sorted(directory.glob(glob)):
        if path.name in skip_names:
            continue
        results.append(validate_file(path))
    return results


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Nokto document validator")
    parser.add_argument("directory", nargs="?", default=".", help="Directory to validate")
    parser.add_argument("--glob", default="**/*.md", help="Glob pattern (default: **/*.md)")
    args = parser.parse_args(argv)

    directory = Path(args.directory)
    if not directory.is_dir():
        print(f"ERROR: '{directory}' is not a directory", file=sys.stderr)
        return 1

    results = validate_directory(directory, glob=args.glob)
    checked = len(results)
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
        print(f"RESULT: FAIL â€” {len(all_errors)} error(s)")
        return 1

    if all_warnings:
        print(f"RESULT: PASS with {len(all_warnings)} warning(s)")
    else:
        print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())

