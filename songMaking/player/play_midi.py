#!/usr/bin/env python3
"""
MIDI playback tool using mido and pygame.midi.

This tool plays back MIDI files with precise timing control, tempo scaling,
and instrument selection.

Installation:
    pip install mido pygame

Usage Examples:
    # Basic playback
    python -m songMaking.player.play_midi input.mid

    # Play with piano (program 0)
    python -m songMaking.player.play_midi input.mid --program 0

    # Play with electric guitar (program 26) at 1.5x speed
    python -m songMaking.player.play_midi input.mid --program 26 --bpm-scale 1.5

    # Play on specific channel with device selection hint
    python -m songMaking.player.play_midi input.mid --channel 0 --device-hint "USB"

    # Slow down to half speed for detailed listening
    python -m songMaking.player.play_midi input.mid --bpm-scale 0.5

Features:
    - Accurate timing using mido's tick2second conversion
    - Tempo scaling via --bpm-scale (1.0 = original, 0.5 = half speed, 2.0 = double speed)
    - Instrument override via --program (0-127)
    - MIDI channel selection via --channel (0-15)
    - Device selection via --device-hint substring matching
    - Handles tempo changes in MIDI file
    - Clean shutdown on Ctrl+C

Requirements:
    - mido: For MIDI file parsing and timing
    - pygame: For MIDI output device access
"""
import argparse
import sys
import time
from pathlib import Path

try:
    import mido
except ImportError:
    print("Error: mido is not installed.", file=sys.stderr)
    print("Install with: pip install mido", file=sys.stderr)
    sys.exit(1)

try:
    import pygame.midi
except ImportError:
    print("Error: pygame is not installed.", file=sys.stderr)
    print("Install with: pip install pygame", file=sys.stderr)
    sys.exit(1)


def list_midi_devices():
    """
    List available MIDI output devices.
    
    Note: pygame.midi must be initialized before calling this function.
    
    Returns:
        list: List of tuples (device_id, device_info)
    """
    devices = []
    
    for i in range(pygame.midi.get_count()):
        info = pygame.midi.get_device_info(i)
        # info = (interf, name, input, output, opened)
        # We only care about output devices
        if info[3]:  # if output
            devices.append((i, info))
    
    return devices


def find_output_device(hint: str = None):
    """
    Find a suitable MIDI output device.
    
    Note: pygame.midi must be initialized before calling this function.
    
    Args:
        hint: Optional substring to match in device name
        
    Returns:
        int: Device ID
        
    Raises:
        RuntimeError: If no suitable device found
    """
    devices = list_midi_devices()
    
    if not devices:
        raise RuntimeError("No MIDI output devices available")
    
    # If hint provided, try to match it
    if hint:
        for device_id, info in devices:
            device_name = info[1].decode('utf-8')
            if hint.lower() in device_name.lower():
                print(f"Using MIDI device: {device_name}")
                return device_id
        
        print(f"Warning: No device matching '{hint}' found, using default", file=sys.stderr)
    
    # Use default device
    default_id = pygame.midi.get_default_output_id()
    
    if default_id == -1:
        # Fallback to first available device
        device_id = devices[0][0]
        device_name = devices[0][1][1].decode('utf-8')
        print(f"Using MIDI device: {device_name}")
        return device_id
    
    # Find and print default device name
    for device_id, info in devices:
        if device_id == default_id:
            device_name = info[1].decode('utf-8')
            print(f"Using MIDI device: {device_name}")
            return default_id
    
    # Should not reach here, but just in case
    return default_id


