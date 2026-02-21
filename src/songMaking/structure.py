"""
Melody structure specification for structural constraints.
Defines rhythmic repetition patterns and phrase organization.
"""
from dataclasses import dataclass
from typing import List, Optional, Dict


@dataclass
class MelodyStructureSpec:
    """
    Structural constraints for melody generation.
    
    Attributes:
        repeat_unit_beats: Length of repeating unit in beats (e.g., 4.0 for 1 bar in 4/4)
                          None = no structural repetition constraint
        rhythm_profile: Target distribution of durations as {duration: proportion}
                       e.g., {0.5: 0.4, 1.0: 0.6} = 40% eighths, 60% quarters
                       None = no rhythmic profile constraint
        allow_motif_variation: Allow subtle pitch variations in repeated units (default: False)
        variation_probability: Probability of applying variation to repeated motif (0.0-1.0)
    """
    repeat_unit_beats: Optional[float] = None
    rhythm_profile: Optional[Dict[float, float]] = None
    allow_motif_variation: bool = False
    variation_probability: float = 0.0


def create_default_structure_spec() -> MelodyStructureSpec:
    """Create default structure spec with no constraints."""
    return MelodyStructureSpec(
        repeat_unit_beats=None,
        rhythm_profile=None,
        allow_motif_variation=False,
        variation_probability=0.0
    )


def create_structured_spec(
    repeat_unit_beats: float,
    rhythm_profile: Optional[Dict[float, float]] = None,
    allow_variation: bool = True,
    variation_prob: float = 0.3
) -> MelodyStructureSpec:
    """
    Create structure spec with repetition and optional rhythm profile.
    
    Args:
        repeat_unit_beats: Repeating unit length in beats
        rhythm_profile: Target rhythm distribution (None = no constraint)
        allow_variation: Enable subtle variations in repeated motifs
        variation_prob: Probability of variation when repeating (0.0-1.0)
    
    Returns:
        Configured MelodyStructureSpec
    """
    return MelodyStructureSpec(
        repeat_unit_beats=repeat_unit_beats,
        rhythm_profile=rhythm_profile,
        allow_motif_variation=allow_variation,
        variation_probability=variation_prob
    )
