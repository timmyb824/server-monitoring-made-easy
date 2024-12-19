"""Shared pytest fixtures."""

import os
import tempfile
from typing import Generator

import pytest
import yaml


@pytest.fixture
def temp_config_file() -> Generator[str, None, None]:
    """Create a temporary config file for testing."""
    config = {
        "database": {"dsn": "postgresql://user:password@localhost:5432/testdb"},
        "monitors": {
            "system": {"enabled": True, "interval": 60},
            "http": {
                "enabled": True,
                "interval": 60,
                "endpoints": [{"url": "http://example.com", "name": "example"}],
            },
        },
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(config, f)
        config_path = f.name

    yield config_path

    # Cleanup
    os.unlink(config_path)


class MockMonitor:
    """Mock monitor class."""

    def __init__(self, name, config, silent=False):
        """Initialize mock monitor."""
        self.name = name
        self.config = config
        self.silent = silent

    def collect(self):
        """Mock collect method."""
        if "cpu" in self.name.lower():
            return {"cpu_percent": 50.0}
        elif "memory" in self.name.lower():
            return {"memory_percent": 60.0}
        elif "disk" in self.name.lower():
            return {"disk_usage_percent": 70.0}
        return {}


@pytest.fixture
def mock_metrics_command(monkeypatch):
    """Mock the metrics collection to avoid actual system calls."""
    monkeypatch.setattr("app.monitors.CPUMonitor", MockMonitor)
    monkeypatch.setattr("app.monitors.MemoryMonitor", MockMonitor)
    monkeypatch.setattr("app.monitors.DiskMonitor", MockMonitor)
