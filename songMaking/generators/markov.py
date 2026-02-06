"""
Markov-based melody generator using n-gram transitions.
Trains on synthetic patterns then generates new sequences.
"""
import random
from typing import List, Tuple, Dict
from collections import defaultdict
from songMaking.harmony import HarmonySpec


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
    base_midi = 60  # C4
    
    # Build scale pitches
    scale_notes = []
    for octave in range(-1, 3):
        for interval in spec.scale_pattern:
            pitch = base_midi + (octave * 12) + interval
            if spec.lowest_midi <= pitch <= spec.highest_midi:
                scale_notes.append(pitch)
    
    scale_notes = sorted(set(scale_notes))
    
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


def generate_markov_melody(spec: HarmonySpec, rng_seed: int, config: dict) -> Tuple[List[int], List[float]]:
    """
    Generate melody using Markov chain trained on synthetic patterns.
    
    Args:
        spec: HarmonySpec defining musical context
        rng_seed: Seed for reproducibility
        config: Additional parameters (ngram_order, etc.)
    
    Returns:
        (midi_pitches, durations) as parallel lists
    """
    rng = random.Random(rng_seed)
    
    # Build and train model
    model_order = config.get("ngram_order", 2)
    model = PitchTransitionModel(order=model_order)
    
    training_patterns = _create_training_data(spec, rng)
    model.train_from_patterns(training_patterns)
    
    # Calculate target length
    beats_per_bar = spec.meter_numerator * (4.0 / spec.meter_denominator)
    total_beats = beats_per_bar * spec.total_measures
    
    # Generate pitch sequence
    pitches = []
    durations = []
    
    # Initialize with random starting context
    base_midi = 60
    scale_notes = []
    for octave in range(-1, 3):
        for interval in spec.scale_pattern:
            pitch = base_midi + (octave * 12) + interval
            if spec.lowest_midi <= pitch <= spec.highest_midi:
                scale_notes.append(pitch)
    
    scale_notes = sorted(set(scale_notes))
    if not scale_notes:
        scale_notes = list(range(spec.lowest_midi, spec.highest_midi + 1))
    
    # Start with random context
    for _ in range(model_order):
        pitches.append(rng.choice(scale_notes))
    
    # Generate until we fill duration
    elapsed_beats = 0.0
    min_dur = spec.subdivision_unit
    max_dur = beats_per_bar / 2
    
    note_idx = 0
    while elapsed_beats < total_beats:
        # Add duration for current note
        remaining = total_beats - elapsed_beats
        dur_options = []
        d = min_dur
        while d <= min(max_dur, remaining):
            dur_options.append(d)
            d += min_dur
        
        if not dur_options:
            dur_options = [remaining]
        
        durations.append(rng.choice(dur_options))
        elapsed_beats += durations[-1]
        
        # Predict next pitch if we need more
        if elapsed_beats < total_beats:
            context = tuple(pitches[-model_order:])
            next_pitch = model.predict_next(context, rng)
            pitches.append(next_pitch)
        
        note_idx += 1
    
    # Ensure lists are same length
    pitches = pitches[:len(durations)]
    
    return pitches, durations
