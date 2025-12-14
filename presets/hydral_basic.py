# presets/hydral_basic.py
from pipeline import hydral_pipeline

def run():
    hydral_pipeline(
        "data/raw/recorded.wav",
        "/mnt/c/hydral/outputs/hydral_basic_2025_12_14.wav",
        is_assemble=True,
        grain_sec=0.08,
        seed=1234,
        is_extra_pan=True
    )

if __name__ == "__main__":
    run()