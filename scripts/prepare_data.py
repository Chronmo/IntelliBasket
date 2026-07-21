"""Compatibility wrapper for the IntelliBasket data preparation command."""

from intellibasket.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["prepare-data"]))
