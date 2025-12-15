# presets/hydral_basic.py
from pipelines.audio_pipeline import hydral_pipeline
from routes import Path

def run():
    hydral_pipeline(
        input_wav=Path["input_wav"],
        output_wav=Path["output_wav"],
        is_assemble=True,
        grain_sec=0.08,
        seed=1234,
        is_extra_pan=True
    )

if __name__ == "__main__":
    run()