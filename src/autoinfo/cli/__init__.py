"""AutoInfo CLI entry point."""

import typer

from . import collect, doctor, process, status, summaries

# Import init function directly (not as typer app — single-command module)
from .init import init as init_func

app = typer.Typer(
    name="autoinfo",
    help="Universal information tracking and knowledge base platform",
    no_args_is_help=True,
)


@app.callback()
def main(
    ctx: typer.Context,
    json: bool = typer.Option(False, "--json", help="Enable JSON output"),
):
    """AutoInfo CLI — collect, process, and manage your information."""
    ctx.obj = {"json": json}


# Register subcommand modules as top-level commands
app.command()(init_func)
app.add_typer(doctor.app, name="doctor")
app.add_typer(collect.app, name="collect")
app.add_typer(process.app, name="process")
app.add_typer(status.app, name="status")
app.add_typer(summaries.app, name="summaries")

if __name__ == "__main__":
    app()
