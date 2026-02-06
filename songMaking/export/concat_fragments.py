"""
Concatenate multiple MIDI fragments with constraint-based filtering.
Generates multiple short melody fragments and assembles them into a single MIDI file.
"""
import argparse
import io
import json
from pathlib import Path
from typing import List, Tuple, Dict, Optional
import pretty_midi

from songMaking.harmony import choose_harmony, HarmonySpec
from songMaking.cli import generate_melody_midi


def analyze_pitch_stats(notes: List[pretty_midi.Note]) -> Tuple[float, int, int]:
    """
    Analyze pitch statistics from MIDI notes.
    
    Args:
        notes: List of pretty_midi.Note objects
    
    Returns:
        (mean_pitch, min_pitch, max_pitch) tuple
        Returns (0, 0, 0) if no sounding notes
    """
    # Filter out rests (pitch 0) and collect sounding pitches
    sounding_pitches = [note.pitch for note in notes if note.pitch > 0]
    
    if not sounding_pitches:
        return 0.0, 0, 0
    
    mean_pitch = sum(sounding_pitches) / len(sounding_pitches)
    min_pitch = min(sounding_pitches)
    max_pitch = max(sounding_pitches)
    
    return mean_pitch, min_pitch, max_pitch


def meets_constraints(stats: Tuple[float, int, int], config: dict) -> bool:
    """
    Check if pitch statistics meet configured constraints.
    
    Args:
        stats: (mean_pitch, min_pitch, max_pitch) tuple
        config: Configuration dict with optional keys:
                - min_pitch: Minimum allowed pitch
                - max_pitch: Maximum allowed pitch
                - target_mean_pitch: Target mean pitch
                - mean_tolerance: Tolerance around target mean
    
    Returns:
        True if all applicable constraints are met
    """
    mean_pitch, min_pitch, max_pitch = stats
    
    # If no sounding notes, accept it
    if mean_pitch == 0:
        return True
    
    # Check min_pitch constraint
    if config.get("min_pitch") is not None:
        if min_pitch < config["min_pitch"]:
            return False
    
    # Check max_pitch constraint
    if config.get("max_pitch") is not None:
        if max_pitch > config["max_pitch"]:
            return False
    
    # Check target_mean_pitch constraint
    if config.get("target_mean_pitch") is not None and config.get("mean_tolerance") is not None:
        target = config["target_mean_pitch"]
        tolerance = config["mean_tolerance"]
        if abs(mean_pitch - target) > tolerance:
            return False
    
    return True


def build_concatenated_midi(
    fragments: List[pretty_midi.PrettyMIDI],
    gap_beats: float,
    tempo: int
) -> pretty_midi.PrettyMIDI:
    """
    Build a single MIDI file by concatenating fragments with gaps.
    
    Args:
        fragments: List of PrettyMIDI objects to concatenate
        gap_beats: Gap duration in beats between fragments
        tempo: Tempo in BPM for timing calculations
    
    Returns:
        Single PrettyMIDI object containing all fragments
    """
    # Create new PrettyMIDI object
    concatenated = pretty_midi.PrettyMIDI(initial_tempo=tempo)
    
    # Create a single instrument (piano)
    instrument = pretty_midi.Instrument(program=0)  # Acoustic Grand Piano
    
    # Calculate beat duration in seconds
    beat_duration = 60.0 / tempo
    gap_seconds = gap_beats * beat_duration
    
    current_time = 0.0
    
    for fragment in fragments:
        # Find the duration of this fragment
        fragment_duration = 0.0
        
        # Get all notes from the fragment
        fragment_notes = []
        for frag_instrument in fragment.instruments:
            fragment_notes.extend(frag_instrument.notes)
        
        if fragment_notes:
            # Find the end time of the last note
            fragment_duration = max(note.end for note in fragment_notes)
        
        # Copy notes from fragment, offsetting by current_time
        for frag_instrument in fragment.instruments:
            for note in frag_instrument.notes:
                new_note = pretty_midi.Note(
                    velocity=note.velocity,
                    pitch=note.pitch,
                    start=note.start + current_time,
                    end=note.end + current_time
                )
                instrument.notes.append(new_note)
        
        # Advance time by fragment duration plus gap
        current_time += fragment_duration + gap_seconds
    
    concatenated.instruments.append(instrument)
    
    return concatenated


