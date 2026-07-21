"""`autoinfo clean` — Remove cached artifacts and temporary files."""

from __future__ import annotations

import shutil
from pathlib import Path

import typer

app = typer.Typer(help="Remove cached artifacts and temporary files.")

_DEFAULT_DIRS = {
    "collections": Path("collections"),
    "outputs": Path("outputs"),
    "knowledge": Path("knowledge"),
}
_DB_PATH = Path("autoinfo.db")


def _rmtree(path: Path, dry_run: bool) -> int:
    """Remove directory contents, return count of deleted items."""
    if not path.is_dir():
        return 0
    count = 0
    for child in path.iterdir():
        if dry_run:
            typer.echo(f"  would remove  {child}")
        else:
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
        count += 1
    return count


def _clean_collections(dry_run: bool = False) -> int:
    return _rmtree(_DEFAULT_DIRS["collections"], dry_run)


def _clean_outputs(dry_run: bool = False) -> int:
    return _rmtree(_DEFAULT_DIRS["outputs"], dry_run)


def _clean_knowledge(dry_run: bool = False) -> int:
    return _rmtree(_DEFAULT_DIRS["knowledge"], dry_run)


def _clean_db(dry_run: bool = False) -> bool:
    if not _DB_PATH.is_file():
        return False
    if dry_run:
        typer.echo(f"  would remove  {_DB_PATH}")
    else:
        _DB_PATH.unlink()
    return True


@app.callback(invoke_without_command=True)
def clean(
    collections: bool = typer.Option(
        False, "--collections", help="Remove cached collections/ contents"
    ),
    outputs: bool = typer.Option(
        False, "--outputs", help="Remove outputs/ contents"
    ),
    everything: bool = typer.Option(
        False,
        "--everything",
        help="Remove ALL cached data (collections + outputs + knowledge + DB)",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be deleted without deleting"
    ),
) -> None:
    """Remove cached artifacts and temporary files.

    At least one of --collections, --outputs, or --everything is required.
    """
    # Safety: --everything requires confirmation (unless --dry-run)
    if everything and not dry_run:
        typer.echo(
            "⚠️  This will delete all collected data, KB entries, and the database."
        )
        confirm = typer.prompt("Are you sure? [y/N]", default="n")
        if confirm.lower() != "y":
            typer.echo("Cancelled.")
            raise typer.Exit(code=0)

    total = 0

    if collections or everything:
        total += _clean_collections(dry_run=dry_run)
    if outputs or everything:
        total += _clean_outputs(dry_run=dry_run)
    if everything:
        total += _clean_knowledge(dry_run=dry_run)
        if _clean_db(dry_run=dry_run):
            total += 1

    if dry_run:
        typer.echo(f"Would remove {total} item(s).")
    elif total > 0:
        typer.echo(f"Removed {total} item(s).")
    else:
        typer.echo("Nothing to clean.")
