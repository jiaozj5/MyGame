"""LOL top-lane level 1–6 matchup simulator package."""

# Keep the public API small and importable both from Python and the CLI.
from .catalog import get_catalog
from .engine import ValidationError, optimize, simulate

__all__ = ["get_catalog", "simulate", "optimize", "ValidationError"]
