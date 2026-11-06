# Contributing

Thanks for your interest in BlueKitchen.

## Development setup

- Python 3.10+
- Git
- Optional: a virtual environment

    python -m venv .venv
    python -m pip install -e ".[dev]"
    python -m pytest
    python -m ruff check .

On Windows, activate the environment with .venv\Scripts\Activate.ps1. On Linux, use source .venv/bin/activate.

## Guidelines

- Keep inspection features read-only.
- Do not extract or modify user-supplied firmware implicitly.
- Add tests for new parsers, including malformed-input cases.
- Avoid claiming support for formats that are only partially recognized.
- Keep optional third-party tools optional and document their versions.
- Prefer clear errors over silent fallback behavior.

## Pull requests

Describe the problem, the change, test coverage, and known limitations. Do not include proprietary firmware, private keys, device identifiers, or personal data in test fixtures.
