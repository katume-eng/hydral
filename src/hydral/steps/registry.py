"""Step registry: maps step names to factory callables.

Usage::

    from hydral.steps.registry import StepRegistry

    # Register a custom step factory:
    StepRegistry.register("my_step", MyStep)

    # Build a step from config:
    step = StepRegistry.build("normalize", {"target_db": -3.0})
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List


class StepRegistry:
    """Maps step names to zero-argument (or keyword-argument) factory callables.

    Built-in steps are registered in :mod:`hydral.steps.builtin`.
    Third-party code can call :meth:`register` to add custom steps.
    """

    _factories: Dict[str, Callable[..., Any]] = {}

    @classmethod
    def register(cls, name: str, factory: Callable[..., Any]) -> None:
        """Register *factory* under *name*.

        *factory* must accept the keyword arguments that appear in the YAML
        ``params`` block for that step (unknown kwargs should be ignored or
        validated by the factory itself).
        """
        cls._factories[name] = factory

    @classmethod
    def build(cls, name: str, params: Dict[str, Any] | None = None) -> Any:
        """Instantiate and return the step registered under *name*.

        Parameters
        ----------
        name:
            The step name as it appears in the YAML config.
        params:
            Keyword arguments forwarded to the factory.

        Raises
        ------
        ValueError
            If *name* is not registered.
        """
        if name not in cls._factories:
            known = ", ".join(sorted(cls._factories)) or "(none registered)"
            raise ValueError(
                f"Unknown step {name!r}. Known steps: {known}"
            )
        return cls._factories[name](**(params or {}))

    @classmethod
    def names(cls) -> List[str]:
        """Return a sorted list of all registered step names."""
        return sorted(cls._factories)
