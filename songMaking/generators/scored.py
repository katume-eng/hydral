"""
Scored melody generator - generates multiple candidates and selects best.
Uses evaluation metrics to rank and filter melodies.
"""
import random
from typing import List, Tuple
from songMaking.harmony import HarmonySpec
from songMaking.generators.random import generate_random_melody
from songMaking.eval import aggregate_melody_score


def generate_scored_melody(spec: HarmonySpec, rng_seed: int, config: dict) -> Tuple[List[int], List[float], float]:
    """
    Generate multiple melody candidates and return highest-scoring one.
    
    Args:
        spec: HarmonySpec defining musical context
        rng_seed: Base seed for reproducibility
        config: Parameters including candidate_count, score_threshold
    
    Returns:
        (midi_pitches, durations, score) for best candidate
    """
    num_candidates = config.get("candidate_count", 10)
    min_acceptable = config.get("score_threshold", 0.3)
    
    candidates = []
    
    for attempt in range(num_candidates):
        # Derive unique seed for each candidate
        trial_seed = rng_seed + attempt * 1000
        
        pitches, durations = generate_random_melody(spec, trial_seed, config)
        
        # Filter out rests for scoring
        sounding_notes = [p for p in pitches if p > 0]
        
        if len(sounding_notes) < 4:
            # Too sparse, skip
            continue
        
        score, metrics = aggregate_melody_score(sounding_notes, durations)
        
        if score >= min_acceptable:
            candidates.append((pitches, durations, score, metrics))
    
    if not candidates:
        # No candidate met threshold, use first attempt anyway
        pitches, durations = generate_random_melody(spec, rng_seed, config)
        score, _ = aggregate_melody_score([p for p in pitches if p > 0], durations)
        return pitches, durations, score
    
    # Sort by score descending
    candidates.sort(key=lambda x: x[2], reverse=True)
    
    best_pitches, best_durations, best_score, _ = candidates[0]
    
    return best_pitches, best_durations, best_score
