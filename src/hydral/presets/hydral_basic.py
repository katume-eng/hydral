# presets/hydral_basic.py
from pipelines.audio_pipeline import hydral_pipeline
from src.hydral.routes import PATH

def run():
    hydral_pipeline(
        input_wav=PATH["input_wav"],
        output_wav=PATH["output_wav"],
        is_assemble=True,
        grain_sec=0.08,
        seed=1234,
        is_extra_pan=True
    )

if __name__ == "__main__":
    run()

