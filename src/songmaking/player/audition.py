"""
Interactive audition system for MIDI fragments.
Generates fragments and attempts playback using pygame.midi if available.
"""
import argparse
import sys
from pathlib import Path
import pretty_midi

from songmaking.export.concat_fragments import export_concatenated_fragments


def check_pygame_midi():
    """
    Check if pygame.midi is available for playback.
    
    Returns:
        True if pygame.midi is available, False otherwise
    """
    try:
        import pygame.midi
        return True
    except ImportError:
        return False


def play_midi_file(midi_path: str):
    """
    Play a MIDI file using pygame.midi if available.
    
    Args:
        midi_path: Path to MIDI file to play
    """
    # Import pygame modules locally since they're optional dependencies
    try:
        import pygame
        import pygame.midi
        import time
        
        # Initialize pygame.midi
        pygame.midi.init()
        
        # Get default output device
        port = pygame.midi.get_default_output_id()
        midi_out = pygame.midi.Output(port)
        
        print(f"\nPlaying: {midi_path}")
        print("(Playback via pygame.midi - press Ctrl+C to stop)")
        
        # Load and parse MIDI file
        pm = pretty_midi.PrettyMIDI(midi_path)
        
        # Simple playback: send all notes with timing
        all_events = []
        
        for instrument in pm.instruments:
            for note in instrument.notes:
                # Note on event
                all_events.append((note.start, 'note_on', note.pitch, note.velocity))
                # Note off event
                all_events.append((note.end, 'note_off', note.pitch, 0))
        
        # Sort events by time
        all_events.sort(key=lambda x: x[0])
        
        # Play events
        start_time = time.time()
        
        for event_time, event_type, pitch, velocity in all_events:
            # Wait until event time
            current_time = time.time() - start_time
            wait_time = event_time - current_time
            
            if wait_time > 0:
                time.sleep(wait_time)
            
            # Send MIDI event
            if event_type == 'note_on':
                midi_out.note_on(pitch, velocity)
            elif event_type == 'note_off':
                midi_out.note_off(pitch, velocity)
        
        # Clean up
        del midi_out
        pygame.midi.quit()
        
        print("Playback complete.")
        
    except Exception as e:
        print(f"Playback error: {e}")
        print("MIDI file saved but playback failed.")


def interactive_audition(
    method: str,
    seed: int,
    n_fragments: int,
    bars: int,
    gap_beats: float,
    config: dict,
    out_path: str
):
    """
    Generate fragments and optionally play them interactively.
    
    Args:
        method: Melody generation method
        seed: Base random seed
        n_fragments: Number of fragments to generate
        bars: Bars per fragment
        gap_beats: Gap between fragments in beats
        config: Configuration dict with constraints
        out_path: Output base path
    """
    # Check if pygame.midi is available
    has_pygame = check_pygame_midi()
    
    if not has_pygame:
        print("Note: pygame.midi is not available.")
        print("Fragments will be generated and exported, but playback is unavailable.")
        print("You can play the exported MIDI file with an external player.\n")
    
    # Generate and export fragments
    export_concatenated_fragments(
        out_path=out_path,
        harmony="auto",
        method=method,
        seed=seed,
        config=config,
        n_fragments=n_fragments,
        bars=bars,
        gap_beats=gap_beats
    )
    
    midi_path = f"{out_path}.mid"
    
    # Attempt playback if available
    if has_pygame:
        print("\n" + "="*60)
        response = input("Play generated MIDI? (y/n): ").strip().lower()
        
        if response == 'y':
            play_midi_file(midi_path)
        else:
            print("Playback skipped.")
    else:
        print(f"\nTo listen, open {midi_path} in your MIDI player.")


def main():
    """CLI entry point for interactive audition."""
    parser = argparse.ArgumentParser(
        description="Interactive MIDI fragment audition with optional playback"
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
    
    # Run interactive audition
    interactive_audition(
        method=args.method,
        seed=args.seed,
        n_fragments=args.n_fragments,
        bars=args.bars,
        gap_beats=args.gap_beats,
        config=config,
        out_path=str(out_path)
    )
    
    print("\nAudition complete!")


if __name__ == "__main__":
    main()
