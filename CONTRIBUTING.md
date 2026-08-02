# Contributing

Contributions are welcome through GitHub issues and pull requests.

## Development setup

Use Python 3.14 or newer and install the test dependencies:

```bash
python -m pip install -r requirements_test.txt
```

Before opening a pull request, run:

```bash
ruff check .
ruff format --check .
mypy custom_components/mynissan tests
pytest
```

Keep changes focused and include tests for new behavior. Do not include account
credentials, OAuth tokens, VINs, or captured service responses in issues, test
fixtures, commits, or logs.
