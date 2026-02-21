from pydub import AudioSegment

def load_wav(path):
    return AudioSegment.from_wav(path)

def export_wav(audio, path):
    audio.export(path, format="wav")
