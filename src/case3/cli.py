from __future__ import annotations

import typer

app = typer.Typer(add_completion=False)


@app.command()
def hello() -> None:
    typer.echo("case3")
