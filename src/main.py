"""Main entrypoint for the rebuilt HRFB application."""

from __future__ import annotations

from src.gui.app import run_app


def main() -> None:
    """Launch the HRFB experiment GUI application."""
    run_app()


if __name__ == "__main__":
    main()
