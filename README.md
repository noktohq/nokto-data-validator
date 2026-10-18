# nokto-data-validator

Structured-document validator for Markdown libraries, with a generic `Schema` API. Ships with Nokto's own default prompt-library schema (Norwegian `ID`/`NAVN`/`STYRKE`/`BRUK`/`REGLER`-format) — validates files against declared schemas, checking required fields, sections, and variable placeholders.

## Installation

```bash
pip install pytest  # for tests only
```

No runtime dependencies.

## Usage

### CLI

```bash
python -m src.validator ./my-library
python -m src.validator ./my-library --glob "docs/**/*.md"
```

### Library

```python
from src.validator import validate_file, validate_directory, GENERATOR_SCHEMA

# Validate a single file
result = validate_file(Path("doc.md"), schema=GENERATOR_SCHEMA)
if not result.ok:
    for error in result.errors:
        print(error)

# Validate a directory
results = validate_directory(Path("./library"))
```

### Choosing the schema

Pick the schema from explicit context, not from the content being validated:

```bash
python -m src.validator ./library --schema generator          # one schema for every file
python -m src.validator ./library --manifest schemas.json     # per-path rules
```

```json
{"rules": [
  {"pattern": "referanse/*", "schema": "reference"},
  {"pattern": "README.md",   "schema": "skip"},
  {"pattern": "*.md",        "schema": "generator"}
]}
```

First matching rule wins (`fnmatch` on the path relative to the directory; `*` also matches `/`).
A file that matches no rule is reported as an error. In Python: `validate_directory(path, schema=...)`
or `validate_directory(path, rules=load_rules(Path("schemas.json")))`.

Without a schema or rules, the schema is inferred from content (legacy behaviour) and each result
carries a warning. Since 2026-10 inference is conservative: any generator marker (`ID:`/`NAVN:`/`STYRKE:`
at line start, or a `BRUK`/`REGLER`/`HVIS INPUT MANGLER` heading) selects the generator schema, so a
generator that lacks `ID:` fails instead of passing as a reference. The CLI exits 1 when no files match.

### Custom schema

```python
from src.validator import Schema, validate_file

schema = Schema(
    required_fields=["title:", "version:"],
    required_sections=["Overview", "Usage"],
    requires_placeholders=False,
    requires_header_comment=False,
)
result = validate_file(path, schema=schema)
```

## Running tests

```bash
pytest tests/ -v
```

