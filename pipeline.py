from core.io import load_wav, export_wav
from core.grain import split_grains
from core.transform import shuffle, extreme_pan, dynamics_pan, state_pan,random_state_pan
from core.assemble import concat
from pathlib import Path
import random

#  An alternative pipeline that only shuffles grains without assempling
def hydral_pipeline(
        input_wav,
        output_wav,
        is_assemble,
        grain_sec,
        seed,
        is_extra_pan=False
):
    audio = load_wav(input_wav)
    grains = split_grains(audio, int(grain_sec * 1000))
    grains = shuffle(grains, seed=seed)

    if is_extra_pan:
        grains = state_pan(grains)

    if is_assemble:
        out = concat(grains)
        export_wav(out, output_wav)
    else:
        out_dir = Path(f"{output_wav}_grains")
        out_dir.mkdir(parents=True, exist_ok=True)

        for i, g in enumerate(grains):
            export_wav(g, out_dir / f"grain_{i}.wav")

# A simple pipeline that reverses the entire audio
def reverse_audio_pipeline(
        input_wav,
        output_wav
):
    audio = load_wav(input_wav)
    reversed_audio = audio.reverse()
    export_wav(reversed_audio, output_wav)
    print(f"Reversed audio saved to {output_wav}")

# A simple pipeline that applies random panning to the audio
def random_pan_pipeline(
        input_wav,
        output_wav
):
    from pydub.effects import pan

    audio = load_wav(input_wav)
    panned_audio = pan(audio, random.choice([-1.0,1.0]))
    export_wav(panned_audio, output_wav)
    print(f"Panned audio saved to {output_wav}")


if __name__ == "__main__":
    # ここに「今やりたい処理」だけを書く
    random_pan_pipeline(
        "data/raw/recorded.wav",
        "/mnt/c/hydral/outputs/panned.wav",
    )