def export_concatenated_fragments(
    out_path: str,
    harmony: str,
    method: str,
    seed: int,
    config: dict,
    n_fragments: int = 20,
    bars: int = 2,
    gap_beats: float = 1.0
) -> None:
    """
    Generate and export concatenated MIDI fragments with constraint filtering.
    
    Args:
        out_path: Base output path (without extension)
        harmony: Harmony generation method ('auto' for choose_harmony)
        method: Melody generation method ('random', 'scored', 'markov')
        seed: Base random seed
        config: Configuration dict with optional constraints and generation params
        n_fragments: Number of fragments to generate
        bars: Number of bars per fragment (default 2)
        gap_beats: Gap duration in beats between fragments
    """
    max_attempts = config.get("max_attempts", 25)
    
    # Prepare harmony config
    harmony_config = {
        "min_bpm": config.get("min_bpm", 80),
        "max_bpm": config.get("max_bpm", 140)
    }
    
    # Prepare generation config
    generation_config = {
        "rest_probability": config.get("rest_probability", 0.15),
        "candidate_count": config.get("candidate_count", 10),
        "score_threshold": config.get("score_threshold", 0.3),
        "ngram_order": config.get("ngram_order", 2)
    }
    
    fragments_midi = []
    fragments_metadata = []
    
    print(f"Generating {n_fragments} fragments ({bars} bars each) with method '{method}'...")
    
    # Track cumulative time
    current_time_sec = 0.0
    
    for i in range(n_fragments):
        fragment_seed = seed + i
        best_fragment = None
        best_stats = None
        
        # Try to generate a fragment that meets constraints
        for attempt in range(max_attempts):
            attempt_seed = fragment_seed + attempt * 1000
            
            # Generate harmony spec with forced settings
            harmony_spec = choose_harmony(attempt_seed, harmony_config)
            
            # Force specific settings per requirements
            harmony_spec.total_measures = bars
            harmony_spec.meter_numerator = 4
            harmony_spec.meter_denominator = 4
            
            # Generate melody
            midi_bytes, pitches, durations, score = generate_melody_midi(
                harmony_spec,
                method,
                attempt_seed,
                generation_config
            )
            
            # Convert to PrettyMIDI for analysis
            pm = pretty_midi.PrettyMIDI(io.BytesIO(midi_bytes))
            
            # Analyze pitch stats
            all_notes = []
            for inst in pm.instruments:
                all_notes.extend(inst.notes)
            
            stats = analyze_pitch_stats(all_notes)
            
            # Check constraints
            if meets_constraints(stats, config):
                best_fragment = pm
                best_stats = stats
                break
            else:
                # Keep trying, but remember the last attempt
                best_fragment = pm
                best_stats = stats
        
        # Use the best (or last) fragment
        fragments_midi.append(best_fragment)
        
        # Calculate fragment duration in seconds
        fragment_duration_sec = 0.0
        for inst in best_fragment.instruments:
            if inst.notes:
                fragment_duration_sec = max(fragment_duration_sec, max(note.end for note in inst.notes))
        
        # Compute beat duration for gap
        tempo = harmony_spec.beats_per_minute
        beat_duration = 60.0 / tempo
        gap_seconds = gap_beats * beat_duration
        
        # Record metadata
        mean_pitch, min_pitch, max_pitch = best_stats
        fragment_meta = {
            "index": i,
            "start_time_sec": current_time_sec,
            "end_time_sec": current_time_sec + fragment_duration_sec,
            "duration_sec": fragment_duration_sec,
            "mean_pitch": float(mean_pitch),
            "min_pitch": int(min_pitch),
            "max_pitch": int(max_pitch),
            "seed": fragment_seed,
            "harmony": {
                "tonic": harmony_spec.tonic_note,
                "scale_pattern": harmony_spec.scale_pattern,
                "tempo_bpm": harmony_spec.beats_per_minute,
                "time_signature": f"{harmony_spec.meter_numerator}/{harmony_spec.meter_denominator}",
                "measures": harmony_spec.total_measures,
                "pitch_range": [harmony_spec.lowest_midi, harmony_spec.highest_midi]
            },
            "method": method
        }
        
        fragments_metadata.append(fragment_meta)
        
        # Advance time
        current_time_sec += fragment_duration_sec + gap_seconds
        
        if (i + 1) % 5 == 0:
            print(f"  Generated {i + 1}/{n_fragments} fragments...")
    
    print(f"All {n_fragments} fragments generated. Concatenating...")
    
    # Build concatenated MIDI
    # Use tempo from first fragment's harmony spec
    first_tempo = fragments_metadata[0]["harmony"]["tempo_bpm"]
    concatenated = build_concatenated_midi(fragments_midi, gap_beats, first_tempo)
    
    # Write MIDI file
    midi_path = f"{out_path}.mid"
    concatenated.write(midi_path)
    print(f"Saved MIDI: {midi_path}")
    
    # Write JSON metadata
    metadata = {
        "n_fragments": n_fragments,
        "bars_per_fragment": bars,
        "gap_beats": gap_beats,
        "method": method,
        "base_seed": seed,
        "config": {
            "constraints": {
                "min_pitch": config.get("min_pitch"),
                "max_pitch": config.get("max_pitch"),
                "target_mean_pitch": config.get("target_mean_pitch"),
                "mean_tolerance": config.get("mean_tolerance")
            },
            "generation": generation_config,
            "harmony": harmony_config,
            "max_attempts": max_attempts
        },
        "fragments": fragments_metadata,
        "total_duration_sec": current_time_sec - gap_seconds  # Remove last gap
    }
    
    json_path = f"{out_path}.json"
    with open(json_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    print(f"Saved metadata: {json_path}")
    
    print("\nExport complete!")


def main():
    """CLI entry point for concatenated fragment export."""
    parser = argparse.ArgumentParser(
        description="Generate and concatenate MIDI fragments with constraint filtering"
    )
    
    parser.add_argument(
        "--method",
        choices=["random", "scored", "markov"],
        default="random",
        help="Melody generation method"
    )
    
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Base random seed"
    )
    
    parser.add_argument(
        "--out",
        type=str,
        default="songMaking/output/audition_001",
        help="Output base path (without extension)"
    )
    
    parser.add_argument(
        "--n-fragments",
        type=int,
        default=20,
        help="Number of fragments to generate"
    )
    
    parser.add_argument(
        "--bars",
        type=int,
        default=2,
        help="Number of bars per fragment"
    )
    
    parser.add_argument(
        "--gap-beats",
        type=float,
        default=1.0,
        help="Gap duration in beats between fragments"
    )
    
    parser.add_argument(
        "--min-pitch",
        type=int,
        default=None,
        help="Minimum allowed pitch (MIDI note number)"
    )
    
    parser.add_argument(
        "--max-pitch",
        type=int,
        default=None,
        help="Maximum allowed pitch (MIDI note number)"
    )
    
    parser.add_argument(
        "--target-mean-pitch",
        type=int,
        default=None,
        help="Target mean pitch (MIDI note number)"
    )
    
    parser.add_argument(
        "--mean-tolerance",
        type=int,
        default=None,
        help="Tolerance around target mean pitch"
    )
    
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=25,
        help="Max attempts per fragment to meet constraints"
    )
    
    parser.add_argument(
        "--min-bpm",
        type=int,
        default=80,
        help="Minimum tempo"
    )
    
    parser.add_argument(
        "--max-bpm",
        type=int,
        default=140,
        help="Maximum tempo"
    )
    
    args = parser.parse_args()
    
    # Build config from args
    config = {
        "min_pitch": args.min_pitch,
        "max_pitch": args.max_pitch,
        "target_mean_pitch": args.target_mean_pitch,
        "mean_tolerance": args.mean_tolerance,
        "max_attempts": args.max_attempts,
        "min_bpm": args.min_bpm,
        "max_bpm": args.max_bpm
    }
    
    # Ensure output directory exists
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Run export
    export_concatenated_fragments(
        out_path=str(out_path),
        harmony="auto",
        method=args.method,
        seed=args.seed,
        config=config,
        n_fragments=args.n_fragments,
        bars=args.bars,
        gap_beats=args.gap_beats
    )


if __name__ == "__main__":
    main()
