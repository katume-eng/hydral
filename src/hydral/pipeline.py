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

from hydral.artifacts import Artifacts


@dataclass
class PipelineContext:
    """Carries input/output paths and shared state through a pipeline.

    ``input_path`` is the original source file and never changes.
    ``audio_path`` starts equal to ``input_path`` and is updated by each
    transform step to point at its primary output, enabling step-to-step
    piping (e.g. normalize → grain uses the normalized audio as input).
    ``artifacts`` holds typed output paths filled in by built-in steps.
    ``extra`` is a free-form dict kept for ad-hoc debugging payloads.
    """

    input_path: Path
    output_dir: Path
    sample_rate: Optional[int] = None
    artifacts: Artifacts = field(default_factory=Artifacts)
    extra: Dict[str, Any] = field(default_factory=dict)
    # audio_path is derived from input_path; excluded from __init__ so that
    # existing call-sites (PipelineContext(input_path=…, output_dir=…)) still work.
    audio_path: Path = field(init=False)

    def __post_init__(self) -> None:
        self.audio_path = self.input_path


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
