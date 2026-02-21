"""
Utilities for note duration, timing, and scale constraint handling.
Provides discrete note values, grid snapping, and scale-aware pitch selection.
"""
import random
from typing import List, Tuple, Optional


# Discrete note durations in beats (quarter note = 1 beat)
# Maps to standard note values
DISCRETE_DURATIONS = {
    "whole": 4.0,
    "half": 2.0,
    "quarter": 1.0,
    "eighth": 0.5,
    "sixteenth": 0.25,
    "thirty_second": 0.125
}

# Ordered list for easy sampling
DURATION_VALUES = [
    DISCRETE_DURATIONS["whole"],
    DISCRETE_DURATIONS["half"],
    DISCRETE_DURATIONS["quarter"],
    DISCRETE_DURATIONS["eighth"],
    DISCRETE_DURATIONS["sixteenth"],
    DISCRETE_DURATIONS["thirty_second"]
]

# Grid resolution for start times (32nd note = 0.125 beats in 4/4)
GRID_RESOLUTION = 0.125


def get_discrete_duration_values(beats_per_bar: float = 4.0) -> List[float]:
    """
    Get list of valid discrete note durations, scaled for time signature.
    
    Args:
        beats_per_bar: Beats per measure (e.g., 4.0 for 4/4, 3.0 for 3/4)
    
    Returns:
        List of valid duration values in beats
    """
    # For now, keep standard durations regardless of time signature
    # Could scale in future if needed
    return DURATION_VALUES.copy()


def snap_to_grid(beat_position: float, grid_resolution: float = GRID_RESOLUTION) -> float:
    """
    Snap a beat position to the nearest grid point.
    
    Args:
        beat_position: Position in beats
        grid_resolution: Grid spacing in beats (default: 32nd note = 0.125)
    
    Returns:
        Snapped position
    """
    return round(beat_position / grid_resolution) * grid_resolution


def choose_duration(
    remaining_beats: float,
    allowed_durations: List[float],
    rng: random.Random
) -> float:
    """
    Choose a valid discrete duration that fits within remaining time.
    
    Args:
        remaining_beats: How many beats are left to fill
        allowed_durations: List of valid duration values
        rng: Random number generator
    
    Returns:
        Selected duration in beats
    """
    # Filter to durations that fit
    valid = [d for d in allowed_durations if d <= remaining_beats + 0.001]  # Small epsilon
    
    if not valid:
        # If no standard duration fits, use smallest available
        # or snap remaining to grid
        return snap_to_grid(remaining_beats)
    
    return rng.choice(valid)


def build_scale_pitch_set(
    tonic_note: str,
    scale_pattern: List[int],
    lowest_midi: int,
    highest_midi: int
) -> List[int]:
    """
    Build complete set of allowed MIDI pitches from scale across octaves.
    
    Args:
        tonic_note: Root note name (e.g., "C", "F#")
        scale_pattern: Intervals in semitones from tonic
        lowest_midi: Minimum allowed MIDI pitch
        highest_midi: Maximum allowed MIDI pitch
    
    Returns:
        Sorted list of MIDI pitches in scale within range
    """
    base_midi = _note_name_to_midi(tonic_note, 4)  # C4 = 60
    
    allowed_pitches = []
    # Cover sufficient octave range
    for octave_offset in range(-3, 5):
        for interval in scale_pattern:
            candidate = base_midi + (octave_offset * 12) + interval
            if lowest_midi <= candidate <= highest_midi:
                allowed_pitches.append(candidate)
    
    return sorted(set(allowed_pitches))


def pick_scale_pitch(
    scale_pitches: List[int],
    previous_pitch: Optional[int],
    lowest_midi: int,
    highest_midi: int,
    octave_up_chance: float,
    rng: random.Random
) -> Tuple[int, bool]:
    """
    Select next pitch from scale with optional octave-up jump.
    
    Args:
        scale_pitches: Available scale pitches
        previous_pitch: Last pitch (None if first note)
        lowest_midi: Minimum MIDI pitch
        highest_midi: Maximum MIDI pitch
        octave_up_chance: Probability of octave jump (0.01-0.05)
        rng: Random number generator
    
    Returns:
        (selected_pitch, octave_jump_occurred)
    """
    octave_jump = False
    
    # Decide octave jump (rare, suppressed near max range)
    if previous_pitch is not None and rng.random() < octave_up_chance:
        # Check if we have room for octave jump
        if previous_pitch + 12 <= highest_midi - 2:  # Leave some headroom
            # Find pitch class (within octave)
            pitch_class = previous_pitch % 12
            
            # Look for same pitch class one octave up, still in scale
            candidate = previous_pitch + 12
            
            # Check if candidate is in scale_pitches
            if candidate in scale_pitches and candidate <= highest_midi:
                octave_jump = True
                return candidate, octave_jump
    
    # Normal selection - prefer stepwise motion if we have previous pitch
    if previous_pitch is not None and previous_pitch in scale_pitches:
        # Find nearby scale notes
        prev_idx = scale_pitches.index(previous_pitch)
        
        # Collect neighbors within a few scale steps
        neighbors = []
        for offset in [-2, -1, 1, 2]:
            idx = prev_idx + offset
            if 0 <= idx < len(scale_pitches):
                neighbors.append(scale_pitches[idx])
        
        # Prefer neighbors with 60% probability
        if neighbors and rng.random() < 0.6:
            return rng.choice(neighbors), octave_jump
    
    # Random selection from scale
    return rng.choice(scale_pitches), octave_jump


def ensure_pitch_in_range(
    pitch: int,
    scale_pitches: List[int],
    lowest_midi: int,
    highest_midi: int,
    rng: random.Random
) -> int:
    """
    Ensure pitch is within allowed range, resample if needed.
    
    Args:
        pitch: Candidate MIDI pitch
        scale_pitches: Available scale pitches
        lowest_midi: Minimum allowed pitch
        highest_midi: Maximum allowed pitch
        rng: Random number generator
    
    Returns:
        Valid pitch within range
    """
    if lowest_midi <= pitch <= highest_midi:
        return pitch
    
    # Out of range - resample from scale pitches in range
    valid = [p for p in scale_pitches if lowest_midi <= p <= highest_midi]
    if valid:
        return rng.choice(valid)
    
    # Fallback: clamp to range
    return max(lowest_midi, min(highest_midi, pitch))


def _note_name_to_midi(note_name: str, octave: int) -> int:
    """
    Convert note name to MIDI number at given octave.
    
    Supports enharmonic equivalents including rare cases:
    - Fb = E (enharmonic equivalent, pitch class 4)
    - E# = F (enharmonic equivalent, pitch class 5)
    - B# = C of next octave (pitch class 0 with octave adjustment)
    """
    note_map = {
        "C": 0, "C#": 1, "Db": 1,
        "D": 2, "D#": 3, "Eb": 3,
        "E": 4, "Fb": 4, "E#": 5,
        "F": 5, "F#": 6, "Gb": 6,
        "G": 7, "G#": 8, "Ab": 8,
        "A": 9, "A#": 10, "Bb": 10,
        "B": 11, "Cb": 11, "B#": 0  # B# uses C pitch class
    }
    
    base = note_map.get(note_name, 0)
    midi_num = (octave + 1) * 12 + base
    
    # B# requires octave adjustment since it's enharmonic to C of next octave
    if note_name == "B#":
        midi_num += 12
    
    return midi_num


def is_pitch_in_scale(pitch: int, scale_pitches: List[int]) -> bool:
    """Check if a MIDI pitch is in the scale."""
    return pitch in scale_pitches
