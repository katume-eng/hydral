"""
Random melody generator with harmonic constraints.
Produces melodies using constrained randomness within HarmonySpec bounds.
"""
import random
from typing import List, Tuple
from songMaking.harmony import HarmonySpec


def generate_random_melody(spec: HarmonySpec, rng_seed: int, config: dict) -> Tuple[List[int], List[float]]:
    """
    Create melody using random selection within harmonic constraints.
    
    Args:
        spec: HarmonySpec defining tonality, range, rhythm
        rng_seed: Seed for reproducibility
        config: Additional parameters (note_density, rest_probability, etc.)
    
    Returns:
        (midi_pitches, durations_in_beats) as parallel lists
    """
    rng = random.Random(rng_seed)
    
    # Build usable pitch palette from scale
    base_midi = _note_name_to_midi(spec.tonic_note, 4)  # middle octave reference
    
    allowed_pitches = []
    for octave_offset in range(-2, 4):  # cover multiple octaves
        for interval in spec.scale_pattern:
            candidate = base_midi + (octave_offset * 12) + interval
            if spec.lowest_midi <= candidate <= spec.highest_midi:
                allowed_pitches.append(candidate)
    
    allowed_pitches = sorted(set(allowed_pitches))
    
    if not allowed_pitches:
        # Fallback if constraints too tight
        allowed_pitches = list(range(spec.lowest_midi, spec.highest_midi + 1))
    
    # Calculate total duration to fill
    beats_per_bar = spec.meter_numerator * (4.0 / spec.meter_denominator)
    total_beats = beats_per_bar * spec.total_measures
    
    # Generate note sequence
    pitches = []
    durations = []
    elapsed_beats = 0.0
    
    rest_chance = config.get("rest_probability", 0.15)
    min_duration = spec.subdivision_unit
    max_duration = beats_per_bar
    
    while elapsed_beats < total_beats:
        remaining = total_beats - elapsed_beats
        
        # Choose duration
        max_here = min(max_duration, remaining)
        # Quantize to subdivision units
        possible_lengths = []
        current = min_duration
        while current <= max_here:
            possible_lengths.append(current)
            current += min_duration
        
        if not possible_lengths:
            possible_lengths = [remaining]
        
        dur = rng.choice(possible_lengths)
        
        # Decide rest or note
        if rng.random() < rest_chance:
            # Rest (represented as MIDI 0)
            pitches.append(0)
        else:
            # Pick from allowed pitches
            # Slight preference for middle range
            if len(pitches) > 0 and pitches[-1] != 0:
                # Step motion bias
                last_pitch = pitches[-1]
                nearby = [p for p in allowed_pitches if abs(p - last_pitch) <= 4]
                if nearby and rng.random() < 0.6:
                    pitch = rng.choice(nearby)
                else:
                    pitch = rng.choice(allowed_pitches)
            else:
                pitch = rng.choice(allowed_pitches)
            
            pitches.append(pitch)
        
        durations.append(dur)
        elapsed_beats += dur
    
    return pitches, durations


def _note_name_to_midi(note_name: str, octave: int) -> int:
    """Convert note name like 'C' or 'F#' to MIDI number at given octave."""
    note_map = {
        "C": 0, "C#": 1, "Db": 1,
        "D": 2, "D#": 3, "Eb": 3,
        "E": 4, "Fb": 4, "E#": 5,
        "F": 5, "F#": 6, "Gb": 6,
        "G": 7, "G#": 8, "Ab": 8,
        "A": 9, "A#": 10, "Bb": 10,
        "B": 11, "Cb": 11, "B#": 0
    }
    
    base = note_map.get(note_name, 0)
    return (octave + 1) * 12 + base
