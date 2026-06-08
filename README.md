# nokto-data-validator

Generic structured-document validator for Markdown libraries. Validates files against declared schemas â€” checking required fields, sections, and variable placeholders.

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

