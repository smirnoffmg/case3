from typer.testing import CliRunner

from case3.cli import app

runner = CliRunner()


def test_cli_run_stub():
    result = runner.invoke(app, ["run", "список сотрудников", "--stub"])
    assert result.exit_code == 0
    assert "SELECT" in result.stdout.upper()
    assert "Approved: True" in result.stdout
