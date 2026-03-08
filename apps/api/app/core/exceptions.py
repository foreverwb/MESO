from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(eq=False)
class MesoError(Exception):
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return self.message


class ConfigError(MesoError):
    """Raised when application configuration is missing or invalid."""


class ImportValidationError(MesoError):
    """Raised when imported rows fail validation."""


class DomainValidationError(MesoError):
    """Raised when domain constraints are violated."""


class ScoringError(MesoError):
    """Raised when scoring execution or scoring inputs are invalid."""
