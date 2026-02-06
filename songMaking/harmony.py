"""
Harmony specification for melody generation.
Defines musical context: tonality, rhythm framework, pitch boundaries.
"""
from dataclasses import dataclass
from typing import List, Tuple
import random


@dataclass
class HarmonySpec:
    """Complete musical context specification for melody generation."""
    tonic_note: str  # e.g., "C", "F#", "Bb"
    scale_pattern: List[int]  # semitone intervals from tonic
    chord_sequence: List[str]  # roman numerals or chord symbols
    beats_per_minute: int
    meter_numerator: int
    meter_denominator: int
    lowest_midi: int  # bottom of usable pitch range
    highest_midi: int  # top of usable pitch range
    subdivision_unit: float  # smallest rhythmic division (e.g., 0.25 = sixteenth)
    total_measures: int


def choose_harmony(rng_seed: int, options: dict) -> HarmonySpec:
    """
    Generate a complete harmonic framework using deterministic randomness.
    
    Args:
        rng_seed: Seed for reproducible random choices
        options: Configuration parameters (can be empty for defaults)
    
    Returns:
        HarmonySpec with all musical parameters defined
    """
    rng = random.Random(rng_seed)
    
    # Pitch center selection
    note_names = ["C", "D", "E", "F", "G", "A", "B"]
    accidentals = ["", "b", "#"]
    root = rng.choice(note_names) + rng.choice(accidentals)
    
    # Scale/mode selection with distinct interval patterns
    scale_library = {
        "ionian": [0, 2, 4, 5, 7, 9, 11],
        "dorian": [0, 2, 3, 5, 7, 9, 10],
        "phrygian": [0, 1, 3, 5, 7, 8, 10],
        "lydian": [0, 2, 4, 6, 7, 9, 11],
        "mixolydian": [0, 2, 4, 5, 7, 9, 10],
        "aeolian": [0, 2, 3, 5, 7, 8, 10],
        "harmonic_minor": [0, 2, 3, 5, 7, 8, 11],
        "melodic_minor": [0, 2, 3, 5, 7, 9, 11],
        "pentatonic_major": [0, 2, 4, 7, 9],
        "pentatonic_minor": [0, 3, 5, 7, 10],
    }
    
    chosen_mode = rng.choice(list(scale_library.keys()))
    intervals = scale_library[chosen_mode]
    
    # Chord progression construction
    prog_length = rng.randint(4, 8)
    roman_options = ["I", "ii", "iii", "IV", "V", "vi", "vii°"]
    progression = [rng.choice(roman_options) for _ in range(prog_length)]
    
    # Tempo parameters
    tempo = rng.randint(options.get("min_bpm", 80), options.get("max_bpm", 140))
    
    # Time signature
    time_sigs = [(3, 4), (4, 4), (5, 4), (6, 8), (7, 8)]
    numerator, denominator = rng.choice(time_sigs)
    
    # Pitch boundaries
    octave_start = rng.randint(3, 5)
    range_span = rng.randint(14, 24)
    low_note = (octave_start + 1) * 12  # MIDI octave numbering: C4 = 60, C3 = 48
    high_note = low_note + range_span
    
    # Rhythmic granularity
    note_divisions = [0.0625, 0.125, 0.25, 0.5]  # 64th, 32nd, 16th, 8th
    rhythm_grain = rng.choice(note_divisions)
    
    # Form length
    measure_count = rng.choice([4, 8, 12, 16])
    
    return HarmonySpec(
        tonic_note=root,
        scale_pattern=intervals,
        chord_sequence=progression,
        beats_per_minute=tempo,
        meter_numerator=numerator,
        meter_denominator=denominator,
        lowest_midi=low_note,
        highest_midi=high_note,
        subdivision_unit=rhythm_grain,
        total_measures=measure_count
    )
