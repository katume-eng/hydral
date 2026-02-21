"""Minimal pipeline framework for hydral.

Usage::

    from hydral.pipeline import Pipeline, PipelineContext
    from hydral.steps import AnalyzeStep, NormalizeStep

    ctx = PipelineContext(input_path=Path("data/raw/track.wav"),
                          output_dir=Path("data/processed/hydral/track"))
    Pipeline([AnalyzeStep(), NormalizeStep()]).run(ctx)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


@dataclass
class PipelineContext:
    """Carries input/output paths and shared state through a pipeline."""

    input_path: Path
    output_dir: Path
    sample_rate: Optional[int] = None
    extra: Dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class Step(Protocol):
    """A single composable pipeline step."""

    def run(self, ctx: PipelineContext) -> PipelineContext:
        ...


class Pipeline:
    """Chains a sequence of Steps and executes them in order."""

    def __init__(self, steps: List[Step]) -> None:
        self._steps = list(steps)

    def run(self, ctx: PipelineContext) -> PipelineContext:
        for step in self._steps:
            ctx = step.run(ctx)
        return ctx
