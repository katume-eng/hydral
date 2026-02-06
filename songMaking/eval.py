"""
Melody evaluation metrics for scoring generated sequences.
Used by scored generator to filter/rank candidates.
"""
from typing import List, Tuple
import statistics


def compute_interval_complexity(midi_notes: List[int]) -> float:
    """
    Calculate harmonic complexity from interval distribution.
    Returns 0-1 where higher = more varied intervals.
    """
    if len(midi_notes) < 2:
        return 0.0
    
    jumps = [abs(midi_notes[i+1] - midi_notes[i]) for i in range(len(midi_notes)-1)]
    
    if not jumps:
        return 0.0
    
    # Count unique interval sizes
    unique_intervals = len(set(jumps))
    max_possible = min(12, len(jumps))  # within one octave
    
    return unique_intervals / max(max_possible, 1)


def measure_contour_balance(midi_notes: List[int]) -> float:
    """
    Evaluate melodic contour balance (ascending vs descending motion).
    Returns 0-1 where 0.5 is perfectly balanced.
    """
    if len(midi_notes) < 2:
        return 0.5
    
    up_moves = sum(1 for i in range(len(midi_notes)-1) if midi_notes[i+1] > midi_notes[i])
    down_moves = sum(1 for i in range(len(midi_notes)-1) if midi_notes[i+1] < midi_notes[i])
    
    total_moves = up_moves + down_moves
    if total_moves == 0:
        return 0.0  # all repeated notes - not balanced
    
    ratio = min(up_moves, down_moves) / total_moves
    return ratio


def check_leap_smoothness(midi_notes: List[int], max_jump: int = 7) -> float:
    """
    Penalize excessive melodic leaps.
    Returns 1.0 if all intervals within max_jump, lower if not.
    """
    if len(midi_notes) < 2:
        return 1.0
    
    jumps = [abs(midi_notes[i+1] - midi_notes[i]) for i in range(len(midi_notes)-1)]
    violations = sum(1 for j in jumps if j > max_jump)
    
    return 1.0 - (violations / len(jumps))


def assess_pitch_variety(midi_notes: List[int]) -> float:
    """
    Measure pitch class diversity.
    Returns 0-1 based on unique pitches used.
    """
    if not midi_notes:
        return 0.0
    
    unique_pitches = len(set(midi_notes))
    return min(unique_pitches / 7, 1.0)  # normalize to 7 scale degrees


def evaluate_rhythmic_entropy(durations: List[float]) -> float:
    """
    Calculate rhythmic variety from duration distribution.
    Higher values indicate more rhythmic diversity.
    """
    if len(durations) < 2:
        return 0.0
    
    unique_rhythms = len(set(durations))
    return min(unique_rhythms / 5, 1.0)  # cap at 5 different durations


def compute_phrase_coherence(midi_notes: List[int], phrase_len: int = 4) -> float:
    """
    Assess phrase-level repetition and structure.
    Looks for motivic consistency across segments.
    """
    if len(midi_notes) < phrase_len * 2:
        return 0.5
    
    # Break into phrases
    phrases = []
    for start in range(0, len(midi_notes) - phrase_len + 1, phrase_len):
        phrases.append(tuple(midi_notes[start:start + phrase_len]))
    
    if len(phrases) < 2:
        return 0.5
    
    # Calculate phrase similarity (simple matching)
    matches = 0
    comparisons = 0
    for i in range(len(phrases)):
        for j in range(i + 1, len(phrases)):
            comparisons += 1
            if phrases[i] == phrases[j]:
                matches += 1
    
    if comparisons == 0:
        return 0.5
    
    return matches / comparisons


def aggregate_melody_score(
    midi_notes: List[int],
    durations: List[float],
    weights: dict = None
) -> Tuple[float, dict]:
    """
    Combine all evaluation metrics into single score.
    
    Returns:
        (total_score, individual_metrics) where total is 0-1
    """
    if weights is None:
        weights = {
            "complexity": 0.15,
            "contour": 0.20,
            "smoothness": 0.25,
            "variety": 0.20,
            "rhythm": 0.10,
            "coherence": 0.10
        }
    
    metrics = {
        "complexity": compute_interval_complexity(midi_notes),
        "contour": measure_contour_balance(midi_notes),
        "smoothness": check_leap_smoothness(midi_notes),
        "variety": assess_pitch_variety(midi_notes),
        "rhythm": evaluate_rhythmic_entropy(durations),
        "coherence": compute_phrase_coherence(midi_notes)
    }
    
    total = sum(metrics[k] * weights.get(k, 0.0) for k in metrics)
    
    return total, metrics
