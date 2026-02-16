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
from songMaking.structure import MelodyStructureSpec, create_default_structure_spec, create_structured_spec
from songMaking.generators.random import generate_random_melody
from songMaking.generators.scored import generate_scored_melody
from songMaking.generators.markov import generate_markov_melody
from songMaking.export_midi import create_melody_midi, save_midi_file
from songMaking.eval import aggregate_melody_score
from songMaking.pitch_stats import (
    check_pitch_constraint,
    get_pitch_stats,
    compute_pitch_stats,
    extract_melody_pitches_from_midi,
    calculate_mean_interval
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)


def generate_melody_midi(harmony_spec, method: str, seed: int, config: dict, structure_spec=None):
    """
    Generate MIDI melody using specified method and harmonic context.
    
    Args:
        harmony_spec: HarmonySpec defining musical parameters
        method: Generator method name ('random', 'scored', 'markov')
        seed: Random seed for reproducibility
        config: Method-specific configuration
        structure_spec: Optional MelodyStructureSpec for structural constraints
    
    Returns:
        (midi_bytes, pitches, durations, score_value, pitch_stats, debug_stats, enhanced_pitch_stats)
    """
    debug_stats = {}
    
    if method == "random":
        pitches, durations, debug_stats = generate_random_melody(
            harmony_spec, seed, config, structure_spec
        )
        score_value = None
    elif method == "scored":
        pitches, durations, score_value, debug_stats = generate_scored_melody(
            harmony_spec, seed, config, structure_spec
        )
    elif method == "markov":
        pitches, durations, debug_stats = generate_markov_melody(
            harmony_spec, seed, config, structure_spec
        )
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
            score_value, _ = aggregate_melody_score(sounding, durations, structure_spec=structure_spec)
        else:
            score_value = 0.0
    
    # Calculate pitch statistics
    pitch_stats = get_pitch_stats(pitches)
    
    # Calculate enhanced pitch statistics for JSON export
    enhanced_pitch_stats = compute_pitch_stats(pitches)
    
    return midi_bytes, pitches, durations, score_value, pitch_stats, debug_stats, enhanced_pitch_stats


def resolve_batch_id(output_root: Path, requested_id: str | None) -> str:
    """バッチIDを確定する。"""
    if requested_id:
        candidate_dir = output_root / f"batch_{requested_id}"
        if candidate_dir.exists():
            raise FileExistsError(f"出力先が既に存在します: {candidate_dir}")
        return requested_id

    base_date = datetime.now().strftime("%Y-%m-%d")
    for offset in range(26):
        suffix = chr(ord("A") + offset)
        batch_id = f"{base_date}-{suffix}"
        candidate_dir = output_root / f"batch_{batch_id}"
        if not candidate_dir.exists():
            return batch_id

    raise RuntimeError("同日のバッチIDが上限に達しました。")


def render_midi_to_wav(midi_path: Path, wav_path: Path, soundfont_path: str | None) -> bool:
    """MIDIからWAVをレンダリングする。"""
    if not soundfont_path:
        print("WAVレンダリングには--soundfontが必要なためスキップします。")
        return False

    sf2_path = Path(soundfont_path)
    if not sf2_path.exists():
        print(f"SoundFontが見つかりません: {sf2_path}")
        return False

    try:
        import pretty_midi
        import soundfile as sf
    except ImportError as exc:
        print(f"WAVレンダリングに必要なライブラリが不足しています: {exc}")
        return False

    try:
        midi_data = pretty_midi.PrettyMIDI(str(midi_path))
        sample_rate = 44100
        audio = midi_data.fluidsynth(fs=sample_rate, sf2_path=str(sf2_path))
        sf.write(str(wav_path), audio, sample_rate)
    except Exception as exc:
        print(f"WAVレンダリングに失敗しました: {exc}")
        return False

    return True


