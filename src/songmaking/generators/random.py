"""
Random melody generator with harmonic constraints.
Produces melodies using constrained randomness within HarmonySpec bounds.
"""
import random
from typing import List, Tuple, Dict, Optional
from songmaking.harmony import HarmonySpec
from songmaking.structure import MelodyStructureSpec
from songmaking.structure_utils import (
    apply_motif_repetition,
    enforce_rhythm_profile,
    calculate_repeat_count,
    compute_duration_distribution
)
from songmaking.note_utils import (
    get_discrete_duration_values,
    snap_to_grid,
    choose_duration,
    build_scale_pitch_set,
    pick_scale_pitch,
    ensure_pitch_in_range
)


def generate_random_melody(
    spec: HarmonySpec,
    rng_seed: int,
    config: dict,
    structure_spec: Optional[MelodyStructureSpec] = None
) -> Tuple[List[int], List[float], Dict]:
    """
    Create melody using random selection within harmonic constraints.
    
    Args:
        spec: HarmonySpec defining tonality, range, rhythm
        rng_seed: Seed for reproducibility
        config: Additional parameters (note_density, rest_probability, etc.)
        structure_spec: Optional structural constraints (repetition, rhythm profile)
    
    Returns:
        (midi_pitches, durations_in_beats, debug_stats) as tuple
    """
    rng = random.Random(rng_seed)
    
    # Debug stats
    debug_stats = {
        "duration_distribution": {},
        "scale_out_rejections": 0,
        "octave_up_events": 0,
        "total_beats": 0.0,
        "repeat_count": 0,
        "actual_duration_distribution": {}
    }
    
    # Build scale pitch set
    scale_pitches = build_scale_pitch_set(
        spec.tonic_note,
        spec.scale_pattern,
        spec.lowest_midi,
        spec.highest_midi
    )
    
    if not scale_pitches:
        # Fallback if constraints too tight
        scale_pitches = list(range(spec.lowest_midi, spec.highest_midi + 1))
    
    # Calculate total duration to fill
    beats_per_bar = spec.meter_numerator * (4.0 / spec.meter_denominator)
    total_beats = beats_per_bar * spec.total_measures
    
    # Get discrete duration values
    allowed_durations = get_discrete_duration_values(beats_per_bar)
    
    # Apply rhythm profile if specified
    if structure_spec and structure_spec.rhythm_profile:
        allowed_durations = list(structure_spec.rhythm_profile.keys())
    
    # Octave-up jump chance (1-5%)
    octave_up_chance = config.get("octave_up_chance", 0.03)
    
    # Generate note sequence
    pitches = []
    durations = []
    elapsed_beats = 0.0
    
    rest_chance = config.get("rest_probability", 0.15)
    
    while elapsed_beats < total_beats:
        remaining = total_beats - elapsed_beats
        
        # Choose discrete duration
        if structure_spec and structure_spec.rhythm_profile:
            # Weight choice by rhythm profile
            dur = rng.choices(
                list(structure_spec.rhythm_profile.keys()),
                weights=list(structure_spec.rhythm_profile.values())
            )[0]
            # Ensure it fits
            if dur > remaining + 0.001:
                dur = choose_duration(remaining, allowed_durations, rng)
        else:
            dur = choose_duration(remaining, allowed_durations, rng)
        
        # Track duration usage
        dur_key = f"{dur:.3f}"
        debug_stats["duration_distribution"][dur_key] = \
            debug_stats["duration_distribution"].get(dur_key, 0) + 1
        
        # Decide rest or note
        if rng.random() < rest_chance:
            # Rest (represented as MIDI 0)
            pitches.append(0)
        else:
            # Pick from scale pitches with possible octave jump
            prev_pitch = pitches[-1] if pitches and pitches[-1] != 0 else None
            
            pitch, octave_jump = pick_scale_pitch(
                scale_pitches,
                prev_pitch,
                spec.lowest_midi,
                spec.highest_midi,
                octave_up_chance,
                rng
            )
            
            if octave_jump:
                debug_stats["octave_up_events"] += 1
            
            # Ensure in range
            pitch = ensure_pitch_in_range(
                pitch,
                scale_pitches,
                spec.lowest_midi,
                spec.highest_midi,
                rng
            )
            
            pitches.append(pitch)
        
        durations.append(dur)
        elapsed_beats = snap_to_grid(elapsed_beats + dur)
    
    # Apply structural constraints if specified
    if structure_spec and structure_spec.repeat_unit_beats:
        pitches, durations = apply_motif_repetition(
            pitches,
            durations,
            structure_spec.repeat_unit_beats,
            structure_spec.allow_motif_variation,
            structure_spec.variation_probability,
            rng
        )
        debug_stats["repeat_count"] = calculate_repeat_count(
            pitches, durations, structure_spec.repeat_unit_beats
        )
    
    # Record final stats
    debug_stats["total_beats"] = sum(durations)
    debug_stats["actual_duration_distribution"] = compute_duration_distribution(durations)
    
    return pitches, durations, debug_stats

def _note_name_to_midi(note_name: str, octave: int) -> int:
    """Convert note name like 'C' or 'F#' to MIDI number at given octave."""
    note_map = {
        "C": 0, "C#": 1, "Db": 1,
        "D": 2, "D#": 3, "Eb": 3,
        "E": 4, "Fb": 4, "E#": 5,
        "F": 5, "F#": 6, "Gb": 6,
        "G": 7, "G#": 8, "Ab": 8,
        "A": 9, "A#": 10, "Bb": 10,
        "B": 11, "Cb": 11, "B#": 12
    }
    
    base = note_map.get(note_name, 0)
    return (octave + 1) * 12 + base
