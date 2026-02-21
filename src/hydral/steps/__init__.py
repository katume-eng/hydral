"""hydral.steps – built-in pipeline steps and step infrastructure.

This package supersedes the legacy ``steps.py`` module.  All public names
from that module are re-exported here for backward compatibility, so existing
code that does::

    from hydral.steps import AnalyzeStep, NormalizeStep

continues to work without modification.

New code should import from the sub-modules directly:

* :mod:`hydral.steps.base` – :class:`BaseStep` abstract base class
* :mod:`hydral.steps.registry` – :class:`StepRegistry`
* :mod:`hydral.steps.builtin` – concrete built-in step implementations
"""
from __future__ import annotations

# Built-in step classes (backward-compatible exports)
from hydral.steps.builtin import (  # noqa: F401
    AnalyzeStep,
    BandSplitStep,
    GrainStep,
    NormalizeStep,
)

# Infrastructure exports
from hydral.steps.base import BaseStep  # noqa: F401
from hydral.steps.registry import StepRegistry  # noqa: F401

__all__ = [
    "AnalyzeStep",
    "BandSplitStep",
    "GrainStep",
    "NormalizeStep",
    "BaseStep",
    "StepRegistry",
]
