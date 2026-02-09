"""
Melody evaluation metrics for scoring generated sequences.
Used by scored generator to filter/rank candidates.
"""
from typing import List, Tuple, Dict, Optional, Any
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


def measure_self_similarity(
    midi_notes: List[int],
    durations: List[float],
    unit_beats: float
) -> float:
    """
    Measure repetition/self-similarity based on repeating unit length.
    Segments melody into units and computes similarity between them.
    
    Args:
        midi_notes: MIDI pitch sequence
        durations: Duration sequence in beats
        unit_beats: Length of repeating unit in beats
    
    Returns:
        0-1 where 1 = perfect repetition, 0 = completely random
    """
    if len(midi_notes) < 2 or unit_beats <= 0:
        return 0.0
    
    # Build time-segmented units
    units = []
    current_unit = []
    current_beats = 0.0
    
    for pitch, dur in zip(midi_notes, durations):
        current_unit.append(pitch)
        current_beats += dur
        
        # Complete unit when we've accumulated enough beats
        if current_beats >= unit_beats - 0.01:  # small tolerance
            units.append(tuple(current_unit))
            current_unit = []
            current_beats = 0.0
    
    # Need at least 2 units to compare
    if len(units) < 2:
        return 0.0
    
    # Compare consecutive units for similarity
    similarities = []
    for i in range(len(units) - 1):
        unit_a = units[i]
        unit_b = units[i + 1]
        
        # Exact match gives 1.0
        if unit_a == unit_b:
            similarities.append(1.0)
        else:
            # Partial match: count matching positions
            min_len = min(len(unit_a), len(unit_b))
            if min_len == 0:
                similarities.append(0.0)
            else:
                matches = sum(1 for j in range(min_len) if unit_a[j] == unit_b[j])
                similarities.append(matches / min_len)
    
    if not similarities:
        return 0.0
    
    return sum(similarities) / len(similarities)


def measure_rhythm_profile_alignment(
    durations: List[float],
    target_profile: Dict[float, float]
) -> float:
    """
    Measure how well actual duration distribution matches target rhythm profile.
    
    Args:
        durations: Actual durations in beats
        target_profile: Target distribution as {duration: proportion}
                       e.g., {0.5: 0.4, 1.0: 0.6}
    
    Returns:
        0-1 where 1 = perfect match, 0 = completely different
    """
    if not durations or not target_profile:
        return 0.0
    
    # Calculate actual distribution
    total_count = len(durations)
    actual_counts = {}
    for dur in durations:
        # Snap to nearest target duration for comparison
        nearest = min(target_profile.keys(), key=lambda d: abs(d - dur))
        actual_counts[nearest] = actual_counts.get(nearest, 0) + 1
    
    actual_proportions = {d: count / total_count for d, count in actual_counts.items()}
    
    # Calculate similarity using sum of absolute differences
    # Start with all target durations
    all_durations = set(target_profile.keys()) | set(actual_proportions.keys())
    
    total_difference = 0.0
    for dur in all_durations:
        target_prop = target_profile.get(dur, 0.0)
        actual_prop = actual_proportions.get(dur, 0.0)
        total_difference += abs(target_prop - actual_prop)
    
    # Normalize: max difference is 2.0 (all in wrong bucket)
    # Return 1.0 - (difference / 2.0) for 0-1 score
    similarity = 1.0 - (total_difference / 2.0)
    return max(0.0, min(1.0, similarity))


def aggregate_melody_score(
    midi_notes: List[int],
    durations: List[float],
    weights: dict = None,
    structure_spec: Optional[Any] = None
) -> Tuple[float, dict]:
    """
    Combine all evaluation metrics into single score.
    
    Args:
        midi_notes: MIDI pitch sequence
        durations: Duration sequence in beats
        weights: Metric weights (None = use defaults)
        structure_spec: Optional MelodyStructureSpec for structural scoring
    
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
    
    # Add structural metrics if spec provided
    if structure_spec is not None:
        if hasattr(structure_spec, 'repeat_unit_beats') and structure_spec.repeat_unit_beats is not None:
            metrics["self_similarity"] = measure_self_similarity(
                midi_notes, durations, structure_spec.repeat_unit_beats
            )
            # Add weight for self-similarity
            if "self_similarity" not in weights:
                weights["self_similarity"] = 0.15
        
        if hasattr(structure_spec, 'rhythm_profile') and structure_spec.rhythm_profile is not None:
            metrics["rhythm_alignment"] = measure_rhythm_profile_alignment(
                durations, structure_spec.rhythm_profile
            )
            # Add weight for rhythm alignment
            if "rhythm_alignment" not in weights:
                weights["rhythm_alignment"] = 0.15
    
    # Normalize weights to sum to 1.0
    total_weight = sum(weights.get(k, 0.0) for k in metrics)
    if total_weight > 0:
        normalized_weights = {k: weights.get(k, 0.0) / total_weight for k in metrics}
    else:
        normalized_weights = weights
    
    total = sum(metrics[k] * normalized_weights.get(k, 0.0) for k in metrics)
    
    return total, metrics
