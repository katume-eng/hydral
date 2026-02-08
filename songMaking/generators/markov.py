"""
Markov-based melody generator using n-gram transitions.
Trains on synthetic patterns then generates new sequences.
Quantizes all output to scale notes.
"""
import random
from typing import List, Tuple, Dict
from collections import defaultdict
from songMaking.harmony import HarmonySpec
from songMaking.note_utils import (
    get_discrete_duration_values,
    snap_to_grid,
    choose_duration,
    build_scale_pitch_set,
    pick_scale_pitch,
    ensure_pitch_in_range
)


class PitchTransitionModel:
    """N-gram model for pitch transitions."""
    
    def __init__(self, order: int = 1):
        self.order = order  # how many previous notes to consider
        self.transitions = defaultdict(list)  # context -> list of next notes
    
    def train_from_patterns(self, training_sequences: List[List[int]]):
        """Learn transition probabilities from example sequences."""
        for sequence in training_sequences:
            for idx in range(len(sequence) - self.order):
                context = tuple(sequence[idx:idx + self.order])
                next_note = sequence[idx + self.order]
                self.transitions[context].append(next_note)
    
    def predict_next(self, context: Tuple[int, ...], rng: random.Random) -> int:
        """Predict next note given context, with randomness."""
        if context in self.transitions and self.transitions[context]:
            return rng.choice(self.transitions[context])
        
        # Fallback: pick from any observed note
        all_notes = []
        for followers in self.transitions.values():
            all_notes.extend(followers)
        
        if all_notes:
            return rng.choice(all_notes)
        
        return 60  # fallback to middle C


def _create_training_data(spec: HarmonySpec, rng: random.Random) -> List[List[int]]:
    """
    Generate synthetic training sequences based on harmonic spec.
    Creates varied melodic patterns for model to learn from.
    """
    # Build scale pitches
    scale_notes = build_scale_pitch_set(
        spec.tonic_note,
        spec.scale_pattern,
        spec.lowest_midi,
        spec.highest_midi
    )
    
    if not scale_notes:
        scale_notes = list(range(spec.lowest_midi, spec.highest_midi + 1))
    
    # Generate varied patterns
    patterns = []
    
    # Pattern type 1: Ascending/descending scales
    for start_idx in range(len(scale_notes) - 5):
        ascending = scale_notes[start_idx:start_idx + 5]
        patterns.append(ascending)
        patterns.append(list(reversed(ascending)))
    
    # Pattern type 2: Arpeggios (skip notes)
    for start_idx in range(0, len(scale_notes) - 8, 2):
        arpeggio = [scale_notes[start_idx + i] for i in range(0, 8, 2)]
        patterns.append(arpeggio)
    
    # Pattern type 3: Neighbor tones
    for center_idx in range(1, len(scale_notes) - 1):
        neighbor = [
            scale_notes[center_idx],
            scale_notes[center_idx + 1],
            scale_notes[center_idx],
            scale_notes[center_idx - 1],
            scale_notes[center_idx]
        ]
        patterns.append(neighbor)
    
    # Pattern type 4: Random walks
    for _ in range(10):
        walk_length = rng.randint(6, 10)
        walk = [rng.choice(scale_notes)]
        for _ in range(walk_length - 1):
            current_idx = scale_notes.index(walk[-1])
            # Prefer nearby notes
            move = rng.choice([-2, -1, 0, 1, 2])
            next_idx = max(0, min(len(scale_notes) - 1, current_idx + move))
            walk.append(scale_notes[next_idx])
        patterns.append(walk)
    
    return patterns


def _quantize_to_nearest_scale_note(pitch: int, scale_pitches: List[int]) -> int:
    """Find nearest pitch in scale."""
    if pitch in scale_pitches:
        return pitch
    
    # Find closest
    closest = min(scale_pitches, key=lambda p: abs(p - pitch))
    return closest


def generate_markov_melody(spec: HarmonySpec, rng_seed: int, config: dict) -> Tuple[List[int], List[float], Dict]:
    """
    Generate melody using Markov chain trained on synthetic patterns.
    Quantizes all transitions to nearest scale note.
    
    Args:
        spec: HarmonySpec defining musical context
        rng_seed: Seed for reproducibility
        config: Additional parameters (ngram_order, etc.)
    
    Returns:
        (midi_pitches, durations, debug_stats) as tuple
    """
    rng = random.Random(rng_seed)
    
    # Debug stats
    debug_stats = {
        "duration_distribution": {},
        "scale_out_rejections": 0,
        "octave_up_events": 0,
        "total_beats": 0.0
    }
    
    # Build and train model
    model_order = config.get("ngram_order", 2)
    model = PitchTransitionModel(order=model_order)
    
    training_patterns = _create_training_data(spec, rng)
    model.train_from_patterns(training_patterns)
    
    # Calculate target length
    beats_per_bar = spec.meter_numerator * (4.0 / spec.meter_denominator)
    total_beats = beats_per_bar * spec.total_measures
    
    # Get discrete durations
    allowed_durations = get_discrete_duration_values(beats_per_bar)
    
    # Build scale
    scale_notes = build_scale_pitch_set(
        spec.tonic_note,
        spec.scale_pattern,
        spec.lowest_midi,
        spec.highest_midi
    )
    if not scale_notes:
        scale_notes = list(range(spec.lowest_midi, spec.highest_midi + 1))
    
    # Octave-up jump chance
    octave_up_chance = config.get("octave_up_chance", 0.03)
    
    # Generate pitch sequence
    pitches = []
    durations = []
    
    # Start with random context from scale
    for _ in range(model_order):
        pitch = rng.choice(scale_notes)
        pitches.append(pitch)
    
    # Generate until we fill duration
    elapsed_beats = 0.0
    
    note_idx = 0
    while elapsed_beats < total_beats:
        # Add duration for current note
        remaining = total_beats - elapsed_beats
        dur = choose_duration(remaining, allowed_durations, rng)
        
        # Track duration
        dur_key = f"{dur:.3f}"
        debug_stats["duration_distribution"][dur_key] = \
            debug_stats["duration_distribution"].get(dur_key, 0) + 1
        
        durations.append(dur)
        elapsed_beats = snap_to_grid(elapsed_beats + dur)
        
        # Predict next pitch if we need more
        if elapsed_beats < total_beats:
            context = tuple(pitches[-model_order:])
            next_pitch = model.predict_next(context, rng)
            
            # Quantize to nearest scale note
            if next_pitch not in scale_notes:
                next_pitch = _quantize_to_nearest_scale_note(next_pitch, scale_notes)
                # Track scale corrections (parallel to scored's rejection of entire candidates)
                debug_stats["scale_out_rejections"] += 1
            
            # Ensure in range (resample if needed)
            next_pitch = ensure_pitch_in_range(
                next_pitch,
                scale_notes,
                spec.lowest_midi,
                spec.highest_midi,
                rng
            )
            
            pitches.append(next_pitch)
        
        note_idx += 1
    
    # Ensure lists are same length
    pitches = pitches[:len(durations)]
    
    # Record final total
    debug_stats["total_beats"] = sum(durations)
    
    return pitches, durations, debug_stats
