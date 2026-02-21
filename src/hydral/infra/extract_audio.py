import subprocess
from pathlib import Path

def extract_audio_mp3(video_path: str, out_path: str, bitrate="192k"):
    video = Path(video_path)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg", "-y", "-i", str(video),
        "-vn",
        "-ar", "44100",          # サンプルレート
        "-ac", "2",              # チャンネル（必要なら1に）
        "-b:a", bitrate,         # ビットレート
        str(out)
    ]
    subprocess.run(cmd, check=True)

extract_audio_mp3("20260211.mov", "output.mp3")
