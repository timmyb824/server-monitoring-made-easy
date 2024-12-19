"""Test the metrics collection functionality."""

import os

import yaml
from click.testing import CliRunner

from app.cli import cli


def test_metrics_command_help():
    """Test that the metrics command help works."""
    runner = CliRunner()
    result = runner.invoke(cli, ["metrics", "--help"])
    assert result.exit_code == 0
    assert "Display current system metrics" in result.output


def test_metrics_command(mock_metrics_command, temp_config_file, monkeypatch):
    """Test that the metrics command returns expected data."""
    # Set environment variable for config path
    monkeypatch.setenv("SME_CONFIG", temp_config_file)

    runner = CliRunner()
    result = runner.invoke(cli, ["metrics"])

    assert result.exit_code == 0, f"Command failed with error: {result.output}"
    assert "CPU Usage" in result.output
    assert "Memory Usage" in result.output
    assert "Disk Usage" in result.output
    assert "Network Latency" in result.output


def test_metrics_command_with_config(
    temp_config_file, mock_metrics_command, monkeypatch
):
    """Test metrics command with a config file."""
    # Modify config to enable only CPU monitoring
    with open(temp_config_file) as f:
        config = yaml.safe_load(f)

    config["monitors"]["system"]["enabled"] = True

    with open(temp_config_file, "w") as f:
        yaml.dump(config, f)

    # Set environment variable for config path
    monkeypatch.setenv("SME_CONFIG", temp_config_file)

    runner = CliRunner()
    result = runner.invoke(cli, ["metrics"])

    assert result.exit_code == 0, f"Command failed with error: {result.output}"
    assert "CPU Usage" in result.output
    assert "Memory Usage" in result.output
