"""Support ``python -m autoinfo.cli`` (module entry point).

The ``autoinfo`` console script (declared in ``pyproject.toml`` under
``[project.scripts] autoinfo = "autoinfo.cli:app"``) is the primary entry
point. ``python -m autoinfo.cli`` is an equivalent invocation that runs the
same Typer app — e.g. ``python -m autoinfo.cli --help``.
"""

from autoinfo.cli import app

if __name__ == "__main__":
    app()
