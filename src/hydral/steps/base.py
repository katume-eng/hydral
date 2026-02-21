"""Abstract base class for hydral pipeline steps.

All built-in steps extend :class:`BaseStep`.  The :class:`~hydral.pipeline.Step`
*Protocol* defined in ``pipeline.py`` remains the structural interface used by
:class:`~hydral.pipeline.Pipeline`; :class:`BaseStep` adds the richer contract
required by the YAML runner (fingerprints, structured outputs, validation).
"""
from __future__ import annotations

import abc
from pathlib import Path
from typing import Any, Dict, List

from hydral.pipeline import PipelineContext


class BaseStep(abc.ABC):
    """Abstract base for all hydral pipeline steps.

    Sub-classes **must** implement :meth:`step_name` and :meth:`run`.
    The remaining methods have sensible defaults that sub-classes may override.
    """

    @property
    @abc.abstractmethod
    def step_name(self) -> str:
        """Stable, lower-case identifier for this step (e.g. ``"normalize"``)."""
        ...

    @abc.abstractmethod
    def run(self, ctx: PipelineContext) -> PipelineContext:
        """Execute the step and return the (possibly mutated) context."""
        ...

    def outputs(self, ctx: PipelineContext) -> List[Path]:
        """Return the list of output paths this step would produce for *ctx*.

        Used by the runner to populate the run report and check caches.
        The default returns an empty list; override to provide accurate paths.
        """
        return []

    def fingerprint(self, ctx: PipelineContext) -> Dict[str, Any]:
        """Return a JSON-serialisable, stable dict that uniquely identifies
        this step invocation.

        The default includes ``step_name`` and the input file size / mtime so
        that content changes are detected without a full SHA-256 scan.
        Override to include step-specific parameters.
        """
        try:
            stat = ctx.audio_path.stat()
            input_info: Dict[str, Any] = {
                "size": stat.st_size,
                "mtime": stat.st_mtime,
            }
        except OSError:
            input_info = {}
        return {
            "step": self.step_name,
            "input": str(ctx.audio_path),
            "input_stat": input_info,
        }

    def validate(self, ctx: PipelineContext) -> None:
        """Raise :exc:`ValueError` if *ctx* is not suitable for this step.

        Called by the runner before :meth:`run`.  The default is a no-op.
        """
