import os
import shutil

src_dir = r"d:\Projekt"
dest_dir = r"d:\Projekt\BeatHub_Upload"

if os.path.exists(dest_dir):
    shutil.rmtree(dest_dir)
os.makedirs(dest_dir)

def ignore_patterns(path, names):
    ignored = set()
    for name in names:
        if name in ('venv', '__pycache__', '.git', 'scratch', 'db.sqlite3', '.env', '.tempmediaStorage', 'BeatHub_Upload'):
            ignored.add(name)
        elif name.endswith('.pyc'):
            ignored.add(name)
        # Handle specific media exclusions
        elif os.path.basename(path) == 'media' and name in ('artists', 'albums', 'avatars'):
            ignored.add(name)
        # Exclude generated songs, allow base templates and genres
        elif os.path.basename(path) == 'songs' and name.endswith('.mp3') and (name.startswith('song_') or name.startswith('s_')):
            ignored.add(name)
    return ignored

for item in os.listdir(src_dir):
    if item in ('venv', '__pycache__', '.git', 'scratch', 'db.sqlite3', '.env', '.tempmediaStorage', 'BeatHub_Upload'):
        continue
    
    s = os.path.join(src_dir, item)
    d = os.path.join(dest_dir, item)
    
    if os.path.isdir(s):
        shutil.copytree(s, d, ignore=ignore_patterns)
    else:
        shutil.copy2(s, d)

print("Kopiowanie zakończone!")
