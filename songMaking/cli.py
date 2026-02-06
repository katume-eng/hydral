"""
Command-line interface for melody generation.
Entry point for songMaking system.
"""
import argparse
import json
import logging
import os
from datetime import datetime
from pathlib import Path

from songMaking.harmony import choose_harmony
from songMaking.generators.random import generate_random_melody
from songMaking.generators.scored import generate_scored_melody
from songMaking.generators.markov import generate_markov_melody
from songMaking.export_midi import create_melody_midi, save_midi_file
from songMaking.eval import aggregate_melody_score
from songMaking.pitch_stats import check_pitch_constraint, get_pitch_stats

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)


def generate_melody_midi(harmony_spec, method: str, seed: int, config: dict):
    """
    Generate MIDI melody using specified method and harmonic context.
    
    Args:
        harmony_spec: HarmonySpec defining musical parameters
        method: Generator method name ('random', 'scored', 'markov')
        seed: Random seed for reproducibility
        config: Method-specific configuration
    
    Returns:
        (midi_bytes, pitches, durations, score_value, pitch_stats)
    """
    if method == "random":
        pitches, durations = generate_random_melody(harmony_spec, seed, config)
        score_value = None
    elif method == "scored":
        pitches, durations, score_value = generate_scored_melody(harmony_spec, seed, config)
    elif method == "markov":
        pitches, durations = generate_markov_melody(harmony_spec, seed, config)
        score_value = None
    else:
        raise ValueError(f"Unknown method: {method}")
    
    # Create MIDI
    midi_bytes = create_melody_midi(
        pitches,
        durations,
        harmony_spec.beats_per_minute,
        (harmony_spec.meter_numerator, harmony_spec.meter_denominator)
    )
    
    # Calculate score if not already done
    if score_value is None:
        sounding = [p for p in pitches if p > 0]
        if sounding:
            score_value, _ = aggregate_melody_score(sounding, durations)
        else:
            score_value = 0.0
    
    # Calculate pitch statistics
    pitch_stats = get_pitch_stats(pitches)
    
    return midi_bytes, pitches, durations, score_value, pitch_stats


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Generate MIDI melodies using various algorithms"
    )
    
    parser.add_argument(
        "--method",
        choices=["random", "scored", "markov"],
        default="random",
        help="Generation method to use"
    )
    
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility"
    )
    
    parser.add_argument(
        "--output-dir",
        type=str,
        default="songMaking/output",
        help="Output directory for MIDI and JSON files"
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
    
    parser.add_argument(
        "--candidates",
        type=int,
        default=10,
        help="Number of candidates for scored method"
    )
    
    parser.add_argument(
        "--ngram-order",
        type=int,
        default=2,
        help="N-gram order for markov method"
    )
    
    parser.add_argument(
        "--bars",
        type=int,
        default=2,
        help="Number of bars/measures in 4/4 time (default: 2, typical for short melodic phrases)"
    )
    
    parser.add_argument(
        "--mean-pitch-target",
        type=float,
        default=None,
        help="Target mean pitch in MIDI (e.g., 60 for middle C). If specified, generation will retry until constraint is met."
    )
    
    parser.add_argument(
        "--mean-pitch-tolerance",
        type=float,
        default=2.0,
        help="Tolerance for mean pitch target in semitones (default: 2.0)"
    )
    
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=100,
        help="Maximum generation attempts when using pitch constraints (default: 100)"
    )
    
    args = parser.parse_args()
    
    # Prepare configuration
    harmony_config = {
        "min_bpm": args.min_bpm,
        "max_bpm": args.max_bpm,
        "bars": args.bars
    }
    
    generation_config = {
        "rest_probability": 0.15,
        "candidate_count": args.candidates,
        "score_threshold": 0.3,
        "ngram_order": args.ngram_order
    }
    
    # Generate harmony specification
    print(f"Generating harmony specification with seed {args.seed}...")
    harmony_spec = choose_harmony(args.seed, harmony_config)
    
    print(f"Key: {harmony_spec.tonic_note}")
    print(f"Scale: {harmony_spec.scale_pattern}")
    print(f"Tempo: {harmony_spec.beats_per_minute} BPM")
    print(f"Time: {harmony_spec.meter_numerator}/{harmony_spec.meter_denominator}")
    print(f"Measures: {harmony_spec.total_measures}")
    
    # Display pitch constraint if enabled
    if args.mean_pitch_target is not None:
        print(f"\nPitch constraint enabled:")
        print(f"  Target mean pitch: {args.mean_pitch_target:.1f} MIDI")
        print(f"  Tolerance: ±{args.mean_pitch_tolerance:.1f} semitones")
        print(f"  Max attempts: {args.max_attempts}")
    
    # Generate melody with retry loop for pitch constraints
    print(f"\nGenerating melody using '{args.method}' method...")
    
    attempt = 0
    midi_bytes = None
    pitches = None
    durations = None
    score = None
    pitch_stats = None
    
    while attempt < args.max_attempts:
        attempt += 1
        
        # Use different seed for each attempt to get variation
        attempt_seed = args.seed + attempt - 1
        
        midi_bytes, pitches, durations, score, pitch_stats = generate_melody_midi(
            harmony_spec,
            args.method,
            attempt_seed,
            generation_config
        )
        
        # Check if pitch constraint is satisfied (or not enabled)
        if args.mean_pitch_target is None:
            # No constraint - accept first generation
            break
        elif pitch_stats["mean"] is not None and check_pitch_constraint(
            pitches,
            args.mean_pitch_target,
            args.mean_pitch_tolerance
        ):
            # Constraint satisfied
            print(f"Constraint satisfied on attempt {attempt}")
            print(f"  Generated mean pitch: {pitch_stats['mean']:.2f}")
            break
        else:
            # Constraint not satisfied - try again
            if pitch_stats["mean"] is not None:
                logging.debug(
                    f"Attempt {attempt}: mean pitch {pitch_stats['mean']:.2f} "
                    f"outside range [{args.mean_pitch_target - args.mean_pitch_tolerance:.2f}, "
                    f"{args.mean_pitch_target + args.mean_pitch_tolerance:.2f}]"
                )
    
    # Check if we failed to meet constraint
    if args.mean_pitch_target is not None and attempt >= args.max_attempts:
        final_mean = f"{pitch_stats['mean']:.2f}" if pitch_stats and pitch_stats["mean"] is not None else "N/A"
        print(f"\nWarning: Failed to meet pitch constraint after {args.max_attempts} attempts")
        print(f"Final mean pitch: {final_mean}")
        print("Using last generated melody anyway.")
    
    print(f"Generated {len(pitches)} notes")
    print(f"Quality score: {score:.3f}")
    
    # Prepare output directory
    output_path = Path(args.output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Create timestamp-based filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"melody_{args.method}_seed{args.seed}_{timestamp}"
    
    # Save MIDI file
    midi_filename = output_path / f"{base_name}.mid"
    save_midi_file(midi_bytes, str(midi_filename))
    print(f"\nSaved MIDI: {midi_filename}")
    
    # Save metadata JSON
    metadata = {
        "method": args.method,
        "seed": args.seed,
        "timestamp": timestamp,
        "harmony": {
            "tonic": harmony_spec.tonic_note,
            "scale_intervals": harmony_spec.scale_pattern,
            "chord_progression": harmony_spec.chord_sequence,
            "tempo_bpm": harmony_spec.beats_per_minute,
            "time_signature": f"{harmony_spec.meter_numerator}/{harmony_spec.meter_denominator}",
            "pitch_range": [harmony_spec.lowest_midi, harmony_spec.highest_midi],
            "subdivision": harmony_spec.subdivision_unit,
            "measures": harmony_spec.total_measures
        },
        "generation_config": generation_config,
        "pitch_constraint": {
            "enabled": args.mean_pitch_target is not None,
            "target_mean": args.mean_pitch_target,
            "tolerance": args.mean_pitch_tolerance if args.mean_pitch_target is not None else None,
            "max_attempts": args.max_attempts if args.mean_pitch_target is not None else None,
            "attempts_used": attempt if args.mean_pitch_target is not None else 1
        },
        "result": {
            "note_count": len(pitches),
            "quality_score": round(score, 4),
            "total_duration_beats": sum(durations),
            "pitch_stats": {
                "mean": round(pitch_stats["mean"], 2) if pitch_stats["mean"] is not None else None,
                "min": pitch_stats["min"],
                "max": pitch_stats["max"],
                "range": pitch_stats["range"],
                "sounding_count": pitch_stats["sounding_count"]
            }
        }
    }
    
    json_filename = output_path / f"{base_name}.json"
    with open(json_filename, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"Saved metadata: {json_filename}")
    print("\nGeneration complete!")


if __name__ == "__main__":
    main()
