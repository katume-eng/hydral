"""
Scored melody generator - generates multiple candidates and selects best.
Uses evaluation metrics to rank and filter melodies.
"""
import random
from typing import List, Tuple, Dict
from songMaking.harmony import HarmonySpec
from songMaking.generators.random import generate_random_melody
from songMaking.eval import aggregate_melody_score
from songMaking.note_utils import (
    get_discrete_duration_values,
    is_pitch_in_scale,
    build_scale_pitch_set
)


def generate_scored_melody(spec: HarmonySpec, rng_seed: int, config: dict) -> Tuple[List[int], List[float], float, Dict]:
    """
    Generate multiple melody candidates and return highest-scoring one.
    Rejects candidates with out-of-scale pitches or invalid durations.
    
    Args:
        spec: HarmonySpec defining musical context
        rng_seed: Base seed for reproducibility
        config: Parameters including candidate_count, score_threshold
    
    Returns:
        (midi_pitches, durations, score, debug_stats) for best candidate
    """
    num_candidates = config.get("candidate_count", 10)
    min_acceptable = config.get("score_threshold", 0.3)
    
    # Build scale for validation
    scale_pitches = build_scale_pitch_set(
        spec.tonic_note,
        spec.scale_pattern,
        spec.lowest_midi,
        spec.highest_midi
    )
    
    # Get valid durations
    beats_per_bar = spec.meter_numerator * (4.0 / spec.meter_denominator)
    valid_durations = set(get_discrete_duration_values(beats_per_bar))
    
    candidates = []
    combined_debug_stats = {
        "duration_distribution": {},
        "scale_out_rejections": 0,
        "octave_up_events": 0,
        "total_beats": 0.0
    }
    
    for attempt in range(num_candidates):
        # Derive unique seed for each candidate
        trial_seed = rng_seed + attempt * 1000
        
        pitches, durations, debug_stats = generate_random_melody(spec, trial_seed, config)
        
        # Validation: check for out-of-scale notes
        scale_violation = False
        for pitch in pitches:
            if pitch > 0 and not is_pitch_in_scale(pitch, scale_pitches):
                scale_violation = True
                combined_debug_stats["scale_out_rejections"] += 1
                break
        
        if scale_violation:
            continue
        
        # Validation: check for invalid durations
        invalid_duration = False
        for dur in durations:
            # Allow small floating point tolerance
            if not any(abs(dur - vd) < 0.001 for vd in valid_durations):
                invalid_duration = True
                break
        
        if invalid_duration:
            continue
        
        # Filter out rests for scoring
        sounding_notes = [p for p in pitches if p > 0]
        
        if len(sounding_notes) < 4:
            # Too sparse, skip
            continue
        
        score, metrics = aggregate_melody_score(sounding_notes, durations)
        
        if score >= min_acceptable:
            candidates.append((pitches, durations, score, metrics, debug_stats))
    
    if not candidates:
        # No candidate met threshold, generate one more and use it anyway
        pitches, durations, debug_stats = generate_random_melody(spec, rng_seed, config)
        score, _ = aggregate_melody_score([p for p in pitches if p > 0], durations)
        
        # Merge debug stats
        for key in debug_stats.get("duration_distribution", {}):
            combined_debug_stats["duration_distribution"][key] = \
                combined_debug_stats["duration_distribution"].get(key, 0) + \
                debug_stats["duration_distribution"][key]
        combined_debug_stats["octave_up_events"] += debug_stats.get("octave_up_events", 0)
        combined_debug_stats["total_beats"] = debug_stats.get("total_beats", sum(durations))
        
        return pitches, durations, score, combined_debug_stats
    
    # Sort by score descending
    candidates.sort(key=lambda x: x[2], reverse=True)
    
    best_pitches, best_durations, best_score, _, best_debug = candidates[0]
    
    # Merge all debug stats
    for _, _, _, _, debug_stats in candidates:
        for key in debug_stats.get("duration_distribution", {}):
            combined_debug_stats["duration_distribution"][key] = \
                combined_debug_stats["duration_distribution"].get(key, 0) + \
                debug_stats["duration_distribution"][key]
        combined_debug_stats["octave_up_events"] += debug_stats.get("octave_up_events", 0)
    
    combined_debug_stats["total_beats"] = best_debug.get("total_beats", sum(best_durations))
    
    return best_pitches, best_durations, best_score, combined_debug_stats
