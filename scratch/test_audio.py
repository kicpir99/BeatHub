import os
import glob
from mutagen.mp3 import MP3
from mutagen import File as MutagenFile

media_songs = r"e:\beathub_project\media\songs"
files = glob.glob(os.path.join(media_songs, "*.mp3"))

print(f"Znaleziono {len(files)} plików MP3.")

templates = [f for f in files if not os.path.basename(f).startswith(('s_', 'song_'))]
print(f"Testowanie {len(templates)} oryginalnych szablonów...")

results = {"ok": 0, "fail": 0}
for f in templates:
    try:
        audio = MP3(f)
        if audio.info is not None:
            print(f"OK (MP3): {os.path.basename(f)} - {int(audio.info.length)}s")
            results["ok"] += 1
            continue
            
        audio = MutagenFile(f)
        if audio and audio.info:
            print(f"OK (MutagenFile): {os.path.basename(f)} - {int(audio.info.length)}s")
            results["ok"] += 1
        else:
            print(f"FAIL (No info): {os.path.basename(f)}")
            results["fail"] += 1
    except Exception as e:
        print(f"ERROR: {os.path.basename(f)} - {str(e)}")
        results["fail"] += 1

print(f"\nPodsumowanie: OK: {results['ok']}, FAIL: {results['fail']}")
