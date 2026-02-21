"""
Utilities for applying structural constraints to melody generation.
Handles repetition, motif variation, and rhythm profile enforcement.
"""
import random
from typing import List, Tuple, Dict, Optional


def apply_motif_repetition(
    pitches: List[int],
    durations: List[float],
    repeat_unit_beats: float,
    allow_variation: bool = False,
    variation_probability: float = 0.3,
    rng: random.Random = None
) -> Tuple[List[int], List[float]]:
    """
    Apply repeating unit structure to pitch/duration sequence.
    
    Args:
        pitches: Original MIDI pitch sequence
        durations: Original duration sequence in beats
        repeat_unit_beats: Length of repeating unit in beats
        allow_variation: Allow subtle variations in repetitions
        variation_probability: Probability of variation per repeat
        rng: Random number generator (default: create new one)
    
    Returns:
        (modified_pitches, modified_durations) with repetition applied
    """
    if rng is None:
        rng = random.Random()
    
    if len(pitches) == 0 or repeat_unit_beats <= 0:
        return pitches, durations
    
    # Extract first unit
    unit_pitches = []
    unit_durations = []
    accumulated_beats = 0.0
    idx = 0
    
    while accumulated_beats < repeat_unit_beats - 0.01 and idx < len(durations):
        unit_pitches.append(pitches[idx])
        unit_durations.append(durations[idx])
        accumulated_beats += durations[idx]
        idx += 1
    
    if not unit_pitches:
        return pitches, durations
    
    # Calculate how many full repetitions we need
    total_beats = sum(durations)
    num_repeats = int(total_beats / repeat_unit_beats)
    
    if num_repeats < 2:
        # Not enough material for repetition
        return pitches, durations
    
    # Build repeated sequence
    new_pitches = []
    new_durations = []
    
    for repeat_idx in range(num_repeats):
        if repeat_idx == 0 or not allow_variation or rng.random() >= variation_probability:
            # Use original motif
            new_pitches.extend(unit_pitches)
            new_durations.extend(unit_durations)
        else:
            # Apply subtle variation
            varied_pitches = _apply_subtle_variation(unit_pitches, rng)
            new_pitches.extend(varied_pitches)
            new_durations.extend(unit_durations)  # Keep rhythm same
    
    # Trim to original length
    trim_beats = sum(new_durations[:len(durations)])
    if len(new_durations) > len(durations):
        new_pitches = new_pitches[:len(durations)]
        new_durations = new_durations[:len(durations)]
    
    return new_pitches, new_durations


def _apply_subtle_variation(pitches: List[int], rng: random.Random) -> List[int]:
    """
    Apply subtle variation to pitch sequence (transpose or neighbor tone).
    
    Args:
        pitches: Original pitches
        rng: Random number generator
    
    Returns:
        Varied pitch sequence
    """
    variation_type = rng.choice(["transpose", "neighbor", "inversion"])
    
    if variation_type == "transpose":
        # Transpose by small interval (-2 to +2 semitones)
        offset = rng.choice([-2, -1, 1, 2])
        return [max(0, p + offset) if p > 0 else 0 for p in pitches]
    
    elif variation_type == "neighbor":
        # Add neighbor tone to one note
        if len(pitches) > 1:
            varied = pitches.copy()
            idx = rng.randint(0, len(pitches) - 1)
            if varied[idx] > 0:
                varied[idx] += rng.choice([-1, 1])
            return varied
        return pitches
    
    elif variation_type == "inversion":
        # Invert interval direction around first note
        if len(pitches) < 2:
            return pitches
        
        anchor = pitches[0]
        inverted = [anchor]
        for i in range(1, len(pitches)):
            if pitches[i] > 0:
                interval = pitches[i] - pitches[i-1]
                inverted.append(max(0, inverted[-1] - interval))
            else:
                inverted.append(0)
        return inverted
    
    return pitches


def enforce_rhythm_profile(
    durations: List[float],
    target_profile: Dict[float, float],
    rng: random.Random = None
) -> List[float]:
    """
    Adjust durations to better match target rhythm profile.
    
    Args:
        durations: Original durations in beats
        target_profile: Target distribution {duration: proportion}
        rng: Random number generator
    
    Returns:
        Adjusted durations matching profile
    """
    if rng is None:
        rng = random.Random()
    
    if not durations or not target_profile:
        return durations
    
    # Calculate how many notes should have each duration
    total_notes = len(durations)
    target_counts = {dur: int(total_notes * prop) for dur, prop in target_profile.items()}
    
    # Adjust for rounding errors
    diff = total_notes - sum(target_counts.values())
    if diff > 0:
        # Add extra notes to most common duration
        max_dur = max(target_profile.keys(), key=lambda d: target_profile[d])
        target_counts[max_dur] += diff
    
    # Build new duration list
    new_durations = []
    for dur, count in target_counts.items():
        new_durations.extend([dur] * count)
    
    # Shuffle to avoid patterns
    rng.shuffle(new_durations)
    
    # Ensure we have exact count
    if len(new_durations) < total_notes:
        # Pad with random choices from profile
        while len(new_durations) < total_notes:
            new_durations.append(rng.choice(list(target_profile.keys())))
    elif len(new_durations) > total_notes:
        new_durations = new_durations[:total_notes]
    
    return new_durations


def calculate_repeat_count(
    pitches: List[int],
    durations: List[float],
    unit_beats: float
) -> int:
    """
    Count number of complete repeating units in sequence.
    
    Args:
        pitches: MIDI pitch sequence
        durations: Duration sequence
        unit_beats: Expected unit length in beats
    
    Returns:
        Number of complete units found
    """
    if unit_beats <= 0 or not durations:
        return 0
    
    total_beats = sum(durations)
    return int(total_beats / unit_beats)


def compute_duration_distribution(durations: List[float]) -> Dict[float, float]:
    """
    Calculate actual duration distribution from sequence.
    
    Args:
        durations: Duration sequence in beats
    
    Returns:
        Distribution as {duration: proportion}
    """
    if not durations:
        return {}
    
    counts = {}
    for dur in durations:
        # Round to 3 decimals to avoid floating point issues
        rounded_dur = round(dur, 3)
        counts[rounded_dur] = counts.get(rounded_dur, 0) + 1
    
    total = len(durations)
    return {dur: count / total for dur, count in counts.items()}