def play_midi(
    midi_path: str,
    program: int = 0,
    bpm_scale: float = 1.0,
    channel: int = 0,
    device_hint: str = None
):
    """
    Play a MIDI file with specified parameters.
    
    Args:
        midi_path: Path to MIDI file
        program: MIDI program number (0-127) for instrument
        bpm_scale: Tempo scaling factor (1.0 = original, 2.0 = double speed)
        channel: MIDI channel (0-15)
        device_hint: Optional device name substring for device selection
        
    Raises:
        FileNotFoundError: If MIDI file doesn't exist
        RuntimeError: If no MIDI output device available
    """
    # Check file exists
    if not Path(midi_path).exists():
        raise FileNotFoundError(f"MIDI file not found: {midi_path}")
    
    # Initialize pygame.midi and open output device
    pygame.midi.init()
    midi_out = None
    
    try:
        # Find output device (must be after pygame.midi.init())
        device_id = find_output_device(device_hint)
        
        midi_out = pygame.midi.Output(device_id)
        
        # Load MIDI file
        mid = mido.MidiFile(midi_path)
        
        print(f"\nPlaying: {midi_path}")
        print(f"Program: {program} (channel {channel})")
        print(f"Tempo scale: {bpm_scale}x")
        print(f"Type: {mid.type}, Ticks per beat: {mid.ticks_per_beat}")
        print("\nPress Ctrl+C to stop\n")
        
        # Set program (instrument) on the channel
        midi_out.set_instrument(program, channel)
        
        # Current tempo in microseconds per beat (default 120 BPM = 500000 us/beat)
        current_tempo = 500000
        
        # Play all tracks
        for i, track in enumerate(mid.tracks):
            # Extract track name from meta messages if present
            track_name = None
            for msg in track:
                if msg.type == 'track_name':
                    track_name = msg.name
                    break
            
            display_name = track_name if track_name else 'unnamed'
            print(f"Track {i}: {display_name}")
            
            for msg in track:
                # Convert ticks to seconds
                delta_seconds = mido.tick2second(
                    msg.time,
                    mid.ticks_per_beat,
                    current_tempo
                )
                
                # Apply tempo scaling by adjusting sleep duration
                # bpm_scale > 1.0: faster playback, dividing shortens sleep time
                # bpm_scale < 1.0: slower playback, dividing by value < 1.0 increases sleep time
                sleep_time = delta_seconds / bpm_scale
                
                if sleep_time > 0:
                    time.sleep(sleep_time)
                
                # Handle tempo changes
                if msg.type == 'set_tempo':
                    current_tempo = msg.tempo
                    actual_bpm = mido.tempo2bpm(msg.tempo) * bpm_scale
                    print(f"  Tempo change: {actual_bpm:.1f} BPM (scaled)")
                
                # Send note messages (override channel with our parameter)
                elif msg.type == 'note_on':
                    midi_out.note_on(msg.note, msg.velocity, channel)
                
                elif msg.type == 'note_off':
                    midi_out.note_off(msg.note, msg.velocity, channel)
                
                # Ignore program_change from file since we prefer --program parameter
                elif msg.type == 'program_change':
                    pass  # Already set via set_instrument
                
                # Handle other control messages on specified channel
                elif msg.type == 'control_change':
                    midi_out.write_short(0xB0 | channel, msg.control, msg.value)
                
                elif msg.type == 'pitchwheel':
                    # Pitchwheel is 14-bit (0-16383), centered at 8192
                    midi_out.pitch_bend(msg.pitch, channel)
        
        print("\nPlayback complete.")
    
    except KeyboardInterrupt:
        print("\n\nPlayback interrupted by user.")
    
    except Exception as e:
        print(f"\nPlayback error: {e}", file=sys.stderr)
        raise
    
    finally:
        # Clean shutdown
        if midi_out:
            # Send All Notes Off (CC 123) to prevent stuck notes
            # More efficient than sending 128 individual note_off messages
            midi_out.write_short(0xB0 | channel, 123, 0)
            
            del midi_out
        
        pygame.midi.quit()


def main():
    """CLI entry point for MIDI playback."""
    parser = argparse.ArgumentParser(
        description="Play MIDI files with tempo and instrument control",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s song.mid
  %(prog)s song.mid --program 0 --bpm-scale 1.5
  %(prog)s song.mid --channel 0 --device-hint "USB"
  
Available MIDI programs (General MIDI):
  0 = Acoustic Grand Piano    24 = Acoustic Guitar (nylon)
  1 = Bright Acoustic Piano    25 = Acoustic Guitar (steel)
  4 = Electric Piano 1         26 = Electric Guitar (jazz)
  16 = Drawbar Organ           33 = Acoustic Bass
  40 = Violin                  48 = String Ensemble 1
  56 = Trumpet                 73 = Flute
  
  (See General MIDI spec for full list of 128 programs)
"""
    )
    
    parser.add_argument(
        "midi_file",
        type=str,
        nargs='?',  # Make it optional
        help="Path to MIDI file to play"
    )
    
    parser.add_argument(
        "--program",
        type=int,
        default=0,
        help="MIDI program number 0-127 (default: 0 = Acoustic Grand Piano)"
    )
    
    parser.add_argument(
        "--bpm-scale",
        type=float,
        default=1.0,
        help="Tempo scaling factor (default: 1.0). Use 2.0 for double speed, 0.5 for half speed"
    )
    
    parser.add_argument(
        "--channel",
        type=int,
        default=0,
        help="MIDI channel 0-15 (default: 0)"
    )
    
    parser.add_argument(
        "--device-hint",
        type=str,
        default=None,
        help="Substring to match in MIDI device name (e.g., 'USB', 'Synth')"
    )
    
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="List available MIDI output devices and exit"
    )
    
    args = parser.parse_args()
    
    # Handle --list-devices
    if args.list_devices:
        print("Available MIDI output devices:")
        pygame.midi.init()
        try:
            devices = list_midi_devices()
            
            if not devices:
                print("  (none)")
            else:
                for device_id, info in devices:
                    # info = (interf, name, input, output, opened)
                    device_name = info[1].decode('utf-8')
                    interface = info[0].decode('utf-8')
                    print(f"  [{device_id}] {device_name} ({interface})")
        finally:
            pygame.midi.quit()
        
        return
    
    # Require midi_file if not listing devices
    if not args.midi_file:
        print("Error: midi_file is required (use --list-devices to list devices)", file=sys.stderr)
        parser.print_usage()
        sys.exit(1)
    
    # Validate arguments
    if args.program < 0 or args.program > 127:
        print("Error: --program must be between 0 and 127", file=sys.stderr)
        sys.exit(1)
    
    if args.channel < 0 or args.channel > 15:
        print("Error: --channel must be between 0 and 15", file=sys.stderr)
        sys.exit(1)
    
    if args.bpm_scale <= 0:
        print("Error: --bpm-scale must be positive", file=sys.stderr)
        sys.exit(1)
    
    # Play MIDI file
    try:
        play_midi(
            midi_path=args.midi_file,
            program=args.program,
            bpm_scale=args.bpm_scale,
            channel=args.channel,
            device_hint=args.device_hint
        )
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
