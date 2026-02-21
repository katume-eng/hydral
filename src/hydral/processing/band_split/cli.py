"""
Command-line interface for band splitting.

Usage:
    python -m processing.band_split.cli --input <path/to/audio.wav>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .split import DEFAULT_BANDS, split_into_bands


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Split audio into frequency bands and tonal/noise components"
    )
    
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Path to input WAV file"
    )
    
    parser.add_argument(
        "--out-root",
        type=Path,
        default=Path("data/processed/band_split/v1"),
        help="Output root directory (default: data/processed/band_split/v1)"
    )
    
    parser.add_argument(
        "--bands",
        type=str,
        help="Custom band definitions as JSON string or path to JSON file"
    )
    
    parser.add_argument(
        "--sr",
        type=int,
        help="Target sample rate for processing (default: use original)"
    )
    
    parser.add_argument(
        "--mono",
        action="store_true",
        help="Convert to mono before processing"
    )
    
    parser.add_argument(
        "--filter-order",
        type=int,
        default=5,
        help="Butterworth filter order (default: 5)"
    )
    
    parser.add_argument(
        "--hpss-kernel",
        type=int,
        default=31,
        help="HPSS kernel size (default: 31)"
    )
    
    parser.add_argument(
        "--hpss-margin",
        type=float,
        default=2.0,
        help="HPSS margin for soft masking (default: 2.0)"
    )
    
    args = parser.parse_args()
    
    # Validate input file exists
    if not args.input.exists():
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)
    
    # Parse custom bands if provided
    bands = None
    if args.bands:
        # Check if it's a file path
        bands_path = Path(args.bands)
        if bands_path.exists():
            with open(bands_path, "r", encoding="utf-8") as f:
                bands = json.load(f)
        else:
            # Try to parse as JSON string
            try:
                bands = json.loads(args.bands)
            except json.JSONDecodeError as e:
                print(f"Error: Invalid JSON for --bands: {e}", file=sys.stderr)
                sys.exit(1)
    
    # Determine output directory
    input_stem = args.input.stem
    output_dir = args.out_root / input_stem
    
    print(f"Processing: {args.input}")
    print(f"Output directory: {output_dir}")
    if bands:
        print(f"Using custom bands: {json.dumps(bands, indent=2)}")
    else:
        print(f"Using default bands")
    
    # Run the splitting process
    try:
        manifest = split_into_bands(
            input_path=args.input,
            output_dir=output_dir,
            bands=bands,
            target_sr=args.sr,
            mono=args.mono,
            filter_order=args.filter_order,
            hpss_kernel_size=args.hpss_kernel,
            hpss_margin=args.hpss_margin,
        )
        
        print(f"\n✓ Processing complete!")
        print(f"  - Generated {len(manifest['outputs'])} output files")
        print(f"  - Manifest: {output_dir / 'split_manifest.json'}")
        
        # Show output files
        print(f"\nOutput files:")
        for output in manifest['outputs']:
            print(f"  - {output['path']} ({output['band_id']}, {output['component']})")
        
    except Exception as e:
        print(f"Error during processing: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
