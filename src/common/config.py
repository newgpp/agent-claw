"""Common configuration models."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class LoggingConfig:
    """Logging-related runtime settings."""

    service_name: str = "agent-claw"
    log_to_stdout: bool = True
    log_to_file: bool = False
    log_dir: str = "logs"


@dataclass(slots=True)
class RuntimeConfig:
    """Common runtime-level configuration."""

    max_steps: int = 5
    logging: LoggingConfig = field(default_factory=LoggingConfig)