def generate_and_save(
    args,
    seed: int,
    harmony_config: dict,
    generation_config: dict,
    structure_spec,
    output_path: Path,
    batch_id: str | None = None,
    batch_index: int | None = None,
    render_wav: bool = False,
    soundfont_path: str | None = None
):
    """指定パラメータでメロディを生成して保存する。"""
    print(f"Generating harmony specification with seed {seed}...")
    harmony_spec = choose_harmony(seed, harmony_config)

    print(f"Key: {harmony_spec.tonic_note}")
    print(f"Scale: {harmony_spec.scale_pattern}")
    print(f"Tempo: {harmony_spec.beats_per_minute} BPM")
    print(f"Time: {harmony_spec.meter_numerator}/{harmony_spec.meter_denominator}")
    print(f"Measures: {harmony_spec.total_measures}")

    if structure_spec:
        print("\nStructural constraints enabled:")
        if structure_spec.repeat_unit_beats:
            print(f"  Repeat unit: {structure_spec.repeat_unit_beats} beats")
            print(f"  Allow variations: {structure_spec.allow_motif_variation}")
            if structure_spec.allow_motif_variation:
                print(f"  Variation probability: {structure_spec.variation_probability}")
        if structure_spec.rhythm_profile:
            print(f"  Rhythm profile: {structure_spec.rhythm_profile}")

    if args.mean_pitch_target is not None:
        print(f"\nPitch constraint enabled:")
        print(f"  Target mean pitch: {args.mean_pitch_target:.1f} MIDI")
        print(f"  Tolerance: ±{args.mean_pitch_tolerance:.1f} semitones")
        print(f"  Max attempts: {args.max_attempts}")

    print(f"\nGenerating melody using '{args.method}' method...")

    attempt = 0
    midi_bytes = None
    pitches = None
    durations = None
    score = None
    pitch_stats = None
    debug_stats = None
    enhanced_pitch_stats = None

    while attempt < args.max_attempts:
        attempt += 1

        attempt_seed = seed + attempt - 1

        midi_bytes, pitches, durations, score, pitch_stats, debug_stats, enhanced_pitch_stats = generate_melody_midi(
            harmony_spec,
            args.method,
            attempt_seed,
            generation_config,
            structure_spec
        )

        if args.mean_pitch_target is None:
            break
        elif pitch_stats["mean"] is not None and check_pitch_constraint(
            pitches,
            args.mean_pitch_target,
            args.mean_pitch_tolerance
        ):
            print(f"Constraint satisfied on attempt {attempt}")
            print(f"  Generated mean pitch: {pitch_stats['mean']:.2f}")
            break
        else:
            if pitch_stats["mean"] is not None:
                logging.debug(
                    f"Attempt {attempt}: mean pitch {pitch_stats['mean']:.2f} "
                    f"outside range [{args.mean_pitch_target - args.mean_pitch_tolerance:.2f}, "
                    f"{args.mean_pitch_target + args.mean_pitch_tolerance:.2f}]"
                )

    if args.mean_pitch_target is not None and attempt >= args.max_attempts:
        final_mean = f"{pitch_stats['mean']:.2f}" if pitch_stats and pitch_stats["mean"] is not None else "N/A"
        print(f"\nWarning: Failed to meet pitch constraint after {args.max_attempts} attempts")
        print(f"Final mean pitch: {final_mean}")
        print("Using last generated melody anyway.")

    print(f"Generated {len(pitches)} notes")
    print(f"Quality score: {score:.3f}")

    output_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if batch_index is None:
        base_name = f"melody_{args.method}_seed{seed}_{timestamp}"
    else:
        base_name = f"melody_{args.method}_seed{seed}_{timestamp}_b{batch_index:02d}"

    midi_filename = output_path / f"{base_name}.mid"
    save_midi_file(midi_bytes, str(midi_filename))
    print(f"\nSaved MIDI: {midi_filename}")

    melody_pitches = extract_melody_pitches_from_midi(midi_bytes)
    mean_interval = calculate_mean_interval(melody_pitches)

    metadata = {
        "method": args.method,
        "seed": seed,
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
        "structure": {
            "enabled": structure_spec is not None,
            "repeat_unit_beats": structure_spec.repeat_unit_beats if structure_spec else None,
            "rhythm_profile": structure_spec.rhythm_profile if structure_spec else None,
            "allow_motif_variation": structure_spec.allow_motif_variation if structure_spec else False,
            "variation_probability": structure_spec.variation_probability if structure_spec else 0.0
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
            },
            "avg_pitch": round(enhanced_pitch_stats["avg_pitch"], 2) if enhanced_pitch_stats["avg_pitch"] is not None else None,
            "pitch_min": enhanced_pitch_stats["pitch_min"],
            "pitch_max": enhanced_pitch_stats["pitch_max"],
            "pitch_range": enhanced_pitch_stats["pitch_range"],
            "pitch_std": round(enhanced_pitch_stats["pitch_std"], 2) if enhanced_pitch_stats["pitch_std"] is not None else None,
            "mean_interval": round(mean_interval, 4)
        },
        "debug_stats": {
            "duration_distribution": debug_stats.get("duration_distribution", {}) if debug_stats else {},
            "scale_out_rejections": debug_stats.get("scale_out_rejections", 0) if debug_stats else 0,
            "octave_up_events": debug_stats.get("octave_up_events", 0) if debug_stats else 0,
            "total_beats": debug_stats.get("total_beats", sum(durations)) if debug_stats else sum(durations),
            "repeat_count": debug_stats.get("repeat_count", 0) if debug_stats else 0,
            "actual_duration_distribution": debug_stats.get("actual_duration_distribution", {}) if debug_stats else {}
        }
    }
    if batch_id is not None:
        metadata["batch_id"] = batch_id

    json_filename = output_path / f"{base_name}.json"
    with open(json_filename, 'w') as f:
        json.dump(metadata, f, indent=2)

    print(f"Saved metadata: {json_filename}")

    if render_wav:
        wav_filename = output_path / f"{base_name}.wav"
        if render_midi_to_wav(midi_filename, wav_filename, soundfont_path):
            print(f"Saved WAV: {wav_filename}")

    print("\nGeneration complete!")
    return midi_filename, json_filename


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
    
    parser.add_argument(
        "--repeat-unit-beats",
        type=float,
        default=None,
        help="Repeating unit length in beats (e.g., 4.0 for 1 bar in 4/4). Enables structural repetition."
    )
    
    parser.add_argument(
        "--allow-motif-variation",
        action="store_true",
        help="Allow subtle variations in repeated motifs (default: False)"
    )
    
    parser.add_argument(
        "--variation-probability",
        type=float,
        default=0.3,
        help="Probability of applying variation to repeated motif (0.0-1.0, default: 0.3)"
    )
    
    parser.add_argument(
        "--rhythm-profile",
        type=str,
        default=None,
        help="Target rhythm profile as JSON, e.g., '{\"0.5\": 0.6, \"1.0\": 0.4}' for 60%% eighths, 40%% quarters"
    )

    parser.add_argument(
        "--batch",
        action="store_true",
        help="バッチ生成を有効にする"
    )

    parser.add_argument(
        "--batch-count",
        type=int,
        default=10,
        help="バッチ生成の件数（デフォルト: 10）"
    )

    parser.add_argument(
        "--batch-id",
        type=str,
        default=None,
        help="バッチID（例: 2026-02-16-A）。未指定なら日付+連番で生成"
    )

    parser.add_argument(
        "--render-wav",
        action="store_true",
        help="MIDIからWAVをレンダリングする（要SoundFont）"
    )

    parser.add_argument(
        "--soundfont",
        type=str,
        default=None,
        help="WAVレンダリング用SoundFont(.sf2)のパス"
    )

    args = parser.parse_args()

    if args.batch and args.batch_count < 1:
        parser.error("--batch-countは1以上を指定してください。")

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
    
    # Parse structure spec
    structure_spec = None
    if args.repeat_unit_beats is not None or args.rhythm_profile is not None:
        # Parse rhythm profile if provided
        rhythm_profile = None
        if args.rhythm_profile:
            try:
                rhythm_profile = json.loads(args.rhythm_profile)
                # Convert string keys to float
                rhythm_profile = {float(k): float(v) for k, v in rhythm_profile.items()}
            except (json.JSONDecodeError, ValueError) as e:
                print(f"Warning: Could not parse rhythm profile: {e}")
                print("Continuing without rhythm profile constraint.")
        
        if args.repeat_unit_beats is not None:
            structure_spec = create_structured_spec(
                repeat_unit_beats=args.repeat_unit_beats,
                rhythm_profile=rhythm_profile,
                allow_variation=args.allow_motif_variation,
                variation_prob=args.variation_probability
            )
        elif rhythm_profile is not None:
            # Only rhythm profile, no repetition
            structure_spec = MelodyStructureSpec(
                repeat_unit_beats=None,
                rhythm_profile=rhythm_profile,
                allow_motif_variation=False,
                variation_probability=0.0
            )
    
    if args.batch:
        repo_root = Path(__file__).resolve().parents[1]
        output_root = repo_root / "generated"
        output_root.mkdir(parents=True, exist_ok=True)
        try:
            batch_id = resolve_batch_id(output_root, args.batch_id)
        except (FileExistsError, RuntimeError) as exc:
            parser.error(str(exc))

        output_path = output_root / f"batch_{batch_id}"
        output_path.mkdir(parents=True, exist_ok=True)
        print(f"バッチ生成を開始します: {args.batch_count}件 -> {output_path}")

        for index in range(args.batch_count):
            seed = args.seed + index
            print(f"\n--- バッチ {index + 1}/{args.batch_count} (seed={seed}) ---")
            generate_and_save(
                args,
                seed,
                harmony_config,
                generation_config,
                structure_spec,
                output_path,
                batch_id=batch_id,
                batch_index=index + 1,
                render_wav=args.render_wav,
                soundfont_path=args.soundfont
            )

        print("\nバッチ生成が完了しました。")
        return

    output_path = Path(args.output_dir)
    generate_and_save(
        args,
        args.seed,
        harmony_config,
        generation_config,
        structure_spec,
        output_path,
        render_wav=args.render_wav,
        soundfont_path=args.soundfont
    )


if __name__ == "__main__":
    main()
